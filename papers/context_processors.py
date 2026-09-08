from .models import (
    Notification, Paper, PaperStatus, AccessRequest,
    AccessRequestStatus, ReviewAssignment
)

def notifications_context(request):
    """Provides unread notification counts and real-time contextual badge metrics across navbar."""
    if not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'recent_notifications': [],
            'pending_triage_count': 0,
            'pending_access_tickets_count': 0,
            'doctor_revision_required_count': 0,
            'doctor_pending_reviews_count': 0,
            'doctor_action_badge_total': 0,
        }

    user = request.user
    user_notifications = Notification.objects.filter(recipient=user)
    unread_count = user_notifications.filter(is_read=False).count()
    recent = user_notifications[:6]

    pending_triage_count = 0
    pending_access_tickets_count = 0
    if user.is_coordinator or user.is_admin_role:
        pending_triage_count = Paper.objects.filter(
            current_status__in=[PaperStatus.PENDING_COORD, PaperStatus.ADVISOR_COMMENTED]
        ).count()
        pending_access_tickets_count = AccessRequest.objects.filter(
            status=AccessRequestStatus.PENDING
        ).count()

    doctor_revision_required_count = 0
    doctor_pending_reviews_count = 0
    if user.is_doctor:
        doctor_revision_required_count = Paper.objects.filter(
            author=user,
            current_status__in=[PaperStatus.REVISION_REQUIRED, PaperStatus.RETRACTED_FOR_REVISION]
        ).count()
        doctor_pending_reviews_count = ReviewAssignment.objects.filter(
            reviewer=user,
            is_completed=False
        ).count()

    doctor_action_badge_total = doctor_revision_required_count + doctor_pending_reviews_count

    return {
        'unread_notifications_count': unread_count,
        'recent_notifications': recent,
        'pending_triage_count': pending_triage_count,
        'pending_access_tickets_count': pending_access_tickets_count,
        'doctor_revision_required_count': doctor_revision_required_count,
        'doctor_pending_reviews_count': doctor_pending_reviews_count,
        'doctor_action_badge_total': doctor_action_badge_total,
    }

