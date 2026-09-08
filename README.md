# 🏥 MedResearch DMS (Clinical Manuscript & Peer Review System)

Welcome to **MedResearch DMS** — an enterprise-grade Clinical Document Management System designed for hospital academic research, double-blind peer review governance, and confidential document delivery.

---

## ⚡ Quick Start (The Fastest Way to Run)

### 1. Prerequisites
- **Python 3.12+**
- Git

### 2. Setup & Run in 1 Command
If you just cloned the repository, you can get everything running (virtualenv, dependencies, database migrations, and pre-seeded demo doctors & research papers) with:

```bash
# 1. Clone the repo (if you haven't)
git clone https://github.com/someact/NasHospital.git
cd NasHospital

# 2. Create virtual environment & install requirements
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Launch the all-in-one demo script
chmod +x run_demo.sh
./run_demo.sh
```

The system will automatically:
1. Enable Demo Mode (`ENABLE_DEMO_MODE=True`).
2. Run database migrations.
3. Seed realistic clinical manuscripts and demo doctors.
4. Launch the server at **http://127.0.0.1:8000**.

---

## 🎭 Pre-Seeded Test Accounts

When running with Demo Mode enabled, you can switch between accounts in 1 click using the **Demo Switcher Bar** at the top of the browser, or log in manually:

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `alice` | `password123` | **Doctor (Author)** | Attending Cardiologist; authored heart failure studies, reviews oncology papers. |
| `bob` | `password123` | **Doctor (Reviewer)** | Surgical Oncologist; reviews Dr. Alice's cardiology manuscripts. |
| `charlie` | `password123` | **Coordinator** | Research Coordinator (นาย C); triage gatekeeper, double-blind synthesizer, access ticket approver. |
| `sarah` | `password123` | **Staff Clinician** | Emergency Medicine Fellow; browses catalog and requests 7-day reading passes. |
| `admin` | `password123` | **Administrator** | IT Administrator; manages user profiles, 2FA resets, and views audit logs. |

---

## 🚩 Demo Mode Feature Flag (`ENABLE_DEMO_MODE`)

We use the `ENABLE_DEMO_MODE` environment variable to strictly separate demo tools from production security:

* **In Development / Demo (`ENABLE_DEMO_MODE=True`):**
  - The top **Demo Switcher Bar** appears on every page for 1-click persona swapping.
  - Login page shows pre-seeded credential hints.
  - Route `/accounts/switch-role/<id>/` is active.

* **In Production (`ENABLE_DEMO_MODE=False` - Default):**
  - The Demo Switcher Bar is completely hidden.
  - Persona swap endpoint `/accounts/switch-role/<id>/` immediately raises `404 Not Found`.
  - Context processors do not expose demo users.
  - Pre-seeded hints on login are removed.

To toggle it manually:
```bash
# In your .env file or terminal:
export ENABLE_DEMO_MODE=True   # For local testing & demo
export ENABLE_DEMO_MODE=False  # For staging & production
```

---

## 🛠️ Developer Cheatsheet & Useful Commands

### Running Automated Tests
The project includes a comprehensive test suite covering FSM transitions, Conflict of Interest guards, Argon2 hashing, zero-plaintext encrypted storage, and audit remediations:

```bash
python manage.py test
# Or with virtualenv binary:
.venv/bin/python manage.py test
```

### Re-seeding Demo Data
To wipe and re-generate clean demo papers, reviews, and test accounts:
```bash
python manage.py seed_demo
```

### Disaster Recovery: Backup & Restore
All uploaded PDFs are encrypted at rest with Fernet (`.enc`). To create a verifiable backup archive:
```bash
# 1. Create a backup (.tar.gz with SHA-256 manifest)
python manage.py backup_dms

# 2. Restore from a backup archive
python manage.py restore_dms backups/dms_backup_<TIMESTAMP>.tar.gz
```
> 💡 *Note: `backup_dms` verifies the binary header of every stored file. If an unencrypted `%PDF-` file is detected in protected media, it immediately halts to prevent data leaks.*

---

## 🐳 Running with Docker Compose

If you prefer running in Docker with PostgreSQL, Nginx, and Mailpit:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start all services (web, db, nginx, mailpit)
docker compose up --build
```
- Web Application: **http://localhost:8000**
- Mailpit Webmail (capture test emails): **http://localhost:8025**

---

## 🧠 Key Architecture Highlights for Developers

1. **Unified Doctor Role:** Doctors hold the unified role `DOCTOR`. They act as Authors for their own papers and Reviewers for assigned peer papers. There is no separate mutually exclusive "Author" vs "Reviewer" role.
2. **Conflict of Interest (COI) Guard:** Authors are excluded from review panels both at the queryset level (`exclude(id=paper.author_id)`) and model validation (`clean()`).
3. **Double-Blind Air Gap:** Authors only see synthesized `CoordinatorLetter` feedback from Coordinator Charlie. Reviewers inspect manuscripts with author names masked as `[Blinded for Peer Review]`.
4. **Zero-Plaintext Storage:** Manuscripts are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before touching the disk. Files are saved as `<uuid>.enc`. Decryption occurs strictly in-memory during streaming.
5. **In-Browser Watermarked PDF Viewer:** Full-text documents are rendered via Mozilla PDF.js on an HTML5 `<canvas>` with dynamic diagonal watermarks (`Doctor Name • Hospital Domain • UTC Time • Client IP`) and anti-tamper shortcut interception (`Ctrl+S`, `Ctrl+P`).
6. **Argon2id Password Hashing:** Powered by `argon2-cffi` as Django's default hasher.

---

## 📚 Further Documentation

For deep architectural and operational details, refer to:
- [`skills.md`](skills.md): Engineering constraints, security guidelines & lessons learned.
- [`architecture.md`](architecture.md): Database schemas, FSM state diagrams, and topology maps.
- [`features.md`](features.md): Detailed functional specifications and clinical workflows.
- [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md): Clinician user manual.
- [`docs/ADMIN_MANUAL.md`](docs/ADMIN_MANUAL.md): Coordinator and IT administrator manual.
