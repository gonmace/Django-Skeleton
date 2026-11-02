from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('healthz', views.healthz, name='healthz'),
]
