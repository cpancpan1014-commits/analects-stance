#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Figure 1 — backbone of the dispute graph, IEEE single column (3.35 in).

Figure contract
---------------
Claim      : criticism in the Analects commentary corpus runs backwards in time
             and is never answered; and the sharpest Japanese critic attacks
             Zhu Xi almost as hard as he attacks his own compatriot Jinsai,
             so shared opposition to Neo-Confucianism produced no shared
             position.
Evidence   : one schematic panel. x = era; edge width = single critic ->
             target count; node size = times the figure is criticized
             (Table II target tally, across all critics).
Archetype  : schematic-led composite (single hero panel).
Backend    : Python / matplotlib.

Data contract
-------------
Edges are strict single-critic -> target tallies read from out/network7.json
(the `edges` field), so every number here can be recomputed. Combined
references (范呂謝尹氏) are not split in this figure; that is why the six
edges shown are exactly the six heaviest named ones. Generic collectives
(宋儒/後儒/舊註/或曰) and works never enter the figure.

Outputs: draft/figures/fig1_dispute.{svg,pdf,tiff,png}
"""
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

# MANDATORY: keep text as text in every vector export
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

import paths as P

OUT = P.OUT
FIG = P.FIG

INK = "#4D4D4D"
INK_SOFT = "#8C8C8C"
SINO, SINO_FILL = "#0F4D92", "#DCE7F3"
KOG, KOG_FILL = "#A63E38", "#F3DDDA"

SRC = {"heyan": "He Yan", "shu": "Xing Bing", "zhuxi": "Zhu Xi", "kogi": "Jinsai",
       "cho": "Sorai", "liu": "Liu Baonan", "huowen": "Zhu Xi"}

TGT = {
    "朱熹": "Zhu Xi", "朱子": "Zhu Xi", "朱註": "Zhu Xi", "朱注": "Zhu Xi", "朱氏": "Zhu Xi",
    "仁斋": "Jinsai", "仁齋": "Jinsai", "伊藤仁斋": "Jinsai",
    "徂徕": "Sorai", "徂徠": "Sorai", "荻生徂徠": "Sorai",
    "謝氏": "Xie", "杨氏": "Yang", "楊氏": "Yang", "范氏": "Fan",
    "程子": "Cheng Yi", "程氏": "Cheng Yi", "程": "Cheng Yi",
    "何晏": "He Yan", "何氏": "He Yan", "何註": "He Yan", "集解": "He Yan",
    "鄭玄": "Zheng Xuan", "郑玄": "Zheng Xuan", "鄭": "Zheng Xuan",
}

POS = {
    "He Yan": (0.50, 0.62),
    "Xie":    (1.78, 0.34),
    "Yang":   (1.78, -0.14),
    "Fan":    (1.78, -0.62),
    "Zhu Xi": (2.48, -0.14),
    "Jinsai": (3.00, -0.58),
    "Sorai":  (3.00, 0.62),
}

TRAD = {"He Yan": "cn", "Xie": "cn", "Yang": "cn", "Fan": "cn",
        "Zhu Xi": "cn", "Sorai": "jp", "Jinsai": "jp"}
COL = {"cn": SINO, "jp": KOG}
FILL = {"cn": SINO_FILL, "jp": KOG_FILL}

# label text and anchor side
LABEL = {
    "He Yan": ("He Yan",       "above"),
    "Xie":    ("Xie Liangzuo", "left"),
    "Yang":   ("Yang Shi",     "left"),
    "Fan":    ("Fan Zuyu",     "left"),
    "Zhu Xi": ("Zhu Xi",       "right"),
    "Jinsai": ("Jinsai",       "below"),
    "Sorai":  ("Sorai",        "above"),
}

# times criticized (Table II target tally); Sorai is never rebutted,
# which is itself part of the claim
DEG = {"Zhu Xi": 157, "Jinsai": 61, "Xie": 60, "Yang": 39, "Fan": 35,
       "He Yan": 31, "Sorai": 0}

EDGES = [("Sorai", "Zhu Xi"), ("Sorai", "Jinsai"), ("Zhu Xi", "Xie"),
         ("Zhu Xi", "Yang"), ("Zhu Xi", "Fan"), ("Sorai", "He Yan")]

RAD = {("Sorai", "Zhu Xi"): -0.16, ("Sorai", "Jinsai"): 0.0,
       ("Zhu Xi", "Xie"): 0.18, ("Zhu Xi", "Yang"): 0.0,
       ("Zhu Xi", "Fan"): 0.16, ("Sorai", "He Yan"): 0.0}

# (t along the arc, perpendicular offset in data units)
COUNT = {("Sorai", "Zhu Xi"): (0.46, -0.105), ("Sorai", "Jinsai"): (0.32, 0.105),
         ("Zhu Xi", "Xie"): (0.60, 0.080), ("Zhu Xi", "Yang"): (0.55, -0.078),
         ("Zhu Xi", "Fan"): (0.60, 0.080), ("Sorai", "He Yan"): (0.40, -0.085)}

XLIM = (0.0, 3.35)
YLIM = (-1.17, 1.10)
FS = 5.5


def build_edges():
    d = json.load(open(OUT / "network7.json", encoding="utf-8"))
    agg = defaultdict(float)
    for key, w in d["edges"].items():
        s, t = key.split("->")
        src = SRC.get(s, s)
        name = TGT.get(t)
        if name and name != src:
            agg[(src, name)] += w
    return agg


def node_radius(name):
    return 0.058 + 0.072 * (DEG.get(name, 0) / 157.0) ** 0.5


def bezier(p0, p1, rad, t):
    """Quadratic control point following matplotlib's arc3 convention."""
    (x0, y0), (x1, y1) = p0, p1
    cx = (x0 + x1) / 2 + (y1 - y0) * rad
    cy = (y0 + y1) / 2 - (x1 - x0) * rad
    return ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1,
            (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1)


def bezier_normal(p0, p1, rad, t):
    x0, y0 = bezier(p0, p1, rad, max(t - 0.004, 0.0))
    x1, y1 = bezier(p0, p1, rad, min(t + 0.004, 1.0))
    dx, dy = x1 - x0, y1 - y0
    n = (dx * dx + dy * dy) ** 0.5 or 1.0
    return -dy / n, dx / n


def main():
    agg = build_edges()
    edges = [(s, t, agg[(s, t)]) for s, t in EDGES]
    edges.sort(key=lambda e: -e[2])
    wmax = edges[0][2]

    fig, ax = plt.subplots(figsize=(3.35, 2.24))
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    for xc, lab, span in ((0.50, "Han–Wei", "c. 200–250"),
                          (2.02, "Song", "c. 1050–1200"),
                          (3.00, "Edo", "c. 1650–1720")):
        ax.text(xc, 1.045, lab, fontsize=5.4, color=INK_SOFT, style="italic",
                ha="center", va="center", zorder=2)
        ax.text(xc, 0.972, span, fontsize=4.9, color=INK_SOFT,
                ha="center", va="center", zorder=2)

    for s, t, w in edges:
        p0, p1 = POS[s], POS[t]
        rad = RAD[(s, t)]
        lw = 0.55 + 2.30 * (w / wmax) ** 0.75
        ax.add_patch(FancyArrowPatch(
            p0, p1, connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>,head_length=2.4,head_width=1.4",
            linewidth=lw, color=INK, alpha=0.92, zorder=3,
            shrinkA=node_radius(s) * 72 + 1.0,
            shrinkB=node_radius(t) * 72 + 1.6,
            mutation_scale=1.0, capstyle="round", joinstyle="round"))

    for name, (x, y) in POS.items():
        ax.add_patch(Circle((x, y), node_radius(name), facecolor=FILL[TRAD[name]],
                            edgecolor=COL[TRAD[name]], linewidth=0.9, zorder=5))

    for name, (x, y) in POS.items():
        txt, where = LABEL[name]
        r = node_radius(name)
        gap = 0.055
        if where == "above":
            ax.text(x, y + r + gap, txt, fontsize=FS, ha="center", va="bottom",
                    color=COL[TRAD[name]], zorder=6)
        elif where == "below":
            ax.text(x, y - r - gap, txt, fontsize=FS, ha="center", va="top",
                    color=COL[TRAD[name]], zorder=6)
        elif where == "left":
            ax.text(x - r - gap, y, txt, fontsize=FS, ha="right", va="center",
                    color=COL[TRAD[name]], zorder=6)
        else:
            ax.text(x + r + gap, y, txt, fontsize=FS, ha="left", va="center",
                    color=COL[TRAD[name]], zorder=6)

    for s, t, w in edges:
        p0, p1 = POS[s], POS[t]
        rad = RAD[(s, t)]
        tt, off = COUNT[(s, t)]
        mx, my = bezier(p0, p1, rad, tt)
        nx, ny = bezier_normal(p0, p1, rad, tt)
        ax.text(mx + nx * off, my + ny * off, f"{int(round(w))}", fontsize=5.8,
                ha="center", va="center", color="#1A1A1A", zorder=7,
                bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.95))

    ky = -0.925
    ax.add_patch(Circle((0.09, ky), 0.045, facecolor=FILL["cn"], edgecolor=COL["cn"],
                        linewidth=0.8, zorder=5, clip_on=False))
    ax.text(0.19, ky, "Chinese exegesis", fontsize=5.3, va="center",
            color=INK, zorder=6, clip_on=False)
    ax.add_patch(Circle((1.68, ky), 0.045, facecolor=FILL["jp"], edgecolor=COL["jp"],
                        linewidth=0.8, zorder=5, clip_on=False))
    ax.text(1.78, ky, "Japanese kogaku", fontsize=5.3, va="center",
            color=INK, zorder=6, clip_on=False)

    # 图例文字印在图内（审稿意见 P2-1）：色块、箭头、边权、节点面积全在框内说明
    ax.text(0.09, -1.055,
            "Arrow: critic \u2192 authority \u00b7 width: count \u00b7 "
            "area: times criticized \u00b7 six heaviest of 867",
            fontsize=4.9, va="center", color=INK_SOFT, clip_on=False)

    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf"):
        fig.savefig(FIG / f"fig1_dispute.{ext}")
    for ext in ("png", "tiff"):
        fig.savefig(FIG / f"fig1_dispute.{ext}", dpi=600)
    plt.close(fig)

    print("edges in figure (strict single critic -> target):")
    for s, t, w in edges:
        print(f"  {s:<9} -> {t:<9} {int(w)}")
    print(f"\nsum {int(sum(w for _, _, w in edges))} / 867")


if __name__ == "__main__":
    main()
