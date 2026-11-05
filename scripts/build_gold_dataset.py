#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble data/gold/gold_40.jsonl -- the human labels with their context.

`gold_40.csv` is what the annotator filled in; it holds no text. A reader who
wants to re-judge an item needs three things the CSV does not carry: the
canonical text, the commentary around the gloss, and which of the two stances
came from the model and which from the annotator. This script joins them.

    python3 scripts/build_gold_dataset.py
"""
import csv
import json
import re

import paths as P

# Three items sit in the gold standard but not in the cross-family subset: their
# He Yan note is shorter than 40 characters (9, 12 and 31), and the blind
# judging pool skips layers that short -- there is no context to judge in.
BLIND_EXCLUDED = {7: "He Yan note is 9 characters", 20: "He Yan note is 12 characters",
                  36: "He Yan note is 31 characters"}
WINDOW = 200          # characters of commentary either side of the gloss


def main():
    labels = list(csv.DictReader(open(P.GOLD_CSV, encoding="utf-8-sig")))
    items = {x["no"]: x for x in json.loads((P.GOLD / "sample_40.json").read_text(encoding="utf-8"))}
    corpus = {r["chapter"]: r for r in
              (json.loads(l) for l in open(P.CORPUS, encoding="utf-8"))}

    out = []
    for row in labels:
        no = int(row["no"])
        it = items[no]
        ch, layer = row["ch"], row["layer"]
        note = re.sub(r"[\s　]", "", corpus[ch].get(layer) or "")
        ev = it.get("evidence") or ""
        pos = note.find(ev[:12]) if ev else -1
        if pos < 0:
            pos = note.find(it["term"])
        if pos < 0:
            ctx = note[:2 * WINDOW] + ("…" if len(note) > 2 * WINDOW else "")
        else:
            s, e = max(0, pos - WINDOW), min(len(note), pos + len(it["gloss"]) + WINDOW)
            ctx = ("…" if s else "") + note[s:e] + ("…" if e < len(note) else "")

        out.append({
            "no": no,
            "chapter": ch,
            "pian": corpus[ch].get("pian"),
            "layer": layer,
            "stratum": row["bucket"],
            "term": it["term"],
            "gloss": it["gloss"],
            "type": it["type"],
            "model_stance": row["model_stance"],
            "model_source": it.get("source"),
            "evidence": ev,
            "gold_stance": row["gold_stance"],
            "stance_correct": bool(int(row["stance_ok"])),
            "term_in_text": bool(int(row["term_ok"])),
            "source_class": row["source_class"],
            "source_note": row["source_note"],
            "verdict_note": row["verdict_note"],
            "jing": corpus[ch].get("jing"),
            "context": ctx,
            "in_blind_subset": no not in BLIND_EXCLUDED,
            "blind_exclusion": BLIND_EXCLUDED.get(no),
        })

    out.sort(key=lambda x: x["no"])
    dest = P.GOLD / "gold_40.jsonl"
    with open(dest, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(out)
    ok = sum(1 for r in out if r["stance_correct"])
    print(f"{n} items, {ok} stances correct ({ok / n * 100:.1f}%), "
          f"{sum(1 for r in out if r['in_blind_subset'])} in the blind subset")
    print(f"wrote {dest.relative_to(P.ROOT)}")


if __name__ == "__main__":
    main()
