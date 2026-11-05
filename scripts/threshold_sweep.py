#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚类阈值 tau 的敏感性分析。

论文 III-E 用字符级相似度把同章同字的各家训释聚成「说法」，
阈值为 0.66。本脚本在 0.50–0.90 上重跑聚类，回答两个问题：
  1. 分歧率是否只在某个狭窄阈值区间成立（即结论对参数是否稳健）；
  2. 单一阈值能否同时适用于 doctrine 与 realia（§VII 的失效模式）。

七层配置，与论文主结果一致：
  EXTRA_SRC=out/terms_liu.jsonl,out/terms_huowen.jsonl EXTRA_LAYERS=liu,huowen
"""
import json
import os
from collections import defaultdict

import alg1
import build_network as bn
import paths as P

THRS = [0.50, 0.55, 0.60, 0.63, 0.66, 0.70, 0.75, 0.80, 0.85, 0.90]


def main():
    items, disp, _ = bn.load_items(extra=(), layers=P.CORE_LAYERS)

    node = defaultdict(list)
    for i in items:
        if i['stance'] in ('assert', 'adopt'):
            node[(i['chapter'], i['tn'])].append(i)

    # 只保留「两家以上对同一字给出训释」的节点，与主结果口径一致
    comp = {k: v for k, v in node.items() if len({x['annotator'] for x in v}) >= 2}

    out = []
    for thr in THRS:
        dis, ncl, multi = 0, 0, 0
        for v in comp.values():
            cl = alg1.link_cluster([x['gloss'] for x in v], thr)
            ncl += len(cl)
            if len(cl) >= 2:
                dis += 1
                if len(cl) >= 3:
                    multi += 1
        out.append({
            'tau': thr, 'comparable': len(comp), 'disputed': dis,
            'rate': round(dis / len(comp) * 100, 1),
            'mean_readings': round(ncl / len(comp), 2),
            'three_or_more': multi,
        })

    print(f'可比节点 {len(comp)} 个')
    print(f'{"tau":>6}{"disputed":>10}{"rate%":>8}{"mean":>7}{">=3种":>8}')
    for r in out:
        print(f'{r["tau"]:>6.2f}{r["disputed"]:>10d}{r["rate"]:>8.1f}'
              f'{r["mean_readings"]:>7.2f}{r["three_or_more"]:>8d}')

    (P.OUT / 'threshold_sweep.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('\n写出 out/threshold_sweep.json')


if __name__ == '__main__':
    main()
