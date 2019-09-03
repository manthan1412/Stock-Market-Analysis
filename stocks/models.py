from django.db import models
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User


class Tickers(models.Model):
    ticker = models.CharField(unique=True, max_length=255)
    full_name = models.CharField(max_length=255)
    added_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    next_earning_date = models.DateField(default=timezone.now)
    price = models.FloatField(default=0)
    percent_change = models.FloatField(default=0)
    last30days_avg_volume = models.BigIntegerField(default=0)
    last_day_volume = models.BigIntegerField(default=0)


class Notification(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    primary = models.CharField(max_length=32, null=True)
    secondary = models.CharField(max_length=32, null=True)
    sma_cross = models.SmallIntegerField(null=True)
    bungee_values_yellow = models.SmallIntegerField(null=True)
    bungee_values_green = models.SmallIntegerField(null=True)
    bungee_values_blue = models.SmallIntegerField(null=True)
    bungee_values_red = models.SmallIntegerField(null=True)
    time = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = (('ticker', 'user', 'primary', 'secondary', 'sma_cross', 'bungee_values_yellow', 'bungee_values_green', 'bungee_values_blue', 'bungee_values_red'),)


class NotificationGroup(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_global = models.BooleanField(null=False)
    time = models.DateTimeField(default=timezone.now)
    bungee = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        self.time = timezone.now()
        return super(NotificationGroup, self).save(*args, **kwargs)


class IsNotificationSent(models.Model):
    notification_group = models.ForeignKey(NotificationGroup, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    time = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        self.time = timezone.now()
        return super(IsNotificationSent, self).save(*args, **kwargs)


class BungeeNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32, null=False)


class BungeeNotificationSettings(models.Model):
    bungee_notification = models.ForeignKey(BungeeNotification, on_delete=models.CASCADE)
    operator = models.CharField(max_length=2, null=False)
    bungee_color = models.CharField(max_length=1, null=False)
    bungee_value = models.SmallIntegerField(null=False)

    class Meta:
        db_constraints = {
            "bungee_clr": "check (bungee_color IN ('y', 'g', 'b', 'r'))",
            "comparison_operator": "check (operator IN ('<', '<=', '>', '>=', '='))",
        }


class NotificationNew(models.Model):
    notification_group = models.ForeignKey(NotificationGroup, on_delete=models.CASCADE)
    primary_tf = models.CharField(max_length=3, null=True)
    primary_type = models.SmallIntegerField(null=True)
    secondary = models.SmallIntegerField(null=True)
    sma_cross = models.NullBooleanField()
    rsi_threshold = models.SmallIntegerField(null=True)
    bungee_notification = models.ForeignKey(BungeeNotification, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = (('notification_group', 'primary_tf', 'primary_type', 'secondary', 'sma_cross', 'rsi_threshold', 'bungee_notification'),)


class GlobalNotification(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    primary = models.CharField(max_length=32, null=True)
    secondary = models.CharField(max_length=32, null=True)
    bungee = models.CharField(max_length=32, null=True)
    time = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = (('user', 'primary', 'secondary', 'bungee'),)


class StockUpdate(models.Model):
    time = models.DateTimeField(default=timezone.now)
    ongoing = models.BooleanField(default=False)

    class Meta:
        ordering = ['-time']


class IQFeedStatus(models.Model):
    last_on = models.DateTimeField(default=timezone.now)
    version = models.CharField(max_length=16)

    class Meta:
        ordering = ['-last_on']


class StockHistData(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    time = models.DateTimeField(auto_now=True)
    price = models.FloatField(blank=False, null=False)

    class Meta:
        ordering = ['-time']
        unique_together = (('ticker', 'time'),)


class SignalData(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    interval = models.CharField(max_length=8, blank=False, null=False)
    price = models.FloatField(null=False)
    time = models.DateTimeField(null=False)
    type = models.SmallIntegerField(null=False)
    age = models.SmallIntegerField(null=False)
    second = models.SmallIntegerField(null=False)
    sma_cross = models.BooleanField(null=False)
    sma_cross_candles = models.SmallIntegerField(null=False)
    rsi_threshold = models.SmallIntegerField(null=False)
    rsi_threshold_candles = models.SmallIntegerField(null=False)
    bungee_values_yellow = models.SmallIntegerField(null=False)
    bungee_values_green = models.SmallIntegerField(null=False)
    bungee_values_blue = models.SmallIntegerField(null=False)
    bungee_values_red = models.SmallIntegerField(null=False)
    candlestick_shapes = models.SmallIntegerField(null=False)
    candlestick_shapes_age = models.SmallIntegerField(null=False)
    royal_sig = models.SmallIntegerField(null=False)
    royal_sig_age = models.SmallIntegerField(null=False)

    class Meta:
        unique_together = (('ticker', 'interval'),)


class Stock5Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    time = models.TimeField(null=True)
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.IntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)

    def save(self, *args, **kwargs):
        self.time = self.end_time.time()
        return super(Stock5Min, self).save(*args, **kwargs)


class Stock15Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    time = models.TimeField(null=True)
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.IntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)

    def save(self, *args, **kwargs):
        self.time = self.end_time.time()
        return super(Stock15Min, self).save(*args, **kwargs)


class Stock60Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    time = models.TimeField(null=True)
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.IntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)

    def save(self, *args, **kwargs):
        self.time = self.end_time.time()
        return super(Stock60Min, self).save(*args, **kwargs)


class Stock4Hour(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    time = models.TimeField(null=True)
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.IntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)

    def save(self, *args, **kwargs):
        self.time = self.end_time.time()
        return super(Stock4Hour, self).save(*args, **kwargs)


class Stock1Day(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.IntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Stock1Week(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    volume = models.BigIntegerField(blank=False, null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class TempSignalData(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    interval = models.CharField(max_length=8, blank=False, null=False)
    price = models.FloatField(null=False)
    time = models.DateTimeField(null=False)
    type = models.SmallIntegerField(null=False)
    age = models.SmallIntegerField(null=False)
    second = models.SmallIntegerField(null=False)
    expiry = models.DateTimeField(null=False)
    signal_time = models.DateTimeField(null=False)

    class Meta:
        unique_together = (('ticker', 'interval', 'expiry'),)


class Temp5Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Temp15Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Temp60Min(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Temp4Hour(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateTimeField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Temp1Day(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)


class Temp1Week(models.Model):
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    end_time = models.DateField()
    open = models.FloatField(blank=False, null=False)
    close = models.FloatField(blank=False, null=False)
    low = models.FloatField(blank=False, null=False)
    high = models.FloatField(blank=False, null=False)
    # expiry = models.DateTimeField(null=False)

    class Meta:
        ordering = ['-end_time']
        unique_together = (('ticker', 'end_time'),)
