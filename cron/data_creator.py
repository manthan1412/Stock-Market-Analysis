from util import Util
from dateutil import parser
from psycopg2 import IntegrityError
import traceback

indices = {
    'end_time': 0,
    'open': 1,
    'low': 2,
    'high': 3,
    'close': 4,
    'volume': 5,
    'time': 6,
}


class DataCreator:

    def __init__(self, table_data_list, util_instance=None, tickers=None, tickers_id=None):
        self.util = util_instance if util_instance else Util(socket_connection=False)
        self.args = self.util.get_args()
        if not tickers or not tickers_id:
            self.tickers, self.tickers_id = self.util.get_tickers()
        else:
            self.tickers, self.tickers_id = tickers, tickers_id
        self.tables = table_data_list
        self.new_util = False if util_instance else True

    def start(self):
        for table_data in self.tables:
            self.util.log("Creating new data for setting: " + str(table_data))
            self.__generate_new_data(table_data)
        if self.new_util:
            self.util.close()

    @staticmethod
    def __should_merge(current, data, current_date, from_tf):
        return current < len(data) \
               and data[current][indices['end_time']].date() == current_date \
               and parser.parse(from_tf[0]).time() <= data[current][indices['time']] <= parser.parse(from_tf[-1]).time()

    @staticmethod
    def __get_lhc(data, low=float('inf'), high=float('-inf'), volume=0):
        return min(low, data[indices['low']]), max(high, data[indices['high']]), data[indices['close']], volume + data[indices['volume']]

    def __get_end_time(self, end_date, end_time):
        return self.util.localize(parser.parse(end_time).replace(year=end_date.year, month=end_date.month, day=end_date.day))

    def __store_or_update(self, queries, interval, ticker_id):
        try:
            for query in queries:
                sql_query = self.util.get_sql_insert_query(interval, ticker_id, query[0], query[1], query[2], query[3], query[4], query[5])
                self.util.log(sql_query)
                if self.args.fetch:
                    continue
                self.util.query_insert(sql_query, commit=False)
            self.util.query_commit()
        except IntegrityError:
            self.util.query_rollback()
            for query in queries:
                try:
                    self.util.query_insert(self.util.get_sql_insert_query(
                        interval, ticker_id, query[0], query[1], query[2], query[3], query[4], query[5]),
                                            commit=True)
                except IntegrityError:
                    self.util.query_rollback()
                    try:
                        # util.log("data already exist")
                        sql_query = self.util.get_sql_update_query(
                            interval, ticker_id, query[0], query[1], query[2], query[3], query[4], query[5])
                        self.util.query_update(sql_query, commit=True)
                        self.util.log(sql_query)
                    except Exception:
                        self.util.query_rollback()
                        traceback.print_exc()
                except Exception:
                    self.util.query_rollback()
                    traceback.print_exc()
        except Exception:
            self.util.query_rollback()
            traceback.print_exc()

    def __create_new_data(self, ticker_id, table_from, table_to, from_tf, to_tf, start_time):
        data = self.util.get_historic_data(start_time, table_from, from_tf, ticker_id)
        current = 0
        queries = []
        while current < len(data) and str(data[current][indices['time']]) != from_tf[0]:
            current += 1
        while current < len(data):
            current_date = data[current][indices['end_time']].date()
            open = data[current][indices['open']]
            low, high, close, volume = self.__get_lhc(data[current])
            self.util.log(data[current])
            current += 1
            while self.__should_merge(current, data, current_date, from_tf):
                self.util.log(data[current])
                low, high, close, volume = self.__get_lhc(data[current], low, high, volume)
                current += 1
            end_time = self.__get_end_time(current_date, to_tf)
            queries.append((open, low, high, close, end_time, volume))
            if self.args.wait:
                self.__store_or_update([queries.pop()], table_to, ticker_id)
                input()
        self.__store_or_update(queries, table_to, ticker_id)

    def __get_start_time(self, start_time, ticker_id, table_name):
        if start_time:
            return start_time
        data = self.util.query_select(
            "select end_time from stocks_stock{0} where ticker_id={1} order by end_time desc limit 1"
                .format(table_name, ticker_id))
        if not data or not data[0]:
            return ''
        return str(data[0][0].replace(tzinfo=None))

    def __generate_new_data(self, table_data):
        table_from = table_data['from']
        table_to = table_data['to']
        timeframes = table_data['timeframes']
        for ticker in self.tickers:
            self.util.log("Creating new data for " + ticker)
            ticker_id = self.tickers_id[ticker]
            start_time = self.__get_start_time(table_data['start_time'], ticker_id, table_data['to'])
            for from_tf, to_tf in timeframes.items():
                self.__create_new_data(ticker_id, table_from, table_to, from_tf, to_tf, start_time)


if __name__ == "__main__":
    tables = [
        {
            'from': '60min',
            'to': '4hour',
            'start_time': '',
            'timeframes': {
                ('09:30:00', '10:30:00', '11:30:00', '12:30:00'): '09:30:00',
                ('13:30:00', '14:30:00', '15:30:00'): '13:30:00',
            },
        },
    ]
    DataCreator(tables).start()
