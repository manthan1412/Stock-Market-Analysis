import requests
import os
from util import Util

util = Util(socket_connection=False)
args = util.get_args()
shorten = {'5min': '5m', '15min': '15m', '60min': '60m', '4hour': '4h', '1day': '1d', '1week': '1w'}
notification_api = os.environ['BASE_API'] +  'tickers/notification-new/'
headers = {'Authorization': 'Token ' + args.token}

def create_empty_setting(primary_type=None, primary_tf=None, secondary=None):
    return {
        'primary_type': primary_type,
        'primary_tf': primary_tf,
        'secondary': secondary
    }

def parse_notification(settings):
    data = []
    index_map = {}

    if settings['primary']:
        for primary_setting in settings['primary'].split(','):
            primary_type, tf = primary_setting.split('-')
            tf = shorten[tf]
            if tf not in index_map:
                index_map[tf] = len(data)
                data.append(create_empty_setting(primary_tf=tf))
            data[index_map[tf]]['primary_type'] = int(primary_type)

    if settings['secondary']:
        for secondary_setting in settings['secondary'].split(','):
            secondary_type, tf = secondary_setting.split('-')
            tf = shorten[tf]
            if tf not in index_map:
                index_map[tf] = len(data)
                data.append(create_empty_setting(primary_tf=tf))
            data[index_map[tf]]['secondary'] = int(secondary_type)
    return data

def copy_notification(ticker, notification):
    info = {
        'ticker': ticker,
        'is_global': False,
        'bungee': False,
        'settings': parse_notification(notification)
    }
    response = requests.post(notification_api, headers=headers, json=info)
    print('------------------')
    print(info)
    print(response.text)
    print(response.status_code)
    print('--------------\n')


def copy_notifications(ticker, notifications):
    for notification in notifications:
        copy_notification(ticker, notification)

def main():
    ticker_notification_data, global_notification_data = util.get_old_notification_data()
    for ticker_id, notification in ticker_notification_data.items():
        copy_notifications(util.reverse_tickers_id[ticker_id], notification)

if __name__ == '__main__':
    main()
