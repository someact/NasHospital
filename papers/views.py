import os
import io
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, FileResponse, Http404, JsonResponse
from django.conf import settings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .encryption import decrypt_bytes

from django.db.models import Q, Count, Avg, F
from accounts.models import User, UserRole, AuditAction
from accounts.utils import log_audit, get_client_ip
from .models import (
    Paper, PaperRound, ReviewAssignment, ReviewFeedback, CoordinatorLetter,
    AccessRequest, Notification, PaperStatus, ReviewDecision, CoordinatorDecision,
    AccessRequestStatus, NotificationType, get_assignable_reviewers, notify_user
)
from .forms import (
    PaperSubmissionForm, RevisionSubmissionForm, ReviewCritiqueForm,
    CoordinatorLetterForm, AccessRequestForm
)


@login_required
def doctor_dashboard(request):
    """
    Unified Doctor Workspace:
    Separates authored research manuscripts from assigned peer-review invitations.
    """
    user = request.user
    active_tab = request.GET.get('tab', 'my_researches')

    # Authored Manuscripts
    my_papers = Paper.objects.filter(author=user).prefetch_related('rounds').order_by('-created_at')

    # Assigned Peer Reviews
    assigned_reviews = ReviewAssignment.objects.filter(reviewer=user).select_related(
        'round__paper', 'round'
    ).prefetch_related('feedback').order_by('-assigned_at')

    context = {
        'active_tab': active_tab,
        'my_papers': my_papers,
        'assigned_reviews': assigned_reviews,
        'pending_reviews_count': assigned_reviews.filter(is_completed=False).count(),
        'published_count': my_papers.filter(current_status=PaperStatus.PUBLISHED).count(),
        'retracted_count': my_papers.filter(current_status=PaperStatus.RETRACTED_FOR_REVISION).count(),
    }
    return render(request, 'papers/doctor_dashboard.html', context)


@login_required
def paper_submit(request):
    """Allows doctors to submit a new clinical research paper."""
    if request.method == 'POST':
        form = PaperSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            paper = form.save(commit=False)
            paper.author = request.user
            paper.current_status = PaperStatus.PENDING_COORD
            paper.save()

            # Create Round 1
            PaperRound.objects.create(
                paper=paper,
                round_number=1,
                pdf_file=form.cleaned_data['pdf_file'],
                summary_notes=form.cleaned_data.get('summary_notes', '')
            )

            log_audit(request, AuditAction.SUBMIT_PAPER, user=request.user, details=f"Submitted initial manuscript: {paper.title}")

            # Notify Coordinators
            for c in User.objects.filter(role=UserRole.COORDINATOR):
                notify_user(
                    recipient=c,
                    actor=request.user,
                    paper=paper,
                    notif_type=NotificationType.REVISION_SUBMITTED,
                    message=f"New manuscript '{paper.title}' submitted by Dr. {request.user.get_full_name()} for triage.",
                    target_url="/coordinator/triage/"
                )

            messages.success(request, f"Manuscript '{paper.title}' successfully submitted for Coordinator triage.")
            return redirect('doctor_dashboard')
    else:
        form = PaperSubmissionForm(initial={'department': request.user.department})

    return render(request, 'papers/paper_submit.html', {'form': form})


@login_required
def paper_detail(request, paper_id):
    """
    Author Paper Detail & History Tracker:
    AIR-GAPPED: Shows submission timeline, rounds, and synthesized Coordinator Letters only.
    Reviewer identities and raw review comments are strictly excluded.
    """
    paper = get_object_or_404(Paper, id=paper_id)

    # Permission: Author, Coordinator, Admin
    if not (request.user == paper.author or request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("You do not have permission to inspect this manuscript tracking dossier.")

    rounds = paper.rounds.prefetch_related('coordinator_letter').order_by('round_number')

    context = {
        'paper': paper,
        'rounds': rounds,
        'is_author': request.user == paper.author,
    }
    return render(request, 'papers/paper_detail.html', context)


@login_required
def paper_revision(request, paper_id):
    """Allows author to submit a revised manuscript (Round N+1) in response to Coordinator directives or Retraction."""
    paper = get_object_or_404(Paper, id=paper_id)

    if request.user != paper.author and not request.user.is_admin_role:
        return HttpResponseForbidden("Only the primary author may upload a manuscript revision.")

    if paper.current_status not in [PaperStatus.REVISION_REQUIRED, PaperStatus.RETRACTED_FOR_REVISION]:
        messages.error(request, "This manuscript is not currently awaiting revision submission.")
        return redirect('paper_detail', paper_id=paper.id)

    latest_round = paper.latest_round
    next_round_number = (latest_round.round_number + 1) if latest_round else 1

    if request.method == 'POST':
        form = RevisionSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            PaperRound.objects.create(
                paper=paper,
                round_number=next_round_number,
                pdf_file=form.cleaned_data['pdf_file'],
                summary_notes=form.cleaned_data['summary_notes']
            )
            paper.submit_to_coordinator()

            log_audit(
                request,
                AuditAction.SUBMIT_PAPER,
                user=request.user,
                details=f"Submitted Revision Round {next_round_number} for '{paper.title}'"
            )

            # Notify Coordinators
            for c in User.objects.filter(role=UserRole.COORDINATOR):
                notify_user(
                    recipient=c,
                    actor=request.user,
                    paper=paper,
                    notif_type=NotificationType.REVISION_SUBMITTED,
                    message=f"Revision Round {next_round_number} uploaded by Dr. {request.user.get_full_name()} for '{paper.title}'.",
                    target_url="/coordinator/triage/"
                )

            messages.success(request, f"Revision Round {next_round_number} submitted to Coordinator C for re-evaluation.")
            return redirect('doctor_dashboard')
    else:
        form = RevisionSubmissionForm()

    context = {
        'paper': paper,
        'form': form,
        'next_round_number': next_round_number,
        'latest_letter': getattr(latest_round, 'coordinator_letter', None) if latest_round else None,
        'is_retracted': paper.current_status == PaperStatus.RETRACTED_FOR_REVISION,
    }
    return render(request, 'papers/paper_revision.html', context)


@login_required
def coordinator_triage(request):
    """
    Coordinator Triage & Desk:
    Gatekeeper reviews initial submissions, assigns eligible reviewers (enforcing COI Guard),
    and monitors progression.
    """
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    status_filter = request.GET.get('status', 'ALL')
    papers = Paper.objects.select_related('author').prefetch_related('rounds').order_by('-created_at')

    if status_filter != 'ALL':
        papers = papers.filter(current_status=status_filter)

    # Pre-fetch assignable reviewers for pending papers with COI exclusion
    assignable_reviewers_map = {}
    for p in papers:
        if p.current_status in [PaperStatus.PENDING_COORD, PaperStatus.PENDING_ADVISOR]:
            assignable_reviewers_map[str(p.id)] = get_assignable_reviewers(p)

    context = {
        'papers': papers,
        'status_filter': status_filter,
        'status_choices': PaperStatus.choices,
        'assignable_reviewers_map': assignable_reviewers_map,
    }
    return render(request, 'papers/coordinator_triage.html', context)


@login_required
def coordinator_assign_reviewers(request, paper_id):
    """
    Advisor Dispatcher Action:
    Enforces strict COI guard: author can never be assigned as reviewer.
    """
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    paper = get_object_or_404(Paper, id=paper_id)

    if request.method == 'POST':
        reviewer_ids = request.POST.getlist('reviewers')
        if not reviewer_ids:
            messages.error(request, "Please select at least one reviewer.")
            return redirect('coordinator_triage')

        # Strict COI Check
        if str(paper.author_id) in reviewer_ids:
            messages.error(request, "Conflict of Interest Violation: Paper author cannot be assigned to review their own work.")
            return redirect('coordinator_triage')

        reviewers = User.objects.filter(id__in=reviewer_ids, role=UserRole.DOCTOR)
        try:
            paper.assign_reviewers(reviewers, actor=request.user)
            names = ", ".join([r.get_full_name() or r.username for r in reviewers])

            log_audit(
                request,
                AuditAction.ASSIGN_REVIEWER,
                user=request.user,
                details=f"Assigned reviewers [{names}] to '{paper.title}'"
            )

            messages.success(request, f"Assigned peer-reviewers [{names}] to '{paper.title}'.")
        except Exception as e:
            messages.error(request, f"Assignment error: {str(e)}")

    return redirect('coordinator_triage')


@login_required
def coordinator_retract_paper(request, paper_id):
    """Module 3: Recall a published manuscript for revision with justification note."""
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    paper = get_object_or_404(Paper, id=paper_id)

    if request.method == 'POST':
        reason = (request.POST.get('reason') or request.POST.get('retraction_reason') or '').strip()
        if not reason:
            messages.error(request, "Please provide a clinical or editorial justification for recalling this publication.")
            return redirect('coordinator_triage')

        try:
            paper.retract_for_revision(coordinator=request.user, reason=reason)
            log_audit(
                request,
                AuditAction.RETRACT_PAPER,
                user=request.user,
                details=f"Recalled published paper '{paper.title}'. Justification: {reason}"
            )
            messages.warning(
                request,
                f"Manuscript '{paper.title}' has been recalled for revision. De-listed from Public Catalog."
            )
        except Exception as e:
            messages.error(request, f"Retraction error: {str(e)}")

    return redirect('coordinator_triage')


@login_required
def review_workspace(request, paper_id):
    """
    Split-Screen Review Desk:
    Left Pane: PDF.js embedded viewer with dynamic visual watermark.
    Right Pane: Structured critique (เค้าโครง, บทนำ, บทขยาย) and recommendation.
    """
    paper = get_object_or_404(Paper, id=paper_id)
    latest_round = paper.latest_round
    if not latest_round:
        raise Http404("No rounds available for this paper.")

    # Locate reviewer assignment
    assignment = ReviewAssignment.objects.filter(
        round=latest_round,
        reviewer=request.user
    ).first()

    if not assignment and not request.user.is_admin_role:
        return HttpResponseForbidden("You are not assigned as a reviewer for this manuscript.")

    existing_feedback = getattr(assignment, 'feedback', None) if assignment else None

    if request.method == 'POST':
        form = ReviewCritiqueForm(request.POST, request.FILES, instance=existing_feedback)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.assignment = assignment
            feedback.save()

            log_audit(
                request,
                AuditAction.SUBMIT_REVIEW,
                user=request.user,
                details=f"Submitted critique for '{paper.title}' (Round {latest_round.round_number}). Decision: {feedback.get_decision_display()}"
            )

            messages.success(request, f"Review critique for '{paper.title}' submitted successfully.")
            return redirect('doctor_dashboard')
    else:
        form = ReviewCritiqueForm(instance=existing_feedback)

    # Dynamic visual watermark parameters
    client_ip = get_client_ip(request)
    watermark_time = timezone.now().strftime('%Y-%m-%d %H:%M')
    viewer_name = request.user.get_full_name() or request.user.username

    context = {
        'paper': paper,
        'round': latest_round,
        'assignment': assignment,
        'form': form,
        'is_completed': assignment.is_completed if assignment else False,
        'client_ip': client_ip,
        'watermark_time': watermark_time,
        'viewer_name': viewer_name,
    }
    return render(request, 'papers/review_workspace.html', context)


@login_required
def coordinator_consolidation(request, paper_id):
    """
    Coordinator Consolidation Desk:
    Side-by-side view of reviewer critiques and synthesis editor for the air-gapped Coordinator Letter.
    """
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    paper = get_object_or_404(Paper, id=paper_id)
    latest_round = paper.latest_round
    if not latest_round:
        raise Http404("Paper has no rounds.")

    assignments = latest_round.assignments.select_related('reviewer').prefetch_related('feedback').all()
    existing_letter = getattr(latest_round, 'coordinator_letter', None)

    if request.method == 'POST':
        form = CoordinatorLetterForm(request.POST, instance=existing_letter)
        if form.is_valid():
            letter = form.save(commit=False)
            paper.dispatch_coordinator_letter(
                coordinator=request.user,
                comment=letter.consolidated_comment,
                decision=letter.decision,
                round_obj=latest_round
            )

            log_audit(
                request,
                AuditAction.DISPATCH_LETTER,
                user=request.user,
                details=f"Dispatched Coordinator Decision Letter for '{paper.title}' ({letter.get_decision_display()})"
            )

            messages.success(request, f"Coordinator Decision Letter dispatched to author ({letter.get_decision_display()}).")
            return redirect('coordinator_triage')
    else:
        form = CoordinatorLetterForm(instance=existing_letter)

    context = {
        'paper': paper,
        'round': latest_round,
        'assignments': assignments,
        'form': form,
    }
    return render(request, 'papers/coordinator_consolidation.html', context)


@login_required
def coordinator_publish_paper(request, paper_id):
    """Publication Lock action."""
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    paper = get_object_or_404(Paper, id=paper_id)
    try:
        paper.publish()
        log_audit(
            request,
            AuditAction.PUBLISH_PAPER,
            user=request.user,
            details=f"Officially published and locked manuscript: '{paper.title}'"
        )
        messages.success(request, f"Paper '{paper.title}' officially published and locked!")
    except Exception as e:
        messages.error(request, f"Unable to publish: {str(e)}")

    return redirect('coordinator_triage')


def catalog_view(request):
    """
    Research Catalog & Search:
    Lists published manuscripts. Displays time-bound Access Gate state for the current user.
    """
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    author_id = request.GET.get('author', '').strip()

    papers = Paper.objects.filter(current_status=PaperStatus.PUBLISHED).select_related('author').prefetch_related('rounds')

    if q:
        papers = papers.filter(
            Q(title__icontains=q) |
            Q(abstract__icontains=q) |
            Q(department__icontains=q) |
            Q(author__first_name__icontains=q) |
            Q(author__last_name__icontains=q) |
            Q(category__icontains=q)
        )

    if category:
        papers = papers.filter(category__icontains=category)

    if author_id:
        papers = papers.filter(author_id=author_id)

    # Categories for filter dropdown
    categories = Paper.objects.filter(current_status=PaperStatus.PUBLISHED).values_list('category', flat=True).distinct()

    # Authors with published papers for filter dropdown
    authors = User.objects.filter(
        authored_papers__current_status=PaperStatus.PUBLISHED
    ).distinct().order_by('first_name', 'last_name')

    # Pre-compute user access statuses
    access_map = {}
    if request.user.is_authenticated:
        now = timezone.now()
        user_requests = AccessRequest.objects.filter(requester=request.user)
        for req in user_requests:
            if req.status == AccessRequestStatus.APPROVED and req.expires_at and req.expires_at > now:
                access_map[req.paper_id] = {'status': 'ACTIVE', 'ticket': req}
            elif req.status == AccessRequestStatus.PENDING:
                access_map[req.paper_id] = {'status': 'PENDING', 'ticket': req}

    context = {
        'papers': papers,
        'query': q,
        'category': category,
        'categories': categories,
        'authors': authors,
        'selected_author': author_id,
        'access_map': access_map,
        'access_form': AccessRequestForm(),
    }
    return render(request, 'papers/catalog.html', context)


@login_required
def request_access(request, paper_id):
    """Submit time-bound access ticket for a published paper."""
    paper = get_object_or_404(Paper, id=paper_id, current_status=PaperStatus.PUBLISHED)

    if request.method == 'POST':
        form = AccessRequestForm(request.POST)
        if form.is_valid():
            req_obj, created = AccessRequest.objects.get_or_create(
                paper=paper,
                requester=request.user,
                defaults={
                    'reason': form.cleaned_data['reason'],
                    'duration_days': form.cleaned_data['duration_days'],
                    'status': AccessRequestStatus.PENDING
                }
            )
            if not created:
                req_obj.reason = form.cleaned_data['reason']
                req_obj.duration_days = form.cleaned_data['duration_days']
                req_obj.status = AccessRequestStatus.PENDING
                req_obj.expires_at = None
                req_obj.save()

            log_audit(
                request,
                AuditAction.REQUEST_ACCESS,
                user=request.user,
                details=f"Requested {form.cleaned_data['duration_days']}-day access pass for '{paper.title}'"
            )

            messages.success(request, f"Access pass ticket submitted for '{paper.title}'. Coordinator C will review your request.")
    return redirect('catalog_view')


@login_required
def coordinator_access_queue(request):
    """Coordinator Queue for reviewing time-bound full-text reading access tickets."""
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator authorization required.")

    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        action = request.POST.get('action')
        ticket = get_object_or_404(AccessRequest, id=ticket_id)

        if action == 'approve':
            ticket.approve(coordinator=request.user)
            log_audit(
                request,
                AuditAction.GRANT_ACCESS,
                user=request.user,
                details=f"Granted {ticket.duration_days}-day access pass to {ticket.requester.username} for '{ticket.paper.title}'"
            )
            messages.success(request, f"Approved access for {ticket.requester.get_full_name()} ({ticket.duration_days} days pass granted).")
        elif action == 'reject':
            notes = request.POST.get('notes', 'Access request declined by research coordinator.')
            ticket.reject(coordinator=request.user, notes=notes)
            log_audit(
                request,
                AuditAction.DENY_ACCESS,
                user=request.user,
                details=f"Denied access pass to {ticket.requester.username} for '{ticket.paper.title}'"
            )
            messages.warning(request, f"Rejected access pass for {ticket.requester.get_full_name()}.")
        return redirect('coordinator_access_queue')

    pending_tickets = AccessRequest.objects.filter(status=AccessRequestStatus.PENDING).select_related('paper', 'requester')
    active_tickets = AccessRequest.objects.filter(status=AccessRequestStatus.APPROVED).select_related('paper', 'requester', 'reviewed_by').order_by('-expires_at')

    context = {
        'pending_tickets': pending_tickets,
        'active_tickets': active_tickets,
    }
    return render(request, 'papers/coordinator_access_queue.html', context)


@login_required
@xframe_options_sameorigin
def serve_protected_paper(request, paper_id, round_number):
    """
    Protected Document Delivery & Access Gate:
    Strict authorization verification before streaming protected full-text PDFs.
    Decorated with @xframe_options_sameorigin to allow embedding in split-screen review desk.
    """
    paper = get_object_or_404(Paper, id=paper_id)
    round_obj = get_object_or_404(PaperRound, paper=paper, round_number=round_number)

    if not round_obj.pdf_file:
        raise Http404("PDF file not found for this round.")

    user = request.user
    authorized = False
    auth_reason = ""

    # 1. Coordinator or Admin
    if user.is_coordinator or user.is_admin_role:
        authorized = True
        auth_reason = "Coordinator Oversight"

    # 2. Paper Author
    elif user.id == paper.author_id:
        authorized = True
        auth_reason = "Author Access"

    # 3. Assigned Reviewer for this round
    elif ReviewAssignment.objects.filter(round=round_obj, reviewer=user).exists():
        authorized = True
        auth_reason = "Peer Reviewer Assignment"

    # 4. Published Paper with Active Access Pass
    elif paper.current_status == PaperStatus.PUBLISHED:
        now = timezone.now()
        active_pass = AccessRequest.objects.filter(
            paper=paper,
            requester=user,
            status=AccessRequestStatus.APPROVED,
            expires_at__gt=now
        ).exists()

        if active_pass:
            authorized = True
            auth_reason = "Approved Time-Bound Access Pass"
        else:
            return HttpResponseForbidden(
                "Access Denied: Full-text manuscript requires an approved Access Request ticket."
            )
    else:
        return HttpResponseForbidden(
            "Access Denied: You do not hold authorization to access this unpublished manuscript."
        )

    file_path = round_obj.pdf_file.path
    if not os.path.exists(file_path):
        raise Http404("File missing on server storage.")

    # Audit logging
    log_audit(
        request,
        AuditAction.STREAM_PDF,
        user=request.user,
        details=f"Streamed PDF for '{paper.title}' (Round {round_number}). Reason: {auth_reason}"
    )

    # In-Memory Decryption: zero unencrypted files on disk
    with open(file_path, 'rb') as f:
        ciphertext = f.read()
    decrypted_bytes = decrypt_bytes(ciphertext)
    clean_filename = os.path.basename(file_path).replace('.enc', '')
    if not clean_filename.lower().endswith('.pdf'):
        clean_filename += '.pdf'

    response = FileResponse(io.BytesIO(decrypted_bytes), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{clean_filename}"'
    response['X-Auth-Reason'] = auth_reason
    return response


@login_required
@xframe_options_sameorigin
def serve_annotated_pdf(request, feedback_id):
    """
    Protected Document Delivery for Reviewer Annotated PDFs.
    Allows same-origin frame embedding with in-memory decryption.
    """
    feedback = get_object_or_404(ReviewFeedback, id=feedback_id)
    if not (request.user.is_coordinator or request.user.is_admin_role or request.user.id == feedback.assignment.reviewer_id):
        return HttpResponseForbidden("Access Denied: You cannot inspect this reviewer annotation.")

    if not feedback.annotated_pdf:
        raise Http404("Annotated PDF not found.")

    file_path = feedback.annotated_pdf.path
    if not os.path.exists(file_path):
        raise Http404("File missing on server storage.")

    with open(file_path, 'rb') as f:
        ciphertext = f.read()
    decrypted_bytes = decrypt_bytes(ciphertext)
    clean_filename = os.path.basename(file_path).replace('.enc', '')
    if not clean_filename.lower().endswith('.pdf'):
        clean_filename += '.pdf'

    response = FileResponse(io.BytesIO(decrypted_bytes), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{clean_filename}"'
    return response


@login_required
def paper_pdf_viewer(request, paper_id):
    """
    Dedicated In-Browser Secure PDF Viewer (PDF.js Canvas Engine):
    Renders PDF pages into HTML5 canvas with multi-line diagonal watermarks.
    Restricts context menu and keyboard shortcuts (Ctrl+S, Ctrl+P).
    """
    paper = get_object_or_404(Paper, id=paper_id)
    round_param = request.GET.get('round')
    if round_param:
        try:
            target_round_num = int(round_param)
            round_obj = paper.rounds.filter(round_number=target_round_num).first()
            if not round_obj:
                round_obj = paper.latest_round
        except (ValueError, TypeError):
            round_obj = paper.latest_round
    else:
        round_obj = paper.latest_round

    if not round_obj or not round_obj.pdf_file:
        raise Http404("Manuscript PDF document not found for this round.")

    user = request.user
    authorized = False
    auth_reason = ""

    # Authorization Check
    if user.is_coordinator or user.is_admin_role:
        authorized = True
        auth_reason = "Coordinator Oversight"
    elif user.id == paper.author_id:
        authorized = True
        auth_reason = "Author Access"
    elif ReviewAssignment.objects.filter(round=round_obj, reviewer=user).exists():
        authorized = True
        auth_reason = "Peer Reviewer Assignment"
    elif paper.current_status == PaperStatus.PUBLISHED:
        now = timezone.now()
        active_pass = AccessRequest.objects.filter(
            paper=paper,
            requester=user,
            status=AccessRequestStatus.APPROVED,
            expires_at__gt=now
        ).exists()
        if active_pass:
            authorized = True
            auth_reason = "Approved Time-Bound Access Pass"

    if not authorized:
        return HttpResponseForbidden("Access Denied: You do not hold authorization to view this manuscript.")

    client_ip = get_client_ip(request)
    hospital_domain = getattr(settings, 'HOSPITAL_DOMAIN', 'medresearch.hospital.internal')
    timestamp_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    user_display = f"{user.get_full_name() or user.username} ({user.get_role_display()})"
    watermark_text = f"{user_display} • {hospital_domain} • {timestamp_str} • {client_ip}"

    # Log viewer access
    log_audit(
        request,
        AuditAction.STREAM_PDF,
        user=user,
        details=f"Opened Secure In-Browser PDF Viewer for '{paper.title}' (Round {round_obj.round_number}). Reason: {auth_reason}"
    )

    # Double-Blind Air Gap Hardening (SEC-03)
    is_blinded_reviewer = (
        not (user.is_coordinator or user.is_admin_role or user.id == paper.author_id)
    ) and ReviewAssignment.objects.filter(round=round_obj, reviewer=user).exists()

    context = {
        'paper': paper,
        'round_number': round_obj.round_number,
        'round_obj': round_obj,
        'pdf_stream_url': reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': round_obj.round_number}),
        'watermark_text': watermark_text,
        'user_display': user_display,
        'hospital_domain': hospital_domain,
        'timestamp_str': timestamp_str,
        'client_ip': client_ip,
        'all_rounds': paper.rounds.order_by('round_number'),
        'is_blinded_reviewer': is_blinded_reviewer,
    }
    return render(request, 'papers/pdf_viewer.html', context)



# ==========================================
# MODULE 1: IN-APP NOTIFICATION VIEWS
# ==========================================

@login_required
def notification_list(request):
    """List of all notifications for current user."""
    notifications = Notification.objects.filter(recipient=request.user)
    return render(request, 'papers/notification_list.html', {'notifications': notifications})


@login_required
def mark_notification_read(request, notification_id):
    """Marks a single notification as read and redirects to target URL."""
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    target = notif.target_url if notif.target_url and notif.target_url != '#' else 'doctor_dashboard'
    return redirect(target)


@login_required
def mark_all_notifications_read(request):
    """Bulk marks all unread notifications as read."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(referer)
    return redirect('doctor_dashboard')


# ==========================================
# MODULE 4: EXECUTIVE DASHBOARD VIEW
# ==========================================

@login_required
def executive_dashboard(request):
    """Executive Overview Dashboard with KPI metrics and Chart.js visualizations."""
    if not (request.user.is_coordinator or request.user.is_admin_role):
        return HttpResponseForbidden("Coordinator or Administrator authorization required.")

    total_papers = Paper.objects.count()
    published_papers = Paper.objects.filter(current_status=PaperStatus.PUBLISHED).count()
    retracted_papers = Paper.objects.filter(current_status=PaperStatus.RETRACTED_FOR_REVISION).count()
    active_reviews = ReviewAssignment.objects.filter(is_completed=False).count()
    publish_ratio = round((published_papers / total_papers * 100), 1) if total_papers else 0

    # Calculate average turnaround days for published papers
    pub_list = Paper.objects.filter(current_status=PaperStatus.PUBLISHED, published_at__isnull=False)
    turnaround_days = []
    for p in pub_list:
        diff = (p.published_at - p.created_at).days
        turnaround_days.append(max(diff, 1))
    avg_turnaround = round(sum(turnaround_days) / len(turnaround_days), 1) if turnaround_days else 0

    # 2FA Adoption Rate
    total_users = User.objects.count()
    totp_users = User.objects.filter(is_totp_enabled=True).count()
    totp_adoption = round((totp_users / total_users * 100), 1) if total_users else 0

    # 1. Department Distribution Data (Doughnut Chart)
    dept_qs = Paper.objects.values('department').annotate(count=Count('id')).order_by('-count')
    dept_labels = [item['department'] or 'General' for item in dept_qs]
    dept_counts = [item['count'] for item in dept_qs]

    # 2. Status Funnel Distribution (Bar Chart)
    status_counts_dict = {s[0]: 0 for s in PaperStatus.choices}
    for item in Paper.objects.values('current_status').annotate(count=Count('id')):
        status_counts_dict[item['current_status']] = item['count']

    funnel_labels = [
        'Pending Triage', 'In Peer Review', 'Reviews Complete',
        'Revision Required', 'Published', 'Retracted'
    ]
    funnel_data = [
        status_counts_dict.get(PaperStatus.PENDING_COORD, 0),
        status_counts_dict.get(PaperStatus.PENDING_ADVISOR, 0),
        status_counts_dict.get(PaperStatus.ADVISOR_COMMENTED, 0),
        status_counts_dict.get(PaperStatus.REVISION_REQUIRED, 0),
        status_counts_dict.get(PaperStatus.PUBLISHED, 0),
        status_counts_dict.get(PaperStatus.RETRACTED_FOR_REVISION, 0),
    ]

    # 3. Monthly Submission Volume (Last 6 months)
    now = timezone.now()
    month_labels = []
    month_data = []
    for i in range(5, -1, -1):
        m_date = now - timedelta(days=i * 30)
        m_label = m_date.strftime('%b %Y')
        month_labels.append(m_label)
        # Approximate month count
        m_count = Paper.objects.filter(created_at__year=m_date.year, created_at__month=m_date.month).count()
        month_data.append(m_count)

    context = {
        'total_papers': total_papers,
        'published_papers': published_papers,
        'retracted_papers': retracted_papers,
        'active_reviews': active_reviews,
        'publish_ratio': publish_ratio,
        'avg_turnaround': avg_turnaround,
        'totp_adoption': totp_adoption,
        'dept_labels': dept_labels,
        'dept_counts': dept_counts,
        'funnel_labels': funnel_labels,
        'funnel_data': funnel_data,
        'month_labels': month_labels,
        'month_data': month_data,
        'dept_labels_json': json.dumps(dept_labels),
        'dept_counts_json': json.dumps(dept_counts),
        'funnel_labels_json': json.dumps(funnel_labels),
        'funnel_data_json': json.dumps(funnel_data),
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_data),
    }
    return render(request, 'papers/executive_dashboard.html', context)
