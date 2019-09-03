import os
import socket
import traceback
import util
from datetime import datetime
from messages import MessageParameters
from psycopg2 import IntegrityError

args = util.parse_arguments()
interval_map = {
    5: '5min',
    15: '15min',
    60: '60min',
    240: '4hour',
    '1d': '1day',
    '7d': '1week'
}
require_date_format = {'1day', '1week'}
error_messages_set = {"E,!NO_DATA!,,", "S,SERVER DISCONNECTED"}


def get_earliest_data_time(cursor, ticker_id, interval, start_time):
    if start_time:
        return start_time
    cursor.execute(
        "SELECT end_time FROM stocks_stock{0} WHERE ticker_id={1} ORDER BY end_time LIMIT 1".format(interval, ticker_id))
    data = cursor.fetchall()
    if not data or not data[0]:
        return ''
    return str(data[0][0] if interval in require_date_format else data[0][0].replace(tzinfo=None))


def save_hist_data(conn, cursor, data, interval, ticker_id, expected_length):
    temp_data = []
    try:
        # first attempt bulk insertion
        for d in data:
            buffer = d.split(",")
            if len(buffer) != expected_length:
                util.report_fault(
                    "Something went wrong in the data\nexpected_length: {0}\nactual_length[0]: {1}\nactual data: {2}\nticker id:{3}"
                        .format(expected_length, len(buffer), buffer, ticker_id))
                continue
            if args.prints:
                print("Storing", buffer)
            o, l, h, c, end_time, volume = util.get_olhc(buffer, interval, is_historic=True, has_request_id=False)
            temp_data.append((volume, end_time))
            if args.fetch:
                continue
            cursor.execute(util.get_update_volume_query(interval, ticker_id, volume, end_time))
        conn.commit()
    except IntegrityError:
        cursor.execute("rollback")
        if args.debug:
            print("Encounter integrity in bulk insertions")
        if args.fetch:
            return
        for volume, end_time in temp_data:
            try:
                cursor.execute(util.get_update_volume_query(interval, ticker_id, volume, end_time))
                conn.commit()
            except IntegrityError:
                cursor.execute("rollback")
            except Exception:
                traceback.print_exc()
                cursor.execute("rollback")
    except Exception:
        traceback.print_exc()
        cursor.execute("rollback")


def fetch_hist_data(conn, cursor, sock, interval, ticker_id, recv_buffers=4096):
    interval = interval_map[interval]
    last_incomplete = ''
    last = False
    separator = ','
    expected_length = 8
    while True:
        buffer = sock.recv(recv_buffers).decode("utf-8").split("\r\n")
        if buffer and not buffer[-1]:
            buffer.pop()
        util.print_buffer(buffer, last_incomplete, "Before", args.prints, args.wait)
        if buffer[0] in error_messages_set:
            break
        if "!ENDMSG!" in buffer[-1]:
            last = True
            buffer.pop()

        buffer, last_incomplete = \
            util.combine_last_incomplete_if_any(buffer, last_incomplete, last, expected_length, separator,
                                                args.prints, args.dev)
        util.print_buffer(buffer, last_incomplete, "After", args.prints, args.wait)
        save_hist_data(conn, cursor, buffer, interval, ticker_id,  expected_length)
        if last or last_incomplete.startswith('!') or (not buffer and not last_incomplete):
            break
    util.update_average_volume(conn, cursor, ticker_id, interval)


def load_hist_data(sock, conn, cursor, symbol, ticker_id, interval, interval_type, start_time, end_time, max_data_points=''):
    parameters = {
        MessageParameters.SYMBOL: symbol,
        MessageParameters.BEGIN_DATETIME: start_time,
        MessageParameters.END_DATETIME: end_time,
        MessageParameters.DATAPOINTS_PER_SECOND: "100",
        MessageParameters.MAX_DATAPOINTS: max_data_points
    }
    message = util.create_iqfeed_message(interval_type, interval, parameters, args.debug, is_historic=True, tick_interval=args.tick)

    try:
        sock.sendall(message.encode('utf-8'))
        fetch_hist_data(conn, cursor, sock, interval, ticker_id)
        return True
    except Exception:
        traceback.print_exc()
        return False


def update_volume(conn, cursor, tickers, tickers_id, intervals, current_time):
    sock = util.get_iqfeed_socket_connection(is_historic=True, debug=args.debug, dev=args.dev)
    for ticker in tickers:
        for interval in intervals:
            interval_full = interval_map[interval]
            start_time = get_earliest_data_time(cursor, tickers_id[ticker], interval_full, args.start_time)
            start_time, end_time, max_data_points, interval_type = \
                util.get_parameters(cursor, tickers_id[ticker], interval, current_time, start_time)
            status_healthy = load_hist_data(sock, conn, cursor, ticker, tickers_id[ticker], interval, interval_type,
                                            start_time, end_time, max_data_points)
            if not status_healthy:
                return
    sock.shutdown(socket.SHUT_RDWR)


def main():
    conn = util.get_db_connection()
    cursor = conn.cursor()
    tickers_id, tickers = util.get_tickers(cursor)
    intervals = args.timeframes

    if args.daily:
        for interval in args.daily:
            if interval in {1, 7}:
                intervals.insert(0, str(interval) + 'd')

    if not intervals:
        intervals.append("1d")

    if args.cut:
        tickers = tickers[:args.cut]

    if args.tickers:
        tickers = args.tickers

    update_volume(conn, cursor, tickers, tickers_id, intervals, datetime.now())


if __name__ == '__main__':
    main()
