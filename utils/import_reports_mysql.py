#!/usr/bin/env python3
import os
import json
import argparse
import subprocess
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
import re
from pathlib import Path
from datetime import datetime

# —— CONFIGURE YOUR MySQL CONNECTION HERE —— #
DB_CONFIG = {
    'host':       'localhost',
    'user':       'admin',
    'password':   'password',
    'database':   'scoresight',
    'charset':    'utf8mb4',
    'autocommit': False,
}
# --------------------------------------------- #

EXAM_TYPES = {'Midterm', 'End of Term', 'Beginning of Term', 'Mocks'}

SCHEMA_MYSQL = """
CREATE TABLE IF NOT EXISTS `exams` (
  `id`          INT AUTO_INCREMENT PRIMARY KEY,
  `name`        VARCHAR(255)   NOT NULL,
  `type`        ENUM('Midterm','End of Term','Beginning of Term','Mocks') NOT NULL,
  `created_at`  TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uniq_exam_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `exam_reports` (
  `id`            INT AUTO_INCREMENT PRIMARY KEY,
  `exam_id`       INT            NULL,
  `student_name`  VARCHAR(255)   NULL,
  `class_name`    VARCHAR(100)   NULL,
  `subject_name`  VARCHAR(100)   NOT NULL DEFAULT 'SST',
  `question_no`   VARCHAR(50)    NULL,
  `question`      TEXT           NULL,
  `answer`        TEXT           NULL,
  `page_number`   INT            NULL,
  `grading`       VARCHAR(50)    NULL,
  `created_at`    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_exam_id` (`exam_id`),
  CONSTRAINT `fk_exam_reports_exams`
    FOREIGN KEY (`exam_id`)
    REFERENCES `exams`(`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

KEY_MAP = {
    'studentname': 'student_name',
    'student_name': 'student_name',
    'student name': 'student_name',
    'questionno': 'question_no',
    'question_no': 'question_no',
    'question no': 'question_no',
    'question number': 'question_no',
    'pagenumber': 'page_number',
    'page_number': 'page_number',
    'page number': 'page_number',
    'classname': 'class_name',
    'class_name': 'class_name',
    'class name': 'class_name',
    'subjectname': 'subject_name',
    'subject_name': 'subject_name',
    'subject name': 'subject_name',
    'question': 'question',
    'answer': 'answer',
    'grading': 'grading',
    'grade': 'grading',
    'marks': 'grading',
    'score': 'grading'
}

# Define valid database columns (excluding auto-generated fields)
VALID_DB_COLUMNS = {
    'exam_id', 'student_name', 'class_name', 'subject_name', 
    'question_no', 'question', 'answer', 'page_number', 'grading'
}

def normalize_column_name(col_name):
    """
    Normalize column names to handle different naming conventions
    """
    if not col_name:
        return ''
    # Convert to lowercase and replace underscores/spaces with spaces
    normalized = re.sub(r'[_\s]+', ' ', str(col_name).lower().strip())
    # Remove extra spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized

def map_column_to_db_field(col_name):
    """
    Map a column name to database field using flexible matching
    """
    normalized = normalize_column_name(col_name)
    return KEY_MAP.get(normalized, normalized.replace(' ', '_'))

def read_file_data(file_path):
    """
    Read data from JSONL, CSV, or XLSX files
    Returns a list of dictionaries
    """
    file_path = Path(file_path)
    file_ext = file_path.suffix.lower()
    
    data = []
    
    if file_ext == '.jsonl':
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
    
    elif file_ext == '.csv':
        df = pd.read_csv(file_path)
        # Replace NaN values with None
        df = df.where(pd.notna(df), None)
        data = df.to_dict('records')
    
    elif file_ext in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
        # Replace NaN values with None
        df = df.where(pd.notna(df), None)
        data = df.to_dict('records')
    
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Supported formats: .jsonl, .csv, .xlsx, .xls")
    
    return data

def get_supported_files(path):
    """
    Get all supported files from a directory or return the single file if path is a file
    """
    path = Path(path)
    supported_extensions = {'.jsonl', '.csv', '.xlsx', '.xls'}
    
    if path.is_file():
        if path.suffix.lower() in supported_extensions:
            return [path]
        else:
            raise ValueError(f"File {path} has unsupported format. Supported: {supported_extensions}")
    
    elif path.is_dir():
        files = []
        for file_path in path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                files.append(file_path)
        return files
    
    else:
        raise ValueError(f"Path {path} does not exist or is not a file/directory")

def connect_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print("❌ DB connection error:", err)
        raise

def init_db(conn):
    cursor = conn.cursor()
    for stmt in SCHEMA_MYSQL.strip().split(';'):
        if stmt.strip():
            cursor.execute(stmt)
    conn.commit()
    cursor.close()

def get_or_create_exam(conn, name, exam_type):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM exams WHERE name = %s", (name,))
    row = cursor.fetchone()
    if row:
        exam_id = row[0]
    else:
        cursor.execute(
            "INSERT INTO exams (name, type) VALUES (%s, %s)",
            (name, exam_type)
        )
        conn.commit()
        exam_id = cursor.lastrowid
    cursor.close()
    return exam_id

def import_reports(data_path, exam_name, exam_type, default_subject, default_class_name, do_export):
    # Generate default exam name if not provided
    if not exam_name:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        exam_name = f"Exam_{timestamp}"
    
    # Use default exam type if not provided
    if not exam_type:
        exam_type = "Midterm"  # Default to Midterm
    
    if exam_type not in EXAM_TYPES:
        raise ValueError(f"exam_type must be one of {EXAM_TYPES}")

    conn = connect_db()
    init_db(conn)

    exam_id = get_or_create_exam(conn, exam_name, exam_type)
    print(f"📝 Using exam_id={exam_id} for '{exam_name}' ({exam_type})")

    overall_total = 0
    overall_inserted = 0

    cursor = conn.cursor()
    
    # Get all supported files
    files = get_supported_files(data_path)
    
    if not files:
        print("❌ No supported files found (.jsonl, .csv, .xlsx, .xls)")
        return
    
    print(f"📂 Found {len(files)} supported file(s) to process")
    
    for file_path in files:
        print(f"🔄 Processing: {file_path.name}")
        
        try:
            raw_data = read_file_data(file_path)
        except Exception as e:
            print(f"❌ Error reading {file_path.name}: {e}")
            continue
        
        total = 0
        inserted = 0

        for raw_record in raw_data:
            if not raw_record:
                continue
                
            # 1) remap keys & drop empty values
            record = {}
            for k, v in raw_record.items():
                if v in (None, "", "nan", "NaN"):
                    continue
                    
                # Map column name to database field
                db_field = map_column_to_db_field(k)
                
                # Only keep columns that exist in the database schema
                if db_field in VALID_DB_COLUMNS:
                    record[db_field] = v
                else:
                    # Optionally log unknown columns (uncomment if needed for debugging)
                    # print(f"🔍 Ignoring unknown column: {k} -> {db_field}")
                    pass
                
            if not record:
                continue

            total += 1
            
            # 2) apply defaults/overrides
            record['exam_id'] = exam_id
            
            # Use subject_name from data if available, otherwise use default
            if 'subject_name' not in record or not record['subject_name']:
                record['subject_name'] = default_subject
            
            # Use class_name from data if available, otherwise use default
            if 'class_name' not in record or not record['class_name']:
                if default_class_name:
                    record['class_name'] = default_class_name
                # If no default class_name provided and none in data, leave as None

            # 3) build & execute INSERT (skip duplicates)
            cols = ', '.join(f"`{c}`" for c in record.keys())
            placeholders = ', '.join(['%s'] * len(record))
            sql = f"INSERT INTO `exam_reports` ({cols}) VALUES ({placeholders})"

            try:
                cursor.execute(sql, list(record.values()))
                inserted += 1
            except mysql.connector.Error as e:
                if e.errno == errorcode.ER_DUP_ENTRY:
                    # duplicate, just skip
                    continue
                else:
                    print(f"⚠️  Skipped record in {file_path.name}: {e}")

        conn.commit()
        overall_total += total
        overall_inserted += inserted
        print(f"✅ Imported {inserted}/{total} rows from {file_path.name}")

    cursor.close()
    conn.close()

    print(f"🎉 Data import complete: {overall_inserted}/{overall_total} total rows inserted.")

    if do_export:
        dump_file = f"{DB_CONFIG['database']}_dump.sql"
        cmd = [
            "mysqldump",
            f"-h{DB_CONFIG['host']}",
            f"-u{DB_CONFIG['user']}",
            f"-p{DB_CONFIG['password']}",
            DB_CONFIG['database']
        ]
        with open(dump_file, 'w', encoding='utf-8') as out:
            result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"💾 Database dump written to `{dump_file}`")
        else:
            print("❌ mysqldump failed:", result.stderr)

if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description="Import exam_reports from JSONL/CSV/XLSX files into MySQL and export full SQL dump"
    )
    p.add_argument(
        "--data-path", "-d", 
        required=True, 
        help="File path or directory containing supported files (.jsonl, .csv, .xlsx, .xls)"
    )
    p.add_argument(
        "--exam-name", "-n", 
        required=False, 
        help="Unique exam name (auto-generated if not provided), e.g. 'Term I Midterm 2025'"
    )
    p.add_argument(
        "--exam-type", "-t",
        choices=list(EXAM_TYPES),
        required=False,
        default="Midterm",
        help="Exam type (default: Midterm)"
    )
    p.add_argument(
        "--subject", "-s", 
        default="SST", 
        help="Default subject_name (used when not found in data)"
    )
    p.add_argument(
        "--class-name", "-c", 
        required=False, 
        help="Default class_name (used when not found in data)"
    )
    p.add_argument(
        "--export", "-x",
        action="store_true",
        help="After importing, export full SQL dump to <database>_dump.sql"
    )
    args = p.parse_args()

    import_reports(
        data_path=args.data_path,
        exam_name=args.exam_name,
        exam_type=args.exam_type,
        default_subject=args.subject,
        default_class_name=args.class_name,
        do_export=args.export
    )
