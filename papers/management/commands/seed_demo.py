import os
import io
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from accounts.models import User, UserRole, AuditLog, AuditAction
from papers.models import (
    Paper, PaperRound, ReviewAssignment, ReviewFeedback, CoordinatorLetter,
    AccessRequest, PaperStatus, ReviewDecision, CoordinatorDecision,
    AccessRequestStatus, Notification, NotificationType, notify_user
)


def generate_medical_pdf(title, author_name, department, round_num=1, status="Clinical Manuscript"):
    """Generates a valid, realistic multi-page medical research PDF document using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        'HospitalHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=0
    )
    title_style = ParagraphStyle(
        'PaperTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        alignment=0,
        spaceAfter=12
    )
    meta_style = ParagraphStyle(
        'PaperMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )

    story = []

    # Hospital Header Banner
    banner_data = [
        [
            Paragraph("<b>CENTRAL MEDICAL RESEARCH INSTITUTE</b><br/>Division of Clinical Investigation & Peer Review", header_style),
            Paragraph(f"<b>STATUS:</b> {status}<br/><b>ROUND:</b> {round_num} &bull; <b>SECURITY:</b> PROTECTED", header_style)
        ]
    ]
    banner_table = Table(banner_data, colWidths=[320, 180])
    banner_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.5, colors.HexColor('#1e40af')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 16))

    # Title & Metadata
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"Principal Investigator: <b>{author_name}</b> | Department of {department} | Date: {timezone.now().strftime('%B %Y')}", meta_style))
    story.append(Spacer(1, 10))

    # Abstract Box
    story.append(Paragraph("STRUCTURED CLINICAL ABSTRACT", h2_style))
    abstract_text = (
        "<b>Background:</b> Standard interventional guidelines require prospective clinical validation across diverse patient cohorts. "
        "This study evaluated clinical endpoints, adverse complication rates, and 12-month post-procedure functional status.<br/>"
        "<b>Methods:</b> In this multi-center prospective trial, eligible patients were randomized 1:1 to interventional therapy versus standard medical care. "
        "Primary endpoint was defined as composite freedom from major adverse cardiovascular/surgical events.<br/>"
        "<b>Results:</b> A total of 428 patients (mean age 64.2 ± 11.5 years) completed follow-up. The intervention group demonstrated a 34% risk reduction "
        "(HR 0.66, 95% CI 0.49-0.89, p=0.007). In-hospital mortality was 1.4% vs 3.1% in the control cohort.<br/>"
        "<b>Conclusions:</b> Interventional protocol demonstrates statistically significant clinical superiority with an acceptable adverse safety profile."
    )
    abstract_table = Table([[Paragraph(abstract_text, body_style)]], colWidths=[500])
    abstract_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(abstract_table)
    story.append(Spacer(1, 14))

    # Section 1: Introduction & Literature
    story.append(Paragraph("1. Introduction & Clinical Rationale", h2_style))
    story.append(Paragraph(
        "Acute and chronic pathophysiological manifestations present ongoing therapeutic challenges. "
        "While conventional pharmacotherapy and standard procedural pathways provide moderate symptomatic relief, long-term prognostic "
        "indicators remain suboptimal. Recent retrospective analyses suggested improved hemodynamic parameters under modified operative guidelines; "
        "however, robust prospective randomized data remain scarce in tertiary hospital environments.",
        body_style
    ))

    # Section 2: Study Design & Patient Demographics Table
    story.append(Paragraph("2. Methodology & Cohort Characteristics", h2_style))
    table_data = [
        ["Baseline Characteristic", "Intervention Cohort (n=214)", "Control Cohort (n=214)", "p-value"],
        ["Age, mean (SD)", "64.1 (10.8)", "64.4 (11.2)", "0.78"],
        ["Female sex, n (%)", "92 (43.0%)", "89 (41.6%)", "0.84"],
        ["Hypertension, n (%)", "168 (78.5%)", "172 (80.4%)", "0.68"],
        ["Prior MI / Intervention", "45 (21.0%)", "48 (22.4%)", "0.74"],
        ["Primary Endpoint Freedom", "182 (85.0%)", "154 (72.0%)", "0.007*"]
    ]
    t = Table(table_data, colWidths=[180, 120, 120, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Section 3: Discussion & Limitations
    story.append(Paragraph("3. Clinical Discussion & Limitations", h2_style))
    story.append(Paragraph(
        "The primary findings demonstrate marked improvement in patient functional outcomes with reduced length of stay. "
        "Limitations include single-institution tertiary bias and 12-month observational duration. Continued multicenter surveillance "
        "is recommended to assess 36-month survival metrics.",
        body_style
    ))

    # Footer note
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>Confidential Document - For MedResearch Institutional Review and Clinical Governance Only. Unlawful reproduction is prohibited.</i>",
        meta_style
    ))

    doc.build(story)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Seeds high-fidelity realistic demo data across all clinical workflow stages with valid PDFs."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("--- Starting MedResearch DMS Demo Seeding ---"))

        # 1. Clear existing domain data (clean rebuild)
        AccessRequest.objects.all().delete()
        CoordinatorLetter.objects.all().delete()
        ReviewFeedback.objects.all().delete()
        ReviewAssignment.objects.all().delete()
        PaperRound.objects.all().delete()
        Paper.objects.all().delete()

        # 2. Seed Personas
        self.stdout.write("Creating clinical demo personas...")

        alice, _ = User.objects.update_or_create(
            username='alice',
            defaults={
                'first_name': 'Alice',
                'last_name': 'Mercer',
                'email': 'alice.mercer@hospital.internal',
                'role': UserRole.DOCTOR,
                'department': 'Cardiology',
                'specialization': 'Interventional Cardiology',
                'is_staff': False,
            }
        )
        alice.set_password('password123')
        alice.save()

        bob, _ = User.objects.update_or_create(
            username='bob',
            defaults={
                'first_name': 'Robert',
                'last_name': 'Chen',
                'email': 'bob.chen@hospital.internal',
                'role': UserRole.DOCTOR,
                'department': 'Surgery',
                'specialization': 'Oncologic Surgery',
                'is_staff': False,
            }
        )
        bob.set_password('password123')
        bob.save()

        charlie, _ = User.objects.update_or_create(
            username='charlie',
            defaults={
                'first_name': 'Charlie',
                'last_name': 'Vance',
                'email': 'charlie.vance@hospital.internal',
                'role': UserRole.COORDINATOR,
                'department': 'Research Administration',
                'specialization': 'Clinical Governance & Triage',
                'is_staff': True,
            }
        )
        charlie.set_password('password123')
        charlie.save()

        sarah, _ = User.objects.update_or_create(
            username='sarah',
            defaults={
                'first_name': 'Sarah',
                'last_name': 'Jenkins',
                'email': 'sarah.jenkins@hospital.internal',
                'role': UserRole.STAFF_VIEWER,
                'department': 'Emergency Medicine',
                'specialization': 'Clinical Fellow',
                'is_staff': False,
            }
        )
        sarah.set_password('password123')
        sarah.save()

        admin, _ = User.objects.update_or_create(
            username='admin',
            defaults={
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@hospital.internal',
                'role': UserRole.ADMIN,
                'department': 'IT Operations',
                'specialization': 'System Oversight',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin.set_password('password123')
        admin.save()

        self.stdout.write(self.style.SUCCESS("Demo personas created: Alice, Bob, Charlie, Sarah, Admin."))

        # 3. Seed Papers across all states
        self.stdout.write("Seeding 5 realistic clinical papers with ReportLab PDFs...")

        # Paper 1: PENDING_COORD (Alice author, Round 1 submitted)
        p1 = Paper.objects.create(
            title="Randomized Evaluation of SGLT2 Inhibition in Acute Decompensated Heart Failure",
            author=alice,
            department="Cardiology",
            category="Cardiology / Clinical Trial",
            co_authors="Dr. Marcus Thorne, MD; Dr. Emily Hayes, PhD",
            abstract="Evaluates early initiation of sodium-glucose cotransporter 2 inhibitors in stabilized patients hospitalized for acute heart failure, measuring decongestion efficacy, NT-proBNP trajectory, and 90-day rehospitalization rates.",
            current_status=PaperStatus.PENDING_COORD
        )
        pdf1 = generate_medical_pdf(p1.title, "Dr. Alice Mercer, MD", "Cardiology", round_num=1, status="Pending Triage")
        PaperRound.objects.create(
            paper=p1,
            round_number=1,
            pdf_file=ContentFile(pdf1, name="sglt2_heart_failure_r1.pdf"),
            summary_notes="Initial Phase 3 multi-center trial manuscript submitted for institutional coordinator review."
        )

        # Paper 2: PENDING_ADVISOR (Bob author, Alice assigned as peer-reviewer)
        # Enforces COI Guard: Bob is author, Alice (Doctor) is assigned reviewer
        p2 = Paper.objects.create(
            title="Laparoscopic vs Robotic-Assisted Hepatectomy for Colorectal Liver Metastases",
            author=bob,
            department="Surgery",
            category="Surgical Oncology",
            co_authors="Dr. Henry Lin, FACS; Dr. Samantha Wu, MD",
            abstract="A prospective comparative cohort study examining intraoperative blood loss, R0 resection margins, conversion rates, and 3-year disease-free survival in minimally invasive liver resections.",
            current_status=PaperStatus.PENDING_ADVISOR
        )
        pdf2 = generate_medical_pdf(p2.title, "Dr. Robert Chen, MD", "Surgery", round_num=1, status="Under Peer Review")
        r2 = PaperRound.objects.create(
            paper=p2,
            round_number=1,
            pdf_file=ContentFile(pdf2, name="robotic_hepatectomy_r1.pdf"),
            summary_notes="Comparative surgical cohort data completed; ready for peer critique."
        )
        ReviewAssignment.objects.create(
            round=r2,
            reviewer=alice,  # Alice reviews Bob's paper
            is_completed=False,
            deadline=timezone.now() + timedelta(days=14)
        )

        # Paper 3: ADVISOR_COMMENTED (Alice author, Bob completed review critique)
        p3 = Paper.objects.create(
            title="Percutaneous Coronary Intervention in Bifurcation Lesions: A Multi-Center Registry",
            author=alice,
            department="Cardiology",
            category="Interventional Cardiology",
            co_authors="Dr. Alan Vance, MD; Dr. Claire Dubois, MD",
            abstract="Investigates long-term target lesion revascularization and stent thrombosis rates comparing provisional single-stent versus routine dual-stent culotte techniques in complex coronary bifurcation disease.",
            current_status=PaperStatus.ADVISOR_COMMENTED
        )
        pdf3 = generate_medical_pdf(p3.title, "Dr. Alice Mercer, MD", "Cardiology", round_num=1, status="Critique Submitted")
        r3 = PaperRound.objects.create(
            paper=p3,
            round_number=1,
            pdf_file=ContentFile(pdf3, name="bifurcation_pci_r1.pdf"),
            summary_notes="Registry cohort data with 24-month angiographic follow-up."
        )
        assignment3 = ReviewAssignment.objects.create(
            round=r3,
            reviewer=bob,  # Bob reviews Alice's paper
            is_completed=True,
            deadline=timezone.now() + timedelta(days=7)
        )
        ReviewFeedback.objects.create(
            assignment=assignment3,
            structure_comment="The prospective multi-center registry design is robust, with clear propensity score matching. However, the angiographic core lab blinding protocol should be articulated more explicitly in Section 2.2.",
            intro_comment="Literature review comprehensively covers EBC recommendations; suggests referencing the recent 2025 DEFINITION II trial updates regarding Medina 1,1,1 bifurcation criteria.",
            expansion_comment="Kaplan-Meier curves demonstrate convincing separation at 12 months. Recommend providing a supplementary subgroup analysis on diabetic patients with Medina 1,1,1 side-branch involvement.",
            decision=ReviewDecision.REVISION_NEEDED
        )

        # Paper 4: REVISION_REQUIRED (Bob author, Alice reviewed, Charlie dispatched Letter)
        p4 = Paper.objects.create(
            title="Fluorescence-Guided Surgery Using Indocyanine Green in Gastrointestinal Malignancies",
            author=bob,
            department="Surgery",
            category="Surgical Oncology",
            co_authors="Dr. Diana Prince, MD; Dr. Arthur Curry, MD",
            abstract="Explores real-time intraoperative near-infrared fluorescence imaging with ICG for lymphatic mapping, sentinel node biopsy, and anastomotic perfusion assessment in gastrointestinal oncology.",
            current_status=PaperStatus.REVISION_REQUIRED
        )
        pdf4 = generate_medical_pdf(p4.title, "Dr. Robert Chen, MD", "Surgery", round_num=1, status="Revision Required")
        r4 = PaperRound.objects.create(
            paper=p4,
            round_number=1,
            pdf_file=ContentFile(pdf4, name="fluorescence_icg_r1.pdf"),
            summary_notes="Initial submission on intraoperative perfusion assessment."
        )
        assignment4 = ReviewAssignment.objects.create(
            round=r4,
            reviewer=alice,
            is_completed=True,
            deadline=timezone.now() - timedelta(days=2)
        )
        ReviewFeedback.objects.create(
            assignment=assignment4,
            structure_comment="Surgical protocol is well described. Quantification of fluorescence intensity needs standardized calibration across different laparoscope camera platforms.",
            intro_comment="Strong clinical background. Emphasize how false negative sentinel node rates compare with conventional radiocolloid techniques.",
            expansion_comment="Anastomotic leak reduction is promising (2.1% vs 6.8%). Expand on pharmacokinetics and dosing timing relative to incision.",
            decision=ReviewDecision.REVISION_NEEDED
        )
        CoordinatorLetter.objects.create(
            round=r4,
            coordinator=charlie,
            consolidated_comment=(
                "REVISION DIRECTIVES (Round 1):\n\n"
                "1. Calibration Protocol: Provide detailed operating-room calibration procedures for near-infrared fluorescence cameras in Section 2.\n"
                "2. Comparative Sensitivity: Contrast your false-negative lymphatic mapping rates directly against Tc-99m radiocolloid benchmarks in the Discussion.\n"
                "3. Timing & Dosing: Add a standardized timeline chart detailing exact ICG bolus timing relative to mucosal transection.\n\n"
                "Please upload a comprehensive Round 2 manuscript along with your itemized response to these directives."
            ),
            decision=CoordinatorDecision.REVISION_REQUIRED
        )

        # Paper 5: PUBLISHED (Alice author, Multi-round complete, published in catalog)
        p5 = Paper.objects.create(
            title="Long-term Neurological Outcomes Following Endovascular Thrombectomy in Acute Ischemic Stroke",
            author=alice,
            department="Cardiology",
            category="Neuro-Cardiology / Interventional",
            co_authors="Dr. Sarah Jenkins, MD; Dr. Bruce Wayne, MD",
            abstract="A 5-year longitudinal clinical trial evaluating modified Rankin Scale (mRS 0-2) functional independence, symptomatic intracranial hemorrhage, and survival after mechanical thrombectomy with modern aspiration vs stent-retriever devices.",
            current_status=PaperStatus.PUBLISHED,
            published_at=timezone.now() - timedelta(days=30)
        )
        # Round 1
        pdf5_r1 = generate_medical_pdf(p5.title, "Dr. Alice Mercer, MD", "Cardiology", round_num=1, status="Revision Historical")
        r5_1 = PaperRound.objects.create(
            paper=p5,
            round_number=1,
            pdf_file=ContentFile(pdf5_r1, name="thrombectomy_stroke_r1.pdf"),
            summary_notes="Initial prospective 5-year cohort trial results."
        )
        a5_1 = ReviewAssignment.objects.create(round=r5_1, reviewer=bob, is_completed=True)
        ReviewFeedback.objects.create(
            assignment=a5_1,
            structure_comment="Cohort follow-up is exceptional. Clarify core infarct volume criteria (ASPECTS score cutoffs).",
            intro_comment="Well written introduction citing EXTEND-IA and DEFUSE 3.",
            expansion_comment="Statistical models are robust. Recommend clarifying subgroup results beyond the 6-hour extended window.",
            decision=ReviewDecision.REVISION_NEEDED
        )
        CoordinatorLetter.objects.create(
            round=r5_1,
            coordinator=charlie,
            consolidated_comment="Please address reviewer recommendations by specifying ASPECTS volume thresholds and extended window subgroup data.",
            decision=CoordinatorDecision.REVISION_REQUIRED
        )

        # Round 2 (Approved & Published)
        pdf5_r2 = generate_medical_pdf(p5.title, "Dr. Alice Mercer, MD", "Cardiology", round_num=2, status="Published Final Full Text")
        r5_2 = PaperRound.objects.create(
            paper=p5,
            round_number=2,
            pdf_file=ContentFile(pdf5_r2, name="thrombectomy_stroke_r2_final.pdf"),
            summary_notes="Round 2 revision incorporating expanded ASPECTS subgroup analyses and extended window protocol details."
        )
        a5_2 = ReviewAssignment.objects.create(round=r5_2, reviewer=bob, is_completed=True)
        ReviewFeedback.objects.create(
            assignment=a5_2,
            structure_comment="All methodological and subgroup clarifications have been rigorously addressed. Outstanding revision.",
            intro_comment="Flawless integration of 2025 neuro-interventional literature.",
            expansion_comment="Results convincingly prove superior long-term functional independence without increased hemorrhagic transformation.",
            decision=ReviewDecision.APPROVED
        )
        CoordinatorLetter.objects.create(
            round=r5_2,
            coordinator=charlie,
            consolidated_comment="All peer criteria satisfied. Approved for institutional research publication and inclusion in hospital catalog.",
            decision=CoordinatorDecision.APPROVED
        )

        # Access Requests for Paper 5
        # 1. Pending Request from Dr. Sarah (STAFF_VIEWER) - for interactive testing
        AccessRequest.objects.create(
            paper=p5,
            requester=sarah,
            duration_days=14,
            reason="Emergency Department acute stroke protocol revision: reviewing mechanical thrombectomy triage criteria for acute ischemic stroke transfers.",
            status=AccessRequestStatus.PENDING
        )

        # 2. Approved Active Pass for Bob (DOCTOR) - demonstrates active pass
        AccessRequest.objects.create(
            paper=p5,
            requester=bob,
            duration_days=30,
            reason="Collaborative neurosurgical study on vascular access complications.",
            status=AccessRequestStatus.APPROVED,
            expires_at=timezone.now() + timedelta(days=25),
            reviewed_by=charlie,
            reviewed_at=timezone.now() - timedelta(days=5),
            coordinator_notes="Approved for collaborative clinical review."
        )

        # ----------------------------------------------------
        # Paper 6: Recalled / Retracted Manuscript (Post-Publication Retraction Test)
        # ----------------------------------------------------
        p6 = Paper.objects.create(
            title="Longitudinal Efficacy of Monoclonal Anti-CGRP Antibodies in Chronic Migraine: 3-Year Observational Outcomes",
            author=bob,
            category="Neurology",
            department="Neurology",
            co_authors="Dr. Robert Chen, MD, Dr. Alice Mercer, MD",
            abstract="A 3-year prospective observational study assessing the efficacy and safety of quarterly anti-CGRP monoclonal antibodies in refractory chronic migraine. Follow-up includes monthly headache day reduction and adverse reaction surveillance.",
            current_status=PaperStatus.RETRACTED_FOR_REVISION,
            retraction_reason="Post-publication clinical audit: Statistical discrepancy identified in Table 3 patient washout period data. Formal re-verification with neurology clinical trial database required.",
            published_at=timezone.now() - timedelta(days=60)
        )
        pdf6_r1 = generate_medical_pdf(p6.title, "Dr. Robert Chen, MD", "Neurology", round_num=1, status="Recalled for Revision")
        r6_1 = PaperRound.objects.create(
            paper=p6,
            round_number=1,
            pdf_file=ContentFile(pdf6_r1, name="cgrp_migraine_r1.pdf"),
            summary_notes="Initial publication cohort data."
        )

        # ----------------------------------------------------
        # Seed Notifications (Module 1)
        # ----------------------------------------------------
        Notification.objects.all().delete()

        # Alice: Revision directive, access pass approval
        Notification.objects.create(
            recipient=alice,
            actor=charlie,
            paper=p1,
            notification_type=NotificationType.DIRECTIVE_ISSUED,
            message="Coordinator Decision issued for 'Cardiovascular Safety': Minor revision required.",
            target_url=f"/papers/{p1.id}/",
            is_read=False
        )
        Notification.objects.create(
            recipient=alice,
            actor=charlie,
            paper=p5,
            notification_type=NotificationType.ACCESS_GRANTED,
            message="Your research 'Long-Term Outcomes of Mechanical Thrombectomy' was approved for hospital-wide catalog publication.",
            target_url=f"/papers/{p5.id}/",
            is_read=True
        )

        # Bob: Review assignment and retraction alert
        Notification.objects.create(
            recipient=bob,
            actor=charlie,
            paper=p1,
            notification_type=NotificationType.PAPER_ASSIGNED,
            message="You have been assigned to peer review 'Cardiovascular Safety of GLP-1 Receptor Agonists'.",
            target_url=f"/papers/{p1.id}/review/",
            is_read=False
        )
        Notification.objects.create(
            recipient=bob,
            actor=charlie,
            paper=p6,
            notification_type=NotificationType.PAPER_RETRACTED,
            message="ALERT: Manuscript 'Longitudinal Efficacy of Monoclonal Anti-CGRP Antibodies' has been recalled for revision.",
            target_url=f"/papers/{p6.id}/",
            is_read=False
        )

        # Sarah: Access pass update
        Notification.objects.create(
            recipient=sarah,
            actor=charlie,
            paper=p5,
            notification_type=NotificationType.SYSTEM,
            message="Your access request for 'Long-Term Outcomes of Mechanical Thrombectomy' is currently under coordinator review.",
            target_url="/catalog/",
            is_read=False
        )

        # Charlie: New submission triage
        Notification.objects.create(
            recipient=charlie,
            actor=alice,
            paper=p2,
            notification_type=NotificationType.SYSTEM,
            message="New manuscript 'AI-Assisted Triaging in Emergency Acute Stroke' submitted by Dr. Alice Mercer.",
            target_url="/coordinator/triage/",
            is_read=False
        )

        # ----------------------------------------------------
        # Seed Security Audit Logs (Module 5)
        # ----------------------------------------------------
        AuditLog.objects.all().delete()

        now = timezone.now()
        demo_logs = [
            (alice, AuditAction.LOGIN_SUCCESS, "127.0.0.1", "Standard password authentication verified for Dr. Alice Mercer", now - timedelta(hours=24)),
            (alice, AuditAction.LOGIN_2FA, "127.0.0.1", "Enrolled TOTP authenticator device with verified token", now - timedelta(hours=23)),
            (bob, AuditAction.LOGIN_SUCCESS, "192.168.1.105", "Standard authentication success for Dr. Robert Chen", now - timedelta(hours=18)),
            (charlie, AuditAction.LOGIN_SUCCESS, "192.168.1.101", "Coordinator session established for Charlie Davis", now - timedelta(hours=12)),
            (charlie, AuditAction.ASSIGN_REVIEWER, "192.168.1.101", f"Assigned Dr. Robert Chen as peer reviewer for '{p1.title}'", now - timedelta(hours=10)),
            (bob, AuditAction.STREAM_PDF, "192.168.1.105", f"Streamed protected PDF for '{p1.title}' (Round 1) under Peer Reviewer Assignment", now - timedelta(hours=8)),
            (charlie, AuditAction.RETRACT_PAPER, "192.168.1.101", f"Recalled manuscript '{p6.title}' for author revision. Reason: Statistical discrepancy in Table 3.", now - timedelta(hours=5)),
            (bob, AuditAction.GRANT_ACCESS, "192.168.1.101", f"Approved 30-day access pass for Dr. Robert Chen on '{p5.title}'", now - timedelta(hours=4)),
            (bob, AuditAction.STREAM_PDF, "192.168.1.105", f"Streamed protected PDF for '{p5.title}' (Round 2) under Approved Time-Bound Access Pass", now - timedelta(hours=3)),
            (admin, AuditAction.USER_CREATE, "127.0.0.1", "Registered new clinician user 'jdoe' (Cardiology)", now - timedelta(hours=2)),
            (admin, AuditAction.RESET_2FA, "127.0.0.1", "Emergency reset of 2FA authenticator for user 'temp_clinician'", now - timedelta(minutes=45)),
        ]

        for user_obj, action, ip, details, ts in demo_logs:
            AuditLog.objects.create(
                user=user_obj,
                action=action,
                ip_address=ip,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                details=details,
                timestamp=ts
            )

        self.stdout.write(self.style.SUCCESS("Demo seeding completed successfully!"))
        self.stdout.write(self.style.SUCCESS("All 6 papers, multi-round histories, notifications, and security audit logs generated."))

