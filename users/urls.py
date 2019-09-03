import os
from . import views
from django.urls import path
from django.conf.urls import url, include
from rest_framework_jwt.views import refresh_jwt_token

urlpatterns = [
    url(os.environ['URL_USERS_AUTH_TOKEN'], views.authToken, name='auth_token'),
    url(os.environ['URL_USERS_TOKEN'], views.TokenView.as_view()),
    url(os.environ['URL_USERS_AUTH'], include('rest_auth.urls')),
    url(os.environ['URL_USERS_REGISTRATION'], include('rest_auth.registration.urls')),
    url(os.environ['URL_USERS_REFRESH_TOKEN'], refresh_jwt_token),
    url(os.environ['URL_USERS_RATE_TICKERS'], views.UserRatingTickersView.as_view()),
    url(os.environ['URL_USERS_ADD_REMOVE_TICKERS'], views.AddRemoveTickersView.as_view()),
    url(os.environ['URL_USERS_GET_TICKERS'], views.GetUserTickersView.as_view()),
    url(os.environ['URL_USERS_UPDATE_POSITION'], views.UpdateTickerPositionView.as_view()),
    url(os.environ['URL_USERS_DELETE_TICKERS'], views.DeleteUserTickersView.as_view()),
    url(os.environ['URL_USERS_RELOAD_TICKERS'], views.ReloadUserTickersView.as_view()),
    url(os.environ['URL_USERS_PROFILE'], views.UserProfileView.as_view()),
    url(os.environ['URL_USERS_PROFILE_SORT'], views.UserProfileSortView.as_view()),
    url(os.environ['URL_USERS_TICKER_UPDATE'], views.UpdateUserTickerData.as_view()),
    url(os.environ['URL_USERS_TICKER_INTERVANL_FEATURES'], views.UpdateUserTickerIntervalFeatures.as_view()),
    url(os.environ['URL_USERS_SCIPT_UPDATED'], views.ScriptUpdateView.as_view()),
    url(os.environ['URL_USERS_NOTE_IMAGE'], views.UserNoteImageView.as_view()),
    url(os.environ['URL_USERS_WATCH_LIST_NOTE'], views.WatchListNotesView.as_view()),
    url(os.environ['URL_USERS_WATCH_LIST_NOTE_HISTORY'], views.WatchListNoteHistoryView.as_view()),
]
