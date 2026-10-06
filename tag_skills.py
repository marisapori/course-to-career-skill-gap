"""
Tag CCI courses and job postings with a shared skills vocabulary, by
keyword-matching against a fixed skill list.

Courses are matched on title + description: a course named "Media Planning"
teaches media planning even if its description never repeats the phrase.
Job postings are matched on description only -- their titles mostly echo the
search terms used to find them, which would inflate those skills further.

Matching is literal-phrase, case-insensitive, whole-word/phrase boundaries,
plus a short ALIASES list of spelled-out forms ("user experience design" for
"UX design"). Still undercounts skills that appear under looser names (e.g.
"AWS" won't tag "cloud computing") -- simple and auditable over clever.

Known false positive, accepted rather than solved: "Excel" also matches
the verb ("prepares students to excel in..."), not just the spreadsheet
tool. Fixing this well needs context-aware NLP, out of scope here.

Run: python tag_skills.py
Outputs: course_skills.csv, job_skills.csv
"""

import re
import pandas as pd

SKILLS = {
    # Technical / IT
    "SQL": "Technical/IT",
    "Python": "Technical/IT",
    "database management": "Technical/IT",
    "network administration": "Technical/IT",
    "cybersecurity": "Technical/IT",
    "cloud computing": "Technical/IT",
    "JavaScript": "Technical/IT",
    "HTML": "Technical/IT",
    "CSS": "Technical/IT",
    "mobile app development": "Technical/IT",
    "UX design": "Technical/IT",
    "UI design": "Technical/IT",
    "data visualization": "Technical/IT",
    "data analytics": "Technical/IT",
    "project management": "Technical/IT",
    "Excel": "Technical/IT",
    "API": "Technical/IT",
    "machine learning": "Technical/IT",
    "AI": "Technical/IT",
    # Communications / Marketing
    "social media management": "Communications/Marketing",
    "content strategy": "Communications/Marketing",
    "copywriting": "Communications/Marketing",
    "public relations": "Communications/Marketing",
    "media planning": "Communications/Marketing",
    "campaign management": "Communications/Marketing",
    "video production": "Communications/Marketing",
    "graphic design": "Communications/Marketing",
    "SEO": "Communications/Marketing",
    "digital marketing": "Communications/Marketing",
    "crisis communication": "Communications/Marketing",
    "brand strategy": "Communications/Marketing",
    "market research": "Communications/Marketing",
}

# Most skills match the literal phrase with plain word boundaries. A few
# single-word/acronym skills need a small suffix allowance because the
# word-boundary regex otherwise misses same-skill surface variants seen in
# the actual data:
#   - "API"  also matches "APIs" (plural)
#   - "HTML" also matches "HTML5" (versioned)
#   - "CSS"  also matches "CSS3" (versioned)
# "Excel" deliberately does NOT get an "s?" suffix -- "Excels" in the data
# turned out to be the verb ("someone who excels at..."), not the tool, so
# adding it would trade a real miss for a worse false positive.
SUFFIX_OVERRIDES = {
    "API": r"s?",
    "HTML": r"\d*",
    "CSS": r"\d*",
}

# Other names for the same skill. Kept to exact equivalents (spelled-out
# acronyms, spacing variants) so a match still means the skill is named.
ALIASES = {
    "AI": ["artificial intelligence"],
    "UX design": ["user experience design"],
    "UI design": ["user interface design"],
    "SEO": ["search engine optimization"],
    "cybersecurity": ["cyber security"],
}

SKILL_PATTERNS = {
    skill: re.compile(
        r"\b(?:"
        + "|".join(re.escape(name) for name in [skill] + ALIASES.get(skill, []))
        + r")"
        + SUFFIX_OVERRIDES.get(skill, "")
        + r"\b",
        re.IGNORECASE,
    )
    for skill in SKILLS
}


def find_skills(text):
    """Return the set of skill names whose pattern matches text."""
    if not isinstance(text, str) or not text.strip():
        return set()
    return {skill for skill, pattern in SKILL_PATTERNS.items() if pattern.search(text)}


def tag_dataframe(df, id_col, text_cols):
    """Tag each row's text_cols, return a list of {id_col, skill, skill_category} dicts."""
    rows = []
    for _, row in df.iterrows():
        text = " ".join(str(row[col]) for col in text_cols if isinstance(row[col], str))
        for skill in find_skills(text):
            rows.append({
                id_col: row[id_col],
                "skill": skill,
                "skill_category": SKILLS[skill],
            })
    return rows


def print_summary(label, total_rows, tagged_ids, skill_rows):
    counts = pd.Series([r["skill"] for r in skill_rows]).value_counts()
    matched_skills = set(counts.index)
    zero_skills = sorted(set(SKILLS) - matched_skills)

    print(f"\n=== {label} ===")
    print(f"{len(tagged_ids)} of {total_rows} rows have at least one skill match")
    print(f"{len(skill_rows)} total (id, skill) tags across {len(matched_skills)} distinct skills")
    print("\nSkill frequency (most to least common):")
    for skill, count in counts.items():
        print(f"  {count:4d}  {skill}")
    if zero_skills:
        print("\nSkills with zero matches:")
        for skill in zero_skills:
            print(f"  - {skill}")


def main():
    courses = pd.read_csv("cci_all_courses.csv")
    jobs = pd.read_csv("cci_job_postings_latest.csv")

    course_skill_rows = tag_dataframe(courses, "course_code", ["title", "description"])
    job_skill_rows = tag_dataframe(jobs, "job_id", ["description"])

    pd.DataFrame(course_skill_rows).to_csv("course_skills.csv", index=False)
    pd.DataFrame(job_skill_rows).to_csv("job_skills.csv", index=False)

    tagged_courses = {r["course_code"] for r in course_skill_rows}
    tagged_jobs = {r["job_id"] for r in job_skill_rows}

    print_summary("Courses", len(courses), tagged_courses, course_skill_rows)
    print_summary("Job postings", len(jobs), tagged_jobs, job_skill_rows)

    print("\nDone. Wrote course_skills.csv and job_skills.csv")


if __name__ == "__main__":
    main()
