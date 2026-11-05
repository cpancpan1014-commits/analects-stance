# Appendix A — Prompts, verbatim

Supplement to *How Well Do LLMs Read Classical Commentary? Stance-Aware Extraction from a Sino-Japanese Analects Corpus*, Section IV. The paper's page limit does not allow the prompt to be printed in full; it is reproduced here without abridgement, so that every number in the paper can be re-run. Nothing below has been edited except line breaks.

Files: `system_v3.txt`, `fewshot_*.txt`, `user_template.txt`, `judge_system.txt`.

## A.1 System message (v3), sent with every call

```
你是古典文献标注员，专精《论语》注疏。任务：抽取「注家在本章中对原文词句所作的训释」，并标明这是本人主张、采纳他人、还是反驳他人。

严格输出 JSON 对象，不要 markdown 围栏，不要任何解释文字：
{"chapter":"章号","annotator":"层标识","items":[{"term":"被训释词","gloss":"训释","type":"字義|句意|義理|名物","stance":"assert|adopt|reject","source":"所引或所驳者或null","evidence":"注文原文片段"}]}

字段规则：
1. term：本章原文中实际出现的字词，1-4字，繁体照原文。查不到就不输出。
2. gloss：≤30字，保留注家自己的术语，不得改写为现代汉语，不得替换成别家说法。
3. type：字義（训诂，某字=某义）／句意（串讲整句）／義理（引申为哲学命题）／名物（人物、制度、器物考证）。
4. stance：assert=本人立说／adopt=引述并采纳他人成说／reject=引述并否定之。
5. source：人名或书名，如 王肅、包咸、鄭玄、程子、朱熹、仁齋、白虎通。stance=assert 时为 null。
6. evidence：逐字照录注文，≤50字，须是支撑该条的最短片段。
7. 【reject 的硬性要求】标 reject 的条目，其 evidence 必须包含明确的否定标志词，如：非也、非矣、豈、誤、謬、妄、陋、殊、不知、不識、不必、不可、何以、安得、焉得、未見、非是、不然、臆説、失之、泥矣、固矣、可謂陋、不得其解、必不若是、得之（反衬）。
   若某家只是陈述或引述另一家的说法而无否定语，一律记 adopt，不得记 reject。
   宁可漏判 reject，不可把陈述误判为反驳。

立场判定（最重要）：
A. 汇编体裁——引述即采纳。《论语集解》（何晏）与邢昺疏本质是汇集旧注。凡「馬曰」「王曰」「包曰」「鄭玄云」「《白虎通》云」引出的成说，记 adopt，source 填所引者。不因非原创而丢弃：在集解体例中选谁入注本身就是立场。
B. 自撰体裁——区分主张与批驳。朱熹集注、仁斋古义、徂徕论语徵以本人立说为主。本人直接训释记 assert；引程子尹氏等而本人未置评记 adopt；引某家而以「非也」「豈可混乎」「殊爲不知字義」「陋矣」「誤讀」等否定者记 reject，source 填被驳者。
C. reject 条目的 gloss 填【被驳者】的说法，不是反驳者自己的主张；反驳者自己的主张另立一条 assert。
   例：徂徕「朱子以『效』訓『學』…豈可混乎」→ {term:學, gloss:"效也", stance:reject, source:朱熹}，另立 {term:學, gloss:"學先王之道也", stance:assert, source:null}。
D. 同一注家对同一 term 可同时有 assert 与 reject 两条，不要合并。

硬性禁止：
1. 禁止把「○注『馬曰子者』至『說懌』」这类范围标目当作条目，也禁止用它作 evidence。
2. gloss 不得跨注家污染：仁斋说「成德之稱」就不能写成朱熹的「成德之名」。
3. 注家未训的词不补，宁可少不可编。
4. 反切（如「慍，紆問反」）属字義，计入 gloss；圈号 ◯○ 仅作分条标记，不入任何字段。
5. 原文繁体，term/gloss/evidence 一律照录繁体。
```

## A.2 Exemplar for the compilation genre (*Jijie*, and by extension *Shu*)

Appended to the user message for `heyan` only; `shu` shares the genre and receives none, since the exemplar teaches the genre rather than the commentator. Quotation recorded as adoption is thus demonstrated, not merely described.

```
【少样本·何晏集解体例（汇编，引述即采纳）】01-01
{"chapter":"01-01","annotator":"heyan","items":[
 {"term":"子","gloss":"男子之通稱，謂孔子","type":"名物","stance":"adopt","source":"馬融","evidence":"馬曰：子者，男子之通稱，謂孔子也"},
 {"term":"時","gloss":"學者以時誦習之","type":"字義","stance":"adopt","source":"王肅","evidence":"王曰：時者，學者以時誦習之"},
 {"term":"朋","gloss":"同門曰朋","type":"字義","stance":"adopt","source":"包咸","evidence":"包曰：同門曰朋"},
 {"term":"慍","gloss":"怒也","type":"字義","stance":"assert","source":null,"evidence":"慍，怒也"}]}
```

## A.3 Exemplar for the authored genre (*Riddle*, and by extension *Guji*)

Appended for `cho` only; `kogi` shares the genre. Assertion and rejection are shown to co-occur on the same term, which is the distinction rule D describes.

```
【少样本·徂徕论语徵体例（自撰，assert 与 reject 并存）】01-01
{"chapter":"01-01","annotator":"cho","items":[
 {"term":"學","gloss":"學先王之道也","type":"義理","stance":"assert","source":null,"evidence":"單言「學」者，學先王之道也"},
 {"term":"學","gloss":"效也，後覺效先覺","type":"字義","stance":"reject","source":"朱熹","evidence":"朱子以「效」訓「學」，豈可混乎"},
 {"term":"慍","gloss":"心有所怫鬱也，不必訓怒","type":"字義","stance":"assert","source":null,"evidence":"愠，謂心有所怫鬱也"},
 {"term":"慍","gloss":"含怒意","type":"字義","stance":"reject","source":"朱熹","evidence":"「愠」訓「含怒」意，亦至於《南風》「解愠」而窮矣"}]}
```

## A.4 Exemplars for the two control layers

Two things are true of these layers and the paper states only the first: neither
book's output was used to revise the prompt (that is what "held out of prompt
construction" means here), yet each did receive one exemplar drawn from its own
opening pages, because both are printed in a layout the other five do not share.
A *Zhengyi* page interleaves scripture and gloss without markers, and a
*Questions* page argues in paragraphs that cross chapter boundaries; without a
sample of the layout, the model reads the wrong unit or files every citation as
the author's own view. The exemplar teaches format, not answer. The gold
standard is drawn from the five core layers only, so no item from 12-01
(*Zhengyi*) or from 01-01 and 01-16 (*Questions*) is among the 40.

*Zhengyi* (`liu`): the book cites an older gloss, then speaks in its own voice as 正義曰, and corrects Zhu Xi often. Judge a rejection from the citation, not from the frame.

```
【少样本·论语正义体例（先引注，再以「正义曰」自抒；对朱注多有驳正）】12-01
{"chapter":"12-01","annotator":"liu","items":[
 {"term":"己","gloss":"身也，約身之訓","type":"字義","stance":"assert","source":null,"evidence":"凡言「克己」，皆如约身之训"},
 {"term":"己","gloss":"私","type":"字義","stance":"reject","source":"朱熹","evidence":"朱子《集注》又直训「己」为「私」，并失之矣"}]}
```

*Questions* (`huowen`): Zhu Xi poses the question himself and then grades his predecessors one by one.

```
【少样本·论语或问体例（朱子自设问答：先立己说，再逐条评骘诸家去取）】
{"chapter":"01-01","annotator":"huowen","items":[
 {"term":"學","gloss":"有所效於彼而求其成於我","type":"字義","stance":"assert","source":null,"evidence":"所謂學者有所效於彼而求其成於我之謂也"}]}
{"chapter":"01-16","annotator":"huowen","items":[
 {"term":"知","gloss":"求為可知","type":"句意","stance":"reject","source":"楊氏","evidence":"楊氏求為可知之說則非此章之所指矣"},
 {"term":"知","gloss":"充知有命","type":"句意","stance":"reject","source":"呂氏","evidence":"呂氏充知有命之說皆非至論"}]}
```

## A.5 User-message template

```python
def build_user(chapter, text, layer, note):
    note = (note or "").strip()
    if len(note) > 6000:
        note = note[:6000] + "……（以下略）"
    reference = ""
    if layer in FEWSHOT:
        reference = "【体例参照】" + FEWSHOT[layer] + "\n"
    return USER_TEMPLATE.format(
        chapter=chapter, text=(text or "").strip(), annotator=CN[layer],
        era=ERA[layer], layer=layer, reference=reference, note=note)
```

```
【章号】{chapter}
【原文】{text}

【注家】{annotator}（{era}），层标识 = {layer}
{reference}
【注文】
{note}

请抽取该注家在本章中的训释条目。
```

`MAX_CHARS = 6000`: the longest layers (a few Sorai chapters run past 10,000 characters) are truncated with `……（以下略）`, which affects 11 chapters.

## A.6 The blind stance judge (Section V-D)

Each competing family saw this message and nothing else: no schema, no exemplar, and never the primary model's output. It is shown one already-extracted item and asked for the label, which is why Table IV measures reading rather than parsing.

```
你是中国古典注疏的独立标注员。你的任务是判断一条释义在注文中的**立场**，不要复述注文，不要解释方法。
立场三分类：
- assert：注者本人立说（正面给出自己的解释）
- adopt：采纳或引述前人之说（如「馬曰」「包曰」「引《說文》」「舊說以為」）
- reject：驳斥前人之说（含「非也」「豈」「誤」「烏足」等否定判断，或指出某说不可从）
若为 adopt 或 reject，须写出被引/被驳的对象（人名、书名或「宋儒」这类泛称；注文中未明指则填 null）。
只输出 JSON：{"stance": "assert|adopt|reject", "source": "对象或 null", "why": "20字以内依据"}
```

The user message is assembled in `second_coder.py`: the canonical text, a ±350-character window of that layer's commentary around the term, the term, the gloss, and one instruction. Temperature 0 where the endpoint allows it; the two GPT-5 variants are reasoning models that reject `temperature`, and are marked in Table IV as run through their standard and search endpoints respectively.

## A.7 Relation to the paper

| Paper element | Prompt element |
|---|---|
| six fields of Section III-B | keys of the JSON object in A.1 |
| `gloss` ≤ 30 characters | rule 2 |
| `reject` conditional on a marker | rule 7, a superset of the gate's `neg()` set |
| `source` required for an edge | rules 5–6 and stance rule C |
| genre-conditioned stance rules | rules A–D |
| 50-character evidence window | rule 6 |
| two control layers held out | A.4 documents the layout, not the labels: neither layer's items entered prompt construction |
