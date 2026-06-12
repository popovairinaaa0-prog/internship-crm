"""URL-конфигурация проекта."""

from django.contrib import admin
from django.urls import include, path

from notifications.views import get_dashboard_data, healthz

admin.site.site_header = "Internship CRM"
admin.site.site_title = "Internship CRM"
admin.site.index_title = "Главная"


# Инжектим дашборд в стандартный admin index — patch без подменены AdminSite.
_original_admin_index = admin.site.index


def _index_with_dashboard(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context["dashboard"] = get_dashboard_data()
    return _original_admin_index(request, extra_context)


admin.site.index = _index_with_dashboard

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/notifications/", include("notifications.urls")),
    path("admin/", admin.site.urls),
    path("api/students/", include("students.api.urls")),
    path("api/managers/", include("accounts.api.urls")),
    path("api/manual-contacts/", include("notifications.api.urls")),
]
