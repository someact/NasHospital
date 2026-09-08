from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    DOCTOR = 'DOCTOR', 'Doctor (Author & Reviewer)'
    COORDINATOR = 'COORDINATOR', 'Research Coordinator'
    STAFF_VIEWER = 'STAFF_VIEWER', 'Staff Clinician / Viewer'
    ADMIN = 'ADMIN', 'System Administrator'


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.DOCTOR,
        db_index=True,
        help_text="Unified Doctor role allows both authoring and reviewing peer papers."
    )
    department = models.CharField(max_length=100, blank=True, help_text="Clinical department, e.g., Cardiology, Surgery")
    specialization = models.CharField(max_length=150, blank=True, help_text="Medical sub-specialty")
    is_totp_enabled = models.BooleanField(default=False, help_text="Designates whether TOTP 2FA is active.")

    class Meta:
        db_table = 'accounts_user'
        ordering = ['first_name', 'last_name', 'username']

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            role_label = self.get_role_display()
            return f"{full_name} ({role_label} - {self.department or 'General'})"
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_doctor(self):
        return self.role == UserRole.DOCTOR

    @property
    def is_coordinator(self):
        return self.role in [UserRole.COORDINATOR, UserRole.ADMIN]

    @property
    def is_staff_viewer(self):
        return self.role == UserRole.STAFF_VIEWER

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN or self.is_superuser


class AuditAction(models.TextChoices):
    LOGIN_SUCCESS = 'LOGIN_SUCCESS', 'User Login'
    LOGIN_FAILURE = 'LOGIN_FAILURE', 'Failed Login Attempt'
    LOGIN_2FA = 'LOGIN_2FA', '2FA Verification Success'
    LOGOUT = 'LOGOUT', 'User Logout'
    STREAM_PDF = 'STREAM_PDF', 'Protected PDF Streamed'
    SUBMIT_PAPER = 'SUBMIT_PAPER', 'Manuscript Submitted'
    ASSIGN_REVIEWER = 'ASSIGN_REVIEWER', 'Reviewer Assigned'
    SUBMIT_REVIEW = 'SUBMIT_REVIEW', 'Critique Submitted'
    DISPATCH_LETTER = 'DISPATCH_LETTER', 'Coordinator Letter Dispatched'
    PUBLISH_PAPER = 'PUBLISH_PAPER', 'Paper Published & Locked'
    RETRACT_PAPER = 'RETRACT_PAPER', 'Paper Recalled for Revision'
    REQUEST_ACCESS = 'REQUEST_ACCESS', 'Access Pass Requested'
    GRANT_ACCESS = 'GRANT_ACCESS', 'Access Pass Granted'
    DENY_ACCESS = 'DENY_ACCESS', 'Access Pass Denied'
    RESET_2FA = 'RESET_2FA', '2FA Reset by Administrator'
    USER_CREATE = 'USER_CREATE', 'User Created'
    USER_UPDATE = 'USER_UPDATE', 'User Updated'
    USER_TOGGLE_ACTIVE = 'USER_TOGGLE_ACTIVE', 'User Active Status Toggled'


class AuditLog(models.Model):
    """Append-only security and operational audit trail."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=40, choices=AuditAction.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_auditlog'
        ordering = ['-timestamp']

    def __str__(self):
        actor_name = self.user.get_full_name() if self.user else "System/Anonymous"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.get_action_display()} by {actor_name}"
