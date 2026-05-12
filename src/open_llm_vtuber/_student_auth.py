"""學生身分驗證（簡易版）。

設計：
- vtuber-poc 把學生名單存在同一支 SQLite 的 `students` table
  - 由 admin SPA 預先註冊；admin 沒做 UI 之前，預設 `ALLOW_STUDENT_AUTOREGISTER=true`
    讓學生第一次登入時自動建一筆（DEV 友善）
- 表結構：device_id PRIMARY KEY, name, class_name, created_at, last_login_at
- METRICS_DB env 共用 vtuber-poc 那支 SQLite

⚠️ schema / 正則 SOURCE OF TRUTH：本檔案
   vtuber-poc/src/admin_server.py 的 students CRUD 必須與這裡保持一致
   (DEVICE_ID_PATTERN / STUDENTS_SCHEMA_SQL)
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from typing import Optional, Tuple

# device_id 格式：字母 / 數字 / 底線 / dash / 中文，最多 32 字
DEVICE_ID_PATTERN = r"^[A-Za-z0-9_\-\u4e00-\u9fff]{1,32}$"
_DEVICE_RE = re.compile(DEVICE_ID_PATTERN)

STUDENTS_SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS students (
    device_id TEXT PRIMARY KEY,
    name TEXT,
    class_name TEXT,
    created_at INTEGER NOT NULL,
    last_login_at INTEGER
)"""


def _db_path() -> str:
    return os.environ.get("METRICS_DB") or "data/poc.db"


def _ensure_table(con: sqlite3.Connection) -> None:
    con.execute(STUDENTS_SCHEMA_SQL)
    # 既存 DB migration：補 last_login_at 欄位
    cols = {r[1] for r in con.execute("PRAGMA table_info(students)").fetchall()}
    if "last_login_at" not in cols:
        con.execute("ALTER TABLE students ADD COLUMN last_login_at INTEGER")


def _connect() -> sqlite3.Connection:
    # WAL + busy_timeout：解決 OLV (12393) 與 admin (8765) 同時寫入時的鎖定問題
    con = sqlite3.connect(_db_path(), timeout=5.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
    except sqlite3.Error:
        pass
    _ensure_table(con)
    return con


def is_valid_device_id(device_id: str) -> bool:
    return bool(device_id) and bool(_DEVICE_RE.match(device_id))


def find_student(device_id: str) -> Optional[dict]:
    if not is_valid_device_id(device_id):
        return None
    con = _connect()
    try:
        row = con.execute(
            "SELECT device_id, name, class_name, created_at, last_login_at FROM students WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def autoregister() -> bool:
    val = os.environ.get("ALLOW_STUDENT_AUTOREGISTER", "true").lower()
    return val in ("1", "true", "yes", "on")


def _touch_login(con: sqlite3.Connection, device_id: str, ts: int) -> None:
    con.execute("UPDATE students SET last_login_at = ? WHERE device_id = ?", (ts, device_id))


def login(device_id: str, name: str = "") -> Tuple[bool, dict]:
    """回傳 (ok, student_dict_or_error)。"""
    if not is_valid_device_id(device_id):
        return False, {"error": "device_id 格式不合法 (僅允許字母/數字/中文，最多 32 字)"}
    now = int(time.time())
    student = find_student(device_id)
    if student:
        # 已存在：更新 last_login_at；name 參數一律忽略，避免冒名覆寫
        con = _connect()
        try:
            _touch_login(con, device_id, now)
            con.commit()
        finally:
            con.close()
        student["last_login_at"] = now
        return True, student
    if not autoregister():
        return False, {"error": "找不到學生，請聯絡老師註冊"}
    # auto register
    name = (name or "").strip()[:64]
    con = _connect()
    try:
        con.execute(
            "INSERT INTO students (device_id, name, class_name, created_at, last_login_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (device_id, name, "", now, now),
        )
        con.commit()
    finally:
        con.close()
    return True, {
        "device_id": device_id, "name": name, "class_name": "",
        "created_at": now, "last_login_at": now, "auto_registered": True,
    }
