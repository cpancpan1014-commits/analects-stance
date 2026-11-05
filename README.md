# Analects stance corpus and dispute graph

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23983960.svg)](https://doi.org/10.5281/zenodo.23983960)

Data and code for *How Well Do LLMs Read Classical Commentary? Stance-Aware
Extraction from a Sino-Japanese Analects Corpus* (ICISE-IE 2026).

Seven commentaries on the *Analects* — five Chinese, two Japanese, all in
literary Chinese — annotated for stance at the level of the individual gloss.
The output is a directed graph of who rejects whom, and a measure of how many
readings a term carries.

**Everything here runs offline.** The model calls are cached in `out/`, so no
API key is needed to reproduce the paper.

```bash
python3 scripts/verify.py        # recompute every number in the paper
```

```
1. Corpus
  [PASS] chapters in the corpus                       501   paper: 501
  ...
all checks pass        (5 known differences from the printed text: docs/ERRATA.md)
```

---

## What is where

| | |
|---|---|
| `data/corpus_clean.jsonl` | the corpus: 501 chapters, scripture + five commentaries |
| `data/gold/gold_40.jsonl` | the 40 human-labelled items, with context |
| `data/prompts/` | the prompt set, verbatim (Appendix A) |
| `scripts/alg1.py` | **Algorithm 1**, readable end to end |
| `out/` | 2,646 cached model replies and every derived table |
| `docs/DATA_CARD.md` | what the data is, and where it will mislead you |
| `docs/ERRATA.md` | five numbers where the paper and the code disagree |

## Reproducing the paper

`scripts/alg1.py` is the pseudocode: one call per chapter-layer pair, a term
filter, a negative-marker gate, a greedy clustering of glosses. `build_network.py`
drives it over the seven layers and prints the tables.

```bash
python3 scripts/build_network.py --all-seven    # Figure 1, Tables I–II, §V
python3 scripts/concept_divergence.py           # Table III
python3 scripts/threshold_sweep.py              # τ = .50–.90 sensitivity
python3 scripts/make_fig_dispute.py             # Figure 1, vector + raster
python3 scripts/gold_metrics.py                 # κ = .917 on 40 items
python3 scripts/cross_family.py                 # Table IV, seven families
python3 scripts/second_coder.py report          # κ = .843 on 197 items, model vs model
```

`second_coder.py report` reads the blind judgements a second model family (GLM)
gave on 200 sampled items — 197 parsed — already cached in
`out/second_coder_glm.jsonl`, and reports agreement against the primary model.
These are the two κ the paper quotes, and they mean different things: .917 is
model against a human expert on 40 items; .843 is one model against another on
197 items, which bounds stability across families, not against truth.

Cost of a full re-extraction, if you want to spend it: 2,646 calls, about USD
0.79 at the prices of November 2026.

```bash
export DEEPSEEK_API_KEY=sk-...
python3 scripts/extract_terms.py              # 1,695 calls, five core layers
python3 scripts/extract_liu.py                #   496, Liu Baonan
python3 scripts/extract_huowen.py             #   455, Zhu Xi's Questions
```

Any OpenAI-compatible endpoint works: `--model` and `--base-url` are arguments,
not constants. `--dry-run` prints the first message so you can read the prompt
before paying for it.

## Rebuilding the corpus

```bash
python3 scripts/build_release_corpus.py    # OCR repair + edition-defect flags
python3 scripts/build_liu_corpus.py        # from data/raw/liu_zhengyi/*.html
python3 scripts/build_huowen_corpus.py     # from data/raw/huowen/*.html
```

The release corpus is byte-identical, layer by layer, to the text the published
calls saw; `build_release_corpus.py --check` proves it against a reference copy.

## Three things that make this corpus awkward

1. **Quotation and judgement share a surface.** Zhu Xi writes 陸氏曰：「…誤也」:
   the negation is Lu Deming's, its object is a recension, and Zhu Xi asserts
   nothing. Both readings fit the six fields, and the gate cannot separate them
   (Section I of the paper; item `10-04` in the gold standard).
2. **Six chapters carry the wrong Japanese commentary.** The edition binds two
   works in one volume and mis-assigns pages. Flagged in the data as
   `kogi_status: "suppressed"`, with evidence in `data/contamination.json`.
3. **The two control layers do not share the chapter grid.** The *Zhengyi*
   prints scripture and gloss in one stream; the *Questions* argues in paragraphs
   that cross chapter boundaries. They enter Tables I, II and V but not III.

## Authors

**Cheng Pan** (潘呈) — PhD in Literature, Soochow University; School of
International Business and Language Studies, Guangdong University of Science and
Technology, Dongguan, China. Correspondence: pancheng1@gdust.edu.cn

**Di Wu** — School of International Business and Language Studies, Guangdong
University of Science and Technology, Dongguan, China.

## Citing

If you use the data, cite the paper and the repository version. `CITATION.cff`
has both. Code is MIT, data is CC BY 4.0.

The archive is on Zenodo under two DOIs, and the difference matters:

| DOI | Resolves to | Use it when |
|---|---|---|
| `10.5281/zenodo.23983960` | always the latest version (concept DOI) | you want a citation that will not break when a later version appears |
| `10.5281/zenodo.23983961` | v1.0.0 exactly (version DOI) | you need to pin the exact archive the paper's numbers came from |
