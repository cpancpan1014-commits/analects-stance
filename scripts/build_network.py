#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the dispute graph and report every number the paper quotes.

Algorithm 1 lives in alg1.py; this file drives it over the seven layers and
prints the tables. Splitting them keeps the algorithm readable and keeps the
reporting out of the method.

    python3 scripts/build_network.py                        # five core layers
    python3 scripts/build_network.py --all-seven            # + Zhengyi, Questions
    python3 scripts/build_network.py --all-seven --out network7.json

Output
    out/<name>.json with items, edges, per-layer stances and disputed nodes.
    Every table in the paper is generated from that file; no number is typed
    by hand.
"""
import argparse
import json
from collections import Counter, defaultdict

import alg1
import paths as P

# Report labels. The gate, the normalisation and the clustering come from alg1.
CN = P.CN_SHORT
GENERIC = alg1.GENERIC


def load_items(extra=(), layers=None):
    """Run steps 2-3 over cached calls; return (items, display terms, stats).

    Threshold sensitivity reuses this function so the sweep cannot drift from
    the main result.
    """
    corpus = [json.loads(l) for l in open(P.CORPUS, encoding="utf-8")]
    calls = alg1.load_cached(("v3",)) if not extra else _load_all(extra)
    items, stats = alg1.filter_items(calls, corpus, mu=alg1.MU)
    for it in items:                       # historical name used by the reports
        it["annotator"] = it["layer"]

    disp = {}
    for i in items:
        disp.setdefault((i["chapter"], i["tn"]), Counter())[i["term"]] += 1
    disp = {k: v.most_common(1)[0][0] for k, v in disp.items()}
    if layers:
        items = [i for i in items if i["layer"] in layers]
    return items, disp, stats


def _load_all(extra):
    calls = alg1.load_cached(("v3",))
    for path in extra:
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            if d.get("ok"):
                calls.append(d)
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-seven", action="store_true",
                    help="add Liu Baonan's Zhengyi and Zhu Xi's Questions")
    ap.add_argument("--extra-src", default="", help="comma-separated terms_*.jsonl")
    ap.add_argument("--out", default="network.json")
    ap.add_argument("--tau", type=float, default=alg1.TAU)
    a = ap.parse_args()

    extra = [x for x in a.extra_src.split(",") if x.strip()]
    if a.all_seven:
        extra = extra or [str(P.TERMS_LIU), str(P.TERMS_HUOWEN)]
        layers = ["heyan", "shu", "zhuxi", "kogi", "cho", "liu", "huowen"]
    else:
        layers = list(P.CORE_LAYERS)

    items, disp, stats = load_items(extra, layers)
    print(f"chapters {len({i['chapter'] for i in items})}  items kept {len(items)}")
    print(f"  dropped: term longer than {alg1.MU} {stats.get('term_too_long', 0)}"
          f" | not in canonical text after folding {stats.get('term_not_in_text', 0)}"
          f" | phonetic only {stats.get('phonetic', 0)}"
          f" | suppressed Jinsai layer {stats.get('suppressed', 0)}")

    # ---------- edges ----------
    rejections = [i for i in items if i["stance"] == "reject"]
    edges, held, no_target = alg1.gate(rejections)
    tgt = Counter(i["source"] for i in edges)
    edge = Counter((i["layer"], i["source"]) for i in edges)
    print()
    print("=" * 64)
    print(f"1. dispute edges: high-confidence {len(edges)} / held {len(held)} / no target {len(no_target)}")
    print("   high-confidence = a non-null target and an explicit negative marker")
    print("=" * 64)
    print("most criticized:")
    for k, v in tgt.most_common(10):
        print(f"  {k:<8s}{v:4d}")
    print("heaviest edges:")
    for (critic, src), v in edge.most_common(10):
        print(f"  {CN.get(critic, critic)} -> {src}   {v}")

    # ---------- divergence ----------
    node = defaultdict(list)
    for i in items:
        if i["stance"] in ("assert", "adopt"):
            node[(i["chapter"], i["tn"])].append(i)
    N, D = {}, {}
    for key, group in node.items():
        if len({x["layer"] for x in group}) < 2:
            continue
        groups = alg1.link_cluster(group, a.tau, key=lambda x: x["gloss"])
        D[key] = len(groups)
        if len(groups) >= 2:
            N[key] = groups
    print()
    print("=" * 64)
    print(f"2. divergence: {len(N)} nodes where two or more critics gloss one term")
    print("=" * 64)
    dist = Counter(len(c) for c in N.values())
    print("readings per node: " + "  ".join(f"{k}:{v}" for k, v in sorted(dist.items())))
    print()
    for (ch, tn), cl in sorted(N.items(), key=lambda x: -len(x[1]))[:12]:
        print(f"  [{ch} {disp.get((ch, tn), tn)}] {len(cl)} readings")
        for g in cl[:4]:
            who = "/".join(dict.fromkeys(CN.get(m["layer"], m["layer"]) for m in g))
            print(f"      {who:<10s} {g[0]['gloss'][:34]}")

    # ---------- per-layer composition ----------
    print()
    print("=" * 64)
    print("3. composition by commentator")
    print("=" * 64)
    print(f"{'critic':<8}{'items':>7}{'assert':>8}{'adopt':>7}{'reject':>8}{'reject%':>9}")
    layer_stats = {}
    for L in layers:
        sub = [i for i in items if i["layer"] == L]
        c = Counter(i["stance"] for i in sub)
        r = c.get("reject", 0) / max(len(sub), 1) * 100
        print(f"{CN[L]:<8}{len(sub):7d}{c.get('assert', 0):8d}{c.get('adopt', 0):7d}"
              f"{c.get('reject', 0):8d}{r:7.1f}%")
        layer_stats[L] = {
            "cn": CN[L], "items": len(sub),
            "assert": c.get("assert", 0), "adopt": c.get("adopt", 0),
            "reject": c.get("reject", 0), "reject_rate": round(r, 1),
            "reject_high": sum(1 for i in edges if i["layer"] == L),
        }

    dest = P.OUT / a.out
    dest.write_text(json.dumps({
        "n_items": len(items), "n_reject_high": len(edges),
        "n_reject_low": len(held), "n_reject_nosrc": len(no_target),
        "tau": a.tau,
        "layer_stats": layer_stats,
        "criticized": dict(tgt.most_common()),
        "edges": {f"{critic}->{src}": v for (critic, src), v in edge.most_common()},
        "disputed_nodes": {
            f"{ch}|{disp.get((ch, tn), tn)}": [
                {"gloss": g[0]["gloss"],
                 "who": sorted({CN.get(m["layer"], m["layer"]) for m in g})}
                for g in cl]
            for (ch, tn), cl in N.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote out/{a.out}")


if __name__ == "__main__":
    main()
