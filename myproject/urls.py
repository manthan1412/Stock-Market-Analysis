"""myproject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls import url
from . import views, settings
from django.conf.urls.static import static
import os

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(os.environ['ADMIN_API'], admin.site.urls),
    url(r'^api/v1/', include([
        url(r'^users/', include('users.urls')),
        url(r'^tickers/', include('stocks.urls')),
        url(r'^tradingView/', include('trading_view.urls')),
    ]))
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# if settings.DEBUG:
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
