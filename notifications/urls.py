from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("broadcast/new/", views.broadcast_new, name="broadcast_new"),
    path("broadcast/<int:pk>/", views.broadcast_detail, name="broadcast_detail"),
    path("broadcast/<int:pk>/status/", views.broadcast_status, name="broadcast_status"),
]
