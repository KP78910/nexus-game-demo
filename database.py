"""SQLite for local demos, PostgreSQL when DATABASE_URL is configured."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQLITE_FILE = ROOT / 'game_shop.db'
POSTGRES_SCHEMA = ROOT / 'sql' / 'schema_postgres.sql'

TABLES = (
    ('STAFF', 'staff_id'),
    ('PROMOTION', 'promotion_id'),
    ('TIME_PACKAGE', 'package_id'),
    ('TIME_CODE', 'time_code_id'),
    ('COMPUTER', 'computer_id'),
    ('SALE', 'sale_id'),
    ('SALE_DETAIL', 'sale_detail_id'),
    ('USAGE_SESSION', 'session_id'),
    ('PAYMENT', 'payment_id'),
    ('AUDIT_LOG', 'log_id'),
)


def engine():
    return 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'


class HybridRow(dict):
    """Match sqlite3.Row's support for both column names and positions."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def hybrid_row(cursor):
    names = [column.name for column in cursor.description]
    return lambda values: HybridRow(zip(names, values))


class PostgresConnection:
    def __init__(self, url):
        import psycopg
        self.raw = psycopg.connect(url, autocommit=True, row_factory=hybrid_row)

    def execute(self, statement, params=()):
        if statement.strip().upper() == 'BEGIN IMMEDIATE':
            statement = 'BEGIN'
        return self.raw.execute(statement.replace('?', '%s'), params)

    def executemany(self, statement, rows):
        with self.raw.cursor() as cursor:
            cursor.executemany(statement.replace('?', '%s'), rows)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect():
    url = os.environ.get('DATABASE_URL')
    if url:
        return PostgresConnection(url)
    conn = sqlite3.connect(SQLITE_FILE, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


def initialize_postgres(conn):
    for statement in POSTGRES_SCHEMA.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            conn.execute(statement)


def import_sqlite_once(conn):
    """Copy the tracked demo data only when the PostgreSQL database is empty."""
    conn.execute('BEGIN')
    try:
        conn.execute('SELECT pg_advisory_xact_lock(73429051)')
        if conn.execute('SELECT COUNT(*) FROM STAFF').fetchone()[0]:
            conn.commit()
            return False
        if not SQLITE_FILE.exists():
            conn.commit()
            return False
        source = sqlite3.connect(f'file:{SQLITE_FILE.as_posix()}?mode=ro', uri=True)
        source.row_factory = sqlite3.Row
        try:
            for table, primary_key in TABLES:
                cursor = source.execute(f'SELECT * FROM {table} ORDER BY {primary_key}')
                columns = [column[0] for column in cursor.description]
                rows = [tuple(row) for row in cursor]
                if not rows:
                    continue
                placeholders = ','.join('?' for _ in columns)
                conn.executemany(
                    f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholders})', rows
                )
                conn.execute(
                    'SELECT setval(pg_get_serial_sequence(?, ?), ?, true)',
                    (table.lower(), primary_key, max(row[0] for row in rows)),
                )
        finally:
            source.close()
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
