from django.contrib import admin
from .models import Profile, Order


# Register your models here.
class ProfileAdmin(admin.ModelAdmin):
    '''
        Admin View for 
    '''
    list_display = ('nickname', 'btc_balance', 'usd_balance')
    
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Order)
