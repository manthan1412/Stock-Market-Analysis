from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from rest_framework import views
from rest_framework.response import Response
from django.http import HttpResponse
from django.contrib.auth.models import User
from .models import Tickers, StockHistData, Stock5Min, Stock15Min, Stock60Min, Stock4Hour, Stock1Day, Stock1Week, SignalData, BungeeNotification, BungeeNotificationSettings, NotificationNew, NotificationGroup
from users.models import UserTickers
from .serializers import TickersSerializer
from django.db import transaction
import datetime
from dateutil.relativedelta import relativedelta
import csv
import numpy
import json
import dateutil.parser
import socket
import os.path
import pandas as pd
import subprocess
import time
import pytz
from django.db import IntegrityError
from yahoo_earnings_calendar import YahooEarningsCalendar
from datetime import datetime
import traceback


yec = YahooEarningsCalendar()
model_ab = ['5m', '15m', '60m', '4h', '1d', '1w']
in_order = model_ab
abbr = {'5min': '5m', '15min': '15m', '60min': '60m', '4hour': '4h', '1day': '1d', '1week': '1w'}
full = {'5m': '5min', '60m': '60min', '1d': '1day', '15m': '15min', '1w': '1week', '4h': '4hour'}
minutes = {'5m': 5, '15m': 15, '60m': 60, '4h': 4*60, '1d': 24*60, '1w': 24*60*7}
higher_timeframes = set(['1d', '1w'])
models = {'5m': Stock5Min, '15m': Stock15Min, '60m': Stock60Min, '4h': Stock4Hour, '1d': Stock1Day, '1w': Stock1Week}
host = "127.0.0.1"
port = 9100
sock = None
default_points = 2000
date_format = '%d/%m/%y'
begin_time = '09:30:00'
end_time = '16:00:00'


class CSVView(views.APIView):

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)

        data = request.data
        if 'ticker' not in data:
            return HttpResponse('ticker data missing', status=400)

        if 'type' not in data:
            return HttpResponse('type data missing', status=400)
        ticker = data['ticker']
        signal_type = data['type']
        user = request.user

        try:
            ticker_instance = get_object_or_404(Tickers, ticker=ticker)
        except Exception as e:
            print(str(e))
            return HttpResponse('invalid ticker data', status=400)
        try:
            delete_file = subprocess.Popen('rm csv/*', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out, err) = delete_file.communicate()

            if err.decode('ascii'):
                if 'No such file or directory' in err.decode('ascii'):
                    # print(err.decode('ascii'))
                    pass
                else:
                    return HttpResponse('Error while deleting old ticker data' + str(err.decode('ascii')), status=400)

            local_tz = pytz.timezone("America/New_York")
            if signal_type == 'all':
                for signal_type in model_ab:
                    model = models[signal_type]
                    if signal_type in higher_timeframes:
                        signal_data = model.objects.filter(ticker=ticker_instance).order_by('-end_time')
                    else:
                        signal_data = model.objects.filter(ticker=ticker_instance, time__gte=begin_time, time__lt=end_time).order_by('-end_time')
                    # signal_data = model.objects.filter(ticker=ticker_instance, time__gte=begin_time, time__lt=end_time).order_by('-end_time')
                    with open('csv/' + ticker + '_' + full[signal_type] + '.csv', 'w') as f:
                        f.write("{0},{1},{2},{3},{4}\n".format("time", "open", "high", "low", "close"))
                        for sig_data in signal_data:
                            # end_time = dateutil.parser.parse(str(sig_data.end_time))
                            # end_time_nyc = local_tz.localize(end_time)
                            if signal_type == '1d' or signal_type == '1w':
                                end_time_nyc = sig_data.end_time
                            else:
                                end_time_nyc = sig_data.end_time.astimezone(local_tz)
                            f.write("{0},{1},{2},{3},{4}\n".format(str(end_time_nyc), str(sig_data.open), str(sig_data.high), str(sig_data.low), str(sig_data.close)))

                ## edit this zip command
                create_zip = subprocess.Popen('zip -9 csv/' + ticker + '.zip csv/' + ticker + '_*.csv', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                (out, err) = create_zip.communicate()
                filename = ticker + '.zip'

                if err.decode('ascii'):
                    return HttpResponse('Error while creating  ticker data' + str(err.decode('ascii')), status=400)

            else:
                try:
                    model = models[signal_type]
                except Exception as e:
                    return HttpResponse('invalid signal type', status=400)

                if signal_type in higher_timeframes:
                    signal_data = model.objects.filter(ticker=ticker_instance).order_by('-end_time')
                else:
                    signal_data = model.objects.filter(ticker=ticker_instance, time__gte=begin_time, time__lt=end_time).order_by('-end_time')
                filename = ticker + '_' + full[signal_type] + '.csv'

                with open('csv/' + filename, 'w') as f:
                    f.write("{0},{1},{2},{3},{4}\n".format("time", "open", "high", "low", "close"))
                    for sig_data in signal_data:
                        if signal_type == '1d' or signal_type == '1w':
                            end_time_nyc = sig_data.end_time
                        else:
                            end_time_nyc = sig_data.end_time.astimezone(local_tz)
                        f.write("{0},{1},{2},{3},{4}\n".format(str(end_time_nyc), str(sig_data.open), str(sig_data.high), str(sig_data.low), str(sig_data.close)))

            return Response({'status': 'files successfully created', 'filename': filename})
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Server error' + str(e), status=500)

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)

        data = request.data
        if 'filename' not in data:
            return HttpResponse('filename missing', status=400)
        filename = data['filename']
        try:
            delete_file = subprocess.Popen('rm csv/' + filename, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out, err) = delete_file.communicate()
            if err.decode('ascii'):
                return HttpResponse('Error while deleting old ticker data' + str(err.decode('ascii')), status=400)
            return Response({'status': 'files successfully deleted'})
        except Exception as e:
            print(str(e))
            return HttpResponse('Server error' + str(e), status=500)


class DeleteTicker(views.APIView):

    def delete(self, request):

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        deleted = []

        if user.is_superuser:
            data = request.data
            tickers = data["tickers"]
            if type(tickers) is list:

                for ticker in tickers:
                    print("deleting", ticker)
                    ticker_instance = get_object_or_404(Tickers, ticker=ticker)
                    ticker_instance.is_active = False
                    ticker_instance.save()
                return Response({"tickers": {"deleted": tickers}})
            else:
                return HttpResponse('Bad request', status=400)
        else:
            return HttpResponse('You don\'t have access to this API', status=403)


'''class GlobalNotificationView(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        data = GlobalNotification.objects.filter(user_id = user.id).all()
        result = []
        for row in data:
            result.append([row.id, row.primary, row.secondary])
        return Response({'result': result})

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        data = request.data

        if 'primary' not in data:
            primary = None
        else:
            primary = data['primary']

        if 'secondary' not in data:
            secondary = None
        else:
            secondary = data['secondary']

        if not primary and not secondary:
            return HttpResponse('At least primary of secondary is required', status=400)
        notif_instance, created = GlobalNotification.objects.get_or_create(user=user, primary=primary, secondary=secondary)
        return Response({'status': "notification is successfully added"})

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        data = request.data

        if 'id' not in data:
            return HttpResponse('id is missing', status=400)
        notification_id = data['id']
        try:
            GlobalNotification.objects.get(id=notification_id, user=user).delete()
        except Exception as e:
            print(str(e))
            return HttpResponse('Either id is wrong or that notification doesn\'t belong to your profile', status=400)
        return Response({'status': 'Notification deleted successfully'})
'''


def delete_bungee_notification_setting(bungee_notif_id, user):
    try:
        BungeeNotification.objects.get(id=bungee_notif_id, user=user).delete()
    except Exception as e:
        traceback.print_exc()
        return HttpResponse('Either id is wrong or that bungee notification setting doesn\'t belong to your profile', status=400)
    return Response({'status': 'Notification deleted successfully'})


def serialize_bungee_notif(bns):
    return {
                'operator': bns.operator,
                'bungee_color': bns.bungee_color,
                'bungee_value': bns.bungee_value,
           }


def serialize_bungee_settings(id_name_map, bungee_notification_settings):
    index = {}
    serialized = []
    for bns in bungee_notification_settings:
        if bns.bungee_notification_id in index:
            serialized[index[bns.bungee_notification_id]]['settings'].append(serialize_bungee_notif(bns))
        else:
            index[bns.bungee_notification_id] = len(serialized)
            serialized.append({
                                'id': bns.bungee_notification_id,
                                'name': id_name_map[bns.bungee_notification_id],
                                'settings': [serialize_bungee_notif(bns)],
                                })
    return serialized


def add_bungee_notification_setting(user, settings, bungee_notification, delete_if_error=True):
    try:
        for setting in settings:
            BungeeNotificationSettings(bungee_notification=bungee_notification, operator=setting['operator'], bungee_color=setting['bungee_color'], bungee_value=setting['bungee_value']).save()
        return Response({'status': 'Bungee Notification Setting added/edited successfully.', 'id': bungee_notification.id})
    except:
        traceback.print_exc()
        if delete_if_error:
            delete_bungee_notification_setting(bungee_notification.id, user)
        return HttpResponse('Improper bungee settings', status=400)


def get_bungee_notifications(bungee_notif_id, user, wrap_in_response):
    if bungee_notif_id is None:
        return Response({}) if wrap_in_response else [{}]
    if bungee_notif_id == -1:
        bungee_notification = BungeeNotification.objects.filter(user=user)
        id_name_map = {bn.id: bn.name for bn in bungee_notification}
        bungee_notication_settings = BungeeNotificationSettings.objects.filter(bungee_notification__in=bungee_notification)
    else:
        try:
            bungee_notification = BungeeNotification.objects.get(id=bungee_notif_id, user=user)
            id_name_map = {bungee_notification.id: bungee_notification.name}
            bungee_notication_settings = BungeeNotificationSettings.objects.filter(bungee_notification=bungee_notification)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Either id is wrong or that notification doesn\'t belong to your profile', status=400)
    response = serialize_bungee_settings(id_name_map, bungee_notication_settings)
    return Response(response) if wrap_in_response else response


class BungeeNotificationView(views.APIView):
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        return get_bungee_notifications(int(request.GET.get('id', -1)), request.user, wrap_in_response=True)

    def put(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        bungee_notif_id = int(request.data.get('id', -1))
        if bungee_notif_id == -1:
            return HttpResponse('Id is missing', status=400)
        bungee_notification = get_object_or_404(BungeeNotification, id=bungee_notif_id, user=request.user)
        try:
            bungee_notification.name = request.data.get('name')
            bungee_notification.save()
            BungeeNotificationSettings.objects.filter(bungee_notification=bungee_notification).delete()
            return add_bungee_notification_setting(request.user, request.data.get('settings'), bungee_notification, delete_if_error=False)
        except:
            traceback.print_exc()
            return HttpResponse('Something went wrong', status=500)

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        try:
            bungee_notification = BungeeNotification(name=request.data.get('name'), user=request.user)
            bungee_notification.save()
            return add_bungee_notification_setting(request.user, request.data.get('settings'), bungee_notification, delete_if_error=True)
        except:
            traceback.print_exc()
            return Response({'status': 'Something went wrong'})

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        bungee_notif_id = request.data.get('id', None)
        if bungee_notif_id is None:
            return HttpResponse('id is missing', status=400)
        return delete_bungee_notification_setting(bungee_notif_id, request.user)


def delete_notification_group(id, user):
    try:
        NotificationGroup(user=user, id=id).delete()
        return Response({'status': 'Notification deleted successfully'})
    except:
        traceback.print_exc()
        return HttpResponse('Something went wrong while deleting notification with id ' + id, status=500)


def serialize_notification(ns, user):
    return {
        'primary_tf': ns.primary_tf,
        'primary_type': ns.primary_type,
        'secondary': ns.secondary,
        'sma_cross': ns.sma_cross,
        'bolt': ns.rsi_threshold,
        'bungee_notification': {
                                'id': ns.bungee_notification_id,
                                'name': ns.bungee_notification.name if ns.bungee_notification_id else 'None'
        },
        #'bungee_notification': get_bungee_notifications(ns.bungee_notification_id, user, wrap_in_response=False)[0],
    }


def serialize_notification_settings(ticker, is_global, note, group_id_and_detail_map, notification_settings, user):
    if ticker is None or ticker == global_str:
        is_global = True
    index = {}
    serialized = []
    for ns in notification_settings:
        if ns.notification_group_id not in index:
            index[ns.notification_group_id] = len(serialized)
            serialized.append(dict(group_id_and_detail_map[ns.notification_group_id]))
        serialized[index[ns.notification_group_id]]['settings'].append(serialize_notification(ns, user))
    serialized.sort(key=lambda x: (x['bungee'], x['active']))
    return {'ticker': ticker, 'notifications': serialized, 'is_global': is_global, 'note': note, 'settings_length': len(notification_settings)}


def convert_to_group_id_map(notification_groups):
    return {n_g.id:
            {
                'id': n_g.id,
                'is_global': n_g.is_global,
                'time': n_g.time,
                'active': n_g.active,
                'deleted': n_g.deleted,
                'bungee': n_g.bungee,
                'settings': [],
            } for n_g in notification_groups}

def str_or_none(a):
    return None if a is None or a == '' else str(a)

def int_or_none(a):
    return None if a is None or a == '' else int(a)

def bool_or_none(a):
    return None if a is None or a == '' else bool(a)

def add_new_notification(settings, notification_group, user, delete_if_error=True):
    try:
        for setting in settings:
            NotificationNew(notification_group=notification_group,
                            primary_tf=str_or_none(setting.get('primary_tf')),
                            primary_type=int_or_none(setting.get('primary_type')),
                            secondary=int_or_none(setting.get('secondary')),
                            sma_cross=bool_or_none(setting.get('sma_cross')),
                            rsi_threshold=int_or_none(setting.get('bolt')),
                            bungee_notification_id=int_or_none(setting.get('bungee_notification_id'))).save()
        return Response({'status': 'Notification added/edited successfully', 'id': notification_group.id})
    except:
        traceback.print_exc()
        if delete_if_error:
            delete_notification_group(notification_group.id, user)
        return HttpResponse('Bad request', status=400)


def zip_dict(*dicts):
    for key in set(dicts[0]).intersection(*dicts[1:]):
        yield (key,) + tuple(d[key] for d in dicts)

global_str = 'GLOBAL'
def get_key_from_ng(ng):
    return ng.ticker.ticker if ng.ticker else global_str


class AllNotificationsView(views.APIView):
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        filter_map = {'user': request.user}
        if not request.GET.get('include_deleted'):
            filter_map['deleted'] = False
        if request.GET.get('bungee'):
            filter_map['bungee'] = True if request.GET.get('bungee') == 't' or request.GET.get('bungee') == 'true' else False
        notification_groups = NotificationGroup.objects.filter(**filter_map)
        notification_settings = NotificationNew.objects.filter(notification_group__in=notification_groups)
        notification_group_to_ticker = {ng.id: get_key_from_ng(ng) for ng in notification_groups}
        ticker_notification_group = defaultdict(list)
        for ng in notification_groups:
            ticker_notification_group[get_key_from_ng(ng)].append(ng)
        ticker_notification_settings = defaultdict(list)
        for ns in notification_settings:
            ticker_notification_settings[notification_group_to_ticker[ns.notification_group_id]].append(ns)
        user_tickers = UserTickers.objects.filter(user=request.user)
        ticker_note = {ut.ticker.ticker: ut.note for ut in user_tickers}

        # for global
        ticker_note[global_str] = ''

        response = [serialize_notification_settings(ticker, False, note, convert_to_group_id_map(ng), ns, request.user)
             for ticker, ng, ns, note in
             zip_dict(ticker_notification_group, ticker_notification_settings, ticker_note)]
        response.sort(key= lambda x: (x['is_global'], x['ticker']))
        return Response(response)

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        NotificationGroup.objects.filter(user=request.user).update(deleted=True)
        return Response({'status': 'All notifications deleted successfully'})


class ActivateDeactivateNotificationView(views.APIView):
    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        active = request.data.get('active', False)
        id = request.data.get('id')
        NotificationGroup.objects.filter(user=request.user, id=id).update(active=active)
        return Response({'status': "activated" if active else "paused"})


class NewNotificationView(views.APIView):
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        ticker = request.GET.get('ticker')
        is_global = request.GET.get("is_global", "").lower()
        bungee = request.GET.get('bungee').lower()
        bungee = True if bungee == 't' or bungee == 'true' else False
        is_global = True if is_global == 't' or is_global == 'true' else False
        if is_global:
            notification_groups = NotificationGroup.objects.filter(is_global=is_global, user=request.user, bungee=bungee, deleted=False)
            note = ''
            ticker = None
        elif ticker is not None:
            ticker_instance = get_object_or_404(Tickers, ticker=ticker)
            notification_groups = NotificationGroup.objects.filter(ticker=ticker_instance, user=request.user, bungee=bungee, deleted=False)
            user_tickers = UserTickers.objects.get(ticker=ticker_instance, user=request.user)
            note = user_tickers.note
        else:
            return HttpResponse('Bad request', status=400)
        notification_settings = NotificationNew.objects.filter(notification_group__in=notification_groups)
        return Response([serialize_notification_settings(ticker, is_global, note, convert_to_group_id_map(notification_groups), notification_settings, request.user)])

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        is_global = data.get('is_global')
        ticker = None if is_global else get_object_or_404(Tickers, ticker=data.get('ticker'))
        bungee = data.get('bungee')
        try:
            notification_group = NotificationGroup(ticker=ticker, user=request.user, is_global=is_global, bungee=bungee)
            notification_group.save()
            return add_new_notification(data.get('settings'), notification_group, request.user, delete_if_error=True)
        except:
            traceback.print_exc()
            return HttpResponse('Something went wrong', status=500)

    def put(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        notification_group = get_object_or_404(NotificationGroup, id=request.data.get('id'), user=request.user)
        NotificationNew.objects.filter(notification_group=notification_group).delete()
        return add_new_notification(request.data.get('settings'), notification_group, request.user, delete_if_error=False)

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        return delete_notification_group(request.data.get('id'), request.user)


'''class NotificationView(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        try:
            ticker = request.GET.get('ticker')
        except Exception as e:
            print(str(e))
            return HttpResponse('Missing ticker', status=400)
        try:
            ticker_instance = get_object_or_404(Tickers, ticker=ticker)
        except Exception as e:
            print(str(e))
            return HttpResponse('Wrong ticker data', status=400)
        data = Notification.objects.filter(user_id = user.id, ticker=ticker_instance).all()
        result = []
        for row in data:
            result.append([row.id, row.primary, row.secondary])
        return Response({'result': result})

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        data = request.data
        if 'ticker' not in data:
            return HttpResponse('Missing ticker', status=400)
        if 'primary' not in data:
            primary = None
        else:
            primary = data['primary']

        if 'secondary' not in data:
            secondary = None
        else:
            secondary = data['secondary']

        if not primary and not secondary:
            return HttpResponse('At least primary of secondary is required', status=400)
        ticker = data['ticker']
        try:
            ticker_instance = get_object_or_404(Tickers, ticker=ticker)
        except Exception as e:
            print(str(e))
            return HttpResponse('Wrong ticker data', status=400)

        notif_instance, created = Notification.objects.get_or_create(ticker=ticker_instance, user=user, primary=primary, secondary=secondary)
        return Response({'status': "notification is successfully added"})

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        data = request.data
        if 'id' not in data:
            return HttpResponse('id is missing', status=400)
        notification_id = data['id']
        try:
            Notification.objects.get(id=notification_id, user=user).delete()
        except Exception as e:
            print(str(e))
            return HttpResponse('Either id is wrong or that notification doesn\'t belong to your profile', status=400)
        return Response({'status': 'Notification deleted successfully'})
'''

class GetTicker(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        if user.is_superuser:
            tickers = Tickers.objects.all()
            serializer = TickersSerializer(tickers, many=True)
            return Response({'tickers': serializer.data})
        else:
            return HttpResponse('You don\'t have access to this API', status=403)


class GetActiveTicker(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        if user.is_superuser:
            tickers = Tickers.objects.filter(is_active=True)
            serializer = TickersSerializer(tickers, many=True)
            return Response({'tickers': serializer.data})
        else:
            return HttpResponse('You don\'t have access to this API', status=403)


class UpdateTicker(views.APIView):

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', stauts=401)
        user = request.user
        if user.is_superuser:
            data = request.data
            update_by = data['update_by']
            if update_by == "ticker":
                ticker = get_object_or_404(Tickers, ticker = data["ticker"])
                ticker.full_name = data["full_name"]
            elif update_by == "full_name":
                ticker = get_object_or_404(Tickers, full_name = data["full_name"])
                ticker.ticker = data["ticker"]
            ticker.save()
            return Response({"status" : "Updated successfully"})
        else:
            return HttpResponse('You don\'t have access to this API', status=403)


class NextEarningDate(views.APIView):

    def post(self, request):
        data = request.data

        if request.auth is None or not request.user.is_superuser:
            return HttpResponse('Unauthorized access', status=401)
        if 'tickers' not in data or type(data['tickers']) is not list or 'next_earning_dates' not in data or \
                type(data['next_earning_dates']) is not list or len(data['tickers']) != len(data['next_earning_dates']):
            return HttpResponse('Bad request 3', status=400)

        try:
            tickers = data["tickers"]
            next_earning_dates = data['next_earning_dates']
            for ticker, next_earning_date in zip(tickers, next_earning_dates):
                try:
                    ticker_instance = Tickers.objects.get(ticker=ticker)
                    next_earning = datetime.strptime(next_earning_date, date_format).date()

                    # if next_earning > ticker_instance.next_earning_date:
                    ticker_instance.next_earning_date = next_earning
                    ticker_instance.save()

                except Exception as e:
                    traceback.print_exc()
                    return HttpResponse('Check next earning date format: dd/mm/yy', status=400)
                pass
                # timestamp = yec.get_next_earnings_date(ticker)
                # results[ticker] = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
            return Response({'status': "Earning dates updated successfully"})
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Bad request 2', status=400)


def current_signal(ticker_id):
    results = {"5m": None, "15m": None, "60m": None, "4h": None, '1d': None, '1w': None}
    data = SignalData.objects.filter(ticker_id=ticker_id)
    for d in data:
        results[abbr[d.interval]] = {'type': d.type, 'age': d.age, 'time': str(d.time), 'price': d.price}
    res = []
    for interval in in_order:
        if results[interval]:
           res.append({interval: results[interval]})
    return res


def secondary_signal(ticker_id):
    results = {"5m": None, "15m": None, "60m": None, "4h": None, '1d': None, '1w': None}
    data = SignalData.objects.filter(ticker_id=ticker_id)
    for d in data:
        results[abbr[d.interval]] = {'type': d.second}
    return results

