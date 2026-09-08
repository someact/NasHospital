import os
import io
import uuid
from datetime import timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from accounts.models import User, UserRole
from .encryption import encrypt_bytes, decrypt_bytes, is_encrypted


class EncryptedFileSystemStorage(FileSystemStorage):
    """
    Application-level zero-unencrypted disk storage:
    Encrypts files at rest with Fernet (AES-128-CBC + HMAC-SHA256) before writing to filesystem.
    Files on disk are saved with .enc extensions and contain opaque ciphertext.
    """
    def _save(self, name, content):
        if not name.endswith('.enc'):
            name = f"{name}.enc"
        
        # Read raw content
        raw_bytes = content.read()
        encrypted_bytes = encrypt_bytes(raw_bytes)
        
        # Create encrypted ContentFile to pass to base save
        encrypted_content = ContentFile(encrypted_bytes)
        return super()._save(name, encrypted_content)

    def _open(self, name, mode='rb'):
        # Open raw file from disk
        raw_file = super()._open(name, mode)
        ciphertext = raw_file.read()
        raw_file.close()
        
        plaintext = decrypt_bytes(ciphertext)
        return io.BytesIO(plaintext)


protected_storage = EncryptedFileSystemStorage(location=settings.PROTECTED_MEDIA_ROOT)


def protected_paper_path(instance, filename):
    date_path = timezone.now().strftime('%Y/%m')
    clean_name = filename.replace('.enc', '')
    unique_name = f"{uuid.uuid4().hex[:12]}_{clean_name}.enc"
    return os.path.join('secure_papers', date_path, unique_name)


def protected_review_path(instance, filename):
    date_path = timezone.now().strftime('%Y/%m')
    clean_name = filename.replace('.enc', '')
    unique_name = f"{uuid.uuid4().hex[:12]}_{clean_name}.enc"
    return os.path.join('annotated_reviews', date_path, unique_name)


class PaperStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PENDING_COORD = 'PENDING_COORD', 'Pending Coordinator Triage'
    REJECTED_INITIAL = 'REJECTED_INITIAL', 'Rejected at Triage'
    PENDING_ADVISOR = 'PENDING_ADVISOR', 'Under Peer Review'
    ADVISOR_COMMENTED = 'ADVISOR_COMMENTED', 'Reviews Submitted (Awaiting Consolidation)'
    REVISION_REQUIRED = 'REVISION_REQUIRED', 'Revision Required'
    ADVISOR_APPROVED = 'ADVISOR_APPROVED', 'Reviewers Approved'
    PUBLISHED = 'PUBLISHED', 'Published (Archived Lock)'
    RETRACTED_FOR_REVISION = 'RETRACTED_FOR_REVISION', 'Retracted for Revision'


class ReviewDecision(models.TextChoices):
    REVISION_NEEDED = 'REVISION_NEEDED', 'Request Revisions'
    APPROVED = 'APPROVED', 'Approve as Final'


class CoordinatorDecision(models.TextChoices):
    REVISION_REQUIRED = 'REVISION_REQUIRED', 'Require Author Revisions'
    APPROVED = 'APPROVED', 'Approve for Publication'


class AccessRequestStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class NotificationType(models.TextChoices):
    PAPER_ASSIGNED = 'PAPER_ASSIGNED', 'Paper Assigned for Review'
    REVIEW_SUBMITTED = 'REVIEW_SUBMITTED', 'Review Critique Submitted'
    DIRECTIVE_ISSUED = 'DIRECTIVE_ISSUED', 'Revision Directive Issued'
    PAPER_RETRACTED = 'PAPER_RETRACTED', 'Paper Recalled for Revision'
    ACCESS_GRANTED = 'ACCESS_GRANTED', 'Access Pass Granted'
    REVISION_SUBMITTED = 'REVISION_SUBMITTED', 'Revision Round Submitted'
    SYSTEM = 'SYSTEM', 'System Alert'


def get_assignable_reviewers(paper):
    """
    Conflict of Interest (COI) Guard:
    Returns doctors eligible to review this paper, strictly excluding the paper's author.
    """
    return User.objects.filter(role=UserRole.DOCTOR).exclude(id=paper.author_id).order_by('department', 'first_name')


class Paper(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    category = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    co_authors = models.CharField(max_length=255, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_papers')
    current_status = models.CharField(
        max_length=30,
        choices=PaperStatus.choices,
        default=PaperStatus.DRAFT,
        db_index=True
    )
    retraction_reason = models.TextField(blank=True, help_text="Clinical justification for post-publication recall.")
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'papers_paper'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.get_current_status_display()}]"

    @property
    def latest_round(self):
        # Use prefetched cache if available to prevent N+1 queries in list views
        if hasattr(self, '_prefetched_objects_cache') and 'rounds' in self._prefetched_objects_cache:
            rounds = sorted(self._prefetched_objects_cache['rounds'], key=lambda r: r.round_number, reverse=True)
            return rounds[0] if rounds else None
        return self.rounds.order_by('-round_number').first()

    @property
    def round_count(self):
        if hasattr(self, '_prefetched_objects_cache') and 'rounds' in self._prefetched_objects_cache:
            return len(self._prefetched_objects_cache['rounds'])
        return self.rounds.count()

    @property
    def is_published(self):
        return self.current_status == PaperStatus.PUBLISHED

    @property
    def is_locked(self):
        return self.current_status == PaperStatus.PUBLISHED

    # FSM State Transition Methods
    def submit_to_coordinator(self):
        if self.current_status not in [PaperStatus.DRAFT, PaperStatus.REVISION_REQUIRED, PaperStatus.RETRACTED_FOR_REVISION]:
            raise ValidationError(f"Cannot submit manuscript from state '{self.current_status}'.")
        self.current_status = PaperStatus.PENDING_COORD
        self.save(update_fields=['current_status'])

    def reject_initial(self):
        if self.current_status != PaperStatus.PENDING_COORD:
            raise ValidationError("Only papers pending coordinator triage can be rejected initially.")
        self.current_status = PaperStatus.REJECTED_INITIAL
        self.save(update_fields=['current_status'])

    def assign_reviewers(self, reviewers, round_obj=None, deadline_days=14, actor=None):
        """Assigns reviewers enforcing COI Guard."""
        if self.current_status not in [PaperStatus.PENDING_COORD, PaperStatus.PENDING_ADVISOR]:
            raise ValidationError(f"Cannot assign reviewers in state '{self.current_status}'.")
        
        target_round = round_obj or self.latest_round
        if not target_round:
            raise ValidationError("Cannot assign reviewers to a paper with no rounds.")

        deadline = timezone.now() + timedelta(days=deadline_days)
        assignments = []

        for reviewer in reviewers:
            if reviewer.id == self.author_id:
                raise ValidationError(f"Conflict of Interest: Author {reviewer.get_full_name()} cannot review their own paper.")
            if reviewer.role != UserRole.DOCTOR:
                raise ValidationError(f"User {reviewer.username} is not a DOCTOR.")

            assignment, created = ReviewAssignment.objects.get_or_create(
                round=target_round,
                reviewer=reviewer,
                defaults={'deadline': deadline}
            )
            assignments.append(assignment)

            # In-App Notification to reviewer
            notify_user(
                recipient=reviewer,
                actor=actor,
                paper=self,
                notif_type=NotificationType.PAPER_ASSIGNED,
                message=f"You have been assigned to peer-review '{self.title}' (Round {target_round.round_number}).",
                target_url=f"/papers/{self.id}/review/"
            )

        self.current_status = PaperStatus.PENDING_ADVISOR
        self.save(update_fields=['current_status'])
        return assignments

    def check_and_update_reviews(self, round_obj=None):
        """Checks if all assigned reviews for the round are completed."""
        target_round = round_obj or self.latest_round
        if not target_round:
            return
        
        assignments = target_round.assignments.all()
        if assignments.exists() and all(a.is_completed for a in assignments):
            self.current_status = PaperStatus.ADVISOR_COMMENTED
            self.save(update_fields=['current_status'])

    def dispatch_coordinator_letter(self, coordinator, comment, decision, round_obj=None):
        """Dispatches an air-gapped synthesized coordinator letter to the author."""
        if self.current_status != PaperStatus.ADVISOR_COMMENTED:
            raise ValidationError("Coordinator letter can only be dispatched after reviews are completed.")
        
        target_round = round_obj or self.latest_round
        letter, _ = CoordinatorLetter.objects.update_or_create(
            round=target_round,
            defaults={
                'coordinator': coordinator,
                'consolidated_comment': comment,
                'decision': decision,
                'sent_at': timezone.now()
            }
        )

        if decision == CoordinatorDecision.REVISION_REQUIRED:
            self.current_status = PaperStatus.REVISION_REQUIRED
            # Notify Author
            notify_user(
                recipient=self.author,
                actor=coordinator,
                paper=self,
                notif_type=NotificationType.DIRECTIVE_ISSUED,
                message=f"Coordinator C issued revision directives for '{self.title}'. Round {target_round.round_number + 1} requested.",
                target_url=f"/papers/{self.id}/revision/"
            )
        elif decision == CoordinatorDecision.APPROVED:
            self.current_status = PaperStatus.ADVISOR_APPROVED

        self.save(update_fields=['current_status'])
        return letter

    def publish(self):
        """Permanently locks paper into PUBLISHED state."""
        if self.current_status not in [PaperStatus.ADVISOR_COMMENTED, PaperStatus.ADVISOR_APPROVED]:
            raise ValidationError(f"Cannot publish paper from state '{self.current_status}'.")
        self.current_status = PaperStatus.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=['current_status', 'published_at'])

    def retract_for_revision(self, coordinator, reason):
        """
        Module 3: Retracts a PUBLISHED paper back for revisions.
        Immediately de-lists the paper from the public catalog.
        """
        if self.current_status != PaperStatus.PUBLISHED:
            raise ValidationError("Only published manuscripts can be recalled for revision.")
        self.current_status = PaperStatus.RETRACTED_FOR_REVISION
        self.retraction_reason = reason
        self.save(update_fields=['current_status', 'retraction_reason'])

        # Notify author
        notify_user(
            recipient=self.author,
            actor=coordinator,
            paper=self,
            notif_type=NotificationType.PAPER_RETRACTED,
            message=f"Published manuscript '{self.title}' has been recalled for revision: {reason}",
            target_url=f"/papers/{self.id}/revision/"
        )
        return self


class PaperRound(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.PositiveIntegerField(default=1)
    pdf_file = models.FileField(upload_to=protected_paper_path, storage=protected_storage)
    summary_notes = models.TextField(blank=True, help_text="Author's notes regarding this submission round.")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'papers_paperround'
        unique_together = ('paper', 'round_number')
        ordering = ['round_number']

    def __str__(self):
        return f"{self.paper.title} - Round {self.round_number}"


class ReviewAssignment(models.Model):
    round = models.ForeignKey(PaperRound, on_delete=models.CASCADE, related_name='assignments')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_assignments')
    is_completed = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'papers_reviewassignment'
        unique_together = ('round', 'reviewer')
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Review by {self.reviewer.get_full_name() or self.reviewer.username} on Round {self.round.round_number}"

    def clean(self):
        super().clean()
        if self.round_id and self.reviewer_id:
            if self.reviewer_id == self.round.paper.author_id:
                raise ValidationError("Conflict of Interest: Author cannot be assigned as reviewer to their own manuscript.")
            if self.reviewer.role != UserRole.DOCTOR:
                raise ValidationError("Reviewers must possess the DOCTOR role.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ReviewFeedback(models.Model):
    assignment = models.OneToOneField(ReviewAssignment, on_delete=models.CASCADE, related_name='feedback')
    structure_comment = models.TextField(help_text="เค้าโครง: Structure & Methodology critique")
    intro_comment = models.TextField(help_text="บทนำ: Introduction & Literature critique")
    expansion_comment = models.TextField(help_text="บทขยาย: Results, Data & Discussion critique")
    decision = models.CharField(max_length=20, choices=ReviewDecision.choices, default=ReviewDecision.REVISION_NEEDED)
    annotated_pdf = models.FileField(upload_to=protected_review_path, storage=protected_storage, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'papers_reviewfeedback'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Feedback for {self.assignment} [{self.get_decision_display()}]"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Mark assignment completed and verify paper state
        assignment = self.assignment
        if not assignment.is_completed:
            assignment.is_completed = True
            assignment.save(update_fields=['is_completed'])
        assignment.round.paper.check_and_update_reviews(assignment.round)

        # Notify Coordinator C
        if is_new:
            coordinators = User.objects.filter(role=UserRole.COORDINATOR)
            for c in coordinators:
                notify_user(
                    recipient=c,
                    actor=assignment.reviewer,
                    paper=assignment.round.paper,
                    notif_type=NotificationType.REVIEW_SUBMITTED,
                    message=f"Critique submitted for '{assignment.round.paper.title}' (Round {assignment.round.round_number}).",
                    target_url=f"/coordinator/papers/{assignment.round.paper.id}/consolidate/"
                )


class CoordinatorLetter(models.Model):
    """
    Air-Gapped Synthesis Letter:
    The ONLY feedback viewable by the author. Reviewer identities and raw critique are excluded.
    """
    round = models.OneToOneField(PaperRound, on_delete=models.CASCADE, related_name='coordinator_letter')
    coordinator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_letters')
    consolidated_comment = models.TextField(help_text="Consolidated synthesis and revision directives")
    decision = models.CharField(max_length=20, choices=CoordinatorDecision.choices)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'papers_coordinatorletter'
        ordering = ['-sent_at']

    def __str__(self):
        return f"Coordinator Letter for Round {self.round.round_number} [{self.get_decision_display()}]"


class AccessRequest(models.Model):
    DURATION_CHOICES = [
        (7, '7 Days Pass (Urgent Consultation)'),
        (14, '14 Days Pass (Departmental Research)'),
        (30, '30 Days Pass (Fellowship & Study)'),
    ]

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='access_requests')
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paper_access_requests')
    reason = models.TextField(help_text="Clinical justification for requesting full-text reading access.")
    duration_days = models.PositiveIntegerField(choices=DURATION_CHOICES, default=7)
    status = models.CharField(max_length=20, choices=AccessRequestStatus.choices, default=AccessRequestStatus.PENDING, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_access_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    coordinator_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'papers_accessrequest'
        ordering = ['-created_at']

    def __str__(self):
        return f"AccessRequest by {self.requester.get_full_name()} for {self.paper.title} [{self.get_status_display()}]"

    @property
    def is_active(self):
        return self.status == AccessRequestStatus.APPROVED and bool(self.expires_at) and self.expires_at > timezone.now()

    @property
    def is_expired(self):
        return bool(self.expires_at) and self.expires_at <= timezone.now()

    def approve(self, coordinator, notes=''):
        self.status = AccessRequestStatus.APPROVED
        self.reviewed_by = coordinator
        self.reviewed_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(days=self.duration_days)
        if notes:
            self.coordinator_notes = notes
        self.save()

        # In-App Notification to requester
        notify_user(
            recipient=self.requester,
            actor=coordinator,
            paper=self.paper,
            notif_type=NotificationType.ACCESS_GRANTED,
            message=f"Your {self.duration_days}-day reading pass for '{self.paper.title}' has been approved.",
            target_url="/catalog/"
        )

    def reject(self, coordinator, notes=''):
        self.status = AccessRequestStatus.REJECTED
        self.reviewed_by = coordinator
        self.reviewed_at = timezone.now()
        self.coordinator_notes = notes
        self.save()


class Notification(models.Model):
    """Module 1: In-App Notification Engine."""
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='triggered_notifications')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    message = models.CharField(max_length=255)
    target_url = models.CharField(max_length=255, default='#')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'papers_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message}"


def notify_user(recipient, *args, actor=None, paper=None, notif_type=None, message='', target_url='#', **kwargs):
    """Helper to create and dispatch in-app notifications."""
    if len(args) == 4:
        actor = args[0]
        paper = args[1]
        notif_type = args[2]
        message = args[3]
    elif len(args) == 2:
        notif_type = args[0]
        message = args[1]
    elif len(args) == 1:
        message = args[0]

    n_type = notif_type or kwargs.get('notification_type') or NotificationType.SYSTEM
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        paper=paper,
        notification_type=n_type,
        message=message,
        target_url=target_url
    )
