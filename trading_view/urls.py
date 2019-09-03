import os
from . import views
from django.urls import path
from django.conf.urls import url, include

urlpatterns = [
    url(os.environ['URL_TRADING_VIEW_CONFIG'], views.ConfigView.as_view()),
    url(os.environ['URL_TRADING_VIEW_SYMBOL_INFO'], views.SymbolInfoView.as_view()),
    url(os.environ['URL_TRADING_VIEW_SYMBOLS'], views.SymbolView.as_view()),
    url(os.environ['URL_TRADING_VIEW_SEARCH'], views.SymbolSearchView.as_view()),
    url(os.environ['URL_TRADING_VIEW_HISTORY'], views.BarsView.as_view()),
    url(os.environ['URL_TRADING_VIEW_MARKS'], views.MarksView.as_view()),
    url(os.environ['URL_TRADING_VIEW_TIMELINE_MARKS'], views.TimescaleMarksView.as_view()),
    url(os.environ['URL_TRADING_VIEW_TIME'], views.ServerTimeView.as_view()),
    url(os.environ['URL_TRADING_VIEW_QUOTES'], views.QuotesView.as_view()),
    url(os.environ['URL_TRADING_VIEW_CHARTS'], views.ChartsView.as_view()),
]
