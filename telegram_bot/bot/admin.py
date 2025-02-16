from django.contrib import admin
from .models import Chat

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("message_content", "chat_id", "username", "message_type", "timestamp")
    search_fields = ("chat_id", "username", "message_content")
