"""
CCI Course-to-Career Skill Gap Dashboard.

Reads directly from cci_pipeline_public.db (not the CSVs) -- the trimmed,
publishable copy of the database made by make_public_db.py. Reuses the query SQL
already defined in analyze.py instead of duplicating it.

Run: streamlit run dashboard.py
"""

import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from analyze import PUBLIC_DB_PATH, RARE_IN_COURSES, Q1A_SQL, Q1B_SQL, Q3_SQL, Q4A_SQL, Q4B_SQL

CREAM = "#F5F1E8"
TAN = "#E8DFCE"
GARNET = "#782F40"
GOLD = "#C99B45"
BODY_TEXT = "#3D3833"

# Heatmap colors. Zero-posting cells get a flat neutral tan (clearly distinct
# from the CREAM page background). Non-zero cells use a ramp that starts at a
# light tint OF the brand color, not at tan -- a tan-to-garnet ramp made every
# low count (most cells are 1-9 postings) look beige, and the midpoints a
# muddy mauve. The ramp runs on a log scale because counts span 1 to ~60.
HEATMAP_ZERO = "#DBCDB3"
HEATMAP_RAMP = {
    "Technical/IT": ["#E9C4CC", "#430E1B"],              # light garnet -> dark garnet
    "Communications/Marketing": ["#EED9A6", "#654915"],  # light gold -> dark gold
}
# Counts at or above this get white cell labels (the cell is dark enough);
# below it, labels use BODY_TEXT. Garnet darkens faster than gold, so its
# cutoff is lower -- picked by checking which text color has more contrast.
HEATMAP_LIGHT_TEXT_MIN = {
    "Technical/IT": 5,
    "Communications/Marketing": 15,
}
HEATMAP_WIDTH = 1000  # px, cell area only; wide enough that track names don't touch

CATEGORY_COLORS = {
    "Technical/IT": GARNET,
    "Communications/Marketing": GOLD,
}

CUSTOM_CSS = f"""
<style>
.stApp h1, .stApp h2, .stApp h3 {{
    font-style: italic !important;
    font-weight: 700 !important;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {TAN};
    border-radius: 0.5rem;
}}

[data-testid="stMetric"] {{
    background-color: transparent;
}}

div[data-testid="stAlertContainer"] {{
    background-color: {TAN} !important;
    border-radius: 0.5rem;
}}

div[data-testid="stAlertContentWarning"] {{
    border-left: 6px solid {GOLD} !important;
    padding-left: 0.75rem;
}}

div[data-testid="stAlertContentInfo"] {{
    border-left: 6px solid {GARNET} !important;
    padding-left: 0.75rem;
}}

div[data-testid="stAlertContentWarning"],
div[data-testid="stAlertContentWarning"] *,
div[data-testid="stAlertContentInfo"],
div[data-testid="stAlertContentInfo"] * {{
    color: {BODY_TEXT} !important;
}}
</style>
"""

LIS_4380_DESCRIPTION = (
    "This course explores the tools and techniques of professional social "
    "media management through hands-on work with designing and managing "
    "social media campaigns. Students participating in this class will "
    "actively design, implement, and coordinate a series of social media "
    "management tasks."
)


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
def get_headline_gap():
    return pd.read_sql_query(Q3_SQL, get_connection())


@st.cache_data
def get_school_coverage():
    conn = get_connection()
    return pd.read_sql_query(Q4A_SQL, conn), pd.read_sql_query(Q4B_SQL, conn)


st.set_page_config(page_title="CCI Course-to-Career Skill Gap", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

n_courses, n_jobs, n_skills, pull_date = get_overview_counts()

st.title("CCI Course-to-Career Skill Gap Dashboard")
st.caption("FSU College of Communication & Information")

st.warning(
    "**Data caveats**\n\n"
    "- Job posting text is truncated by Adzuna's free-tier API (~500 characters) "
    "before skill matching runs, so job-skill counts below are undercounts, not "
    "proof of zero demand.\n"
    "- Course descriptions are written abstractly, so course-skill counts are "
    "conservative — a skill may be taught without being named in the catalog "
    f"description.\n"
    f"- Job posting data is a **snapshot pulled {pull_date}** — not live; postings "
    "will go stale over time.\n\n"
    "Job posting data provided by the Adzuna API (adzuna.com)."
)

col1, col2, col3 = st.columns(3)
with col1.container(border=True):
    st.metric("Courses", n_courses)
with col2.container(border=True):
    st.metric("Job postings", f"{n_jobs:,}")
with col3.container(border=True):
    st.metric("Tracked skills", n_skills)

st.divider()

st.header("Overall Skill Demand")
st.caption(
    "How often each skill appears across all job postings, colored by category. "
    "Zero-count skills are included deliberately — they're likely undercounts "
    "from description truncation (see caveats above), not genuine zero demand."
)

demand = get_skill_demand()
chart = (
    alt.Chart(demand)
    .mark_bar()
    .encode(
        x=alt.X("n_postings:Q", title="Job postings"),
        y=alt.Y("skill:N", sort="-x", title=None),
        color=alt.Color(
            "category:N",
            title="Category",
            scale=alt.Scale(
                domain=list(CATEGORY_COLORS.keys()),
                range=list(CATEGORY_COLORS.values()),
            ),
        ),
        tooltip=["skill", "category", "n_postings"],
    )
    .properties(height=800)
)
st.altair_chart(chart, width="stretch")

st.divider()

st.header("Skill Demand by Job Track")
st.caption(
    "Posting count for each skill, broken out by the 4 job-search tracks. "
    "Each cell shows its count; darker = more postings. Blank tan cells = 0."
)

by_track = get_skill_by_track().merge(demand[["skill", "category"]], on="skill")
skill_order = demand.sort_values("n_postings", ascending=False)["skill"].tolist()
all_tracks = sorted(by_track["track"].unique())

heatmap_charts = []
for category in CATEGORY_COLORS:
    cat_skills = demand.loc[demand["category"] == category, "skill"]
    # Cartesian product of this category's skills x all tracks, so a
    # (skill, track) combo with zero postings still renders as a cell in
    # HEATMAP_ZERO instead of being silently absent (which left it looking
    # identical to the page background -- indistinguishable from "empty").
    grid = pd.MultiIndex.from_product([cat_skills, all_tracks], names=["skill", "track"]).to_frame(index=False)
    subset = grid.merge(by_track[["skill", "track", "n_postings"]], on=["skill", "track"], how="left")
    subset["n_postings"] = subset["n_postings"].fillna(0).astype(int)
    n_rows = subset["skill"].nunique()

    base = alt.Chart(subset).encode(
        x=alt.X(
            "track:N",
            title=None,
            axis=alt.Axis(
                orient="top", labelAngle=0, labelLimit=0, labelOverlap=False, labelPadding=8,
                labelFontSize=13, labelColor=BODY_TEXT,
            ),
        ),
        y=alt.Y(
            "skill:N",
            sort=skill_order,
            title=None,
            axis=alt.Axis(labelLimit=0, labelFontSize=13, labelColor=BODY_TEXT),
        ),
        tooltip=["track", "skill", "n_postings"],
    )
    cells = base.mark_rect(stroke=CREAM, strokeWidth=1).encode(
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
        title=alt.TitleParams(
            f"{category} skills", anchor="start", color=CATEGORY_COLORS[category], fontSize=15
        ),
        height=max(n_rows, 1) * 28,
        # Fixed width: with full-length axis labels, letting Streamlit stretch
        # the concat pushed the last column past the right edge.
        width=HEATMAP_WIDTH,
    )
    heatmap_charts.append(chart)

st.altair_chart(
    alt.vconcat(*heatmap_charts, spacing=30)
    .resolve_scale(color="independent")
    # Extra left padding: Vega can measure the skill labels before the Karla
    # web font loads, which clipped the longest ones on the left edge.
    .properties(padding={"left": 30, "top": 5, "right": 5, "bottom": 5}),
    width="content",
)

st.divider()

st.header("The Headline Gap: In-Demand but Rarely/Never Taught")
st.caption(
    f'"Rarely/never taught" means {RARE_IN_COURSES} or fewer CCI courses matched '
    "that skill. Click a column header to re-sort."
)

gap = get_headline_gap()
st.dataframe(
    gap,
    column_config={
        "n_postings": st.column_config.ProgressColumn(
            "n_postings", max_value=int(gap["n_postings"].max()), format="%d"
        ),
    },
    hide_index=True,
    width="stretch",
)

st.divider()

st.header("School Coverage of In-Demand Skills")
st.caption("\"In-demand\" = matched at least one job posting.")

coverage, coverage_detail = get_school_coverage()
schools = coverage["school"].tolist()
cols = st.columns(len(schools))
for col, school in zip(cols, schools):
    row = coverage[coverage["school"] == school].iloc[0]
    with col.container(border=True):
        st.metric(
            school,
            f"{row['in_demand_skills_covered']} / {row['total_in_demand_skills']}",
        )
        skills_for_school = coverage_detail[coverage_detail["school"] == school]["skill"].tolist()
        for skill in skills_for_school:
            st.markdown(f"- {skill}")

st.info(
    "**Notable finding:** \"social media management\" is taught in the "
    "**School of Information**, not Communication — via **LIS 4380 "
    f'(Social Media Management)**. Course description: *"{LIS_4380_DESCRIPTION}"*  \n\n'
    "Worth noting since this skill sounds like Communications territory at "
    "first glance."
)

st.divider()
st.caption(f"Job posting data provided by the Adzuna API (adzuna.com). Data pulled {pull_date}.")
st.caption(
    "This is an independent student data analysis project and is not officially "
    "affiliated with, endorsed by, or produced by Florida State University or the "
    "College of Communication & Information. Course data is sourced from FSU's "
    "public course catalog for educational/research purposes."
)
