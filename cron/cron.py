import traceback
from data_creator import DataCreator
from datetime import datetime
from messages import MessageParameters, IntervalType
from psycopg2 import IntegrityError
from signals import main_signal, second_signal, update_signals
from util import Util

util = Util()
args = util.get_args()
data_limit = '4000'
create_4hr_settings = {
    'from': '60min',
    'to': '4hour',
    'start_time': '',
    # 'start_time': util.localize(datetime.now()),
    'timeframes': {
        ('09:30:00', '10:30:00', '11:30:00', '12:30:00'): '09:30:00',
        ('13:30:00', '14:30:00', '15:30:00'): '13:30:00',
    },
}
interval_map = {
    5: '5min',
    15: '15min',
    60: '60min',
    240: '4hour',
    '1d': '1day',
    '7d': '1week'
}
error_messages_set = {"E,!NO_DATA!,,", "S,SERVER DISCONNECTED"}


def transform_data(data, interval, ticker_id, expected_length):
    temp_data = []
    for d in data:
        buffer = d.split(",")
        if len(buffer) != expected_length:
            util.report_fault(
                "Something went wrong in the data\nexpected_length: {0}\nactual_length[0]: {1}\n"
                "actual data: {2}\nticker id:{3}"
                .format(expected_length, len(buffer), buffer, ticker_id))
            continue
        open, low, high, close, end_time, volume = \
            util.get_olhc(buffer, interval, has_request_id=False, iqfeed_daylight=True)
        temp_data.append([open, low, high, close, end_time, volume])
    return temp_data


def save_hist_data(data, interval, ticker_id, expected_length):
    data = transform_data(data, interval, ticker_id, expected_length)
    try:
        # first attempt bulk insertion
        for buffer in data:
            open, low, high, close, end_time, volume = buffer
            if args.fetch:
                util.log("Skipping", buffer)
                continue
            util.query_insert(util.get_sql_insert_query(interval, ticker_id, open, low, high, close, end_time, volume),
                              commit=False)
            util.log_print_level("Stored", buffer)
        util.query_commit()
    except IntegrityError:
        util.query_rollback()
        util.log("Encounter integrity in bulk insertions")
        if args.fetch:
            return
        for buffer in data:
            try:
                open, low, high, close, end_time, volume = buffer
                util.query_insert(util.get_sql_insert_query(interval, ticker_id, open, low, high, close, end_time, volume),
                                  commit=True)
                util.log_print_level("Stored", buffer)
            except IntegrityError:
                util.query_rollback()
                util.log("Datapoint already there in the system. Updating the data point.")
                util.query_update(util.get_sql_update_query(interval, ticker_id, open, low, high, close, end_time, volume),
                                  commit=True)
                util.log_print_level("Updated", buffer)
            except Exception as e:
                util.query_rollback()
                util.log("12", str(e))
    except Exception as e:
        util.log("125", str(e))


def fetch_hist_data(interval, ticker_id, recv_buffers=4096):
    interval = interval_map[interval]
    last_incomplete = ''
    last = False
    separator = ','
    expected_length = 8
    while True:
        buffer = util.receive_from_socket(recv_buffers).decode("utf-8").split("\r\n")
        if buffer and not buffer[-1]:
            buffer.pop()
        util.print_buffer(buffer, last_incomplete, "Before")
        if buffer[0] in error_messages_set:
            break
        if "!ENDMSG!" in buffer[-1]:
            last = True
            buffer.pop()

        buffer, last_incomplete = \
            util.combine_last_incomplete_if_any(buffer, last_incomplete, last, expected_length, separator)
        util.print_buffer(buffer, last_incomplete, "After")
        save_hist_data(buffer, interval, ticker_id,  expected_length)
        if last or last_incomplete.startswith('!') or (not buffer and not last_incomplete):
            break
    util.update_percent_change(ticker_id, interval)
    util.update_average_volume(ticker_id, interval)


def load_hist_data(symbol, ticker_id, interval, interval_type, start_time, end_time, max_data_points=''):
    parameters = {
        MessageParameters.SYMBOL: symbol,
        MessageParameters.BEGIN_DATETIME: start_time,
        MessageParameters.END_DATETIME: end_time,
        MessageParameters.DATAPOINTS_PER_SECOND: "100",
        MessageParameters.MAX_DATAPOINTS: max_data_points
    }
    message = util.create_iqfeed_message(interval_type, interval, parameters)
    try:
        util.send_to_socket(message.encode('utf-8'))
        fetch_hist_data(interval, ticker_id)
        return True
    except Exception as e:
        print(str(e))
        util.send_notification(str(e))
        return False


def fetch_data(interval_to_fetch, current_time, tickers, tickers_id):
    for ticker in tickers:
        for interval in interval_to_fetch:
            ticker_id = tickers_id[ticker]
            start_time, end_time, max_data_points, interval_type = \
                util.get_parameters(ticker_id, interval, current_time, args.start_time)
            # if isinstance(start_time, datetime):
            #    create_4hr_settings['start_time'] = min(create_4hr_settings['start_time'], start_time)
            if args.debug:
                print(ticker, interval, interval_type)
            status_healthy = load_hist_data(ticker, ticker_id, interval, interval_type,
                                            start_time, end_time, max_data_points)
            if not status_healthy:
                return


def main():
    to_fetch, current_time, expected_length, create_4hour = util.get_timeframes_to_fetch()
    tickers, tickers_id = util.get_tickers()
    if not args.update_tickers and not args.update_signals:
        util.print_msg("You should consider using update_tickers or update_signals flag.")
        util.print_arguments_and_exit()
    if args.update_tickers:
        util.print_msg("Fetching intervals: ", to_fetch, " 4 hour:", create_4hour)
        fetch_data(to_fetch, current_time, tickers, tickers_id)
        if create_4hour:
            # create_4hr_settings['start_time'] = str(create_4hr_settings['start_time'].replace(tzinfo=None))
            DataCreator([create_4hr_settings], util, tickers, tickers_id).start()
    if args.new:
        util.print_msg('New tickers are added')
    if args.update_signals:
        if create_4hour:
            to_fetch.append(240)
        util.print_msg("Updating intervals: ", to_fetch)
        update_signals(util, tickers, tickers_id, [interval_map[interval] for interval in to_fetch])
        util.update_time(current_time)
    util.update_next_earning_date()
    util.close()
    util.print_msg("Finished running cron script started at", current_time)


if __name__ == '__main__':
    main()
