from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class FileManager(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="files/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="file_managers",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "File Manager"
        verbose_name_plural = "File Managers"
        ordering = ["-created_at"]
