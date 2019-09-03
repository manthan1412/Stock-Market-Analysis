import os
from datetime import datetime
from enum import Enum

green = 'Green'
yellow = 'Yellow'
red = 'Red'
null = ''
primary_type_map = {0: green, 1: yellow, 2: red, None: ''}
sma_cross_map = {True: red, False: green}
rsi_threshold_map = {1: green, 2: red, 0: null}
new_line = "<br>"
primary_tf_map = {'5min': '5M', '15min': '15M', '60min': '60M', '4hour': '4 Hourly', '1day': 'Daily', '1week': 'Weekly', '': '', None: ''}
intervals = ['5min', '15min', '60min', '4hour', '1day', '1week']
sentinel_url = os.environ['SENTINEL_URL']


class NotificationType(Enum):
    TICKER = 0
    GLOBAL = 1


class NotificationSettingType(Enum):
    Dial = 'Main Dial Change'
    Bungee = 'Bungee'
    Bolt = 'Bolt Notification'
    SmaCross = 'SMA Cross Notification'


def bungee_match(signals, bungee_setting):
    return eval('signals.bungee_' + bungee_setting['color'] + bungee_setting['operator'] + bungee_setting['value'])


def is_none_or_equal(setting_value, signal_value):
    return setting_value is None or setting_value == signal_value


def is_none_or_bungee_match(bungee_notification_id, interval_signals, bungee_settings):
    return bungee_notification_id is None\
        or all(bungee_match(interval_signals, bungee_setting)
            for bungee_setting in bungee_settings[bungee_notification_id]["settings"])


def interal_signals_match(interval_signals, setting, bungee_settings):
    return is_none_or_equal(setting["primary_type"], interval_signals.primary_type) \
        and is_none_or_equal(setting["sma_cross"], interval_signals.sma_cross) \
        and is_none_or_equal(setting["secondary"], interval_signals.secondary) \
        and is_none_or_equal(setting["rsi_threshold"], interval_signals.rsi_threshold) \
        and is_none_or_bungee_match(setting["bungee_notification_id"], interval_signals, bungee_settings)


def ticker_interval_setting_match(interval, ticker_signals, setting, bungee_settings):
    return ticker_signals.has_interval_signals(interval) \
        and interal_signals_match(ticker_signals.get_interval_signals(interval), setting, bungee_settings)


def setting_match(ticker_signals, setting, bungee_settings):
    if setting["primary_tf"]:
        return ticker_interval_setting_match(setting["primary_tf"], ticker_signals, setting, bungee_settings)
    return any(ticker_interval_setting_match(interval, ticker_signals, setting, bungee_settings)
        for interval in intervals)


def notification_match(ticker_signals, notification_settings, bungee_settings):
    return all(setting_match(ticker_signals, setting, bungee_settings)
               for setting in notification_settings["settings"])


def get_dial_trend_message(ticker_signal, interval):
    return "{}{}".format(ticker_signal.get_interval_signals(interval).to_dial_notification_message(interval), new_line)

def get_notification_type(setting):
    if setting["is_bungee"] is False:
        return NotificationSettingType.Dial
    if setting["settings"][0]:
        if any(ns["bungee_notification_id"] is not None or ns["primary_tf"] is not None for ns in setting["settings"]):
            return NotificationSettingType.Bungee
        if any(ns["rsi_threshold"] is not None for ns in setting["settings"]):
            return NotificationSettingType.Bolt
        if any(ns["sma_cross"] is not None for ns in setting["settings"]):
            return NotificationSettingType.SmaCross
    return NotificationSettingType.Bungee


def trend_across_all_tf(trends):
    return "{0}<b>**Trends across all timeframes**</b>{0}{1}".format(new_line, trends)


def dial_notification_message(ticker_signals, prev_ticker_signals, notification_setting, bungee_settings):
    message = []
    prev_trend, new_trend = ["{}Previous Trend: ".format(new_line)], ["New Trend: "]
    for ns in notification_setting["settings"]:
        message.append("Timeframe: <b>{}: {}</b>{}".format(primary_tf_map[ns["primary_tf"]], primary_type_map[ns["primary_type"]], new_line))
        message.append("Type of Bungee event: <b>{}</b>{}".format("Not Applicable", new_line))
        prev_trend.append(get_dial_trend_message(prev_ticker_signals, ns["primary_tf"]))
        new_trend.append(get_dial_trend_message(ticker_signals, ns["primary_tf"]))
    message.extend(prev_trend)
    message.extend(new_trend)
    message.append(trend_across_all_tf(ticker_signals.to_dial_notification_message(new_line)))
    return message

def bungee_notification_message(ticker_signals, prev_ticker_signals, notification_setting, bungee_settings):
    message = []
    for ns in notification_setting["settings"]:
        if ns["primary_tf"] is None:
            message.append("<b> Any timeframe</b>")
        else:
            message.append(" Timeframe: <b>{}</b>".format(primary_tf_map[ns["primary_tf"]]))
        if ns["primary_type"] is not None:
            message.append(" <b>({})</b>".format(primary_type_map[ns["primary_type"]]))
        if ns["sma_cross"] is not None:
            message.append(", SMA cross: {}".format(sma_cross_map[ns["sma_cross"]]))
        if ns["rsi_threshold"] is not None:
            message.append(", Bolt: {}".format(rsi_threshold_map[ns["rsi_threshold"]]))
        message.append(new_line);
        if ns["bungee_notification_id"] is not None:
            message.append(" Type of Bungee event: <b>{}</b>{}".format(bungee_settings[ns["bungee_notification_id"]]["name"], new_line))
    message.append(trend_across_all_tf(ticker_signals.to_bungee_notification_message(new_line)))
    return message

def bolt_notification_message(ticker_signals, prev_ticker_signals, notification_setting, bungee_settings):
    message = []
    for ns in notification_setting["settings"]:
        if ns["rsi_threshold"] is not None:
            message.append(" Bolt: <b>{}</b>{}".format(rsi_threshold_map[ns["rsi_threshold"]], new_line))
    message.append(trend_across_all_tf(ticker_signals.to_bolt_notification_message(new_line)))
    return message

def sma_cross_notification_message(ticker_signals, prev_ticker_signals, notification_setting, bungee_settings):
    message = []
    for ns in notification_setting["settings"]:
        if ns["sma_cross"] is not None:
            message.append(" SMA cross: <b>{}</b>{}".format(sma_cross_map[ns["sma_cross"]], new_line))
    message.append(trend_across_all_tf(ticker_signals.to_sma_cross_notification_message(new_line)))
    return message

notification_message_map = {
    NotificationSettingType.Dial: dial_notification_message,
    NotificationSettingType.Bungee: bungee_notification_message,
    NotificationSettingType.Bolt: bolt_notification_message,
    NotificationSettingType.SmaCross: sma_cross_notification_message
}


def get_ticker_interval_link(ticker, interval):
    ticker_url = "{}?ticker={}&interval={}".format(sentinel_url, ticker, interval)
    return "{1}{1}Ticker URL: <a href='{0}'>{0}</a>".format(ticker_url, new_line)


def create_message(ticker, ticker_signals, prev_ticker_signals, notification_setting, bungee_settings):
    curr_time = datetime.now()
    message = []
    include_trends = False
    notification_type = get_notification_type(notification_setting)
    message.append("Symbol:  <b>{}</b>{}".format(ticker, new_line))
    message.append("Date: {}{}".format(curr_time.date().strftime('%d/%m/%Y'), new_line))
    message.append("Time: <b>{}</b>{}".format(curr_time.time().strftime('%H:%M hrs'), new_line))
    message.append("Current price: <b>${}</b>{}".format(ticker_signals.price, new_line))
    message.append("Notification Setting: <b>{}</b>{}".format(notification_type.value, new_line))
    message.extend(notification_message_map[notification_type](ticker_signals, prev_ticker_signals, notification_setting, bungee_settings))
    message.append(get_ticker_interval_link(ticker, notification_setting["settings"][0]["primary_tf"]))
    return "{} alert for {} via Sentinel".format(notification_type.value, ticker), "".join(message)


def send_notification(util, ticker_id, notification_id, notification_setting, notification_sent, ticker_belong_to_users, ticker_signals, prev_ticker_signals, bungee_settings):
    if (ticker_id, notification_id) in notification_sent:
        util.log("Notification match, but not updated", notification_setting)
        return
    if notification_setting["user_id"] in ticker_belong_to_users:
        subject, message = create_message(util.reverse_tickers_id[ticker_id],
                                 ticker_signals,
                                 prev_ticker_signals,
                                 notification_setting,
                                 bungee_settings)
        util.notify_user(subject, message, notification_setting["user_id"], ticker_id, notification_id)


def get_notification_settings(notification_data, notification_type, ticker_id):
    if notification_type == NotificationType.TICKER:
        if notification_data.has_ticker_notification_setting(ticker_id):
            return notification_data.get_ticker_notification_setting(ticker_id)
    if notification_type == NotificationType.GLOBAL:
        return notification_data.get_global_notifications()
    return {}


def send_notification_if_match(util, ticker_id, ticker_signals, prev_ticker_signals, notification_data, notification_type):
    notification_settings = get_notification_settings(notification_data, notification_type, ticker_id)
    util.log_print_level("Notification type: ", notification_type, "\nNotifications:", notification_settings)
    notification_sent = notification_data.get_notification_sent()
    bungee_settings = notification_data.get_bungee_settings()
    ticker_belong_to_users = util.get_ticker_to_users(ticker_id)
    for notification_id, notification_setting in notification_settings.items():
        if notification_match(ticker_signals, notification_setting, bungee_settings):
            send_notification(util, ticker_id, notification_id, notification_setting, notification_sent, ticker_belong_to_users, ticker_signals, prev_ticker_signals, bungee_settings)
        else:
            util.renew_notification_sent(ticker_id, notification_id)


def check(util, ticker_id, prev_ticker_signals, notification_data):
    ticker_signals = util.get_ticker_signals(ticker_id)
    send_notification_if_match(util,
                               ticker_id,
                               ticker_signals,
                               prev_ticker_signals,
                               notification_data,
                               NotificationType.TICKER)
    send_notification_if_match(util,
                               ticker_id,
                               ticker_signals,
                               prev_ticker_signals,
                               notification_data,
                               NotificationType.GLOBAL)
