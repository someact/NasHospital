# Engineering Guidelines & Technical Constraints: MedResearch DMS (Enterprise Suite)

## 1. Core Technology Stack
- **Backend Framework:** Python 3.12, Django 5.x (Monolithic Architecture with clean app modularity: `accounts`, `papers`).
- **Database Layer:** PostgreSQL 16 Alpine in Docker with transparent, zero-config SQLite3 (WAL mode) fallback for isolated local environments.
- **Frontend Layer:** Django Templates + Bootstrap 5.3 + Bootstrap Icons + Chart.js 4.x + Mozilla PDF.js v3.11 + Vanilla JavaScript.
- **Password Hashing Standard:** Argon2id (`django.contrib.auth.hashers.Argon2PasswordHasher` via `argon2-cffi`) as primary hasher, with transparent automatic migration from legacy PBKDF2 on successful login.
- **Application-Level Cryptographic Storage:** Fernet authenticated encryption (AES-128-CBC + HMAC-SHA256 via `cryptography.fernet`) at rest for all clinical PDFs (`.enc` extension). Zero plaintext `%PDF-` files on disk.
- **Two-Factor Authentication (TOTP):** RFC 6238 time-based one-time password standard via `django-otp` and `django_otp.plugins.otp_totp`, generating interactive inline base64 QR codes using `qrcode` for Google Authenticator and Microsoft Authenticator pairing.
- **Multi-Service Container Topology:** Docker Compose coordinating `web` (Python 3.12-slim non-root `appuser:appgroup`), `db` (PostgreSQL 16 Alpine with `pg_isready` healthcheck), `nginx` reverse proxy with strict security headers, and `mailpit` SMTP sandbox (Port 1025 SMTP / 8025 Web UI).

---

## 2. Strict Architectural Rules & Guardrails

### A. Unified Doctor Persona (Context-Dependent Role Model)
- Clinicians hold the unified `DOCTOR` role. There are no mutually exclusive "Author" or "Reviewer" database roles.
- Capability is dynamic: a doctor is an **Author** in the context of their own submitted manuscripts, and a **Peer Reviewer** in the context of manuscripts assigned to them by Coordinator C.

### B. Conflict of Interest (COI) Guard
- Authors are strictly forbidden from reviewing their own manuscripts or participating in review panels for their own submissions.
- **Queryset Level:** `get_assignable_reviewers(paper)` enforces `User.objects.filter(role=UserRole.DOCTOR).exclude(id=paper.author_id)`.
- **Model Validation Level:** `ReviewAssignment.clean()` validates `reviewer_id != round.paper.author_id` and raises a fatal `ValidationError`.

### C. Double-Blind Air-Gap Mediation
- Authors and Peer Reviewers never interact directly and cannot view each other's identities or raw critique notes.
- Reviewers submit structured critiques (เค้าโครง, บทนำ, บทขยาย) solely to Coordinator C.
- Authors only ever receive synthesized `CoordinatorLetter` records dispatched by Coordinator C.
- In-browser PDF viewers automatically detect assigned reviewers (`is_blinded_reviewer`) and mask the lead investigator as `[Blinded for Peer Review]`, suppressing all author dossier navigation links.

### D. Production vs. Demo Mode Isolation (`ENABLE_DEMO_MODE`)
- Interactive demo tools (e.g., One-Click Persona Switcher bar, pre-seeded credentials hints) are strictly gated behind the environment variable `ENABLE_DEMO_MODE=True`.
- When `ENABLE_DEMO_MODE` is disabled (Production default):
  * `accounts/views.py:switch_role` raises `Http404("Demo Mode is disabled.")`.
  * `accounts.context_processors.demo_personas` returns an empty list.
  * UI templates completely suppress demo switcher navigation bars and credential hints.

### E. In-Browser Secure PDF Delivery (PDF.js Canvas Engine)
- Raw binary PDF streaming into native browser PDF plugins is strictly blocked for full-text manuscript inspection.
- Full-text reading routes via `/papers/<id>/viewer/`, rendering pages onto an HTML5 `<canvas>` using Mozilla PDF.js.
- A dynamic 2D canvas diagonal watermark is stamped across every rendered page buffer at -45°:
  `[User Full Name] ([Role]) • [Hospital Domain] • [Timestamp UTC] • [Client IP]`
- Anti-tamper event listeners disable right-click context menus and intercept keyboard save/print shortcuts (`Ctrl+S`, `Ctrl+P`, `Cmd+S`, `Cmd+P`).

### F. Disaster Recovery & Integrity Verification Loop
- Backups are generated via `python manage.py backup_dms`, bundling JSON database fixtures and encrypted `.enc` media files alongside a `manifest.json` containing SHA-256 checksums.
- `backup_dms` verifies the first 16 bytes of each file in protected storage; if any unencrypted `%PDF-` file is encountered, the backup is halted with a `CommandError` to prevent data leakage.
- Restorations via `python manage.py restore_dms <archive>` recalculate SHA-256 hashes of all components before committing files or database records.

### G. In-Memory Prefetch Optimization Rules (N+1 Query Prevention)
- Model properties accessed in list views (such as `Paper.latest_round` and `Paper.round_count`) must check `hasattr(self, '_prefetched_objects_cache')` before executing database queries.
- List views must utilize `.prefetch_related('rounds')` to ensure constant $O(1)$ query overhead regardless of manuscript volume.

---

## 3. Enterprise Extension Constraints & Patterns

### A. Chart.js Safe JSON Script Pattern
- Inline Django template interpolation (e.g., `{{ data|safe }}`) inside `<script>` blocks is strictly forbidden to prevent XSS and script tag termination vulnerabilities.
- Data must be serialized via Django's `json_script` template filter and parsed client-side using `JSON.parse(document.getElementById('...').textContent)`.

### B. Append-Only Audit Logging Pattern
- `accounts_auditlog` is strictly append-only: updates and deletes are disallowed by policy and design.
- Client IP addresses are resolved by inspecting proxy headers (`HTTP_X_FORWARDED_FOR`, `HTTP_X_REAL_IP`, `REMOTE_ADDR`), and validated using Python's `ipaddress.ip_address()` to eliminate malformed inputs or header injections.
- Authentication failures must be logged as `AuditAction.LOGIN_FAILURE`, keeping failed security events distinct from `LOGIN_SUCCESS`.

### C. In-App Notification Engine Guidelines
- Dispatched via helper `notify_user(recipient, actor, paper, notif_type, message, target_url)`.
- Global unread counters and contextual badges are injected via `notifications_context` context processor, optimizing badge computation across clinical workspaces.

---

## 💡 Lessons Learned from Demo / Prototype (สิ่งที่ได้เรียนรู้จากการทำ Demo)

### 1. Native Browser PDF Viewing Fails Healthcare Security Requirements
* **Discovery:** In early iterations, manuscripts were served directly to the browser via binary streaming with standard `Content-Disposition: inline`. Browsers (Chrome, Firefox, Safari) used their internal PDF plugins (PDFium/PDF.js plugin).
* **Security Gap:** Native browser plugins bypass the application DOM completely. CSS watermark overlays and JavaScript anti-tamper guards (blocking right-click or `Ctrl+S`) cannot execute within the native plugin sandbox. Furthermore, users could easily click the browser's built-in "Download" or "Print" buttons to export unwatermarked clinical documents.
* **Remediation:** Migrated to a dedicated in-browser viewer (`/papers/<id>/viewer/`) using Mozilla PDF.js embedded directly in the page DOM. Pages are drawn onto an HTML5 `<canvas>`, allowing the application to directly draw non-destructive 2D diagonal watermarks onto the canvas bitmap before display, while full JavaScript anti-tamper handlers trap save and print hotkeys.

### 2. The Critical Necessity of Feature Flags for Demo Impersonation Tools
* **Discovery:** The one-click demo role switcher bar (`/accounts/switch-role/<id>/`) provided exceptional agility during clinical stakeholder demonstrations, enabling instant role swapping between Author, Reviewer, and Coordinator.
* **Security Gap:** If shipped into staging or production without architectural isolation, any unauthenticated attacker could issue a GET request to swap personas directly into the System Administrator or Coordinator account without entering credentials or solving TOTP challenges.
* **Remediation:** Enforced a strict environment feature flag `ENABLE_DEMO_MODE`. In production, the switcher endpoint returns a hard 404, context processors return empty lists, and all switcher templates are excluded from rendering. Local demonstration scripts (`run_demo.sh`) explicitly enable the flag for developer environments.

### 3. The Danger of Orphaned Plaintext PDF Files During Development & Test Seeding
* **Discovery:** When transitioning from plaintext storage to application-level Fernet encrypted storage (`EncryptedFileSystemStorage`), 206 plaintext `.pdf` files remained in `protected_media/` from legacy test runs and seeding iterations.
* **Security Gap:** Although active database records pointed to `.pdf.enc` files, the presence of plaintext medical documents on disk represented a catastrophic compliance vulnerability in the event of an OS-level filesystem breach or backup dump.
* **Remediation:** Purged all orphaned `.pdf` files from disk and added an automated assertion in `backup_dms`: the command inspects the binary header of every file in `protected_media/`; if the magic bytes `b'%PDF-'` are detected, the backup is immediately aborted with a `CommandError` to prevent unencrypted clinical data leakage.

### 4. In-Memory Decryption Memory Management for Heavy Clinical Documents
* **Discovery:** Decrypting encrypted PDF ciphertexts on-the-fly inside streaming endpoints (`serve_protected_paper`) requires reading the Fernet ciphertext and decrypting it into an in-memory buffer (`io.BytesIO`).
* **Engineering Constraint:** For massive clinical dossiers or high concurrency, holding entire decrypted byte arrays in worker RAM can increase memory consumption on web containers.
* **Remediation:** Streaming responses were structured using `FileResponse` wrapping in-memory buffers with garbage collection triggers. In high-volume production deployments, pre-decrypting temporary chunks or delegating cryptographic streaming to an internal Nginx acceleration module (`X-Accel-Buffering: no`) provides the ideal balance between memory overhead and zero-plaintext disk security.
