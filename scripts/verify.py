#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recompute every number the paper reports and say whether it holds.

No API key, no network: steps 1 of Algorithm 1 are served from out/terms_*.jsonl.
This is the script a reviewer should run first.

    python3 scripts/verify.py

Each line is one claim, the value this repository computes, the value the paper
prints, and PASS/FAIL. Two claims are known to differ; both are explained in
docs/ERRATA.md and marked KNOWN there.

Exit code 0 if every check passes, 1 otherwise.
"""
import csv
import json
import sys
from collections import Counter, defaultdict

import alg1
import paths as P

TOL = 0.011        # a printed .01 is allowed to round either way
FAILS = []
KNOWN = []


def check(label, got, want, tol=None, note=""):
    if isinstance(want, str):
        ok = got == want
    elif isinstance(want, (int,)) and isinstance(got, int):
        ok = got == want
    else:
        ok = abs(got - want) <= (tol if tol is not None else TOL)
    mark = "PASS" if ok else ("KNOWN" if note.startswith("KNOWN") else "FAIL")
    if mark == "FAIL":
        FAILS.append(label)
    if mark == "KNOWN":
        KNOWN.append(label)
    shown = f"{got:.3f}" if isinstance(got, float) else str(got)
    print(f"  [{mark}] {label:<52} {shown:>10}   paper: {want}")
    return ok


def load_network():
    f = P.NETWORK7
    if not f.exists():
        sys.exit("out/network7.json missing -- run scripts/build_network.py --all-seven first")
    return json.loads(f.read_text(encoding="utf-8"))


def main():
    net = load_network()
    corpus = [json.loads(l) for l in open(P.CORPUS, encoding="utf-8")]

    print("1. Corpus  (Table I; data card)")
    check("chapters in the corpus", len(corpus), 501)
    check("books (pian)", len({r["pian_no"] for r in corpus}), 20)
    check("chapters with all five core layers", sum(
        1 for r in corpus if all((r.get(L) or "").strip() for L in P.CORE_LAYERS)), 339)
    check("Jinsai layers suppressed (edition defect)",
          sum(1 for r in corpus if r.get("kogi_status") == "suppressed"), 6)

    print("\n2. Extraction and the gate  (Algorithm 1; Section III)")
    check("items after filtering", net["n_items"], 12702)
    edges = net["n_reject_high"]
    held, nosrc = net["n_reject_low"], net["n_reject_nosrc"]
    check("high-confidence edges", edges, 867)
    check("rejections held for review", held, 594)
    check("rejections with no target", nosrc, 95)
    check("all rejections before the gate", edges + held + nosrc, 1556)

    print("\n3. Per-commentator composition  (Table I)")
    rate = {L: s["reject_rate"] for L, s in net["layer_stats"].items()}
    for L, want in (("heyan", 0.0), ("shu", 0.7), ("zhuxi", 0.3), ("kogi", 2.1),
                    ("cho", 33.8), ("liu", 9.9), ("huowen", 51.2)):
        check(f"  rejection rate, {L}", rate[L], want, tol=0.05)

    print("\n4. Targets and edges  (Table II; Fig. 1)")
    tgt = net["criticized"]
    check("times Zhu Xi is criticized", tgt["朱熹"], 155)
    check("times Jinsai is criticized", tgt["仁斋"], 61)
    e = net["edges"]
    # Fig. 1 folds spelling variants of one authority (何氏/集解 -> He Yan) and
    # draws six strict single-critic edges; build_edges() is the figure's own
    # data path, so importing it verifies the figure rather than a copy of it.
    import make_fig_dispute as FIG
    agg = FIG.build_edges()
    for critic, target, want in (("Sorai", "Zhu Xi", 152), ("Sorai", "Jinsai", 61),
                                 ("Zhu Xi", "Xie", 56), ("Zhu Xi", "Yang", 34),
                                 ("Zhu Xi", "Fan", 31), ("Sorai", "He Yan", 19)):
        check(f"  edge {critic} -> {target}", int(agg[(critic, target)]), want)
    check("six edges drawn in Fig. 1 sum to",
          int(sum(agg[(c, t)] for c, t, _ in (("Sorai", "Zhu Xi", 0), ("Sorai", "Jinsai", 0),
                                              ("Zhu Xi", "Xie", 0), ("Zhu Xi", "Yang", 0),
                                              ("Zhu Xi", "Fan", 0), ("Sorai", "He Yan", 0)))), 353)

    print("\n5. Divergence  (Section III-E; Table III)")
    check("disputed nodes, seven layers", len(net["disputed_nodes"]), 1856)
    items5, _ = _five_layer_items()
    node = defaultdict(list)
    for i in items5:
        if i["stance"] in ("assert", "adopt"):
            node[(i["chapter"], i["tn"])].append(i)
    comp = {k: v for k, v in node.items() if len({x["layer"] for x in v}) >= 2}
    dis = {k: alg1.link_cluster([x["gloss"] for x in v]) for k, v in comp.items()}
    dis = {k: c for k, c in dis.items() if len(c) >= 2}
    check("comparable nodes, five aligned layers", len(comp), 1776)
    check("disputed nodes, five aligned layers", len(dis), 1383)
    dist = Counter(len(c) for c in dis.values())
    check("  nodes with two readings", dist[2], 695)
    check("  nodes with three readings", dist[3], 365)
    check("  nodes with four readings", dist[4], 203)

    print("\n6. Core concepts  (Table III)")
    import concept_divergence as CD
    core_items = [i for i in items5 if i["stance"] in ("assert", "adopt")]
    tot_c = tot_d = 0
    for c in CD.CORE:
        by = defaultdict(list)
        for i in core_items:
            if i["term"] == c:
                by[i["chapter"]].append(i)
        for group in by.values():
            if len({x["layer"] for x in group}) < 2:
                continue
            tot_c += 1
            if len(alg1.link_cluster([x["gloss"] for x in group])) >= 2:
                tot_d += 1
    # v1.0.0 of the paper printed 111 / 101 / 91.0%. Those came from a population
    # that still held pronunciation-only glosses, which Algorithm 1 step 3 removes
    # (one node: 17-08, where Zhu Xi writes 知，去聲). The revision prints
    # 110 / 100 / 90.9%, so the check now passes; see docs/ERRATA.md.
    check("comparable nodes on the 24 core concepts", tot_c, 110)
    check("disputed nodes on the 24 core concepts", tot_d, 100)
    check("divergence rate on core concepts (%)", round(tot_d / tot_c * 100, 1), 90.9,
          tol=0.05)

    print("\n7. Gold standard  (Section V-D)")
    rows = list(csv.DictReader(open(P.GOLD_CSV, encoding="utf-8-sig")))
    gold = [r["gold_stance"] for r in rows]
    pred = [r["model_stance"] for r in rows]
    acc = sum(1 for a, b in zip(gold, pred) if a == b) / len(rows)
    check("gold items", len(rows), 40)
    check("stance agreement (%)", round(acc * 100, 1), 95.0, tol=0.05)
    check("Cohen kappa, 40 items", round(_kappa(gold, pred), 3), 0.917, tol=0.002)

    print("\n7b. Second coder, an independent model family  (Section V-D)")
    import second_coder as SC
    sc = [r for r in _jsonl(P.OUT / "second_coder_glm.jsonl") if r.get("ok")]
    ds = [r["ds_stance"] for r in sc]
    gl = [r["glm_stance"] for r in sc]
    check("items judged blind by the second model", len(sc), 197)
    check("Cohen kappa, model vs model", round(_kappa(ds, gl), 3), 0.84, tol=0.005)
    lo95, hi95 = SC.boot_ci(ds, gl)
    check("  bootstrap CI lower bound", round(lo95, 2), 0.77, tol=0.011)
    check("  bootstrap CI upper bound", round(hi95, 2), 0.90, tol=0.011)

    print("\n8. Cross-family agreement  (Table IV)")
    fams = json.loads((P.DATA / "families.json").read_text(encoding="utf-8"))["families"]
    gidx = {int(r["no"]): r for r in rows}
    per = {}
    for f in fams:
        if not f["file"]:
            per[f["name"]] = {n: gidx[n][f["field"]] for n in gidx}
            continue
        per[f["name"]] = {d["no"]: d[f["field"]]
                          for d in _jsonl(P.ROOT / f["file"]) if d.get("ok")}
    common = set(gidx)
    for d in per.values():
        common &= set(d)
    common = sorted(common)
    check("items in the shared blind subset", len(common), 37)
    g = [gidx[n]["gold_stance"] for n in common]
    want = {"DeepSeek V4-Flash": 0.906, "GLM-5.3-Flash": 0.690, "Qwen-max": 0.496,
            "Qwen-plus": 0.449, "Gemini-3.5-Flash": 0.605, "GPT-5": 0.571,
            "Claude Opus 5": 0.590}
    for f in fams:
        name = f["name"]
        k = _kappa(g, [per[name][n] for n in common])
        check(f"  kappa, {name}", round(k, 3), want[name], tol=0.002)
    kv = [(_kappa(g, [per[f["name"]][n] for n in common]), f["name"]) for f in fams]
    check("spread across families (min)", round(min(k for k, _ in kv), 2), 0.45, tol=0.01)
    check("spread across families (max)", round(max(k for k, _ in kv), 2), 0.91, tol=0.01)
    cn = [i for i, n in enumerate(common) if gidx[n]["layer"] in ("heyan", "shu", "zhuxi")]
    jp = [i for i, n in enumerate(common) if gidx[n]["layer"] in ("kogi", "cho")]
    check("  Han layers in the subset", len(cn), 20)
    check("  Japanese layers in the subset", len(jp), 17)
    lower = [name for name in per
             if _kappa([g[i] for i in jp], [per[name][common[i]] for i in jp]) <
                _kappa([g[i] for i in cn], [per[name][common[i]] for i in cn])]
    check("families scoring lower on the Japanese layers", len(lower), 1)

    print("\n9. Threshold sweep  (Section III-E)")
    sweep = []
    for tau in (0.50, 0.66, 0.90):
        d = sum(1 for v in comp.values()
                if len(alg1.link_cluster([x["gloss"] for x in v], tau)) >= 2)
        sweep.append((tau, d, round(d / len(comp) * 100, 1)))
    check("disputed share at tau = .50 (%)", sweep[0][2], 71.8, tol=0.05)
    check("disputed nodes at tau = .66", sweep[1][1], 1383)
    check("disputed share at tau = .90 (%)", sweep[2][2], 87.2, tol=0.05)

    print("\n10. Table II decomposition  (named individuals, collectivities, works)")
    import table2_targets as T2
    tgt2 = Counter()
    for k, v in e.items():
        for name, share in T2.fold(k.split("->")[1]):
            tgt2[name] += v * share
    kinds = Counter()
    for n, v in tgt2.items():
        kinds[T2.kind(n)] += v
    check("Table II total", round(sum(tgt2.values())), 867)
    check("share held by named individuals (%)", round(kinds["individual"] / edges * 100, 1), 82.8, tol=0.2)
    check("share held by collectivities (%)", round(kinds["collectivity"] / edges * 100, 1), 12.7, tol=0.2)
    check("share held by works (%)", round(kinds["work"] / edges * 100, 1), 4.3, tol=0.2)
    ranked = [(n, v) for n, v in tgt2.most_common() if T2.kind(n) == "individual"]
    check("edges to the top three individuals", round(sum(v for _, v in ranked[:3]), 1), 277.8, tol=0.2)
    # Table II lists eleven rows by name and folds the rest into one line. The
    # paper's 196 and 369 are that remainder, and 867 - 498 = 369 holds on the
    # rounded row values the table prints. Rounding each row costs ~1.7 edges
    # against the unrounded sum, which is why the fold is checked by arithmetic.
    check("targets beyond the eleven named rows", len(tgt2) - 11, 196)
    check("named individuals beyond the top three (info)", len(ranked) - 3, 137)

    print()
    if KNOWN:
        print(f"{len(KNOWN)} known difference(s) from the printed text: see docs/ERRATA.md")
        for k in KNOWN:
            print(f"  - {k}")
    if FAILS:
        print(f"\n{len(FAILS)} FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("all checks pass")
    return 0


def _jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def _five_layer_items():
    corpus = [json.loads(l) for l in open(P.CORPUS, encoding="utf-8")]
    calls = alg1.load_cached(("v3",))
    return alg1.filter_items(calls, corpus)


def _kappa(a, b):
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe)


if __name__ == "__main__":
    sys.exit(main())
