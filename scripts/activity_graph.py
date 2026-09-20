"""Generate a 31-day GitHub activity line graph as an SVG.

Env vars:
  GITHUB_TOKEN  token for the GraphQL API (the Actions default one works)
  GH_USER       GitHub username (defaults to GITHUB_REPOSITORY_OWNER)
  OUT_PATH      output file (defaults to assets/activity-graph.svg)
"""
import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

SHOW_VALUES = True  # print the count above each point (hover does not work on GitHub)
GREEN = "#2ECC71"
MUTED = "#8b949e"
DAYS = 31

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_days(login, token):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=DAYS + 1)
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": login,
            "from": start.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    today = end.date()
    days = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    return [(d, counts.get(d.isoformat(), 0)) for d in days]


def render(days):
    W, H = 900, 318
    L, R, T, B = 60, 24, 34, 70
    pw, ph = W - L - R, H - T - B
    n = len(days)
    peak = max(c for _, c in days)
    raw = math.ceil(max(peak, 5) / 5)
    steps = sorted(b * 10**k for k in range(0, 7) for b in (1, 2, 3, 4, 5, 6, 8))
    step = next(s for s in steps if s >= raw)
    ymax = step * 5

    def px(i):
        return L + i * pw / (n - 1)

    def py(v):
        return T + ph - v * ph / ymax

    pts = [(px(i), py(c)) for i, (_, c) in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},{T + ph} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{T + ph} Z"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" fill="{MUTED}">',
        f'<title>GitHub activity, last {DAYS} days</title>',
    ]
    for k in range(6):
        v = k * step
        y = py(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="{MUTED}" stroke-opacity="0.25" stroke-width="1"/>')
        out.append(f'<text x="{L - 10}" y="{y + 4:.1f}" text-anchor="end">{v}</text>')
    for i, (d, _) in enumerate(days):
        x = px(i)
        out.append(f'<text x="{x:.1f}" y="{T + ph + 20}" text-anchor="middle">{d.day}</text>')
        if i == 0 or d.day == 1:
            out.append(f'<text x="{x:.1f}" y="{T + ph + 36}" text-anchor="middle" font-size="11">{d.strftime("%b")}</text>')
    out.append(f'<text x="{L + pw / 2:.1f}" y="{H - 10}" text-anchor="middle">Days</text>')
    out.append(f'<text transform="translate(16 {T + ph / 2:.1f}) rotate(-90)" text-anchor="middle">Contributions</text>')
    out.append(f'<path d="{area}" fill="{GREEN}" fill-opacity="0.2"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{GREEN}" stroke-width="2" stroke-linejoin="round"/>')
    for (x, y), (d, c) in zip(pts, days):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#fff" stroke="{GREEN}" stroke-width="2"><title>{d.isoformat()}: {c}</title></circle>')
    if SHOW_VALUES:
        for (x, y), (_, c) in zip(pts, days):
            out.append(f'<text x="{x:.1f}" y="{y - 9:.1f}" text-anchor="middle" font-size="11">{c}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    login = os.environ.get("GH_USER") or os.environ["GITHUB_REPOSITORY_OWNER"]
    token = os.environ["GITHUB_TOKEN"]
    path = os.environ.get("OUT_PATH", "assets/activity-graph.svg")
    svg = render(fetch_days(login, token))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
