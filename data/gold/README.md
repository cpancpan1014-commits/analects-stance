# Gold standard

40 items judged by hand against the model's output, plus the two thousand-word
sheets that produced them. Everything here is small on purpose: it is a
reliability sample, not an annotation of the corpus.

## Files

| File | What it is |
|---|---|
| `gold_40.csv` | the labels, one row per item; the columns the paper reports from |
| `gold_40.jsonl` | the same items joined to scripture, a ±200-character commentary window, and the model's original output |
| `sample_40.json` | the items as drawn, before judging: term, gloss, type, stance, source, evidence |
| `blind_sheet_20.md` | twenty edges, presented blind, for auditing whether the target attribution is right |
| `audit_20.json` | the twenty edges in machine-readable form (critic, target, chapter, term, evidence) |
| `review_40.md` | the judging sheet the annotator actually saw: scripture, gloss, evidence, context |

## How the sample was drawn

Stratified, from the five core layers only, excluding chapter `01-01` (the
few-shot chapter in the prompt):

| Stratum | Definition | n |
|---|---|---|
| `R-high` | `reject`, and `evidence` carries a negative marker | 14 |
| `R-low` | `reject`, no marker in `evidence` | 8 |
| `assert` | the commentator's own gloss | 12 |
| `adopt` | a gloss quoted from someone else | 6 |

Rejections are oversampled about fourfold against their 12.3% share of the
corpus, because rejections are what the paper's graph is made of. Layers are
rotated so that no single commentary dominates. Seed 20261101; re-running
`scripts/sample_gold.py` reproduces the file exactly.

## The three questions

Each item was judged with 300–400 characters of the commentary open, on:

1. **Is the term the one being expounded?** Not merely a word that appears in
   the chapter: a commentator may mention 仁 without glossing it.
2. **Is the stance right?** `assert` = the commentator's own gloss; `adopt` = a
   gloss he reports and accepts; `reject` = a gloss he reports and rejects.
3. **Is the target right, and is it named?** `source_class` records the outcome,
   and the values are worth knowing before reading the column:

| `source_class` | n | Meaning |
|---|---|---|
| `named` | 17 | an exegete who maps to a node in the graph |
| `vague` | 4 | a collectivity (宋儒, 舊說) — a target, but not a node |
| `nonent` | 3 | names someone inside the text (宰我, 子貢), not an exegete |
| `missing` | 3 | the model left it null although the commentary names one |
| `none` | 12 | the item proposes no target, correctly |
| `wrong` | 1 | the target is wrong |

Of the 28 items that propose any target, 17 (60.7%) are mappable to a node; that
coverage figure, not precision, is the binding constraint on the graph.

Agreement is computed on question 2, three labels, Cohen's κ. Result: 38/40
(95.0%), κ = .917; macro F1 .945.

## The two errors

Both run the same way — a quotation recorded as the commentator's own claim,
which is the quotation-boundary failure discussed in Section I:

- **`10-04`** (Zhu Xi). 陸氏曰：「趨下本無進字，俗本有之，誤也。」 The 誤也 is Lu
  Deming's; its object is a recension, not an exegete. Zhu Xi asserts nothing.
- **`04-26`** (Xing Bing). A pronunciation note, recorded as a gloss.

## Three items not in the cross-family subset

Items **7**, **20** and **36** carry He Yan notes of 9, 12 and 31 characters.
The blind judging pool skips layers under 40 characters — there is no context to
judge in — so those three are in `gold_40` but not in the 37-item subset that
Table IV is computed on. The `in_blind_subset` field marks them.

## One annotator

Every κ against gold is agreement with the person who designed the schema and
wrote the prompt. It bounds prompt fit, not truth, and the paper says so. The
paper's one human-independent check is model against model — GLM re-judged 200
sampled items blind and agrees with the primary model at κ = .843 (95% CI
.77–.90) on the 197 that parsed, reproducible with `scripts/second_coder.py
report`. That measures stability across model families; it is not evidence about
truth, and a second human annotator remains the first item of further work.

## The twenty-edge audit

`blind_sheet_20.md` presents twelve edges into Zhu Xi and eight into Jinsai
without their labels, asking only: does the named authority appear in the
evidence, and does the negative judgement attach to him? All twenty passed. It is
reproduced here so the check can be repeated rather than believed.
