from django.db import models

class Chat(models.Model):
    chat_id = models.BigIntegerField()
    username = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    message_type = models.CharField(max_length=50)  # text, voice, sticker, etc.
    message_content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat {self.chat_id} - {self.message_type}"
