"""Game Shop demo, Python 3 standard library only. Run: python server.py"""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / 'game_shop.db'
SCHEMA_FILE = ROOT / 'sql' / 'schema.sql'
STATIC = ROOT / 'static'
TH = timezone(timedelta(hours=7))
SESSIONS = {}
AUTH_LOCK = threading.Lock()

class AppError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def th_date():
    return datetime.now(TH).date().isoformat()

def db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 250_000)
    return f'{salt.hex()}:{result.hex()}'

def valid_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(':', 1)
        value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 250_000)
        return hmac.compare_digest(value, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def init_database():
    conn = db_connection()
    conn.executescript(SCHEMA_FILE.read_text(encoding='utf-8'))
    if conn.execute('SELECT COUNT(*) FROM STAFF').fetchone()[0] == 0:
        conn.execute('INSERT INTO STAFF(staff_name,username,password_hash,role) VALUES(?,?,?,?)',
                     ('เจ้าของร้าน', 'admin01', hash_password('demo1234'), 'ADMIN'))
        conn.execute('INSERT INTO STAFF(staff_name,username,password_hash,role) VALUES(?,?,?,?)',
                     ('พนักงานขาย', 'staff01', hash_password('demo1234'), 'STAFF'))
    if conn.execute('SELECT COUNT(*) FROM TIME_PACKAGE').fetchone()[0] == 0:
        conn.executemany('INSERT INTO TIME_PACKAGE(package_name,duration_minutes,price) VALUES(?,?,?)',
                         [('1 ชั่วโมง', 60, 30), ('2 ชั่วโมง', 120, 60), ('3 ชั่วโมง', 180, 80)])
    if conn.execute('SELECT COUNT(*) FROM COMPUTER').fetchone()[0] == 0:
        conn.executemany('INSERT INTO COMPUTER(computer_name,machine_status,location) VALUES(?,?,?)',
                         [('PC-01','READY','โซน A'), ('PC-02','READY','โซน A'),
                          ('PC-03','READY','โซน B'), ('PC-04','MAINTENANCE','โซน B')])
    if conn.execute('SELECT COUNT(*) FROM PROMOTION').fetchone()[0] == 0:
        conn.execute('INSERT INTO PROMOTION(promotion_name,discount_type,discount_value,start_date,end_date,promotion_status) VALUES(?,?,?,?,?,?)',
                     ('ลด 10% สำหรับ Demo', 'PERCENT', 10, '2020-01-01', '2099-12-31', 'ACTIVE'))
    conn.close()

def user_from_token(token):
    if not token:
        return None
    with AUTH_LOCK:
        rec = SESSIONS.get(token)
        if rec is None or rec['expires'] < time.monotonic():
            SESSIONS.pop(token, None)
            return None
        return rec['user']

def require_user(user, admin=False):
    if not user:
        raise AppError('กรุณาเข้าสู่ระบบพนักงานก่อน', 401)
    if admin and user['role'] != 'ADMIN':
        raise AppError('เฉพาะเจ้าของร้าน (ADMIN) ที่ใช้งานส่วนนี้ได้', 403)
    return user

def money(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def created_code(conn):
    for _ in range(10):
        code = secrets.token_hex(6).upper()
        if not conn.execute('SELECT 1 FROM TIME_CODE WHERE code_value=?', (code,)).fetchone():
            return code
    raise AppError('ไม่สามารถสร้างรหัสได้ กรุณาลองใหม่', 500)

def parsed_time(value):
    return datetime.fromisoformat(value)

def calc_seconds(conn, time_code_id):
    purchased = conn.execute('''SELECT COALESCE(SUM(d.added_minutes),0)
      FROM SALE_DETAIL d JOIN SALE s ON s.sale_id=d.sale_id
      WHERE d.time_code_id=? AND s.sale_status='COMPLETED' ''', (time_code_id,)).fetchone()[0] * 60
    rows = conn.execute('SELECT start_time,end_time FROM USAGE_SESSION WHERE time_code_id=?', (time_code_id,)).fetchall()
    now = datetime.now(timezone.utc)
    used = 0
    for row in rows:
        begin = parsed_time(row['start_time'])
        end = parsed_time(row['end_time']) if row['end_time'] else now
        used += max(0, int((end - begin).total_seconds()))
    return max(0, int(purchased - used))

def refresh_expired(conn):
    rows = conn.execute('SELECT session_id,time_code_id,start_time FROM USAGE_SESSION WHERE session_status="ACTIVE"').fetchall()
    for row in rows:
        if calc_seconds(conn,row['time_code_id']) == 0:
            conn.execute('UPDATE USAGE_SESSION SET end_time=?, session_status="ENDED" WHERE session_id=?', (now_iso(),row['session_id']))
            write_audit(conn, None, 'AUTO_END', 'USAGE_SESSION', row['session_id'], 'เวลาหมด ระบบปิด Session อัตโนมัติ')

def write_audit(conn, user, action, table, entity_id, desc):
    conn.execute('''INSERT INTO AUDIT_LOG(staff_id,actor_type,action_type,target_table,target_id,action_time,description)
       VALUES(?,?,?,?,?,?,?)''',
       (user['staff_id'] if user else None, 'STAFF' if user else 'SYSTEM', action,
        table,str(entity_id),now_iso(),desc))

def sale_price(conn, package_id, promo_id):
    p = conn.execute('SELECT * FROM TIME_PACKAGE WHERE package_id=? AND package_status="ACTIVE"', (package_id,)).fetchone()
    if not p:
        raise AppError('ไม่พบแพ็กเกจที่เปิดขาย')
    price = money(p['price'])
    promo = None
    discount = 0.0
    if promo_id:
        promo = conn.execute('SELECT * FROM PROMOTION WHERE promotion_id=? AND promotion_status="ACTIVE"', (promo_id,)).fetchone()
        if not promo or not (promo['start_date'] <= th_date() <= promo['end_date']):
            raise AppError('โปรโมชั่นนี้ไม่สามารถใช้ได้')
        if promo['discount_type'] == 'PERCENT':
            discount = money(Decimal(str(price)) * Decimal(str(promo['discount_value'])) / Decimal(100))
        else:
            discount = money(promo['discount_value'])
    discount = min(discount,price)
    amount = money(price - discount)
    if amount <= 0:
        raise AppError('Demo นี้ไม่รองรับการชำระเงินยอด 0 บาท')
    return p, amount, discount

def sale_transaction(user, data, topup=False):
    require_user(user)
    try:
        pid = int(data.get('package_id'))
        promo_id = int(data['promotion_id']) if data.get('promotion_id') else None
    except (ValueError, TypeError):
        raise AppError('กรุณาเลือกแพ็กเกจที่ถูกต้อง')
    method = data.get('payment_method','CASH')
    if method not in ('CASH','QR_DEMO'):
        raise AppError('วิธีชำระเงินไม่ถูกต้อง')
    if not data.get('confirmed'):
        raise AppError('ต้องยืนยันการรับชำระเงินก่อน')
    conn = db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        refresh_expired(conn)
        package, amount, discount = sale_price(conn,pid,promo_id)
        if topup:
            value = str(data.get('code_value', '')).strip().upper()
            tc = conn.execute('SELECT * FROM TIME_CODE WHERE code_value=? AND code_status="ACTIVE"', (value,)).fetchone()
            if not tc:
                raise AppError('ไม่พบรหัสที่ใช้งานได้สำหรับเติมเวลา')
            cid = tc['time_code_id']
            code = tc['code_value']
        else:
            code = created_code(conn)
            cur = conn.execute('INSERT INTO TIME_CODE(code_value,created_at,code_status) VALUES(?,?,"ACTIVE")', (code,now_iso()))
            cid = cur.lastrowid
        cur = conn.execute('''INSERT INTO SALE(staff_id,promotion_id,sale_date,discount_amount,sale_status)
            VALUES(?,?,?,?,"PENDING")''', (user['staff_id'],promo_id,now_iso(),discount))
        sid = cur.lastrowid
        conn.execute('''INSERT INTO PAYMENT(sale_id,payment_method,payment_amount,payment_status,paid_at)
            VALUES(?,?,?,"SUCCESS",?)''', (sid,method,amount,now_iso()))
        conn.execute('''INSERT INTO SALE_DETAIL(sale_id,package_id,time_code_id,sale_type,added_minutes,unit_price)
            VALUES(?,?,?,?,?,?)''', (sid,pid,cid,'TOPUP' if topup else 'NEW',package['duration_minutes'],package['price']))
        conn.execute('UPDATE SALE SET sale_status="COMPLETED" WHERE sale_id=?',(sid,))
        write_audit(conn,user,'TOPUP_TIME' if topup else 'CREATE_SALE','SALE',sid,
                    f'{code}: {package["package_name"]}, รับชำระ {amount:.2f} บาท')
        remaining = calc_seconds(conn,cid)
        conn.commit()
        return dict(sale_id=sid,code_value=code,package_name=package['package_name'],
                    added_minutes=package['duration_minutes'],amount=amount,discount=discount,
                    remaining_seconds=remaining,payment_method=method,sale_type='TOPUP' if topup else 'NEW')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def start_session(data):
    code = str(data.get('code_value','')).strip().upper()
    try: comp_id = int(data.get('computer_id'))
    except (TypeError,ValueError): raise AppError('เลือกเครื่องไม่ถูกต้อง')
    conn = db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        refresh_expired(conn)
        tc = conn.execute('SELECT * FROM TIME_CODE WHERE code_value=?', (code,)).fetchone()
        pc = conn.execute('SELECT * FROM COMPUTER WHERE computer_id=?',(comp_id,)).fetchone()
        if not pc or pc['machine_status'] != 'READY':
            raise AppError('เครื่องนี้ไม่พร้อมให้บริการ')
        if not tc or tc['code_status'] != 'ACTIVE':
            raise AppError('รหัสไม่ถูกต้องหรือถูกปิดใช้งาน')
        if calc_seconds(conn,tc['time_code_id']) <= 0:
            raise AppError('รหัสนี้ไม่มีเวลาเล่นคงเหลือ กรุณาเติมเวลา')
        if conn.execute('SELECT 1 FROM USAGE_SESSION WHERE time_code_id=? AND session_status="ACTIVE"',(tc['time_code_id'],)).fetchone():
            raise AppError('รหัสนี้กำลังใช้งานอยู่บนเครื่องอื่น ไม่สามารถใช้ซ้ำได้',409)
        if conn.execute('SELECT 1 FROM USAGE_SESSION WHERE computer_id=? AND session_status="ACTIVE"',(comp_id,)).fetchone():
            raise AppError('เครื่องนี้มีผู้เล่นใช้งานอยู่แล้ว',409)
        cur=conn.execute('''INSERT INTO USAGE_SESSION(time_code_id,computer_id,start_time,session_status)
          VALUES(?,?,?,"ACTIVE")''',(tc['time_code_id'],comp_id,now_iso()))
        write_audit(conn,None,'START_SESSION','USAGE_SESSION',cur.lastrowid,f'{pc["computer_name"]}: เริ่มใช้รหัส {code}')
        conn.commit()
        return dict(session_id=cur.lastrowid,computer_name=pc['computer_name'],code_value=code,
                    remaining_seconds=calc_seconds(conn,tc['time_code_id']))
    except sqlite3.IntegrityError:
        conn.rollback()
        raise AppError('เครื่องหรือรหัสกำลังถูกใช้งานอยู่แล้ว',409)
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def end_session(data,user=None):
    try: comp_id=int(data.get('computer_id'))
    except (TypeError,ValueError): raise AppError('กรุณาระบุเครื่อง')
    code=str(data.get('code_value','')).strip().upper()
    conn=db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        item=conn.execute('''SELECT s.*,t.code_value FROM USAGE_SESSION s
          JOIN TIME_CODE t ON s.time_code_id=t.time_code_id
          WHERE s.computer_id=? AND s.session_status='ACTIVE' ''',(comp_id,)).fetchone()
        if not item: raise AppError('ไม่พบ Session ที่กำลังใช้งาน')
        if (not user or user['role']!='ADMIN') and code != item['code_value']:
            raise AppError('รหัสไม่ตรงกับ Session ที่กำลังใช้งาน',403)
        conn.execute('UPDATE USAGE_SESSION SET end_time=?,session_status="ENDED" WHERE session_id=?',(now_iso(),item['session_id']))
        write_audit(conn,user,'END_SESSION','USAGE_SESSION',item['session_id'],'ออกจากเครื่องโดยผู้ใช้')
        remaining=calc_seconds(conn,item['time_code_id'])
        conn.commit()
        return dict(remaining_seconds=remaining)
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def get_state(user):
    conn=db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        refresh_expired(conn)
        conn.commit()
        pcs=[]
        for item in conn.execute('''SELECT c.computer_id,c.computer_name,c.machine_status,c.location,
          s.session_id,s.time_code_id,t.code_value
          FROM COMPUTER c LEFT JOIN USAGE_SESSION s
            ON c.computer_id=s.computer_id AND s.session_status='ACTIVE'
          LEFT JOIN TIME_CODE t ON s.time_code_id=t.time_code_id
          ORDER BY c.computer_id'''):
            r=dict(item)
            r['occupied']=r['session_id'] is not None
            r['remaining_seconds']=calc_seconds(conn,r['time_code_id']) if r['occupied'] else None
            if not user: r.pop('code_value',None)
            pcs.append(r)
        packages=[dict(r) for r in conn.execute('SELECT * FROM TIME_PACKAGE WHERE package_status="ACTIVE" ORDER BY duration_minutes')]
        promotions=[dict(r) for r in conn.execute('''SELECT * FROM PROMOTION WHERE promotion_status="ACTIVE"
             AND start_date<=? AND end_date>=? ORDER BY promotion_id''',(th_date(),th_date()))]
        data=dict(computers=pcs,packages=packages,promotions=promotions,user=user,
                  stats=dict(total=len(pcs),available=sum(p['machine_status']=='READY' and not p['occupied'] for p in pcs),
                  busy=sum(p['occupied'] for p in pcs),maintenance=sum(p['machine_status']!='READY' for p in pcs)))
        if user:
            recent=[]
            for row in conn.execute('''SELECT s.sale_id,s.sale_date,s.sale_status,t.code_value,
              d.sale_type,d.added_minutes,p.payment_method,p.payment_amount
              FROM SALE s JOIN SALE_DETAIL d ON s.sale_id=d.sale_id
              JOIN TIME_CODE t ON d.time_code_id=t.time_code_id
              JOIN PAYMENT p ON p.sale_id=s.sale_id AND p.payment_status='SUCCESS'
              ORDER BY s.sale_id DESC LIMIT 8'''):
                recent.append(dict(row))
            data['recent_sales']=recent
        return data
    finally: conn.close()

def get_reports(user):
    require_user(user,admin=True)
    conn=db_connection()
    try:
        # Each transaction contributes just once to revenue, not per payment attempt.
        sales=[dict(row) for row in conn.execute('''SELECT s.sale_id,s.sale_date,s.sale_status,s.discount_amount,
            f.staff_name, p.payment_method, p.payment_amount, t.code_value,
            d.sale_type,d.added_minutes,k.package_name
            FROM SALE s JOIN STAFF f ON f.staff_id=s.staff_id
            JOIN SALE_DETAIL d ON d.sale_id=s.sale_id
            JOIN TIME_PACKAGE k ON k.package_id=d.package_id
            JOIN TIME_CODE t ON t.time_code_id=d.time_code_id
            JOIN PAYMENT p ON p.sale_id=s.sale_id AND p.payment_status='SUCCESS'
            WHERE s.sale_status='COMPLETED' ORDER BY s.sale_id DESC''')]
        # Demo supports one successful payment and one detail per sale.
        today=th_date()
        today_rows=[s for s in sales if parsed_time(s['sale_date']).astimezone(TH).date().isoformat()==today]
        by_pack={}
        for s in today_rows:
            by_pack[s['package_name']]=money(by_pack.get(s['package_name'],0)+s['payment_amount'])
        return dict(today=today,revenue=money(sum(s['payment_amount'] for s in today_rows)),
                    sales_count=len(today_rows),new_codes=sum(s['sale_type']=='NEW' for s in today_rows),
                    topups=sum(s['sale_type']=='TOPUP' for s in today_rows),
                    packages=[dict(name=k,amount=v) for k,v in by_pack.items()],sales=sales[:50])
    finally: conn.close()

def get_audit(user):
    require_user(user,admin=True)
    conn=db_connection()
    try:
        return [dict(row) for row in conn.execute('''SELECT l.*,s.staff_name FROM AUDIT_LOG l
        LEFT JOIN STAFF s ON s.staff_id=l.staff_id ORDER BY log_id DESC LIMIT 80''')]
    finally: conn.close()

def reset_demo(user):
    require_user(user,admin=True)
    conn=db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        for t in ('USAGE_SESSION','AUDIT_LOG','PAYMENT','SALE_DETAIL','SALE','TIME_CODE'):
            conn.execute(f'DELETE FROM {t}')
        conn.commit()
        return {'reset':True}
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

class Handler(BaseHTTPRequestHandler):
    server_version='GameShopDemo/1.0'
    def log_message(self, fmt,*args):
        print('[HTTP]',fmt%args)
    def _user_token(self):
        jar=cookies.SimpleCookie()
        try: jar.load(self.headers.get('Cookie',''))
        except cookies.CookieError: return None,None
        t=jar.get('gs_session')
        token=t.value if t else None
        return user_from_token(token), token
    def respond(self,status,data,extra_headers=None):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        for k,v in (extra_headers or {}).items(): self.send_header(k,v)
        self.end_headers()
        self.wfile.write(body)
    def read_json(self):
        if 'application/json' not in self.headers.get('Content-Type',''):
            raise AppError('ต้องส่งข้อมูลเป็น JSON')
        n=int(self.headers.get('Content-Length','0'))
        if n<=0 or n>100_000:
            raise AppError('ขนาดข้อมูลไม่ถูกต้อง')
        try: return json.loads(self.rfile.read(n))
        except json.JSONDecodeError: raise AppError('JSON ไม่ถูกต้อง')
    def handle_route(self,post=False):
        user,token=self._user_token()
        path=urlsplit(self.path).path
        if post:
            data=self.read_json()
            if path=='/api/login':
                username=str(data.get('username','')).strip()
                password=str(data.get('password',''))
                conn=db_connection()
                try: record=conn.execute('SELECT * FROM STAFF WHERE username=? AND staff_status="ACTIVE"',(username,)).fetchone()
                finally: conn.close()
                if not record or not valid_password(password,record['password_hash']):
                    raise AppError('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง',401)
                payload={k:record[k] for k in ('staff_id','staff_name','username','role')}
                t=secrets.token_urlsafe(32)
                with AUTH_LOCK: SESSIONS[t]={'user':payload,'expires':time.monotonic()+8*3600}
                return self.respond(200,{'user':payload},{'Set-Cookie':f'gs_session={t}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
            if path=='/api/logout':
                with AUTH_LOCK: SESSIONS.pop(token,None)
                return self.respond(200,{'ok':True},{'Set-Cookie':'gs_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/sale': return self.respond(200,sale_transaction(user,data))
            if path=='/api/topup': return self.respond(200,sale_transaction(user,data,True))
            if path=='/api/session/start': return self.respond(200,start_session(data))
            if path=='/api/session/end': return self.respond(200,end_session(data,user))
            if path=='/api/reset': return self.respond(200,reset_demo(user))
            raise AppError('ไม่พบ API',404)
        else:
            if path=='/api/me':return self.respond(200,{'user':user})
            if path=='/api/state':return self.respond(200,get_state(user))
            if path=='/api/reports':return self.respond(200,get_reports(user))
            if path=='/api/audit':return self.respond(200,get_audit(user))
            raise AppError('ไม่พบ API',404)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/api/'):
            try: return self.handle_route()
            except AppError as e: return self.respond(e.code,{'error':str(e)})
            except Exception as e:
                print('ERROR',repr(e))
                return self.respond(500,{'error':'เกิดข้อผิดพลาดภายในระบบ'})
        mapping={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/app.js':'app.js'}
        filename=mapping.get(path)
        if not filename:
            self.send_error(404)
            return
        data=(STATIC/filename).read_bytes()
        mime=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)
    def do_POST(self):
        try: self.handle_route(post=True)
        except AppError as e: self.respond(e.code,{'error':str(e)})
        except Exception as e:
            print('ERROR',repr(e))
            self.respond(500,{'error':'เกิดข้อผิดพลาดภายในระบบ'})

def main():
    init_database()
    port = int(os.environ.get('PORT', '8000'))
    host = '0.0.0.0' if 'PORT' in os.environ else '127.0.0.1'
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Game Shop ready: http://{host}:{port}')
    print('Demo: admin01 / demo1234 | staff01 / demo1234')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
