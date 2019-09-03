import os
from django.urls import path
from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(os.environ['URL_DELETE_TICKER'], views.DeleteTicker.as_view()),
    # url(r'^get/<str:tickerId>/$', views.TickerData.as_view()),
    url(os.environ['URL_GET_ALL_TICKERS'], views.GetTicker.as_view()),
    url(os.environ['URL_GET_ALL_ACTIVE_TICKERS'], views.GetActiveTicker.as_view()),
    url(os.environ['URL_UPDATE_TICKER'], views.UpdateTicker.as_view()),
    url(os.environ['URL_NEXT_EARNING_DATE'], views.NextEarningDate.as_view()),
    url(os.environ['URL_BUNGEE_NOTIFICATION_SETTINGS'], views.BungeeNotificationView.as_view()),
    url(os.environ['URL_NEW_NOTIFICATIONS'], views.NewNotificationView.as_view()),
    url(os.environ['URL_ALL_NOTIFICATIONS'], views.AllNotificationsView.as_view()),
    url(os.environ['URL_NOTIFICATION_ACTIONS'], views.ActivateDeactivateNotificationView.as_view()),
    url(os.environ['URL_REQUEST_FILE'], views.CSVView.as_view()),
]
