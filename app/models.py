import random
from djongo import models
from djongo.models.fields import ObjectIdField, Field
from django.contrib.auth.models import User

# Create your models here.


class Profile(models.Model):
    _id = ObjectIdField()
    nickname = models.CharField(max_length=255, unique=True)
    btc_balance = models.FloatField()
    usd_balance = models.FloatField()
    # randint al posto di uniform e Integer Field


class Order(models.Model):
    class OrderType(models.TextChoices):
        SELL = "SELL", "Sell"
        BUY = "BUY", "Buy"

    class OrderStatus(models.TextChoices):
        OPENED = "OPENED", "Opened"
        CLOSED = "CLOSED", "Closed"

    _id = ObjectIdField()
    # usando questo tipo di foreign key l'attributo della classse importa il campo desiderato in questo caso nickname
    profile = models.ForeignKey(Profile, to_field="nickname", on_delete=models.CASCADE)
    datetime = models.DateTimeField(auto_now_add=True)
    price = models.FloatField()
    quantity = models.FloatField()
    order_type = models.CharField(
        max_length=4, choices=OrderType.choices, default=OrderType.BUY
    )
    order_status = models.CharField(
        max_length=6, choices=OrderStatus.choices, default=OrderStatus.OPENED
    )
