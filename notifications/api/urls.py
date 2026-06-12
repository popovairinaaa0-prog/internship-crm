from django.urls import path

from .views import RegisterManualContactView

app_name = "notifications_api"

urlpatterns = [
    path("", RegisterManualContactView.as_view(), name="register_manual_contact"),
]
