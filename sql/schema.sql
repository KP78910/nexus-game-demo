PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS STAFF (
 staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
 staff_name TEXT NOT NULL,
 username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('ADMIN','STAFF')),
 staff_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(staff_status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS PROMOTION (
 promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
 promotion_name TEXT NOT NULL,
 discount_type TEXT NOT NULL CHECK(discount_type IN ('PERCENT','FIXED')),
 discount_value NUMERIC NOT NULL CHECK(discount_value >= 0),
 start_date TEXT NOT NULL,
 end_date TEXT NOT NULL,
 promotion_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(promotion_status IN ('ACTIVE','INACTIVE')),
 CHECK(end_date >= start_date),
 CHECK(discount_type != 'PERCENT' OR discount_value <= 100)
);

CREATE TABLE IF NOT EXISTS TIME_PACKAGE (
 package_id INTEGER PRIMARY KEY AUTOINCREMENT,
 package_name TEXT NOT NULL,
 duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
 price NUMERIC NOT NULL CHECK(price >= 0),
 package_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(package_status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS TIME_CODE (
 time_code_id INTEGER PRIMARY KEY AUTOINCREMENT,
 code_value TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL,
 code_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(code_status IN ('ACTIVE','DISABLED','EXPIRED'))
);

CREATE TABLE IF NOT EXISTS COMPUTER (
 computer_id INTEGER PRIMARY KEY AUTOINCREMENT,
 computer_name TEXT NOT NULL UNIQUE,
 machine_status TEXT NOT NULL DEFAULT 'READY' CHECK(machine_status IN ('READY','MAINTENANCE','OFFLINE')),
 location TEXT
);

CREATE TABLE IF NOT EXISTS SALE (
 sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
 staff_id INTEGER NOT NULL REFERENCES STAFF(staff_id) ON DELETE RESTRICT,
 promotion_id INTEGER REFERENCES PROMOTION(promotion_id) ON DELETE RESTRICT,
 sale_date TEXT NOT NULL,
 discount_amount NUMERIC NOT NULL DEFAULT 0 CHECK(discount_amount >= 0),
 sale_status TEXT NOT NULL CHECK(sale_status IN ('PENDING','COMPLETED','CANCELLED'))
);

CREATE TABLE IF NOT EXISTS SALE_DETAIL (
 sale_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
 sale_id INTEGER NOT NULL REFERENCES SALE(sale_id) ON DELETE RESTRICT,
 package_id INTEGER NOT NULL REFERENCES TIME_PACKAGE(package_id) ON DELETE RESTRICT,
 time_code_id INTEGER NOT NULL REFERENCES TIME_CODE(time_code_id) ON DELETE RESTRICT,
 sale_type TEXT NOT NULL CHECK(sale_type IN ('NEW','TOPUP')),
 added_minutes INTEGER NOT NULL CHECK(added_minutes > 0),
 unit_price NUMERIC NOT NULL CHECK(unit_price >= 0)
);

CREATE TABLE IF NOT EXISTS USAGE_SESSION (
 session_id INTEGER PRIMARY KEY AUTOINCREMENT,
 time_code_id INTEGER NOT NULL REFERENCES TIME_CODE(time_code_id) ON DELETE RESTRICT,
 computer_id INTEGER NOT NULL REFERENCES COMPUTER(computer_id) ON DELETE RESTRICT,
 start_time TEXT NOT NULL,
 end_time TEXT,
 session_status TEXT NOT NULL CHECK(session_status IN ('ACTIVE','ENDED')),
 CHECK(end_time IS NULL OR end_time >= start_time),
 CHECK((session_status='ACTIVE' AND end_time IS NULL) OR (session_status='ENDED' AND end_time IS NOT NULL))
);

-- Explicitly forbid concurrent use of the same code or the same PC.
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_time_code
 ON USAGE_SESSION(time_code_id) WHERE session_status='ACTIVE';
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_computer
 ON USAGE_SESSION(computer_id) WHERE session_status='ACTIVE';

CREATE TABLE IF NOT EXISTS PAYMENT (
 payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
 sale_id INTEGER NOT NULL REFERENCES SALE(sale_id) ON DELETE RESTRICT,
 payment_method TEXT NOT NULL CHECK(payment_method IN ('CASH','QR_DEMO')),
 payment_amount NUMERIC NOT NULL CHECK(payment_amount > 0),
 payment_status TEXT NOT NULL CHECK(payment_status IN ('PENDING','SUCCESS','FAILED','REFUNDED')),
 paid_at TEXT,
 transaction_ref TEXT UNIQUE,
 CHECK(payment_status!='SUCCESS' OR paid_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS AUDIT_LOG (
 log_id INTEGER PRIMARY KEY AUTOINCREMENT,
 staff_id INTEGER REFERENCES STAFF(staff_id) ON DELETE RESTRICT,
 action_type TEXT NOT NULL,
 target_table TEXT NOT NULL,
 target_id TEXT NOT NULL,
 action_time TEXT NOT NULL,
 description TEXT,
 actor_type TEXT NOT NULL CHECK(actor_type IN ('STAFF','SYSTEM')),
 CHECK((actor_type='SYSTEM' AND staff_id IS NULL) OR (actor_type='STAFF' AND staff_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_sale_date ON SALE(sale_date);
CREATE INDEX IF NOT EXISTS idx_sale_detail_sale ON SALE_DETAIL(sale_id);
CREATE INDEX IF NOT EXISTS idx_payment_sale ON PAYMENT(sale_id);
CREATE INDEX IF NOT EXISTS idx_audit_at ON AUDIT_LOG(action_time);
