from django.contrib.admin import register
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@register(User)
class UserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "date_create",
        "date_update",
        "is_verified",
    )
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")
    ordering = ("-date_create",)
    list_filter = ("is_staff", "is_active")
    readonly_fields = ("date_create", "date_update")
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                )
            },
        ),
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
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "is_verified",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    actions = ["verify_users", "deactivate_users", "activate_users"]

    def verify_users(self, request, queryset):
        """Mark selected users as verified."""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} user(s) marked as verified.")

    verify_users.short_description = _("Mark selected users as verified")  # type: ignore

    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated.")

    deactivate_users.short_description = _("Deactivate selected users")  # type: ignore

    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) activated.")

    activate_users.short_description = _("Activate selected users")  # type: ignore
