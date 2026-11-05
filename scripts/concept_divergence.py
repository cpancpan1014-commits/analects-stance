#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Table III: how often a core educational concept carries more than one reading.

Two kinds of divergence are kept apart. Realia (觚 holds two *sheng* or three,
what a *di* sacrifice is) is antiquarian: it dates a commentator but says little
about how the text teaches. Definitions (字義) and doctrines (義理) are the
divergence an educational reading has to live with.

The population is the five aligned layers -- the two control commentaries are
printed in forms whose chapter alignment is not common to all seven, so they
are excluded here and enter Tables I, II and V only. That is also why the
number of comparable nodes (1,776) is smaller than in the seven-layer graph.

    python3 scripts/concept_divergence.py
"""
import json
from collections import Counter, defaultdict

import alg1
import build_network as bn
import paths as P

CORE = ['學', '教', '仁', '禮', '道', '君子', '知', '思', '習', '德', '義', '信',
        '忠', '孝', '政', '性', '命', '心', '文', '詩', '行', '言', '過', '恥']


def load():
    """Items from the five core layers, assertions and adoptions only.

    Rejection is excluded on purpose: a rejection states someone else's gloss,
    so counting it twice would inflate the number of readings.
    """
    items, _, _ = bn.load_items(extra=(), layers=P.CORE_LAYERS)
    return [i for i in items if i["stance"] in ("assert", "adopt")]


def main():
    items = load()
    print(f"items {len(items)}   type distribution {dict(Counter(i['type'] for i in items))}")
    print()
    print(f"{'concept':<9}{'chapters':>9}{'comparable':>11}{'disputed':>9}{'rate':>8}"
          f"{'readings':>9}{'doctrinal':>10}")
    print("-" * 65)
    rows_out = []
    for c in CORE:
        nodes = defaultdict(list)
        for i in items:
            if i["term"] == c:
                nodes[i["chapter"]].append(i)
        comparable = disputed = readings = doctrinal = 0
        for ch, group in nodes.items():
            if len({x["layer"] for x in group}) < 2:
                continue
            comparable += 1
            clusters = alg1.link_cluster([x["gloss"] for x in group])
            if len(clusters) >= 2:
                disputed += 1
                readings += len(clusters)
                if all(x["type"] in ("義理", "字義") for x in group):
                    doctrinal += 1
        rows_out.append((c, len(nodes), comparable, disputed, readings, doctrinal))
        print(f"{c:<9}{len(nodes):9d}{comparable:11d}{disputed:9d}"
              f"{disputed / max(comparable, 1) * 100:7.1f}%{readings / max(disputed, 1):9.2f}"
              f"{doctrinal:10d}")
    tot_d = sum(r[3] for r in rows_out)
    tot_c = sum(r[2] for r in rows_out)
    print("-" * 65)
    print(f"{'total':<9}{'':9}{tot_c:11d}{tot_d:9d}{tot_d / max(tot_c, 1) * 100:7.1f}%")

    (P.OUT / "concept_divergence.json").write_text(json.dumps(
        [{"term": r[0], "n_chapters": r[1], "n_comparable": r[2], "n_disputed": r[3],
          "mean_readings": r[4] / max(r[3], 1), "n_doctrinal_disputed": r[5]}
         for r in rows_out], ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nwrote out/concept_divergence.json")


if __name__ == "__main__":
    main()
