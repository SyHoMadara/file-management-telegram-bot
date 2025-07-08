from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    is_verified = models.BooleanField(
        default=True,
        verbose_name=_("is verified"),
        help_text=_("Designates whether this user has verified their email address."),
    )
    date_update = models.DateTimeField(
        auto_now=True,
        verbose_name=_("date update"),
    )
    date_create = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("date create"),
    )

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_create"]

    def __str__(self):
        return self.username
