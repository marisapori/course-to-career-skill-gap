"""
CCI Course-to-Career Skill Gap Dashboard.

Reads directly from cci_pipeline_public.db (not the CSVs) -- the trimmed,
publishable copy of the database made by make_public_db.py. Reuses the query SQL
already defined in analyze.py instead of duplicating it.

Run: streamlit run dashboard.py
"""

import sqlite3
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from analyze import (
    PUBLIC_DB_PATH, RARE_IN_COURSES, RARE_IN_JOBS,
    Q1A_SQL, Q1B_SQL, Q2_SQL, Q3_SQL, Q4A_SQL, Q4B_SQL,
)

CREAM = "#F5F1E8"
CARD = "#FFFCF6"          # card background, a touch lighter than the page
GARNET = "#782F40"
GOLD = "#C99B45"
BLUSH = "#F4DDE2"         # pastel garnet, for chips and soft accents
BUTTER = "#F7EBCB"        # pastel gold
BODY_TEXT = "#3D3833"
MUTED_TEXT = "#7A716A"

# Heatmap colors. Zero-posting cells are a faint tint just off the page color,
# so the real counts stand out instead of the grid reading as one beige block.
# Non-zero cells use a ramp that starts at a light tint OF the brand color, on
# a log scale because counts span 1 to ~60.
HEATMAP_ZERO = "#EDE6D8"
HEATMAP_RAMP = {
    "Technical/IT": ["#EBC6CE", "#430E1B"],              # blush -> dark garnet
    "Communications/Marketing": ["#F1DDA8", "#654915"],  # butter -> dark gold
}
# Counts at or above this get white cell labels (the cell is dark enough);
# below it, labels use BODY_TEXT. Garnet darkens faster than gold, so its
# cutoff is lower -- picked by checking which text color has more contrast.
HEATMAP_LIGHT_TEXT_MIN = {
    "Technical/IT": 5,
    "Communications/Marketing": 15,
}
HEATMAP_WIDTH = 900  # px, cell area only; wide enough that track names don't touch

CATEGORY_COLORS = {
    "Technical/IT": GARNET,
    "Communications/Marketing": GOLD,
}
CATEGORY_TINTS = {
    "Technical/IT": BLUSH,
    "Communications/Marketing": BUTTER,
}

# Skills called out together in the "web skills" finding.
WEB_SKILLS = ["JavaScript", "HTML", "CSS", "Python"]

AUTHOR = "Mariana Neri Sapori"
REPO_URL = "https://github.com/marisapori/course-to-career-skill-gap"
PORTFOLIO_URL = "https://marisapori.github.io"

CUSTOM_CSS = f"""
<style>
.stApp h1, .stApp h2, .stApp h3 {{
    font-style: italic !important;
    font-weight: 700 !important;
}}
.stApp h2 {{ color: {GARNET} !important; }}

.intro {{
    font-size: 1.15rem;
    color: {BODY_TEXT};
    margin: -0.5rem 0 1.5rem 0;
}}
.intro .date {{ color: {MUTED_TEXT}; font-size: 0.9rem; }}
.byline {{ margin: -1rem 0 1.5rem 0; font-size: 0.92rem; color: {MUTED_TEXT}; }}
.byline a {{
    color: {GARNET} !important;
    text-decoration: none;
    background: {BLUSH};
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    margin: 0.3rem 0 0 0.35rem;
    display: inline-block;
    white-space: nowrap;
}}
.byline a:hover {{ background: {BUTTER}; }}

/* Shared rounded card look */
.card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}}
.card {{
    background: {CARD};
    border-radius: 1.25rem;
    padding: 1.25rem 1.4rem;
    box-shadow: 0 2px 10px rgba(120, 47, 64, 0.08);
}}
.card.blush {{ background: {BLUSH}; }}
.card.butter {{ background: {BUTTER}; }}

.stat {{ text-align: center; }}
.stat .num {{
    font-family: "Bodoni Moda", serif;
    font-style: italic;
    font-weight: 700;
    font-size: 2.6rem;
    line-height: 1.1;
    color: {GARNET};
}}
.stat .label {{ color: {MUTED_TEXT}; font-size: 0.95rem; }}

.finding .big {{
    font-family: "Bodoni Moda", serif;
    font-style: italic;
    font-weight: 700;
    font-size: 2rem;
    line-height: 1.1;
    color: {GARNET};
}}
.finding.butter .big {{ color: #8A6420; }}
.finding .title {{ font-weight: 700; margin: 0.35rem 0 0.4rem 0; color: {BODY_TEXT}; }}
.finding .body {{ font-size: 0.93rem; color: {BODY_TEXT}; line-height: 1.45; }}

.chip {{
    display: inline-block;
    border-radius: 999px;
    padding: 0.2rem 0.75rem;
    margin: 0.2rem 0.25rem 0.2rem 0;
    font-size: 0.88rem;
    color: {BODY_TEXT};
}}
.chip.Technical-IT {{ background: {BLUSH}; }}
.chip.Communications-Marketing {{ background: {BUTTER}; }}
.chip.plain {{ background: {HEATMAP_ZERO}; }}

.school .name {{ font-weight: 700; color: {BODY_TEXT}; }}
.school .num {{
    font-family: "Bodoni Moda", serif;
    font-style: italic;
    font-weight: 700;
    font-size: 2rem;
    color: {GARNET};
    margin: 0.2rem 0;
}}
.school .num span {{ font-size: 1rem; color: {MUTED_TEXT}; font-style: normal; font-weight: 400; font-family: "Karla", sans-serif; }}
.school .sub {{ color: {MUTED_TEXT}; font-size: 0.88rem; margin-bottom: 0.5rem; }}

.legend {{ margin: 0 0 0.5rem 0; font-size: 0.9rem; color: {MUTED_TEXT}; }}
.legend .chip {{ font-size: 0.82rem; }}

/* Rounded expander and dataframes to match the cards */
[data-testid="stExpander"] details {{
    background: {CARD};
    border: none;
    border-radius: 1.25rem;
    box-shadow: 0 2px 10px rgba(120, 47, 64, 0.08);
}}
[data-testid="stDataFrame"] {{
    border-radius: 1rem;
    overflow: hidden;
}}

/* The heatmap is wider than a phone screen: let it scroll sideways there
   instead of being clipped, and show a hint only on narrow screens. */
div:has(> [data-testid="stVegaLiteChart"]) {{ overflow-x: auto; }}
.swipe-hint {{ display: none; color: {MUTED_TEXT}; font-size: 0.85rem; margin-top: -0.5rem; }}
@media (max-width: 700px) {{ .swipe-hint {{ display: block; }} }}

.footer {{ color: {MUTED_TEXT}; font-size: 0.82rem; margin-top: 3rem; line-height: 1.5; }}
</style>
"""


@alt.theme.register("cci", enable=True)
def cci_theme() -> alt.theme.ThemeConfig:
    # One shared look for every chart: Karla text, no gridlines or frame.
    return {
        "config": {
            "background": "transparent",
            "font": "Karla",
            "view": {"stroke": None},
            "axis": {
                "grid": False,
                "domain": False,
                "ticks": False,
                "labelColor": BODY_TEXT,
                "labelFontSize": 13,
                "titleColor": MUTED_TEXT,
                "titleFontWeight": "normal",
            },
            "title": {"font": "Karla", "fontSize": 15, "anchor": "start"},
        }
    }


@st.cache_resource
def get_connection():
    return sqlite3.connect(PUBLIC_DB_PATH, check_same_thread=False)


@st.cache_data
def get_overview_counts():
    conn = get_connection()
    n_courses = pd.read_sql_query("SELECT COUNT(*) AS n FROM courses", conn)["n"][0]
    n_jobs = pd.read_sql_query("SELECT COUNT(*) AS n FROM jobs", conn)["n"][0]
    n_skills = pd.read_sql_query("SELECT COUNT(*) AS n FROM skills", conn)["n"][0]
    pull_date = pd.read_sql_query("SELECT DISTINCT pull_date FROM jobs", conn)["pull_date"][0]
    return n_courses, n_jobs, n_skills, pull_date


@st.cache_data
def get_skill_demand():
    return pd.read_sql_query(Q1A_SQL, get_connection())


@st.cache_data
def get_skill_by_track():
    return pd.read_sql_query(Q1B_SQL, get_connection())


@st.cache_data
def get_taught_not_demanded():
    return pd.read_sql_query(Q2_SQL, get_connection())


@st.cache_data
def get_headline_gap():
    return pd.read_sql_query(Q3_SQL, get_connection())


@st.cache_data
def get_school_coverage():
    conn = get_connection()
    return pd.read_sql_query(Q4A_SQL, conn), pd.read_sql_query(Q4B_SQL, conn)


@st.cache_data
def get_courses_per_skill():
    # Which courses name each skill, e.g. "LIS 3781 Advanced Database Management; ...".
    return pd.read_sql_query(
        """
        SELECT skill, GROUP_CONCAT(course, '; ') AS courses
        FROM (
            SELECT DISTINCT cs.skill, c.course_code || ' ' || c.title AS course
            FROM course_skills cs
            JOIN courses c ON c.course_code = cs.course_code
            ORDER BY c.course_code
        )
        GROUP BY skill;
        """,
        get_connection(),
    )


@st.cache_data
def get_web_courses():
    return pd.read_sql_query(
        "SELECT course_code || ' ' || title AS course FROM courses "
        "WHERE title LIKE '%web%' ORDER BY course_code",
        get_connection(),
    )["course"].tolist()


@st.cache_data
def get_courses_per_school():
    return pd.read_sql_query(
        "SELECT school, COUNT(*) AS n_courses FROM courses GROUP BY school", get_connection()
    )


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def chip(text, category=None):
    css_class = category.replace("/", "-") if category else "plain"
    return f'<span class="chip {css_class}">{escape(text)}</span>'


def table_height(df):
    # Tall enough to show every row without an inner scrollbar.
    return (len(df) + 1) * 35 + 3


def with_courses(df):
    """Add a readable 'Taught in' column listing the matching courses."""
    out = df.merge(get_courses_per_skill(), on="skill", how="left")
    out["courses"] = out["courses"].fillna("No course names it")
    return out


st.set_page_config(page_title="CCI Course-to-Career Skill Gap", page_icon="favicon.png", layout="wide")
html(CUSTOM_CSS)

n_courses, n_jobs, n_skills, pull_date = get_overview_counts()
demand = get_skill_demand()
gap = with_courses(get_headline_gap())
coverage, coverage_detail = get_school_coverage()
courses_per_school = get_courses_per_school().set_index("school")["n_courses"]
skill_category = demand.set_index("skill")["category"]

# ---------------------------------------------------------------- header

st.title("CCI Course-to-Career Skill Gap")
html(
    '<div class="intro">What FSU\'s College of Communication &amp; Information teaches, '
    "compared with what entry-level employers ask for. "
    f'<span class="date">Job data snapshot from {pull_date}.</span></div>'
)
html(
    f'<div class="byline">By {AUTHOR}'
    f'<a href="{REPO_URL}" target="_blank">Code on GitHub</a>'
    f'<a href="{PORTFOLIO_URL}" target="_blank">Portfolio</a></div>'
)

html(
    '<div class="card-grid">'
    f'<div class="card stat"><div class="num">{n_courses}</div><div class="label">CCI courses</div></div>'
    f'<div class="card stat"><div class="num">{n_jobs:,}</div><div class="label">job postings</div></div>'
    f'<div class="card stat"><div class="num">{n_skills}</div><div class="label">skills tracked</div></div>'
    "</div>"
)

# ---------------------------------------------------------- key findings

st.header("Key findings")

ai = gap.set_index("skill").loc["AI"]
ai_rank_title = (
    "AI is the most-requested skill"
    if (demand["n_postings"] < ai["n_postings"]).sum() == len(demand) - 1
    else "AI ties for the most-requested skill"
)
track_counts = get_skill_by_track()
ai_tracks = (track_counts["skill"] == "AI").sum()
n_tracks = track_counts["track"].nunique()
ai_tracks_text = f"all {n_tracks}" if ai_tracks == n_tracks else f"{ai_tracks} of {n_tracks}"
web = demand.set_index("skill").loc[WEB_SKILLS, "n_postings"]
web_untaught = gap[gap["skill"].isin(WEB_SKILLS) & (gap["n_courses"] == 0)]
web_courses = get_web_courses()
taught = with_courses(get_taught_not_demanded())
taught_unrequested = taught.loc[taught["n_postings"] == 0, "skill"].tolist()
cov = coverage.set_index("school")
info_cov = cov.loc["School of Information", "in_demand_skills_covered"]
comm_cov = cov.loc["School of Communication", "in_demand_skills_covered"]
total_in_demand = cov["total_in_demand_skills"].iloc[0]


def finding(big, title, body, tint):
    return (
        f'<div class="card finding {tint}"><div class="big">{big}</div>'
        f'<div class="title">{title}</div><div class="body">{body}</div></div>'
    )


html(
    '<div class="card-grid">'
    + finding(
        f"{ai['n_postings']} postings",
        ai_rank_title,
        f"It shows up in {ai_tracks_text} job tracks, but only {ai['n_courses']} course names it: "
        f"{escape(ai['courses'])}.",
        "blush",
    )
    + finding(
        f"{len(web_untaught)} languages",
        "Web development is taught, but the languages are never named",
        ", ".join(f"{s} ({web[s]})" for s in web_untaught["skill"])
        + f" show up in job postings. CCI has {len(web_courses)} web development courses, "
        f"like {escape(web_courses[0])}, but none of their descriptions name these languages.",
        "butter",
    )
    + finding(
        f"{len(taught_unrequested)} skills",
        "Taught, but not in a single posting",
        ", ".join(escape(s) for s in taught_unrequested)
        + " each have a CCI course, but none of this snapshot's postings mention them.",
        "blush",
    )
    + finding(
        f"{info_cov} vs. {comm_cov}",
        "The School of Information covers more",
        f"Of {total_in_demand} in-demand skills, Information courses cover {info_cov} and "
        f"Communication courses cover {comm_cov}, even though Communication has "
        f"{courses_per_school['School of Communication']} courses to Information's "
        f"{courses_per_school['School of Information']}.",
        "butter",
    )
    + "</div>"
)

with st.expander("About the data and how it works"):
    st.markdown(
        "**How it works.** Every course (title and description) and every job posting "
        f"description was checked against one shared list of {n_skills} skills, using "
        "whole-word keyword matching plus a few spelled-out forms (\"user experience design\" "
        "counts as UX design). Job postings "
        "come from the Adzuna API, searched with entry-level titles in four tracks: "
        "Advertising / Marketing, Digital Media / Production, IT / Information Systems "
        "and Public Relations.\n\n"
        "**Keep in mind:**\n"
        "- The search terms shape the results. Skills that were search terms (like "
        "digital marketing or cybersecurity) rank high partly by design. Skills that "
        "weren't (like AI and SQL) are better evidence of real demand.\n"
        "- Job counts are undercounts. Adzuna's free API cuts posting text off at about "
        "500 characters, so a skill mentioned further down isn't counted.\n"
        "- Course counts are conservative. Catalog descriptions are written abstractly, "
        "so a skill may be taught without being named.\n"
        f"- Job data is a snapshot pulled {pull_date}, not live.\n\n"
        "Job posting data provided by the Adzuna API (adzuna.com)."
    )

# --------------------------------------------------------- skill demand

st.header("Which skills employers ask for")
st.caption("How many job postings mention each skill, split by skill category.")


def demand_chart(category):
    data = demand[demand["category"] == category]
    base = alt.Chart(data).encode(
        x=alt.X("n_postings:Q", axis=None, scale=alt.Scale(domain=[0, demand["n_postings"].max() * 1.12])),
        y=alt.Y("skill:N", sort="-x", title=None, axis=alt.Axis(labelLimit=0, labelPadding=8)),
        tooltip=[alt.Tooltip("skill", title="Skill"), alt.Tooltip("n_postings", title="Job postings")],
    )
    bars = base.mark_bar(color=CATEGORY_COLORS[category], cornerRadiusEnd=8, height=16)
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=MUTED_TEXT).encode(text="n_postings:Q")
    return (bars + labels).properties(
        title=alt.TitleParams(f"{category} skills", color=CATEGORY_COLORS[category]),
        height=len(data) * 24,
    )


left, right = st.columns(2, gap="large")
left.altair_chart(demand_chart("Technical/IT"), width="stretch", theme=None)
right.altair_chart(demand_chart("Communications/Marketing"), width="stretch", theme=None)

# ------------------------------------------------------------- heatmap

st.header("Skill demand by job track")
st.caption("Each cell is the number of postings in that track that mention the skill. Darker = more postings.")
html('<div class="swipe-hint">Swipe sideways to see all four tracks.</div>')

by_track = get_skill_by_track().merge(demand[["skill", "category"]], on="skill")
skill_order = demand.sort_values("n_postings", ascending=False)["skill"].tolist()
all_tracks = sorted(by_track["track"].unique())
never_requested = demand.loc[demand["n_postings"] == 0, "skill"].tolist()

heatmap_charts = []
for category in CATEGORY_COLORS:
    # Skills with zero postings anywhere are left out of the grid (an all-blank
    # row says nothing) and listed underneath instead.
    cat_skills = demand.loc[(demand["category"] == category) & (demand["n_postings"] > 0), "skill"]
    # Cartesian product of this category's skills x all tracks, so a
    # (skill, track) combo with zero postings still renders as a faint cell
    # instead of being silently absent.
    grid = pd.MultiIndex.from_product([cat_skills, all_tracks], names=["skill", "track"]).to_frame(index=False)
    subset = grid.merge(by_track[["skill", "track", "n_postings"]], on=["skill", "track"], how="left")
    subset["n_postings"] = subset["n_postings"].fillna(0).astype(int)
    n_rows = subset["skill"].nunique()

    base = alt.Chart(subset).encode(
        x=alt.X(
            "track:N",
            title=None,
            axis=alt.Axis(orient="top", labelAngle=0, labelLimit=0, labelOverlap=False, labelPadding=8),
        ),
        y=alt.Y("skill:N", sort=skill_order, title=None, axis=alt.Axis(labelLimit=0, labelPadding=8)),
        tooltip=[
            alt.Tooltip("track", title="Track"),
            alt.Tooltip("skill", title="Skill"),
            alt.Tooltip("n_postings", title="Job postings"),
        ],
    )
    cells = base.mark_rect(stroke=CREAM, strokeWidth=3, cornerRadius=6).encode(
        color=alt.condition(
            alt.datum.n_postings > 0,
            alt.Color(
                "n_postings:Q",
                legend=None,
                # Explicit domain: log(0) is undefined, so the zero cells (colored
                # by the condition below) must be kept out of the scale.
                scale=alt.Scale(
                    type="log",
                    domain=[1, int(subset["n_postings"].max())],
                    range=HEATMAP_RAMP[category],
                    interpolate="hcl",
                ),
            ),
            alt.value(HEATMAP_ZERO),
        ),
    )
    labels = base.transform_filter(alt.datum.n_postings > 0).mark_text(fontSize=12, fontWeight="bold").encode(
        text="n_postings:Q",
        color=alt.condition(
            alt.datum.n_postings >= HEATMAP_LIGHT_TEXT_MIN[category], alt.value("white"), alt.value(BODY_TEXT)
        ),
    )
    chart = (cells + labels).properties(
        title=alt.TitleParams(f"{category} skills", color=CATEGORY_COLORS[category]),
        height=n_rows * 30,
        # Fixed width: with full-length axis labels, letting Streamlit stretch
        # the concat pushed the last column past the right edge.
        width=HEATMAP_WIDTH,
    )
    heatmap_charts.append(chart)

st.altair_chart(
    alt.vconcat(*heatmap_charts, spacing=36)
    .resolve_scale(color="independent")
    # Extra left padding: Vega can measure the skill labels before the Karla
    # web font loads, which clipped the longest ones on the left edge.
    .properties(padding={"left": 30, "top": 5, "right": 5, "bottom": 5}),
    width="content",
    theme=None,
)
if never_requested:
    html(
        '<div class="legend">Not found in any posting: '
        + "".join(chip(s) for s in never_requested)
        + "</div>"
    )

# ------------------------------------------------------------- the gaps

GAP_COLUMNS = {
    "skill": st.column_config.TextColumn("Skill", width="medium"),
    "category": st.column_config.TextColumn("Category", width="medium"),
    "n_courses": st.column_config.NumberColumn("Courses", width="small"),
    "courses": st.column_config.TextColumn("Taught in", width="large"),
}

st.header("In demand, but rarely taught")
st.caption(
    f"Skills found in job postings that {RARE_IN_COURSES} or fewer CCI course descriptions mention. "
    "Click a column header to re-sort."
)
st.dataframe(
    gap[["skill", "n_postings", "n_courses", "courses", "category"]],
    column_config=GAP_COLUMNS
    | {
        "n_postings": st.column_config.ProgressColumn(
            "Job postings", max_value=int(gap["n_postings"].max()), format="%d", color=GARNET
        ),
    },
    hide_index=True,
    width="stretch",
    height=table_height(gap),
)

st.header("Taught, but rarely asked for")
st.caption(f"Skills CCI courses teach that showed up in {RARE_IN_JOBS} or fewer job postings.")
st.dataframe(
    taught[["skill", "n_courses", "n_postings", "courses", "category"]],
    column_config=GAP_COLUMNS | {"n_postings": st.column_config.NumberColumn("Job postings")},
    hide_index=True,
    width="stretch",
    height=table_height(taught),
)

# ------------------------------------------------------ school coverage

st.header("Which school covers what")
st.caption(f"Out of the {total_in_demand} skills that appeared in at least one job posting.")

school_cards = []
for _, row in coverage.iterrows():
    school = row["school"]
    skills = coverage_detail.loc[coverage_detail["school"] == school, "skill"]
    school_cards.append(
        f'<div class="card school"><div class="name">{escape(school)}</div>'
        f'<div class="num">{row["in_demand_skills_covered"]} <span>of {row["total_in_demand_skills"]} skills</span></div>'
        f'<div class="sub">{courses_per_school[school]} courses</div>'
        + "".join(chip(s, skill_category[s]) for s in skills)
        + "</div>"
    )
html('<div class="card-grid">' + "".join(school_cards) + "</div>")

html(
    '<div class="card blush"><b>A surprise:</b> social media management sounds like '
    "Communication territory, but it's taught in the <b>School of Information</b>, in "
    "<b>LIS 4380 (Social Media Management)</b>, a hands-on course where students design "
    "and manage social media campaigns.</div>"
)

# ---------------------------------------------------------------- footer

html(
    f'<div class="footer">Job posting data provided by the Adzuna API (adzuna.com). '
    f"Data pulled {pull_date}.<br>"
    "This is an independent student data analysis project and is not officially "
    "affiliated with, endorsed by, or produced by Florida State University or the "
    "College of Communication &amp; Information. Course data is sourced from FSU's "
    "public course catalog for educational/research purposes.</div>"
)
