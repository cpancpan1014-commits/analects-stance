#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由人工金标准计算 LLM 标注质量：stance 三分类的 P/R/F1、Cohen's κ、term/归属分析。

注意：样本为分层抽样（reject 过采样），κ 与准确率不等于自然分布下的表现，
须在论文中声明。另跑一次按自然比例的估计供参考。
"""
import csv, json, os
from collections import Counter

import paths as P

G = str(P.GOLD)


def main():
    rows = list(csv.DictReader(open(os.path.join(G, 'gold_40.csv'), encoding='utf-8-sig')))
    n = len(rows)
    print(f'金标准 n = {n}')
    print()

    # ---- 1. stance 混淆矩阵 ----
    labels = ['assert', 'adopt', 'reject']
    print('【表 A】stance 混淆矩阵（行=金标准，列=模型）')
    print('           ' + ''.join(f'{l:>9s}' for l in labels) + f'{"合计":>7s}')
    cm = {}
    for g in labels:
        line = f'{g:>10s} '
        tot = 0
        for m in labels:
            v = sum(1 for r in rows if r['gold_stance'] == g and r['model_stance'] == m)
            cm[(g, m)] = v
            tot += v
            line += f'{v:>9d}'
        print(line + f'{tot:>7d}')
    print()

    acc = sum(cm[(l, l)] for l in labels) / n
    # Pe = sum over labels of (gold marginal x predicted marginal). Both margins
    # must be the marginal *of that label*: an earlier version summed the row of
    # the loop's last label for every term, which pinned Pe at .50 and reported
    # kappa = .90 instead of .917.
    pe = sum((sum(cm[(l, m)] for m in labels) / n) *
             (sum(cm[(g, l)] for g in labels) / n) for l in labels)
    kappa = (acc - pe) / (1 - pe)
    print(f'总体一致率 Po = {acc:.4f}   Pe = {pe:.4f}   Cohen κ = {kappa:.4f}')
    print()

    # ---- 2. 逐类 P/R/F1 ----
    print('【表 B】逐类精确率/召回率/F1')
    print(f'{"类别":<8s}{"支持数":>7s}{"精确率":>9s}{"召回率":>9s}{"F1":>8s}')
    f1s = []
    for l in labels:
        tp = cm[(l, l)]
        pred = sum(cm[(g, l)] for g in labels)
        sup = sum(cm[(l, m)] for m in labels)
        p = tp / pred if pred else 0
        r = tp / sup if sup else 0
        f = 2 * p * r / (p + r) if p + r else 0
        f1s.append(f)
        print(f'{l:<8s}{sup:>7d}{p:>9.3f}{r:>9.3f}{f:>8.3f}')
    print(f'{"宏平均":<8s}{n:>7d}{"":>9s}{"":>9s}{sum(f1s)/len(f1s):>8.3f}')
    print()

    # ---- 3. 分层看 reject 精度（论文主结论所在）----
    print('【表 C】分层:高置信论争边（R-high）的可靠性')
    for b in ['R-high', 'R-low', 'assert', 'adopt']:
        sub = [r for r in rows if r['bucket'] == b]
        if not sub:
            continue
        ok = sum(int(r['stance_ok']) for r in sub)
        named = sum(1 for r in sub if r['source_class'] == 'named')
        print(f'  {b:<8s} n={len(sub):2d}  stance 正确 {ok:2d} ({ok/len(sub)*100:5.1f}%)  '
              f'具名归属 {named:2d} ({named/len(sub)*100:5.1f}%)')
    print()

    # ---- 4. term 与归属 ----
    term_ok = sum(int(r['term_ok']) for r in rows)
    print(f'【表 D】term 原文校验：{term_ok}/{n} = {term_ok/n*100:.1f}%')
    sc = Counter(r['source_class'] for r in rows)
    print('  归属分类:', dict(sc))
    claimed = [r for r in rows if r['source_class'] != 'none']
    named_ok = sum(1 for r in claimed if r['source_class'] == 'named')
    print(f'  提出归属者 {len(claimed)} 条，其中可映射到具名注家 {named_ok} 条 '
          f'({named_ok/len(claimed)*100:.1f}%)')
    print()

    # ---- 5. 按注家层 ----
    print('【表 E】按注家层')
    for L, cn in [('heyan', '何晏'), ('shu', '邢昺'), ('zhuxi', '朱熹'), ('kogi', '仁斋'), ('cho', '徂徕')]:
        sub = [r for r in rows if r['layer'] == L]
        if not sub:
            continue
        ok = sum(int(r['stance_ok']) for r in sub)
        print(f'  {cn:<4s} n={len(sub):2d}  stance 正确 {ok:2d} ({ok/len(sub)*100:5.1f}%)')

    # ---- 6. 自然分布下的估计 ----
    print()
    print('【表 F】按自然比例重加权（候选池 assert 5322 / adopt 2057 / R-high 457 / R-low 223）')
    pool = {'assert': 5322, 'adopt': 2057, 'R-high': 457, 'R-low': 223}
    tot = sum(pool.values())
    est = {l: 0.0 for l in labels}
    for b, w in pool.items():
        sub = [r for r in rows if r['bucket'] == b]
        if not sub:
            continue
        for l in labels:
            est[l] += w / tot * sum(1 for r in sub if r['gold_stance'] == l) / len(sub)
    for l in labels:
        print(f'  估计总体占比 {l:<8s}{est[l]*100:6.2f}%')
    print(f'  → 全体条目中 reject 约占 {est["reject"]*100:.1f}%，'
          f'与原始统计 741/8382={741/8382*100:.1f}% 对照')

    json.dump({'n': n, 'kappa': kappa, 'accuracy': acc, 'cm': {f'{g}|{m}': v for (g, m), v in cm.items()},
               'f1': dict(zip(labels, f1s)), 'term_ok': term_ok},
              open(os.path.join(G, 'metrics.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
