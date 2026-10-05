"""
Make cci_pipeline_public.db: a copy of cci_pipeline.db with the Adzuna
posting content removed from the jobs table, safe to publish.

The dashboard only needs each posting's ID, track, search term and pull
date (to count postings per skill/track), so the full posting text,
title, company, location, salary and link are dropped. The full database
stays local and is gitignored.

Safe to re-run: overwrites the public copy each time.

Run (after build_database.py): python make_public_db.py
"""

import os
import shutil
import sqlite3

from analyze import DB_PATH, PUBLIC_DB_PATH

# Columns of the jobs table that come straight from Adzuna postings.
ADZUNA_CONTENT_COLUMNS = [
    "title",
    "company",
    "location",
    "category",
    "salary_min",
    "salary_max",
    "created",
    "description",
    "redirect_url",
]


def main():
    if os.path.exists(PUBLIC_DB_PATH):
        os.remove(PUBLIC_DB_PATH)
    shutil.copyfile(DB_PATH, PUBLIC_DB_PATH)

    conn = sqlite3.connect(PUBLIC_DB_PATH)
    for column in ADZUNA_CONTENT_COLUMNS:
        conn.execute(f"ALTER TABLE jobs DROP COLUMN {column}")
    conn.commit()
    conn.execute("VACUUM")  # actually remove the dropped text from the file

    remaining = [row[1] for row in conn.execute("PRAGMA table_info(jobs)")]
    print(f"jobs columns kept: {', '.join(remaining)}")
    conn.close()
    print(f"Done. Wrote {PUBLIC_DB_PATH}")


if __name__ == "__main__":
    main()
