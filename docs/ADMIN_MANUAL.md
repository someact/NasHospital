# คู่มือผู้ดูแลระบบและเจ้าหน้าที่ประสานงานวิจัย (Administrator & Coordinator Manual)
## MedResearch DMS - Clinical Research Management & Governance Platform

คู่มือฉบับนี้จัดทำขึ้นสำหรับ **เจ้าหน้าที่สำนักงานบริหารงานวิจัย (Coordinator C)** และ **ผู้ดูแลระบบเทคโนโลยีสารสนเทศ (System Administrators)** เพื่อเป็นแนวทางปฏิบัติการควบคุมคุณภาพงานวิจัย (Gatekeeping), การป้องกันผลประโยชน์ทับซ้อน (COI Guard), การสังเคราะห์ความเห็นผู้ตรวจ (Consolidation Desk), การอนุมัติสิทธิ์เข้าถึงเอกสาร (Access Pass Queue), และการบำรุงรักษาเชิงเทคนิค

---

## สารบัญ (Table of Contents)
1. [บทบาทและหน้าที่ของ Coordinator C (Roles & Responsibilities)](#1-บทบาทและหน้าที่ของ-coordinator-c-roles--responsibilities)
2. [การคัดกรองและบริหารจัดการบทความวิจัย (Triage Desk)](#2-การคัดกรองและบริหารจัดการบทความวิจัย-triage-desk)
3. [ระบบป้องกันผลประโยชน์ทับซ้อนและการมอบหมายผู้ตรวจ (COI Guard & Dispatcher)](#3-ระบบป้องกันผลประโยชน์ทับซ้อนและการมอบหมายผู้ตรวจ-coi-guard--dispatcher)
4. [โต๊ะสังเคราะห์ผลประเมินและการปิดผนึกตีพิมพ์ (Consolidation & Publication Lock)](#4-โต๊ะสังเคราะห์ผลประเมินและการปิดผนึกตีพิมพ์-consolidation--publication-lock)
5. [การจัดการคิวคำขอเข้าถึงเอกสาร (Access Ticket Queue Management)](#5-การจัดการคิวคำขอเข้าถึงเอกสาร-access-ticket-queue-management)
6. [การดูแลรักษาระบบและคำสั่งปฏิบัติการ (Technical Operations & Maintenance)](#6-การดูแลรักษาระบบและคำสั่งปฏิบัติการ-technical-operations--maintenance)

---

## 1. บทบาทและหน้าที่ของ Coordinator C (Roles & Responsibilities)

เจ้าหน้าที่ประสานงานวิจัย (Coordinator C - บัญชีทดสอบ `charlie` / `password123`) ทำหน้าที่เป็น **"คนกลางที่ปิดผนึกข้อมูล" (Air-Gapped Double-Blind Proxy)** โดยมีหน้าที่รับผิดชอบหลัก:
1. **Gatekeeper:** ตรวจสอบความถูกต้องและจริยธรรมของบทความวิจัยที่แพทย์ยื่นเข้ามา ก่อนส่งให้ผู้ประเมิน
2. **Dispatcher:** คัดเลือกและมอบหมายแพทย์ผู้ทรงคุณวุฒิในการตรวจ โดยบังคับใช้กฎ Conflict of Interest (COI) อย่างเคร่งครัด
3. **Synthesizer:** รวบรวมความเห็นของผู้ตรวจทุกคน สังเคราะห์ข้อคิดเห็น และออกคำสั่งแก้ไข (Coordinator Decision Letter) ถึงแพทย์ผู้วิจัยโดยไม่เปิดเผยตัวตนผู้ตรวจ
4. **Access Gatekeeper:** ตรวจสอบและอนุมัติบัตรผ่านการอ่านบทความวิจัยฉบับเต็มของบุคลากรในโรงพยาบาล

---

## 2. การคัดกรองและบริหารจัดการบทความวิจัย (Triage Desk)
**เข้าใช้งานที่:** `/coordinator/triage/`

หน้าจอ Triage Desk เป็นศูนย์บัญชาการของ Coordinator C ในการควบคุมวงจรชีวิตบทความวิจัย:

### 2.1 แถบกรองสถานะบทความ (Status Filter Tabs)
- **All Submissions:** แสดงบทความวิจัยทั้งหมดในระบบ
- **Pending Triage (`PENDING_COORD`):** บทความใหม่หรือบทความฉบับแก้ไขรอบถัดไปที่แพทย์ส่งเข้ามา รอการตรวจสอบเบื้องต้น
- **In Peer Review (`PENDING_ADVISOR`):** บทความที่ส่งไปยังผู้ทรงคุณวุฒิแล้ว อยู่ระหว่างรอผลการตรวจ
- **Reviews Completed (`ADVISOR_COMMENTED`):** ผู้ประเมินส่งแบบประเมินครบแล้ว พร้อมสำหรับการสังเคราะห์ความเห็น
- **Published & Locked (`PUBLISHED`):** บทความที่ผ่านการรับรองและล็อกการแก้ไขถาวร เผยแพร่ในคลัง Catalog

### 2.2 ขั้นตอนการตรวจสอบความถูกต้องก่อนส่งตรวจ (Pre-Review Checklist)
ก่อนมอบหมายแพทย์ผู้ตรวจ เจ้าหน้าที่ต้องคลิกปุ่ม **"Dossier"** เพื่อตรวจสอบ:
1. **Patient De-identification Compliance:** ตรวจสอบว่าไฟล์ PDF ไม่มีข้อมูลชื่อ-นามสกุล, เลขประจำตัวผู้ป่วย (HN), หรือข้อมูลที่ระบุตัวตนผู้ป่วยได้ ตามกฎหมาย PDPA และจริยธรรมการวิจัยในมนุษย์
2. **Methodology & Ethics Approval:** ระบุเลขที่รับรองจากคณะกรรมการจริยธรรมการวิจัยในมนุษย์ (IRB/EC)
3. **Completeness:** มีเอกสารครบถ้วน มีตารางสถิติและรูปภาพประกอบที่ชัดเจน

---

## 3. ระบบป้องกันผลประโยชน์ทับซ้อนและการมอบหมายผู้ตรวจ (COI Guard & Dispatcher)

### 3.1 กลไกป้องกันผลประโยชน์ทับซ้อน (Conflict of Interest Guard Architecture)
ระบบ MedResearch DMS มีกลไกป้องกันผลประโยชน์ทับซ้อนที่ระดับฐานข้อมูล (Database Queryset) และระดับโมเดล (Model Validation):

```python
# papers/models.py
def get_assignable_reviewers(paper):
    """
    COI Guard: คัดกรองเฉพาะแพทย์ (role=DOCTOR) 
    และคัดชื่อแพทย์ที่เป็นผู้วิจัย (paper.author_id) ออกจากรายชื่อผู้มีสิทธิ์ตรวจอย่างเด็ดขาด
    """
    return User.objects.filter(role=UserRole.DOCTOR)\
                       .exclude(id=paper.author_id)\
                       .order_by('department', 'first_name')
```

นอกจากนี้ ในระดับโมเดล `ReviewAssignment.clean()` ยังมีการตรวจสอบป้องกันอีกชั้นหนึ่ง หากมีการพยายามบันทึกข้อมูลที่ `reviewer_id == paper.author_id` ระบบจะปฏิเสธและแจ้งเตือน `ValidationError` ทันที

### 3.2 ขั้นตอนการมอบหมายผู้ทรงคุณวุฒิตรวจบทความ (Assigning Reviewers)
1. ในหน้า Triage Desk ที่บทความสถานะ `PENDING_COORD` คลิกปุ่ม **"Assign Reviewers"**
2. ป๊อปอัปหน้าต่าง **Advisor Dispatcher Modal** จะปรากฏขึ้น:
   - ป้ายเตือน **Conflict of Interest (COI) Active** จะแสดงชื่อแพทย์ผู้วิจัยหลักที่ถูกตัดสิทธิ์จากการตรวจบทความนี้
   - ระบบจะแสดงรายชื่อเฉพาะแพทย์ท่านอื่น พร้อมระบุแผนกและความเชี่ยวชาญเฉพาะทาง (Specialization)
3. ทำเครื่องหมายถูกเลือกแพทย์ 1 ถึง 3 ท่านที่ตรงกับสาขาของบทความ
4. คลิกปุ่ม **"Dispatch Assignments"**
5. สถานะบทความจะเปลี่ยนเป็น **`PENDING_ADVISOR`** โดยอัตโนมัติ และระบบจะส่งงานวิจัยไปยังแท็บ "Assigned Peer Reviews" ของแพทย์ที่ได้รับเลือกทันที

---

## 4. โต๊ะสังเคราะห์ผลประเมินและการปิดผนึกตีพิมพ์ (Consolidation & Publication Lock)
**เข้าใช้งานที่:** `/coordinator/papers/<paper_id>/consolidate/`

เมื่อผู้ประเมินทุกคนส่งความเห็นเรียบร้อยแล้ว บทความจะเปลี่ยนสถานะเป็น **`ADVISOR_COMMENTED`** ในหน้า Triage Desk จะปรากฏปุ่มสีฟ้า **"Consolidation Desk"**:

### 4.1 หน้าจอเปรียบเทียบผลการตรวจแบบเคียงข้าง (Side-by-Side Review)
- **ฝั่งซ้าย (Submitted Peer Critiques):**
  - แสดงความเห็นของแพทย์ผู้ตรวจแต่ละท่านแยกตามหมวดหมู่:
    1. เค้าโครง (Structure & Methodology)
    2. บทนำ (Introduction & Literature)
    3. บทขยาย (Results & Discussion)
  - แสดงมติของผู้ตรวจแต่ละท่าน (`Request Revisions` หรือ `Approve as Final`)
  - ลิงก์เปิดดูไฟล์ Annotated PDF ที่ผู้ตรวจแนบโน้ตมา (หากมี)
  - *ส่วนนี้มองเห็นได้เฉพาะ Coordinator C เท่านั้น แพทย์ผู้วิจัยจะไม่สามารถเข้าถึงได้*

### 4.2 การร่างหนังสือสังเคราะห์ความเห็น (Coordinator Decision Letter)
- **ฝั่งขวา (Synthesize Coordinator Decision Letter):**
  - เจ้าหน้าที่ร่างข้อความสังเคราะห์ในช่อง **Consolidated Coordinator Directives** โดยดึงประเด็นสำคัญจากผู้ตรวจทุกท่านมารวมเป็นคำแนะนำเดียว โดย **ห้ามระบุชื่อผู้ตรวจหรือคัดลอกข้อความส่วนบุคคล**
  - **เลือกผลการตัดสิน (Decision):**
    - **Require Author Revisions:** หากต้องการให้แก้ไข บทความจะเปลี่ยนสถานะเป็น `REVISION_REQUIRED` เปิดสิทธิ์ให้แพทย์ผู้วิจัยอัปโหลดแก้ไขในรอบ $N+1$
    - **Approve for Publication:** หากบทความสมบูรณ์และผ่านการประเมิน
  - คลิกปุ่ม **"Dispatch Letter to Author"**

### 4.3 การล็อกและปิดผนึกผลงานวิจัย (Publication Lock)
1. เมื่อบทความผ่านการประเมิน ในหน้า Triage Desk จะมีปุ่มสีเขียว **"Publish Lock"**
2. เมื่อคลิกยืนยัน:
   - บทความจะเข้าสู่สถานะ **`PUBLISHED`**
   - บันทึกเวลาเผยแพร่ `published_at = timezone.now()`
   - **ระบบจะล็อกการแก้ไขถาวร (Archived Lock)** ผู้วิจัยจะไม่สามารถอัปโหลดไฟล์แก้ไขทับได้อีกต่อไป
   - บทความจะปรากฏสู่สาธารณะในหน้า **Hospital Research Catalog** ทันที

---

## 5. การจัดการคิวคำขอเข้าถึงเอกสาร (Access Ticket Queue Management)
**เข้าใช้งานที่:** `/coordinator/access-requests/`

บุคลากรโรงพยาบาล (เช่น แพทย์ประจำบ้าน, พยาบาลวิจัย, หรือเภสัชกร) ที่ต้องการอ่านไฟล์เอกสารวิจัยฉบับเต็มที่มีการล็อกสิทธิ์ จะต้องยื่นคำขอ Access Ticket เข้ามาในระบบ:

```
+------------------------------------------------------------------------------------+
|  Coordinator Access Pass Review Queue                                              |
|                                                                                    |
|  [ Pending Access Tickets (1) ]                                                    |
|  +-------------------------------------------------------------------------------+ |
|  | Requester    | Paper Title              | Duration | Justification | Actions  | |
|  |--------------+--------------------------+----------+---------------+----------| |
|  | Sarah Jenkins| Long-term Outcomes in... | 14 Days  | ED Protocol...| [Grant]  | |
|  |              |                          |          |               | [Deny]   | |
|  +-------------------------------------------------------------------------------+ |
|                                                                                    |
|  [ Active & Expired Access Passes Archive ]                                        |
+------------------------------------------------------------------------------------+
```

### 5.1 ขั้นตอนการพิจารณาคำขอ (Granting / Denying Passes)
1. ตรวจสอบชื่อบุคลากรผู้ขอ, แผนก, และบทความที่ต้องการอ่าน
2. อ่านเหตุผลความจำเป็นทางคลินิก (Clinical Justification) เช่น การทบทวนแนวทางการดูแลผู้ป่วยฉุกเฉิน หรือการทำวิจัยต่อเนื่อง
3. **การดำเนินการ:**
   - **Grant Pass:** กดปุ่มเพื่ออนุมัติบัตรผ่าน ระบบจะคำนวณวันหมดอายุอัตโนมัติ (`expires_at = now + duration_days`) และเปิดสิทธิ์ให้อ่านไฟล์ PDF ได้ทันที
   - **Deny:** กดปุ่มเพื่อปฏิเสธคำขอหากไม่มีเหตุผลสมควร

### 5.2 การตรวจสอบบัตรผ่านที่หมดอายุ (Active & Expired Archive)
ตารางด้านล่างจะบันทึกประวัติบัตรผ่านทั้งหมด โดยแสดงสถานะ **Active** (ยังไม่หมดอายุ) หรือ **Expired** (หมดอายุแล้ว ซึ่งระบบจะตัดสิทธิ์การอ่าน PDF ทันทีและส่งผลให้กลับมาเป็น `HTTP 403 Forbidden`)

---

## 6. การดูแลรักษาระบบและคำสั่งปฏิบัติการ (Technical Operations & Maintenance)

### 6.1 การสั่งรันระบบ (Starting the Application)
ระบบ MedResearch DMS ทำงานบน Python 3.12 ภายใต้โปรเจกต์ Django 5.1 สามารถรันได้ 2 รูปแบบ:

#### วิธีที่ 1: รันด้วยสคริปต์อัตโนมัติ (Automated Shell Script)
```bash
cd /home/nuts/NasHospitalSystem
./run_demo.sh
```
สคริปต์นี้จะทำหน้าที่เปิด Virtualenv, ตรวจสอบ Migration, Seed ข้อมูลตัวอย่าง, และเริ่มการทำงานของเซิร์ฟเวอร์ที่พอร์ต `8000`

#### วิธีที่ 2: รันด้วยคำสั่งแมนนวล (Manual Command)
```bash
cd /home/nuts/NasHospitalSystem
source .venv/bin/activate
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

#### วิธีที่ 3: รันฐานข้อมูลและ Mailpit ด้วย Docker Compose
```bash
cd /home/nuts/NasHospitalSystem
docker compose up -d
```
- **PostgreSQL 16:** พอร์ต `5432` (หากไม่ได้เปิด Docker ระบบจะสลับไปใช้ SQLite3 WAL Mode โดยอัตโนมัติอย่างไร้รอยต่อ)
- **Mailpit Web Inbox:** พอร์ต `8025` (เข้าดูอีเมลแจ้งเตือนที่ถูกส่งออกจากระบบ)

### 6.2 การรีเซ็ตและสร้างข้อมูลจำลองใหม่ (Seed Demo Data)
หากต้องการล้างข้อมูลและเริ่มต้นฐานข้อมูลจำลองใหม่ ให้รันคำสั่ง:
```bash
python manage.py seed_demo
```
คำสั่งนี้จะใช้ไลบรารี **ReportLab** ในการสร้างไฟล์ PDF ทางการแพทย์ที่มีหัวกระดาษ, บทคัดย่อ, ตารางสถิติผู้ป่วย, และลายน้ำอย่างสมจริง จำนวน 5 บทความ ครบทุกสถานะวงจรชีวิต

### 6.3 การทดสอบระบบอัตโนมัติ (Automated Test Suite)
เพื่อตรวจสอบความถูกต้องของระบบ ป้องกันการเกิด Regression ให้รันชุดทดสอบ 9 ข้อ:
```bash
python manage.py test
```
**การครอบคลุมของการทดสอบ (Test Coverage):**
- `test_1_coi_guard_queryset_and_validation`: ตรวจสอบ COI Guard ไม่ให้ผู้แต่งตรวจงานตนเอง
- `test_2_doctor_dual_role`: ตรวจสอบบทบาท DOCTOR ทำหน้าที่ได้ทั้งแต่งและตรวจ
- `test_3_fsm_lifecycle_transitions`: ตรวจสอบ Finite State Machine ในทุกสถานะ
- `test_4_air_gap_coordinator_isolation`: ตรวจสอบว่าชื่อผู้ตรวจไม่รั่วไหลไปยังหน้าจอผู้วิจัย
- `test_5_totp_2fa_setup_and_verification`: ตรวจสอบระบบยืนยันรหัสสองชั้น OTP
- `test_6_catalog_visibility`: ตรวจสอบว่าเฉพาะบทความ `PUBLISHED` เท่านั้นที่ปรากฏใน Catalog
- `test_7_access_gate_enforcement`: ตรวจสอบการบล็อกไฟล์ PDF ด้วย 403 Forbidden และเปิดสิทธิ์เมื่อได้บัตรผ่าน
- `test_8_role_switcher`: ตรวจสอบการสลับบทบาทจำลอง
- `test_9_xframe_options_sameorigin_for_pdf_embedding`: ตรวจสอบค่า `X-Frame-Options: SAMEORIGIN` สำหรับการฝัง PDF ใน iframe

### 6.4 ความปลอดภัยของไฟล์และการจัดเก็บ (Protected Media Storage Architecture)
- ไฟล์บทความวิจัยทั้งหมดจะถูกจัดเก็บที่ไดเรกทอรี `protected_media/secure_papers/%Y/%m/<uuid>_<filename>.pdf`
- **ไม่มีการเปิด URL สถิตสาธารณะ (No Public Static Serving):** ผู้ใช้งานไม่สามารถเข้าถึงไฟล์ผ่านพาธตรงบนเว็บเซิร์ฟเวอร์ได้
- ทุกการดาวน์โหลดหรือเปิดดูต้องผ่านฟังก์ชัน `serve_protected_paper` ใน `papers/views.py` ซึ่งจะตรวจสิทธิ์ผู้ใช้ก่อนส่งไฟล์ผ่าน `FileResponse` เสมอ

---
*MedResearch DMS &bull; Hospital Information Technology Division & Research Ethics Board &bull; 2026*
