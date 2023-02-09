from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [path('signup/', views.signup, name='signup'),
               path('signin/', views.signin, name='signin'),
               path('placeorder/', views.place_order, name='placeorder'),
               path('logout/', LogoutView.as_view(), name='logout'),
               path('orderbook/', views.orderbook),
               path('overview/', views.overview, name='overview'),
               path('delete_order/<order_id>', views.delete_order, name='delete-order')
               ]
