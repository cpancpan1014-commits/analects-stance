# -*- coding: utf-8 -*-
"""Repository layout, resolved from this file so nothing is absolute.

Every script imports DATA / OUT / GOLD / FIG from here. If you move the
repository, nothing else changes.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"                 # released corpora, gold standard, prompts
GOLD = DATA / "gold"                 # human labels
PROMPTS = DATA / "prompts"           # prompt set (Appendix A)
RAW = DATA / "raw"                   # source HTML for the two control layers

OUT = ROOT / "out"                   # cached model output + derived results
FIG = ROOT / "figures"               # Figure 1, vector + raster

# Canonical file names. Scripts read these; do not rename one without the other.
CORPUS = DATA / "corpus_clean.jsonl"
CORPUS_LIU = DATA / "corpus_liu_zhengyi.jsonl"
CORPUS_HUOWEN = DATA / "corpus_huowen.jsonl"

TERMS_CORE = OUT / "terms_v3.jsonl"           # 5 core layers, 1,695 calls
TERMS_LIU = OUT / "terms_liu.jsonl"           # Zhengyi, 496 calls
TERMS_HUOWEN = OUT / "terms_huowen.jsonl"     # Questions, 455 calls

NETWORK7 = OUT / "network7.json"              # the graph the paper reports
GOLD_CSV = GOLD / "gold_40.csv"

LAYERS = ["heyan", "shu", "zhuxi", "kogi", "cho", "liu", "huowen"]
CORE_LAYERS = ["heyan", "shu", "zhuxi", "kogi", "cho"]

CN = {
    "heyan": "何晏集解", "shu": "邢昺疏", "zhuxi": "朱熹集注",
    "kogi": "伊藤仁斋论语古义", "cho": "荻生徂徕论语征",
    "liu": "刘宝楠论语正义", "huowen": "朱熹论语或问",
}
CN_SHORT = {"heyan": "何晏", "shu": "邢昺", "zhuxi": "朱熹", "kogi": "仁斋",
            "cho": "徂徕", "liu": "刘宝楠", "huowen": "朱熹或问"}

# The six chapters whose "Jinsai" layer carries Sorai's text (edition defect).
# The flag is stored in the corpus (`kogi_status`); this tuple is the fallback
# for a corpus that predates the flag.
CONTAM = ("04-16", "07-17", "08-15", "12-21", "12-22", "15-14")
