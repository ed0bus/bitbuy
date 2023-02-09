from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal


class OrderForm(forms.Form):
    bors = [("SELL", "Sell"), ("BUY", "Buy")]
    btc_balance = forms.FloatField(label="btc balance", disabled=True, required=False)
    usd_balance = forms.IntegerField(label="usd balance", disabled=True, required=False)
    quantity = forms.FloatField(label="Amount", help_text="Insert desired amount..")
    price = forms.FloatField(label="Price", help_text="Insert price..")
    action = forms.ChoiceField(label="Action", choices=bors)
