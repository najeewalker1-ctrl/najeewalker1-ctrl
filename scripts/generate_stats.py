#!/usr/bin/env python3
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from svg_common import font_face_css, svg_open, theme_style, xml_escape

ROOT = Path(__file__).resolve().parent.parent
BODY_WIDTH = 696.6
API_URL = "https://api.github.com/graphql"

RAMP = " .`:-=+*cs#%@"
CHAR_W = 7.74
LINE_H = 16.13

LANG_COLOR_FALLBACK = "#8a8a8a"

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
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

LANG_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-script",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def utc_window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    frm = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=timezone.utc)
    to = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
    return frm.isoformat(), to.isoformat()


def fetch_contributions(login, token):
    frm, to = utc_window()
    data = graphql(CONTRIB_QUERY, {"login": login, "from": frm, "to": to}, token)
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    total = cal["totalContributions"]
    days = [d for w in weeks for d in w["contributionDays"]]
    return total, weeks, days


def fetch_languages(login, token):
    bytes_by_lang = {}
    repos_by_lang = {}
    colors = {}
    after = None
    while True:
        data = graphql(LANG_QUERY, {"login": login, "after": after}, token)
        repos = data["user"]["repositories"]
        for node in repos["nodes"]:
            seen_in_repo = set()
            for edge in node["languages"]["edges"]:
                name = edge["node"]["name"]
                colors[name] = edge["node"]["color"] or LANG_COLOR_FALLBACK
                bytes_by_lang[name] = bytes_by_lang.get(name, 0) + edge["size"]
                seen_in_repo.add(name)
            for name in seen_in_repo:
                repos_by_lang[name] = repos_by_lang.get(name, 0) + 1
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    return bytes_by_lang, repos_by_lang, colors


def compute_streaks(days):
    current = 0
    for day in reversed(days):
        if day["contributionCount"] > 0:
            current += 1
        else:
            break
    current_range = None
    if current > 0:
        current_range = (days[-current]["date"], days[-1]["date"])

    longest = 0
    longest_range = None
    run_start = None
    run_len = 0
    for day in days:
        if day["contributionCount"] > 0:
            if run_len == 0:
                run_start = day["date"]
            run_len += 1
            if run_len > longest:
                longest = run_len
                longest_range = (run_start, day["date"])
        else:
            run_len = 0
    return current, current_range, longest, longest_range


def fmt_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")


def data_style(extra_selectors_dim=None):
    style = "<style>"
    style += font_face_css("data-regular", "data-regular.woff2")
    style += font_face_css("data-bold", "data-bold.woff2")
    style += "text{font-family:'data-regular',ui-monospace,monospace;}"
    style += ".num{font-family:'data-bold',ui-monospace,monospace;}"
    style += theme_style([".label", ".num"], selectors_dim=[".dim"] + (extra_selectors_dim or []), selectors_rule=[".rule"])
    style += "</style>"
    return style


def render_stats_svg(total, weeks, out_path):
    height = 110
    svg = [svg_open(BODY_WIDTH, height, "contribution activity"), "<defs>", data_style(), "</defs>"]

    svg.append(f'<text class="num" x="0" y="34" font-size="30">{total}</text>')
    svg.append('<text class="dim" x="0" y="52" font-size="11">contributions in the last year</text>')

    week_totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    peak = max(week_totals) or 1
    chart_top, chart_bottom = 68, 104
    chart_h = chart_bottom - chart_top
    n = len(week_totals)
    step = BODY_WIDTH / max(1, n - 1)
    points = []
    for i, wt in enumerate(week_totals):
        x = round(i * step, 2)
        y = round(chart_bottom - (wt / peak) * chart_h, 2)
        points.append(f"{x},{y}")
    svg.append(f'<polyline class="rule" fill="none" stroke-width="1.5" points="{" ".join(points)}"/>')
    fill_pts = f"0,{chart_bottom} " + " ".join(points) + f" {round((n-1)*step,2)},{chart_bottom}"
    svg.append(f'<polygon class="label" points="{fill_pts}" opacity="0.08"/>')

    svg.append("</svg>")
    out_path.write_text("".join(svg), encoding="utf-8")


def render_streak_svg(current, current_range, longest, longest_range, out_path):
    height = 70
    svg = [svg_open(BODY_WIDTH, height, "streaks"), "<defs>", data_style(), "</defs>"]

    half = BODY_WIDTH / 2
    svg.append(f'<text class="num" x="0" y="30" font-size="26">{current}</text>')
    svg.append('<text class="dim" x="0" y="48" font-size="11">current streak (days)</text>')
    if current_range:
        rng = f"{fmt_date(current_range[0])} - {fmt_date(current_range[1])}"
        svg.append(f'<text class="dim" x="0" y="62" font-size="10">{xml_escape(rng)}</text>')

    svg.append(f'<text class="num" x="{half}" y="30" font-size="26">{longest}</text>')
    svg.append(f'<text class="dim" x="{half}" y="48" font-size="11">longest streak (days)</text>')
    if longest_range:
        rng = f"{fmt_date(longest_range[0])} - {fmt_date(longest_range[1])}"
        svg.append(f'<text class="dim" x="{half}" y="62" font-size="10">{xml_escape(rng)}</text>')

    svg.append("</svg>")
    out_path.write_text("".join(svg), encoding="utf-8")


def render_langs_svg(bytes_by_lang, repos_by_lang, colors, out_path, top_n=6):
    ranked = sorted(bytes_by_lang.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    total_bytes = sum(bytes_by_lang.values()) or 1
    row_h = 22
    height = 12 + row_h * len(ranked)

    svg = [svg_open(BODY_WIDTH, height, "top languages"), "<defs>", data_style(), "</defs>"]

    bar_x = 150
    bar_w_max = BODY_WIDTH - bar_x - 110
    for i, (name, size) in enumerate(ranked):
        y = 12 + i * row_h
        pct = size / total_bytes * 100
        bar_w = round(bar_w_max * (size / ranked[0][1]), 2)
        color = colors.get(name, LANG_COLOR_FALLBACK)
        svg.append(f'<text class="label" x="0" y="{y + 13}" font-size="12">{xml_escape(name)}</text>')
        svg.append(f'<rect x="{bar_x}" y="{y + 4}" width="{bar_w}" height="9" fill="{color}" opacity="0.85"/>')
        svg.append(
            f'<text class="dim" x="{BODY_WIDTH}" y="{y + 13}" font-size="10" text-anchor="end">'
            f'{pct:.1f}% - {repos_by_lang.get(name, 0)} repos</text>'
        )

    svg.append("</svg>")
    out_path.write_text("".join(svg), encoding="utf-8")


def render_year_svg(weeks, out_path):
    grid = [[0] * len(weeks) for _ in range(7)]
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            dow = datetime.strptime(day["date"], "%Y-%m-%d").weekday()
            dow = (dow + 1) % 7
            grid[dow][col] = day["contributionCount"]

    max_count = max((c for row in grid for c in row), default=0) or 1
    n = len(RAMP) - 1
    rows = []
    for row in grid:
        chars = []
        for c in row:
            if c == 0:
                chars.append(RAMP[0])
                continue
            level = math.sqrt(c) / math.sqrt(max_count)
            idx = max(1, min(n, round(level * n)))
            chars.append(RAMP[idx])
        rows.append("".join(chars))

    cols = len(weeks)
    grid_w = round(cols * CHAR_W, 2)
    height = round(7 * LINE_H + 6, 2)

    style = "<style>"
    style += font_face_css("ramp", "ramp.woff2")
    style += f"text{{font-family:'ramp',ui-monospace,monospace;font-size:{LINE_H * 0.8:.2f}px;white-space:pre;}}"
    style += theme_style([".glyph"])
    style += "</style>"

    svg = [svg_open(grid_w, height, "the year, one character per day"), "<defs>", style, "</defs>"]
    for i, line in enumerate(rows):
        y = round(i * LINE_H + LINE_H * 0.8, 2)
        svg.append(f'<text class="glyph" x="0" y="{y}" xml:space="preserve">{xml_escape(line)}</text>')
    svg.append("</svg>")
    out_path.write_text("".join(svg), encoding="utf-8")


def main():
    login = os.environ.get("GH_LOGIN")
    token = os.environ.get("GITHUB_TOKEN")
    if not login or not token:
        sys.exit("GH_LOGIN and GITHUB_TOKEN must be set")

    total, weeks, days = fetch_contributions(login, token)
    bytes_by_lang, repos_by_lang, colors = fetch_languages(login, token)
    current, current_range, longest, longest_range = compute_streaks(days)

    render_stats_svg(total, weeks, ROOT / "stats.svg")
    render_streak_svg(current, current_range, longest, longest_range, ROOT / "streak.svg")
    render_langs_svg(bytes_by_lang, repos_by_lang, colors, ROOT / "langs.svg")
    render_year_svg(weeks, ROOT / "year.svg")
    print(f"total={total} current_streak={current} longest_streak={longest} langs={len(bytes_by_lang)}")


if __name__ == "__main__":
    main()
