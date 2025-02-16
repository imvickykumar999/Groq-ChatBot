from django.contrib import admin
from .models import Chat
from django.utils.html import format_html

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("message_content", "chat_id", "first_name", "message_type", "timestamp")
    search_fields = ("chat_id", "first_name", "message_content", "message_type")
    readonly_fields = ("download_file_link",)  # Use download_file_link instead of download_file
    list_filter = ("message_type", "timestamp", "chat_id", "first_name")

    def download_file_link(self, obj):
        if obj.download_file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.download_file, obj.download_file)
        return "No file"
    
    download_file_link.short_description = "Download file"  # Admin label
