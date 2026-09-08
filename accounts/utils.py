import ipaddress
from .models import AuditLog


def get_client_ip(request):
    """Resolves and validates client IP address considering proxy headers."""
    if not request:
        return '127.0.0.1'

    candidates = []
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        for part in x_forwarded_for.split(','):
            cand = part.strip()
            if cand:
                candidates.append(cand)

    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        candidates.append(x_real_ip.strip())

    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr:
        candidates.append(remote_addr.strip())

    for ip_str in candidates:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            return str(ip_obj)
        except ValueError:
            continue

    return '127.0.0.1'


def log_audit(request, action, user=None, details='', ip_address=None):
    """Appends an event record to the security audit trail."""
    actor = user or (request.user if request and request.user.is_authenticated else None)
    ip = ip_address or (get_client_ip(request) if request else '127.0.0.1')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255] if request else ''
    
    return AuditLog.objects.create(
        user=actor,
        action=action,
        ip_address=ip,
        user_agent=user_agent,
        details=str(details)
    )
