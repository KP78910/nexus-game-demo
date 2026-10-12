# NEXUS GAME — ระบบจัดการร้านเกม (Demo สำหรับนำเสนออาจารย์)

ตัวอย่างเว็บแอป UI ภาษาไทย เชื่อมกับฐานข้อมูล **SQLite จริง** โดยใช้ Python 3 standard library เท่านั้น (ไม่ต้องติดตั้ง Flask หรือ npm)

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

## เปิดบน Render

รีโปมี `render.yaml` สำหรับสร้าง Python Web Service แผน Free: Build Command คือ
`python -m py_compile server.py` และ Start Command คือ `python server.py`.
เซิร์ฟเวอร์จะรับพอร์ตจากตัวแปร `PORT` ของ Render โดยอัตโนมัติ

แผน Free ใช้พื้นที่ไฟล์ชั่วคราว การขายและการใช้งานที่บันทึกใน SQLite บนเว็บจะย้อนกลับ
ไปเป็นข้อมูลใน `game_shop.db` ที่อยู่ในรีโปเมื่อบริการรีสตาร์ตหรือ deploy ใหม่
หากต้องการเก็บข้อมูลต่อเนื่อง ต้องใช้พื้นที่เก็บข้อมูลถาวรและปรับตำแหน่งไฟล์ฐานข้อมูล

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
- ดูข้อมูล 10 ตารางจาก SQLite ที่เว็บกำลังใช้อยู่ (Admin, อ่านอย่างเดียว; ซ่อน password_hash)
- รีเซ็ตข้อมูลการขายเพื่อ Demo ใหม่ (Admin)

## Demo 5 ขั้นตามเกณฑ์อาจารย์

1. **ก่อนทำ:** Login `staff01`, เปิด Dashboard แสดง PC-01 ว่าง
2. **ฟังก์ชันหลัก:** เข้าหน้า "ขายรหัสเวลา" เลือก 2 ชั่วโมง ราคา 60 บาท ติ๊กยืนยันรับเงิน กดขาย คัดลอกรหัส → ไปหน้า "เครื่องลูกค้า" เลือก PC-01 กรอกรหัส กดเข้าใช้งาน
3. **หลังทำ:** Login `admin01` แล้วเปิด "ตารางฐานข้อมูล" กดรีเฟรชเพื่อดูแถวที่เพิ่มหรือแก้ไขใน `SALE`, `PAYMENT`, `TIME_CODE`, `SALE_DETAIL`, `USAGE_SESSION`, `AUDIT_LOG` (หรือเปิดไฟล์ `game_shop.db` ด้วย SQLite Browser เมื่อรันในเครื่อง) ส่วน `COMPUTER` ไม่ต้อง UPDATE เพราะสถานะมีคนใช้คำนวณจาก Active Session
4. **กรณีปฏิเสธ:** เลือก PC-02 กรอกรหัสเดิมจาก PC-01 → UI แจ้งว่าใช้รหัสซ้ำ ไม่เปิด Session ใหม่
5. **ผลลัพธ์:** ออกจากบัญชี staff, Login `admin01`, เปิด "รายงานยอดขาย" → เห็นรายได้ รายการขาย และรหัสที่เพิ่งขาย

เพิ่มเติม: หน้า "เติมเวลาเล่น" ใช้รหัสเดิม เพิ่ม 60 นาที แล้วดูเวลาคงเหลือของ PC-01 เปลี่ยน

## ฐานข้อมูล 3NF — 10 ตาราง

ดู SQL DDL ที่ `sql/schema.sql`

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

เปิดด้วย DB Browser for SQLite และทดลอง:

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
