#!/usr/bin/env bash
# Run one stage of a dataset against a running vLLM server: trials and the manipulation check at
# the same time (the check's slow tail then hides behind the trials), then that version's analysis.
#   STAGE=smoke bash infra/run_stage.sh                     # v2 smoke, 1 sample
#   STAGE=main SAMPLES=5 bash infra/run_stage.sh
# Env knobs: DATA (v2), STAGE (required: a split of the dataset), SAMPLES (1), MODEL_CFG
# (qwen3.6-27b-vllm), CONCURRENCY (256 for trials; the check uses a quarter), OUT.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

DATA="${DATA:-v2}"
STAGE="${STAGE:?set STAGE, e.g. smoke}"
SAMPLES="${SAMPLES:-1}"
MODEL_CFG="${MODEL_CFG:-qwen3.6-27b-vllm}"
CONCURRENCY="${CONCURRENCY:-256}"
OUT="${OUT:-outputs/${MODEL_CFG%-vllm}/$DATA/$STAGE}"
TAG="$DATA-$STAGE"

cd "$(dirname "$0")/.."
mkdir -p logs "$(dirname "$OUT")"
curl -sf localhost:8000/v1/models >/dev/null || { echo "!! no vLLM server on localhost:8000" >&2; exit 1; }
stamp() { echo ">> $(date -u +%H:%M:%S) $*"; }

stamp "$TAG: trials ($SAMPLES sample(s)) and check in parallel"
uv run cot-secret-file run --data "$DATA" --model "$MODEL_CFG" --split "$STAGE" --samples "$SAMPLES" \
  --concurrency "$CONCURRENCY" --out "$OUT" > "logs/$TAG-run.log" 2>&1 &
run=$!
uv run cot-secret-file check --data "$DATA" --model "$MODEL_CFG" --split "$STAGE" \
  --concurrency "$((CONCURRENCY / 4))" --out "$OUT-check" > "logs/$TAG-check.log" 2>&1 &
check=$!
status=0
wait "$run" || { echo "!! trials failed; see logs/$TAG-run.log" >&2; status=1; }
wait "$check" || { echo "!! check failed; see logs/$TAG-check.log" >&2; status=1; }
[ "$status" -eq 0 ] || exit 1
stamp "$TAG: done; analysis"
uv run python "scripts/secret_file/analysis/$DATA.py" "$OUT" --check "$OUT-check" | tee "logs/$TAG-analysis.txt"
