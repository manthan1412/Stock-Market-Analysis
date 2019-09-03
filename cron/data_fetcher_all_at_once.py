from datetime import datetime
from signals import update_signals
from psycopg2 import IntegrityError
from dateutil import parser
from util import Util
import re
from messages import MessageParameters, MessageType, IntervalType
import traceback
import data_creator

error_messages_set = {"S,SERVER DISCONNECTED"}
util = Util()
args = util.get_args()
interval_map = {
    5: '5min',
    15: '15min',
    60: '60min',
    240: '4hour',
    '1d': '1day',
    '7d': '1week'
}
create_4hr_settings = {
    'from': '60min',
    'to': '4hour',
    'start_time': util.localize(datetime.now()),
    'timeframes': {
        ('09:30:00', '10:30:00', '11:30:00', '12:30:00'): '09:30:00',
        ('13:30:00', '14:30:00', '15:30:00'): '13:30:00',
    },
}


def save_hist_data(data, tickers_id, expected_length, request_id_to_interval_map, request_ids):
    temp_data = []
    try:
        for index, d in enumerate(data):
            buffer = d.split(",")
            if len(buffer) != expected_length:
                if d and re.match("[0-9]+,!E.*", d):
                    request_id = buffer[0]
                    request_ids.remove(request_id)
                    continue
                util.report_fault(
                    "Something went wrong in the data\nexpected_length: {0}\nactual_length[0]: {1}\nactual data: {2}\n"
                    .format(expected_length, len(buffer), buffer))
                continue
            if args.prints:
                print("Storing", buffer)
            interval, ticker = request_id_to_interval_map[buffer[0]]
            open, low, high, close, end_time = util.get_olhc(buffer, interval, has_request_id=True)
            ticker_id = tickers_id[ticker]
            temp_data.append((interval, ticker_id, [open, low, high, close, end_time]))

            if args.fetch:
                continue
            util.query_insert(util.get_sql_insert_query(interval, ticker_id, open, low, high, close, end_time),
                              commit=False)
        if not args.fetch:
            util.query_commit()
    except IntegrityError:
        util.query_rollback()
        util.log("Encounter integrity in bulk insertions")
        for interval, ticker_id, buffer in temp_data:
            try:
                util.query_insert(util.get_sql_insert_query(
                    interval, ticker_id, open=buffer[0], low=buffer[1], high=buffer[2], close=buffer[3],
                    end_time=buffer[4]),
                    commit=True)
            except IntegrityError:
                util.query_rollback()
            except Exception:
                util.query_rollback()
                traceback.print_exc()
    except Exception:
        traceback.print_exc()
        util.query_rollback()
    finally:
        for interval, ticker_id, buffer in temp_data:
            util.update_percent_change(ticker_id, interval)


def check_first_and_last(buffer, request_ids, last_incomplete):
    if buffer and buffer[0] == "S,SERVER CONNECTED":
        buffer = buffer[1:]
    if buffer and re.match("n,[A-Z]+", buffer[0]):
        buffer = buffer[1:]
    if buffer and re.match("[0-9]+,E,!NO_DATA!,,", buffer[0]):
        buffer = buffer[1:]
    if buffer and not buffer[-1]:
        buffer.pop()
    if buffer and re.match("[0-9]+,!END_MSG!,", buffer[0]):
        if len(last_incomplete.split(",")) == 1:
            request_id = last_incomplete + buffer[0].split(',')[0]
            try:
                request_ids.remove(request_id)
                last_incomeplete = ""
            except Exception:
                request_id = buffer[0].split(',')[0]
                request_ids.remove(request_id)
        else:
            request_id = buffer[0].split(',')[0]
            request_ids.remove(request_id)
        buffer = buffer[1:]
    if buffer and re.match("[0-9]+,!E.*", buffer[-1]):
        request_id = buffer[-1].split(',')[0]
        request_ids.remove(request_id)
        buffer.pop()
    return buffer, last_incomplete


def fetch_data(tickers_id, request_id_to_interval_map, expected_length, recv_buffers=4096):
    last = False
    last_incomplete = ""
    separator = ","
    request_ids = set(key for key in request_id_to_interval_map.keys())
    while True:
        buffer = util.receive_from_socket(recv_buffers).decode("utf-8").split("\r\n")
        util.print_buffer(buffer, last_incomplete, "Before")

        if buffer and buffer[0] in error_messages_set:
            util.log("Encountered an error message. Got message:" + str(buffer))
            break

        buffer, last_incomplete = check_first_and_last(buffer, request_ids, last_incomplete)
        util.print_buffer(buffer, last_incomplete, "Middle")

        buffer, last_incomplete = \
            util.combine_last_incomplete_if_any(buffer, last_incomplete, last, expected_length, separator,
                                                request_ids)
        util.print_buffer(buffer, last_incomplete, "After")
        save_hist_data(buffer, tickers_id, expected_length, request_id_to_interval_map, request_ids)
        if len(request_ids) == 0:
            if len(last_incomplete.split(separator)) == expected_length:
                save_hist_data([last_incomplete], tickers_id, expected_length, request_id_to_interval_map, request_ids)
            break
        util.log(request_ids)


def create_request_id(index):
    return str(int(index) + 1)


def get_parameters(request_id, ticker, ticker_id, timeframe, current_time):
    start_time, end_time, max_data_points, interval_type = \
        util.get_parameters(ticker_id, timeframe, current_time, args.start_time)
    if isinstance(start_time, datetime):
        create_4hr_settings['start_time'] = min(create_4hr_settings['start_time'], start_time)
    return {
        MessageParameters.SYMBOL: ticker,
        MessageParameters.REQUEST_ID: request_id,
        MessageParameters.INTERVAL: timeframe,
        MessageParameters.BEGIN_DATETIME: start_time,
        MessageParameters.END_DATETIME: end_time,
        MessageParameters.DATAPOINTS_PER_SECOND: args.datapoints_per_second,
        MessageParameters.MAX_DATAPOINTS: max_data_points
    }, interval_type


def create_iqfeed_messages(tickers, tickers_id, timeframes, start_time):
    messages = []
    request_id = '0'
    request_id_to_interval_map = {}
    for ticker in tickers:
        ticker_id = tickers_id[ticker]
        for timeframe in timeframes:
            request_id = create_request_id(request_id)
            parameters, interval_type = get_parameters(request_id, ticker, ticker_id, timeframe, start_time)
            messages.append(util.create_iqfeed_message(interval_type, timeframe, parameters))
            request_id_to_interval_map[request_id] = (interval_map[timeframe], ticker)
    return "".join(messages), request_id_to_interval_map


def send_request(tickers, tickers_id, timeframes, start_time):
    message, request_id_to_interval_map = create_iqfeed_messages(tickers, tickers_id, timeframes, start_time)
    util.send_to_socket(message.encode('utf-8'))
    return request_id_to_interval_map


def main():
    timeframes, start_time, expected_length, create_4hour = util.get_timeframes_to_fetch()
    tickers, tickers_id = util.get_tickers()
    util.log("Fetching data for timeframes: " + str(timeframes))

    if not args.signal:
        request_id_to_interval_map = send_request(tickers, tickers_id, timeframes, start_time)
        fetch_data(tickers_id, request_id_to_interval_map, expected_length)
        if create_4hour:
            create_4hr_settings['start_time'] = str(create_4hr_settings['start_time'].replace(tzinfo=None))
            DataCreator([create_4hr_settings], util, tickers, tickers_id).start()

    update_signals(util, tickers, tickers_id)
    if args.new:
        print('new tickers are added')
    util.update_next_earning_date()
    util.update_time(start_time)
    util.close()


if __name__ == '__main__':
    main()
