# NEXUS GAME — ระบบจัดการร้านเกม (Demo สำหรับนำเสนออาจารย์)

ตัวอย่างเว็บแอป UI ภาษาไทย ใช้ **PostgreSQL บน Render** และใช้ SQLite เมื่อลองรันในเครื่องโดยไม่ตั้ง `DATABASE_URL`

## วิธีเปิดใช้งาน (Windows / macOS / Linux)

1. ติดตั้ง Python 3.10 หรือใหม่กว่า ถ้ายังไม่มี
2. แตกไฟล์ ZIP แล้วเปิด Terminal / Command Prompt ในโฟลเดอร์ `game-shop-demo`
3. รันคำสั่ง:

   ```sh
   python server.py
   ```

   ถ้าเครื่อง Windows ใช้ `py server.py` ได้
4. เปิดเว็บเบราว์เซอร์ที่ `http://127.0.0.1:8000`
5. หยุด Server ด้วย `Ctrl + C`

ฐานข้อมูล `game_shop.db` ถูกสร้างอัตโนมัติในการเปิดครั้งแรก และบันทึกข้อมูลข้ามการเปิดเว็บใหม่

หากต้องการรันกับ PostgreSQL ในเครื่อง ให้ติดตั้ง `requirements.txt` แล้วตั้ง `DATABASE_URL`
เป็น connection string ของ PostgreSQL ก่อนรันเซิร์ฟเวอร์

## เปิดบน Render

รีโปมี `render.yaml` สำหรับ Python Web Service แผน Free: Build Command คือ
`pip install -r requirements.txt && python -m py_compile server.py database.py`
และ Start Command คือ `python server.py`.
เซิร์ฟเวอร์จะรับพอร์ตจากตัวแปร `PORT` ของ Render โดยอัตโนมัติ

บริการใช้ฐานข้อมูล Render PostgreSQL ชื่อ `nexus-game-demo-db` ใน Singapore
ตั้งตัวแปร `DATABASE_URL` ใน Web Service เป็น **Internal Database URL** ของฐานข้อมูลนี้
(หรือให้ Blueprint ดึง `connectionString` ด้วย `fromDatabase`).
เมื่อเปิดบริการครั้งแรก ระบบสร้าง 10 ตารางจาก `sql/schema_postgres.sql`
และคัดลอกข้อมูลตัวอย่างจาก `game_shop.db` เข้า PostgreSQL เพียงครั้งเดียว
หลังจากนั้น PostgreSQL เป็นแหล่งข้อมูลจริงและจะไม่คัดลอกทับเมื่อ deploy ใหม่

หาก `DATABASE_URL` ไม่ถูกตั้ง เว็บจะกลับไปใช้ SQLite ซึ่งเป็นไฟล์ชั่วคราวบน Render
Render PostgreSQL แผน Free เก็บข้อมูลข้าม deploy ได้ แต่มีขนาด 1 GB
และหมดอายุ 30 วันหลังสร้าง (ฐานข้อมูลนี้หมดอายุ 11 พฤศจิกายน 2026)
ควรสำรองข้อมูลหรืออัปเกรดก่อนวันดังกล่าว

## บัญชี Demo

- พนักงาน: **staff01 / demo1234**
- เจ้าของร้าน: **admin01 / demo1234**

โปรดอย่าใช้บัญชี/รหัสผ่าน Demo นี้กับระบบจริง

## ฟังก์ชันที่ทำงานได้

- Dashboard สถานะเครื่องคอมพิวเตอร์ คำนวณจาก Active Session
- ขายเวลา รับชำระเงินสดหรือ **QR จำลอง** และสร้างรหัสแบบสุ่ม
- หน้าเครื่องลูกค้ากรอกรหัสเพื่อเริ่มใช้งาน
- ป้องกัน Active Session ซ้ำทั้ง **รหัสเดียวกัน** และ **เครื่องเดียวกัน** ด้วย Unique Index ที่ฐานข้อมูล
- ออกจากเครื่องแล้วกลับมาใช้งานใหม่ได้หากยังมีเวลาเหลือ
- เติมเวลาลงรหัสเดิมผ่านรายการขายใหม่
- รายงานยอดขายรายวัน แพ็กเกจยอดนิยม จำนวนขายใหม่/เติมเวลา (Admin)
- Audit Log (Admin)
- ดูข้อมูล 10 ตารางจากฐานข้อมูลที่เว็บกำลังใช้อยู่ (Admin, อ่านอย่างเดียว; ซ่อน password_hash)
- รีเซ็ตข้อมูลการขายเพื่อ Demo ใหม่ (Admin)

## Demo 5 ขั้นตามเกณฑ์อาจารย์

1. **ก่อนทำ:** Login `staff01`, เปิด Dashboard แสดง PC-01 ว่าง
2. **ฟังก์ชันหลัก:** เข้าหน้า "ขายรหัสเวลา" เลือก 2 ชั่วโมง ราคา 60 บาท ติ๊กยืนยันรับเงิน กดขาย คัดลอกรหัส → ไปหน้า "เครื่องลูกค้า" เลือก PC-01 กรอกรหัส กดเข้าใช้งาน
3. **หลังทำ:** Login `admin01` แล้วเปิด "ตารางฐานข้อมูล" กดรีเฟรชเพื่อดูแถวที่เพิ่มหรือแก้ไขใน `SALE`, `PAYMENT`, `TIME_CODE`, `SALE_DETAIL`, `USAGE_SESSION`, `AUDIT_LOG` ส่วน `COMPUTER` ไม่ต้อง UPDATE เพราะสถานะมีคนใช้คำนวณจาก Active Session
4. **กรณีปฏิเสธ:** เลือก PC-02 กรอกรหัสเดิมจาก PC-01 → UI แจ้งว่าใช้รหัสซ้ำ ไม่เปิด Session ใหม่
5. **ผลลัพธ์:** ออกจากบัญชี staff, Login `admin01`, เปิด "รายงานยอดขาย" → เห็นรายได้ รายการขาย และรหัสที่เพิ่งขาย

เพิ่มเติม: หน้า "เติมเวลาเล่น" ใช้รหัสเดิม เพิ่ม 60 นาที แล้วดูเวลาคงเหลือของ PC-01 เปลี่ยน

## ฐานข้อมูล 3NF — 10 ตาราง

ดู SQL DDL ที่ `sql/schema_postgres.sql` สำหรับ Render และ `sql/schema.sql` สำหรับ SQLite ในเครื่อง

- STAFF, PROMOTION, TIME_PACKAGE, TIME_CODE, COMPUTER
- SALE, SALE_DETAIL, USAGE_SESSION, PAYMENT, AUDIT_LOG

เวลาคงเหลือคำนวณจากการขาย/เติมเวลาที่ COMPLETED ลบกับระยะเวลาของ Session ทั้งที่จบและกำลังทำงาน จึงไม่มีคอลัมน์ `remaining_minutes` ใน TIME_CODE เวอร์ชันนี้

## ขอบเขตสำคัญ

- **หน้าเครื่องลูกค้าเป็นตัวจำลองในเว็บ**: ยังไม่มี Client Agent สำหรับล็อก/ปลดล็อก Windows หรือควบคุมเครื่องจริง
- **QR เป็นการรับเงินแบบจำลอง**: ไม่มีการสร้าง QR PromptPay หรือตรวจสอบจากธนาคารจริง
- ระบบ Demo มีบัญชีเริ่มต้นแบบคงที่; ต้องเพิ่ม HTTPS, CSRF protection, password reset, rate limiting, role-management และระบบสำรอง/กู้คืนก่อนเปิดใช้จริงบนเครือข่ายสาธารณะ
- เวลาเก็บเป็น timestamp UTC และรายงานวันนี้ใช้เขตเวลา Asia/Bangkok (+07:00)
- การขาย Demo รองรับแพ็กเกจ **หนึ่งรายการต่อหนึ่ง SALE** แต่แยก SALE_DETAIL เพื่อรองรับการขยายในอนาคต
- การตรวจสอบ Session แบบฝั่ง Server เหมาะกับ Demo; ระบบจริงต้องมี Client Agent และกลไก heartbeat เพื่อจัดการเครื่องขัดข้อง

## ตรวจสอบฐานข้อมูล SQL

บน Render ดูผ่านเมนู "ตารางฐานข้อมูล" ในเว็บ หรือเชื่อมด้วยไคลเอนต์ PostgreSQL เช่น pgAdmin แล้วทดลอง:

```sql
SELECT * FROM SALE ORDER BY sale_id DESC;
SELECT * FROM PAYMENT ORDER BY payment_id DESC;
SELECT * FROM TIME_CODE ORDER BY time_code_id DESC;
SELECT * FROM SALE_DETAIL ORDER BY sale_detail_id DESC;
SELECT * FROM USAGE_SESSION ORDER BY session_id DESC;
SELECT * FROM AUDIT_LOG ORDER BY log_id DESC;

-- ต้องไม่มีรหัสที่ ACTIVE ซ้ำ
SELECT time_code_id, COUNT(*) AS n
FROM USAGE_SESSION WHERE session_status='ACTIVE'
GROUP BY time_code_id HAVING COUNT(*) > 1;
```
