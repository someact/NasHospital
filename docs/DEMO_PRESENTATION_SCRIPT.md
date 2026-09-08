# สคริปต์การสาธิตระบบ MedResearch DMS ใน 5 นาที
## (5-Minute High-Fidelity Demo Script for Hospital Directors & Research Committee)

เอกสารนี้จัดทำขึ้นสำหรับผู้นำเสนอ (Presenter) เพื่อใช้สาธิตฟังก์ชันสำคัญของระบบ **MedResearch DMS** ต่อหน้าคณะกรรมการบริหารโรงพยาบาลและศาสตราจารย์ผู้ทรงคุณวุฒิ โดยเน้นย้ำ 5 ประเด็นสำคัญ:
1. **Unified Doctor Role:** แพทย์คนเดียวเป็นได้ทั้งผู้แต่งและผู้ตรวจ
2. **COI Guard:** ระบบป้องกันผลประโยชน์ทับซ้อนอัตโนมัติ
3. **Split-Screen PDF Review:** โต๊ะตรวจบทความแยกสองจอไร้รอยต่อ
4. **Air-Gapped Double-Blind Mediation:** ป้องกันการรั่วไหลของชื่อผู้ตรวจ 100%
5. **Time-Bound Access Gate:** บัตรผ่านควบคุมการอ่าน PDF ฉบับเต็ม

---

## ตารางสรุปเวลาการสาธิต (Timeline Overview)

| เวลา | ลำดับการสาธิต | ผู้แสดงบทบาท (Persona) | จุดเน้นย้ำ (Key Architecture Highlight) |
|---|---|---|---|
| 00:00 - 01:00 | **Scene 1: การยื่นเสนอบทความวิจัยใหม่** | Dr. Alice (Cardiology) | Unified Doctor Workspace & Protected PDF Upload |
| 01:00 - 02:00 | **Scene 2: การคัดกรองและมอบหมายผู้ตรวจ** | Charlie (Coordinator) | Conflict of Interest (COI) Guard & Author Exclusion |
| 02:00 - 03:00 | **Scene 3: การตรวจบทความแบบแยกสองจอ** | Dr. Bob (Surgery) | In-Browser PDF Embedding & 3-Part Critique Form |
| 03:00 - 04:00 | **Scene 4: การสังเคราะห์คำสั่งและประวัติแบบ Air-Gap** | Charlie & Dr. Alice | Double-Blind Proxy & Coordinator Decision Letter |
| 04:00 - 05:00 | **Scene 5: คลังผลงานวิจัยและการขอเปิดสิทธิ์อ่าน** | Dr. Sarah & Charlie | Time-Bound Access Gate (403 Gated $\rightarrow$ 200 Stream) |

---

## บทบรรยายและขั้นตอนการคลิกแบบละเอียด (Step-by-Step Walkthrough)

### 🎬 Scene 1: การยื่นเสนอบทความวิจัย (Dr. Alice - 1 นาที)
**เป้าหมาย:** แสดงให้เห็นพื้นที่ทำงานแพทย์ที่ใช้งานง่าย และการอัปโหลดไฟล์ PDF ฉบับเต็มเข้าสู่ระบบจัดเก็บแบบปลอดภัย

1. **การตั้งค่าเริ่มต้น:**
   - เปิดหน้าต่างเบราว์เซอร์ไปที่ `http://localhost:8000`
   - ที่แถบ **Demo Switcher Bar** ด้านบน คลิกเลือก **🩺 Alice Mercer**
2. **การนำเสนอ:**
   - *คำบรรยายผู้พูด:*
     > "เรียนท่านผู้อำนวยการและคณะกรรมการทุกท่าน นี่คือ MedResearch DMS หน้าแรกที่แพทย์จะได้พบเมื่อเข้าใช้งาน ระบบนี้ใช้สถาปัตยกรรม **Unified Doctor Role** โดย Dr. Alice เป็นอายุรแพทย์โรคหัวใจ สามารถดูทั้งงานวิจัยที่ตนเองเป็นผู้วิจัยหลักในแท็บ **'My Researches'** และงานวิจัยที่ตนเองได้รับเชิญให้ตรวจในแท็บ **'Assigned Peer Reviews'** ในหน้าจอเดียวกันครับ"
3. **การคลิก:**
   - คลิกแท็บ **"My Researches"** ชี้ให้เห็นว่ามีบทความ Paper 1, 3, 5 แสดงสถานะวงจรชีวิตและรอบการตรวจอย่างชัดเจน
   - คลิกปุ่ม **"+ New Research Submission"**
   - ชี้ให้เห็นแบบฟอร์มการส่งงาน: รองรับทั้งชื่อเรื่อง, สาขา, แผนก, รายชื่อผู้วิจัยร่วม, บทคัดย่อแบบมีโครงสร้าง, และการอัปโหลดไฟล์ PDF ฉบับเต็ม
   - คลิก **"Back to Workspace"** เพื่อเตรียมเข้าสู่ขั้นตอนถัดไป

---

### 🎬 Scene 2: การคัดกรองและมอบหมายผู้ตรวจ พร้อมระบบ COI Guard (Charlie - 1 นาที)
**เป้าหมาย:** เน้นย้ำระบบป้องกันผลประโยชน์ทับซ้อน (COI Guard) ว่าผู้แต่งจะไม่มีทางตรวจบทความของตนเองได้เด็ดขาด

1. **การคลิก:**
   - ที่แถบ Demo Switcher ด้านบน คลิกเลือก **📋 Charlie Vance (Coordinator)**
   - ระบบจะนำไปยัง **Triage Desk** (`/coordinator/triage/`) โดยอัตโนมัติ
2. **การนำเสนอ:**
   - *คำบรรยายผู้พูด:*
     > "เมื่อผู้วิจัยส่งบทความเข้ามา จะผ่านการคัดกรองโดย Coordinator C ซึ่งเป็นเลขาธิการวิจัยของโรงพยาบาล ในหน้านี้เราสามารถกรองดูตามสถานะได้ เช่น รอคัดกรอง (Pending Triage), อยู่ระหว่างตรวจ (In Peer Review), หรือตีพิมพ์แล้ว (Published)"
3. **การคลิกแสดง COI Guard:**
   - ในตาราง หาบทความ **Paper 1: Randomized Evaluation of SGLT2 Inhibition** (ซึ่งผู้วิจัยหลักคือ **Dr. Alice Mercer**)
   - คลิกปุ่ม **"Assign Reviewers"**
   - หน้าต่าง Modal จะเด้งขึ้นมา ชี้ให้เห็นกล่องสีเหลือง:
     > ⚠️ **"Conflict of Interest (COI) Active: Author Alice Mercer is strictly excluded from assignable reviewers."**
   - ชี้ให้คณะกรรมการดูรายชื่อในกล่อง: **มีชื่อ Dr. Robert Chen (Surgery) ให้เลือก แต่ไม่มีชื่อ Dr. Alice Mercer อย่างเด็ดขาด!**
   - *คำบรรยายผู้พูด:*
     > "นี่คือกฎเหล็กของระบบเราครับ COI Guard ทำงานตั้งแต่ระดับ Database Queryset ทำให้แพทย์ผู้วิจัยจะไม่มีทางถูกมอบหมายให้ตรวจบทความของตนเองได้เด็ดขาด ช่วยรักษามาตรฐานจริยธรรมการแพทย์ในระดับสูงสุดครับ"
   - กดปิด Modal

---

### 🎬 Scene 3: โต๊ะตรวจบทความแบบแยกสองจอ Split-Screen Desk (Dr. Bob - 1 นาที)
**เป้าหมาย:** แสดงความสะดวกในการอ่าน PDF คู่ขนานกับการกรอกแบบประเมิน 3 มิติทางการแพทย์

1. **การคลิก:**
   - ที่แถบ Demo Switcher คลิกเลือก **🔪 Robert Chen (Doctor - Surgery)**
   - ในหน้า Doctor Workspace คลิกแท็บ **"Assigned Peer Reviews"**
   - ชี้ให้เห็น Paper 2: *Laparoscopic vs Robotic-Assisted Hepatectomy*
   - คลิกปุ่ม **"Open Review Desk"**
2. **การนำเสนอ:**
   - *คำบรรยายผู้พูด:*
     > "นี่คือหน้าจอ Split-Screen Review Desk ที่แพทย์ผู้ตรวจบทความจะได้ใช้งานครับ โดยเราแบ่งหน้าจอออกเป็น 2 ฝั่ง: ฝั่งซ้ายคือโปรแกรมอ่านเอกสาร PDF ของบทความวิจัยที่ถูกสตรีมมิ่งอย่างปลอดภัย ผู้ตรวจสามารถซูมเข้า-ออก หรือเปิดเต็มจอได้ ส่วนฝั่งขวาคือแบบประเมิน 3 มิติมาตรฐานทางการแพทย์ ได้แก่:
     > 1. เค้าโครง (Structure & Methodology)
     > 2. บทนำ (Introduction & Literature)
     > 3. บทขยาย (Results, Data & Discussion)
     > พร้อมทั้งสามารถเลือกข้อเสนอแนะว่าจะให้แก้ไข (Request Revisions) หรือให้ผ่าน (Approve as Final) และแนบไฟล์ PDF ที่ตรวจแล้วกลับมาได้ด้วยครับ"

---

### 🎬 Scene 4: การสังเคราะห์ความเห็นและการรับประกัน Air-Gap (Charlie & Dr. Alice - 1 นาที)
**เป้าหมาย:** แสดงกระบวนการ Double-Blind Proxy ที่ผู้แต่งจะไม่เห็นชื่อหรือข้อความดิบของผู้ตรวจ

1. **การคลิก:**
   - ที่แถบ Demo Switcher คลิกเลือก **📋 Charlie Vance (Coordinator)**
   - ไปที่หน้า Triage Desk และเปิดบทความที่ตรวจเสร็จแล้ว เช่น Paper 3 หรือ Paper 4
   - ชี้ให้เห็นปุ่ม **"Consolidation Desk"**
2. **การนำเสนอ:**
   - *คำบรรยายผู้พูด:*
     > "เมื่อผู้ตรวจส่งข้อคิดเห็นเข้ามา ข้อความดิบจะส่งตรงมายังเลขาธิการวิจัยเท่านั้น ในหน้านี้ Coordinator จะเห็นข้อคิดเห็นของผู้ตรวจทุกคนแบบ Side-by-Side จากนั้น Coordinator จะทำหน้าที่สังเคราะห์เป็นคำสั่งทบทวนเดียว (Consolidated Coordinator Directives) โดยไม่เปิดเผยชื่อผู้ตรวจเลยครับ"
3. **การพิสูจน์ Air-Gap จากมุมมองผู้วิจัย:**
   - คลิก Demo Switcher สลับกลับไปเป็น **🩺 Alice Mercer (Doctor - Cardiology)**
   - เปิดหน้ารายละเอียดบทความ **Paper 3 Dossier**
   - ชี้ให้เห็นว่าในประวัติ Multi-Round: **แสดงเฉพาะกล่องสีฟ้า Coordinator Letter จาก Charlie เท่านั้น ไม่ปรากฏชื่อ Dr. Robert Chen หรือข้อความดิบของผู้ตรวจเลยแม้แต่คำเดียว**

---

### 🎬 Scene 5: คลังงานวิจัยและการขอเปิดสิทธิ์อ่าน Time-Bound Access Gate (Dr. Sarah & Charlie - 1 นาที)
**เป้าหมาย:** แสดงระบบคลังบทความที่เผยแพร่ และการขอ/อนุมัติบัตรผ่านอ่านเอกสารฉบับเต็ม

1. **การคลิก:**
   - ที่แถบ Demo Switcher คลิกเลือก **🔬 Sarah Jenkins (Staff Clinician - Emergency)**
   - ในแถบนำทาง คลิก **"Research Catalog"** (`/catalog/`)
2. **การนำเสนอ:**
   - *คำบรรยายผู้พูด:*
     > "เมื่อบทความวิจัยได้รับการรับรองและล็อกการตีพิมพ์ (PUBLISHED) จะเข้ามาอยู่ใน Research Catalog สาธารณะของโรงพยาบาล บุคลากรทุกคนสามารถค้นหาด้วยคีย์เวิร์ด เช่น พิมพ์คำว่า 'Stroke' หรือ 'Thrombectomy' เพื่ออ่านบทคัดย่อได้ทันที"
3. **การสาธิตการล็อกสิทธิ์ (Access Gate):**
   - เลื่อนลงมาที่บทความ Paper 5: *Long-term Neurological Outcomes Following Endovascular Thrombectomy*
   - ชี้ให้เห็นป้ายสีแดง: 🔒 **"Full-Text PDF Gated (Access Pass Required)"**
   - *คำบรรยายผู้พูด:*
     > "หากแพทย์ท่านอื่นหรือแพทย์ประจำบ้านต้องการอ่านเอกสารฉบับเต็ม ระบบจะล็อกไว้ด้วย Access Gate หากพยายามเปิดไฟล์ตรงๆ ระบบจะตอบกลับด้วย HTTP 403 Forbidden ทันทีครับ"
   - คลิกปุ่ม **"Request Full-Text Access Pass"**
   - แสดงหน้าต่างเลือกบัตรผ่าน 7 วัน, 14 วัน หรือ 30 วัน พร้อมกรอกเหตุผลทางคลินิก
4. **การอนุมัติบัตรผ่าน:**
   - สลับ Demo Switcher ไปที่ **📋 Charlie Vance (Coordinator)**
   - คลิกเมนู **"Access Passes Queue"** (`/coordinator/access-requests/`)
   - ในตาราง Pending กดปุ่มเขียว **"Grant Pass (14d)"**
   - สลับกลับมาที่ **🔬 Sarah Jenkins** แล้วรีเฟรชหน้า Research Catalog
   - ชี้ให้เห็นป้ายเปลี่ยนเป็นสีเขียว: 🔓 **"Pass Active • Expires: [วันที่]"** และมีปุ่ม **"Read Full Manuscript PDF"**
   - คลิกเปิดไฟล์ PDF ฉบับเต็มให้คณะกรรมการชมบนหน้าจออย่างราบรื่น

---

### สรุปปิดการนำเสนอ (Closing Pitch - 15 วินาที)
> *"MedResearch DMS มอบความมั่นใจให้โรงพยาบาล ทั้งด้านความโปร่งใสทางจริยธรรมวิจัยด้วย COI Guard, ความเป็นกลางด้วย Air-Gapped Mediation, และความปลอดภัยในการปกป้องทรัพย์สินทางปัญญาด้วย Time-Bound Access Gate ขอขอบพระคุณคณะกรรมการทุกท่านครับ"*
