import csv
import json
import shutil
import sqlite3
from pathlib import Path

from flask import flash, redirect, url_for
from werkzeug.utils import secure_filename
from sentence_transformers import SentenceTransformer
from check import check_files
with open("config.json", "r") as json_file:
    DATA = json.load(json_file)
    print(DATA)
DATABASE = DATA ['datasets'][0]


def generate_schema_from_sqlite(sqlite_path, dataset_dir, dataset_name):
    """
    Creates:
      data/<dataset>/tables.json
      data/<dataset>/schema/<DATASET>-<TABLE>.csv

    tables.json format:
      [
        {
          "schema": "TABLE,COL1,COL2,...",
          "schema_embedding": [...]
        }
      ]
    """

    dataset_dir = Path(dataset_dir)
    schema_dir = dataset_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    tables_json_path = dataset_dir / "tables.json"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    table_names = [row[0] for row in cursor.fetchall()]

    model = SentenceTransformer("all-MiniLM-L6-v2")

    tables_json = []

    for table_name in table_names:
        columns = get_sqlite_columns(cursor, table_name)
        foreign_keys = get_sqlite_foreign_keys(cursor, table_name)

        schema_string = ",".join(
            [table_name.upper()] + [column["name"] for column in columns]
        )

        schema_embedding = model.encode(
            schema_string,
            convert_to_tensor=True
        ).detach().cpu().numpy().tolist()

        tables_json.append({
            "schema": schema_string,
            "schema_embedding": schema_embedding
        })

        schema_csv_name = f"{dataset_name.upper()}-{table_name.upper()}.csv"
        schema_csv_path = schema_dir / schema_csv_name

        with open(schema_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["COLUMN_NAME", "DATA_TYPE", "PKEY", "FKEY"]
            )
            writer.writeheader()

            for column in columns:
                column_name = column["name"]

                pkey = "PRIMARY KEY" if column["pk"] else ""
                fkey = foreign_keys.get(column_name, "")

                writer.writerow({
                    "COLUMN_NAME": column_name,
                    "DATA_TYPE": column["type"],
                    "PKEY": pkey,
                    "FKEY": fkey
                })

    with open(tables_json_path, "w", encoding="utf-8") as f:
        json.dump(tables_json, f, indent=4)

    conn.close()

    return tables_json_path, schema_dir


def get_sqlite_columns(cursor, table_name):
    cursor.execute(f'PRAGMA table_info("{table_name}")')

    columns = []

    for row in cursor.fetchall():
        # row format:
        # cid, name, type, notnull, dflt_value, pk
        columns.append({
            "cid": row[0],
            "name": row[1],
            "type": row[2] or "text",
            "notnull": row[3],
            "default": row[4],
            "pk": row[5] > 0
        })

    return columns


def get_sqlite_foreign_keys(cursor, table_name):
    cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')

    foreign_keys = {}

    for row in cursor.fetchall():
        # row format:
        # id, seq, table, from, to, on_update, on_delete, match
        referenced_table = row[2]
        from_column = row[3]
        referenced_column = row[4]

        foreign_keys[from_column] = (
            f"FOREIGN KEY {referenced_table.upper()} ({referenced_column})"
        )

    return foreign_keys

def generate_tables_csv_from_sqlite(sqlite_path, dataset_dir):
    """
    Creates data/<dataset>/tables.csv in checker format:

    table,columnname,data-type,description
    CUSTOMERS,CustomerID,INTEGER,
    CUSTOMERS,Segment,TEXT,
    """

    dataset_dir = Path(dataset_dir)
    tables_csv_path = dataset_dir / "tables.csv"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    table_names = [row[0] for row in cursor.fetchall()]

    with open(tables_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["table", "columnname", "data-type", "description"]
        )
        writer.writeheader()

        for table_name in table_names:
            cursor.execute(f'PRAGMA table_info("{table_name}")')

            for row in cursor.fetchall():
                column_name = row[1]
                data_type = row[2] or "text"

                writer.writerow({
                    "table": table_name,
                    "columnname": column_name,
                    "data-type": data_type,
                    "description": ""
                })

    conn.close()

    return tables_csv_path


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
    dataset_dir = DATABASE / dataset_name

    schema_dir = dataset_dir / "schema"
    database_dir = dataset_dir / "database"

    schema_dir.mkdir(parents=True, exist_ok=True)
    database_dir.mkdir(parents=True, exist_ok=True)

    database_path = database_dir / database_filename
    queries_json_path = dataset_dir / "queries.json"

    # Save uploaded SQLite database
    database_file.save(database_path)

    # Optional: save original uploaded schema file, if provided
    if schema_file and schema_file.filename:
        schema_filename = secure_filename(schema_file.filename)
        original_schema_path = schema_dir / schema_filename
        schema_file.save(original_schema_path)

    # Create queries.json from uploaded .sql or .json file
    create_queries_json(sql_file, queries_json_path)

    # Generate these from the SQLite DB:
    #   data/<dataset>/tables.csv
    #   data/<dataset>/tables.json
    #   data/<dataset>/schema/<DATASET>-<TABLE>.csv
    tables_csv_path = generate_tables_csv_from_sqlite(
        sqlite_path=database_path,
        dataset_dir=dataset_dir
    )

    tables_json_path = generate_tables_json_and_schema_csvs_from_sqlite(
        sqlite_path=database_path,
        dataset_dir=dataset_dir,
        dataset_name=dataset_name
    )

    # Run your checker
    valid, errors = check_files(
        str(queries_json_path),
        str(database_path),
        str(tables_csv_path)
    )

    if not valid:
        for error in errors:
            flash(error)

        # Optional cleanup if invalid
        # shutil.rmtree(dataset_dir, ignore_errors=True)

        return redirect(url_for("upload"))

    flash(f"Dataset '{dataset_name}' uploaded successfully.")
    return redirect(url_for("task_selection"))



def create_queries_json(uploaded_file, queries_json_path):
    """
    Creates queries.json.

    If uploaded file is JSON, it should contain:
    [
        {
            "sql": "...",
            "question": "..."
        }
    ]

    If uploaded file is SQL, this creates:
    [
        {
            "sql": "SELECT ...;",
            "question": ""
        }
    ]
    """

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

        for i, query in enumerate(sql_text.split(";"), start=1):
            query = query.strip()

            if not query:
                continue

            queries.append({
                "sql": query + ";",
                "question": ""
            })

        with open(queries_json_path, "w", encoding="utf-8") as f:
            json.dump(queries, f, indent=4)

        return queries_json_path

    raise ValueError("Query file must be .json or .sql")

def generate_tables_csv_from_sqlite(sqlite_path, dataset_dir):
    """
    Creates checker-compatible tables.csv:

    table,columnname,data-type,description
    CUSTOMERS,CustomerID,INTEGER,
    CUSTOMERS,Segment,TEXT,
    """

    dataset_dir = Path(dataset_dir)
    tables_csv_path = dataset_dir / "tables.csv"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    table_names = get_sqlite_table_names(cursor)

    with open(tables_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["table", "columnname", "data-type", "description"]
        )
        writer.writeheader()

        for table_name in table_names:
            columns = get_sqlite_columns(cursor, table_name)

            for column in columns:
                writer.writerow({
                    "table": table_name,
                    "columnname": column["name"],
                    "data-type": column["type"],
                    "description": ""
                })

    conn.close()

    return tables_csv_path

def generate_tables_json_and_schema_csvs_from_sqlite(sqlite_path, dataset_dir, dataset_name):
    """
    Creates:
      data/<dataset>/tables.json
      data/<dataset>/schema/<DATASET>-<TABLE>.csv

    tables.json format:
      [
        {
          "schema": "CUSTOMERS,CustomerID,Segment,Currency",
          "schema_embedding": [...]
        }
      ]
    """

    dataset_dir = Path(dataset_dir)
    schema_dir = dataset_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    tables_json_path = dataset_dir / "tables.json"

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    table_names = get_sqlite_table_names(cursor)

    model = SentenceTransformer("all-MiniLM-L6-v2")

    tables_json = []

    for table_name in table_names:
        columns = get_sqlite_columns(cursor, table_name)
        foreign_keys = get_sqlite_foreign_keys(cursor, table_name)

        schema_string = ",".join(
            [table_name.upper()] + [column["name"] for column in columns]
        )

        schema_embedding = model.encode(
            schema_string,
            convert_to_tensor=True
        ).detach().cpu().numpy().tolist()

        tables_json.append({
            "schema": schema_string,
            "schema_embedding": schema_embedding
        })

        schema_csv_path = schema_dir / f"{dataset_name.upper()}-{table_name.upper()}.csv"

        with open(schema_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["COLUMN_NAME", "DATA_TYPE", "PKEY", "FKEY"]
            )
            writer.writeheader()

            for column in columns:
                column_name = column["name"]

                writer.writerow({
                    "COLUMN_NAME": column_name,
                    "DATA_TYPE": column["type"],
                    "PKEY": "PRIMARY KEY" if column["pk"] else "",
                    "FKEY": foreign_keys.get(column_name, "")
                })

    with open(tables_json_path, "w", encoding="utf-8") as f:
        json.dump(tables_json, f, indent=4)

    conn.close()

    return tables_json_path

def get_sqlite_table_names(cursor):
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    return [row[0] for row in cursor.fetchall()]

def get_sqlite_columns(cursor, table_name):
    cursor.execute(f'PRAGMA table_info("{table_name}")')

    columns = []

    for row in cursor.fetchall():
        # SQLite PRAGMA table_info row:
        # cid, name, type, notnull, dflt_value, pk

        columns.append({
            "cid": row[0],
            "name": row[1],
            "type": row[2] or "text",
            "notnull": row[3],
            "default": row[4],
            "pk": row[5] > 0
        })

    return columns

def get_sqlite_foreign_keys(cursor, table_name):
    cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')

    foreign_keys = {}

    for row in cursor.fetchall():
        # SQLite PRAGMA foreign_key_list row:
        # id, seq, table, from, to, on_update, on_delete, match

        referenced_table = row[2]
        from_column = row[3]
        referenced_column = row[4]

        foreign_keys[from_column] = (
            f"FOREIGN KEY {referenced_table.upper()} ({referenced_column})"
        )

    return foreign_keys
