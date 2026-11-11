# Differences between the archived v1.0.0 and the code

`scripts/verify.py` recomputes every number in the paper from the released data.
As of the present revision it reports **all checks pass, no known differences**.

This file records what changed. The archived v1.0.0 of the paper (version DOI
`10.5281/zenodo.23983961`) printed five numbers that the code does not produce.
All five are corrected in the revised manuscript, and `verify.py` now checks
against the corrected values. Anyone citing v1.0.0 should prefer this repository.

---

## 1–3. Table III: 111 / 101 / 91.0% → 110 / 100 / 90.9%

**Where** Abstract ("90.9% of the 110 nodes"); §I roadmap; §V-C Table III total
row and the 知 row; §V-C "only 15 of the 88 disputed nodes in the named rows";
§VIII conclusion ("multiple readings in 90.9% of the chapters").

**Cause.** The concept table was computed by an earlier script that read the
extraction output directly. It therefore kept the 289 pronunciation-only glosses
that Algorithm 1 step 3 removes (`I <- I \ phonetic(I)`). One node depends on
this: **17-08**, where Xing Bing glosses 知 as 明照於事曰知 and Zhu Xi writes
only 知，去聲. With the 去聲 note counted, the node has two readings and 知 has 6
comparable nodes; without it, one reading, and 知 has 5. The 知 row therefore
moves from 6 / 5 / 83.3% to 5 / 4 / 80.0%, and the named rows of Table III sum
to 96 + 14 = 110 comparable and 88 + 12 = 100 disputed.

Dropping the note is also the better reading: 知，去聲 records a tone change that
identifies the word as 智, which is a phonological instruction, not a competing
gloss of 知 "to know". The paper's own §VII argument that the measure separates
definitions and doctrines assumes such notes are not readings.

§III-E's "1,776 comparable nodes" and "1,383 disputed nodes" are unaffected;
both were already computed on the filtered set.

---

## 4–5. §V-B: the tail of Table II

**Corrected claim.** "three targets absorb 278 edges (32.1%), the next eight a
further 220 (25.4%), the remaining 196 share 369 (42.6%)."

The archived version read "three targets absorb 278 edges (32.1%) while 196
others share 369 (42.6%)", which leaves the eight intervening rows unaccounted
for: 278 + 369 = 647, not 867. The figures themselves are right. Table II lists
eleven rows by name summing to 498 on the rounded values it prints, and
867 − 498 = 369; 278 / 867 = 32.1% and 369 / 867 = 42.6% both reproduce. Only
the sentence was incomplete, and it now closes.

**Note on a false lead.** An earlier draft of this file claimed the tail should
read "137 named individuals share 440 (50.7%)" and that no aggregation produces
369. That is wrong. 137 is the count of individuals *other than the top three*,
and 439.7 is the edges they hold; but Table II names nine individuals and two
collectivities before folding the rest, so the table's remainder is 196 targets
carrying 369 edges. Rounding each named row to the integer the table prints
costs about 1.7 edges against the unrounded sum, which is the whole of the
discrepancy. `verify.py` now checks the fold by arithmetic rather than by
comparing two differently-defined quantities.

---

## 6. Wording: "held out of prompt construction" → "development"

**Where** §IV, the two control layers.

**Cause.** Neither book's output was used to revise the prompt, which is the
claim the sentence was making. But each did receive one exemplar drawn from its
own opening pages, because both are printed in a layout the core five do not
share; without it the model reads the wrong unit. That is stated in Appendix A.4
of the release but was not in the paper, and a careful reader of the code will
find the exemplars.

**Revised sentence.** "held out of prompt development (each received one layout
exemplar; no revision followed its output)".

---

## 7. Jinsai contamination: similarity 0.88–0.99 → 0.85–0.97

**Where** §IV, the layer-integrity check.

Recomputed with the released rule (punctuation-stripped `SequenceMatcher` ratio,
chapters of 50+ characters), the six chapters run **0.851–0.971**: 04-16 .971,
12-22 .970, 08-15 .888, 15-14 .868, 12-21 .857, 07-17 .851. The set of six is
identical and the conclusion is unaffected. The values, per chapter, are in
`data/contamination.json`; a seventh chapter (11-05, a 24-character layer) scores
.889 on a single shared classical phrase and is listed there as a near miss, not
a defect.
