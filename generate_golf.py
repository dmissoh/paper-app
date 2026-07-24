#!/usr/bin/env python3
"""Generate a printable Paper-Golf notepad PDF (3x5 inch pages).

Inspired by the roll-and-write genre: each hole is a dot-grid course with
fairway, rough, sand, water, trees and slopes. Play with a d6 and a pen.

Usage:
    python generate_golf.py [--courses 3] [--holes 18] [--seed 42] [--out golf_notepad.pdf]
    python generate_golf.py --selftest
"""

import argparse
import random
import sys

from reportlab.lib.colors import Color, black, white
from reportlab.pdfgen import canvas as pdfcanvas

# Page geometry (3 x 5 inch, portrait, coil binding at top)
PAGE_W, PAGE_H = 216, 360
SP = 15                    # grid spacing in points
COLS, ROWS = 13, 19        # dot grid
GX0 = (PAGE_W - (COLS - 1) * SP) / 2
GY0 = 40                   # bottom row y (leaves room for caption)

GRAY_DOT = Color(0.62, 0.62, 0.62)
GRAY_FAIRWAY = Color(0.86, 0.86, 0.86)
GRAY_FAIRWAY_DOT = Color(0.45, 0.45, 0.45)
GRAY_SAND = Color(0.55, 0.55, 0.55)
GRAY_WATER = Color(0.55, 0.55, 0.55)
GRAY_TREE = Color(0.22, 0.22, 0.22)

ORTHO = [(1, 0), (-1, 0), (0, 1), (0, -1)]
DIRS8 = ORTHO + [(1, 1), (1, -1), (-1, 1), (-1, -1)]

COURSE_NAME_A = ["Whispering", "Sunny", "Foggy", "Rolling", "Hidden", "Windy",
                 "Old", "Sandy", "Misty", "Crooked", "Quiet", "Wild"]
COURSE_NAME_B = ["Pines", "Hollow", "Creek", "Meadow", "Dunes", "Ridge",
                 "Willow", "Heron", "Fox", "Badger", "Marmot", "Thistle"]
COURSE_NAME_C = ["Links", "Golf Club", "Country Club", "Greens", "Fields"]


# ---------------------------------------------------------------- generation

def grow_blob(rng, occ, start, size):
    """Grow an orthogonally-connected blob of free cells from start."""
    if occ.get(start) is not None:
        return set()
    cells = {start}
    for _ in range(size * 30):
        if len(cells) >= size:
            break
        cx, cy = rng.choice(list(cells))
        dx, dy = rng.choice(ORTHO)
        nc = (cx + dx, cy + dy)
        if 0 <= nc[0] < COLS and 0 <= nc[1] < ROWS and occ.get(nc) is None and nc not in cells:
            cells.add(nc)
    return cells


def mark(occ, cells, kind):
    for c in cells:
        occ[c] = kind


def try_generate_hole(rng):
    """Return dict with occ, tee, hole, fairway blob list, tree glyphs, slopes."""
    occ = {}
    tee = (rng.randint(3, COLS - 4), rng.randint(0, 1))
    hole = (rng.randint(2, COLS - 3), rng.randint(ROWS - 3, ROWS - 1))

    # Fairway blobs along the tee->hole line (first contains tee, last the hole)
    fairways = []
    ts = [0.0] + sorted(rng.uniform(0.3, 0.7) for _ in range(rng.randint(1, 2))) + [1.0]
    for t in ts:
        jx = rng.randint(-2, 2) if 0 < t < 1 else 0
        cx = round(tee[0] + (hole[0] - tee[0]) * t) + jx
        cy = round(tee[1] + (hole[1] - tee[1]) * t)
        seed = (min(max(cx, 0), COLS - 1), min(max(cy, 0), ROWS - 1))
        if t == 0:
            seed = tee
        if t == 1:
            seed = hole
        blob = grow_blob(rng, occ, seed, rng.randint(6, 13))
        if blob:
            mark(occ, blob, "fairway")
            fairways.append(blob)
    if occ.get(tee) != "fairway" or occ.get(hole) != "fairway":
        return None

    # Keep the cells around the tee free of hazards
    for dx, dy in DIRS8:
        c = (tee[0] + dx, tee[1] + dy)
        if occ.get(c) is None:
            occ[c] = "reserved"

    # Sand next to fairway
    edges = [(fx + dx, fy + dy) for blob in fairways for fx, fy in blob
             for dx, dy in ORTHO]
    edges = [c for c in set(edges) if 0 <= c[0] < COLS and 0 <= c[1] < ROWS
             and occ.get(c) is None]
    for _ in range(rng.randint(1, 2)):
        if not edges:
            break
        blob = grow_blob(rng, occ, rng.choice(edges), rng.randint(3, 7))
        mark(occ, blob, "sand")

    # Water
    for _ in range(rng.randint(0, 2)):
        seed = (rng.randint(0, COLS - 1), rng.randint(2, ROWS - 3))
        blob = grow_blob(rng, occ, seed, rng.randint(4, 10))
        mark(occ, blob, "water")

    # Tree clusters (glyph style per cluster: pine or round)
    trees = {}
    for _ in range(rng.randint(2, 4)):
        seed = (rng.randint(0, COLS - 1), rng.randint(1, ROWS - 2))
        blob = grow_blob(rng, occ, seed, rng.randint(3, 8))
        mark(occ, blob, "tree")
        style = rng.choice(["pine", "round"])
        for c in blob:
            trees[c] = style

    # Slopes on plain rough
    slopes = {}
    free = [(x, y) for x in range(COLS) for y in range(ROWS) if occ.get((x, y)) is None]
    for c in rng.sample(free, min(len(free), rng.randint(0, 3))):
        slopes[c] = rng.choice(ORTHO)

    return {"occ": occ, "tee": tee, "hole": hole, "trees": trees, "slopes": slopes}


def reachable(hole_data):
    """BFS from tee to hole through non-water, non-tree cells (8 directions)."""
    occ, tee, hole = hole_data["occ"], hole_data["tee"], hole_data["hole"]
    seen, queue = {tee}, [tee]
    while queue:
        cur = queue.pop()
        if cur == hole:
            return True
        for dx, dy in DIRS8:
            nc = (cur[0] + dx, cur[1] + dy)
            if (0 <= nc[0] < COLS and 0 <= nc[1] < ROWS and nc not in seen
                    and occ.get(nc) not in ("water", "tree")):
                seen.add(nc)
                queue.append(nc)
    return False


def generate_hole(rng):
    for _ in range(100):
        hole = try_generate_hole(rng)
        if hole and reachable(hole):
            return hole
    raise RuntimeError("could not generate a solvable hole")


def course_name(rng):
    return "%s %s %s" % (rng.choice(COURSE_NAME_A), rng.choice(COURSE_NAME_B),
                         rng.choice(COURSE_NAME_C))


# ------------------------------------------------------------------ drawing

def pt(cell):
    return GX0 + cell[0] * SP, GY0 + cell[1] * SP


def draw_blob(c, cells, color):
    """Rounded blob: a circle per cell plus rects bridging orthogonal neighbours."""
    r = 0.46 * SP
    c.setFillColor(color)
    for cell in cells:
        x, y = pt(cell)
        c.circle(x, y, r, stroke=0, fill=1)
        for dx, dy in ((1, 0), (0, 1)):
            if (cell[0] + dx, cell[1] + dy) in cells:
                if dx:
                    c.rect(x, y - r, SP, 2 * r, stroke=0, fill=1)
                else:
                    c.rect(x - r, y, 2 * r, SP, stroke=0, fill=1)


def draw_water(c, cells):
    """Diagonal hatch clipped to the blob shape."""
    r = 0.46 * SP
    c.saveState()
    p = c.beginPath()
    for cell in cells:
        x, y = pt(cell)
        p.circle(x, y, r)
        for dx, dy in ((1, 0), (0, 1)):
            if (cell[0] + dx, cell[1] + dy) in cells:
                if dx:
                    p.rect(x, y - r, SP, 2 * r)
                else:
                    p.rect(x - r, y, 2 * r, SP)
    c.clipPath(p, stroke=0, fill=0)
    xs = [pt(cell)[0] for cell in cells]
    ys = [pt(cell)[1] for cell in cells]
    x0, x1 = min(xs) - SP, max(xs) + SP
    y0, y1 = min(ys) - SP, max(ys) + SP
    c.setStrokeColor(GRAY_WATER)
    c.setLineWidth(1.1)
    d = x0 - (y1 - y0)
    while d < x1:
        c.line(d, y0, d + (y1 - y0), y1)
        d += 3.2
    c.restoreState()


def draw_pine(c, x, y):
    c.setFillColor(GRAY_TREE)
    p = c.beginPath()
    p.moveTo(x - 3.6, y - 3.2)
    p.lineTo(x + 3.6, y - 3.2)
    p.lineTo(x, y + 1.2)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(x - 2.9, y - 0.6)
    p.lineTo(x + 2.9, y - 0.6)
    p.lineTo(x, y + 4.4)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.rect(x - 0.8, y - 4.8, 1.6, 1.8, stroke=0, fill=1)


def draw_round_tree(c, x, y):
    c.setFillColor(GRAY_TREE)
    c.circle(x, y + 1.2, 3.1, stroke=0, fill=1)
    c.rect(x - 0.8, y - 4.6, 1.6, 3.4, stroke=0, fill=1)


def draw_slope(c, x, y, d):
    dx, dy = d
    c.setStrokeColor(GRAY_TREE)
    c.setFillColor(GRAY_TREE)
    c.setLineWidth(1.2)
    c.line(x - dx * 3.5, y - dy * 3.5, x + dx * 2.0, y + dy * 2.0)
    p = c.beginPath()
    p.moveTo(x + dx * 4.5, y + dy * 4.5)
    p.lineTo(x + dx * 1.2 - dy * 2.2, y + dy * 1.2 - dx * 2.2)
    p.lineTo(x + dx * 1.2 + dy * 2.2, y + dy * 1.2 + dx * 2.2)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def draw_hole_page(c, hole_data, hole_no):
    occ, trees, slopes = hole_data["occ"], hole_data["trees"], hole_data["slopes"]
    by_kind = {}
    for cell, kind in occ.items():
        by_kind.setdefault(kind, set()).add(cell)

    for blob_kind, color in (("fairway", GRAY_FAIRWAY), ("sand", GRAY_SAND)):
        cells = by_kind.get(blob_kind, set())
        if cells:
            draw_blob(c, cells, color)
    if by_kind.get("water"):
        draw_water(c, by_kind["water"])

    # dot grid on top of the blobs
    for x in range(COLS):
        for y in range(ROWS):
            kind = occ.get((x, y))
            if kind in ("water", "tree"):
                continue
            px, py = pt((x, y))
            if kind == "sand":
                c.setFillColor(white)
            elif kind == "fairway":
                c.setFillColor(GRAY_FAIRWAY_DOT)
            else:
                c.setFillColor(GRAY_DOT)
            c.circle(px, py, 1.15, stroke=0, fill=1)

    for cell, style in trees.items():
        x, y = pt(cell)
        (draw_pine if style == "pine" else draw_round_tree)(c, x, y)
    for cell, d in slopes.items():
        x, y = pt(cell)
        draw_slope(c, x, y, d)

    # tee (white ring) and hole (solid dot)
    tx, ty = pt(hole_data["tee"])
    c.setFillColor(white)
    c.setStrokeColor(black)
    c.setLineWidth(1.7)
    c.circle(tx, ty, 3.9, stroke=1, fill=1)
    hx, hy = pt(hole_data["hole"])
    c.setFillColor(GRAY_TREE)
    c.circle(hx, hy, 4.3, stroke=0, fill=1)

    c.setFillColor(black)
    c.setFont("Courier", 9)
    c.drawString(GX0 - 4, 18, "Hole %-2d  Strokes:   /6  Total:" % hole_no)
    c.showPage()


def draw_cover(c, n_courses, n_holes, seed):
    c.setFillColor(Color(0.55, 0.72, 0.15))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(Color(0.12, 0.3, 0.08))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, 218, "PAPER")
    c.drawCentredString(PAGE_W / 2, 182, "GOLF")
    c.setFont("Helvetica", 9)
    c.drawCentredString(PAGE_W / 2, 150, "%d courses x %d holes" % (n_courses, n_holes))
    c.drawCentredString(PAGE_W / 2, 138, "a pen + a d6 is all you need")
    # little flag
    c.setLineWidth(2)
    c.setStrokeColor(Color(0.12, 0.3, 0.08))
    c.line(PAGE_W / 2, 60, PAGE_W / 2, 110)
    p = c.beginPath()
    p.moveTo(PAGE_W / 2, 110)
    p.lineTo(PAGE_W / 2 + 22, 101)
    p.lineTo(PAGE_W / 2, 92)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setFont("Helvetica", 6)
    c.drawCentredString(PAGE_W / 2, 14, "seed %s" % seed)
    c.showPage()


RULES = [
    ("H", "HOW TO PLAY"),
    ("T", "Goal: get the ball from the tee (white ring) into the hole"),
    ("T", "(black dot) in as few strokes as possible. Par is 6."),
    ("S", ""),
    ("H", "DICE GOLF (with a d6)"),
    ("T", "Roll the die: that is how many spaces the ball travels in a"),
    ("T", "straight line. Pick any of the 8 directions. +1 to the roll"),
    ("T", "when hitting from fairway, -1 from sand. You may always"),
    ("T", "putt (move 1 space) instead of using your roll."),
    ("T", "Draw the line, then a small circle at the new ball spot."),
    ("T", "You may re-roll once on each tee shot. You also have 6"),
    ("T", "mulligans per course: mark one off to re-roll any shot."),
    ("S", ""),
    ("H", "SPEED GOLF (no die)"),
    ("T", "Choose a club each shot: DRIVER moves 6 (fairway only,"),
    ("T", "may fly over trees), IRON moves 3 (2 from sand, never over"),
    ("T", "trees), PUTTER moves 1 (always allowed)."),
    ("S", ""),
    ("H", "LANDING RULES"),
    ("T", "The ball may fly over water but never land in it. Trees"),
    ("T", "block the ball: you can only fly over trees when hitting"),
    ("T", "from the fairway, and you may never land on a tree."),
    ("T", "If your line crosses the hole you may stop 1 space past it"),
    ("T", "and count it as holed. Slope arrows push the ball 1 space"),
    ("T", "(keep rolling on chained arrows, ignore arrows into water)."),
    ("S", ""),
    ("H", "TERRAIN"),
]


def draw_rules(c):
    y = PAGE_H - 34
    for kind, text in RULES:
        if kind == "H":
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(black)
            c.drawString(16, y, text)
            y -= 11
        elif kind == "S":
            y -= 4
        else:
            c.setFont("Helvetica", 6.6)
            c.setFillColor(Color(0.15, 0.15, 0.15))
            c.drawString(16, y, text)
            y -= 8.6

    # terrain legend with the real glyphs
    ly = y - 6
    x = 24
    r = 0.46 * SP

    def label(t):
        c.setFont("Helvetica", 6.6)
        c.setFillColor(Color(0.15, 0.15, 0.15))
        c.drawString(x + 14, ly - 2.3, t)

    c.setFillColor(GRAY_FAIRWAY)
    c.circle(x, ly, r, stroke=0, fill=1)
    c.setFillColor(GRAY_FAIRWAY_DOT)
    c.circle(x, ly, 1.15, stroke=0, fill=1)
    label("fairway  (+1 to roll, driver ok)")
    ly -= 15
    c.setFillColor(GRAY_SAND)
    c.circle(x, ly, r, stroke=0, fill=1)
    c.setFillColor(white)
    c.circle(x, ly, 1.15, stroke=0, fill=1)
    label("sand  (-1 to roll)")
    ly -= 15
    c.saveState()
    p = c.beginPath()
    p.circle(x, ly, r)
    c.clipPath(p, stroke=0, fill=0)
    c.setStrokeColor(GRAY_WATER)
    c.setLineWidth(1.1)
    d = x - 2 * r
    while d < x + 2 * r:
        c.line(d, ly - r, d + 2 * r, ly + r)
        d += 3.2
    c.restoreState()
    label("water  (no landing)")
    ly -= 15
    draw_pine(c, x - 4, ly)
    draw_round_tree(c, x + 5, ly)
    label("trees  (block shots)")
    ly -= 15
    draw_slope(c, x, ly, (1, 0))
    label("slope  (ball rolls 1)")
    ly -= 15
    c.setFillColor(white)
    c.setStrokeColor(black)
    c.setLineWidth(1.7)
    c.circle(x - 4, ly, 3.9, stroke=1, fill=1)
    c.setFillColor(GRAY_TREE)
    c.circle(x + 7, ly, 4.3, stroke=0, fill=1)
    label("tee  /  hole")
    c.showPage()


def draw_course_title(c, name, course_no, n_holes):
    c.setFillColor(black)
    c.setFont("Courier-Bold", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 52, "COURSE %d" % course_no)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 72, name)
    c.setFont("Courier", 8)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 88, "%d holes . par 6 each" % n_holes)

    c.setFont("Courier", 8)
    c.drawString(24, PAGE_H - 116, "Mulligans:")
    for i in range(6):
        c.rect(88 + i * 16, PAGE_H - 123, 9, 9, stroke=1, fill=0)

    c.setFont("Courier", 8)
    top = PAGE_H - 150
    half = (n_holes + 1) // 2
    for i in range(n_holes):
        col = i // half
        row = i % half
        x = 24 + col * 100
        y = top - row * 14
        c.drawString(x, y, "H%-2d ______" % (i + 1))
    c.line(24, top - half * 14 - 4, 192, top - half * 14 - 4)
    c.drawString(24, top - half * 14 - 16, "TOTAL ______")
    c.showPage()


# --------------------------------------------------------------------- main

def build_pdf(out, n_courses, n_holes, seed):
    rng = random.Random(seed)
    c = pdfcanvas.Canvas(out, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("Paper Golf Notepad")
    draw_cover(c, n_courses, n_holes, seed)
    draw_rules(c)
    for course_no in range(1, n_courses + 1):
        draw_course_title(c, course_name(rng), course_no, n_holes)
        for hole_no in range(1, n_holes + 1):
            draw_hole_page(c, generate_hole(rng), hole_no)
    c.save()
    return 2 + n_courses * (1 + n_holes)


def selftest():
    for seed in range(30):
        rng = random.Random(seed)
        h = generate_hole(rng)
        assert h["tee"] != h["hole"]
        assert reachable(h)
        assert h["occ"][h["hole"]] == "fairway"
    print("selftest ok: 30 seeds, all holes solvable")


def main():
    ap = argparse.ArgumentParser(description="Generate a Paper-Golf notepad PDF")
    ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--holes", type=int, default=18)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default="golf_notepad.pdf")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    seed = args.seed if args.seed is not None else random.randrange(10 ** 6)
    pages = build_pdf(args.out, args.courses, args.holes, seed)
    print("wrote %s (%d pages, seed %d)" % (args.out, pages, seed))


if __name__ == "__main__":
    main()
