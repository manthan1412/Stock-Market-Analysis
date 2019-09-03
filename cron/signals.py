import notifications
import traceback
import pandas as pd
from signal_helper import main_signal, second_signal, sma_cross, rsi_threshold, bungee_values, candlestick_shapes, royal_signal

data_limit = 4000
date_time = {"5min": 0, "15min": 0, "60min": 0, "4hour": 0, "1day": 1, "1week": 1}
stock_tables = ["5min", "15min", "60min", "4hour", "1day", "1week"]
requires_date_format = {"1day", "1week"}
translate = {0: 'Green', 1: 'Yellow', 2: 'Red'}
begin_time = "09:30:00"
end_time = "16:00:00"


def get_data_sql(interval, ticker_id):
    if interval in requires_date_format:
        return  "select open, close, low, high, end_time from stocks_stock{0} WHERE ticker_id={1} ORDER BY end_time DESC limit {2}".format(interval, ticker_id, data_limit)
    return "select open, close, low, high, end_time from stocks_stock{0} WHERE ticker_id={1} and time >= '{2}' and time < '{3}' ORDER BY end_time DESC limit {4}".format(interval, ticker_id, begin_time, end_time, data_limit)


def update_signals(util, tickers, tickers_id, intervals=stock_tables):
    notification_data = util.get_notification_data()
    args = util.get_args()
    util.print_msg("Starting to update signals")
    for ticker in tickers:
        util.log("Updating signals for ", ticker)
        ticker_id = tickers_id[ticker]
        prev_ticker_signals = util.get_ticker_signals(ticker_id)
        for interval in intervals:
            if args.debug:
                print(interval, end='\t')
            df = pd.DataFrame(util.query_select(get_data_sql(interval, ticker_id)),
                              columns=['Open', 'Close', 'Low', 'High', 'end_time'])
            df = df[::-1]
            df.index = df.index[::-1]
            # df = df.reindex(index=df.index[::-1])

            try:
                signal_type, signal_age = main_signal(df)
                signal_type, signal_age = int(signal_type), int(signal_age)
                sec_sig = second_signal(df)
                bungee_yellow, bungee_green, bungee_blue, bungee_red = bungee_values(df)
                candlestick_shapes_sig, candlestick_shapes_age = candlestick_shapes(df)
                sma_cross_sig, sma_cross_candles = sma_cross(df)
                rsi_threshold_sig, rsi_threshold_candles = rsi_threshold(df)
                royal_sig, royal_sig_age = royal_signal(df)
                if args.debug:
                    print("main signal", signal_type, signal_age, end='\t')
                    print("second signal", sec_sig, end='\t')
                    print("sma_cross", sma_cross_sig, sma_cross_candles, end='\t')
                    print("rsi_threshold", rsi_threshold_sig, rsi_threshold_candles, end='\t')
                    print("bungee_values", bungee_yellow, bungee_green, bungee_blue, bungee_red, end='\t')
                    print("candlestick_shapes", candlestick_shapes_sig, candlestick_shapes_age, end='\t')
                    print("royal signal", royal_sig, royal_sig_age)
                sma_cross_sig = 'true' if sma_cross_sig else 'false'
                entry = df.iloc[df.shape[0] - signal_age - 1]
                signal_time, price = entry['end_time'], entry['Close']
                signal_data = util.query_select(
                    "select type, age, second, time from stocks_signaldata where ticker_id={0} AND interval='{1}'"
                    .format(ticker_id, interval))
                signals = [price, str(signal_time), signal_type, signal_age, sec_sig, sma_cross_sig, sma_cross_candles,
                           rsi_threshold_sig, rsi_threshold_candles, bungee_yellow, bungee_green, bungee_blue,
                           bungee_red, candlestick_shapes_sig, candlestick_shapes_age, royal_sig, royal_sig_age]

                if not signal_data or not signal_data[0]:
                    try:
                        query = "INSERT INTO stocks_signaldata (ticker_id, interval, price, time, type, age, second, " \
                                "sma_cross, sma_cross_candles, rsi_threshold, rsi_threshold_candles, " \
                                "bungee_values_yellow, bungee_values_green, bungee_values_blue, bungee_values_red, " \
                                "candlestick_shapes, candlestick_shapes_age, royal_sig, royal_sig_age) " \
                                "VALUES ({0},'{1}',{2},'{3}',{4},{5},{6},{7},{8},{9},{10},{11},{12},{13},{14},{15}," \
                                "{16},{17},{18})".format(ticker_id, interval, *signals)
                        util.query_insert(query, commit=True)
                    except Exception:
                        traceback.print_exc()
                        util.query_rollback()
                else:
                    try:
                        query = "UPDATE stocks_signaldata " \
                                "SET price={2},time='{3}',type={4},age={5},second={6},sma_cross={7},sma_cross_candles={8}," \
                                "rsi_threshold={9},rsi_threshold_candles={10},bungee_values_yellow={11}," \
                                "bungee_values_green={12},bungee_values_blue={13},bungee_values_red={14}," \
                                "candlestick_shapes={15},candlestick_shapes_age={16},royal_sig={17}, royal_sig_age={18} " \
                                "WHERE ticker_id={0} AND interval='{1}'".format(ticker_id, interval, *signals)
                        util.query_update(query, commit=True)
                    except Exception:
                        traceback.print_exc()
                        util.query_rollback()
            except Exception:
                util.print_msg(ticker_id)
                traceback.print_exc()
        notifications.check(util, ticker_id, prev_ticker_signals, notification_data)
    util.update_notification_is_sent()
