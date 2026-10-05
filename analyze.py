"""
Run the Step 4 gap-analysis queries against cci_pipeline.db and print the
results.

RARE_IN_JOBS / RARE_IN_COURSES are fixed thresholds for "rarely" -- tune
here if the definition of "rare" should change.

Queries are module-level constants so dashboard.py (Step 5) can import and
reuse them instead of duplicating the SQL.

Run: python analyze.py
"""

import sqlite3
import pandas as pd

DB_PATH = "cci_pipeline.db"
# Trimmed copy without Adzuna posting text (built by make_public_db.py).
# This is the one that gets published and that dashboard.py reads.
PUBLIC_DB_PATH = "cci_pipeline_public.db"

RARE_IN_JOBS = 5      # postings; skills at/under this count are "rarely in-demand"
RARE_IN_COURSES = 1   # courses; skills at/under this count are "rarely/never taught"

pd.set_option("display.max_rows", None)
pd.set_option("display.width", 120)

Q1A_SQL = """
    SELECT s.skill, s.category, COUNT(DISTINCT js.job_id) AS n_postings
    FROM skills s
    LEFT JOIN job_skills js ON js.skill = s.skill
    GROUP BY s.skill
    ORDER BY n_postings DESC;
"""

Q1B_SQL = """
    SELECT j.track, js.skill, COUNT(DISTINCT js.job_id) AS n_postings
    FROM job_skills js
    JOIN jobs j ON j.job_id = js.job_id
    GROUP BY j.track, js.skill
    ORDER BY j.track, n_postings DESC;
"""

Q2_SQL = f"""
    SELECT s.skill, s.category,
           COUNT(DISTINCT cs.course_code) AS n_courses,
           COUNT(DISTINCT js.job_id)      AS n_postings
    FROM skills s
    JOIN course_skills cs ON cs.skill = s.skill
    LEFT JOIN job_skills js ON js.skill = s.skill
    GROUP BY s.skill
    HAVING n_postings <= {RARE_IN_JOBS}
    ORDER BY n_postings ASC, n_courses DESC;
"""

Q3_SQL = f"""
    SELECT s.skill, s.category,
           COUNT(DISTINCT js.job_id)      AS n_postings,
           COUNT(DISTINCT cs.course_code) AS n_courses
    FROM skills s
    JOIN job_skills js ON js.skill = s.skill
    LEFT JOIN course_skills cs ON cs.skill = s.skill
    GROUP BY s.skill
    HAVING n_courses <= {RARE_IN_COURSES}
    ORDER BY n_postings DESC;
"""

Q4A_SQL = """
    WITH in_demand_skills AS (
        SELECT DISTINCT skill FROM job_skills
    )
    SELECT c.school,
           COUNT(DISTINCT cs.skill) AS in_demand_skills_covered,
           (SELECT COUNT(*) FROM in_demand_skills) AS total_in_demand_skills
    FROM courses c
    JOIN course_skills cs ON cs.course_code = c.course_code
    JOIN in_demand_skills d ON d.skill = cs.skill
    GROUP BY c.school;
"""

Q4B_SQL = """
    WITH in_demand_skills AS (
        SELECT DISTINCT skill FROM job_skills
    )
    SELECT DISTINCT c.school, cs.skill
    FROM courses c
    JOIN course_skills cs ON cs.course_code = c.course_code
    JOIN in_demand_skills d ON d.skill = cs.skill
    ORDER BY c.school, cs.skill;
"""


def run(conn, label, sql):
    print(f"\n=== {label} ===")
    df = pd.read_sql_query(sql, conn)
    print(df.to_string(index=False))
    return df


def main():
    conn = sqlite3.connect(DB_PATH)

    run(conn, "Q1a. Skill frequency in job postings, overall (most -> least common)", Q1A_SQL)
    run(conn, "Q1b. Skill frequency in job postings, by track", Q1B_SQL)
    run(conn, f"Q2. Taught in courses but rarely in-demand (<= {RARE_IN_JOBS} postings)", Q2_SQL)
    run(conn, f"Q3. In-demand but rarely/never taught (<= {RARE_IN_COURSES} course), the headline gap", Q3_SQL)
    run(conn, "Q4a. In-demand skills covered, by school", Q4A_SQL)
    run(conn, "Q4b. Which specific in-demand skills each school covers", Q4B_SQL)

    conn.close()


if __name__ == "__main__":
    main()
