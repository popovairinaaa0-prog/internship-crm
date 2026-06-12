from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("broadcast/new/", views.broadcast_new, name="broadcast_new"),
]
