from django.db import models
from django.contrib.auth.models import User
from stocks.models import Tickers
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class UserTickers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)
    rating = models.IntegerField(default=0, validators=[MaxValueValidator(5), MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()
    target_value = models.FloatField(null=True)
    grade = models.CharField(max_length=4, null=True, default="")
    watch_list = models.NullBooleanField(default=None, null=True)
    note = models.TextField(default="", null=True)
    note_created = models.DateTimeField(null=True, blank=True)
    note_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['user', 'position']
        unique_together = (('user', 'ticker'),)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        current_time = timezone.now()
        if not self.id:
            self.created = current_time
        self.modified = current_time
        return super(UserTickers, self).save(*args, **kwargs)


class UserTickerIntervalFeatures(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE)
    interval = models.CharField(max_length=8, blank=False, null=False)
    wave_rating = models.CharField(max_length=8, null=False, default="")
    divergence_symbol = models.NullBooleanField(default=None, null=True)

    class Meta:
        unique_together = (('user', 'ticker', 'interval'),)


class ScriptUpdate(models.Model):
    updated = models.DateTimeField()

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        self.updated = timezone.now()
        return super(ScriptUpdate, self).save(*args, **kwargs)


class WatchListNotes(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note_data = models.TextField()
    created_time = models.DateTimeField(editable=False)
    updated_time = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        current_time = timezone.now()
        if not self.id:
            self.created_time = current_time
        self.updated_time = current_time
        return super(WatchListNotes, self).save(*args, **kwargs)


class UserNoteImages(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_name = models.TextField()
    image_data = models.BinaryField()
    note_id = models.ForeignKey(WatchListNotes, on_delete=models.CASCADE, null=True, blank=True)
    ticker = models.ForeignKey(Tickers, on_delete=models.CASCADE, null=True, blank=True)


class AppUser(models.Model):
    def __unicode__(self):
        return self.user.username

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    app_token = models.CharField(max_length=128, null=True)
    app_user = models.CharField(max_length=128, null=True)

    class Meta:
        unique_together = (('user', 'app_token'),)
