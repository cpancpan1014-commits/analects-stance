# 训释对象词抽取 · 提示词规范 v2

> v1 → v2 的关键改动：新增 `stance`（立场）与 `source`（所引对象），
> 把「同词异释」的弱关联升级为「谁在哪个字上驳了谁」的直接论争边。
> v1 的缺陷：对《集解》《疏》这类汇编体裁误判「引述＝抄袭」，
> 且丢弃了反驳关系中的「反驳对象」，而这是全库最有价值的信息。

## 一、任务定义

给定**一章**《论语》原文与**一家**注文，输出该注家在本章中对原文词句所作的训释条目。
每条须标明：训释哪个词、给出什么训释、训释类型、**这是本人的主张还是引述/反驳**、**所引或所驳者是谁**。

## 二、输出格式（严格 JSON，无 markdown 围栏）

```json
{
  "chapter": "01-01",
  "annotator": "cho",
  "items": [
    {
      "term": "學",
      "gloss": "學先王之道也",
      "type": "義理",
      "stance": "assert",
      "source": null,
      "evidence": "單言「學」者，學先王之道也"
    },
    {
      "term": "學",
      "gloss": "效也；後覺效先覺",
      "type": "字義",
      "stance": "reject",
      "source": "朱熹",
      "evidence": "朱子以「效」訓「學」…豈可混乎"
    }
  ]
}
```

| 字段 | 约束 |
|---|---|
| `term` | 本章原文中实际出现的字词，1–4 字，繁体，照原文写法 |
| `gloss` | ≤30 字，保留注家自己的术语，**不得改写成现代汉语，不得替换成别家说法** |
| `type` | `字義`（训诂：某字＝某义）／`句意`（串讲整句）／`義理`（引申为哲学命题）／`名物`（人物、制度、器物之考证） |
| `stance` | `assert`＝本人立说／`adopt`＝引述并采纳他人成说／`reject`＝引述并否定之 |
| `source` | 所引或所驳者：人名，或书名（如 `王肅`、`包咸`、`鄭玄`、`程子`、`朱熹`、`仁齋`、`白虎通`）。`stance=assert` 时为 `null` |
| `evidence` | 逐字照录注文，≤30 字，须是支撑该条的最短片段 |

## 三、立场判定规则（v2 核心）

**A. 汇编体裁：引述即采纳。**
《论语集解》（何晏）与《论语注疏》（邢昺疏）的本质是汇集旧注。凡以「馬曰」「王曰」「包曰」「鄭玄云」「《白虎通》云」引出的成说，记为 `stance=adopt`，`source` 填所引者名。
不因“不是本人原创”而丢弃——在集解体例中，**选谁入注本身就是立场**。

**B. 自撰体裁：区分主张与批驳。**
《论语集注》（朱熹）、《论语古义》（仁斋）、《论语徵》（徂徕）以本人立说为主。
- 本人直接给出的训释 → `assert`
- 引程子、尹氏等而本人未置评 → `adopt`，`source` 填被引者
- 引某家之说而以「非也」「豈可混乎」「殊爲不知字義」「陋矣」「誤讀」等否定 → `reject`，`source` 填被驳者
- **关键**：`reject` 条目的 `gloss` 填**被驳者**的说法（即被否定掉的那个训释），不是反驳者自己的主张。反驳者自己的主张另立一条 `assert`。
  例：徂徕「朱子以『效』訓『學』…豈可混乎」→ 一条 `{term:學, gloss:"效也", stance:reject, source:朱熹}`；
  他本人的「學先王之道」→ 另一条 `{term:學, gloss:"學先王之道也", stance:assert, source:null}`。

**C. 同一注家可对同一 term 有多条**（assert + reject 并存），这是正常的，不要合并。

## 四、硬性禁止

1. **term 必须能在本章原文中找到**。查不到就不输出。
2. **禁止把「○注『馬曰子者』至『說懌』」这类范围标目当作条目**，也禁止把它用作 `evidence`。这是标出被疏注文的起止，不是训释。
3. **gloss 不得跨注家污染**。仁斋说「成德之稱」就不能写成朱熹的「成德之名」；一字之差也是错。
4. **注家未训的词不要补**。宁可少，不可编。
5. 原文繁体，`term`／`gloss`／`evidence` 一律照录繁体，不改简体。

## 五、已知陷阱

| 陷阱 | 表现 | 处理 |
|---|---|---|
| 反切 | `慍，紆問反` | 属字義，反切计入 gloss |
| 圈号分隔 | `◯` `○` | 仅作分条标记，不入任何字段 |
| 页眉残留 | `12論語古義論語徵` | 清洗阶段已删；若仍见，忽略 |
| 徂徕长段论辩 | 2,000 字以上，训释散落辩驳中 | 逐句扫；辩驳句优先判 reject |
| 邢昺疏双重结构 | 先「正義曰」串讲，再「○注…」逐注疏证 | 两段都要抽，后者抽实质训释而非标目 |

## 六、少样本（01-01 人工核校）

**何晏集解**（汇编体，全部 adopt）

```json
{"chapter":"01-01","annotator":"heyan","items":[
 {"term":"子","gloss":"男子之通稱，謂孔子","type":"名物","stance":"adopt","source":"馬融","evidence":"馬曰：子者，男子之通稱，謂孔子也"},
 {"term":"時","gloss":"學者以時誦習之","type":"字義","stance":"adopt","source":"王肅","evidence":"王曰：時者，學者以時誦習之"},
 {"term":"朋","gloss":"同門曰朋","type":"字義","stance":"adopt","source":"包咸","evidence":"包曰：同門曰朋"},
 {"term":"慍","gloss":"怒也","type":"字義","stance":"assert","source":null,"evidence":"慍，怒也。凡人有所不知，君子不怒"}
]}
```

**朱熹集注**

```json
{"chapter":"01-01","annotator":"zhuxi","items":[
 {"term":"學","gloss":"效也；後覺者效先覺之所為","type":"字義","stance":"assert","source":null,"evidence":"學之為言效也"},
 {"term":"習","gloss":"鳥數飛也；學之不已如鳥數飛","type":"字義","stance":"assert","source":null,"evidence":"習，鳥數飛也"},
 {"term":"說","gloss":"喜意也","type":"字義","stance":"assert","source":null,"evidence":"說，喜意也"},
 {"term":"朋","gloss":"同類也","type":"字義","stance":"assert","source":null,"evidence":"朋，同類也"},
 {"term":"慍","gloss":"含怒意","type":"字義","stance":"assert","source":null,"evidence":"慍，含怒意"},
 {"term":"君子","gloss":"成德之名","type":"字義","stance":"assert","source":null,"evidence":"君子，成德之名"}
]}
```

**荻生徂徕论语征**（assert 与 reject 并存）

```json
{"chapter":"01-01","annotator":"cho","items":[
 {"term":"學","gloss":"學先王之道也","type":"義理","stance":"assert","source":null,"evidence":"單言「學」者，學先王之道也"},
 {"term":"學","gloss":"效也（後覺效先覺）","type":"字義","stance":"reject","source":"朱熹","evidence":"朱子以「效」訓「學」…豈可混乎"},
 {"term":"學","gloss":"覺也（一旦豁然貫通）","type":"字義","stance":"reject","source":"宋儒","evidence":"又如訓「覺」，是其一旦豁然貫通之說"},
 {"term":"君子","gloss":"治民者之稱，包大夫以上","type":"名物","stance":"assert","source":null,"evidence":"君子，治民者之稱，包大夫以上"},
 {"term":"慍","gloss":"心有所怫鬱也（不必訓怒）","type":"字義","stance":"assert","source":null,"evidence":"愠，謂心有所怫鬱也"},
 {"term":"慍","gloss":"含怒意","type":"字義","stance":"reject","source":"朱熹","evidence":"「愠」訓「含怒」意，亦至於《南風》「解愠」而窮矣"}
]}
```

注意最后一例：徂徕对朱熹「慍，含怒意」的否定，被单独立为一条 reject。这条边比任何词频统计都硬——它明确记录了**谁在哪个字上驳了谁**。
