# Known differences from the printed paper

`scripts/verify.py` recomputes every number in the paper from the released data.
Five checks are marked `KNOWN`: the code and the PDF disagree, and the code is
right. Each is listed here with the location in the paper, the cause, and a
suggested replacement sentence.

Two of the five are one root cause: a population that still contained
pronunciation-only glosses.

---

## 1–3. Table III: 111 / 101 / 91.0% → 110 / 100 / 90.9%

**Where** Abstract ("91.0% of the 111 nodes", "91.0% of chapters"); §I roadmap;
§V-C Table III total row and the sentence "Across the five aligned layers, 1,383
(chapter, term) nodes carry two or more distinct readings"; §VIII conclusion
("admits multiple readings in 91.0% of the chapters"); also §V-C's "only 15 of
the 89 disputed nodes in the named rows of Table III".

**Cause.** The concept table was computed by an earlier script that read the
extraction output directly. It therefore kept the 289 pronunciation-only glosses
that Algorithm 1 step 3 removes (`I <- I \ phonetic(I)`). One node depends on
this: **17-08**, where Xing Bing glosses 知 as 明照於事曰知 and Zhu Xi writes
only 知，去聲. With the 去聲 note counted, the node has two readings and 知 has 6
comparable nodes; without it, one reading, and 知 has 5. Everything else in
Tables III and the τ sweep already uses the filtered set -- §III-E's "1,776
comparable nodes" only reconciles with 110, not 111.

Dropping the note is also the better reading: 知，去聲 records a tone change that
identifies the word as 智, which is a phonological instruction, not a competing
gloss of 知 "to know". The paper's own §VII argument that the measure separates
definitions and doctrines assumes such notes are not readings.

**Suggested replacement.** In all five places, `111` → `110`, `101` → `100`,
`91.0%` → `90.9%`; Table III total row to 110 / 100 / 90.9%.

---

## 4–5. §V-B: "196 others share 369 (42.6%)" → 137 share 440 (50.7%)

**Where** §V-B, second sentence: "The peak is narrow and the tail long: three
targets absorb 278 edges (32.1%) while 196 others share 369 (42.6%)."

**Cause.** 278 (32.1%) reproduces exactly, as do the three composition shares in
the next sentence (named individuals 82.8%, collectivities 12.7%, works 4.3%).
The tail does not: `out/table2.json` holds 140 named individuals carrying 717.3
edges, of which the top three take 277.8 and the other **137 take 439.7
(50.7%)**. The 199 labels required for "3 + 196" are not in the data, and no
aggregation in `table2_targets.py` produces 369. The figure appears to date from
an earlier snapshot of the graph.

**Suggested replacement.** "three targets absorb 278 edges (32.1%) while the
other 137 named individuals share 440 (50.7%); 36 collectivities and 29 works
take a further 148 (17.1%)."

---

## 6. Wording: "held out of prompt construction"

**Where** §IV, the two control layers.

**Cause.** Neither book's output was used to revise the prompt, which is the
claim the sentence is making. But each did receive one exemplar drawn from its
own opening pages, because both are printed in a layout the core five do not
share; without it the model reads the wrong unit. That is stated in Appendix A.4
of the release but not in the paper, and a careful reader of the code will find
the exemplars.

**Suggested replacement.** "held out of prompt development (each received one
layout exemplar from its own opening, and no revision was made in response to
its output)".

---

## Not an erratum: the Jinsai contamination similarity range

§IV says the duplicated layer "similarity runs 0.88–0.99". Recomputed with the
released rule (punctuation-stripped `SequenceMatcher` ratio, chapters of 50+
characters), the six chapters run **0.851–0.971**: 04-16 .971, 12-22 .970,
08-15 .888, 15-14 .868, 12-21 .857, 07-17 .851. The set of six is identical and
the conclusion is unaffected, but the range should read 0.85–0.97. The values,
per chapter, are in `data/contamination.json`; a seventh chapter (11-05, a
24-character layer) scores .889 on a single shared classical phrase and is
listed there as a near miss, not a defect.
