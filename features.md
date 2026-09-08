# Product Specifications: MedResearch DMS (Enterprise Suite)

## 1. System Roles & Clinical Personas

### A. Unified Doctor Persona (Context-Dependent Role Model)
* **Design Philosophy:** In hospital environments, attending physicians and department chiefs do not exist in rigid, mutually exclusive "Author" or "Reviewer" silos. A doctor frequently authors groundbreaking research in their medical sub-specialty while simultaneously serving as an expert peer reviewer for colleagues.
* **Dr. Alice (Cardiologist - Role: `DOCTOR`):** Lead author of cardiology clinical trials; designated peer reviewer for surgical oncology manuscripts.
* **Dr. Bob (Surgical Specialist - Role: `DOCTOR`):** Lead author of surgical trials; designated peer reviewer for Dr. Alice's cardiology manuscripts.
* **Dynamic Role Context:** 
  - When viewing authored papers: Doctor acts as **Author** (submits manuscripts, views coordinator decision letters, submits Round $N+1$ revisions).
  - When reviewing peer papers: Doctor acts as **Peer Reviewer** (inspects blinded manuscripts in secure viewer, submits structured critiques).

### B. Research Coordinator (นาย C / Charlie - Role: `COORDINATOR`)
* Central triage officer, editorial manager, and double-blind air-gap mediator.
* Performs initial manuscript triage (approves for review or rejects).
* Dispatches reviewers with automated Conflict of Interest (COI) exclusion.
* Synthesizes multiple reviewer critiques into single authoritative revision directive letters (`CoordinatorLetter`).
* Authorizes immutable publication locks and executes post-publication retraction recalls.
* Reviews and grants temporary hospital full-text reading passes (7, 14, 30 days).

### C. Internal Clinician / Staff Viewer (Dr. Sarah - Role: `STAFF_VIEWER`)
* Hospital clinicians, clinical fellows, nurses, and residents browsing the institutional research catalog.
* Unrestricted access to manuscript titles, lead authors, departments, and clinical abstracts.
* Access Gate: Must submit a clinical justification request for time-bound reading access (7, 14, or 30 days) to inspect full-text PDFs.

### D. System Administrator (Admin - Role: `ADMIN`)
* Dedicated administrative operator enforcing strict separation of duties (IT security vs. clinical editorial workflow).
* Full user lifecycle management: provisions doctor profiles with medical departments and clinical sub-specialties.
* Security operations: executes 1-click 2FA resets for compromised or damaged clinician TOTP devices.
* Forensic analysis: inspects append-only security audit trail (`AuditLog`) with IP filtering and action timelines.

---

## 2. Core Clinical Workflows & Interfaces

### A. Unified Doctor Workspace (`/doctor/dashboard/`)
* **Two-Tab Clinical Layout:**
  1. **"My Researches" (งานวิจัยของฉัน):** Real-time tracking of authored manuscripts across lifecycle stages, current round counter ($N$), coordinator directives, and revision desks.
  2. **"Assigned Peer Reviews" (งานที่ได้รับมอบหมายให้ตรวจ):** Active review invitations, countdown deadlines, and direct triggers to the Split-Screen Review Desk.
* **Instant Client-Side Workspace Search:** Responsive live search input filtering table rows in real-time across titles, departments, and status categories as the physician types.
* **Clickable Table Rows (`tr[data-href]`):** Clinicians can click anywhere on a manuscript row to navigate directly to its detailed dossier, with event delegation protecting nested buttons and dropdown triggers.

### B. Coordinator Triage & Air-Gapped Consolidation Desk
* **Triage Inbox (`/coordinator/triage/`):** Central editorial board filtering manuscripts by stage (`PENDING_COORD`, `PENDING_ADVISOR`, `ADVISOR_COMMENTED`, `PUBLISHED`, `RETRACTED_FOR_REVISION`).
* **COI-Guarded Reviewer Assignment:** Multi-select dropdown surfacing available doctors by department and specialization, strictly excluding the manuscript's author.
* **Air-Gapped Consolidation Desk (`/coordinator/papers/<id>/consolidate/`):** Side-by-side synthesis interface displaying raw critiques from all assigned reviewers (เค้าโครง, บทนำ, บทขยาย) alongside an editorial drafting pane to generate unified directives.
* **Publication Lock:** Explicit editorial action freezing manuscripts into immutable `PUBLISHED` status and catalog archiving.

### C. Split-Screen Review Workspace (`/papers/<id>/review/`)
* **Left Pane (Confidential PDF Reader):** Embedded document viewer with page navigation, zoom, fit width, and diagonal anti-leak watermark.
* **Right Pane (Structured Clinical Critique Form):**
  - Structure & Methodology critique (เค้าโครง)
  - Introduction & Literature critique (บทนำ)
  - Results & Data critique (บทขยาย)
  - Review Decision selector (`Request Revisions` vs `Approve as Final`)
  - Optional annotated PDF attachment upload.

### D. Dedicated In-Browser Watermarked PDF Viewer (`/papers/<id>/viewer/?round=<N>`)
* Full-DOM Mozilla PDF.js canvas engine replacing raw browser PDF plugins.
* **Dynamic 2D Canvas Watermarking:** Stamps high-contrast diagonal watermark across every page buffer at -45°:
  `[User Full Name] ([Role]) • [Hospital Domain] • [Timestamp UTC] • [Client IP]`
* **Double-Blind Air-Gap Enforcement:** Assigned peer reviewers are identified via `is_blinded_reviewer`; the lead author's name is dynamically masked with `[Blinded for Peer Review]`, and the return link safely redirects to the Doctor Workspace instead of the author dossier.
* **Anti-Tamper Protections:** Context menu is completely disabled; hotkey listeners intercept `Ctrl+S`, `Ctrl+P`, `Cmd+S`, and `Cmd+P` with on-screen institutional security alerts.

### E. Research Catalog & Time-Bound Access Gate (`/catalog/`)
* Public and internal institutional repository of all published papers.
* **Quick Dossier Cover Modal (`#dossierModal{{ paper.id }}`):** Immediate modal preview displaying abstract, category, lead author, publication date, and reading pass action buttons.
* **Lead Author & Keyword Filtering:** Allows clinicians to filter publications by specific primary investigator or free-text clinical terms.
* **Access Request Ticket System:** Time-bound pass requests (7, 14, 30 days) requiring clinical justification, reviewed and granted by Coordinator C.

---

## 3. Enterprise Extension Modules

### Module 1: In-App Notification Engine
* Interactive top navigation bell icon with live unread counter badge and preview dropdown.
* Dispatches targeted events: review assignment, critique submission, revision directive, publication, retraction recall, and access ticket approval.
* Endpoints for individual (`/notifications/mark-read/<id>/`) and bulk mark-as-read (`/notifications/mark-all-read/`).

### Module 2: Dedicated IT Admin Portal (`/admin-portal/`)
* Complete separation from clinical review workflow: dedicated to user provisioning, role assignments, and security maintenance.
* Directory of clinical staff with real-time 2FA status, role, and active status filters.
* 1-click **"Reset 2FA"** recovery button unbinding lost or damaged TOTP devices.

### Module 3: Post-Publication Retraction & Revision Re-Entry
* FSM Transition: `PUBLISHED` $\rightarrow$ `RETRACTED_FOR_REVISION`.
* Coordinator modal requires clinical justification note.
* System effects: instant catalog de-listing, Access Gate lockdown (403 for readers), and author revision desk unlock for Round $N+1$ re-submission.

### Module 4: Executive Overview Analytics Dashboard (`/executive/dashboard/`)
* Executive KPI cards: Total Manuscripts, Publication Ratio, Active Peer Reviews, Average Turnaround Days, 2FA Adoption Rate.
* Chart.js visualizations safely rendered via Django `json_script` and `JSON.parse`:
  - Department Distribution (Doughnut Chart)
  - Governance Pipeline Funnel (Bar Chart)
  - Trailing 6-Month Submission Velocity (Line Chart)

### Module 5: Security Audit Trail (`AuditLog`)
* Append-only forensic log capturing user, action type, sanitized IP address, user agent, details, and timestamp.
* Distinct `LOGIN_FAILURE` action logging for failed authentication attempts.
* Filterable timeline viewer in IT Admin Portal.

### Module 6: Application-Level Cryptographic Storage & Disaster Recovery
* Files stored at rest as Fernet-encrypted ciphertext (`.enc`) with zero unencrypted `%PDF-` files on disk.
* `backup_dms` and `restore_dms` management commands utilizing SHA-256 manifest validation and plaintext leak detection.

---

## 💡 Lessons Learned from Demo / Prototype (สิ่งที่ได้เรียนรู้จากการทำ Demo)

### 1. Clinical Workflow Reality: Doctor Roles Must Be Context-Dependent Rather Than Static
* **Clinical Insight:** In early conceptual phases, the system contemplated separate user models or roles for "Author" and "Reviewer". Clinical feedback immediately invalidated this assumption: in real academic medical centers, every doctor is both a researcher producing papers and a subject-matter expert reviewing peer studies.
* **Engineering Solution:** Implemented the unified `DOCTOR` role model where capabilities are determined entirely by document context and relationship. Conflict of Interest guards (`exclude(id=paper.author_id)`) guarantee that a doctor can review any manuscript except their own, reflecting natural hospital committee dynamics.

### 2. Cognitive Load in Clinical Environments: Real-Time Badges & Clickable Rows Drastically Improve Operational Velocity
* **Clinical Insight:** Hospital doctors and triage coordinators operate under extreme time pressure and task switching. Having to click small text links ("View Dossier") or check multiple tabs to see if action is required caused missed deadlines during user acceptance testing.
* **UX Solution:**
  - Implemented **clickable table rows (`tr[data-href]`)** with event delegation: clinicians can tap or click anywhere on a row to open the document.
  - Implemented **contextual navbar counter badges**: the Doctor Workspace tab displays a red pill showing exactly how many items require clinician attention (revisions required + pending reviews). Coordinator triage and access pass queues display distinct amber and red alerts, eliminating the need to hunt for pending tasks.

### 3. Progressive Disclosure in Research Discovery: Why Quick Dossier Modals Enhance Reader Engagement
* **Clinical Insight:** In the research catalog, forcing staff viewers to navigate away to a separate page just to read an abstract or check authors created friction. Readers often browse 10–20 papers before finding the study relevant to their clinical case.
* **UX Solution:** Added **Quick Dossier Cover Modals (`#dossierModal{{ paper.id }}`)** directly on the catalog grid. Clinicians can preview full abstracts, author credentials, and submission dates instantly without reloading the page. If the full paper is desired, the Access Pass request form or direct secure viewer link is embedded right inside the modal.


