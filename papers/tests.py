from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django_otp.plugins.otp_totp.models import TOTPDevice
from accounts.models import User, UserRole, AuditLog, AuditAction
from papers.models import (
    Paper, PaperRound, ReviewAssignment, ReviewFeedback, CoordinatorLetter,
    AccessRequest, PaperStatus, ReviewDecision, CoordinatorDecision,
    AccessRequestStatus, Notification, NotificationType, notify_user,
    get_assignable_reviewers
)


class MedResearchDMSTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Personas
        self.alice = User.objects.create_user(
            username='alice',
            password='password123',
            first_name='Alice',
            last_name='Mercer',
            role=UserRole.DOCTOR,
            department='Cardiology',
            specialization='Interventional Cardiology'
        )

        self.bob = User.objects.create_user(
            username='bob',
            password='password123',
            first_name='Robert',
            last_name='Chen',
            role=UserRole.DOCTOR,
            department='Surgery',
            specialization='Oncologic Surgery'
        )

        self.charlie = User.objects.create_user(
            username='charlie',
            password='password123',
            first_name='Charlie',
            last_name='Vance',
            role=UserRole.COORDINATOR,
            department='Research Administration'
        )

        self.sarah = User.objects.create_user(
            username='sarah',
            password='password123',
            first_name='Sarah',
            last_name='Jenkins',
            role=UserRole.STAFF_VIEWER,
            department='Emergency Medicine'
        )

        self.admin = User.objects.create_user(
            username='admin',
            password='password123',
            first_name='System',
            last_name='Admin',
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Sample PDF dummy file
        self.dummy_pdf = SimpleUploadedFile("test_sample.pdf", b"%PDF-1.4 test content", content_type="application/pdf")

    def test_1_coi_guard_queryset_and_validation(self):
        """Conflict of Interest (COI) Guard strictly excludes author and prevents self-assignment."""
        paper = Paper.objects.create(
            title="Cardiology Advances",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Sample cardiology study",
            current_status=PaperStatus.PENDING_COORD
        )
        round1 = PaperRound.objects.create(
            paper=paper,
            round_number=1,
            pdf_file=self.dummy_pdf
        )

        # 1. Test Queryset Exclusion
        assignable = get_assignable_reviewers(paper)
        self.assertIn(self.bob, assignable)
        self.assertNotIn(self.alice, assignable, "COI Guard Failure: Author Alice must be excluded from assignable reviewers!")

        # 2. Test Model Clean Validation
        invalid_assignment = ReviewAssignment(round=round1, reviewer=self.alice)
        with self.assertRaises(ValidationError):
            invalid_assignment.clean()

        # 3. Test Paper.assign_reviewers method rejection
        with self.assertRaises(ValidationError):
            paper.assign_reviewers([self.alice])

    def test_2_doctor_dual_role(self):
        """Unified Doctor role allows both authoring manuscripts and peer-reviewing colleagues."""
        # Alice authors Paper A
        paper_a = Paper.objects.create(
            title="Paper by Alice",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Abstract A",
            current_status=PaperStatus.PENDING_COORD
        )
        r_a = PaperRound.objects.create(paper=paper_a, round_number=1, pdf_file=self.dummy_pdf)

        # Bob authors Paper B
        paper_b = Paper.objects.create(
            title="Paper by Bob",
            author=self.bob,
            department="Surgery",
            category="Surgery",
            abstract="Abstract B",
            current_status=PaperStatus.PENDING_COORD
        )
        r_b = PaperRound.objects.create(paper=paper_b, round_number=1, pdf_file=self.dummy_pdf)

        # Alice reviews Bob's paper, Bob reviews Alice's paper
        assignment_b_to_alice = paper_b.assign_reviewers([self.alice])
        assignment_a_to_bob = paper_a.assign_reviewers([self.bob])

        self.assertEqual(len(assignment_b_to_alice), 1)
        self.assertEqual(len(assignment_a_to_bob), 1)
        self.assertEqual(paper_a.current_status, PaperStatus.PENDING_ADVISOR)
        self.assertEqual(paper_b.current_status, PaperStatus.PENDING_ADVISOR)

    def test_3_fsm_lifecycle_transitions(self):
        """Finite State Machine correctly transitions through all states."""
        paper = Paper.objects.create(
            title="FSM Lifecycle Paper",
            author=self.alice,
            department="Cardiology",
            category="Clinical Trial",
            abstract="Lifecycle test",
            current_status=PaperStatus.DRAFT
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)

        # DRAFT -> PENDING_COORD
        paper.submit_to_coordinator()
        self.assertEqual(paper.current_status, PaperStatus.PENDING_COORD)

        # PENDING_COORD -> PENDING_ADVISOR
        paper.assign_reviewers([self.bob])
        self.assertEqual(paper.current_status, PaperStatus.PENDING_ADVISOR)

        # Peer critique submission -> ADVISOR_COMMENTED
        assignment = ReviewAssignment.objects.get(round=round1, reviewer=self.bob)
        ReviewFeedback.objects.create(
            assignment=assignment,
            structure_comment="Methodology is sound",
            intro_comment="Background is good",
            expansion_comment="Expand discussion",
            decision=ReviewDecision.REVISION_NEEDED
        )
        paper.refresh_from_db()
        self.assertEqual(paper.current_status, PaperStatus.ADVISOR_COMMENTED)

        # Coordinator Letter dispatch -> REVISION_REQUIRED
        paper.dispatch_coordinator_letter(
            coordinator=self.charlie,
            comment="Please expand discussion per directives.",
            decision=CoordinatorDecision.REVISION_REQUIRED
        )
        paper.refresh_from_db()
        self.assertEqual(paper.current_status, PaperStatus.REVISION_REQUIRED)

        # Author submits Round 2 -> PENDING_COORD
        round2 = PaperRound.objects.create(paper=paper, round_number=2, pdf_file=self.dummy_pdf)
        paper.submit_to_coordinator()
        self.assertEqual(paper.current_status, PaperStatus.PENDING_COORD)

        # Re-assign Bob for Round 2
        paper.assign_reviewers([self.bob], round_obj=round2)
        assignment2 = ReviewAssignment.objects.get(round=round2, reviewer=self.bob)
        ReviewFeedback.objects.create(
            assignment=assignment2,
            structure_comment="Perfect",
            intro_comment="Approved",
            expansion_comment="Approved",
            decision=ReviewDecision.APPROVED
        )
        paper.refresh_from_db()
        self.assertEqual(paper.current_status, PaperStatus.ADVISOR_COMMENTED)

        # Publish lock
        paper.publish()
        self.assertEqual(paper.current_status, PaperStatus.PUBLISHED)
        self.assertTrue(paper.is_locked)
        self.assertIsNotNone(paper.published_at)

    def test_4_air_gap_coordinator_isolation(self):
        """Author cannot view reviewer identities or raw feedback; only Coordinator letters."""
        paper = Paper.objects.create(
            title="Air Gap Protocol Paper",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Testing double-blind mediation",
            current_status=PaperStatus.PENDING_ADVISOR
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)
        assignment = ReviewAssignment.objects.create(round=round1, reviewer=self.bob, is_completed=True)
        ReviewFeedback.objects.create(
            assignment=assignment,
            structure_comment="SECRET_REVIEWER_STRUCTURE_COMMENT_9988",
            intro_comment="SECRET_REVIEWER_INTRO_COMMENT_9988",
            expansion_comment="SECRET_REVIEWER_EXPANSION_COMMENT_9988",
            decision=ReviewDecision.REVISION_NEEDED
        )
        paper.current_status = PaperStatus.ADVISOR_COMMENTED
        paper.save()

        CoordinatorLetter.objects.create(
            round=round1,
            coordinator=self.charlie,
            consolidated_comment="PUBLIC_SYNTHESIZED_COORDINATOR_DIRECTIVE_1234",
            decision=CoordinatorDecision.REVISION_REQUIRED
        )

        # Login as author (Alice) and inspect dossier
        self.client.login(username='alice', password='password123')
        response = self.client.get(reverse('paper_detail', kwargs={'paper_id': paper.id}))
        self.assertEqual(response.status_code, 200)

        # Verify raw feedback and reviewer name are completely absent in the dossier main content
        content = response.content.decode('utf-8')
        self.assertNotIn("SECRET_REVIEWER_STRUCTURE_COMMENT_9988", content)
        main_content = content.split('<main')[1]
        self.assertNotIn("Robert Chen", main_content)
        self.assertNotIn("bob.chen@hospital.internal", main_content)

        # Verify synthesized directive IS present
        self.assertIn("PUBLIC_SYNTHESIZED_COORDINATOR_DIRECTIVE_1234", content)

    def test_5_totp_2fa_setup_and_verification(self):
        """TOTP 2FA setup generates QR code and activates upon token confirmation."""
        from django_otp.oath import TOTP
        self.client.login(username='alice', password='password123')

        # 1. Load setup page
        response = self.client.get(reverse('totp_setup'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data:image/png;base64,', response.content.decode('utf-8'))

        # 2. Retrieve unconfirmed device and generate valid time-based token
        device = TOTPDevice.objects.get(user=self.alice, confirmed=False)
        totp = TOTP(key=device.bin_key, step=device.step, t0=device.t0, digits=device.digits, drift=device.drift)
        token = str(totp.token()).zfill(6)

        # 3. Submit verification token
        post_response = self.client.post(reverse('totp_setup'), {
            'action': 'verify',
            'token': token
        }, follow=True)
        self.assertEqual(post_response.status_code, 200)

        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_totp_enabled)
        device.refresh_from_db()
        self.assertTrue(device.confirmed)

    def test_6_catalog_visibility(self):
        """Catalog displays ONLY published papers and supports keyword search."""
        published = Paper.objects.create(
            title="Thrombectomy in Stroke",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Stroke intervention",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        draft = Paper.objects.create(
            title="Unpublished Trauma Draft",
            author=self.bob,
            department="Surgery",
            category="Surgery",
            abstract="Trauma study",
            current_status=PaperStatus.DRAFT
        )

        response = self.client.get(reverse('catalog_view'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("Thrombectomy in Stroke", content)
        self.assertNotIn("Unpublished Trauma Draft", content)

        # Test search query
        search_res = self.client.get(reverse('catalog_view') + '?q=Stroke')
        self.assertIn("Thrombectomy in Stroke", search_res.content.decode('utf-8'))

        search_res2 = self.client.get(reverse('catalog_view') + '?q=Trauma')
        self.assertNotIn("Unpublished Trauma Draft", search_res2.content.decode('utf-8'))

    def test_7_access_gate_enforcement(self):
        """Time-bound access ticket unlocks protected PDF delivery for staff clinicians."""
        paper = Paper.objects.create(
            title="Locked Clinical Trial",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Trial abstract",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)

        # Dr. Sarah (Staff Viewer) attempts unauthorized access
        self.client.login(username='sarah', password='password123')
        denied_response = self.client.get(
            reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': 1})
        )
        self.assertEqual(denied_response.status_code, 403)

        # Sarah submits Access Request Ticket
        ticket = AccessRequest.objects.create(
            paper=paper,
            requester=self.sarah,
            duration_days=14,
            reason="Emergency department clinical audit",
            status=AccessRequestStatus.PENDING
        )

        # Charlie (Coordinator) approves ticket
        ticket.approve(coordinator=self.charlie)

        # Sarah requests PDF again -> Granted
        granted_response = self.client.get(
            reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': 1})
        )
        self.assertEqual(granted_response.status_code, 200)
        self.assertEqual(granted_response['Content-Type'], 'application/pdf')
        # Verify X-Frame-Options allows SAMEORIGIN embedding in review iframe
        self.assertEqual(granted_response.headers.get('X-Frame-Options'), 'SAMEORIGIN')

    def test_8_role_switcher(self):
        """One-click role switcher respects ENABLE_DEMO_MODE feature flag (SEC-01)."""
        # When demo mode is disabled: raises 404
        with self.settings(ENABLE_DEMO_MODE=False):
            res_disabled = self.client.get(reverse('switch_role', kwargs={'user_id': self.bob.id}))
            self.assertEqual(res_disabled.status_code, 404)

        # When demo mode is enabled: successfully switches persona
        with self.settings(ENABLE_DEMO_MODE=True):
            response = self.client.get(reverse('switch_role', kwargs={'user_id': self.bob.id}), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['user'].id, self.bob.id)

    def test_9_xframe_options_sameorigin_for_pdf_embedding(self):
        """PDF streaming response explicitly returns X-Frame-Options: SAMEORIGIN for in-browser review embedding."""
        paper = Paper.objects.create(
            title="Stroke Study",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Study",
            current_status=PaperStatus.PENDING_ADVISOR
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)
        ReviewAssignment.objects.create(round=round1, reviewer=self.bob)

        # Bob (reviewer) requests PDF for review desk
        self.client.login(username='bob', password='password123')
        response = self.client.get(reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')

    def test_10_in_app_notifications(self):
        """Notification engine triggers alerts, provides navbar badge counts, and supports mark-as-read."""
        paper = Paper.objects.create(
            title="Cardio Risk",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Risk assessment",
            current_status=PaperStatus.PENDING_COORD
        )
        # 1. Trigger notification via notify_user helper
        notif = notify_user(
            recipient=self.alice,
            notification_type=NotificationType.PAPER_ASSIGNED,
            message="Test notification for Alice",
            actor=self.charlie,
            paper=paper,
            target_url=f"/papers/{paper.id}/"
        )
        self.assertIsNotNone(notif)
        self.assertFalse(notif.is_read)

        # 2. Verify context processor populates unread count in template
        self.client.login(username='alice', password='password123')
        res = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['unread_notifications_count'], 1)
        self.assertIn("Test notification for Alice", res.content.decode('utf-8'))

        # 3. Mark single notification as read
        mark_res = self.client.get(reverse('mark_notification_read', kwargs={'notification_id': notif.id}))
        self.assertEqual(mark_res.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # 4. Mark all notifications as read
        notify_user(self.alice, NotificationType.SYSTEM, "System notification 1")
        notify_user(self.alice, NotificationType.SYSTEM, "System notification 2")
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=False).count(), 2)

        bulk_res = self.client.get(reverse('mark_all_notifications_read'))
        self.assertEqual(bulk_res.status_code, 302)
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=False).count(), 0)

    def test_11_dedicated_it_admin_portal(self):
        """IT Admin Portal enforces strict role boundary, user management, and 1-click 2FA reset."""
        # 1. Access Control: Coordinator and regular Doctor are denied access
        self.client.login(username='alice', password='password123')
        res_alice = self.client.get(reverse('admin_portal_dashboard'))
        self.assertEqual(res_alice.status_code, 403)

        self.client.login(username='charlie', password='password123')
        res_charlie = self.client.get(reverse('admin_portal_dashboard'))
        self.assertEqual(res_charlie.status_code, 403)

        # 2. System Admin is granted access
        self.client.login(username='admin', password='password123')
        res_admin = self.client.get(reverse('admin_portal_dashboard'))
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn("IT Administration & Security Portal", res_admin.content.decode('utf-8'))

        # 3. Create new clinician via admin portal
        create_res = self.client.post(reverse('admin_user_create'), {
            'username': 'dr_house',
            'first_name': 'Gregory',
            'last_name': 'House',
            'email': 'ghouse@hospital.internal',
            'password': 'password123',
            'role': UserRole.DOCTOR,
            'department': 'Diagnostic Medicine',
            'specialization': 'Infectious Disease & Nephrology',
            'is_active': True,
        }, follow=True)
        self.assertEqual(create_res.status_code, 200)
        house = User.objects.get(username='dr_house')
        self.assertEqual(house.department, 'Diagnostic Medicine')

        # 4. 1-Click 2FA Reset
        # Enable 2FA on Alice first
        TOTPDevice.objects.create(user=self.alice, name='default', confirmed=True)
        self.alice.is_totp_enabled = True
        self.alice.save()
        self.assertTrue(self.alice.is_totp_enabled)

        # Admin resets 2FA for Alice
        reset_res = self.client.post(reverse('admin_user_reset_2fa', kwargs={'user_id': self.alice.id}), follow=True)
        self.assertEqual(reset_res.status_code, 200)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_totp_enabled)
        self.assertFalse(TOTPDevice.objects.filter(user=self.alice).exists())

        # 5. Toggle active status
        toggle_res = self.client.post(reverse('admin_user_toggle_active', kwargs={'user_id': house.id}), follow=True)
        self.assertEqual(toggle_res.status_code, 200)
        house.refresh_from_db()
        self.assertFalse(house.is_active)

    def test_12_post_publication_retraction_workflow(self):
        """Post-publication retraction removes paper from catalog, locks access, and unlocks revision desk."""
        # 1. Setup Published Paper
        paper = Paper.objects.create(
            title="Cardiovascular Safety of Drug X",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Study abstract",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        r1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)

        # Sarah has an approved access pass
        pass_ticket = AccessRequest.objects.create(
            paper=paper,
            requester=self.sarah,
            duration_days=30,
            reason="Clinical review",
            status=AccessRequestStatus.APPROVED,
            expires_at=timezone.now() + timedelta(days=20),
            reviewed_by=self.charlie
        )

        # 2. Coordinator retracts paper with directive
        self.client.login(username='charlie', password='password123')
        retract_res = self.client.post(reverse('coordinator_retract_paper', kwargs={'paper_id': paper.id}), {
            'reason': 'Data anomaly detected in Table 2: Statistical verification required.'
        }, follow=True)
        self.assertEqual(retract_res.status_code, 200)

        paper.refresh_from_db()
        self.assertEqual(paper.current_status, PaperStatus.RETRACTED_FOR_REVISION)
        self.assertFalse(paper.is_locked)
        self.assertIn("Data anomaly detected", paper.retraction_reason)

        # 3. Verify paper is excluded from public Research Catalog
        cat_res = self.client.get(reverse('catalog_view'))
        self.assertNotIn("Cardiovascular Safety of Drug X", cat_res.content.decode('utf-8'))

        # 4. Verify Sarah's access to PDF is now rejected (403 Forbidden)
        self.client.login(username='sarah', password='password123')
        denied_res = self.client.get(reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': 1}))
        self.assertEqual(denied_res.status_code, 403)

        # 5. Author (Alice) sees retraction and submits Round 2 revision
        self.client.login(username='alice', password='password123')
        rev_page = self.client.get(reverse('paper_revision', kwargs={'paper_id': paper.id}))
        self.assertEqual(rev_page.status_code, 200)

        rev_pdf = SimpleUploadedFile("test_rev.pdf", b"%PDF-1.4 revised content", content_type="application/pdf")
        rev_post = self.client.post(reverse('paper_revision', kwargs={'paper_id': paper.id}), {
            'pdf_file': rev_pdf,
            'summary_notes': 'Table 2 data corrected and verified against trial database.'
        }, follow=True)
        self.assertEqual(rev_post.status_code, 200)

        paper.refresh_from_db()
        self.assertEqual(paper.current_status, PaperStatus.PENDING_COORD)
        self.assertEqual(paper.rounds.count(), 2)

    def test_13_executive_overview_dashboard(self):
        """Executive dashboard aggregates institutional research KPIs and Chart.js dataset formats."""
        # Staff viewer denied
        self.client.login(username='sarah', password='password123')
        res_sarah = self.client.get(reverse('executive_dashboard'))
        self.assertEqual(res_sarah.status_code, 403)

        # Coordinator permitted
        self.client.login(username='charlie', password='password123')
        res_coord = self.client.get(reverse('executive_dashboard'))
        self.assertEqual(res_coord.status_code, 200)
        self.assertIn('dept_labels_json', res_coord.context)
        self.assertIn('funnel_data_json', res_coord.context)
        self.assertIn('month_labels_json', res_coord.context)
        self.assertIn('Executive Research Overview & Analytics', res_coord.content.decode('utf-8'))

    def test_14_security_audit_trail(self):
        """Audit logging captures user actions, IP addresses, and renders in admin audit trail."""
        from accounts.utils import log_audit

        # Clear logs
        AuditLog.objects.all().delete()

        # Log an action
        log_audit(
            request=None,
            action=AuditAction.STREAM_PDF,
            user=self.alice,
            ip_address="192.168.1.50",
            details="Streamed protected PDF for testing audit log"
        )
        self.assertEqual(AuditLog.objects.count(), 1)
        log_entry = AuditLog.objects.first()
        self.assertEqual(log_entry.user, self.alice)
        self.assertEqual(log_entry.ip_address, "192.168.1.50")
        self.assertEqual(log_entry.action, AuditAction.STREAM_PDF)

        # Admin views audit logs
        self.client.login(username='admin', password='password123')
        res = self.client.get(reverse('admin_audit_logs'))
        self.assertEqual(res.status_code, 200)
        self.assertIn("Streamed protected PDF for testing audit log", res.content.decode('utf-8'))

    def test_15_dynamic_visual_pdf_watermark(self):
        """Peer review workspace renders non-destructive watermark overlay with viewer details."""
        paper = Paper.objects.create(
            title="Watermark Manuscript",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Testing watermark",
            current_status=PaperStatus.PENDING_ADVISOR
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)
        ReviewAssignment.objects.create(round=round1, reviewer=self.bob)

        # Bob accesses review desk
        self.client.login(username='bob', password='password123')
        response = self.client.get(reverse('review_workspace', kwargs={'paper_id': paper.id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("watermark-overlay", content)
        self.assertIn("pointer-events: none", content)
        self.assertIn("HOSPITAL CONFIDENTIAL", content)
        self.assertIn("bob", content)

    def test_16_argon2_password_hashing(self):
        """User passwords are encrypted with Argon2 algorithm and verify correctly."""
        from django.contrib.auth import authenticate
        user = User.objects.create_user(
            username='argon_doctor',
            password='ComplexArgon2Password!2026',
            role=UserRole.DOCTOR
        )
        self.assertTrue(user.password.startswith('argon2'), f"Expected Argon2 hash prefix, got {user.password[:15]}")
        auth_user = authenticate(username='argon_doctor', password='ComplexArgon2Password!2026')
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user.username, 'argon_doctor')

    def test_17_pdf_encryption_at_rest(self):
        """Uploaded PDFs are stored on disk with .enc extension and encrypted bytes, streaming decrypts in-memory."""
        from papers.encryption import is_encrypted
        import os

        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        dummy_file = SimpleUploadedFile("encrypted_test.pdf", pdf_content, content_type="application/pdf")

        paper = Paper.objects.create(
            title="Encrypted Storage Test",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Testing zero-plaintext disk storage.",
            current_status=PaperStatus.PENDING_COORD
        )
        round_obj = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=dummy_file)

        # Verify disk file properties
        disk_path = round_obj.pdf_file.path
        self.assertTrue(disk_path.endswith('.enc'), f"Expected .enc file extension, got {disk_path}")
        self.assertTrue(os.path.exists(disk_path))

        with open(disk_path, 'rb') as f:
            disk_bytes = f.read()

        self.assertTrue(is_encrypted(disk_bytes), "File on disk should be encrypted with Fernet")
        self.assertNotIn(b"%PDF-", disk_bytes, "Raw plaintext PDF magic bytes must not be present on disk")

        # Verify in-memory decryption when streaming
        self.client.login(username='alice', password='password123')
        stream_res = self.client.get(reverse('serve_protected_paper', kwargs={'paper_id': paper.id, 'round_number': 1}))
        self.assertEqual(stream_res.status_code, 200)
        self.assertEqual(stream_res['Content-Type'], 'application/pdf')
        stream_content = b"".join(stream_res.streaming_content)
        self.assertIn(b"%PDF-", stream_content, "Streamed content must be decrypted in-memory")

    def test_18_backup_and_restore_dms(self):
        """Backup command bundles database, encrypted media, and SHA-256 manifest; restore verifies and loads."""
        from django.core.management import call_command
        import tempfile
        import os
        import tarfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            backup_file = os.path.join(tmp_dir, "test_backup.tar.gz")
            call_command('backup_dms', output=backup_file)
            self.assertTrue(os.path.exists(backup_file))

            # Inspect archive
            with tarfile.open(backup_file, 'r:gz') as tar:
                names = tar.getnames()
                self.assertIn('manifest.json', names)
                self.assertIn('db_dump.json', names)

            # Test restore
            call_command('restore_dms', backup_file)

    def test_19_catalog_author_filter_and_modal(self):
        """Research catalog supports author dropdown filtering and renders dossier cover modal."""
        # Alice's paper
        paper_alice = Paper.objects.create(
            title="Alice Cardiology Thesis",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Study on heart failure",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        PaperRound.objects.create(paper=paper_alice, round_number=1, pdf_file=self.dummy_pdf)

        # Bob's paper
        paper_bob = Paper.objects.create(
            title="Bob Surgical Review",
            author=self.bob,
            department="Surgery",
            category="Surgery",
            abstract="Study on robotics",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        PaperRound.objects.create(paper=paper_bob, round_number=1, pdf_file=self.dummy_pdf)

        # Filter by Alice
        res = self.client.get(reverse('catalog_view') + f'?author={self.alice.id}')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn("Alice Cardiology Thesis", content)
        self.assertNotIn("Bob Surgical Review", content)
        self.assertIn(f"dossierModal{paper_alice.id}", content)

    def test_20_contextual_nav_badges(self):
        """Context processor injects contextual metrics for coordinator triage and doctor action badges."""
        # Paper needing triage
        Paper.objects.create(
            title="Pending Triage Paper",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Needs review",
            current_status=PaperStatus.PENDING_COORD
        )

        # Paper needing revision
        Paper.objects.create(
            title="Needs Revision Paper",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Needs revision",
            current_status=PaperStatus.REVISION_REQUIRED
        )

        # Coordinator login checks triage badge
        self.client.login(username='charlie', password='password123')
        res_coord = self.client.get(reverse('coordinator_triage'))
        self.assertEqual(res_coord.status_code, 200)
        self.assertGreaterEqual(res_coord.context['pending_triage_count'], 1)

        # Alice login checks doctor action badge
        self.client.login(username='alice', password='password123')
        res_alice = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(res_alice.status_code, 200)
        self.assertGreaterEqual(res_alice.context['doctor_action_badge_total'], 1)

    def test_21_paper_pdf_viewer_route_and_watermark_context(self):
        """In-browser secure viewer enforces access permissions and renders PDF.js canvas with anti-tamper guards."""
        paper = Paper.objects.create(
            title="Secure Viewer Manuscript",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Viewer test",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now()
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)

        # Sarah (staff viewer) attempts viewing without pass -> 403 Forbidden
        self.client.login(username='sarah', password='password123')
        res_forbidden = self.client.get(reverse('paper_pdf_viewer', kwargs={'paper_id': paper.id}))
        self.assertEqual(res_forbidden.status_code, 403)

        # Grant access pass to Sarah
        AccessRequest.objects.create(
            paper=paper,
            requester=self.sarah,
            duration_days=7,
            status=AccessRequestStatus.APPROVED,
            expires_at=timezone.now() + timedelta(days=7)
        )

        # Sarah accesses secure viewer with active pass -> 200 OK
        res_viewer = self.client.get(reverse('paper_pdf_viewer', kwargs={'paper_id': paper.id}) + '?round=1')
        self.assertEqual(res_viewer.status_code, 200)
        content = res_viewer.content.decode('utf-8')
        self.assertIn("pdfCanvas", content)
        self.assertIn("pdf.min.js", content)
        self.assertIn("contextmenu", content)
        self.assertIn("Ctrl+S", content)
        self.assertIn("Sarah Jenkins", content)

    def test_22_audit_remediations_sec_suite(self):
        """Comprehensive verification of R&D audit security remediations (SEC-01 through SEC-15)."""
        from django.core.management import call_command
        from django.core.management.base import CommandError
        import tempfile
        import os

        # 1. SEC-01: Context processor gates demo personas when ENABLE_DEMO_MODE is False
        with self.settings(ENABLE_DEMO_MODE=False):
            res = self.client.get(reverse('login'))
            self.assertFalse(res.context['enable_demo_mode'])
            self.assertEqual(len(res.context['demo_users']), 0)
            self.assertNotIn("Demo Switcher", res.content.decode('utf-8'))
            self.assertNotIn("Pre-seeded Credentials", res.content.decode('utf-8'))

        with self.settings(ENABLE_DEMO_MODE=True):
            res = self.client.get(reverse('login'))
            self.assertTrue(res.context['enable_demo_mode'])
            self.assertGreater(len(res.context['demo_users']), 0)
            self.assertIn("Demo Switcher", res.content.decode('utf-8'))

        # 2. SEC-03: Double-blind reviewer masking in paper_pdf_viewer
        paper = Paper.objects.create(
            title="Blinded Review Manuscript",
            author=self.alice,
            department="Cardiology",
            category="Cardiology",
            abstract="Double-blind evaluation",
            current_status=PaperStatus.PENDING_ADVISOR
        )
        round1 = PaperRound.objects.create(paper=paper, round_number=1, pdf_file=self.dummy_pdf)
        ReviewAssignment.objects.create(round=round1, reviewer=self.bob)

        # Bob is assigned reviewer -> author masked
        self.client.login(username='bob', password='password123')
        res_bob = self.client.get(reverse('paper_pdf_viewer', kwargs={'paper_id': paper.id}))
        self.assertEqual(res_bob.status_code, 200)
        self.assertTrue(res_bob.context['is_blinded_reviewer'])
        content_bob = res_bob.content.decode('utf-8')
        self.assertIn("[Blinded for Peer Review]", content_bob)
        self.assertNotIn("Alice Mercer", content_bob)

        # Author Alice views own paper -> not blinded
        self.client.login(username='alice', password='password123')
        res_alice = self.client.get(reverse('paper_pdf_viewer', kwargs={'paper_id': paper.id}))
        self.assertEqual(res_alice.status_code, 200)
        self.assertFalse(res_alice.context['is_blinded_reviewer'])
        self.assertIn("Alice Mercer", res_alice.content.decode('utf-8'))

        # 3. SEC-06: Open redirect rejection in login_view and mark_all_notifications_read
        res_login_redirect = self.client.post(reverse('login') + '?next=https://evil.com', {
            'username': 'alice',
            'password': 'password123'
        })
        self.assertEqual(res_login_redirect.status_code, 302)
        self.assertNotEqual(res_login_redirect.url, 'https://evil.com')
        self.assertEqual(res_login_redirect.url, reverse('doctor_dashboard'))

        res_notif_redirect = self.client.get(
            reverse('mark_all_notifications_read'),
            HTTP_REFERER='https://evil.com/phishing'
        )
        self.assertEqual(res_notif_redirect.status_code, 302)
        self.assertNotEqual(res_notif_redirect.url, 'https://evil.com/phishing')
        self.assertEqual(res_notif_redirect.url, reverse('doctor_dashboard'))

        # 4. SEC-09: Password verification required to disable 2FA
        self.alice.is_totp_enabled = True
        self.alice.save()
        TOTPDevice.objects.create(user=self.alice, confirmed=True)

        # Failed attempt with incorrect password
        res_totp_fail = self.client.post(reverse('totp_setup'), {
            'action': 'disable',
            'password': 'wrongpassword'
        })
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_totp_enabled)

        # Successful attempt with correct password
        res_totp_ok = self.client.post(reverse('totp_setup'), {
            'action': 'disable',
            'password': 'password123'
        })
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_totp_enabled)

        # 5. SEC-13: N+1 query optimization using prefetched objects cache
        papers_qs = Paper.objects.prefetch_related('rounds').filter(id=paper.id)
        prefetched_paper = list(papers_qs)[0]
        self.assertTrue(hasattr(prefetched_paper, '_prefetched_objects_cache'))
        with self.assertNumQueries(0):
            lr = prefetched_paper.latest_round
            rc = prefetched_paper.round_count
            self.assertEqual(lr.round_number, 1)
            self.assertEqual(rc, 1)

        # 6. SEC-15: LOGIN_FAILURE audit action logged on bad credentials
        self.client.logout()
        initial_failures = AuditLog.objects.filter(action=AuditAction.LOGIN_FAILURE).count()
        self.client.post(reverse('login'), {'username': 'alice', 'password': 'bad_password'})
        new_failures = AuditLog.objects.filter(action=AuditAction.LOGIN_FAILURE).count()
        self.assertEqual(new_failures, initial_failures + 1)

        # 7. SEC-05: backup_dms detects unencrypted plaintext PDF and aborts
        with tempfile.TemporaryDirectory() as tmp_media:
            bad_pdf = os.path.join(tmp_media, 'leak.pdf')
            with open(bad_pdf, 'wb') as f:
                f.write(b"%PDF-1.4\nMalicious plaintext unencrypted file\n%%EOF")

            with self.settings(PROTECTED_MEDIA_ROOT=tmp_media):
                with tempfile.TemporaryDirectory() as tmp_out:
                    out_archive = os.path.join(tmp_out, 'test_fail.tar.gz')
                    with self.assertRaises(CommandError) as ctx:
                        call_command('backup_dms', output=out_archive)
                    self.assertIn("Security Violation", str(ctx.exception))




