#!/usr/bin/env python3
"""
render_city.py
Reads assets/data/city.json and draws:
  assets/city.svg    an isometric skyline, one building per day
  assets/status.svg  a slim animated terminal strip (blinking cursor,
                      pulsing LIVE dot) for the HUD look already used
                      in github-header.png

Deterministic: every building's windows come from a random generator
seeded on that day's date string, so the skyline is pixel-identical on
every re-render unless the underlying data changes.
"""
import hashlib
import json
import math
import os
import random
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)
DATA_PATH = os.path.join(HERE, "..", "..", "assets", "data", "city.json")
CITY_OUT = os.path.join(HERE, "..", "..", "assets", "city.svg")
STATUS_OUT = os.path.join(HERE, "..", "..", "assets", "status.svg")

BG = "#0d1117"
GRID = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"
ACCENT = "#c9563a"
ACCENT_WALL_R = "#8a3d29"
ACCENT_WALL_L = "#5c2a1c"
ACCENT_DIM = "#3a2016"
GREEN = "#3fb950"
WINDOW_LIT = "#f0a875"

FONT = "ui-monospace, 'SFMono-Regular', Consolas, monospace"

DX, DY = 13, 6.5
TILE_W, TILE_H = 26, 13
MAX_H = 74
MIN_H = 5


def load():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def flat_days(weeks):
    out = []
    for w in weeks:
        out.extend(w)
    return out


def compute_stats(days):
    total = sum(d["count"] for d in days)
    busiest = max((d["count"] for d in days), default=0)
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        else:
            break
    return {"total": total, "busiest": busiest, "longest": longest, "current": current}


def iso(col, row):
    x = (col - row) * DX
    y = (col + row) * DY
    return x, y


def pt(x, y):
    return f"{x:.1f},{y:.1f}"


def building(col, row, count, max_count, date_str):
    cx, cy = iso(col, row)
    top = (cx, cy - TILE_H / 2)
    right = (cx + TILE_W / 2, cy)
    bottom = (cx, cy + TILE_H / 2)
    left = (cx - TILE_W / 2, cy)

    if count <= 0:
        poly = f'<polygon points="{pt(*top)} {pt(*right)} {pt(*bottom)} {pt(*left)}" ' \
               f'fill="{GRID}" stroke="{BORDER}" stroke-width="0.6" opacity="0.55"/>'
        return poly, (min(top[0], left[0]), top[1], max(right[0], bottom[0]), bottom[1])

    h = MIN_H + (MAX_H - MIN_H) * math.sqrt(count / max_count)

    top_u = (top[0], top[1] - h)
    right_u = (right[0], right[1] - h)
    bottom_u = (bottom[0], bottom[1] - h)
    left_u = (left[0], left[1] - h)

    rng = random.Random(f"{date_str}:{count}")
    rows_of_windows = max(1, int(h // 11))
    win_svg = []
    for wr in range(rows_of_windows):
        wy = bottom_u[1] - 4 - wr * 10
        if wy < top_u[1] + 3:
            break
        if wy > bottom[1] - 2:
            continue
        if rng.random() < 0.6:
            t = 0.45
            wx = right[0] - (right[0] - bottom[0]) * t
            lit = WINDOW_LIT if rng.random() < 0.7 else ACCENT_DIM
            win_svg.append(f'<rect x="{wx-1.6:.1f}" y="{wy-1.6:.1f}" width="3.2" height="3.2" '
                            f'fill="{lit}" opacity="0.9"/>')
        if rng.random() < 0.6:
            t = 0.45
            wx = left[0] + (bottom[0] - left[0]) * t
            lit = WINDOW_LIT if rng.random() < 0.7 else ACCENT_DIM
            win_svg.append(f'<rect x="{wx-1.6:.1f}" y="{wy-1.6:.1f}" width="3.2" height="3.2" '
                            f'fill="{lit}" opacity="0.9"/>')

    roof = f'<polygon points="{pt(*top_u)} {pt(*right_u)} {pt(*bottom_u)} {pt(*left_u)}" ' \
           f'fill="{ACCENT}" stroke="{BG}" stroke-width="0.6"/>'
    wall_r = f'<polygon points="{pt(*right)} {pt(*bottom)} {pt(*bottom_u)} {pt(*right_u)}" ' \
              f'fill="{ACCENT_WALL_R}" stroke="{BG}" stroke-width="0.6"/>'
    wall_l = f'<polygon points="{pt(*left)} {pt(*bottom)} {pt(*bottom_u)} {pt(*left_u)}" ' \
              f'fill="{ACCENT_WALL_L}" stroke="{BG}" stroke-width="0.6"/>'

    svg = wall_l + wall_r + roof + "".join(win_svg)
    bbox = (min(top_u[0], left[0]), top_u[1], max(right[0], bottom[0]), bottom[1])
    return svg, bbox


def render_city(data):
    weeks = data.get("weeks") or []
    days = flat_days(weeks)
    stats = compute_stats(days) if days else {"total": 0, "busiest": 0, "longest": 0, "current": 0}
    max_count = max(1, stats["busiest"])

    cols = len(weeks)
    rows = 7
    pieces = []
    minx = miny = 1e9
    maxx = maxy = -1e9

    order = sorted(
        ((c, r) for c in range(cols) for r in range(rows)),
        key=lambda cr: (cr[0] + cr[1]),
    )
    for col, row in order:
        day = weeks[col][row]
        svg, (bx0, by0, bx1, by1) = building(col, row, day["count"], max_count, day["date"])
        pieces.append(svg)
        minx, miny = min(minx, bx0), min(miny, by0)
        maxx, maxy = max(maxx, bx1), max(maxy, by1)

    pad = 24
    vb_x, vb_y = minx - pad, miny - pad - 34
    vb_w, vb_h = (maxx - minx) + pad * 2, (maxy - miny) + pad * 2 + 34

    title_x = vb_x + 18
    title_y = vb_y + 26
    legend_y = vb_y + vb_h - 14

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_x:.0f} {vb_y:.0f} {vb_w:.0f} {vb_h:.0f}" width="100%">
  <defs>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="{GRID}" stroke-width="1"/>
    </pattern>
  </defs>
  <rect x="{vb_x:.0f}" y="{vb_y:.0f}" width="{vb_w:.0f}" height="{vb_h:.0f}" fill="{BG}"/>
  <rect x="{vb_x:.0f}" y="{vb_y:.0f}" width="{vb_w:.0f}" height="{vb_h:.0f}" fill="url(#grid)"/>
  <rect x="{vb_x+2:.0f}" y="{vb_y+2:.0f}" width="{vb_w-4:.0f}" height="{vb_h-4:.0f}"
        fill="none" stroke="{BORDER}" stroke-width="1.5"/>
  <text x="{title_x:.0f}" y="{title_y:.0f}" fill="{TEXT_DIM}" font-family="{FONT}" font-size="12"
        letter-spacing="2">CONTRIBUTION CITY &#183; LAST 52 WEEKS</text>
  <g>
    {''.join(pieces)}
  </g>
  <text x="{title_x:.0f}" y="{legend_y:.0f}" fill="{TEXT}" font-family="{FONT}" font-size="12">
    <tspan fill="{ACCENT}">{stats['total']}</tspan><tspan fill="{TEXT_DIM}"> commits/yr &#183; </tspan><tspan fill="{ACCENT}">{stats['longest']}</tspan><tspan fill="{TEXT_DIM}">d longest streak &#183; </tspan><tspan fill="{GREEN}">{stats['current']}</tspan><tspan fill="{TEXT_DIM}">d current streak</tspan>
  </text>
</svg>'''
    with open(CITY_OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {CITY_OUT}")
    return stats


def render_status(data, stats):
    gen = data.get("generated_at", datetime.now(timezone.utc).isoformat())
    try:
        synced = datetime.fromisoformat(gen.replace("Z", "+00:00")).strftime("%b %d, %H:%M UTC")
    except ValueError:
        synced = gen

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 40" width="100%">
  <style>
    @keyframes blink {{ 0%,45% {{ opacity: 1 }} 50%,95% {{ opacity: 0 }} 100% {{ opacity: 1 }} }}
    @keyframes pulse {{ 0%,100% {{ opacity: 1 }} 50% {{ opacity: 0.35 }} }}
    .cursor {{ animation: blink 1.1s step-end infinite; }}
    .dot {{ animation: pulse 2s ease-in-out infinite; }}
  </style>
  <rect x="0" y="0" width="1200" height="40" fill="{BG}"/>
  <rect x="0.5" y="0.5" width="1199" height="39" fill="none" stroke="{BORDER}" stroke-width="1"/>
  <circle class="dot" cx="18" cy="20" r="4" fill="{GREEN}"/>
  <text x="32" y="25" fill="{GREEN}" font-family="{FONT}" font-size="13" letter-spacing="1">LIVE</text>
  <text x="90" y="25" fill="{TEXT}" font-family="{FONT}" font-size="13">$ whoami &#8594; mursal_furqan_kumbhar</text>
  <rect class="cursor" x="372" y="11" width="8" height="15" fill="{ACCENT}"/>
  <text x="560" y="25" fill="{TEXT_DIM}" font-family="{FONT}" font-size="12">streak {stats['current']}d</text>
  <text x="700" y="25" fill="{TEXT_DIM}" font-family="{FONT}" font-size="12">synced {synced}</text>
</svg>'''
    with open(STATUS_OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {STATUS_OUT}")


def main():
    data = load()
    stats = render_city(data)
    render_status(data, stats)


if __name__ == "__main__":
    main()