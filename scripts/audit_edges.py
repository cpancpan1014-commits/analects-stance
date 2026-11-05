#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定向审计：对指向朱熹、仁斋的高置信边各抽样，验证归属是否准确。

论文的核心数字（朱熹 X 次 / 仁斋 Y 次被驳）完全依赖这两个归属，
必须有独立样本支持，否则审稿人可以说这是 LLM 的编造。
"""
import json, os, random, re

import paths as P

BASE = str(P.ROOT)
OUT = str(P.OUT)
NEG = re.compile(r'非也|非矣|豈|误|誤|陋|殊|不知|不曉|不識|不必|不可|不取|何以|安得|焉得|烏足|'
                 r'未|失|謬|妄|不然|非是|臆説|泥矣|固矣|不得其解|必不若|過也|果其說|何所見|理學者流|堅白')
CN = {'heyan': '何晏', 'shu': '邢昺', 'zhuxi': '朱熹', 'kogi': '仁斋', 'cho': '徂徕'}


def main():
    corpus = {r['chapter']: r for r in
              (json.loads(l) for l in open(P.CORPUS, encoding='utf-8'))}
    recs = [json.loads(l) for l in open(P.TERMS_CORE, encoding='utf-8')]
    pool = {'朱熹': [], '仁齋': []}
    for r in recs:
        if r['chapter'] == '01-01':
            continue
        for it in (r['data'].get('items') or []):
            if (it.get('stance') == 'reject' and it.get('in_text') and it.get('source')
                    and NEG.search(it.get('evidence') or '') and it['source'] in pool):
                pool[it['source']].append((r['chapter'], r['annotator'], it))

    rng = random.Random(424242)
    plan = {'朱熹': 12, '仁齋': 8}
    lines = ['# 论争边定向审计（20 条）', '',
             '目的：验证「朱熹被驳 N 次」「仁斋被驳 M 次」两个核心数字的归属是否属实。', '']
    idx = []
    k = 0
    for tgt, n in plan.items():
        pick = rng.sample(pool[tgt], n)
        for ch, L, it in pick:
            k += 1
            note = re.sub(r'\s', '', corpus[ch][L] or '')
            ev = it.get('evidence') or ''
            pos = note.find(ev[:12]) if ev else -1
            if pos < 0:
                ctx, off = note[:700], '（未定位，显示注文前 700 字）'
            else:
                s, e = max(0, pos - 400), min(len(note), pos + len(ev) + 400)
                ctx = ('…' if s else '') + note[s:e] + ('…' if e < len(note) else '')
                off = f'（注文 {len(note)} 字，显示 {s}–{e}）'
            idx.append({'no': k, 'target': tgt, 'ch': ch, 'L': L, 'term': it.get('term'),
                        'gloss': it.get('gloss'), 'evidence': ev})
            lines += [f'## {k}. 指向【{tgt}】 · {ch} · 注者{CN[L]}', '',
                      f'**term** `{it.get("term")}`　**gloss** {it.get("gloss")}', '',
                      f'**evidence**：{ev}', '', f'**注文上下文**{off}', '', '> ' + ctx, '']
    (P.GOLD / 'audit_edges_20.md').write_text('\n'.join(lines), encoding='utf-8')
    json.dump(idx, open(P.GOLD / 'audit_20.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('候选池:', {k: len(v) for k, v in pool.items()}, ' 抽出 20 条')


if __name__ == '__main__':
    main()
