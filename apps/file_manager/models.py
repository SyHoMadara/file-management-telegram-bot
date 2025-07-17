from django.contrib.auth import get_user_model
from django.db import models
import logging

logger = logging.getLogger(__name__)
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

    def delete(self, *args, **kwargs):
        # Store file path before deletion
        file_path = self.file.name if self.file else None
        # Call parent delete to remove the model instance
        super().delete(*args, **kwargs)
        # Delete file from MinIO if it exists
        if file_path:
            try:
                self.file.storage.delete(file_path)
                logger.info(f"Deleted file {file_path} from MinIO bucket 'media'")
            except Exception as e:
                logger.error(f"Error deleting file {file_path} from MinIO: {e}")

    class Meta:
        verbose_name = "File Manager"
        verbose_name_plural = "File Managers"
        ordering = ["-created_at"]
