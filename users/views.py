import datetime
import os
import subprocess
import threading
import traceback
from .models import UserTickers, UserTickerIntervalFeatures, ScriptUpdate, UserNoteImages, WatchListNotes
from .serializers import UserTickersSerializer
from ast import literal_eval
from collections import defaultdict
from django.contrib.auth.models import User
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from rest_framework import views, parsers, renderers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from stocks.models import Tickers, Stock5Min, Stock15Min, Stock60Min, Stock4Hour, Stock1Day, Stock1Week, SignalData, StockUpdate, BungeeNotification, BungeeNotificationSettings
from users.protobufs.python_proto.profile_pb2 import Profile
from users.serializers import TokenSerializer

version = '1.0.6'
updatable_fileds = set(["target_value", "grade", "watch_list", "note"])
interval_features = set(["wave_rating", "divergence_symbol"])
default_interval_features = {"wave_rating": "", "divergence_symbol": None}
note_field = "note"
note_updated_field = "note_updated"
note_created_field = "note_created"
note_images_field = "note_images"
full_form = {'5m': '5min', '15m': '15min', '60m': '60min', '4h': '4hour', '1d': '1day', '1w': '1week', '': ''}
abbr_form = {v: k for k, v in full_form.items()}
signals = ['primary', 'secondary', 'sma_cross', 'rsi_threshold', 'bungee', 'candlestick_shape', 'royal_signal']
candlestick_shapes = ['Doji', 'Evening Star', 'Morning Star', 'Hammer', 'Inverted Hammer', 'Bearish Engulfing',
                      'Bullish Engulfing', 'Hanging Man', 'Dark Cloud Cover']
interval_type_map = {'5min': Profile._5M, '15min': Profile._15M, '60min': Profile._60M, '4hour': Profile._4H, '1day': Profile._1D, '1week': Profile._1W}
bungee_map = {'y': 'bungee_values_yellow', 'g': 'bungee_values_green', 'b': 'bungee_values_blue', 'r': 'bungee_values_red'}
time_in_past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


def authToken(request):
    t = []
    for user in User.objects.all():
        token = Token.objects.get_or_create(user = user)
        print(token[0])

    return HttpResponse("Just using", t)


class TokenView(views.APIView):
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (
        parsers.FormParser,
        parsers.MultiPartParser,
        parsers.JSONParser,
     )

    renderer_classes = (renderers.JSONRenderer,)

    def post(self, request):
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        try:
            token, created = Token.objects.get_or_create(user=user)
            data = {'token' : str(token)}
            return Response(data)
        except:
            return Response({"non_field_errors":["Username or password are not correct."]})


def get_time():
    time_data = StockUpdate.objects.all().order_by('-time').first()
    return time_data.time, time_data.ongoing


class UserProfileView(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        user = request.user
        page = int(request.GET.get('page', 0))
        offset = int(request.GET.get('offset', 500))
        sort_by = request.GET.get('sort_by', 'positions')
        rating = request.GET.get('rating', None)
        proto = request.GET.get('proto', False)
        if not rating:
            if sort_by == 'rating':
                tickers = UserTickers.objects.filter(user=user, is_active=True).order_by('rating')[page*offset: page*offset + offset]
            elif sort_by == 'ticker':
                tickers = UserTickers.objects.filter(user=user, is_active=True).order_by('ticker__ticker')[
                          page * offset: page * offset + offset]
            else:
                tickers = UserTickers.objects.filter(user=user, is_active=True)[page * offset: page * offset + offset]
        else:
            if sort_by == 'rating':
                tickers = UserTickers.objects.filter(user=user, is_active=True, rating=rating).order_by('rating')[page*offset: page*offset + offset]
            elif sort_by == 'ticker':
                tickers = UserTickers.objects.filter(user=user, is_active=True, rating=rating).order_by('ticker__ticker')[page * offset: page * offset + offset]
            else:
                tickers = UserTickers.objects.filter(user=user, is_active=True, rating=rating)[page * offset: page * offset + offset]
        response = []

        ticker_ids = [ticker.ticker_id for ticker in tickers]
        ticker_instances = get_ticker_instances(ticker_ids)
        signal_data = get_signal_data(ticker_ids)
        if proto:
            user_ticker_interval_features = get_user_ticker_interval_features_for_proto(request.user)
            profile = Profile()
            for ticker in tickers:
                ticker_in_proto(profile, ticker, ticker_instances[ticker.ticker_id],
                                user_ticker_interval_features[ticker.ticker_id],
                                signal_data[ticker.ticker_id])
            return HttpResponse(add_profile_data(profile).SerializeToString())
        else:
            user_ticker_interval_features = get_user_ticker_interval_features(request.user)
            user_ticker_note_images = get_user_ticker_note_images(request.user)
            for ticker in tickers:
                response.append(serialize_tickers(ticker,
                                                  ticker_instances[ticker.ticker_id],
                                                  user_ticker_interval_features[ticker.ticker_id],
                                                  user_ticker_note_images[ticker.ticker_id],
                                                  signal_data[ticker.ticker_id]))
            return Response(ticker_response(response))


def get_signal_data(ticker_ids):
    data = SignalData.objects.filter(ticker_id__in=ticker_ids)
    signal_data = defaultdict(list)
    for d in data:
        signal_data[d.ticker_id].append(d)
    return signal_data

def get_signal_data_by_interval(ticker_ids):
    data = SignalData.objects.filter(ticker_id__in=ticker_ids)
    signal_data = defaultdict(dict)
    for d in data:
        signal_data[d.ticker_id][d.interval] = d
    return signal_data


def get_user_ticker_interval_features_for_proto(user):
    user_ticker_interval_features = defaultdict(dict)
    ticker_interval_features = UserTickerIntervalFeatures.objects.filter(user=user)

    for feature in ticker_interval_features:
        user_ticker_interval_features[feature.ticker.id][feature.interval] = feature
    return user_ticker_interval_features


def get_ticker_instances(ticker_ids):
    ticker_instances = Tickers.objects.filter(id__in=ticker_ids)
    return {ticker_instance.id: ticker_instance for ticker_instance in ticker_instances}


def set_type_and_age(sig_data, sig_type, sig_age):
    sig_data.type = sig_type
    sig_data.age = sig_age


def set_primary_data(sig_data, sig_type, sig_age, sig_time, sig_price):
    sig_data.price = sig_price
    sig_data.time = str(sig_time)
    set_type_and_age(sig_data.type_age, sig_type, sig_age)
    return sig_data


def set_bungee_data(sig_data, y, g, r, b):
    sig_data.y = y
    sig_data.g = g
    sig_data.r = r
    sig_data.b = b
    return sig_data


def add_interval_data(ticker_data, ticker_interval_features, signal_data, ticker_id):
    data = signal_data if signal_data else SignalData.objects.filter(ticker_id=ticker_id)
    for d in data:
        interval_data = ticker_data.interval_data.add()
        interval_data.interval = interval_type_map[d.interval]
        if d.interval in ticker_interval_features:
            interval_data.wave_rating = ticker_interval_features[d.interval].wave_rating
            if ticker_interval_features[d.interval].divergence_symbol:
                interval_data.divergence_symbol = ticker_interval_features[d.interval].divergence_symbol
        set_primary_data(interval_data.primary, d.type, d.age, d.time, d.price)
        interval_data.secondary = d.second
        set_type_and_age(interval_data.rsi_threshold, d.rsi_threshold, d.rsi_threshold_candles)
        set_type_and_age(interval_data.candlestick_shape, d.candlestick_shapes, d.candlestick_shapes_age)
        set_type_and_age(interval_data.sma_cross, d.sma_cross, d.sma_cross_candles)
        set_bungee_data(interval_data.bungee, d.bungee_values_yellow, d.bungee_values_green, d.bungee_values_red,
                        d.bungee_values_blue)
        set_type_and_age(interval_data.royal_signal, d.royal_sig, d.royal_sig_age)


def ticker_in_proto(profile, ticker, ticker_instance, ticker_interval_features, signal_data=None):
    ticker_data = profile.tickers.add()
    ticker_data.ticker = ticker_instance.ticker
    ticker_data.price = ticker_instance.price
    ticker_data.next_earning_date = str(ticker_instance.next_earning_date)
    ticker_data.change = ticker_instance.percent_change
    ticker_data.last30days_avg_volume = ticker_instance.last30days_avg_volume
    ticker_data.last_day_volume = ticker_instance.last_day_volume
    ticker_data.position = ticker.position
    ticker_data.note = ticker.note
    ticker_data.note_updated = str(ticker.note_updated)
    ticker_data.rating = ticker.rating
    ticker_data.grade = ticker.grade
    if ticker.target_value:
        ticker_data.target_value = ticker.target_value
    if ticker.watch_list:
        ticker_data.watch_list = ticker.watch_list
    add_interval_data(ticker_data, ticker_interval_features, signal_data, ticker_instance.id)


def add_profile_data(profile):
    last_updated, ongoing = get_time()
    profile.last_updated = str(last_updated)
    profile.ongoing = ongoing
    profile.script_updated = str(ScriptUpdate.objects.filter()[0].updated)
    profile.version = version
    return profile


class UserProfileSortView(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)

        dials = literal_eval(request.GET.get('dials', '[]'))
        settings = literal_eval(request.GET.get('settings', '[]'))
        proto = request.GET.get('proto', False)

        filter_dict = {}

        if len(dials) > 0:
            filter_dict['interval'] = full_form[dials[0].split('-')[1]]
            # first = full_form[dials[0].split('-')[1]]
        elif len(settings) > 0:
            if is_not_empty(settings[0]['primary_tf']) and is_not_empty(settings[0]['primary_type']):
                filter_dict['interval'] = full_form[settings[0]['primary_tf']]
                filter_dict['type'] = settings[0]['primary_type']
                if is_not_empty(settings[0]['bolt']):
                    filter_dict['rsi_threshold'] = settings[0]['bolt']
                if is_not_empty(settings[0]['sma_cross']):
                    filter_dict['sma_cross'] = settings[0]['sma_cross']
            # first = full_form[settings[0]['primary_tf']]
        else:
            return HttpResponse('Bad request', status=400)
        response = []
        try:
            matched_ids, ticker_data, signal_data, signal_updated_time = get_matched_ticker_ids(request.user, dials, settings)
            if filter_dict:
                filter_dict['ticker_id__in'] = matched_ids
                sorted_ids = SignalData.objects.filter(**filter_dict).values_list('ticker_id', flat=True).order_by('-time')
                #print(SignalData.objects.filter(**filter_dict).values_list('ticker_id', flat=True).query)
            else:
                sorted_tuples = sorted([(v, k) for k, v in signal_updated_time.items() if k in matched_ids], reverse=True)
                sorted_ids = [ticker_id for _, ticker_id in sorted_tuples]
                #print(sorted_tuples)
            #print(matched_ids)
            #print(signal_updated_time)
            #if first is None or first == "":
            #    sorted_ids = SignalData.objects.values('ticker_id').filter(ticker_id__in=matched_ids).annotate(t=Max('time')).order_by('-t').values_list('ticker_id', flat=True) #.distinct('ticker_id')
            #else:
            #    sorted_ids = Tickers.objects.filter(id__in=matched_ids).order_by('-time').values_list('id', flat=True).distinct()
            #sorted_ids = SignalData.objects.values('ticker_id').filter(interval=full_form[first], ticker_id__in=matched_ids).order_by('-time')
            #print(sorted_ids)
            #print(SignalData.objects.values('ticker_id').filter(ticker_id__in=matched_ids).annotate(t=Max('time')).order_by('-t').values_list('ticker_id', flat=True).query)
            ticker_instances = get_ticker_instances(sorted_ids)
            ticker_interval_features = get_user_ticker_interval_features(request.user)
            user_ticker_note_images = get_user_ticker_note_images(request.user)
            for ticker_id in sorted_ids:
                #ticker_id = sorted_id['id']
                response.append(serialize_tickers(ticker_data[ticker_id],
                                                  ticker_instances[ticker_id],
                                                  ticker_interval_features[ticker_id],
                                                  user_ticker_note_images[ticker_id],
                                                  signal_data[ticker_id]))
        except Exception as e:
            traceback.print_exc()
            response = str(e)
        return Response(ticker_response(response))


def get_bungee_notification_settings(user):
    bungee_notifications = BungeeNotificationSettings.objects.filter(bungee_notification__in=BungeeNotification.objects.filter(user=user))
    bns = defaultdict(list)
    for bn in bungee_notifications:
        bns[bn.bungee_notification_id].append(bn)
    return bns


def dial_matches(interval, sig, value):
    return interval in sig and sig[interval].type == value


def bungee_match(bs, signal_data):
    return eval('signal_data.' + bungee_map[bs.bungee_color] + bs.operator + str(bs.bungee_value))


def is_empty(field):
    return field is None or field == ""


def is_not_empty(field):
    return field is not None and field != ""


def bungee_setting_matches(bungee_notification_id, signal_data, bungee_notifications):
    if is_empty(bungee_notification_id):
        return True
    return all(bungee_match(bn, signal_data) for bn in bungee_notifications[bungee_notification_id])


def interval_setting_matches(signal_last_updated, ticker_id, setting, signal_data, bungee_notifications):
    if is_not_empty(setting['primary_type']) and signal_data.type != setting['primary_type']:
        return False
    if is_not_empty(setting['bolt']) and signal_data.rsi_threshold != setting['bolt']:
        return False
    if is_not_empty(setting['sma_cross']) and signal_data.sma_cross != setting['sma_cross']:
        return False
    if bungee_setting_matches(setting['bungee_notification_id'], signal_data, bungee_notifications):
        signal_last_updated[ticker_id] = max(signal_last_updated[ticker_id], signal_data.time)
        return True
    return False


def setting_matches(signal_last_updated, ticker_id, setting, sig, bungee_notifications):
    interval = setting['primary_tf']
    if not interval:
        return any(interval_setting_matches(signal_last_updated, ticker_id, setting, signal_data, bungee_notifications) for _, signal_data in sig.items())
    if interval not in sig:
        return False
    return interval_setting_matches(signal_last_updated, ticker_id, setting, sig[interval], bungee_notifications)


def get_matched_ticker_ids(user, dials, settings):
    dials_to_match = {full_form[d.split('-')[1]]: int(d.split('-')[0]) for d in dials}
    tickers = UserTickers.objects.filter(user=user, is_active=True)
    ticker_ids = [ticker.ticker_id for ticker in tickers]
    signal_data = get_signal_data_by_interval(ticker_ids)
    bungee_notifications = get_bungee_notification_settings(user)

    matched_signal_data = {}
    matched_ticker_data = {}
    signal_last_updated = {ticker.ticker_id: time_in_past for ticker in tickers}
    for setting in settings:
        setting['primary_tf'] = full_form[setting['primary_tf']]
        setting['sma_cross'] = setting.get('sma_cross') if (setting.get('sma_cross') == '' or setting.get('sma_cross') is None) else bool(setting.get('sma_cross'))

    for ticker in tickers:
        sig = signal_data[ticker.ticker_id]
        if not all(dial_matches(interval, sig, value) for interval, value in dials_to_match.items()) \
           or not all(setting_matches(signal_last_updated, ticker.ticker_id, setting, sig, bungee_notifications) for setting in settings):
            continue
        matched_ticker_data[ticker.ticker_id] = ticker
        matched_signal_data[ticker.ticker_id] =  signal_data[ticker.ticker_id].values()
    return matched_ticker_data.keys(), matched_ticker_data, matched_signal_data, signal_last_updated


class UserRatingTickersView(views.APIView):
    '''
	sample:
	with token
	{
		"ticker" : 'AAPL',
		"rating" : 4
	}
    '''

    def post(self, request):
        data = request.data

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'ticker' not in data or 'rating' not in data:
            return HttpResponse('Bad request', status=400)

        try:
            rating = data["rating"]
            ticker_instance = Tickers.objects.get(ticker=data['ticker'])
            UserTickers.objects.filter(user=request.user, ticker=ticker_instance, is_active=True).update(rating=rating)
            return Response({"status": data['ticker'] + " rating updated successfully"})
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Bad request 2', status=400)


class GetUserTickersView(views.APIView):
    '''
    sample:
    send query parameter username
    '''
    def get(self, request):

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)

        tickers = UserTickers.objects.filter(user=request.user, is_active=True)
        serializer = UserTickersSerializer(tickers, many=True)
        return Response({'data': serializer.data})


class UpdateTickerPositionView(views.APIView):
    '''
    sample:
    with token
    {
        "username" : 'username',
        "tickers" : ['AAPL', 'FB'],
        "positions" : [2, 1]
    }
    '''

    def post(self, request):
        data = request.data
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'username' not in data or 'tickers' not in data or 'positions' not in data\
                or type(data['tickers']) != list or type(data['positions']) != list \
                or len(data['tickers']) != len(data['positions']):
            return HttpResponse('Bad request', status=400)

        if request.user.username == data['username']:
            for ticker, position in zip(data['tickers'], data['positions']):
                try:
                    ticker_instance = Tickers.objects.get(ticker=ticker, is_active=True)
                    UserTickers.objects.filter(user=request.user, ticker=ticker_instance, is_active=True).update(
                        position=position)
                except:
                    return HttpResponse('Bad request', status=400)
            return Response({"status": "Positions updated successfully"})
        else:
            return HttpResponse('You don\'t have access', status=403)


def attach_note_images(ticker_instance, user, note_image_ids):
    note_images = UserNoteImages.objects.filter(user=user, id__in=note_image_ids)
    note_images.update(ticker=ticker_instance)


class UpdateUserTickerData(views.APIView):
    def post(self, request):
        data = request.data
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'ticker' not in data:
            return HttpResponse('Bad request', status=400)
        ticker = data['ticker']
        response = {}
        try:
            ticker_instance = Tickers.objects.get(ticker=ticker, is_active=True)
            user_ticker = UserTickers.objects.filter(user=request.user, ticker=ticker_instance, is_active=True)
            fields = {}
            for field in updatable_fileds:
                if field in data:
                    fields[field] = data[field]
                    if field == note_field:
                        current_time = timezone.now()
                        if user_ticker:
                            if not user_ticker[0].note_updated:
                                fields[note_created_field] = current_time
                                response[note_created_field] = fields[note_created_field]
                            else:
                                response[note_created_field] = user_ticker[0].note_created
                            attach_note_images(ticker_instance, request.user, data.get(note_images_field, []))
                        if not data[note_field]:
                            fields[note_created_field] = None
                            fields[note_updated_field] = None
                            response[note_created_field] = fields[note_created_field]
                            response[note_updated_field] = fields[note_updated_field]
                        else:
                            fields[note_updated_field] = current_time
                            response[note_updated_field] = fields[note_updated_field]
            user_ticker.update(**fields)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Bad request', status=400)
        response["status"] = "Ticker data updated successfully"
        return Response(response)


class UpdateUserTickerIntervalFeatures(views.APIView):
    def post(self, request):
        data = request.data
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'ticker' not in data or 'interval' not in data:
            return HttpResponse('Bad request', status=400)
        ticker = data['ticker']
        interval = data['interval']
        try:
            ticker_instance = Tickers.objects.get(ticker=ticker, is_active=True)
            fields = {}
            for interval_feature in interval_features:
                if interval_feature in data:
                    fields[interval_feature] = data[interval_feature]
            UserTickerIntervalFeatures.objects.update_or_create(user=request.user, ticker=ticker_instance, interval=interval, defaults=fields)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Bad request', status=400)
        return Response({"status": "Ticker interval features updated successfully"})


class ScriptUpdateView(views.APIView):
    def post(self, request):
        if request.auth is None or request.user.is_superuser is False:
            return HttpResponse('Unauthorized access', status=401)
        try:
            s = ScriptUpdate.objects.filter().order_by('-updated').first()
            s.save()
        except Exception as e:
            traceback.print_exc()
            s = ScriptUpdate()
            s.save()
        return Response({'updated': s.updated})


class UserNoteImageView(views.APIView):
    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        if 'file_name' not in data or 'data' not in data:
            return HttpResponse('Bad request', status=400)
        try:
            # print (data['data'].encode('utf-8'))
            image = UserNoteImages(user=request.user, image_name=data['file_name'], image_data=data['data'].encode('utf-8'))
            image.save()
            return Response({'file_name': data['file_name'], 'status': 'ok', 'file_id': image.id})
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Server Error', status=500)

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        file_id = request.GET.get('file_id', None)
        if file_id is None:
            return HttpResponse('Bad request', status=400)
        image = get_object_or_404(UserNoteImages, id=int(file_id), user=request.user)
        try:
            return HttpResponse(image.image_data)  # , content_type='application/octet-stream')
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Server Error', status=500)

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        if 'file_id' not in data:
            return HttpResponse('Bad request', status=400)
        try:
            UserNoteImages.objects.filter(id=data['file_id'], user=request.user).delete()
            return Response({'status': 'Image deleted'})
        except Exception:
            traceback.print_exc()
            return HttpResponse('Not found', status=404)


class WatchListNoteHistoryView(views.APIView):
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        watch_list_notes = WatchListNotes.objects.filter(user=request.user).order_by('-created_time')
        response = []
        for watch_list_note in watch_list_notes:
            note_images_id_list = []
            file_names_list = []
            note_data = {
                'data': {'note_id': watch_list_note.id, 'updated': watch_list_note.updated_time, 'created': watch_list_note.created_time},
                'info': {
                    'note_data': watch_list_note.note_data,
                    'note_images': note_images_id_list,
                },
                'file_names': file_names_list,
            }
            note_images = UserNoteImages.objects.filter(note_id=watch_list_note, user=request.user)
            for note_image in note_images:
                note_images_id_list.append(note_image.id)
                file_names_list.append(note_image.image_name)
            response.append(note_data)
        return Response(response)


class WatchListNotesView(views.APIView):

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        note_id = request.GET.get('note_id', None)
        if note_id is None:
            return HttpResponse('Bad request', status=400)
        watch_list_note = get_object_or_404(WatchListNotes, id=int(note_id), user=request.user)
        try:
            return Response({
                'note_id': watch_list_note.id,
                'note_data': watch_list_note.note_data,
                'created': watch_list_note.created_time,
                'updated': watch_list_note.updated_time,
                'note_images': get_note_images(watch_list_note.id, request.user),
            })
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Server Error', status=500)

    def post(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        if 'note_data' not in data or 'note_images' not in data or type(data['note_images']) is not list:
            return HttpResponse('Bad request', status=400)
        watch_list_note = WatchListNotes(user=request.user, note_data=data['note_data'])
        watch_list_note.save()
        try:
            UserNoteImages.objects.filter(user=request.user, id__in=data['note_images']).update(note_id=watch_list_note.id)
        except Exception:
            print("Error in assigning note id to images")
            traceback.print_exc()
        return Response({'status': 'ok', 'note_id': watch_list_note.id, 'updated': watch_list_note.updated_time, 'created': watch_list_note.created_time})

    def put(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        if 'note_id' not in data or 'note_data' not in data or 'note_images' not in data or type(data['note_images']) is not list:
            return HttpResponse('Bad request', status=400)
        watch_list_note = get_object_or_404(WatchListNotes, user=request.user, id=int(data['note_id']))
        try:
            watch_list_note.note_data = data['note_data']
            watch_list_note.save()
            UserNoteImages.objects.filter(user=request.user, id__in=data['note_images']).update(note_id=watch_list_note.id)
        except Exception:
            print("Error in assigning note id to images")
            traceback.print_exc()
        return Response({'status': 'ok', 'note_id': watch_list_note.id, 'updated': watch_list_note.updated_time, 'created': watch_list_note.created_time})

    def delete(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        data = request.data
        if 'note_id' not in data:
            return HttpResponse('Bad request', status=400)
        try:
            WatchListNotes.objects.filter(id=data['note_id'], user=request.user).delete()
            return Response({'status': 'Note deleted'})
        except Exception:
            traceback.print_exc()
            return HttpResponse('Not found', status=404)


def get_serialized_note_image(note_image):
    return {
        'file_id': note_image.id,
        'image_name': note_image.image_name,
        'image_data': note_image.image_data,
    }


def get_note_images(note_id, user):
    note_images = UserNoteImages.objects.filter(note_id=note_id, user=user)
    return [get_serialized_note_image(note_image) for note_image in note_images]

def get_user_ticker_note_images(user):
    note_images = UserNoteImages.objects.filter(user=user, ticker__isnull=False)
    user_ticker_note_images = defaultdict(list)
    for note_image in note_images:
        user_ticker_note_images[note_image.ticker_id].append(note_image)
    return user_ticker_note_images


class DeleteUserTickersView(views.APIView):
    '''
    sample:
    with token
    {
        "username" : 'username',
        "tickers" : ['AAPL', 'FB']
    }
    '''

    def delete(self, request):
        data = request.data

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'username' not in data or 'tickers' not in data:
            return HttpResponse('Bad request', status=400)
        if request.user.username == data['username']:
            delete_tickers(data['tickers'], request.user)
            return Response({"status": "Deleted successfully"})
        else:
            return HttpResponse('You don\'t have access', status=403)


def serialize_signals(ticker_data, ticker_id, signal_data):
    data = signal_data if signal_data else SignalData.objects.filter(ticker_id=ticker_id)
    for sig in signals:
        ticker_data[sig] = {}
    for d in data:
        ticker_data["primary"][abbr_form[d.interval]] = {'type': d.type, 'age': d.age, 'time': str(d.time), 'price': d.price}
        ticker_data["secondary"][abbr_form[d.interval]] = d.second
        ticker_data["sma_cross"][abbr_form[d.interval]] = {'type': d.sma_cross, 'age': d.sma_cross_candles}
        ticker_data["rsi_threshold"][abbr_form[d.interval]] = {'type': d.rsi_threshold, 'age': d.rsi_threshold_candles}
        ticker_data["bungee"][abbr_form[d.interval]] = {'y': d.bungee_values_yellow, 'g': d.bungee_values_green, 'b': d.bungee_values_blue, 'r': d.bungee_values_red}
        ticker_data["candlestick_shape"][abbr_form[d.interval]] = {'type': d.candlestick_shapes, 'age': d.candlestick_shapes_age}
        ticker_data["royal_signal"][abbr_form[d.interval]] = {'type': d.royal_sig, 'age': d.royal_sig_age}
    return ticker_data


def serialize_ticker_note_images(ticker_note_images):
    return {note_image.id: note_image.image_name for note_image in ticker_note_images}


def serialize_tickers(ticker, ticker_instance, ticker_interval_features, ticker_note_images, signal_data=None):
    return ticker_interval_features.serialized(
        serialize_signals({
            'ticker': ticker_instance.ticker,
            'position': ticker.position,
            'rating': ticker.rating,
            'grade': ticker.grade,
            'target_value': ticker.target_value,
            'next_earning_date': ticker_instance.next_earning_date,
            'change': ticker_instance.percent_change,
            'price': ticker_instance.price,
            'last30days_avg_volume': ticker_instance.last30days_avg_volume,
            'last_day_volume': ticker_instance.last_day_volume,
            'watch_list': ticker.watch_list,
            'note': ticker.note,
            'note_updated': ticker.note_updated,
            'note_created': ticker.note_created,
            'note_images': serialize_ticker_note_images(ticker_note_images),
        }, ticker.ticker_id, signal_data))


class TickerFeatures:
    def __init__(self):
        self.interval = defaultdict(dict)

    def add_feature(self, feature):
        for feature_name in interval_features:
            self.interval[feature.interval][feature_name] = eval("feature.{0}".format(feature_name))

    def serialized(self):
        serialized_features = {}
        for interval in full_form.keys():
            serialized_features[interval] = self.interval[interval] if interval in self.interval \
                else default_interval_features
        return serialized_features

    def serialized(self, ticker_data):
        for feature in interval_features:
            ticker_feature = {}
            for interval in full_form.keys():
                if interval in self.interval:
                    ticker_feature[interval] = self.interval[interval][feature]
                # ticker_feature[interval] = self.interval[interval][feature] if interval in self.interval \
                #     else default_interval_features[feature]
            ticker_data[feature] = ticker_feature
        return ticker_data

    def __repr__(self):
        return str(self.interval)


def get_user_ticker_interval_features(user):
    user_ticker_interval_features = defaultdict(TickerFeatures)
    ticker_interval_features = UserTickerIntervalFeatures.objects.filter(user=user)

    for feature in ticker_interval_features:
        user_ticker_interval_features[feature.ticker.id].add_feature(feature)
    return user_ticker_interval_features


def ticker_response(tickers):
    last_updated, ongoing = get_time()
    return {
        'tickers': tickers,
        'last_updated': last_updated,
        'ongoing': ongoing,
        'version': version,
        'script_updated': ScriptUpdate.objects.filter()[0].updated
    }


def delete_tickers(tickers, user):
    for ticker in tickers:
        try:
            ticker_instance = Tickers.objects.get(ticker=ticker)
            t = UserTickers.objects.filter(ticker=ticker_instance, user=user)

            if t:
                t.delete()
            if UserTickers.objects.filter(ticker=ticker_instance):
                continue
            try:
                Stock5Min.objects.filter(ticker=ticker_instance).delete()
                Stock15Min.objects.filter(ticker=ticker_instance).delete()
                Stock60Min.objects.filter(ticker=ticker_instance).delete()
                Stock4Hour.objects.filter(ticker=ticker_instance).delete()
                Stock1Day.objects.filter(ticker=ticker_instance).delete()
                Stock1Week.objects.filter(ticker=ticker_instance).delete()
                SignalData.objects.filter(ticker=ticker_instance).delete()
            except Exception as e:
                print(str(e))
            ticker_instance.delete()
        except Exception as e:
            print(str(e))
            return HttpResponse('Bad request 2', status=400)
    remaining_tickers = UserTickers.objects.filter(user=user, is_active=True)
    if remaining_tickers:
        i = 1
        for ticker in remaining_tickers:
            ticker.position = i
            ticker.save()
            i += 1


def add_tickers(position, tickers, request, entries, interval, new=True):
    issue = []
    try:
        app_status_instance = StockUpdate.objects.order_by('-time')[:1]
        for app_status in app_status_instance:
            app_status.ongoing = True
            app_status.save()
            print('ongoing set to true')
    except Exception as e:
        print(str(e))

    for ticker in tickers:
        try:
            ticker_instance, created = Tickers.objects.get_or_create(ticker=ticker)
            user_ticker_instance, created = UserTickers.objects.get_or_create(user=request.user,
                                                                              ticker=ticker_instance)
            user_ticker_instance.is_active = True
            if new:
                user_ticker_instance.position = position
                user_ticker_instance.rating = 0
            user_ticker_instance.save()

            position += 1
        except Exception as e:
            print(str(e))
            issue.append(ticker)

    print("issue with: ", str(issue))
    command = "{} --tickers {}".format(os.environ['CRON_SCRIPT'], " ".join(tickers))
    print ("Running: {}", command)
    proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if err:
        print(err)
    else:
        print('done running cron.py')


class AddRemoveTickersView(views.APIView):

    def post(self, request):
        data = request.data

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'action' not in data or 'tickers' not in data or type(data['tickers']) != list:
            return HttpResponse('Bad request', status=400)
        action = data['action']
        entries = 0
        if 'entries' in data:
            if data['entries']:
                entries = int(data['entries'])

        # 0: regular
        # 1: extended
        interval = 1
        if 'interval' in data:
            if data['interval'] == '0':
                interval = 0

        if action == 'add':
            try:
                d = UserTickers.objects.filter(user=request.user).order_by('-position').first()
                if not d:
                    position = 1
                else:
                    position = d.position + 1
            except Exception as e:
                traceback.print_exc()
                position = 1

            args = [position, data['tickers'], request, entries, interval]
            background_thread = threading.Thread(target=add_tickers, args=args)
            background_thread.start()
            return Response({"status": "Adding tickers process is initiated"})

        elif action == 'remove':
            delete_tickers(data["tickers"], request.user)
            return Response({"status": "Deleted successfully"})


class ReloadUserTickersView(views.APIView):

    def post(self, request):
        data = request.data

        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        if 'tickers' not in data or type(data['tickers']) != list:
            return HttpResponse('Bad request', status=400)

        entries = 0
        interval = 1

        for ticker in data['tickers']:
            try:
                ticker_instance = Tickers.objects.get(ticker=ticker)
                try:
                    Stock5Min.objects.filter(ticker=ticker_instance).delete()
                    Stock15Min.objects.filter(ticker=ticker_instance).delete()
                    Stock60Min.objects.filter(ticker=ticker_instance).delete()
                    Stock4Hour.objects.filter(ticker=ticker_instance).delete()
                    Stock1Day.objects.filter(ticker=ticker_instance).delete()
                    Stock1Week.objects.filter(ticker=ticker_instance).delete()
                    SignalData.objects.filter(ticker=ticker_instance).delete()
                except Exception as e:
                    traceback.print_exc()

            except Exception as e:
                traceback.print_exc()
                return HttpResponse('Bad request 2', status=400)

        position = 1
        args = [position, data['tickers'], request, entries, interval, False]
        background_thread = threading.Thread(target=add_tickers, args=args)
        background_thread.start()
        return Response({"status": "Adding tickers process is initiated"})
