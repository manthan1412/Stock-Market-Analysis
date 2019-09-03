from rest_framework import serializers, exceptions
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import UserTickers


class TokenSerializer(serializers.Serializer):
    """
    Retrieve the user's access token if the proper
    credentials are provided.
    """
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = get_object_or_404(User,username=username)
            user = authenticate(username=user.username, password=password)
            if user:
                if not user.is_active:
                    msg = 'User account is disabled.'
                    raise exceptions.ValidationError(msg)
            else:
                msg = 'Username or password are not correct.'
                raise exceptions.ValidationError(msg)
        else:
            msg = '"username" and "password" are required.'
            raise exceptions.ValidationError(msg)

        attrs['user'] = user
        return attrs


class UserTickersSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source='ticker.ticker')
    next_earning_date = serializers.CharField(source='ticker.next_earning_date')

    class Meta:
        model = UserTickers
        fields = ('ticker', 'position', 'rating', 'next_earning_date',)
