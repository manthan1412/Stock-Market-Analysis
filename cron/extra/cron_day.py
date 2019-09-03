from psycopg2 import IntegrityError
from datetime import datetime
import socket
import dateutil.parser
from dateutil.relativedelta import relativedelta
from yahoo_earnings_calendar import YahooEarningsCalendar
from signals import main_signal, second_signal, update_signals
import argparse
import util

yec = YahooEarningsCalendar()
host = "127.0.0.1"
port = 9100
sock = None
data_limit = 25000

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", action="store_true", default=False, help="Run in a debug mode")
parser.add_argument("-e", "--dev", action="store_true", default=False, help="Developer mode")
parser.add_argument("-i",
                    "--interval",
                    type=str,
                    default="day",
                    choices={"day", "week"},
                    help="Daily or weekly interval. The value can be either day or week")
try:
    args = parser.parse_args()
except IOError as msg:
    parser.error(str(msg))


def save_hist_data(conn, cursor, sock, ticker_id, recv_buffers=4096):
    data = ""

    while True:
        buffer = sock.recv(recv_buffers).decode("utf-8")
        if "!ENDMSG!" in buffer:
            break
        data += buffer
    data = data.replace("\r", "").split("\n")[:-1]

    for d in data:
        buffer = d.split(",")
        if args.debug:
            if buffer:
                print(buffer)
            else:
                print ("empty")
        date = dateutil.parser.parse(buffer[0]).date()

        try:
            cursor.execute("insert into stocks_stock1{0}(ticker_id, high, low, open, close, end_time) values ({1},{2},{3},{4},{5},'{6}')".format(args.interval, ticker_id, buffer[1], buffer[2], buffer[3], buffer[4], str(date)))
            conn.commit()
        except IntegrityError:
            cursor.execute("rollback")
        except Exception as e:
            print(str(datetime.now()), str(e))
            cursor.execute("rollback")


def load_hist_data(conn, cursor, date_start, symbol, ticker_id, max_points='2'):
    if args.interval == "day":
        date_start = date_start.strftime("%Y%m%d")
        message = "HDT,{0},,{1},{2},0\n".format(symbol, date_start, max_points)
    elif args.interval == "week":
        message = "HWX,{0},{1},0\n".format(symbol, max_points)
    else:
        raise ValueError("Interval must be either day or week")

    try:
        global sock
        if not sock:
            sock = util.get_socket_connection(host, port, args.debug, args.dev)
        sock.sendall(message.encode('utf-8'))
        save_hist_data(conn, cursor, sock, ticker_id)
        return True
    except Exception as e:
        print(str(e))
        send_notif(str(e), args.dev)
        return False


def fetch_data(conn, cursor, tickers, tickers_id, start_time):
    if args.debug:
        print("Updating ", args.interval, "data")
    for ticker in tickers:
        if args.debug:
            print(ticker)
        load_hist_data(conn, cursor, start_time, ticker, tickers_id[ticker])


def update_next_earning_date(conn, cursor, tickers_id, tickers):
    if args.debug:
        print("Updating next earning date\n")
    for ticker in tickers:
        try:
            timestamp = yec.get_next_earnings_date(ticker)
            # results[ticker] = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
            date = datetime.fromtimestamp(int(timestamp)).date()
            cursor.execute("UPDATE stocks_tickers SET next_earning_date='{0}' WHERE id={1}".format(str(date), tickers_id[ticker]))
            conn.commit()
            if args.debug:
                print("updated {0} with date {1}".format(ticker, str(date)))
        except Exception:
            try:
                cursor.execute('rollback')
                date = datetime.now().date()
                cursor.execute("UPDATE stocks_tickers SET next_earning_date='{0}' WHERE id={1}".format(str(date), tickers_id[ticker]))
                conn.commit()
                if args.debug:
                    print("updated {0} with current date".format(ticker))
            except Exception as ex:
                print(str(datetime.now()), str(ex))
                pass


def main():
    global sock
    conn = util.get_db_connection()
    cursor = conn.cursor()
    tickers_id, tickers = util.get_tickers(cursor)
    time_now = datetime.now() + relativedelta(days=1)
    date = time_now.date()
    fetch_data(conn, cursor, tickers, tickers_id, date)
    sock.shutdown(socket.SHUT_RDWR)

    update_next_earning_date(conn, cursor, tickers_id, tickers)
    conn.close()


if __name__ == '__main__':
    if args.debug or args.dev:
        print("Dev mode: ", args.dev, "\tDebug:", args.debug)
    main()
