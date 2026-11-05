#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二标注员：用第二个模型族独立判读 200 条抽取结果，算模型间一致性。

目的（对应论文 VII 第一条）：
    论文现有 κ = .90 只是「DeepSeek vs 单一专家」，不是标注者间信度。
    本脚本用另一家模型（默认智谱 GLM-5.3-Flash）在**不看 DeepSeek 结论**的
    前提下重新判读同一批条目，得到：
      (1) DeepSeek vs GLM 的 stance 一致性（换模型族的稳定性）
      (2) GLM vs 人工金标准 40 条（专家一致性是否可复现）
      (3) 不一致条目清单，供人工裁定

用法：
    export GLM_API_KEY=xxxx.yyyy
    python3 scripts/second_coder.py all        # 抽样 → 判读 → 报告
    python3 scripts/second_coder.py report     # 只重算报告
"""
import argparse
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import paths as P

ROOT = P.ROOT
OUT = P.OUT

LAYERS = ["heyan", "shu", "zhuxi", "kogi", "cho", "liu", "huowen"]
CN = {"heyan": "何晏集解", "shu": "邢昺疏", "zhuxi": "朱熹集注", "kogi": "伊藤仁斋古义",
      "cho": "荻生徂徕论语征", "liu": "刘宝楠论语正义", "huowen": "朱熹论语或问"}

# 串层章：kogi 字段实为徂徕文本（与 build_network.py 同源），仁斋层作废
CONTAM = {"04-16", "07-17", "08-15", "12-21", "12-22", "15-14"}

NEG = re.compile(r"非也|非矣|豈|误|誤|陋|殊|不知|不曉|不識|不必|不可|不取|何以|安得|焉得|烏足|"
                 r"未|失|謬|妄|不然|非是|臆説|泥矣|固矣|不得其解|必不若|過也|果其說|何所見|理學者流|堅白")

# 靶标异写归一（与 build_network.py 的 ALIAS 同源，仅用于 source 比对）
ALIAS = {"朱子": "朱熹", "朱註": "朱熹", "朱注": "朱熹", "集注": "朱熹", "集註": "朱熹",
         "仁齋": "仁斋", "伊藤仁斋": "仁斋", "徂徠": "徂徕", "荻生徂徠": "徂徕",
         "程": "程子", "程氏": "程子", "何氏": "何晏", "邢疏": "邢昺", "鄭": "鄭玄", "郑玄": "鄭玄"}

SYS = """你是中国古典注疏的独立标注员。你的任务是判断一条释义在注文中的**立场**，不要复述注文，不要解释方法。
立场三分类：
- assert：注者本人立说（正面给出自己的解释）
- adopt：采纳或引述前人之说（如「馬曰」「包曰」「引《說文》」「舊說以為」）
- reject：驳斥前人之说（含「非也」「豈」「誤」「烏足」等否定判断，或指出某说不可从）
若为 adopt 或 reject，须写出被引/被驳的对象（人名、书名或「宋儒」这类泛称；注文中未明指则填 null）。
只输出 JSON：{"stance": "assert|adopt|reject", "source": "对象或 null", "why": "20字以内依据"}"""


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def norm(s):
    return re.sub(r"[\s　，。、；：（）()「」『』]", "", s or "")


# ---------------- 抽样 ----------------

def build_pool():
    """返回候选池：每条含章、层、术语、释义、上下文。"""
    cc = {r["chapter"]: r for r in load_jsonl(P.CORPUS)}
    liu = {r["chapter"]: r for r in load_jsonl(P.CORPUS_LIU)}
    hw = {r["chapter"]: r for r in load_jsonl(P.CORPUS_HUOWEN)}

    pool = []
    srcs = [(P.TERMS_CORE, cc, "layer"), (P.TERMS_LIU, liu, "text"),
            (P.TERMS_HUOWEN, hw, "text")]
    suppressed = {r["chapter"] for r in cc.values() if r.get("kogi_status") == "suppressed"}
    for path, book, mode in srcs:
        for r in load_jsonl(path):
            ch, L = r.get("chapter"), r.get("annotator")
            if ch == "01-01":       # 少样本提示章，排除
                continue
            if L == "kogi" and (ch in suppressed or ch in CONTAM):
                continue
            row = book.get(ch)
            if not row:
                continue
            note = row.get(L) if mode == "layer" else row.get("text")
            note = norm(note)
            if len(note) < 40:
                continue
            jing = norm(row.get("jing") or "") if mode == "layer" else ""
            for it in (r.get("data", {}).get("items") or []):
                term = (it.get("term") or "").strip()
                gloss = (it.get("gloss") or "").strip()
                if not (1 <= len(term) <= 4) or not gloss:
                    continue
                st = it.get("stance") or "assert"
                b = ("R-high" if NEG.search(it.get("evidence") or "") else "R-low") \
                    if st == "reject" else st
                pos = note.find(term)
                if pos < 0:
                    ctx = note[:700]
                else:
                    s, e = max(0, pos - 350), min(len(note), pos + len(term) + 350)
                    ctx = ("…" if s else "") + note[s:e] + ("…" if e < len(note) else "")
                pool.append({"ch": ch, "L": L, "bucket": b, "term": term, "gloss": gloss,
                             "type": it.get("type"), "ds_stance": st, "ds_source": it.get("source"),
                             "ds_evidence": it.get("evidence"), "jing": jing[:200], "ctx": ctx})
    return pool


def sample(n=200, seed=20261101):
    """按立场类固定配额抽样（而非按真实比例）。

    真实分布里 assert+adopt 占九成，若按比例抽，拒斥类只剩三四十条，
    κ 会被大类主导、掩盖论文真正依赖的论争边。故与金标准同策略：拒斥类加权。
    """
    pool = build_pool()
    rng = random.Random(seed)
    plan = {"R-high": round(n * 0.30), "R-low": round(n * 0.15),
            "assert": round(n * 0.35), "adopt": n - round(n * 0.30) - round(n * 0.15) - round(n * 0.35)}
    by = defaultdict(lambda: defaultdict(list))
    for x in pool:
        by[x["L"]][x["bucket"]].append(x)
    for L in by:
        for b in by[L]:
            rng.shuffle(by[L][b])

    picked = []
    for b, quota in plan.items():
        got, i = [], 0
        live = [L for L in LAYERS if by[L][b]]
        while len(got) < quota and live:
            L = live[i % len(live)]
            if by[L][b]:
                got.append(by[L][b].pop())
            else:
                live.remove(L)
                continue
            i += 1
        picked.extend(got)
    rng.shuffle(picked)
    for i, x in enumerate(picked, 1):
        x["no"] = i
    (OUT / "second_coder_sample.json").write_text(
        json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"抽样 {len(picked)} 条 → out/second_coder_sample.json")
    print("  按层:", dict(Counter(x["L"] for x in picked)))
    print("  分层:", dict(Counter(x["bucket"] for x in picked)))
    return picked


# ---------------- 调用 ----------------

def _is_reasoning(model):
    """OpenAI 推理系（o3/o4/gpt-5 及以后）不吃 temperature，且只认 max_completion_tokens。"""
    m = model.lower()
    return m.startswith(("o1", "o3", "o4", "gpt-5"))


def call(key, base, model, messages, temperature, retries=4):
    # glm-5.3-flash 是推理模型：max_tokens 同时吃 reasoning 与正文，实测推理占 500–600，
    # 设 500 会正文为空、设 2500 亦可能被长推理耗尽。默认 8000，并做截断自愈。
    mt = int(os.environ.get("GLM_MAX_TOKENS", 8000))
    reasoning = _is_reasoning(model)
    for att in range(retries):
        payload = {"model": model, "messages": messages}
        if reasoning:
            payload["max_completion_tokens"] = mt      # 推理预算与正文共用
        else:
            payload["temperature"] = temperature
            payload["max_tokens"] = mt
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read().decode("utf-8"))
            ch = d["choices"][0]
            content = ch["message"].get("content") or ""
            # 推理未收尾导致正文被截：加倍预算重试（上限 16000）
            if ch.get("finish_reason") == "length" and not content.strip() and mt < 16000:
                mt = min(mt * 2, 16000)
                time.sleep(1)
                continue
            return content, d.get("usage", {})
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")[:300]
            if e.code in (429, 500, 502, 503, 504) and att < retries - 1:
                time.sleep(2 ** att * 3)
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if att < retries - 1:
                time.sleep(2 ** att * 2)
                continue
            raise


def parse(s):
    """模型若带思考过程，正文里可能出现多个花括号片段；逐个试，取第一个可用的。"""
    for m in re.finditer(r"\{[^{}]*\}", s, flags=re.S):
        try:
            d = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(d, dict) and str(d.get("stance", "")).lower() in ("assert", "adopt", "reject"):
            return finish(d)
    for m in re.finditer(r"\{.*\}", s, flags=re.S):   # 兜底：嵌套结构
        try:
            d = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(d, dict) and str(d.get("stance", "")).lower() in ("assert", "adopt", "reject"):
            return finish(d)
    # 最后兜底：模型偶尔把 null 写成 null"（多一个引号）使 JSON 不合语法，
    # 此时不再要求整体可解析，直接按字段抽取值。
    ms = re.search(r'"?stance"?\s*[:：]\s*"?(assert|adopt|reject)', s, flags=re.I)
    if ms:
        src = None
        mso = re.search(r'"?source"?\s*[:：]\s*("(?:null|none|无|-)"|null|"([^"]+)")', s, flags=re.I)
        if mso:
            cand = (mso.group(2) or "").strip()
            src = cand or None
        mw = re.search(r'"?why"?\s*[:：]\s*"([^"]{0,80})', s)
        return {"stance": ms.group(1).lower(), "source": src,
                "why": (mw.group(1) if mw else "")[:60]}
    return None


def finish(d):
    st = (d.get("stance") or "").strip().lower()
    if st not in ("assert", "adopt", "reject"):
        return None
    src = d.get("source")
    if isinstance(src, str):
        src = src.strip()
        if src.lower() in ("null", "none", "", "无", "—"):
            src = None
    else:
        src = None
    return {"stance": st, "source": src, "why": (d.get("why") or "")[:60]}


def run(args):
    key = args.key or os.environ.get("GLM_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        sys.exit("缺少 API key：export GLM_API_KEY=xxx.yyy 后再跑")
    items = json.loads((OUT / args.items).read_text(encoding="utf-8"))
    dest = OUT / f"second_coder_{args.tag}.jsonl"
    done = set()
    if dest.exists():
        for r in load_jsonl(dest):
            if r.get("ok"):
                done.add(r["no"])
    todo = [x for x in items if x["no"] not in done]
    print(f"待判读 {len(todo)} 条（已完成 {len(done)}）")

    delay = float(os.environ.get("CALL_DELAY", "0"))

    def work(x):
        if delay:
            time.sleep(delay)          # 免费额度限流：串行 + 间隔
        user = (f"【经文】{x['jing'] or '（缺）'}\n"
                f"【注文·{CN[x['L']]}】（节选）{x['ctx']}\n"
                f"【待判条目】术语：{x['term']}\n释义：{x['gloss']}\n"
                f"判断该释义在注文中的立场，输出 JSON。")
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": user}]
        raw, usage = call(key, args.base_url, args.model, msgs, args.temperature)
        p = parse(raw)
        return {"no": x["no"], "ch": x["ch"], "L": x["L"], "bucket": x["bucket"],
                "term": x["term"], "gloss": x["gloss"],
                "ds_stance": x["ds_stance"], "ds_source": x["ds_source"],
                "glm_stance": (p or {}).get("stance"), "glm_source": (p or {}).get("source"),
                "glm_why": (p or {}).get("why"), "raw": raw[:600], "ok": bool(p), "usage": usage}

    n_ok = 0
    with open(dest, "a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, x): x for x in todo}
        for k, fu in enumerate(as_completed(futs), 1):
            try:
                r = fu.result()
            except Exception as e:
                x = futs[fu]
                r = {"no": x["no"], "ch": x["ch"], "L": x["L"], "bucket": x["bucket"],
                     "term": x["term"], "ok": False, "err": str(e)[:300]}
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            n_ok += 1 if r.get("ok") else 0
            if k % 20 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)}（成功 {n_ok}）")
    print(f"完成 → {dest}")


# ---------------- 指标 ----------------

def kappa(a, b):
    assert len(a) == len(b) and a
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe), po, pe


def same_src(x, y):
    if x is None and y is None:
        return True
    if x is None or y is None:
        return False
    x, y = ALIAS.get(x, x), ALIAS.get(y, y)
    if x == y:
        return True
    return x in y or y in x


def boot_ci(a, b, n_boot=2000, seed=3):
    """κ 的 bootstrap 95% 区间：审稿人会问 200 条样本的稳定性。"""
    rng = random.Random(seed)
    n = len(a)
    ks = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        x = [a[i] for i in idx]
        y = [b[i] for i in idx]
        kk = kappa(x, y)[0]
        if kk == kk:                       # 跳过 nan
            ks.append(kk)
    if not ks:
        return (float("nan"), float("nan"))
    ks.sort()
    return (ks[int(0.025 * len(ks))], ks[int(0.975 * len(ks)) - 1])


def confusion(a, b, cats=("assert", "adopt", "reject")):
    return [[sum(1 for p, q in zip(a, b) if p == x and q == y) for y in cats] for x in cats]


def report(args):
    rows = [r for r in load_jsonl(OUT / f"second_coder_{args.tag}.jsonl") if r.get("ok")]
    if not rows:
        sys.exit("没有可用的判读结果")
    a = [r["ds_stance"] for r in rows]
    b = [r["glm_stance"] for r in rows]
    k, po, pe = kappa(a, b)
    lo, hi = boot_ci(a, b)
    cats = ["assert", "adopt", "reject"]
    cm = confusion(a, b, cats)
    f1s = {}
    for c in cats:
        tp = sum(1 for p, q in zip(a, b) if p == c and q == c)
        fp = sum(1 for p, q in zip(a, b) if p != c and q == c)
        fn = sum(1 for p, q in zip(a, b) if p == c and q != c)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1s[c] = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    macro_f1 = sum(f1s.values()) / len(f1s)

    print(f"\n=== 模型间一致性（n={len(rows)}，{args.model} vs DeepSeek）===")
    print(f"  一致率 {po*100:.1f}%  Cohen's κ = {k:.3f}  95% CI [{lo:.2f}, {hi:.2f}]")
    print(f"  宏平均 F1 = {macro_f1:.3f}  （" + "  ".join(f"{c}={f1s[c]:.2f}" for c in cats) + "）")
    print("\n  混淆矩阵（行=DeepSeek，列=第二模型）：")
    print("        " + "".join(f"{c:>9}" for c in cats))
    for x, row in zip(cats, cm):
        print(f"  {x:>7} " + "".join(f"{v:>9}" for v in row))

    per = defaultdict(lambda: ([], []))
    for r in rows:
        per[r["L"]][0].append(r["ds_stance"])
        per[r["L"]][1].append(r["glm_stance"])
    print("\n  按注本层：")
    layer_rows = []
    for L in LAYERS:
        if L not in per:
            continue
        x, y = per[L]
        agree = sum(1 for i, j in zip(x, y) if i == j) / len(x) * 100
        degenerate = len(set(x) | set(y)) < 2
        kk = float("nan") if degenerate else kappa(x, y)[0]
        layer_rows.append((L, len(x), agree, kk))
        ks_txt = "—" if degenerate else f"{kk:.2f}"
        print(f"    {CN.get(L,L):12} n={len(x):3}  一致 {agree:5.1f}%  κ={ks_txt}")

    rej = [r for r in rows if r["glm_stance"] == "reject" and r["ds_stance"] == "reject"]
    hit = sum(1 for r in rej if same_src(r["ds_source"], r["glm_source"]))
    print(f"\n  双方均判 reject 的 {len(rej)} 条中，被驳对象一致 {hit} 条 = {hit/max(1,len(rej))*100:.1f}%")

    # ---- 三方对照：若已跑过金标准 40 条 ----
    three = None
    gpath = OUT / "second_coder_gold.jsonl"
    if gpath.exists():
        # 金标准立场取自发布版数据集 data/gold/gold_40.jsonl（字段 gold_stance）；
        # 与第二模型判读结果 second_coder_gold.jsonl 以 no 为键，逐条核对 term/chapter/layer
        items = {x["no"]: x for x in load_jsonl(P.GOLD / "gold_40.jsonl")}
        rows_g = [r for r in load_jsonl(gpath) if r.get("ok") and r["no"] in items]
        for r in rows_g:
            g = items[r["no"]]
            if (g["term"], g["chapter"], g["layer"]) != (r["term"], r["ch"], r["L"]):
                sys.exit(f"金标准与第二判读条目错位：no={r['no']}")
        exp = [items[r["no"]]["gold_stance"] for r in rows_g]
        ds = [r["ds_stance"] for r in rows_g]
        gl = [r["glm_stance"] for r in rows_g]
        kgs_d, po_d, _ = kappa(exp, ds)
        kgs_g, po_g, _ = kappa(exp, gl)
        kdg, po_dg, _ = kappa(ds, gl)
        three = dict(n=len(rows_g), ds_expert=(kgs_d, po_d), glm_expert=(kgs_g, po_g),
                     ds_glm=(kdg, po_dg))
        print(f"\n=== 三方对照（同一批 {len(rows_g)} 条金标准）===")
        print(f"  DeepSeek vs 专家 ：一致 {po_d*100:.1f}%  κ={kgs_d:.3f}")
        print(f"  GLM      vs 专家 ：一致 {po_g*100:.1f}%  κ={kgs_g:.3f}")
        print(f"  GLM      vs DS   ：一致 {po_dg*100:.1f}%  κ={kdg:.3f}")

    dis = [r for r in rows if r["ds_stance"] != r["glm_stance"]]
    md = [f"# 第二模型判读报告（{args.tag}）", "",
          f"- 模型：`{args.model}`", f"- 判读条目：{len(rows)}",
          f"- 一致率：{po*100:.1f}%　Cohen's κ = {k:.3f}（95% CI {lo:.2f}–{hi:.2f}）",
          f"- 宏平均 F1：{macro_f1:.3f}",
          f"- 分歧：{len(dis)} 条（{len(dis)/len(rows)*100:.1f}%）", "",
          "## 混淆矩阵（行=DeepSeek，列=第二模型）", "",
          "| | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for x, row in zip(cats, cm):
        md.append(f"| **{x}** | " + " | ".join(str(v) for v in row) + " |")
    md += ["", "## 按注本层", "", "| 层 | n | 一致率 | κ |", "|---|---|---|---|"]
    for L, n_, ag, kk in layer_rows:
        md.append(f"| {CN.get(L,L)} | {n_} | {ag:.1f}% | " + ("—" if kk != kk else f"{kk:.2f}") + " |")
    if three:
        md += ["", "## 三方对照（同一批金标准条目）", "",
               "| 配对 | n | 一致率 | κ |", "|---|---|---|---|",
               f"| DeepSeek vs 专家 | {three['n']} | {three['ds_expert'][1]*100:.1f}% | {three['ds_expert'][0]:.2f} |",
               f"| GLM vs 专家 | {three['n']} | {three['glm_expert'][1]*100:.1f}% | {three['glm_expert'][0]:.2f} |",
               f"| GLM vs DeepSeek | {three['n']} | {three['ds_glm'][1]*100:.1f}% | {three['ds_glm'][0]:.2f} |"]
    md += ["", f"## 分歧条目（{len(dis)} 条，供裁定）", ""]
    for r in dis[:40]:
        md += [f"### {r['no']}. {r['ch']} · {CN.get(r['L'],r['L'])} · {r['term']}", "",
               f"- DeepSeek：`{r['ds_stance']}` → `{r['ds_source']}`",
               f"- {args.tag}：`{r['glm_stance']}` → `{r['glm_source']}`（{r.get('glm_why') or ''}）", ""]
    (OUT / f"second_coder_report_{args.tag}.md").write_text("\n".join(md), encoding="utf-8")

    json.dump({"model": args.model, "n": len(rows), "kappa": round(k, 4),
               "kappa_ci": [round(lo, 4), round(hi, 4)], "agreement": round(po, 4),
               "macro_f1": round(macro_f1, 4), "per_class_f1": {c: round(v, 3) for c, v in f1s.items()},
               "n_disagree": len(dis), "reject_src_agree": f"{hit}/{len(rej)}",
               "three_way": three},
              open(OUT / f"second_coder_metrics_{args.tag}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n报告 → out/second_coder_report_{args.tag}.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "run", "report", "all"], nargs="?", default="all")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--model", default=os.environ.get("GLM_MODEL", "glm-5.3-flash"))
    ap.add_argument("--base-url", default=os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"))
    ap.add_argument("--key", default=None)
    ap.add_argument("--tag", default="glm")
    ap.add_argument("--items", default="second_coder_sample.json")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()
    if args.cmd in ("sample", "all"):
        sample(args.n)
    if args.cmd in ("run", "all"):
        run(args)
    if args.cmd in ("report", "all"):
        report(args)


if __name__ == "__main__":
    main()
