from .models import Charts
from dateutil.relativedelta import relativedelta
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import views
from rest_framework.response import Response
from stocks.models import Tickers, Stock5Min, Stock15Min, Stock60Min, Stock4Hour, Stock1Day, Stock1Week, Temp5Min, Temp15Min, Temp60Min, Temp4Hour, Temp1Day, Temp1Week
import datetime
import json
import pytz
import time


supported_resolutions = ['5', '15', '60', '240', '1D', '1W']
intraday_multipliers = supported_resolutions
#intraday_multipliers = ['5', '15', '60', '1D', '1W']
begin_time = datetime.time(9, 30)
end_time = datetime.time(16, 0)
local_tz = pytz.timezone("America/New_York")
weekly_timeframe = set(['W', '1W'])
resolution_to_model = {
            '5': Stock5Min,
            '15': Stock15Min,
            '60': Stock60Min,
            '240': Stock4Hour,
            '1D': Stock1Day,
            'D': Stock1Day,
            '1W': Stock1Week,
            'W': Stock1Week
        }
temp_model = {
            '5': Temp5Min,
            '15': Temp15Min,
            '60': Temp60Min,
            '240': Temp4Hour,
            '1D': Temp1Day,
            'D': Temp1Day,
            '1W': Temp1Week,
            'W': Temp1Week
        }

class ConfigView(views.APIView):

    """
    Trading View data feed configuration end point
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)

        supports_group_select = False
        supports_marks = False
        supports_search = True
        supports_timescale_marks = False
        return Response({
                'supported_resolutions': supported_resolutions,
                'supports_group_request': supports_group_select,
                'supports_marks': supports_marks,
                'supports_search': supports_search,
                'supports_timescale_marks': supports_timescale_marks
            })

def getDefaultSymbolInfo(symbol, group):
    exchange_listed = group
    min_movement = 1
    min_movement2 = 0
    has_dwm = True
    has_intraday = True
    has_daily = True
    has_weekly_and_monthly = True
    timezone = 'America/New_York'
    session_regular = '0930-1600'
    pricescale = 100
    has_no_volume = False
    sym_type = 'stock'

    return {
        'listed_exchange' : exchange_listed,
        'minmov' : min_movement,
        'minmov2' : min_movement2,
        'supported_resolutions': supported_resolutions,
        'has_intraday' : has_intraday,
        'intraday_multipliers': intraday_multipliers,
        'has_daily' : has_daily,
        'has_weekly_and_monthly' : has_weekly_and_monthly,
        'timezone' : timezone,
        'session' : session_regular,
        'symbol' : symbol,
        'description': symbol,
        'pricescale' : [pricescale for _ in range(len(symbol))] if type(symbol) == list else pricescale,
        'has_no_volume' : [has_no_volume for _ in range(len(symbol))] if type(symbol) == list else has_no_volume,
        'type': [sym_type for _ in range(len(symbol))] if type(symbol) == list else sym_type,
        'ticker' : symbol}


class SymbolInfoView(views.APIView):

    """
    Trading View data feed symbol group request endpoint
    """

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        group = request.GET.get('group', 'NYSE')
        symbol = []
        tickers = Tickers.objects.all()
        for ticker in tickers:
            symbol.append(ticker.ticker)
        return Response(getDefaultSymbolInfo(symbol, group))


class SymbolView(views.APIView):

    """
    Endpoint for symbol resolve
    """

    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        symbol = request.GET.get('symbol', 'AAPL').replace('NYSE:', '')
        group = 'NYSE'
        return Response(getDefaultSymbolInfo(symbol, group))


class SymbolSearchView(views.APIView):

    """
    Takes search query to search for ticker/symbol
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        q = request.GET.get('query', '')
        limit = int(request.GET.get('limit', 50))
        tickers = Tickers.objects.filter(ticker__startswith = q.upper()).order_by('ticker')[:limit]
        results = []
        exchange = 'NYSE'
        ticker_type = 'stock'
        for ticker in tickers:
            results.append({
                'symbol': ticker.ticker,
                'full_name': ticker.ticker,
                'description': ticker.full_name,
                'exchange' : exchange,
                'type' : ticker_type})
        return Response(results)


def timestamp_to_utc(timestamp):
    return local_tz.localize(datetime.datetime.fromtimestamp(int(timestamp))) #.replace(tzinfo=datetime.timezone.utc)

def from_start_time_to_end_time(given_time):
    return given_time + relativedelta(days=4)


def from_end_time_to_start_time(given_time, resolution):
    if resolution in weekly_timeframe:
        return given_time - relativedelta(days=4)
    return given_time

class BarsView(views.APIView):

    """
    To get historical ticker data such as OHCLV
    """

    def get(self, request):

        try:
            if request.auth is None:
                return HttpResponse('Unauthorized access', status=401)
            symbol = request.GET.get('symbol', '').replace('NYSE:', '')
            from_time = request.GET.get('from')
            if not from_time:
                return Response({'s' : 'error', 'errmsg' : 'From timestamp is missing.'})

            from_time = timestamp_to_utc(from_time)
            to_time = timestamp_to_utc(request.GET.get('to', time.time()))
            resolution = request.GET.get('resolution', '5')

            results = {
                's': 'ok',
                't': [], # Bar time in Unix timestamp (UTC)
                'c': [], # Closing price
                'o': [], # Opening price
                'h': [], # High price
                'l': [], # Low price
                'v': [], # Volume
            }

            s = set(['D', '1D', 'W', '1W'])
            special_tickers = set([])

            if symbol in special_tickers and resolution not in s:
                model = temp_model[resolution]
            else:
                model = resolution_to_model[resolution]
            if resolution in s:
                if resolution in weekly_timeframe:
                    from_time = from_start_time_to_end_time(from_time)
                    to_time = from_start_time_to_end_time(to_time)
                data = model\
                        .objects\
                        .filter(ticker__ticker=symbol,
                                end_time__gte=from_time,
                                end_time__lte=to_time)\
                        .order_by('end_time')
            else:
                data = model\
                        .objects\
                        .filter(ticker__ticker=symbol,
                                end_time__gte=from_time,
                                end_time__lte=to_time,
                                time__gte=begin_time,
                                time__lt=end_time)\
                        .order_by('end_time')
            for row in data:
                """
                if resolution in s:
                    t = datetime.datetime(row.end_time.year, row.end_time.month, row.end_time.day)\
                                .replace(tzinfo=datetime.timezone.utc)
                else:
                    #print (row.end_time.weekday())
                    #if row.end_time.hour < low or (row.end_time.hour == low and row.end_time.minute < 30):
                    #    continue
                    #if row.end_time.hour >= high: #or (row.end_time.hour == high and row.end_time.minute == 0):
                    #    continue
                    t = row.end_time
                """
                results['c'].append(row.close)
                results['o'].append(row.open)
                results['h'].append(row.high)
                results['l'].append(row.low)
                t = from_end_time_to_start_time(datetime.datetime(row.end_time.year, row.end_time.month, row.end_time.day), resolution) if resolution in s else row.end_time
                results['t'].append(int(t.timestamp()))
                results['v'].append(row.volume)

            if not data:
                next = resolution_to_model[resolution]\
                                    .objects\
                                    .filter(ticker__ticker=symbol,
                                            end_time__lte=from_time)\
                                    .order_by('-end_time')[:1]
                if next:
                    t = datetime.datetime(next[0].end_time.year, next[0].end_time.month, next[0].end_time.day)\
                                .replace(tzinfo=datetime.timezone.utc)\
                             if resolution in s else next[0].end_time
                    return Response({
                                's': 'no_data',
                                'nextTime': int(t.timestamp())})
            return Response(results)
        except Exception as e:
            return Response({'s': 'error', 'errmsg': str(e)})


class MarksView(views.APIView):
    """
    Returns marks data, called if support_marks is True.
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        results = {}
        return Response(results)


class TimescaleMarksView(views.APIView):
    """
    Returns time scale marks data, called if support_timescale_marks is True.
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        results = {}
        return Response(results)


class ServerTimeView(views.APIView):

    """
    Return the current server time in seconds after the epoch
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        return HttpResponse(str(int(time.time())), status=200)


class QuotesView(views.APIView):

    """
    Returns a quote of given list of symbols
    """
    def get(self, request):
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        try:
            symbols = request.GET.get('symbols', '')
            symbols = symbols.split(',') if symbols else []
            symbols = [sym.replace('NYSE:', '') for sym in symbols]
            s = set(symbols)
            occurred = set()
            results = {'s': 'ok', 'd': []}
            ticker_data = Stock5Min.objects.filter(ticker__ticker__in = symbols).order_by('-end_time')[:len(symbols)]
            for data in ticker_data:
                if data.ticker.ticker in s and data.ticker.ticker not in occurred:
                    results['d'].append({
                        's' : 'ok',
                        'n' : data.ticker.ticker,
                        'v' : {
                            'chp' : data.ticker.percent_change,
                            'short_name' : data.ticker.ticker,
                            'exchange' : 'NYSE',
                            'description' : data.ticker.ticker,
                            'open_price': data.open,
                            'high_price': data.high,
                            'low_price': data.low,
                            'prev_close_price': data.close
                        }})
                    occurred.add(data.ticker.ticker)
            left = s - occurred
            for sym in left:
                results['d'].append({'s' : 'error', 'errmsg': 'data for {0} not found'.format(sym)})
            return Response(results)
        except Exception as e:
            return Response({'s': 'error', 'errmsg' : str(e)})



class ChartsView(views.APIView):

    """
    API endpoint for saving and getting chart
    """

    def get(self, request):
        """
        Get saved layout of a chart
        """
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        client = request.GET.get('client', None)
        user = request.GET.get('user', request.user)
        chart_id = request.GET.get('chart', None)
        chart_name = request.GET.get('chartName', None)
        if not user or not client:
            return HttpResponse('Invalid data. You must provide ids of client and user.', status=400)
        try:
            if chart_name:
                try:
                    chart = Charts.objects.get(client=client, user=user, name=chart_name)
                    json_acceptable_string = chart.content.replace("'", "\"")
                    content = json.loads(json_acceptable_string)
                    json_acceptable_string = content['content'].replace("'", "\"")
                    content['content'] = json.loads(json_acceptable_string)
                    content['content']['extendedData'] = {
                                                'uid': chart.id,
                                                'name': chart.name
                                            }
                    return Response({
                                        'status': 'ok',
                                        'content': content['content'],
                                    })

                except Exception as e:
                    return Response({'status': str(e),})

            if not chart_id:
                charts = Charts.objects.filter(client=client, user=user)
                results = []
                for chart in charts:
                    results.append({
                        'timestamp': int(chart.added_on.replace(tzinfo=datetime.timezone.utc).timestamp()),
                        'symbol': chart.symbol,
                        'resolution': chart.resolution,
                        'id': chart.id,
                        'name': chart.name
                    })
            else:
                chart = Charts.objects.filter(client=client, user=user, id=int(chart_id))
                chart = chart if not chart else chart[0]
                results =  {} if not chart else {
                                            'content': chart.content,
                                            'id': chart.id,
                                            'name': chart.name,
                                            'symbol': chart.symbol,
                                            'resolution': chart.resolution,
                                            'timestamp': int(chart.added_on.replace(tzinfo=datetime.timezone.utc).timestamp())
                                          }
            return Response({'status': 'ok', 'data': results})
        except Exception as e:
            return Response({'status': 'error ' + str(e)})


    def post(self, request):
        """
        Store layout of a chart
        """
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        client = request.GET.get('client', None)
        user = request.GET.get('user', None)
        chart_id = request.GET.get('chart', None)
        data = request.data
        if not user or not client:
            return HttpResponse('Invalid data. You must provide ids of client and user.', status=400)
        try:
            pass
        except Exception as e:
            pass
        if True:
            name = data['name']
            content = data['content']
            resolution = data['resolution']
            if 'symbol' in data:
                symbol = data['symbol']
            else:
                json_acceptable_string = content.replace("'", "\"")
                c = json.loads(json_acceptable_string)
                if 'symbol' in c:
                    symbol = c['symbol']

            if not chart_id:
                chart = Charts(name=name, client=client, user=user, symbol=symbol, content=content, resolution=resolution)
                chart.save()
            else:
                chart = Charts.objects.get(client=client, user=user, id=int(chart_id))
                chart.name = name
                chart.symbol = symbol
                chart.content = content
                chart.resolution = resolution
                chart.save()
            return Response({'status': 'ok', 'id': chart.id})
        else:
            #except Exception as e:
            return Response({'status': 'error' + str(e)})


    def delete(self, request):
        """
        Delete the layout of a chart
        """
        if request.auth is None:
            return HttpResponse('Unauthorized access', status=401)
        client = request.GET.get('client', None)
        user = request.GET.get('user', None)
        chart_id = request.GET.get('chart', None)

        if not chart_id or not user or not client:
            return HttpResponse('Invalid data. You must provide ids of chart, client and user.', status=400)

        try:
            Charts.objects.filter(client=client,id=chart_id, user=user).delete()
            return Response({'status': 'ok'})
        except Exception as e:
            return Response({'status': 'error'})
