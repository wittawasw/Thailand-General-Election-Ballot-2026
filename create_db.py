#!/usr/bin/env python3

from pathlib import Path
import sqlite3

DATABASE_FILE = "data/ballot_2569.sqlite"
DDL_FILE = "create_tables.sql"
OVERWRITE_DATABASE = True


def execute_sql_file(con: sqlite3.Connection, sql_path: Path) -> None:
    ddl_sql = sql_path.read_text(encoding="utf-8")
    con.executescript(ddl_sql)
    con.commit()


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    database_path = base_dir / DATABASE_FILE
    ddl_path = base_dir / DDL_FILE

    if not ddl_path.exists():
        raise FileNotFoundError(f"DDL file not found: {ddl_path}")

    database_path.parent.mkdir(parents=True, exist_ok=True)

    if OVERWRITE_DATABASE and database_path.exists():
        database_path.unlink()

    con = sqlite3.connect(database_path)

    try:
        execute_sql_file(con, ddl_path)
    finally:
        con.close()

    print(f"Created SQLite database: {database_path}")
    print(f"DDL file used: {ddl_path}")


if __name__ == "__main__":
    main()
