#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Load the prompt set from data/prompts/ -- one source for code and Appendix A.

The text here is byte-identical to the strings that produced the published
runs: the files were dumped from the running module, not retyped, and
`python3 promptset.py --check-legacy ../scripts` proves it against that module
for every (chapter, layer) pair in the corpus.

Files
    system_v3.txt        the schema, the stance rules, the prohibitions
    fewshot_<layer>.txt  one worked example per genre (4 of 7 layers need one)
    user_template.txt    the per-call message, with {chapter} {text} {annotator}
                         {era} {layer} {reference} {note}
    layers.json          which layer is whose commentary, which few-shot it uses
    judge_system.txt     the blind stance judge used for the cross-family test
"""
import json
import sys
from pathlib import Path

import paths as P

MAX_NOTE_CHARS = 6000     # a handful of Sorai chapters run past this


def _read(name):
    """Read a prompt file, dropping exactly one trailing newline."""
    return (P.PROMPTS / name).read_text(encoding="utf-8").removesuffix("\n")


SYSTEM = _read("system_v3.txt")
USER_TEMPLATE = _read("user_template.txt")
JUDGE_SYSTEM = _read("judge_system.txt")
LAYERS = json.loads((P.PROMPTS / "layers.json").read_text(encoding="utf-8"))

FEWSHOT = {L: _read(m["fewshot"]) for L, m in LAYERS.items() if m.get("fewshot")}
CN = {L: m["cn"] for L, m in LAYERS.items()}
ERA = {L: m["era"] for L, m in LAYERS.items()}


def build_user(chapter, text, layer, note):
    """The user message for one (chapter, layer) call.

    Kept as a function rather than a string because two layers need a worked
    example and the other five must not see one: a compilation and an authored
    commentary cannot be shown the same sample without teaching the wrong
    stance prior.
    """
    note = (note or "").strip()
    if len(note) > MAX_NOTE_CHARS:
        note = note[:MAX_NOTE_CHARS] + "……（以下略）"
    reference = ""
    if layer in FEWSHOT:
        reference = "【体例参照】" + FEWSHOT[layer] + "\n"
    return USER_TEMPLATE.format(
        chapter=chapter, text=(text or "").strip(), annotator=CN[layer],
        era=ERA[layer], layer=layer, reference=reference, note=note)


def _check_legacy(legacy_dir):
    """Prove byte-identity against the module that actually ran the calls."""
    sys.path.insert(0, str(Path(legacy_dir).resolve()))
    import extract_terms as ET                      # noqa: E402
    import extract_liu, extract_huowen              # noqa: F401,E402  (registers layers)

    corpus = [json.loads(l) for l in open(P.CORPUS, encoding="utf-8")]
    bad = 0
    if ET.SYSTEM != SYSTEM:
        print("SYSTEM differs", file=sys.stderr)
        bad += 1
    for layer in ET.FEWSHOT:
        if ET.FEWSHOT[layer] != FEWSHOT[layer]:
            print(f"fewshot {layer} differs", file=sys.stderr)
            bad += 1
    n = 0
    for r in corpus:
        for layer in ET.CN:
            note = {"liu": (r.get("text") or "")}.get(layer) or r.get(layer) or "示例注文"
            ch = r["chapter"] if layer != "huowen" else "hw-01-01"
            a = ET.build_user(ch, r.get("jing"), layer, note)
            b = build_user(ch, r.get("jing"), layer, note)
            n += 1
            if a != b:
                if bad < 3:
                    print(f"user message differs: {r['chapter']} {layer}", file=sys.stderr)
                bad += 1
    print(f"compared {n} user messages, {bad} differences")
    return bad == 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--check-legacy":
        sys.exit(0 if _check_legacy(sys.argv[2]) else 1)
    print(f"system prompt   {len(SYSTEM)} chars")
    print(f"user template   {len(USER_TEMPLATE)} chars")
    print(f"few-shot blocks {', '.join(sorted(FEWSHOT))}")
    print(f"layers          {', '.join(sorted(LAYERS))}")
