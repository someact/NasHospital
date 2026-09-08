import io
import base64
import qrcode
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import Http404, HttpResponseForbidden
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import User, UserRole, AuditLog, AuditAction
from .forms import ClinicianCreateForm, ClinicianEditForm
from .utils import log_audit


def admin_required(view_func):
    """Decorator ensuring only users with Admin role or superuser status can access."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin_role:
            return HttpResponseForbidden("Access Denied: IT Administrator authorization required.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def redirect_user_by_role(user):
    """Redirects authenticated users to their natural dashboard based on role."""
    if user.role == UserRole.DOCTOR:
        return redirect('doctor_dashboard')
    elif user.role in [UserRole.COORDINATOR]:
        return redirect('coordinator_triage')
    elif user.role == UserRole.ADMIN:
        return redirect('admin_portal_dashboard')
    elif user.role == UserRole.STAFF_VIEWER:
        return redirect('catalog_view')
    return redirect('doctor_dashboard')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_totp_enabled:
                request.session['pre_2fa_user_id'] = user.id
                return redirect('totp_login_challenge')
            else:
                auth_login(request, user)
                log_audit(request, AuditAction.LOGIN_SUCCESS, user=user, details='Standard password authentication')
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect_user_by_role(user)
        else:
            log_audit(request, AuditAction.LOGIN_FAILURE, user=None, details=f"Failed login attempt for username: {username}")
            messages.error(request, "Invalid username or password.")

    return render(request, 'accounts/login.html')


def totp_login_challenge(request):
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()

        if device and device.verify_token(token):
            auth_login(request, user)
            del request.session['pre_2fa_user_id']
            log_audit(request, AuditAction.LOGIN_2FA, user=user, details='TOTP 2FA verified successfully')
            messages.success(request, f"Two-Factor Authentication verified. Welcome, {user.get_full_name()}!")
            return redirect_user_by_role(user)
        else:
            messages.error(request, "Invalid 6-digit TOTP verification code. Please try again.")

    return render(request, 'accounts/totp_challenge.html', {'target_user': user})


def logout_view(request):
    if request.user.is_authenticated:
        log_audit(request, AuditAction.LOGOUT, user=request.user, details='User logged out')
    auth_logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


def switch_role(request, user_id):
    """Instant persona switcher for high-fidelity interactive demo."""
    if not getattr(settings, 'ENABLE_DEMO_MODE', False):
        raise Http404("Demo Mode is disabled.")
    target_user = get_object_or_404(User, id=user_id)
    auth_login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
    log_audit(request, AuditAction.LOGIN_SUCCESS, user=target_user, details=f"Switched persona via Demo Switcher to {target_user.username}")
    messages.success(
        request,
        f"Switched persona to: {target_user.get_full_name() or target_user.username} "
        f"({target_user.get_role_display()} - {target_user.department or 'N/A'})"
    )
    return redirect_user_by_role(target_user)


@login_required
def totp_setup_view(request):
    """Interactive TOTP 2FA Setup view generating QR code for Google/Microsoft Authenticator."""
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'disable':
            password = request.POST.get('password', '')
            if not user.check_password(password):
                messages.error(request, "Authentication failed: Current password is required to disable Two-Factor Authentication.")
                return redirect('totp_setup')

            # Disable 2FA
            TOTPDevice.objects.filter(user=user).delete()
            user.is_totp_enabled = False
            user.save(update_fields=['is_totp_enabled'])
            log_audit(request, AuditAction.RESET_2FA, user=user, details='User disabled own 2FA after password confirmation')
            messages.warning(request, "Two-Factor Authentication has been disabled for your account.")
            return redirect('totp_setup')

        elif action == 'verify':
            token = request.POST.get('token', '').strip()
            temp_device = TOTPDevice.objects.filter(user=user, confirmed=False).first()

            if temp_device and temp_device.verify_token(token):
                # Clean up any existing confirmed devices
                TOTPDevice.objects.filter(user=user, confirmed=True).delete()
                temp_device.confirmed = True
                temp_device.save()
                user.is_totp_enabled = True
                user.save(update_fields=['is_totp_enabled'])
                log_audit(request, AuditAction.LOGIN_2FA, user=user, details='User activated 2FA security')
                messages.success(request, "Two-Factor Authentication successfully activated!")
                return redirect('totp_setup')
            else:
                messages.error(request, "Invalid verification code. Please check your authenticator app.")

    # Prepare QR Code if not enabled or in setup mode
    qr_data_uri = None
    secret_key = None

    if not user.is_totp_enabled:
        temp_device, _ = TOTPDevice.objects.get_or_create(
            user=user,
            confirmed=False,
            defaults={'name': f'{user.username}_totp'}
        )
        config_url = temp_device.config_url

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=2,
        )
        qr.add_data(config_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')
        secret_key = str(temp_device.key)

    return render(request, 'accounts/totp_setup.html', {
        'is_enabled': user.is_totp_enabled,
        'qr_data_uri': qr_data_uri,
        'secret_key': secret_key,
    })


# ==========================================
# MODULE 2: DEDICATED IT ADMIN PORTAL VIEWS
# ==========================================

@admin_required
def admin_portal_dashboard(request):
    """IT Administration Portal Dashboard."""
    total_users = User.objects.count()
    doctor_count = User.objects.filter(role=UserRole.DOCTOR).count()
    active_users = User.objects.filter(is_active=True).count()
    totp_enabled_count = User.objects.filter(is_totp_enabled=True).count()
    totp_ratio = round((totp_enabled_count / total_users * 100), 1) if total_users else 0
    recent_logs = AuditLog.objects.select_related('user').all()[:8]

    context = {
        'total_users': total_users,
        'doctor_count': doctor_count,
        'active_users': active_users,
        'totp_enabled_count': totp_enabled_count,
        'totp_ratio': totp_ratio,
        'recent_logs': recent_logs,
    }
    return render(request, 'accounts/admin_portal.html', context)


@admin_required
def admin_user_list(request):
    """Directory of all users with search, role filters, and quick security actions."""
    role_filter = request.GET.get('role', '')
    department_filter = request.GET.get('department', '')
    q = request.GET.get('q', '').strip()

    users = User.objects.all().order_by('role', 'first_name')

    if role_filter:
        users = users.filter(role=role_filter)
    if department_filter:
        users = users.filter(department__icontains=department_filter)
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(department__icontains=q) |
            Q(specialization__icontains=q)
        )

    departments = User.objects.exclude(department='').values_list('department', flat=True).distinct()

    context = {
        'users': users,
        'role_filter': role_filter,
        'department_filter': department_filter,
        'departments': departments,
        'query': q,
        'role_choices': UserRole.choices,
    }
    return render(request, 'accounts/user_list.html', context)


@admin_required
def admin_user_create(request):
    """Create a new clinical or administrative user."""
    if request.method == 'POST':
        form = ClinicianCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            log_audit(
                request,
                AuditAction.USER_CREATE,
                user=request.user,
                details=f"Created user {new_user.username} ({new_user.get_role_display()} - {new_user.department})"
            )
            messages.success(request, f"User '{new_user.get_full_name() or new_user.username}' successfully created.")
            return redirect('admin_user_list')
    else:
        form = ClinicianCreateForm()

    return render(request, 'accounts/user_form.html', {'form': form, 'is_create': True})


@admin_required
def admin_user_edit(request, user_id):
    """Edit clinician details, department, or role."""
    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = ClinicianEditForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            log_audit(
                request,
                AuditAction.USER_UPDATE,
                user=request.user,
                details=f"Updated profile for user {target_user.username}"
            )
            messages.success(request, f"Updated profile for {target_user.get_full_name() or target_user.username}.")
            return redirect('admin_user_list')
    else:
        form = ClinicianEditForm(instance=target_user)

    return render(request, 'accounts/user_form.html', {'form': form, 'is_create': False, 'target_user': target_user})


@admin_required
def admin_user_reset_2fa(request, user_id):
    """1-Click Security Action: Reset & unbind lost TOTP 2FA devices for clinicians."""
    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        # Unbind devices
        TOTPDevice.objects.filter(user=target_user).delete()
        target_user.is_totp_enabled = False
        target_user.save(update_fields=['is_totp_enabled'])

        log_audit(
            request,
            AuditAction.RESET_2FA,
            user=request.user,
            details=f"Admin reset and unbound 2FA device for clinician {target_user.username}"
        )
        messages.success(request, f"2FA has been successfully reset and unbound for {target_user.get_full_name() or target_user.username}.")

    return redirect('admin_user_list')


@admin_required
def admin_user_toggle_active(request, user_id):
    """Toggle active state of a user account."""
    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        messages.error(request, "You cannot deactivate your own administrative account.")
        return redirect('admin_user_list')

    if request.method == 'POST':
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])

        state_str = "activated" if target_user.is_active else "deactivated"
        log_audit(
            request,
            AuditAction.USER_TOGGLE_ACTIVE,
            user=request.user,
            details=f"Admin {state_str} account for {target_user.username}"
        )
        messages.info(request, f"Account for {target_user.username} is now {state_str}.")

    return redirect('admin_user_list')


# ==========================================
# MODULE 5: SECURITY AUDIT TRAIL VIEW
# ==========================================

@admin_required
def admin_audit_logs(request):
    """Filterable, chronological security audit trail viewer."""
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    q = request.GET.get('q', '').strip()

    logs = AuditLog.objects.select_related('user').all()

    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    if q:
        logs = logs.filter(
            Q(details__icontains=q) |
            Q(ip_address__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )

    users_with_logs = User.objects.filter(audit_logs__isnull=False).distinct()

    context = {
        'logs': logs[:150],  # Latest 150 events
        'action_filter': action_filter,
        'user_filter': user_filter,
        'query': q,
        'action_choices': AuditAction.choices,
        'users_with_logs': users_with_logs,
    }
    return render(request, 'accounts/audit_logs.html', context)
