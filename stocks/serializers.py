from rest_framework import serializers, exceptions
from .models import Tickers
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

class TickersSerializer(serializers.Serializer):
    """
    Retrieve the user's access token if the proper
    credentials are provided.
    """
    ticker = serializers.CharField()
    full_name = serializers.CharField()
    is_active = serializers.BooleanField()

    def __unicode__(self):
        return self.ticker
