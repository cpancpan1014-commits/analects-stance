#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分层抽样 40 条，生成供人工判读的审阅稿。

判读单元 = 一条抽取结果 (chapter, annotator, term, stance, source)。
抽样分层：
  R-high  reject 且 evidence 含显式否定标志（高置信论争边，论文主结论基础）14 条
  R-low   reject 但 evidence 无否定标志（降级待核）            8 条
  assert  本人立说                                              12 条
  adopt   采纳他人之说                                           6 条
排除 01-01（少样本示例章），按注家层尽量均衡。
"""
import json, os, random, re

import paths as P

BASE = str(P.ROOT)
OUT = str(P.OUT)

NEG = re.compile(r'非也|非矣|豈|误|誤|陋|殊|不知|不曉|不識|不必|不可|不取|何以|安得|焉得|烏足|'
                 r'未|失|謬|妄|不然|非是|臆説|泥矣|固矣|不得其解|必不若|過也|果其說|何所見|理學者流|堅白')

CN = {'heyan': '何晏', 'shu': '邢昺', 'zhuxi': '朱熹', 'kogi': '仁斋', 'cho': '徂徕'}
LAYERS = ['heyan', 'shu', 'zhuxi', 'kogi', 'cho']
FEWSHOT_CH = {'01-01'}


def load():
    corpus = {r['chapter']: r for r in
              (json.loads(l) for l in open(P.CORPUS, encoding='utf-8'))}
    recs = [json.loads(l) for l in open(P.TERMS_CORE, encoding='utf-8')]
    return corpus, recs


def bucket(it):
    st = it.get('stance') or ''
    ev = it.get('evidence') or ''
    if st == 'reject':
        return 'R-high' if NEG.search(ev) else 'R-low'
    if st in ('assert', 'adopt'):
        return st
    return None


def main():
    corpus, recs = load()
    # 每条候选带上上下文
    cand = {b: [] for b in ('R-high', 'R-low', 'assert', 'adopt')}
    for r in recs:
        ch, L = r['chapter'], r['annotator']
        if ch in FEWSHOT_CH:
            continue
        jing = re.sub(r'\s', '', corpus[ch]['jing'] or '')
        note = re.sub(r'\s', '', corpus[ch][L] or '')
        if not jing or not note:
            continue
        for it in (r['data'].get('items') or []):
            if not it.get('in_text'):
                continue
            term = (it.get('term') or '').strip()
            if not (1 <= len(term) <= 4):
                continue
            b = bucket(it)
            if not b:
                continue
            cand[b].append({'ch': ch, 'L': L, 'jing': jing, 'note': note, 'it': it})

    plan = {'R-high': 14, 'R-low': 8, 'assert': 12, 'adopt': 6}
    rng = random.Random(20261101)
    picked = []
    for b, n in plan.items():
        pool = cand[b]
        # 按层均衡：轮转取层
        by_layer = {L: [x for x in pool if x['L'] == L] for L in LAYERS}
        for L in by_layer:
            rng.shuffle(by_layer[L])
        got, i = [], 0
        while len(got) < n and any(by_layer.values()):
            L = LAYERS[i % 5]
            if by_layer[L]:
                got.append(by_layer[L].pop())
            i += 1
        for g in got:
            g['bucket'] = b
        picked.extend(got)
    rng.shuffle(picked)

    lines = ['# 金标准判读稿（40 条）', '']
    lines.append('判读对象：术语定位(term) / 立场(stance) / 归属(source) / 义项(gloss) 四项是否正确。')
    lines.append('')
    idx = []
    for k, x in enumerate(picked, 1):
        it = x['it']
        ev = it.get('evidence') or ''
        # 定位 evidence 在注文中的位置，取上下文
        pos = x['note'].find(ev[:12]) if ev else -1
        if pos < 0:
            ctx = x['note'][:600]
            off = '（evidence 未能定位，显示注文前 600 字）'
        else:
            s, e = max(0, pos - 320), min(len(x['note']), pos + len(ev) + 320)
            ctx = ('…' if s > 0 else '') + x['note'][s:e] + ('…' if e < len(x['note']) else '')
            off = f'（注文全长 {len(x["note"])} 字，显示第 {s}–{e} 字）'
        idx.append({'no': k, 'ch': x['ch'], 'L': x['L'], 'bucket': x['bucket'],
                    'term': it.get('term'), 'gloss': it.get('gloss'), 'type': it.get('type'),
                    'stance': it.get('stance'), 'source': it.get('source'), 'evidence': ev})
        lines += [
            f'## {k}. {x["ch"]} · {CN[x["L"]]} · [{x["bucket"]}]', '',
            f'**原文**：{x["jing"][:160]}', '',
            f'**模型输出**：term=`{it.get("term")}` | type=`{it.get("type")}` | '
            f'stance=`{it.get("stance")}` | source=`{it.get("source")}`', '',
            f'**gloss**：{it.get("gloss")}', '',
            f'**evidence**：{ev}', '',
            f'**注文上下文**{off}', '', '> ' + ctx, '',
        ]
    (P.GOLD / 'review_40.md').write_text('\n'.join(lines), encoding='utf-8')
    (P.GOLD / 'sample_40.json').write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding='utf-8')

    print('抽样完成：')
    from collections import Counter
    print('  分层:', dict(Counter(x['bucket'] for x in picked)))
    print('  按层:', dict(Counter(CN[x['L']] for x in picked)))
    print('  涉及章数:', len({x['ch'] for x in picked}))
    print('  候选池:', {k: len(v) for k, v in cand.items()})


if __name__ == '__main__':
    main()
