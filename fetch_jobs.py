"""
Pull job postings from Adzuna API relevant to FSU CCI majors (IT, Information
Systems, Advertising, PR, Digital Media, Communications).

This script is used under Adzuna's "Personal or academic research" permitted
use category (see https://developer.adzuna.com/docs/terms_of_service).
Per their terms, any published output must acknowledge Adzuna as the data
source with a link to https://www.adzuna.com/ -- include a line like:
  "Job posting data provided by the Adzuna API (adzuna.com)"
in your README / writeup / dashboard footer.

Free tier limits (as of their current ToS): 25 hits/min, 250/day, 1000/week,
2500/month. This script makes ~34 calls total (17 search terms x 2 pages),
well within all of those.

SETUP:
1. pip install requests python-dotenv --break-system-packages
2. Create a .env file in this same folder with:
     ADZUNA_APP_ID=your_app_id_here
     ADZUNA_APP_KEY=your_app_key_here
3. Run: python fetch_jobs.py
"""


import os
import time
from datetime import date
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")
COUNTRY = "us"  # Adzuna country code
BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search"

# Search terms mapped to the CCI tracks they represent.
# Feel free to add/remove terms — these are a starting point covering both
# School of Information (IT) and School of Communication career paths.
SEARCH_TERMS = {
    "IT / Information Systems": [
        "information technology analyst",
        "database administrator",
        "network administrator",
        "IT support specialist",
        "web developer",
        "data analyst",
        "cybersecurity analyst",
        "UX designer",
        "UI designer",
    ],
    "Advertising / Marketing": [
        "advertising coordinator",
        "digital marketing specialist",
        "media planner",
        "marketing analyst",
    ],
    "Public Relations": [
        "public relations coordinator",
        "communications specialist",
        "PR assistant",
    ],
    "Digital Media / Production": [
        "social media manager",
        "video editor",
        "content producer",
    ],
}

RESULTS_PER_TERM = 30  # Adzuna max per page is 50; keep modest to stay in free tier
PAGES_PER_TERM = 2     # pulls RESULTS_PER_TERM x PAGES_PER_TERM postings per search term


def fetch_jobs_for_term(term, track, max_pages=PAGES_PER_TERM):
    """Fetch job postings for a single search term across a few pages."""
    all_jobs = []
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/{page}"
        params = {
            "app_id": APP_ID,
            "app_key": APP_KEY,
            "results_per_page": RESULTS_PER_TERM,
            "what": term,
            "content-type": "application/json",
        }
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            print(f"  [!] Error {resp.status_code} for '{term}' page {page}: {resp.text[:200]}")
            break

        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        for job in results:
            all_jobs.append({
                "pull_date": date.today().isoformat(),
                "search_term": term,
                "track": track,
                "job_id": job.get("id"),
                "title": job.get("title"),
                "company": (job.get("company") or {}).get("display_name"),
                "location": (job.get("location") or {}).get("display_name"),
                "category": (job.get("category") or {}).get("label"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "created": job.get("created"),
                "description": job.get("description"),
                "redirect_url": job.get("redirect_url"),
            })

        time.sleep(0.5)  # be polite to the API

    return all_jobs


def main():
    if not APP_ID or not APP_KEY:
        raise SystemExit(
            "Missing ADZUNA_APP_ID / ADZUNA_APP_KEY. "
            "Create a .env file with your credentials before running this script."
        )

    all_jobs = []
    for track, terms in SEARCH_TERMS.items():
        for term in terms:
            print(f"Fetching: {term} ({track})...")
            jobs = fetch_jobs_for_term(term, track)
            print(f"  -> {len(jobs)} postings")
            all_jobs.extend(jobs)

    df = pd.DataFrame(all_jobs)
    df.drop_duplicates(subset="job_id", inplace=True)

    today_str = date.today().isoformat()
    filename = f"cci_job_postings_{today_str}.csv"
    df.to_csv(filename, index=False)

    # Also save/overwrite a "latest" copy for convenience in downstream scripts
    df.to_csv("cci_job_postings_latest.csv", index=False)

    print(f"\nDone. {len(df)} unique postings saved to {filename}")
    print(f"(also saved as cci_job_postings_latest.csv)")
    print(f"This is a SNAPSHOT as of {today_str} -- postings will go stale over")
    print("time. Re-run this script whenever you want a fresh pull; each run")
    print("creates a new dated file so you can keep a history if you want.")


if __name__ == "__main__":
    main()
