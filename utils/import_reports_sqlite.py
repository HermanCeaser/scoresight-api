#!/usr/bin/env python3
import os
import json
import argparse
import sqlite3
from sqlite3 import Error

# —— DEFAULT DB FILE —— #
DEFAULT_DB = 'reports.db'
# ---------------------- #

EXAM_TYPES = {'Midterm', 'End of Term', 'Beginning of Term', 'Mocks'}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS exams (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT    NOT NULL UNIQUE,
  type        TEXT    NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  CHECK(type IN ('Midterm','End of Term','Beginning of Term','Mocks'))
);

CREATE TABLE IF NOT EXISTS exam_reports (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_id       INTEGER NULL,
  student_name  TEXT    NULL,
  class_name    TEXT    NULL,
  subject_name  TEXT    NOT NULL DEFAULT 'SST',
  question_no   INTEGER NULL,
  question      TEXT    NULL,
  answer        TEXT    NULL,
  page_number   INTEGER NULL,
  grading       TEXT    NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE SET NULL
);
"""

def init_db(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()

def get_or_create_exam(conn: sqlite3.Connection, name: str, exam_type: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM exams WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO exams (name, type) VALUES (?, ?)",
        (name, exam_type)
    )
    conn.commit()
    return cur.lastrowid

# map JSON keys → DB column names
KEY_MAP = {
    'studentName': 'student_name',
    'questionNo':  'question_no',
    'pageNumber':  'page_number',
    'className':   'class_name',
    'subjectName': 'subject_name',
    # the rest already match:
    # 'question' → 'question'
    # 'answer'   → 'answer'
    # 'grading'  → 'grading'
    # plus the defaults/exam_id you'll add below
}

def import_reports(db_file, data_dir, exam_name, exam_type, subject, class_name, do_export):
    if exam_type not in EXAM_TYPES:
        raise ValueError(f"exam_type must be one of {EXAM_TYPES}")

    conn = sqlite3.connect(db_file)
    init_db(conn)

    exam_id = get_or_create_exam(conn, exam_name, exam_type)
    print(f"📝 Using exam_id={exam_id} for '{exam_name}' ({exam_type})")

    cur = conn.cursor()
    for fname in os.listdir(data_dir):
        if not fname.lower().endswith('.jsonl'):
            continue
        path = os.path.join(data_dir, fname)
        inserted = 0

        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                raw = json.loads(line)

                record = {}
                for k, v in raw.items():
                    # skip empty values right here if you like, or do it later
                    if v in (None, ""):
                        continue
                    col = KEY_MAP.get(k, k)   # default to k itself if not in KEY_MAP
                    record[col] = v

                if not record:
                    continue

                # apply defaults/overrides
                record['exam_id']      = exam_id
                record['subject_name'] = record.get('subject_name') or subject
                record['class_name']   = record.get('class_name')   or class_name

                # drop truly empty
                clean = {k: v for k,v in record.items() if v not in (None, "")}
                if not clean:
                    continue

                cols = ', '.join(clean.keys())
                qs   = ', '.join('?' for _ in clean)
                sql  = f"INSERT INTO exam_reports ({cols}) VALUES ({qs})"
                try:
                    cur.execute(sql, list(clean.values()))
                    inserted += 1
                except Error as e:
                    print(f"⚠️  Skipped record in {fname}: {e}")

        conn.commit()
        print(f"Imported {inserted} rows from {fname}")

    # ——— EXPORT TO SQL DUMP (optional) ——— #
    if do_export:
        dump_path = f"{db_file}.sql"
        with open(dump_path, 'w', encoding='utf-8') as dump_file:
            for line in conn.iterdump():
                dump_file.write(f"{line}\n")
        print(f"💾 Database exported to {dump_path}")

    conn.close()
    print("✅ All done!")

if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description="Import exam_reports JSONL into SQLite and export SQL dump"
    )
    p.add_argument(
        "--db", "-d",
        default=DEFAULT_DB,
        help="Path to SQLite DB file (will be created if missing)"
    )
    p.add_argument(
        "--data-dir", "-D",
        required=True,
        help="Folder containing .jsonl files"
    )
    p.add_argument(
        "--exam-name", "-n",
        required=True,
        help="Unique exam name, e.g. 'Term I MidTerm 2025'"
    )
    p.add_argument(
        "--exam-type", "-t",
        choices=list(EXAM_TYPES),
        required=True
    )
    p.add_argument(
        "--subject", "-s",
        default="SST",
        help="Default subject_name"
    )
    p.add_argument(
        "--class-name", "-c",
        required=True,
        help="Default class_name"
    )
    p.add_argument(
        "--export", "-x",
        action="store_true",
        help="After importing, export full SQL dump to <db>.sql"
    )
    args = p.parse_args()

    import_reports(
        db_file    = args.db,
        data_dir   = args.data_dir,
        exam_name  = args.exam_name,
        exam_type  = args.exam_type,
        subject    = args.subject,
        class_name = args.class_name,
        do_export  = args.export
    )
