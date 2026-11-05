# Prompt set

Every string in this directory is what the published run sent, byte for byte.
The files were dumped from the running module, not retyped, and
`python3 scripts/promptset.py --check-legacy <old-scripts-dir>` re-proves that
against the code that made the calls (3,507 user messages, 0 differences).

| File | Used by | Content |
|---|---|---|
| `system_v3.txt` | all seven layers | six-field schema, stance rules, prohibitions |
| `user_template.txt` | all seven layers | per-call message, 7 placeholders |
| `fewshot_heyan.txt` | `heyan` | *Jijie*: quotation recorded as `adopt` |
| `fewshot_cho.txt` | `cho` | *Riddle*: assertion and rejection on one term |
| `fewshot_liu.txt` | `liu` | *Zhengyi*: cite first, then correct Zhu Xi |
| `fewshot_huowen.txt` | `huowen` | *Questions*: self-posed question, then graded verdicts |
| `judge_system.txt` | cross-family test | blind stance judge, 3 labels, target required |
| `layers.json` | — | layer id → commentary, era, exemplar |

## Why four exemplars and not seven

An exemplar teaches a *genre*, not a commentator. `shu` (Xing Bing's
subcommentary) is a compilation like `heyan`, and `kogi` (Jinsai) is authored
like `cho`, so each pair shares the archetype of its genre. Giving all seven
their own would quadruple the prompt for no gain; giving none would leave the
model guessing whether 「馬曰」 is the author's view. The two control layers are
the exception the design forces: the *Zhengyi* prints scripture and gloss in
one stream, and the *Questions* argues in paragraphs, so each needed a sample
of its own layout.

`layers.json` is the authority on which layer gets which exemplar; the
`fewshot` field is `null` where none is sent.

## The user message

```
【章号】{chapter}
【原文】{text}

【注家】{annotator}（{era}），层标识 = {layer}
{reference}
【注文】
{note}

请抽取该注家在本章中的训释条目。
```

`{reference}` is empty or `【体例参照】` + the exemplar + a newline, and it sits
on its own line: when no exemplar is sent, the blank line is kept, because the
published run kept it.

`{note}` is truncated at 6,000 characters with `……（以下略）`. Eleven Sorai
chapters run past that; the truncation is part of the method, not an accident of
the script.

## The judge prompt

The cross-family comparison does not re-run extraction. It shows a second model
one extracted item blind -- scripture, commentary window, term, gloss, and
nothing else, never the primary model's answer -- and asks for the stance. That
is why Table IV measures reading, not parsing: the schema is already filled in.

## Changes across revisions

Only v3 is shipped as a runnable prompt; `history/` holds the two design notes
that preceded it, because the paper reports what each revision did to precision.

| Rev | Change | Share of claimed rejections carrying a marker |
|---|---|---|
| v1 (`history/prompt_design_v1.md`) | five fields, no `stance`; a compilation's quotations were extracted as its own glosses | not measurable: no rejections expressed |
| v2 (`history/prompt_design_v2.md`) | six fields; `stance` + `source` added | 49.5% |
| v3 (`system_v3.txt`) | genre rules A–D; `reject` conditional on a marker; evidence window 30 → 50 characters | 64.6% (five core layers), 59.6% over seven |

The gate is not a prompt instruction. A model's claim to have rejected someone
is checked against its own `evidence` field by `alg1.neg()`; the prompt only
asks for a marker, the code enforces one.
