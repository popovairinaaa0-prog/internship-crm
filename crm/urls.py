"""URL-конфигурация проекта."""

from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Internship CRM"
admin.site.site_title = "Internship CRM"
admin.site.index_title = "Главная"

urlpatterns = [
    path("admin/notifications/", include("notifications.urls")),
    path("admin/", admin.site.urls),
    path("api/students/", include("students.api.urls")),
    path("api/managers/", include("accounts.api.urls")),
    path("api/manual-contacts/", include("notifications.api.urls")),
]
