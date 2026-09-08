# System Architecture & Database Map (MedResearch DMS Enterprise Suite)

## 1. Entity Relationship (ER) Schema

### `accounts_user`
- `id`: BigInt (PK)
- `username`: String (Unique)
- `first_name`, `last_name`, `email`: Standard Django auth fields
- `role`: Enum (`DOCTOR`, `COORDINATOR`, `STAFF_VIEWER`, `ADMIN`), **`db_index=True`**
- `department`: String (e.g., "Cardiology", "Surgery", "Emergency Medicine")
- `specialization`: String (e.g., "Interventional Cardiology", "Oncologic Surgery", "Clinical Fellow")
- `is_totp_enabled`: Boolean (default: False)

### `accounts_auditlog` (Append-Only)
- `id`: BigInt (PK)
- `user_id`: FK -> `accounts_user.id` (Nullable, on_delete=SET_NULL)
- `action`: Enum (`LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGIN_2FA`, `LOGOUT`, `STREAM_PDF`, `SUBMIT_PAPER`, `ASSIGN_REVIEWER`, `SUBMIT_REVIEW`, `DISPATCH_LETTER`, `PUBLISH_PAPER`, `RETRACT_PAPER`, `REQUEST_ACCESS`, `GRANT_ACCESS`, `DENY_ACCESS`, `RESET_2FA`, `USER_CREATE`, `USER_UPDATE`, `USER_TOGGLE_ACTIVE`)
- `ip_address`: GenericIPAddressField (Validated via `ipaddress.ip_address()`)
- `user_agent`: String(255)
- `details`: Text (Structured metadata, paper ID, reasons)
- `timestamp`: DateTime (auto_now_add=True, default ordering: `['-timestamp']`)
- *Constraint: Append-only table. No update or delete operations allowed.*

### `accounts_totpdevice` (`django_otp.plugins.otp_totp.models.TOTPDevice`)
- `id`: BigInt (PK)
- `user_id`: FK -> `accounts_user.id` (related_name: `totpdevice_set`)
- `name`: String(64, default: 'default')
- `confirmed`: Boolean (default: False, flipped to True upon verification)
- `key`: Hex/Base32 RFC 6238 Secret Key
- `step`: PositiveInteger (default: 30 seconds)
- `t0`: BigInteger (default: 0)
- `digits`: PositiveInteger (default: 6)
- `tolerance`: PositiveInteger (default: 1)
- `created_at`: DateTime (auto_now_add=True)
- `last_used_at`: DateTime (Nullable)

### `papers_paper`
- `id`: UUID (PK, default: `uuid.uuid4`, editable=False)
- `title`: String(255)
- `abstract`: Text
- `category`: String(100)
- `department`: String(100)
- `co_authors`: String(255, blank)
- `author_id`: FK -> `accounts_user.id` (related_name: `authored_papers`)
- `current_status`: Enum (`DRAFT`, `PENDING_COORD`, `REJECTED_INITIAL`, `PENDING_ADVISOR`, `ADVISOR_COMMENTED`, `REVISION_REQUIRED`, `ADVISOR_APPROVED`, `PUBLISHED`, `RETRACTED_FOR_REVISION`), **`db_index=True`**
- `retraction_reason`: Text (Clinical justification for recall)
- `created_at`: DateTime (auto_now_add=True)
- `published_at`: DateTime (Nullable)

### `papers_paperround`
- `id`: BigInt (PK)
- `paper_id`: FK -> `papers_paper.id` (related_name: `rounds`)
- `round_number`: Integer (1, 2, 3...)
- `pdf_file`: FileField (Storage: `EncryptedFileSystemStorage` saving to `protected_media/secure_papers/%Y/%m/<uuid>_<name>.enc`)
- `summary_notes`: Text (Author's round submission notes)
- `submitted_at`: DateTime (auto_now_add=True)
- *Constraint: Unique together `(paper_id, round_number)`*

### `papers_reviewassignment`
- `id`: BigInt (PK)
- `round_id`: FK -> `papers_paperround.id` (related_name: `assignments`)
- `reviewer_id`: FK -> `accounts_user.id` (Must NOT equal `paper.author_id`)
- `is_completed`: Boolean (default: False)
- `assigned_at`: DateTime (auto_now_add=True)
- `deadline`: DateTime (Nullable)
- *Constraint: Unique together `(round_id, reviewer_id)`*

### `papers_reviewfeedback`
- `id`: BigInt (PK)
- `assignment_id`: OneToOne -> `papers_reviewassignment.id` (related_name: `feedback`)
- `structure_comment`: Text (เค้าโครง - Structure & Methodology)
- `intro_comment`: Text (บทนำ - Introduction & Literature)
- `expansion_comment`: Text (บทขยาย - Results & Discussion)
- `decision`: Enum (`REVISION_NEEDED`, `APPROVED`)
- `annotated_pdf`: FileField (Storage: `EncryptedFileSystemStorage` saving to `protected_media/annotated_reviews/%Y/%m/<uuid>_<name>.enc`, Nullable)
- `submitted_at`: DateTime (auto_now_add=True)

### `papers_coordinatorletter`
- `id`: BigInt (PK)
- `round_id`: OneToOne -> `papers_paperround.id` (related_name: `coordinator_letter`)
- `coordinator_id`: FK -> `accounts_user.id` (related_name: `sent_letters`)
- `consolidated_comment`: Text (Air-gapped synthesis directive)
- `decision`: Enum (`REVISION_REQUIRED`, `APPROVED`)
- `sent_at`: DateTime (auto_now_add=True)

### `papers_accessrequest`
- `id`: BigInt (PK)
- `paper_id`: FK -> `papers_paper.id` (related_name: `access_requests`)
- `requester_id`: FK -> `accounts_user.id` (related_name: `paper_access_requests`)
- `reason`: Text (Clinical justification)
- `duration_days`: Integer (Choices: 7, 14, 30 days)
- `status`: Enum (`PENDING`, `APPROVED`, `REJECTED`), **`db_index=True`**
- `expires_at`: DateTime (Nullable), **`db_index=True`**
- `reviewed_by_id`: FK -> `accounts_user.id` (Nullable, Coordinator)
- `reviewed_at`: DateTime (Nullable)
- `coordinator_notes`: Text (blank)
- `created_at`: DateTime (auto_now_add=True)

### `papers_notification`
- `id`: BigInt (PK)
- `recipient_id`: FK -> `accounts_user.id` (related_name: `notifications`)
- `actor_id`: FK -> `accounts_user.id` (Nullable, related_name: `triggered_notifications`)
- `paper_id`: FK -> `papers_paper.id` (Nullable, related_name: `notifications`)
- `notification_type`: Enum (`PAPER_ASSIGNED`, `REVIEW_SUBMITTED`, `DIRECTIVE_ISSUED`, `PAPER_RETRACTED`, `ACCESS_GRANTED`, `REVISION_SUBMITTED`, `SYSTEM`)
- `message`: String(255)
- `target_url`: String(255)
- `is_read`: Boolean (default: False), **`db_index=True`**
- `created_at`: DateTime (auto_now_add=True)

---

## 2. Double-Blind Air-Gap Mediation Topology

```
[Doctor Author A]                       [Coordinator C]                      [Doctor Reviewer B]
      │                                       │                                       │
      │ 1. Submits Paper (Title, PDF)         │                                       │
      ├──────────────────────────────────────►│                                       │
      │                                       │ 2. Triage & COI Exclusion Check       │
      │                                       │    (Exclude Author A from candidates) │
      │                                       │ 3. Dispatches Assignment              │
      │                                       ├──────────────────────────────────────►│
      │                                       │                                       │ 4. Opens Blinded PDF Viewer
      │                                       │                                       │    (Author A masked as [Blinded])
      │                                       │ 5. Submits Structured Critique        │
      │                                       │    (เค้าโครง, บทนำ, บทขยาย)            │
      │                                       │◄──────────────────────────────────────┤
      │                                       │                                       │
      │                                       │ 6. Consolidation Desk:                │
      │                                       │    Synthesizes multiple reviews       │
      │ 7. Receives CoordinatorLetter only    │    into single directive letter       │
      │    (Zero reviewer identity/raw text)  │                                       │
      │◄──────────────────────────────────────┤                                       │
```

---

## 3. Finite State Machine (FSM) Matrix (With Retraction Expansion)

| Current State | Trigger Action | Authorized Actor | Next State | Effects |
|---|---|---|---|---|
| `DRAFT` | Submit manuscript | Doctor (Author) | `PENDING_COORD` | Manuscript enters Coordinator triage inbox |
| `PENDING_COORD` | Reject initial | Coordinator C | `REJECTED_INITIAL` | Submission rejected with editorial note |
| `PENDING_COORD` | Assign reviewer(s) | Coordinator C | `PENDING_ADVISOR` | Invitations dispatched to 1–3 reviewers (COI checked) |
| `PENDING_ADVISOR` | Submit critique | Doctor (Reviewer) | `ADVISOR_COMMENTED` | Flipped when all assigned reviewers complete critique |
| `ADVISOR_COMMENTED` | Dispatch revision letter | Coordinator C | `REVISION_REQUIRED` | Synthesized directive sent; Author revision desk unlocked |
| `REVISION_REQUIRED` | Submit Round $N+1$ | Doctor (Author) | `PENDING_COORD` | Re-enters triage queue as new round revision |
| `ADVISOR_COMMENTED` / `ADVISOR_APPROVED` | Final publish lock | Coordinator C | `PUBLISHED` | Published date recorded, catalog listing published |
| `PUBLISHED` | Recall for Revision | Coordinator C | `RETRACTED_FOR_REVISION` | Catalog de-listed, access gate revoked, author notified |
| `RETRACTED_FOR_REVISION` | Submit Round $N+1$ Revision | Doctor (Author) | `PENDING_COORD` | Re-enters triage queue with historical context |

---

## 4. Zero Plaintext Storage & Cryptographic Streaming Pipeline

```
[Clinician PDF Upload] 
       │
       ▼
[EncryptedFileSystemStorage._save]
       │
       ├─► Read raw bytes from upload memory
       ├─► Fernet.encrypt(raw_bytes)  <-- AES-128-CBC + HMAC-SHA256
       ├─► Save unique file: <uuid>_<name>.enc
       ▼
[Disk Storage: protected_media/ (Zero Plaintext %PDF- on disk)]
       │
       ▼
[serve_protected_paper / paper_pdf_viewer]
       │
       ├─► Authenticate user & check Access Gate permissions
       ├─► Read <uuid>.enc ciphertext from disk
       ├─► Fernet.decrypt(ciphertext)
       ├─► Wrap plaintext bytes inside in-memory io.BytesIO buffer
       ▼
[Client Response -> Mozilla PDF.js Canvas Engine]
       │
       ├─► Draw PDF page into HTML5 <canvas id="pdfCanvas">
       ├─► Draw dynamic 2D diagonal watermark over canvas buffer (-45°)
       └─► Disable right-click & intercept Ctrl+S / Ctrl+P hotkeys
```

---

## 5. Disaster Recovery & Manifest Verification Topology

```
[backup_dms Management Command]
       │
       ├─► 1. Dumps DB tables (accounts, papers) to db_dump.json
       ├─► 2. Scans protected_media/ for all encrypted .enc files
       │      (Verifies first 16 bytes; raises CommandError if %PDF- found)
       ├─► 3. Computes SHA-256 digests for db_dump.json and all media files
       ├─► 4. Writes manifest.json containing checksums and metadata
       └─► 5. Compresses into dms_backup_<YYYYMMDD_HHMMSS>.tar.gz
       
[restore_dms Management Command]
       │
       ├─► 1. Decompresses archive into temporary sandbox directory
       ├─► 2. Validates manifest.json presence and version schema
       ├─► 3. Recomputes and validates SHA-256 hashes of db_dump.json and media files
       │      (Aborts immediately on checksum mismatch or tampering)
       ├─► 4. Restores verified .enc files to protected_media/
       └─► 5. Executes call_command('loaddata', db_dump.json) into database
```

---

## 6. Container & Production Deployment Topology

```
Internet / Hospital Intranet
          │
          ▼
   [Nginx Reverse Proxy (Port 80)]
   - Static file caching (/var/www/static/)
   - Security headers: X-Frame-Options: SAMEORIGIN
   - Security headers: X-Content-Type-Options: nosniff
   - Client max body size: 50M
          │
          ▼ (proxy_pass via internal docker network)
   [Gunicorn / Django Application (Port 8000)]
   - Non-root user: appuser (UID/GID 10001)
   - Master Encryption Key (Fernet 32-byte key)
   - Primary password hasher: Argon2id
   - Workers: 3 sync workers
          │
          ├───────────────┬───────────────┐
          ▼               ▼               ▼
     [PostgreSQL 16]   [Mailpit]    [Named Volumes]
     (Port 5432)       (SMTP: 1025) - protected_media_data
     - Healthchecked   (Web: 8025)  - static_data
     - pg_isready                   - backup_data
```

---

## Lessons Learned from Demo / Prototype

### 1. Performance Bottleneck: Model Property Getters Trigger Hidden N+1 Query Storms
* **Architectural Flaw:** In earlier versions, `Paper.latest_round` was implemented naively as `self.rounds.order_by('-round_number').first()`, and `Paper.round_count` as `self.rounds.count()`. When rendering lists with 50+ papers on the Doctor Workspace or Coordinator Triage Desk, calling `paper.latest_round` in template loops resulted in 100+ redundant SQL queries.
* **Architectural Solution:** Modified properties to inspect `hasattr(self, '_prefetched_objects_cache') and 'rounds' in self._prefetched_objects_cache`. When views invoke `.prefetch_related('rounds')`, `latest_round` sorts the cached list in Python RAM without firing any database queries, dropping query counts from $O(N)$ down to a flat $O(1)$.

### 2. Hidden Air-Gap Leaks: Auxiliary UI Toolbars Accidental Identity Disclosure
* **Architectural Flaw:** When designing the dedicated full-screen PDF viewer (`pdf_viewer.html`), the toolbar originally displayed `Investigator: {{ paper.author.get_full_name }}` and included a `Dossier` back button linking to `paper_detail`. When an assigned peer reviewer opened the viewer, they could see the author's real name and click into the author's dossier, completely violating the double-blind air gap.
* **Architectural Solution:** The viewer endpoint computes `is_blinded_reviewer = not (user.is_coordinator or user.is_admin_role or user.id == paper.author_id) and ReviewAssignment.objects.filter(round=round_obj, reviewer=user).exists()`. In templates, the investigator label is replaced with `[Blinded for Peer Review]` and the return button redirects to the reviewer's clinical workspace rather than the dossier.

### 3. Security Posture of JSON Serialization: Never Use Raw Inline Interpolation
* **Architectural Flaw:** In early versions of the Executive Dashboard, Chart.js datasets were injected directly into JavaScript using `{{ dept_labels_json|safe }}`. If a malicious user created a department name containing `</script><script>malicious()</script>`, it would immediately escape the script context and execute arbitrary client-side code (DOM-based XSS).
* **Architectural Solution:** Banned `|safe` for data structures. Standardized on Django's built-in `{{ data|json_script:"element-id" }}` which escapes HTML entities (`<` as `\u003c`, `>` as `\u003e`). JavaScript safely retrieves data using `JSON.parse(document.getElementById('element-id').textContent)`.


