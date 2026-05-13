import csv
import json
import sqlite3
from pathlib import Path

from flask import render_template, redirect, url_for, flash, request
from werkzeug.utils import secure_filename
from sentence_transformers import SentenceTransformer

from check import check_files
import handlers.state as state


# ── Page renderer ────────────────────────────────────────────────────────────

def _upload_page():
    annotation = {
        'options': state.DATA['datasets'],
        'temp': state.DATABASE,
    }
    return render_template("upload.html", annotation=annotation)


# ── POST /save_and_next?type=upload dispatcher ────────────────────────────────

def save():
    state.DATABASE = request.form.get('selected_option')
    db = state.DATABASE
    if db == "OwnUpload":
        schema_file = request.files.get("schema_file")
        database_file = request.files.get("database_file")
        sql_file = request.files.get("sql_file")
        upload(schema_file, database_file, sql_file)
    logdata = _load_json(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    data_length = len(logdata)
    state.REL_TABLES = [''] * data_length
    state.REL_EXAMPLES = [''] * data_length
    return redirect(url_for("task_selection"))


# ── Upload logic (moved from root upload.py) ──────────────────────────────────

def upload(schema_file, database_file, sql_file):
    print("final")
    print("schema_file:", schema_file.filename if schema_file else None)
    print("database_file:", database_file.filename if database_file else None)
    print("sql_file:", sql_file.filename if sql_file else None)

    if not database_file or database_file.filename == "":
        flash("Database file is required.")
        return redirect(url_for("upload"))

    if not sql_file or sql_file.filename == "":
        flash("SQL file is required.")
        return redirect(url_for("upload"))

    database_filename = secure_filename(database_file.filename)
    sql_filename = secure_filename(sql_file.filename)

    dataset_name = Path(database_filename).stem
    dataset_dir = Path("./data") / dataset_name.lower()

    schema_dir = dataset_dir / "schema"
    database_dir = dataset_dir / "database"

    schema_dir.mkdir(parents=True, exist_ok=True)
    database_dir.mkdir(parents=True, exist_ok=True)

    database_path = database_dir / database_filename
    queries_json_path = dataset_dir / "queries.json"

    database_file.save(database_path)

    if schema_file and schema_file.filename:
        schema_filename = secure_filename(schema_file.filename)
        original_schema_path = schema_dir / schema_filename
        schema_file.save(original_schema_path)

    create_queries_json(sql_file, queries_json_path)

    tables_csv_path = generate_tables_csv_from_sqlite(
        sqlite_path=database_path,
        dataset_dir=dataset_dir
    )

    generate_tables_json_and_schema_csvs_from_sqlite(
        sqlite_path=database_path,
        dataset_dir=dataset_dir,
        dataset_name=dataset_name
    )

    valid, errors = check_files(
        str(queries_json_path),
        str(database_path),
        str(tables_csv_path)
    )

    if not valid:
        for error in errors:
            flash(error)
        return redirect(url_for("upload"))

    flash(f"Dataset '{dataset_name}' uploaded successfully.")
    return redirect(url_for("task_selection"))


def create_queries_json(uploaded_file, queries_json_path):
    filename = uploaded_file.filename.lower()
    uploaded_file.seek(0)

    if filename.endswith(".json"):
        data = json.load(uploaded_file)
        with open(queries_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return queries_json_path

    if filename.endswith(".sql"):
        sql_text = uploaded_file.read().decode("utf-8")
        queries = []
        for query in sql_text.split(";"):
            query = query.strip()
            if not query:
                continue
            queries.append({"sql": query + ";", "question": ""})
        with open(queries_json_path, "w", encoding="utf-8") as f:
            json.dump(queries, f, indent=4)
        return queries_json_path

    raise ValueError("Query file must be .json or .sql")


def generate_tables_csv_from_sqlite(sqlite_path, dataset_dir):
    dataset_dir = Path(dataset_dir)
    tables_csv_path = dataset_dir / "tables.csv"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    table_names = _get_table_names(cursor)

    with open(tables_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["table", "columnname", "data-type", "description"])
        writer.writeheader()
        for table_name in table_names:
            for column in _get_columns(cursor, table_name):
                writer.writerow({
                    "table": table_name,
                    "columnname": column["name"],
                    "data-type": column["type"],
                    "description": ""
                })

    conn.close()
    return tables_csv_path


def generate_tables_json_and_schema_csvs_from_sqlite(sqlite_path, dataset_dir, dataset_name):
    dataset_dir = Path(dataset_dir)
    schema_dir = dataset_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    tables_json_path = dataset_dir / "tables.json"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    table_names = _get_table_names(cursor)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    tables_json = []

    for table_name in table_names:
        columns = _get_columns(cursor, table_name)
        foreign_keys = _get_foreign_keys(cursor, table_name)

        schema_string = ",".join([table_name.upper()] + [c["name"] for c in columns])
        schema_embedding = model.encode(schema_string, convert_to_tensor=True).detach().cpu().numpy().tolist()

        tables_json.append({"schema": schema_string, "schema_embedding": schema_embedding})

        schema_csv_path = schema_dir / f"{dataset_name.upper()}-{table_name.upper()}.csv"
        with open(schema_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["COLUMN_NAME", "DATA_TYPE", "PKEY", "FKEY"])
            writer.writeheader()
            for column in columns:
                writer.writerow({
                    "COLUMN_NAME": column["name"],
                    "DATA_TYPE": column["type"],
                    "PKEY": "PRIMARY KEY" if column["pk"] else "",
                    "FKEY": foreign_keys.get(column["name"], "")
                })

    with open(tables_json_path, "w", encoding="utf-8") as f:
        json.dump(tables_json, f, indent=4)

    conn.close()
    return tables_json_path


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _get_table_names(cursor):
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def _get_columns(cursor, table_name):
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return [
        {"cid": r[0], "name": r[1], "type": r[2] or "text", "notnull": r[3], "default": r[4], "pk": r[5] > 0}
        for r in cursor.fetchall()
    ]


def _get_foreign_keys(cursor, table_name):
    cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
    fks = {}
    for r in cursor.fetchall():
        fks[r[3]] = f"FOREIGN KEY {r[2].upper()} ({r[4]})"
    return fks


def _load_json(file_name):
    with open(file_name + '.json', 'r') as f:
        return json.load(f)
