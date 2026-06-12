from django.contrib import admin

from .models import (
    Attachment,
    BroadcastDelivery,
    BroadcastJob,
    Comment,
    ManualContact,
    MessageTemplate,
    PushRule,
    PushSent,
)

admin.site.register(Comment)
admin.site.register(Attachment)
admin.site.register(BroadcastJob)
admin.site.register(BroadcastDelivery)
admin.site.register(ManualContact)
admin.site.register(MessageTemplate)
admin.site.register(PushRule)
admin.site.register(PushSent)
