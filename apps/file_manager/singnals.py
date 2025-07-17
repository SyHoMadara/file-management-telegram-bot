import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import FileManager

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FileManager)
def delete_file_from_minio(sender, instance, **kwargs):
    """
    Delete the associated file from MinIO when a FileManager instance is deleted.
    """
    if instance.file:
        try:
            # Delete the file from MinIO
            instance.file.storage.delete(instance.file.name)
            logger.info(f"Deleted file {instance.file.name} from MinIO bucket 'media'")
        except Exception as e:
            logger.error(f"Error deleting file {instance.file.name} from MinIO: {e}")
