from django.contrib.admin import register
from django.contrib.auth.admin import UserAdmin as ModelAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@register(User)
class UserAdmin(ModelAdmin):
    list_display = (
        "username",
        "date_create",
        "date_update",
        "is_verified",
    )
    search_fields = ("username", "phone_number")
    ordering = ("-date_create",)
    list_filter = ("is_staff", "is_active")
    readonly_fields = ("date_create", "date_update")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("date_create", "date_update")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "is_verified",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
