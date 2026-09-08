from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'specialization', 'is_totp_enabled')
    list_filter = ('role', 'department', 'is_totp_enabled', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Clinical & Security Profile', {
            'fields': ('role', 'department', 'specialization', 'is_totp_enabled')
        }),
    )
