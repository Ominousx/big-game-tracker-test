# Big Fixtures

A one-page tracker for every meeting between the clubs you follow across the
Premier League, La Liga, Bundesliga, Serie A, and Ligue 1 this season —
plus a downloadable `.ics` calendar file.

**Live site:** set after first deploy — `https://ominousx.github.io/big-game-tracker-test/`

## Structure
- `index.html` — the site itself (static, no build step)
- `data/big_fixtures.json` — the fixture dataset the page reads
- `data/big-fixtures.ics` — pre-built calendar file (also downloadable from the site)
- `update_scores.py` — run locally to refresh scores/dates from football-data.org, then
  commit + push the updated `data/` files to update the live site

## Updating scores
```
export FOOTBALL_DATA_API_KEY="your-key"
python update_scores.py --data data/big_fixtures.json --outdir data --exclude-team Arsenal
git add data/
git commit -m "Update scores"
git push
```
