from django.urls import path

from .views import ConsumeManagerInviteView

app_name = "accounts_api"

urlpatterns = [
    path(
        "consume-invite/",
        ConsumeManagerInviteView.as_view(),
        name="consume_invite",
    ),
]
