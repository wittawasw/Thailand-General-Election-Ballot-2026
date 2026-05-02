#!/usr/bin/env python3

from pathlib import Path
import sqlite3

from flask import Flask, abort, g, render_template

from create_db import DATABASE_FILE


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / DATABASE_FILE

app = Flask(__name__)


@app.template_filter("comma")
def comma(value: int | None) -> str:
    return f"{value or 0:,}"


@app.template_filter("signed_comma")
def signed_comma(value: int | None) -> str:
    value = value or 0
    return f"{value:+,}"


@app.template_filter("diff_class")
def diff_class(value: int | None) -> str:
    value = value or 0

    if value < 0:
        return "diff-negative"
    if value > 0:
        return "diff-positive"
    return ""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(
                f"Database not found: {DATABASE_PATH}. Run create_db.py and import.py first."
            )

        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(error: BaseException | None = None) -> None:
    db = g.pop("db", None)

    if db is not None:
        db.close()


@app.route("/")
def index() -> str:
    db = get_db()

    election = db.execute(
        """
        SELECT name, year_be, source_file
        FROM elections
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()

    totals = db.execute(
        """
        SELECT
            election_type,
            COUNT(*) AS row_count,
            COALESCE(SUM(turnout_94), 0) AS turnout_94,
            COALESCE(SUM(turnout_100), 0) AS turnout_100,
            COALESCE(SUM(turnout_diff), 0) AS turnout_diff,
            COALESCE(SUM(valid_ballots_94), 0) AS valid_ballots_94,
            COALESCE(SUM(valid_ballots_100), 0) AS valid_ballots_100,
            COALESCE(SUM(valid_ballots_diff), 0) AS valid_ballots_diff,
            COALESCE(SUM(invalid_ballots_94), 0) AS invalid_ballots_94,
            COALESCE(SUM(invalid_ballots_100), 0) AS invalid_ballots_100,
            COALESCE(SUM(invalid_ballots_diff), 0) AS invalid_ballots_diff,
            COALESCE(SUM(no_vote_ballots_94), 0) AS no_vote_ballots_94,
            COALESCE(SUM(no_vote_ballots_100), 0) AS no_vote_ballots_100,
            COALESCE(SUM(no_vote_ballots_diff), 0) AS no_vote_ballots_diff
        FROM ballot_comparisons
        GROUP BY election_type
        ORDER BY election_type
        """
    ).fetchall()

    provinces = db.execute(
        """
        SELECT
            p.id,
            p.name_th,
            COUNT(DISTINCT c.id) AS constituency_count,
            COALESCE(SUM(bc.turnout_diff), 0) AS turnout_diff,
            COALESCE(SUM(bc.valid_ballots_diff), 0) AS valid_ballots_diff,
            COALESCE(SUM(bc.invalid_ballots_diff), 0) AS invalid_ballots_diff,
            COALESCE(SUM(bc.no_vote_ballots_diff), 0) AS no_vote_ballots_diff
        FROM provinces p
        LEFT JOIN constituencies c ON c.province_id = p.id
        LEFT JOIN ballot_comparisons bc ON bc.constituency_id = c.id
        GROUP BY p.id, p.name_th
        ORDER BY ABS(COALESCE(SUM(bc.turnout_diff), 0)) DESC, p.name_th
        """
    ).fetchall()

    negative_count = db.execute(
        """
        SELECT COUNT(*)
        FROM ballot_comparisons
        WHERE turnout_diff < 0
        OR valid_ballots_diff < 0
        OR invalid_ballots_diff < 0
        OR no_vote_ballots_diff < 0
        """
    ).fetchone()[0]

    return render_template(
        "index.html",
        election=election,
        totals=totals,
        provinces=provinces,
        negative_count=negative_count,
    )


@app.route("/negative")
def negative() -> str:
    db = get_db()

    rows = db.execute(
        """
        SELECT
            p.id AS province_id,
            p.name_th AS province_name,
            c.constituency_no,
            bc.election_type,
            bc.turnout_94,
            bc.turnout_100,
            bc.turnout_diff,
            bc.valid_ballots_94,
            bc.valid_ballots_100,
            bc.valid_ballots_diff,
            bc.invalid_ballots_94,
            bc.invalid_ballots_100,
            bc.invalid_ballots_diff,
            bc.no_vote_ballots_94,
            bc.no_vote_ballots_100,
            bc.no_vote_ballots_diff
        FROM ballot_comparisons bc
        JOIN constituencies c ON c.id = bc.constituency_id
        JOIN provinces p ON p.id = c.province_id
        WHERE bc.turnout_diff < 0
        OR bc.valid_ballots_diff < 0
        OR bc.invalid_ballots_diff < 0
        OR bc.no_vote_ballots_diff < 0
        ORDER BY
            MIN(
                bc.turnout_diff,
                bc.valid_ballots_diff,
                bc.invalid_ballots_diff,
                bc.no_vote_ballots_diff
            ),
            p.name_th,
            c.constituency_no,
            bc.election_type
        """
    ).fetchall()

    return render_template("negative.html", rows=rows)


@app.route("/province/<int:province_id>")
def province(province_id: int) -> str:
    db = get_db()

    province_row = db.execute(
        "SELECT id, name_th FROM provinces WHERE id = ?",
        (province_id,),
    ).fetchone()

    if province_row is None:
        abort(404)

    comparisons = db.execute(
        """
        SELECT
            c.constituency_no,
            bc.election_type,
            bc.turnout_94,
            bc.turnout_100,
            bc.turnout_diff,
            bc.valid_ballots_94,
            bc.valid_ballots_100,
            bc.valid_ballots_diff,
            bc.invalid_ballots_94,
            bc.invalid_ballots_100,
            bc.invalid_ballots_diff,
            bc.no_vote_ballots_94,
            bc.no_vote_ballots_100,
            bc.no_vote_ballots_diff
        FROM constituencies c
        JOIN ballot_comparisons bc ON bc.constituency_id = c.id
        WHERE c.province_id = ?
        ORDER BY c.constituency_no
        """,
        (province_id,),
    ).fetchall()

    totals = db.execute(
        """
        SELECT
            election_type,
            COUNT(*) AS row_count,
            COALESCE(SUM(turnout_diff), 0) AS turnout_diff,
            COALESCE(SUM(valid_ballots_diff), 0) AS valid_ballots_diff,
            COALESCE(SUM(invalid_ballots_diff), 0) AS invalid_ballots_diff,
            COALESCE(SUM(no_vote_ballots_diff), 0) AS no_vote_ballots_diff
        FROM ballot_comparisons bc
        JOIN constituencies c ON c.id = bc.constituency_id
        WHERE c.province_id = ?
        GROUP BY election_type
        ORDER BY election_type
        """,
        (province_id,),
    ).fetchall()

    return render_template(
        "province.html",
        province=province_row,
        comparisons=comparisons,
        totals=totals,
    )


if __name__ == "__main__":
    app.run(debug=True)
