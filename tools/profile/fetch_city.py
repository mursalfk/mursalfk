#!/usr/bin/env python3
"""
fetch_city.py
Pulls the last ~53 weeks of contribution counts (incl. private, via
METRICS_TOKEN) plus a handful of headline numbers from GitHub's GraphQL
API, and writes assets/data/city.json.

Never starts from scratch: if the request fails, the previous JSON is
left untouched so the rendered SVG never goes blank on a bad API day.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GITHUB_PROFILE_USER", "mursalfk")
TOKEN = os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "data", "city.json")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests(states: MERGED) { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      nodes { stargazerCount forkCount }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-console",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.loads(res.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError("GraphQL error: " + "; ".join(e["message"] for e in payload["errors"]))
    return payload["data"]


def load_previous():
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"weeks": [], "stats": {}}


def main():
    if not TOKEN:
        print("warn: no METRICS_TOKEN/GITHUB_TOKEN set, keeping previous data", file=sys.stderr)
        return

    today = datetime.now(timezone.utc)
    frm = today - timedelta(days=370)
    variables = {
        "login": USER,
        "from": frm.strftime("%Y-%m-%dT00:00:00Z"),
        "to": today.strftime("%Y-%m-%dT23:59:59Z"),
    }

    data = load_previous()
    try:
        result = graphql(QUERY, variables)["user"]
        cal = result["contributionsCollection"]["contributionCalendar"]
        stars = sum(r["stargazerCount"] for r in result["repositories"]["nodes"])
        forks = sum(r["forkCount"] for r in result["repositories"]["nodes"])

        weeks = [
            [{"date": d["date"], "count": d["contributionCount"]} for d in w["contributionDays"]]
            for w in cal["weeks"]
        ]
        weeks = [w for w in weeks if len(w) == 7]

        data = {
            "generated_at": today.isoformat(),
            "weeks": weeks,
            "stats": {
                "total_last_year": cal["totalContributions"],
                "followers": result["followers"]["totalCount"],
                "merged_prs": result["pullRequests"]["totalCount"],
                "stars": stars,
                "forks": forks,
            },
        }
    except (urllib.error.URLError, RuntimeError, KeyError) as ex:
        print(f"warn: fetch failed, keeping previous data: {ex}", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()