#!/usr/bin/env python3
"""
update_scores.py
-----------------
Run this once a day (cron/Task Scheduler) to:
  1. Pull current fixture data for your 5 tracked leagues from football-data.org
  2. Update scores for finished matches, and dates/times for any fixture the
     league has rescheduled
  3. Regenerate big-fixtures.ics (and the no-Arsenal variant)

Setup:
  pip install requests
  Get a free API key: https://www.football-data.org/client/register
  export FOOTBALL_DATA_API_KEY="a78dd97ff7584ba1ad390601276df4c9"

Usage:
  python update_scores.py
  python update_scores.py --data big_fixtures.json --outdir ./out
"""

import argparse
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run: pip install requests")

API_BASE = "https://api.football-data.org/v4"
COMPETITIONS = {
    "Premier League": "PL",
    "La Liga": "PD",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Ligue 1": "FL1",
}

# Keywords used to match OUR team names against whatever names
# football-data.org returns. Order matters for the Milan/Inter collision.
KEYWORDS = {
    "Arsenal": ["arsenal"],
    "Chelsea": ["chelsea"],
    "Spurs": ["tottenham"],
    "Man Utd": ["manchester united", "man utd", "man united"],
    "Man City": ["manchester city", "man city"],
    "Liverpool": ["liverpool"],
    "Real Madrid": ["real madrid"],
    "FC Barcelona": ["barcelona"],
    "Atlético de Madrid": [
        "atletico madrid",
        "atlético madrid",
        "atletico de madrid",
        "atlético de madrid",
    ],
    "FC Bayern München": ["bayern"],
    "Borussia Dortmund": ["dortmund"],
    "Como": ["como"],
    "Milan": ["ac milan"],  # must NOT match "inter"
    "Internazionale": ["inter milan", "internazionale", "fc internazionale"],
    "Juventus": ["juventus"],
    "Roma": ["as roma"],
    "Paris Saint-Germain": ["paris saint-germain", "psg"],
    "AS Monaco": ["as monaco", "monaco fc"],
    "Olympique Lyonnais": ["olympique lyonnais", "lyon"],
}

LEAGUE_SHORT = {
    "Premier League": "PL",
    "La Liga": "LIGA",
    "Bundesliga": "BUND",
    "Serie A": "SERIE A",
    "Ligue 1": "LIGUE 1",
}


def normalize(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip()


def matches_keyword(our_name, api_name):
    api_norm = normalize(api_name)
    for kw in KEYWORDS.get(our_name, [our_name.lower()]):
        if kw in api_norm:
            return True
    return False


def fetch_competition_matches(code, api_key):
    url = f"{API_BASE}/competitions/{code}/matches"
    headers = {"X-Auth-Token": api_key}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 429:
        print(f"  Rate limited on {code}, waiting 60s...")
        time.sleep(60)
        resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("matches", [])


def find_api_match(api_matches, home, away):
    for m in api_matches:
        api_home = m["homeTeam"]["name"]
        api_away = m["awayTeam"]["name"]
        if matches_keyword(home, api_home) and matches_keyword(away, api_away):
            return m
    return None


def collect_crests(api_match, home_name, away_name, crests):
    home_crest = api_match.get("homeTeam", {}).get("crest")
    away_crest = api_match.get("awayTeam", {}).get("crest")
    if home_crest:
        crests[home_name] = home_crest
    if away_crest:
        crests[away_name] = away_crest


def update_fixture_from_api(fixture, api_match):
    changed = []
    utc_dt = datetime.strptime(api_match["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
    # football-data.org gives UTC; store as-is with a UTC marker so it's unambiguous.
    new_date = utc_dt.strftime("%Y-%m-%d")
    new_time = utc_dt.strftime("%H:%M")

    if fixture["date"] != new_date or fixture.get("time") != new_time:
        changed.append(
            f"kickoff {fixture['date']} {fixture.get('time')} -> {new_date} {new_time} UTC"
        )
        fixture["date"] = new_date
        fixture["time"] = new_time
        fixture["confirmed_time"] = True
        fixture["time_is_utc"] = True

    status = api_match.get("status")
    if status == "FINISHED":
        score = api_match.get("score", {}).get("fullTime", {})
        h, a = score.get("home"), score.get("away")
        if h is not None and a is not None:
            result = f"{h} - {a}"
            if fixture.get("result") != result:
                changed.append(f"result -> {result}")
            fixture["result"] = result

    return changed


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def build_ics(fixtures):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Big Fixtures//Rivalry Wire//EN",
        "CALSCALE:GREGORIAN",
    ]
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for f in fixtures:
        uid = f"bigfixtures-{f['league']}-{f['round']}-{f['home']}-{f['away']}"
        uid = "".join(c if c.isalnum() else "-" for c in uid).lower() + "@bigfixtures"
        summary = esc(f"{f['home']} vs {f['away']} ({LEAGUE_SHORT[f['league']]})")
        desc = esc(
            f"{f['league']} \u2014 Round {f['round']}"
            + (
                ""
                if f["confirmed_time"]
                else ". Kickoff time not yet confirmed by the league."
            )
            + (f". Result: {f['result']}" if f.get("result") else "")
        )
        loc = esc(f["venue"])
        date_compact = f["date"].replace("-", "")

        lines.append("BEGIN:VEVENT")
        lines.append("UID:" + uid)
        lines.append("DTSTAMP:" + dtstamp)

        if f["confirmed_time"]:
            start = datetime.strptime(f["date"] + " " + f["time"], "%Y-%m-%d %H:%M")
            end = start + timedelta(hours=2, minutes=15)
            suffix = "Z" if f.get("time_is_utc") else ""
            lines.append("DTSTART:" + start.strftime("%Y%m%dT%H%M%S") + suffix)
            lines.append("DTEND:" + end.strftime("%Y%m%dT%H%M%S") + suffix)
        else:
            start = datetime.strptime(f["date"], "%Y-%m-%d")
            end = start + timedelta(days=1)
            lines.append("DTSTART;VALUE=DATE:" + start.strftime("%Y%m%d"))
            lines.append("DTEND;VALUE=DATE:" + end.strftime("%Y%m%d"))

        lines.append("SUMMARY:" + summary)
        lines.append("LOCATION:" + loc)
        lines.append("DESCRIPTION:" + desc)
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", default="big_fixtures.json", help="Path to the master fixture JSON"
    )
    parser.add_argument(
        "--outdir", default=".", help="Where to write updated .ics files"
    )
    parser.add_argument(
        "--exclude-team",
        action="append",
        default=[],
        help="Team name to exclude from the 'no-overlap' ics (repeatable)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        sys.exit("Set FOOTBALL_DATA_API_KEY in your environment first.")

    with open(args.data) as f:
        fixtures = json.load(f)

    api_cache = {}
    total_changes = 0
    crests_path = os.path.join(args.outdir, "team_crests.json")
    crests = {}
    if os.path.exists(crests_path):
        with open(crests_path) as f:
            crests = json.load(f)

    for league, code in COMPETITIONS.items():
        relevant = [fx for fx in fixtures if fx["league"] == league]
        if not relevant:
            continue
        print(f"Fetching {league} ({code})...")
        api_matches = fetch_competition_matches(code, api_key)
        api_cache[league] = api_matches
        time.sleep(6)  # stay comfortably under 10 req/min

        for fx in relevant:
            m = find_api_match(api_matches, fx["home"], fx["away"])
            if not m:
                print(
                    f"  ! No API match found for {fx['home']} vs {fx['away']} (round {fx['round']})"
                )
                continue
            changes = update_fixture_from_api(fx, m)
            collect_crests(m, fx["home"], fx["away"], crests)
            if changes:
                total_changes += len(changes)
                print(f"  {fx['home']} vs {fx['away']}: " + "; ".join(changes))

    with open(args.data, "w") as f:
        json.dump(fixtures, f, indent=1, ensure_ascii=False)

    os.makedirs(args.outdir, exist_ok=True)

    with open(crests_path, "w") as f:
        json.dump(crests, f, indent=1, ensure_ascii=False)

    full_ics = build_ics(fixtures)
    with open(os.path.join(args.outdir, "big-fixtures.ics"), "w") as f:
        f.write(full_ics)

    if args.exclude_team:
        filtered = [
            fx
            for fx in fixtures
            if fx["home"] not in args.exclude_team
            and fx["away"] not in args.exclude_team
        ]
        filt_ics = build_ics(filtered)
        with open(os.path.join(args.outdir, "big-fixtures-filtered.ics"), "w") as f:
            f.write(filt_ics)

    print(f"\nDone. {total_changes} field(s) updated. Files written to {args.outdir}/")


if __name__ == "__main__":
    main()
