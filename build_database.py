"""
Build cci_pipeline.db from the four pipeline CSVs: courses, jobs, and their
skill taggings. Adds a 5th `skills` lookup table (populated from
tag_skills.py's SKILLS dict) so gap-analysis queries can see skills with
zero matches via LEFT JOIN, without duplicating the skill vocabulary.

Safe to re-run: deletes and rebuilds the database from scratch each time,
since everything in it is derived from the CSVs.

Run: python build_database.py
"""

import os
import sqlite3
import pandas as pd

from tag_skills import SKILLS

DB_PATH = "cci_pipeline.db"

SCHEMA = """
CREATE TABLE courses (
    course_code    TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    credits        INTEGER,
    prerequisites  TEXT,
    description    TEXT,
    school         TEXT NOT NULL
);

CREATE TABLE jobs (
    job_id         INTEGER PRIMARY KEY,
    pull_date      TEXT NOT NULL,
    search_term    TEXT,
    track          TEXT NOT NULL,
    title          TEXT,
    company        TEXT,
    location       TEXT,
    category       TEXT,
    salary_min     REAL,
    salary_max     REAL,
    created        TEXT,
    description    TEXT,
    redirect_url   TEXT
);

CREATE TABLE skills (
    skill          TEXT PRIMARY KEY,
    category       TEXT NOT NULL
);

CREATE TABLE course_skills (
    course_code    TEXT NOT NULL REFERENCES courses(course_code),
    skill          TEXT NOT NULL REFERENCES skills(skill),
    PRIMARY KEY (course_code, skill)
);

CREATE TABLE job_skills (
    job_id         INTEGER NOT NULL REFERENCES jobs(job_id),
    skill          TEXT NOT NULL REFERENCES skills(skill),
    PRIMARY KEY (job_id, skill)
);
"""


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    skills_df = pd.DataFrame(
        [{"skill": skill, "category": category} for skill, category in SKILLS.items()]
    )
    skills_df.to_sql("skills", conn, if_exists="append", index=False)

    courses = pd.read_csv("cci_all_courses.csv")
    courses.to_sql("courses", conn, if_exists="append", index=False)

    jobs = pd.read_csv("cci_job_postings_latest.csv")
    jobs.to_sql("jobs", conn, if_exists="append", index=False)

    course_skills = pd.read_csv("course_skills.csv").drop(columns=["skill_category"])
    course_skills.to_sql("course_skills", conn, if_exists="append", index=False)

    job_skills = pd.read_csv("job_skills.csv").drop(columns=["skill_category"])
    job_skills.to_sql("job_skills", conn, if_exists="append", index=False)

    conn.commit()

    print("Row counts:")
    for table in ["courses", "jobs", "skills", "course_skills", "job_skills"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:15s} {count}")

    conn.close()
    print(f"\nDone. Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
