from django.db import models
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User

class Charts(models.Model):
    name = models.CharField(max_length=32)
    content = models.TextField(null=True)
    added_on = models.DateTimeField(auto_now=True)
    symbol = models.CharField(max_length=16, null=True)
    resolution = models.CharField(max_length=3, null=True)
    client = models.CharField(max_length=32)
    user = models.CharField(max_length=32)

    class Meta:
        unique_together = (('name', 'user'),)
