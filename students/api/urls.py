from django.urls import path

from .views import ConsumeInviteView, student_autocomplete

app_name = "students_api"

urlpatterns = [
    path("consume-invite/", ConsumeInviteView.as_view(), name="consume_invite"),
    path("autocomplete/", student_autocomplete, name="autocomplete"),
]
