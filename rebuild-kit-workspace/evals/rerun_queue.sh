#!/bin/sh
# Re-run the iteration-3 arms whose first attempt died on "API Error: Connection
# closed mid-response". Those arms lost real work, not just their closing report
# (eval-0 with_skill reached 94 turns but shipped no backlog or harness), so
# grading them would understate the skill rather than measure it.
#
# Eight concurrent heavy sessions is what caused the drops, so this runs at most
# two at a time and waits for the in-flight eval-3 pair first.
set -u
cd "$(dirname "$0")/isolation"
LOGS=/tmp/rk-iter3-logs
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

# Wait out the eval-3 pair already in flight.
while [ "$(pgrep -f 'run_arm\.py --eval 3' | wc -l | tr -d ' ')" != "0" ]; do sleep 30; done
echo "eval-3 pair done; starting reruns"

run_pair() {
  for spec in "$@"; do
    e=$(echo "$spec" | cut -d: -f1)
    c=$(echo "$spec" | cut -d: -f2)
    python3 run_arm.py --eval "$e" --config "$c" --iteration iteration-3 \
      --model sonnet --timeout 7200 > "$LOGS/eval${e}-${c}.log" 2>&1 &
  done
  wait
}

run_pair 0:with_skill 0:without_skill
echo "eval-0 pair done"
run_pair 2:with_skill
echo "eval-2 with_skill done"
echo "RERUNS COMPLETE"
