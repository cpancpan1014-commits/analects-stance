#!/usr/bin/env bash
# Rebuild everything that can be rebuilt without an API key, then verify.
set -e
cd "$(dirname "$0")"

python3 scripts/build_release_corpus.py
python3 scripts/build_network.py --all-seven --out network7.json
python3 scripts/concept_divergence.py
python3 scripts/threshold_sweep.py
python3 scripts/table2_targets.py
python3 scripts/make_fig_dispute.py
python3 scripts/gold_metrics.py
python3 scripts/cross_family.py
python3 scripts/second_coder.py report     # reuses the cached blind judgements in out/
python3 scripts/verify.py
