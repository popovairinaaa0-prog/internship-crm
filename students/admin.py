from django.contrib import admin

from .models import Direction, Student, TelegramInviteToken

admin.site.register(Direction)
admin.site.register(Student)
admin.site.register(TelegramInviteToken)
