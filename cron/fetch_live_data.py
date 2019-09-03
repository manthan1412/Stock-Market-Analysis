from datetime import datetime
import dateutil.parser
from dateutil.relativedelta import relativedelta
import pytz
from signals import main_signal, second_signal, update_signals
from psycopg2 import IntegrityError
import time
import util
from messages import MessageParameters, MessageType, IntervalType

host = "127.0.0.1"
port = 9400
stock_tables = ["5min", "15min", "60min", "4hour", "1day", "1week"]
data_limit = 4000
requires_date_format = {"1day", "1week", "1d", "7d"}

args = util.parse_arguments()
interval_map = {
    5: '5min',
    15: '15min',
    60: '60min',
    240: '4hour',
    '1d': '1day',
    '7d': '1week'
}


def save_hist_data(conn, cursor, data, tickers_id, expected_length, local_tz, request_id_to_interval_map):
    temp_data = []
    try:
        for d in data:
            buffer = d.split(",")
            """
            Interval bar data message expected format
            [RequestID],B[Type],[Symbol],[DateTime],[Open],[High],[Low],[Last],[CummulativeVolume],[IntervalVolume],
            [NumberOfTrades]<CR><LF>
            """
            ticker_id = tickers_id[buffer[2]]
            if len(buffer) != expected_length:
                util.report_fault(
                    "Something went wrong in the data\nexpected_length: {0}\nactual_length[0]: {1}\nactual data: {2}\nticker id:{3}"
                        .format(expected_length, len(buffer), buffer, ticker_id))
                continue
            if args.prints:
                print("Storing", buffer)
            interval = interval_map[request_id_to_interval_map[buffer[0]]]
            buffer[3] = dateutil.parser.parse(buffer[3]).date() if interval in requires_date_format \
                else local_tz.localize(dateutil.parser.parse(buffer[3]))
            temp_data.append((interval, ticker_id, buffer))

            if not args.fetch:
                cursor.execute(
                "insert into stocks_stock{0}(ticker_id, open, high, low, close, end_time) values ({1},{2},{3},{4},{5},'{6}')"
                    .format(interval, ticker_id, buffer[4], buffer[5], buffer[6], buffer[7], str(buffer[3])))
        if not args.fetch:
            conn.commit()
    except IntegrityError:
        cursor.execute("rollback")
        if args.debug:
            print("Encounter integrity in bulk insertions")
        for interval, ticker_id, buffer in temp_data:
            try:
                cursor.execute(
                    "insert into stocks_stock{0}(ticker_id, open, high, low, close, end_time) values ({1},{2},{3},{4},{5},'{6}')"
                        .format(interval, ticker_id, buffer[4], buffer[5], buffer[6], buffer[7], str(buffer[3])))
                conn.commit()
            except IntegrityError:
                cursor.execute("rollback")
            except Exception as e:
                print("12", str(datetime.now()), str(e))
                cursor.execute("rollback")
    except Exception as e:
        print("125", str(datetime.now()), str(e))
        cursor.execute("rollback")
    finally:
        for interval, ticker_id, buffer in temp_data:
            util.update_percent_change(conn, cursor, ticker_id, interval)


interval_type = {
    5: IntervalType.SECONDS,
    15: IntervalType.SECONDS,
    60: IntervalType.SECONDS
}


def create_request_id(index, ticker_id, timeframe):
    return str(int(index) + 1)


def create_live_bar_message(tickers, tickers_id, timeframes, start_time):
    """
    Request a new interval bar watch message format
    BW,[Symbol],[Interval],[BeginDate BeginTime],[MaxDaysOfDatapoints],[MaxDatapoints],[BeginFilterTime],
    [EndFilterTime],[RequestID],[Interval Type],[Reserved],[UpdateInterval]
    """
    messages = []
    request_id = '0'
    request_id_to_interval_map = {}
    for ticker in tickers:
        ticker_id = tickers_id[ticker]
        parameters = {
            MessageParameters.SYMBOL: ticker,
        }
        for index, timeframe in enumerate(timeframes):
            request_id = create_request_id(request_id, ticker_id, timeframe)
            parameters[MessageParameters.INTERVAL] = timeframe
            parameters[MessageParameters.REQUEST_ID] = request_id
            parameters[MessageParameters.BEGIN_DATETIME] = start_time
            messages.append(util.create_iqfeed_message(
                interval_type[timeframe], timeframe, parameters, args.prints, MessageType.BW))
            request_id_to_interval_map[request_id] = timeframe
            # messages.append("BW,{0},{1},{2},,,,,{3},s,,0\r\n"
            #                 .format(ticker, timeframe, start_time, str((index + 1) * ticker_id)))
    return "".join(messages), request_id_to_interval_map


def send_request(sock, tickers, tickers_id, timeframes, start_time):
    message, request_id_to_interval_map = create_live_bar_message(tickers, tickers_id, timeframes, start_time)
    if args.prints:
        print(message)
    sock.sendall(message.encode('utf-8'))
    return request_id_to_interval_map


error_messages_set = {"E,!NO_DATA!,,", "S,SERVER DISCONNECTED"}


def fetch_data(sock, conn, cursor, tickers, tickers_id, timeframes, request_id_to_interval_map, recv_buffers=4096):
    local_tz = pytz.timezone("America/New_York")
    last = False
    last_incomplete = ""
    separator = ","
    while True:
        """
        Interval bar data message expected format
        [RequestID],B[Type],[Symbol],[DateTime],[Open],[High],[Low],[Last],[CummulativeVolume],[IntervalVolume],
        [NumberOfTrades]<CR><LF>
        """

        buffer = sock.recv(recv_buffers).decode("utf-8").split("\r\n")
        util.print_buffer(buffer, last_incomplete, "Before", args.prints, args.wait)
        if buffer and not buffer[-1]:
            buffer.pop()
        if buffer and buffer[0] == "S,SERVER CONNECTED":
            buffer = buffer[1:]
        if buffer and buffer[0] in error_messages_set:
            if args.debug:
                print("Encountered an error message. Got message:", buffer)
            break
        if "!ENDMSG" in buffer[:-1]:
            last = True
            buffer.pop()

        buffer, last_incomplete = \
            util.combine_last_incomplete_if_any(buffer, last_incomplete, last, args.expected_length, separator,
                                                args.prints, args.dev)
        util.print_buffer(buffer, last_incomplete, "After", args.prints, args.wait)
        save_hist_data(conn, cursor, buffer, tickers_id, args.expected_length, local_tz,
                       request_id_to_interval_map)
        if last or last_incomplete.startswith('!'): # or (not buffer and not last_incomplete):
            break


def main():
    timeframes = args.timeframes if args.timeframes else [5, 15, 60]
    current_time = datetime.now()
    start_time = datetime(current_time.year, current_time.month, current_time.day, 9, 30, 0)

    conn = util.get_db_connection()
    cursor = conn.cursor()
    tickers_id, tickers = util.get_tickers(cursor)
    sock = util.get_socket_connection(host, port, args.debug, args.dev)
    if args.cut:
        tickers = tickers[:args.cut]

    if not args.signal:
        request_id_to_interval_map = send_request(sock, tickers, tickers_id, timeframes, start_time)
        fetch_data(sock, conn, cursor, tickers, tickers_id, timeframes, request_id_to_interval_map)
    update_signals(cursor, conn, tickers, tickers_id, args.debug, args.dev, args.csv, args.email)
    if args.new:
        print('new tickers are added')
    util.update_time(cursor, conn, current_time, args.new)
    conn.close()


if __name__ == '__main__':
    if args.debug or args.dev:
        print("Dev mode: ", args.dev, "\tDebug:", args.debug)
    main()
