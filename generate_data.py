#!/usr/bin/env python3
"""
Helensburgh Tigers – Draw Tracker Data Generator
Fetches live match data from the NRL Community GraphQL API and writes data.json.
Run locally or via GitHub Actions.
"""
import requests
import json
import sys
try:
    import pytz
    from datetime import datetime
    AEST = pytz.timezone('Australia/Sydney')
    def now_str():
        return datetime.now(AEST).strftime("%a %-d %b %Y")
    def parse_dt(ts_ms):
        return datetime.fromtimestamp(ts_ms / 1000, tz=AEST)
except ImportError:
    from datetime import datetime, timezone, timedelta
    AEST = timezone(timedelta(hours=10))
    def now_str():
        return datetime.now(AEST).strftime("%a %d %b %Y")
    def parse_dt(ts_ms):
        return datetime.fromtimestamp(ts_ms / 1000, tz=AEST)

GRAPHQL = "https://community-backend.api.nationalrugbyleague.io/graphql"

COMPS = [
    {"id": 68020257, "key": "harrigan", "name": "Harrigan Plate"},
    {"id": 65724930, "key": "women",    "name": "Open Women"},
    {"id": 65724671, "key": "u18",      "name": "U18 Gold"},
    {"id": 68289482, "key": "ollt1",    "name": "OLLT Div 1"},
    {"id": 68289607, "key": "ollt2",    "name": "OLLT Div 2"},
]

QUERY = (
    '{ competitionMatches(competitionId: %d) { '
    '_id round { number displayName } '
    'homeTeam { name } awayTeam { name } '
    'scores { homeTeam awayTeam } '
    'dateTime status venue { name } } }'
)


HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://prl.mysideline.com.au",
    "Referer": "https://prl.mysideline.com.au/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

def fetch_matches(comp_id):
    resp = requests.post(
        GRAPHQL,
        json={"query": QUERY % comp_id},
        headers=HEADERS,
        timeout=20
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("competitionMatches", [])


def clean_name(name):
    """Strip competition suffix from team name."""
    if not name:
        return "TBD"
    return name.split(" - ")[0].strip()


def process_matches(raw):
    result = []
    for m in raw:
        hn = ((m.get("homeTeam") or {}).get("name") or "")
        an = ((m.get("awayTeam") or {}).get("name") or "")
        is_home = "Helensburgh" in hn
        is_away = "Helensburgh" in an
        if not is_home and not is_away:
            continue

        dt = parse_dt(m["dateTime"])
        date_str = dt.strftime("%a %-d %b")   # e.g. "Sat 2 May"
        time_str = dt.strftime("%-I:%M%p").lower()  # e.g. "1:30pm"
        sort_key = dt.strftime("%Y%m%d%H%M")

        our   = m["scores"]["homeTeam"] if is_home else m["scores"]["awayTeam"]
        their = m["scores"]["awayTeam"] if is_home else m["scores"]["homeTeam"]
        opp   = clean_name(an if is_home else hn)
        venue = ((m.get("venue") or {}).get("name") or "")

        is_final = m["status"] == "Final"
        if is_final:
            if our > their:   res = "W"
            elif our < their: res = "L"
            else:             res = "D"
            score = f"{our} – {their}"
        else:
            res   = None
            score = None

        result.append({
            "rnd":     m["round"]["number"],
            "rndName": m["round"]["displayName"],
            "date":    date_str,
            "sortKey": sort_key,
            "time":    time_str,
            "ha":      "H" if is_home else "A",
            "opp":     opp,
            "venue":   venue,
            "score":   score,
            "res":     res,
        })

    result.sort(key=lambda x: (x["rnd"], x["sortKey"]))
    return result


def main():
    data = {"lastUpdated": now_str(), "teams": {}}

    for comp in COMPS:
        print(f"Fetching {comp['name']} (id={comp['id']})...", end=" ", flush=True)
        try:
            raw = fetch_matches(comp["id"])
            matches = process_matches(raw)
            print(f"{len(matches)} Helensburgh matches found")
        except Exception as e:
            print(f"ERROR: {e}")
            matches = []

        data["teams"][comp["key"]] = {
            "name":    comp["name"],
            "matches": matches,
        }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    total = sum(len(v["matches"]) for v in data["teams"].values())
    print(f"\n✓ data.json written — {total} total matches across all teams")


if __name__ == "__main__":
    main()
