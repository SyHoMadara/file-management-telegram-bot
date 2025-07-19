from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        user = self.model(username=username, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_("username"),
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/._/+/- characters"
        ),
    )
    telegram_id = models.CharField(
        max_length=50,
        verbose_name=_("telegram ID"),
        help_text=_("identifier for the user in Telegram."),
        null=True,
        blank=True,
    )
    first_name = models.CharField(
        max_length=30,
        verbose_name=_("first name"),
        help_text=_("Optional. The user's first name."),
        null=True,
        blank=True,
    )
    last_name = models.CharField(
        max_length=30,
        verbose_name=_("last name"),
        help_text=_("Optional. The user's last name."),
        null=True,
        blank=True,
    )
    remaining_download_size = models.IntegerField(
        default=20,
        verbose_name=_("remaining download size"),
        help_text=_("Remaining download size in bytes for the user."),
    )
    maximum_download_size_per_day = models.IntegerField(
        default=20,
        verbose_name=_("maximum download size per day"),
        help_text=_("Maximum download size per day in bytes for the user."),
    )
    is_premium = models.BooleanField(
        default=False,
        verbose_name=_("is premium"),
        help_text=_("Designates whether this user has a premium account."),
    )
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
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("is active"),
        help_text=_(
            "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_("is staff"),
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_superuser = models.BooleanField(
        default=False,
        verbose_name=_("is superuser"),
        help_text=_(
            "Designates that this user has all permissions without explicitly assigning them."
        ),
    )
    objects = UserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_create"]

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_model_perms(self, app_label):
        return self.is_superuser

    def __str__(self):
        return self.username
