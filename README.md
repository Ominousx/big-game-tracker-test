# Big Fixtures

A one-page tracker for every meeting between the clubs you follow across the
Premier League, La Liga, Bundesliga, Serie A, and Ligue 1 this season —
plus a downloadable/subscribable `.ics` calendar.

**Live site:** https://ominousx.github.io/big-game-tracker-test/

## Structure
- `index.html` — the site (static, no build step)
- `data/big_fixtures.json` — the dataset the page reads
- `data/big-fixtures.ics` / `data/big-fixtures-filtered.ics` — pre-built calendars
  (the "filtered" one drops Arsenal fixtures)
- `data/team_crests.json` — team name → crest image URL, populated by the updater
- `update_scores.py` — refreshes scores/dates from football-data.org and regenerates
  the two `.ics` files plus the crests map
- `.github/workflows/update-scores.yml` — runs `update_scores.py` automatically every
  day and pushes the result, so the site keeps itself current

## One-time setup for the daily auto-update
1. Get a free API key: https://www.football-data.org/client/register
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret**
   — name it `FOOTBALL_DATA_API_KEY`, paste the key as the value.
3. **Settings → Actions → General → Workflow permissions** — set to
   "Read and write permissions" (the Action needs this to push its own commits).
4. That's it. It runs daily at 23:00 UTC, or trigger it manually anytime from the
   **Actions** tab → "Update fixture scores" → "Run workflow".

## Running it manually instead
```
export FOOTBALL_DATA_API_KEY="your-key"
python update_scores.py --data data/big_fixtures.json --outdir data --exclude-team Arsenal
git add data/
git commit -m "Update scores"
git push
```

## Calendar subscription vs download
The site offers both:
- **Download** — one-time import, generated client-side from the fixtures shown on the page.
- **Subscribe** — a `webcal://` link pointing at the files in `data/`. Once added to
  Apple Calendar, it re-checks on its own — as long as the daily Action (or your manual
  runs) keeps `data/big-fixtures.ics` current, the subscription stays current too, no
  re-importing needed.
