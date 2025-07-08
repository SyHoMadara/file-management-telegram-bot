from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    email = models.EmailField(
        max_length=254,
        unique=True,
        verbose_name=_("email address"),
        help_text=_(
            "Required. 254 characters or fewer. Must be a valid email address."
        ),
        error_messages={
            "invalid": _("Enter a valid email address."),
            "unique": _("A user with that email address already exists."),
        },
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("is verified"),
        help_text=_("Designates whether this user has verified their email address."),
    )
    first_name = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_("first name"),
    )
    last_name = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_("last name"),
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name=_("phone number"),
        help_text=_("Optional. Must be a valid phone number."),
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
