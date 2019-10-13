import argparse
import os
import psycopg2
import pytz
import re
import requests
import socket
import subprocess
import sys
import threading
import time
import traceback
from collections import defaultdict
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from inspect import getframeinfo, stack
from mail import send_mail
from messages import MessageParameters, IntervalType, MessageType, IQfeedMessage
from yahoo_earnings_calendar import YahooEarningsCalendar

fromaddr = os.environ['FROM_ADDR']
password = os.environ['EMAIL_PASSWORD']
subject = "Sentinel Alert"
app_token = os.environ['APP_TOKEN']
app_user = os.environ['APP_USER']
iqfeed_host = "127.0.0.1"
local_tz = pytz.timezone("America/New_York")
data_limit = '4000'
requires_date_format = {"1day", "1week", "1d", "7d"}
stock_tables = ["5min", "15min", "60min", "4hour", "1day", "1week"]
yec = YahooEarningsCalendar()
begin_time = "09:30:00"
end_time = "16:00:00"
connector = ", "
line_braker = "<br>"
interval_5min = set(["5min", "5m"])
interval_1day = set(["1day", "1d"])
interval_weekly = set(["1week", "1w"])
daily_intervals = set([1, 7])
volume_data_points = 50
friday_weekday = 4
live_port = 9400
historic_port = 9100
indices = {
    'historic': {
        'request_id': 0,
        'end_time': 1,
        'high': 2,
        'low': 3,
        'open': 4,
        'close': 5,
        'period_volume': 6,
    },
    'live': {
        'request_id': 0,
        'type': 1,
        'ticker': 2,
        'end_time': 3,
        'open': 4,
        'high': 5,
        'low': 6,
        'close': 7,
    }
}
iqfeed_daylight_adjustment = defaultdict(relativedelta, {
    "5min": relativedelta(minutes=5),
    "15min": relativedelta(minutes=15),
    "60min": relativedelta(minutes=60)})
expected_format = {
    IntervalType.SECONDS: "%Y%m%d %H%M%S",
    IntervalType.DAILY: "%Y%m%d"
}
interval_in_seconds = {
    5: "300",
    15: "900",
    60: "3600",
    240: "14400"
}
interval_map = {"5m": "5min", "15m": "15min", "60m": "60min", "4h": "4hour", "1d": "1day", "1w": "1week", None: None}


class TimeframeInfo(object):
    def __init__(self, table_name, interval_type, start_time, relative_delta):
        self.table_name = table_name
        self.interval_type = interval_type
        self.start_time = start_time
        self.relative_delta = relative_delta


tf_info_5m = TimeframeInfo("5min", IntervalType.SECONDS, datetime(2018, 4, 1, 20, 30, 0), relativedelta(minutes=5))
tf_info_15m = TimeframeInfo("15min", IntervalType.SECONDS, datetime(2018, 3, 4, 20, 30, 0), relativedelta(minutes=15))
tf_info_60m = TimeframeInfo("60min", IntervalType.SECONDS, datetime(2017, 10, 15, 20, 30, 0), relativedelta(hours=1))
tf_info_4h = TimeframeInfo("4hour", IntervalType.SECONDS, datetime(2016, 5, 8, 20, 30, 0), relativedelta(hours=4))
tf_info_1d = TimeframeInfo("1day", IntervalType.DAILY, datetime(2015, 1, 1, 0, 0, 0).date(), relativedelta())
tf_info_1w = TimeframeInfo("1week", IntervalType.DAILY, datetime(2012, 1, 1, 0, 0, 0).date(), relativedelta())
timeframe_info = {
    5: tf_info_5m,
    15: tf_info_15m,
    60: tf_info_60m,
    240: tf_info_4h,
    "1d": tf_info_1d,
    "7d": tf_info_1w,
    "5min": tf_info_5m,
    "15min": tf_info_15m,
    "60min": tf_info_60m,
    "4hour": tf_info_4h,
    "1day": tf_info_1d,
    "7day": tf_info_1w,
}
signal_data_id = {
    'ticker_id': 0,
    'interval': 1,
    'type': 2,
    'second': 3,
    'sma_cross': 4,
    'bungee_values_yellow': 5,
    'bungee_values_green': 6,
    'bungee_values_blue': 7,
    'bungee_values_red': 8
}
green = 'Green'
yellow = 'Yellow'
red = 'Red'
dash = '-'
primary_type_map = {0: green, 1: yellow, 2: red}
sma_cross_map = {True: red, False: green}
rsi_threshold_map = {1: green, 2: red, 0: dash}


class Signals:
    def __init__(self, primary_type, primary_age, secondary, sma_cross, bungee_y, bungee_g, bungee_b, bungee_r, rsi_threshold):
        self.primary_type = primary_type
        self.primary_age = primary_age
        self.secondary = secondary
        self.sma_cross = bool(sma_cross) if type(sma_cross) is int else sma_cross
        self.bungee_y = bungee_y
        self.bungee_g = bungee_g
        self.bungee_b = bungee_b
        self.bungee_r = bungee_r
        self.rsi_threshold = rsi_threshold

    def __repr__(self):
        return "Primary_type: {} ({} bars), Secondary: {}, SMA cross: {}, RSI: {}, Bungees: (y: {}, g: {}, b: {}, r: {}) "\
            .format(self.primary_type, self.primary_age, self.secondary, self.sma_cross, self.rsi_threshold,
                    self.bungee_y, self.bungee_g, self.bungee_b, self.bungee_r)

    def to_message(self, interval):
        return "{}:{}, SMA cross: {}, Bungees: (yellow: {}, green: {}, blue: {}, red: {})"\
            .format(interval, primary_type_map[self.primary_type], sma_cross_map[self.sma_cross], self.bungee_y,
                    self.bungee_g, self.bungee_b, self.bungee_r)

    def to_dial_notification_message(self, interval):
        return "{}:{} ({} Bars)"\
            .format(interval, primary_type_map[self.primary_type], self.primary_age)

    def to_bungee_notification_message(self, interval):
        return "{}:{}, SMA cross: {}, Bungees: (yellow: {}, green: {}, blue: {}, red: {})"\
            .format(interval, primary_type_map[self.primary_type], sma_cross_map[self.sma_cross], self.bungee_y,
                    self.bungee_g, self.bungee_b, self.bungee_r)

    def to_bolt_notification_message(self, interval):
        return "{}:{}, Bolt: {}"\
            .format(interval, primary_type_map[self.primary_type], rsi_threshold_map[self.rsi_threshold])

    def to_sma_cross_notification_message(self, interval):
        return "{}:{}, SMA Cross: {}"\
            .format(interval, primary_type_map[self.primary_type], sma_cross_map[self.sma_cross])


class TickerSignalData:
    def __init__(self):
        self.interval_dict = {}
        self.price = 0

    def add(self, ticker_id, interval, primary_type, primary_age, secondary, sma_cross, bungee_y, bungee_g, bungee_b, bungee_r, rsi_threshold):
        self.interval_dict[interval] = \
            Signals(primary_type, primary_age, secondary, sma_cross, bungee_y, bungee_g, bungee_b, bungee_r, rsi_threshold)

    def has_interval_signals(self, interval):
        return interval in self.interval_dict

    def get_interval_signals(self, interval):
        return self.interval_dict[interval]

    def to_message(self, new_line):
        return new_line.join(self.get_interval_signals(interval).to_message(interval)
                             for interval in stock_tables if self.has_interval_signals(interval))

    def to_dial_notification_message(self, new_line):
        return new_line.join(self.get_interval_signals(interval).to_dial_notification_message(interval)
                             for interval in stock_tables if self.has_interval_signals(interval))

    def to_bungee_notification_message(self, new_line):
        return new_line.join(self.get_interval_signals(interval).to_bungee_notification_message(interval)
                             for interval in stock_tables if self.has_interval_signals(interval))

    def to_bolt_notification_message(self, new_line):
        return new_line.join(self.get_interval_signals(interval).to_bolt_notification_message(interval)
                             for interval in stock_tables if self.has_interval_signals(interval))

    def to_sma_cross_notification_message(self, new_line):
        return new_line.join(self.get_interval_signals(interval).to_sma_cross_notification_message(interval)
                             for interval in stock_tables if self.has_interval_signals(interval))

    def set_price(self, price):
        self.price = price

    def __repr__(self):
        return "\n".join(k + ' ' + repr(v) for k, v in self.interval_dict.items())


class SignalData:
    def __init__(self):
        self.ticker_dict = defaultdict(TickerSignalData)

    def add(self, ticker_signal_data):
        self.ticker_dict[ticker_signal_data[signal_data_id['ticker_id']]].add(*ticker_signal_data)
        return self

    def add_all(self, ticker_signal_data_list, price_map):
        for ticker_signal_data in ticker_signal_data_list:
            self.add(ticker_signal_data)
        for ticker_id, ticker_signal in self.ticker_dict.items():
            ticker_signal.set_price(price_map.get(ticker_id))
        return self

    def has_ticker_signals(self, ticker_id):
        return ticker_id in self.ticker_dict

    def get_ticker_signals(self, ticker_id):
        return self.ticker_dict[ticker_id]

    def __repr__(self):
        temp_list = []
        for k, v in self.ticker_dict.items():
            temp_list.append("Ticker id: " + str(k))
            temp_list.append(repr(v))
        return "\n".join(temp_list)


class NotificationData:
    def __init__(self):
        self.notification_sent = None
        self.bungee_settings = None
        self.ticker_notifications = None
        self.global_notifications = None

    def get_notification_sent(self):
        return self.notification_sent

    def set_notification_sent(self, notification_sent):
        self.notification_sent = notification_sent
        return self

    def get_bungee_settings(self):
        return self.bungee_settings

    def set_bungee_settings(self, bungee_settings):
        self.bungee_settings = bungee_settings
        return self

    def get_ticker_notifications(self):
        return self.ticker_notifications

    def has_ticker_notification_setting(self, ticker_id):
        return ticker_id in self.ticker_notifications

    def get_ticker_notification_setting(self, ticker_id):
        return self.ticker_notifications[ticker_id]

    def set_ticker_notifications(self, ticker_notifications):
        self.ticker_notifications = ticker_notifications
        return self

    def get_global_notifications(self):
        return self.global_notifications

    def set_global_notifications(self, global_notifications):
        self.global_notifications = global_notifications
        return self


class Util:

    def __init__(self, socket_connection=True, args=None, auto_commit=False):
        self.args = self.parse_arguments() if args is None else args
        self.__at_start()
        self.conn = None
        self.__init_database(auto_commit)
        self.sock = self.get_iqfeed_socket_connection(socket_connection)
        self.notification_data = None
        self.notification_is_sent = set()
        self.remove_notification_sent = set()
        self.dev_email = os.environ['DEV_EMAIL']

    def __init_database(self, auto_commit):
        if self.args.db_connection:
            self.conn = self.__get_db_connection()
            self.conn.autocommit = auto_commit
            self.cursor = self.conn.cursor()
            self.tickers, self.tickers_id = self.__get_tickers()
            self.reverse_tickers_id = {v: k for k, v in self.tickers_id.items()}
            self.ticker_to_users = self.__get_ticker_user_dict()
            self.user_details = self.__get_user_details()

    def parse_arguments(self):
        self.parser = argparse.ArgumentParser()
        return self.__parse_arguments(self.parser)

    def get_iqfeed_socket_connection(self, need_socket_connection):
        if need_socket_connection and self.args.update_tickers:
            return self.__get_iqfeed_socket_connection()
        return None

    def set_arguments(self, args):
        self.args = args

    def print_arguments(self):
        self.parser.print_help()

    def print_arguments_and_exit(self):
        self.parser.print_help(sys.stderr)
        sys.exit(1)

    @staticmethod
    def add_bool_arg(parser, name, default=False):
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument('--' + name, dest=name, action='store_true')
        group.add_argument('--no-' + name, dest=name, action='store_false')
        parser.set_defaults(**{name:default})

    @staticmethod
    def __parse_arguments(parser):
        parser.add_argument("-a", "--datapoints_per_second", type=str, default="200",
                            help="Max datapoints to fetch from iqfeed per second")
        parser.add_argument("-b", "--start_time", type=str, default="",
                            help="Force start time from where to fetch data")
        parser.add_argument("-c", "--csv", action="store_true", default=False, help="Store data in csv files")
        parser.add_argument("-d", "--debug", action="store_true", default=False, help="Run in a debug mode")
        parser.add_argument("-e", "--dev", action="store_true", default=False, help="Developer mode")
        parser.add_argument("-f", "--fetch", action="store_true", default=False,
                            help="Just fetch data and do not store in database")
        parser.add_argument("-g", "--update_tickers", action="store_true", default=False,
                            help="Fetch new data. Store or not to store in database will be decided flag fetch.")
        parser.add_argument("-i", "--daily", type=int, nargs="+", default=[],
                            help="Daily or weekly interval. The value can be 1 or 7")
        parser.add_argument("-k", "--tick_interval", action="store_true", default=False,
                            help="Set this for fetching tick intervals. Fetches seconds interval when not set.")
        parser.add_argument("-l", "--delay", action="store_true", default=False,
                            help="Run cron with a delay of 2 minutes")
        parser.add_argument("-m", "--email", type=str, default=fromaddr, help="Notification email address")
        parser.add_argument("-n", "--new", action="store_true", default=False, help="Run cron for new ticker")
        parser.add_argument("-o", "--historic", action="store_true", default=True, help="Fetch historic data")
        parser.add_argument("-p", "--prints", action="store_true", default=False, help="Print everything")
        parser.add_argument("-q", "--table_name", type=str, default="stocks_iqfeedstatus", help="IQfeed status table")
        parser.add_argument("-r", "--version", type=str, default="6.0.0.5", help="IQfeed version")
        parser.add_argument("-s", "--update_signals", action="store_true", default=False, help="Update signal data.")
        parser.add_argument("-t", "--timeframes", type=int, nargs="+", default=[], help="Time frames to fetch")
        parser.add_argument("-u", "--cut", type=int, default=0, help="Cut to number of tickers")
        parser.add_argument("-v", "--token", type=str, default="", help="Authorization token of user")
        parser.add_argument("-w", "--wait", action="store_true", default=False, help="Wait for input")
        parser.add_argument("-x", "--force4hr", action="store_true", default=False,
                            help="Force 4 hour timeframe to load")
        parser.add_argument("-y", "--update_earning_date", action="store_true", default=False,
                            help="Update earning date from yahoo api")
        parser.add_argument("-z", "--tickers", type=str, nargs="+", default=[],
                            help="List of tickers to load. If not provided loads all tickers.")
        Util.add_bool_arg(parser, 'db_connection', default=True)
        try:
            args = parser.parse_args()
            if args.prints:
                args.debug = True
            return args
        except IOError as msg:
            parser.error(str(msg))

    def __at_start(self):
        if self.args.debug or self.args.dev:
            print(
                "Dev:{0}\tDebug:{1}\t{2} mode"
                .format(self.args.dev, self.args.debug, "Historic" if self.args.historic else "Live"))
        if self.args.delay:
            time.sleep(120)
            self.log("delay for 2 minutes")

    def __get_db_connection(self):
        return psycopg2.connect(host=os.environ['DB_HOST'],
                                user=os.environ['DB_USER'],
                                password=os.environ['DB_PASSWORD'],
                                dbname=os.environ['DB_NAME'])

    def __get_tickers(self):
        tickers = self.query_select('''select ticker, id from stocks_tickers where is_active = true order by id''')
        tickers_list = []
        tickers_id = {}
        for ticker in tickers:
            tickers_list.append(ticker[0])
            tickers_id[ticker[0]] = ticker[1]
        if self.args.cut:
            tickers_list = tickers_list[:self.args.cut]
        if self.args.tickers:
            tickers_list = self.args.tickers
        temp_ticker_set = set(tickers_list)
        return tickers_list, {k: v for k, v in tickers_id.items() if temp_ticker_set}

    def __get_iqfeed_socket_connection(self):
        if self.__is_iqfeed_running():
            if self.args.debug:
                print("IQFeed is already running")
        else:
            self.start_iqfeed()
        return self.__connect_to_socket(iqfeed_host, historic_port if self.args.historic else live_port)

    def establish_iqfeed_socket_connection(self):
        self.sock = self.__get_iqfeed_socket_connection() if self.sock is None else self.sock

    @staticmethod
    def __is_iqfeed_running():
        is_running = subprocess.Popen('pgrep iqfeed && echo Running',
                                      shell=True,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        (out, err) = is_running.communicate()

        if err.decode('ascii'):
            print(err.decode('ascii'))
            raise SystemError('Shell command "pgrep iqfeed && echo Running" failed!')
        return 'Running' in out.decode('ascii')

    def start_iqfeed(self):
        try:
            self.print_msg('Received a request to start IQFeed')
            p = subprocess.Popen(['sudo', '-S'] + os.environ['MOUNT_COMMAND'].split(),
                                 stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True)
            sudo_prompt = p.communicate(os.environ['USER_PASSWORD'] + '\n')[1]
            proc = subprocess.Popen('sudo service iqfeed stop && sudo service iqfeed start',
                                    shell=True,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            (out, err) = proc.communicate()
            self.log(out)
            if err:
                self.log('Error occured starting iqfeed:', err)
            time.sleep(7)
        except Exception as e:
            raise RuntimeError(str(e))

    def __connect_to_socket(self, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
        except Exception as e:
            self.send_notification(str(e))
            raise RuntimeError("Could not connect to IQFeed host {0}:{1}\n{2}".format(host, port, str(e)))
        return sock

    def send_to_socket(self, message):
        self.sock.sendall(message)

    def receive_from_socket(self, recv_buffers):
        return self.sock.recv(recv_buffers)

    def __get_ticker_user_dict(self):
        users_and_tickers = self.query_select("SELECT user_id, ticker_id FROM users_usertickers WHERE is_active = true")
        ticker_to_user = defaultdict(set)
        for user_id, ticker_id in users_and_tickers:
            ticker_to_user[ticker_id].add(user_id)
        return ticker_to_user

    def __get_user_details(self):
        user_data = self.query_select("SELECT a.id, a.email, b.app_token, b.app_user "
                                      "FROM auth_user a LEFT JOIN users_appuser b ON a.id= b.user_id")
        return {user[0]: {"email": user[1], "app_token": user[2], "app_user": user[3]} for user in user_data}

    def get_timeframes_to_fetch(self):
        current_time = datetime.now()
        create_4hour = False | self.args.force4hr
        timeframes = self.args.timeframes
        minutes_now = current_time.minute
        hours_now = current_time.hour
        current_time -= relativedelta(minutes=minutes_now % 5, seconds=current_time.second)
        expected_length = 9 if self.args.historic else 12

        if self.args.daily:
            for interval in self.args.daily:
                if interval in daily_intervals:
                   timeframes.insert(0, str(interval) + 'd')

        if self.args.historic and len(timeframes) == 0 and create_4hour is False:
            if len(timeframes) == 0:
                timeframes.append(5)
                minutes_now = current_time.minute
                if minutes_now % 15 == 0:
                    timeframes.append(15)
                if minutes_now == 30:
                    timeframes.append(60)
                    if hours_now == 13 or hours_now == 16:
                        create_4hour = True
                if hours_now == 16 and minutes_now == 50:
                    timeframes.extend(['1d', '7d'])
        else:
            timeframes = timeframes if timeframes or create_4hour else [5, 15, 60]
        return timeframes, current_time, expected_length, create_4hour

    @staticmethod
    def get_max_data_points(timeframe, start_time, current_time, default_data_limit):
        if default_data_limit:
            return data_limit
        if timeframe == '7d' or timeframe == '7day':
            return str((current_time.date() - start_time).days // 7 + 1)
        return ''

    def get_start_or_end_time(self, tf_info, ticker_id, start_time, descending=False):
        if start_time:
            start_time = self.localize(parser.parse(start_time))
            return start_time.date() if tf_info.table_name in requires_date_format else start_time, False
        data = self.query_select(
            "select end_time from stocks_stock{0} where ticker_id={1} order by end_time {2} limit 1"
            .format(tf_info.table_name, ticker_id, "desc" if descending else "asc"))
        if not data or not data[0]:
            return tf_info.start_time if tf_info.table_name in requires_date_format \
                       else self.localize(tf_info.start_time), True
        return (data[0][0], False) if tf_info.table_name in requires_date_format \
            else (data[0][0].astimezone(local_tz), False)

    def get_parameters(self, ticker_id, timeframe, current_time, start_time=""):
        tf_info = timeframe_info[timeframe]
        start_time, default_data_limit = self.get_start_or_end_time(tf_info, ticker_id, start_time, descending=True)
        return start_time, current_time - tf_info.relative_delta, \
               self.get_max_data_points(timeframe, start_time, current_time, default_data_limit), tf_info.interval_type

    def get_start_time(self, timeframe, ticker_id, start_time):
        start_time, default_data_limit = \
            self.get_start_or_end_time(timeframe_info[timeframe], ticker_id, start_time, descending=False)
        return start_time

    def get_olhc(self, buffer, interval, has_request_id=True, iqfeed_daylight=False):
        request_id_offset = 0 if has_request_id else -1
        index = indices['historic'] if self.args.historic else indices['live']
        end_time = buffer[index['end_time'] + request_id_offset]
        end_time = self.format_date_in_end_time(parser.parse(end_time).date(), interval) if interval in requires_date_format \
            else self.localize(self.adjust_daylight(parser.parse(end_time), iqfeed_daylight, interval))
        return buffer[index['open'] + request_id_offset], buffer[index['low'] + request_id_offset], \
               buffer[index['high'] + request_id_offset], buffer[index['close'] + request_id_offset], end_time, \
               self.get_volume(buffer, interval, index['period_volume'] + request_id_offset)

    @staticmethod
    def get_volume(buffer, interval, volume_index):
        return buffer[volume_index] if interval in requires_date_format else buffer[volume_index + 1]

    @staticmethod
    def format_date_in_end_time(end_time, interval):
        if interval in interval_weekly:
            return end_time + relativedelta(days=friday_weekday-end_time.weekday())
        return end_time

    @staticmethod
    def get_sql_insert_query(interval, ticker_id, open, low, high, close, end_time, volume=None):
        if interval in requires_date_format:
            return "insert into stocks_stock{0}(ticker_id, open, low, high, close, end_time, volume) values ({1},{2},{3},{4},{5},'{6}',{7})" \
                .format(interval, ticker_id, open, low, high, close, str(end_time), volume)
        return "insert into stocks_stock{0}(ticker_id, open, low, high, close, end_time, time, volume) values ({1},{2},{3},{4},{5},'{6}','{7}',{8})" \
            .format(interval, ticker_id, open, low, high, close, str(end_time), str(end_time.time()), volume)

    @staticmethod
    def get_sql_update_query(interval, ticker_id, open, low, high, close, end_time, volume=None):
        return "update stocks_stock{0} " \
               "set open={1}, low={2}, high={3}, close={4}, volume={5}" \
               "where ticker_id={6} and end_time='{7}'".format(interval, open, low, high, close, volume, ticker_id,
                                                               str(end_time))

    @staticmethod
    def get_update_volume_query(interval, ticker_id, volume, end_time):
        return "UPDATE stocks_stock{0} SET volume={1} WHERE ticker_id={2} AND end_time='{3}'"\
            .format(interval, volume, ticker_id, str(Util.format_date_in_end_time(end_time, interval)))

    @staticmethod
    def get_sql_select_query(interval, ticker_id, start_time, times):
        if interval in requires_date_format:
            return "select end_time, open, low, high, close, volume " \
                   "from stocks_stock{0} " \
                   "where ticker_id={1} and end_time >= '{2}' " \
                   "order by end_time".format(interval, ticker_id, str(start_time))
        return "select end_time, open, low, high, close, volume, time " \
               "from stocks_stock{0} " \
               "where ticker_id={1} and end_time >= '{2}' and time in {3} " \
               "order by end_time".format(interval, ticker_id, str(start_time), times)

    def get_historic_data(self, start_time, interval, times, ticker_id):
        start_time = self.get_start_time(interval, ticker_id, start_time)
        return self.query_select(self.get_sql_select_query(interval, ticker_id, start_time, times))

    @staticmethod
    def format_date_time(parameters, to_format, *args):
        for arg in args:
            if arg in parameters:
                parameters[arg] = parameters[arg].strftime(to_format)

    def get_message_type(self, interval_type, interval):
        if not self.args.historic:
            return MessageType.BW
        if interval_type == IntervalType.SECONDS:
            return MessageType.HIT
        if interval_type == IntervalType.DAILY:
            if interval == "1d":
                return MessageType.HDT
            if interval == "7d":
                return MessageType.HWX
            raise ValueError("Invalid interval ", str(interval), "Must be either 1d or 7d")
        raise ValueError("Invalid interval type ", str(interval_type))

    def create_iqfeed_message(self, interval_type, interval, parameters):
        message_type = self.get_message_type(interval_type, interval)
        self.format_date_time(parameters,
             expected_format[interval_type],
             MessageParameters.BEGIN_DATETIME,
             MessageParameters.END_DATETIME)
        if interval in interval_in_seconds:
            parameters[MessageParameters.INTERVAL] = interval_in_seconds[interval]
            parameters[MessageParameters.INTERVAL_TYPE] = 't' if self.args.tick_interval else 's'
        message = IQfeedMessage(message_type, parameters).get_message()
        self.log(message)
        return message

    def update_percent_change(self, ticker_id, interval):
        if interval not in interval_5min:
            return
        try:
            close_data = self.query_select(
                "SELECT close, end_time FROM stocks_stock1day WHERE ticker_id={0} ORDER BY end_time DESC LIMIT 2"
                .format(ticker_id))
            time_now = datetime.now()

            if close_data[0][1] != time_now.date() and 0 <= time_now.weekday() <= 4 and (
                        (10 <= time_now.hour < 16) or (time_now.hour == 9 and time_now.minute >= 35)):
                price_data = self.query_select(
                    "SELECT close FROM stocks_stock5min WHERE ticker_id={0} AND time >= '{1}' AND time < '{2}'"
                    " ORDER BY end_time DESC LIMIT {3}"
                    .format(ticker_id, begin_time, end_time, 1))
                price = price_data[0][0]
                last_day = close_data[0][0]
            else:
                price = close_data[0][0]
                last_day = close_data[1][0]
            self.query_update(
                "UPDATE stocks_tickers SET percent_change={0}, price={1} WHERE id={2}"
                .format(self.get_percent_change(price, last_day), price, ticker_id),
                commit=True)
        except psycopg2.IntegrityError:
            self.query_rollback()
        except Exception:
            print(ticker_id)
            traceback.print_exc()
            self.query_rollback()

    def update_average_volume(self, ticker_id, interval):
        if interval in interval_1day:
            try:
                # cursor.execute(
                #    "SELECT AVG(volume) FROM stocks_stock{0} WHERE ticker_id={1} AND end_time >='{2}'"
                #    .format(interval, ticker_id, datetime.now().date() - relativedelta(days=30)))
                last30days_avg_volume = self.query_select(
                    "SELECT AVG(t.volume) FROM "
                    "(SELECT volume FROM stocks_stock{0} WHERE ticker_id={1} ORDER BY end_time DESC limit {2}) t"
                    .format(interval, ticker_id, volume_data_points))[0][0]
                if last30days_avg_volume is not None:
                    last_day_volume = self.query_select(
                        "SELECT volume, end_time FROM stocks_stock{0} WHERE ticker_id={1} "
                        "ORDER BY end_time DESC limit 1"
                        .format(interval, ticker_id))[0][0]
                    self.query_update(
                        "UPDATE stocks_tickers SET last30days_avg_volume={0}, last_day_volume={1} WHERE id={2}"
                        .format(last30days_avg_volume, last_day_volume, ticker_id),
                        commit=True)
            except Exception:
                traceback.print_exc()
                self.query_rollback()

    def combine_last_incomplete_if_any(self, buffer, last_incomplete, last, expected_length, separator, request_ids=set()):
        if not buffer:
            if len(last_incomplete.split(separator)) == expected_length:
                return [last_incomplete], ''
            return buffer, ''
        if not last_incomplete:
            if not last:
                last_incomplete = buffer.pop()
            return buffer, last_incomplete
        if len(last_incomplete.split(separator)) == expected_length and len(buffer[0].split(separator)) == expected_length:
            temp = buffer.pop() if not last else ''
            buffer.append(last_incomplete)
            return buffer, temp

        complete_data = last_incomplete + buffer[0]
        if len(complete_data.split(separator)) != expected_length:
            if re.match("[0-9]+,!E.*", complete_data):
                if request_ids:
                    request_id = complete_data.split(',')[0]
                    request_ids.remove(request_id)
                return buffer[1:], ''
            self.report_fault(
                "Something went wrong while merging data\nlast_incomeplete: {0}\nbuffer[0]: {1}\nbuffer length: {2}"
                    .format(last_incomplete, buffer[0], len(buffer)))
            if len(buffer[0].split(separator)) == expected_length:
                return buffer, ''
            return buffer[1:], ''
        if self.args.debug:
            print("Merged two", last_incomplete, buffer[0])
        last_incomplete = buffer.pop() if not last else ''
        buffer.append(complete_data)
        return buffer[1:], last_incomplete

    def update_time(self, current_time):
        time_data = self.query_select("SELECT * FROM stocks_stockupdate ORDER BY time DESC")
        current_time = self.localize(current_time)
        if not time_data:
            self.query_insert("INSERT INTO stocks_stockupdate(time, ongoing) values('{0}', false)".format(current_time),
                              commit=True)
        else:
            self.query_update(
                "UPDATE stocks_stockupdate SET time='{0}' WHERE id={1}".format(current_time, time_data[0][0]),
                commit=False)
            if self.args.new:
                self.query_update(
                    "UPDATE stocks_stockupdate SET ongoing=false WHERE id={0}".format(time_data[0][0]),
                    commit=False)
            self.query_commit()

    def get_old_notification_data(self):
        # fetch individual ticker notifications
        notif_data = self.query_select('''select "user_id", "ticker_id", "primary", "secondary" from stocks_notification''')

        # fetch global notification
        global_notif_data = self.query_select('''select "user_id", "primary", "secondary" from stocks_globalnotification''')

        notifications = {}
        for ticker_notif in notif_data:
            if ticker_notif[1] not in notifications:
                notifications[ticker_notif[1]] = []
            notifications[ticker_notif[1]].append({"primary": ticker_notif[2], "secondary": ticker_notif[3], "user_id": ticker_notif[0]})

        global_notifications = []
        for global_notif in global_notif_data:
            global_notifications.append({"primary": global_notif[1], "secondary": global_notif[2], "user_id": global_notif[0]})

        return notifications, global_notifications

    def get_notification_data(self):
        if self.notification_data is not None:
            return self.notification_data
        self.notification_data = NotificationData()
        notification_sent_data = self.query_select("SELECT id, ticker_id, notification_group_id "
                                                   "FROM stocks_isnotificationsent")
        self.notification_data.set_notification_sent({(ns[1], ns[2]): ns[0] for ns in notification_sent_data})

        bungee_settings = self.query_select("SELECT a.id, a.name, b.operator, b.bungee_color, b.bungee_value "
                                            "FROM stocks_bungeenotification a "
                                            "LEFT JOIN stocks_bungeenotificationsettings b "
                                            "ON a.id = b.bungee_notification_id")
        bungee_settings_dict = {}
        for bs in bungee_settings:
            if bs[0] not in bungee_settings_dict:
                bungee_settings_dict[bs[0]] = {'name':  bs[1], 'settings': []}
            bungee_settings_dict[bs[0]]['settings']\
                .append({'operator': bs[2], 'color': bs[3], 'value': str(bs[4])})

        query = "SELECT a.id,a.is_global,a.ticker_id,a.user_id,b.primary_tf,b.primary_type,b.secondary,b.sma_cross," \
                "b.bungee_notification_id,b.rsi_threshold,a.bungee " \
                "FROM stocks_notificationgroup a LEFT JOIN stocks_notificationnew b ON a.id = b.notification_group_id " \
                "WHERE a.deleted = false AND a.active = true"
        ticker_notifications = {}
        global_notifications = {}

        def get_notification_settings_dict(nf):
            return {
                    'primary_tf': interval_map[nf[4]],
                    'primary_type': nf[5],
                    'secondary': nf[6],
                    'sma_cross': nf[7],
                    'bungee_notification_id': nf[8],
                    'rsi_threshold': nf[9],
                }

        def create_notifications_dict(nf):
            return {'user_id': nf[3], 'settings': [], 'id': nf[0], 'is_bungee': nf[10]}

        for notification in self.query_select(query):
            if notification[1]: # global notifications
                if notification[0] not in global_notifications:
                    global_notifications[notification[0]] = create_notifications_dict(notification)
                global_notifications[notification[0]]['settings'].append(get_notification_settings_dict(notification))
            else:
                if notification[2] not in ticker_notifications:
                    ticker_notifications[notification[2]] = {}
                if notification[0] not in ticker_notifications[notification[2]]:
                    ticker_notifications[notification[2]][notification[0]] = create_notifications_dict(notification)
                ticker_notifications[notification[2]][notification[0]]['settings']\
                    .append(get_notification_settings_dict(notification))
        return self.notification_data\
            .set_bungee_settings(bungee_settings_dict)\
            .set_ticker_notifications(ticker_notifications)\
            .set_global_notifications(global_notifications)

    def get_all_ticker_signals(self, ticker_ids=None):
        ticker_ids = tuple(self.tickers_id.values() if ticker_ids is None else ticker_ids)
        ticker_ids = "({})".format(ticker_ids[0]) if len(ticker_ids) == 1 else ticker_ids
        signal_data = self.query_select("SELECT ticker_id, interval, type, age, second, sma_cross, bungee_values_yellow, "
                                        "bungee_values_green, bungee_values_blue, bungee_values_red, rsi_threshold "
                                        "FROM stocks_signaldata "
                                        "WHERE ticker_id in {0}".format(ticker_ids))
        price_data = self.query_select("SELECT id, price FROM stocks_tickers WHERE id in {0}".format(ticker_ids))
        price_map = {ticker_id: price for ticker_id, price in price_data}
        return SignalData().add_all(signal_data, price_map)

    def get_ticker_signals(self, ticker_id):
        current_signal_data = self.get_all_ticker_signals([ticker_id])
        return current_signal_data.get_ticker_signals(ticker_id)

    def send_email(self, body, from_addr=fromaddr, to_addr=fromaddr, password=password, subject=subject):
        if self.args.debug and not self.args.dev:
            self.log("Sending an email to {0}: {1}\n".format(to_addr, body))
        threading.Thread(target=send_mail, args=[from_addr, password, to_addr, body, subject, self.args.dev]).start()

    def report_fault(self, message, app_notification=False):
        self.send_email(message, to_addr=self.dev_email)
        if app_notification:
            self.send_notification(message)

    @staticmethod
    def send_notif(message, token, user):
        try:
            r = requests.post("https://api.pushover.net/1/messages.json", data={
                "token": token,
                "user": user,
                "message": message
            })
        except Exception as e:
            print(str(datetime.now()), str(e), "Error sending message", message)

    def send_notification(self, message, token=app_token, user=app_user):
        if self.args.dev:
            print(str(datetime.now()), "[Dev mode] Aborting to send notification:", message)
            return
        threading.Thread(target=self.send_notif, args=[message, token, user]).start()

    def notify_user(self, subject, message, user_id, ticker_id, notification_id):
        try:
            self.notification_is_sent.add((ticker_id, notification_id))
            user_details = self.user_details[user_id]
            if user_details["email"] is not None:
                # email_subject = "{} for {}".format(subject, self.reverse_tickers_id[ticker_id])
                self.send_email(message, to_addr=user_details["email"], subject=subject)
            if user_details["app_token"] is not None and user_details["app_user"] is not None:
                self.send_notification(re.sub(r"<b>|</b>", '', message.replace("<br>", "\n")),
                                       user_details["app_token"], user_details["app_user"])
            self.print_msg("Sent notification for ticker id: {} (Notification group id: {})".format(ticker_id, notification_id))
        except Exception:
            traceback.print_exc()

    @staticmethod
    def set_to_tuple(s):
        return "({})".format(list(s)[0]) if len(s) == 1 else tuple(s)

    @staticmethod
    def list_to_tuple(l):
        return "({})".format(l) if len(l) == 1 else tuple(l)

    def renew_notification_sent(self, ticker_id, notification_id):
        if (ticker_id, notification_id) in self.notification_data.get_notification_sent():
            self.remove_notification_sent.add(ticker_id)

    def update_notification_is_sent(self):
        self.log("Remove notification sent", self.remove_notification_sent)
        self.log("Notification sent", self.notification_is_sent)
        if self.remove_notification_sent:
            self.query_delete("DELETE FROM stocks_isnotificationsent WHERE id in {}"
                              .format(self.set_to_tuple(self.remove_notification_sent)))
        if self.notification_is_sent:
            current_time = datetime.now()
            for ticker_id, notification_id in self.notification_is_sent:
                self.query_insert(
                    "INSERT INTO stocks_isnotificationsent(ticker_id, notification_group_id, time) VALUES ({},{},'{}')"
                    .format(ticker_id, notification_id, current_time))

    def update_next_earning_date(self):
        if self.args.update_earning_date is False:
            # updating next earning date manually from front end as yahoo api does not give correct dates
            self.log("Not updating next earning date\n")
            return
        if not self.args.daily:
            return
        self.log("Updating next earning date\n")
        for ticker in self.tickers:
            try:
                timestamp = yec.get_next_earnings_date(ticker)
                # results[ticker] = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
                date = datetime.fromtimestamp(int(timestamp)).date()
                self.query_update("UPDATE stocks_tickers SET next_earning_date='{0}' WHERE id={1}"
                                  .format(str(date), self.tickers_id[ticker]),
                                  commit=True)
                self.log("updated {0} with date {1}".format(ticker, str(date)))
            except Exception:
                try:
                    self.query_rollback()
                    self.query_update("UPDATE stocks_tickers SET next_earning_date='{0}' WHERE id={1}"
                                      .format(str(datetime.now().date()), self.tickers_id[ticker]),
                                      commit=True)
                    self.log("updated {0} with current date".format(ticker))
                except Exception:
                    traceback.print_exc()
                    self.query_rollback()

    @staticmethod
    def localize(given_time):
        return local_tz.localize(given_time, is_dst=None)

    @staticmethod
    def get_percent_change(a, b):
        return float(a - b) * 100.0 / b

    @staticmethod
    def adjust_daylight(given_time, should_adjust, interval):
        if should_adjust and time.localtime().tm_isdst:
            return given_time - iqfeed_daylight_adjustment[interval]
        return given_time

    def get_args(self):
        return self.args

    def get_tickers(self):
        return self.tickers, self.tickers_id

    def get_user_details(self):
        return self.user_details

    def get_ticker_to_users_dict(self):
        return self.ticker_to_users

    def get_ticker_to_users(self, ticker_id):
        return self.ticker_to_users[ticker_id]

    def log(self, *message):
        if self.args.debug or self.args.prints:
            caller = getframeinfo(stack()[1][0])
            print("{} {}({}):{}".format(datetime.now(), caller.filename, caller.function, caller.lineno), end='  ')
            print(*message)

    def print_msg(self, *message):
        caller = getframeinfo(stack()[1][0])
        print("{} {}({}):{}".format(datetime.now(), caller.filename, caller.function, caller.lineno), end='  ')
        print(*message)

    def log_print_level(self, *message):
        if self.args.prints:
            caller = getframeinfo(stack()[1][0])
            print("{} {}({}):{}".format(datetime.now(), caller.filename, caller.function, caller.lineno), end='  ')
            print(*message)

    def print_buffer(self, buffer, last_incomplete, message):
        if self.args.prints:
            print("\n---------{0}".format(message))
            print("buffer:", buffer)
            print("last_incomplete:", last_incomplete)
            if self.args.wait:
                input()

    def query_select(self, query):
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def query_commit(self, commit=True):
        if commit is True:
            self.conn.commit()

    def query_update_or_insert_or_delete(self, query, commit):
        self.cursor.execute(query)
        self.query_commit(commit)

    def query_update(self, query, commit=True):
        self.query_update_or_insert_or_delete(query, commit)

    def query_insert(self, query, commit=True):
        self.query_update_or_insert_or_delete(query, commit)

    def query_delete(self, query, commit=True):
        self.query_update_or_insert_or_delete(query, commit)

    def query_rollback(self):
        self.cursor.execute("rollback")

    def test_iqfeed_connection(self):
        message = "HTD\r\n"
        self.send_to_socket(message.encode("utf-8"))

        # expect to receive error message from sock if iqfeed connection is working fine,
        # it will go into waiting state otherwise.
        buffer = self.receive_from_socket(recv_buffers=4096)
        return True

    def close(self, *msg):
        if self.sock:
            self.sock.shutdown(socket.SHUT_RDWR)
        if self.conn is not None:
            self.conn.close()
        self.print_msg(*msg)
        sys.exit()
