#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import polars as pl

DATABASE_FILE = "data/ballot_2569.sqlite"
XLSX_FILE = "data/ตารางคะแนนผลการเลือกตั้ง 2569.xlsx"

ELECTION_ID = 1
ELECTION_NAME = "การเลือกตั้ง 2569"
ELECTION_YEAR_BE = 2569

SHEET_BALLOT_SUMMARY = "สรุปจำนวนผู้มาใช้สิทธิ และบัตร "
SHEET_CONSTITUENCY_RESULTS = "คะแนนสส.แบ่งเขต (100%)"
SHEET_PARTY_LIST_RESULTS = "คะแนนสส. บัญชีรายชื่อ (100%)"
SHEET_COMPARE_CONSTITUENCY_94 = "เปรียบเทียบคะแนน สส.แบ่งเขต 94%"
SHEET_COMPARE_PARTY_LIST_94 = "เปรียบเทียบคะแนน สส.บัญชีรายชื่"

TOTAL_PARTY_COLUMNS = {
    "รวม",
    "รวม 57 พรรค",
    "รวมพรรค",
    "รวมคะแนน",
}


def connect_sqlite_database(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(database_path)


def normalize_col(name: object) -> str:
    return str(name).strip().replace("\n", " ").replace("\r", " ")


def clean_df(df: pl.DataFrame) -> pl.DataFrame:
    df = df.rename({c: normalize_col(c) for c in df.columns})
    return df.drop_nulls(subset=[df.columns[0]])


def to_int_expr(col: str) -> pl.Expr:
    return (
        pl.col(col)
        .cast(pl.Utf8, strict=False)
        .str.replace_all(",", "")
        .str.strip_chars()
        .cast(pl.Float64, strict=False)
        .round(0)
        .cast(pl.Int64, strict=False)
    )


def to_text_expr(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars()


def read_sheet(xlsx_path: Path, sheet_name: str, header_row: int = 1) -> pl.DataFrame:
    return clean_df(
        pl.read_excel(
            source=xlsx_path,
            sheet_name=sheet_name,
            has_header=True,
            read_options={"header_row": header_row - 1},
        )
    )


def read_all_frames(xlsx_path: Path) -> dict[str, pl.DataFrame]:
    return {
        SHEET_BALLOT_SUMMARY: read_sheet(xlsx_path, SHEET_BALLOT_SUMMARY),
        SHEET_CONSTITUENCY_RESULTS: read_sheet(xlsx_path, SHEET_CONSTITUENCY_RESULTS),
        SHEET_PARTY_LIST_RESULTS: read_sheet(xlsx_path, SHEET_PARTY_LIST_RESULTS),
        SHEET_COMPARE_CONSTITUENCY_94: read_sheet(
            xlsx_path, SHEET_COMPARE_CONSTITUENCY_94, header_row=3
        ),
        SHEET_COMPARE_PARTY_LIST_94: read_sheet(
            xlsx_path, SHEET_COMPARE_PARTY_LIST_94, header_row=3
        ),
    }


def source_rows_frame(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    for sheet_name, df in frames.items():
        first_excel_row = 4 if sheet_name.startswith("เปรียบเทียบ") else 2

        for offset, record in enumerate(df.to_dicts()):
            rows.append(
                {
                    "sheet_name": sheet_name,
                    "row_number": first_excel_row + offset,
                    "row_data": json.dumps(record, ensure_ascii=False, default=str),
                }
            )

    return pl.DataFrame(rows)


def shape_ballot_summary(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        to_text_expr("จังหวัด").alias("province_name"),
        to_int_expr("เขต").alias("constituency_no"),
        to_text_expr("ประเภท").alias("election_type"),
        to_int_expr("ผู้มีสิทธิ์").alias("eligible_voters"),
        to_int_expr("ผู้มาใช้สิทธิ์").alias("turnout_voters"),
        to_int_expr("บัตรดี").alias("valid_ballots"),
        to_int_expr("บัตรเสีย").alias("invalid_ballots"),
        to_int_expr("บัตรไม่เลือก").alias("no_vote_ballots"),
    ).with_columns(pl.lit(100.0).alias("result_percent"))


def shape_constituency_results(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        to_text_expr("จังหวัด").alias("province_name"),
        to_int_expr("เขต").alias("constituency_no"),
        to_int_expr("ลำดับ").alias("candidate_order"),
        to_text_expr("ผู้สมัคร").alias("candidate_name"),
        to_text_expr("พรรค").alias("party_name"),
        to_int_expr("คะแนน").alias("votes"),
    ).with_columns(pl.lit(100.0).alias("result_percent"))


def shape_party_list_results(df: pl.DataFrame) -> pl.DataFrame:
    fixed_cols = {"จังหวัด", "เขต"}

    party_cols = [
        c
        for c in df.columns
        if c not in fixed_cols and normalize_col(c) not in TOTAL_PARTY_COLUMNS
    ]

    long_df = df.unpivot(
        index=["จังหวัด", "เขต"],
        on=party_cols,
        variable_name="party_name",
        value_name="votes",
    )

    return long_df.select(
        to_text_expr("จังหวัด").alias("province_name"),
        to_int_expr("เขต").alias("constituency_no"),
        to_text_expr("party_name").alias("party_name"),
        to_int_expr("votes").alias("votes"),
    ).with_columns(pl.lit(100.0).alias("result_percent"))


def shape_comparison(df: pl.DataFrame, election_type: str) -> pl.DataFrame:
    cols = df.columns

    def find_col(prefix: str) -> str:
        matches = [c for c in cols if c.startswith(prefix)]
        if not matches:
            raise KeyError(f"Cannot find column starting with: {prefix}")
        return matches[0]

    diff_cols = [c for c in cols if c.startswith("ผลต่าง")]

    if len(diff_cols) < 4:
        diff_cols = [cols[4], cols[7], cols[10], cols[13]]

    return df.select(
        to_text_expr("จังหวัด").alias("province_name"),
        to_int_expr("เขต").alias("constituency_no"),
        to_int_expr(find_col("ผู้มาใช้สิทธิ 94%")).alias("turnout_94"),
        to_int_expr(find_col("ผู้มาใช้สิทธิ 100%")).alias("turnout_100"),
        to_int_expr(diff_cols[0]).alias("turnout_diff"),
        to_int_expr(find_col("บัตรดี 94%")).alias("valid_ballots_94"),
        to_int_expr(find_col("บัตรดี 100%")).alias("valid_ballots_100"),
        to_int_expr(diff_cols[1]).alias("valid_ballots_diff"),
        to_int_expr(find_col("บัตรเสีย 94%")).alias("invalid_ballots_94"),
        to_int_expr(find_col("บัตรเสีย 100%")).alias("invalid_ballots_100"),
        to_int_expr(diff_cols[2]).alias("invalid_ballots_diff"),
        to_int_expr(find_col("บัตรไม่เลือก 94%")).alias("no_vote_ballots_94"),
        to_int_expr(find_col("บัตรไม่เลือก 100%")).alias("no_vote_ballots_100"),
        to_int_expr(diff_cols[3]).alias("no_vote_ballots_diff"),
    ).with_columns(pl.lit(election_type).alias("election_type"))


def insert_election(con: sqlite3.Connection, xlsx_path: Path) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO elections (id, name, year_be, source_file)
        VALUES (?, ?, ?, ?)
        """,
        (ELECTION_ID, ELECTION_NAME, ELECTION_YEAR_BE, xlsx_path.name),
    )


def insert_provinces(con: sqlite3.Connection, province_names: list[str]) -> None:
    con.executemany(
        "INSERT OR IGNORE INTO provinces (name_th) VALUES (?)",
        [(name,) for name in province_names if name],
    )


def insert_parties(con: sqlite3.Connection, party_names: list[str]) -> None:
    con.executemany(
        "INSERT OR IGNORE INTO parties (name_th) VALUES (?)",
        [(name,) for name in party_names if name],
    )


def fetch_id_map(con: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    rows = con.execute(f"SELECT id, {column} FROM {table}").fetchall()
    return {value: row_id for row_id, value in rows}


def insert_constituencies(
    con: sqlite3.Connection,
    constituencies: list[dict[str, object]],
    province_id_map: dict[str, int],
) -> None:
    rows = []

    for row in constituencies:
        province_name = row["province_name"]
        constituency_no = row["constituency_no"]

        if not province_name or constituency_no is None:
            continue

        rows.append(
            (
                ELECTION_ID,
                province_id_map[province_name],
                constituency_no,
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO constituencies (
            election_id, province_id, constituency_no
        )
        VALUES (?, ?, ?)
        """,
        rows,
    )


def fetch_constituency_id_map(con: sqlite3.Connection) -> dict[tuple[int, int], int]:
    rows = con.execute(
        """
        SELECT province_id, constituency_no, id
        FROM constituencies
        WHERE election_id = ?
        """,
        (ELECTION_ID,),
    ).fetchall()

    return {
        (province_id, constituency_no): constituency_id
        for province_id, constituency_no, constituency_id in rows
    }


def insert_candidates(
    con: sqlite3.Connection,
    candidates: list[dict[str, object]],
    party_id_map: dict[str, int],
) -> None:
    rows = []

    for row in candidates:
        candidate_name = row["candidate_name"]
        party_name = row["party_name"]

        if not candidate_name:
            continue

        rows.append(
            (
                candidate_name,
                party_id_map.get(party_name),
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO candidates (full_name_th, party_id)
        VALUES (?, ?)
        """,
        rows,
    )


def fetch_candidate_id_map(con: sqlite3.Connection) -> dict[tuple[str, int | None], int]:
    rows = con.execute(
        """
        SELECT id, full_name_th, party_id
        FROM candidates
        """
    ).fetchall()

    return {
        (full_name_th, party_id): candidate_id
        for candidate_id, full_name_th, party_id in rows
    }


def insert_ballot_summaries(
    con: sqlite3.Connection,
    rows: list[dict[str, object]],
    province_id_map: dict[str, int],
    constituency_id_map: dict[tuple[int, int], int],
) -> None:
    insert_rows = []

    for row in rows:
        province_name = row["province_name"]
        constituency_no = row["constituency_no"]

        if not province_name or constituency_no is None:
            continue

        province_id = province_id_map[province_name]
        constituency_id = constituency_id_map[(province_id, constituency_no)]

        insert_rows.append(
            (
                ELECTION_ID,
                constituency_id,
                row["election_type"],
                row["eligible_voters"],
                row["turnout_voters"],
                row["valid_ballots"],
                row["invalid_ballots"],
                row["no_vote_ballots"],
                row["result_percent"],
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO ballot_summaries (
            election_id,
            constituency_id,
            election_type,
            eligible_voters,
            turnout_voters,
            valid_ballots,
            invalid_ballots,
            no_vote_ballots,
            result_percent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        insert_rows,
    )


def insert_constituency_results(
    con: sqlite3.Connection,
    rows: list[dict[str, object]],
    province_id_map: dict[str, int],
    party_id_map: dict[str, int],
    constituency_id_map: dict[tuple[int, int], int],
    candidate_id_map: dict[tuple[str, int | None], int],
) -> None:
    insert_rows = []

    for row in rows:
        if row["votes"] is None:
            continue

        province_name = row["province_name"]
        constituency_no = row["constituency_no"]
        party_name = row["party_name"]
        candidate_name = row["candidate_name"]

        if not province_name or constituency_no is None or not candidate_name:
            continue

        province_id = province_id_map[province_name]
        party_id = party_id_map.get(party_name)
        constituency_id = constituency_id_map[(province_id, constituency_no)]
        candidate_id = candidate_id_map[(candidate_name, party_id)]

        insert_rows.append(
            (
                ELECTION_ID,
                constituency_id,
                candidate_id,
                row["candidate_order"],
                row["votes"],
                row["result_percent"],
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO constituency_results (
            election_id,
            constituency_id,
            candidate_id,
            candidate_order,
            votes,
            result_percent
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        insert_rows,
    )


def insert_party_list_results(
    con: sqlite3.Connection,
    rows: list[dict[str, object]],
    province_id_map: dict[str, int],
    party_id_map: dict[str, int],
    constituency_id_map: dict[tuple[int, int], int],
) -> None:
    insert_rows = []

    for row in rows:
        if row["votes"] is None:
            continue

        province_name = row["province_name"]
        constituency_no = row["constituency_no"]
        party_name = row["party_name"]

        if not province_name or constituency_no is None or not party_name:
            continue

        province_id = province_id_map[province_name]
        constituency_id = constituency_id_map[(province_id, constituency_no)]
        party_id = party_id_map[party_name]

        insert_rows.append(
            (
                ELECTION_ID,
                constituency_id,
                party_id,
                row["votes"],
                row["result_percent"],
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO party_list_results (
            election_id,
            constituency_id,
            party_id,
            votes,
            result_percent
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        insert_rows,
    )


def insert_ballot_comparisons(
    con: sqlite3.Connection,
    rows: list[dict[str, object]],
    province_id_map: dict[str, int],
    constituency_id_map: dict[tuple[int, int], int],
) -> None:
    insert_rows = []

    for row in rows:
        province_name = row["province_name"]
        constituency_no = row["constituency_no"]

        if not province_name or constituency_no is None:
            continue

        province_id = province_id_map[province_name]
        constituency_id = constituency_id_map[(province_id, constituency_no)]

        insert_rows.append(
            (
                ELECTION_ID,
                constituency_id,
                row["election_type"],
                row["turnout_94"],
                row["turnout_100"],
                row["turnout_diff"],
                row["valid_ballots_94"],
                row["valid_ballots_100"],
                row["valid_ballots_diff"],
                row["invalid_ballots_94"],
                row["invalid_ballots_100"],
                row["invalid_ballots_diff"],
                row["no_vote_ballots_94"],
                row["no_vote_ballots_100"],
                row["no_vote_ballots_diff"],
            )
        )

    con.executemany(
        """
        INSERT OR IGNORE INTO ballot_comparisons (
            election_id,
            constituency_id,
            election_type,
            turnout_94,
            turnout_100,
            turnout_diff,
            valid_ballots_94,
            valid_ballots_100,
            valid_ballots_diff,
            invalid_ballots_94,
            invalid_ballots_100,
            invalid_ballots_diff,
            no_vote_ballots_94,
            no_vote_ballots_100,
            no_vote_ballots_diff
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        insert_rows,
    )


def insert_source_rows(
    con: sqlite3.Connection,
    rows: list[dict[str, object]],
) -> None:
    insert_rows = [
        (
            ELECTION_ID,
            row["sheet_name"],
            row["row_number"],
            row["row_data"],
        )
        for row in rows
    ]

    con.executemany(
        """
        INSERT OR IGNORE INTO source_rows (
            election_id,
            sheet_name,
            row_number,
            row_data
        )
        VALUES (?, ?, ?, ?)
        """,
        insert_rows,
    )


def print_counts(con: sqlite3.Connection) -> None:
    tables = [
        "elections",
        "provinces",
        "constituencies",
        "parties",
        "candidates",
        "ballot_summaries",
        "constituency_results",
        "party_list_results",
        "ballot_comparisons",
        "source_rows",
    ]

    for table in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")


def main() -> None:
    xlsx_path = Path(XLSX_FILE)
    database_path = Path(DATABASE_FILE)

    if not xlsx_path.exists():
        raise FileNotFoundError(f"XLSX file not found: {xlsx_path}")

    if not database_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {database_path}. Run create_db.py first."
        )

    frames = read_all_frames(xlsx_path)

    ballot_summary = shape_ballot_summary(frames[SHEET_BALLOT_SUMMARY])
    constituency_results = shape_constituency_results(frames[SHEET_CONSTITUENCY_RESULTS])
    party_list_results = shape_party_list_results(frames[SHEET_PARTY_LIST_RESULTS])
    compare_constituency = shape_comparison(frames[SHEET_COMPARE_CONSTITUENCY_94], "แบ่งเขต")
    compare_party_list = shape_comparison(frames[SHEET_COMPARE_PARTY_LIST_94], "บัญชีรายชื่อ")
    compare = pl.concat([compare_constituency, compare_party_list], how="diagonal")
    source_rows = source_rows_frame(frames)

    provinces = (
        pl.concat(
            [
                ballot_summary.select("province_name"),
                constituency_results.select("province_name"),
                party_list_results.select("province_name"),
            ]
        )
        .filter(pl.col("province_name").is_not_null())
        .unique()
        .sort("province_name")
    )

    parties = (
        pl.concat(
            [
                constituency_results.select("party_name"),
                party_list_results.select("party_name"),
            ]
        )
        .filter(pl.col("party_name").is_not_null())
        .unique()
        .sort("party_name")
    )

    constituencies = (
        pl.concat(
            [
                ballot_summary.select("province_name", "constituency_no"),
                constituency_results.select("province_name", "constituency_no"),
                party_list_results.select("province_name", "constituency_no"),
            ]
        )
        .filter(pl.col("province_name").is_not_null())
        .filter(pl.col("constituency_no").is_not_null())
        .unique()
        .sort(["province_name", "constituency_no"])
    )

    candidates = (
        constituency_results.select("candidate_name", "party_name")
        .filter(pl.col("candidate_name").is_not_null())
        .unique()
    )

    con = connect_sqlite_database(database_path)

    try:
        con.execute("BEGIN")

        insert_election(con, xlsx_path)

        insert_provinces(
            con,
            [row["province_name"] for row in provinces.to_dicts()],
        )

        insert_parties(
            con,
            [row["party_name"] for row in parties.to_dicts()],
        )

        province_id_map = fetch_id_map(con, "provinces", "name_th")
        party_id_map = fetch_id_map(con, "parties", "name_th")

        insert_constituencies(
            con,
            constituencies.to_dicts(),
            province_id_map,
        )

        constituency_id_map = fetch_constituency_id_map(con)

        insert_candidates(
            con,
            candidates.to_dicts(),
            party_id_map,
        )

        candidate_id_map = fetch_candidate_id_map(con)

        insert_ballot_summaries(
            con,
            ballot_summary.to_dicts(),
            province_id_map,
            constituency_id_map,
        )

        insert_constituency_results(
            con,
            constituency_results.to_dicts(),
            province_id_map,
            party_id_map,
            constituency_id_map,
            candidate_id_map,
        )

        insert_party_list_results(
            con,
            party_list_results.to_dicts(),
            province_id_map,
            party_id_map,
            constituency_id_map,
        )

        insert_ballot_comparisons(
            con,
            compare.to_dicts(),
            province_id_map,
            constituency_id_map,
        )

        insert_source_rows(
            con,
            source_rows.to_dicts(),
        )

        con.commit()

    except Exception:
        con.rollback()
        raise

    finally:
        print_counts(con)
        con.close()

    print(f"Imported XLSX: {xlsx_path}")
    print(f"SQLite database: {database_path}")


if __name__ == "__main__":
    main()
