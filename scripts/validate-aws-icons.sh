#!/usr/bin/env bash
# validate-aws-icons.sh — Test AWS PlantUML icon paths against v20.0
#
# Usage:
#   ./validate-aws-icons.sh                        # test all ~800 icons
#   ./validate-aws-icons.sh Analytics              # test one category
#   ./validate-aws-icons.sh check Compute/Lambda.puml  # test a single path

set -uo pipefail

BASE="https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist"
API="https://api.github.com/repos/awslabs/aws-icons-for-plantuml/git/trees/v20.0?recursive=1"

# ── Single path check ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "check" && -n "${2:-}" ]]; then
  path="$2"
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$path")
  if [[ "$code" == "200" ]]; then
    echo "✅ 200  $path"
  else
    echo "❌ $code  $path"
  fi
  exit 0
fi

# ── Fetch icon list from GitHub API ───────────────────────────────────────────
echo "Fetching icon list from GitHub..."
icons=$(curl -s "$API" | python3 -c "
import json, sys
tree = json.load(sys.stdin).get('tree', [])
skip = {'AWSCommon', 'AWSC4', 'AWSRaw', 'AWSSimplified', 'AWSExperimental'}
paths = []
for f in tree:
    p = f['path']
    if not p.startswith('dist/') or not p.endswith('.puml'):
        continue
    if any(s in p for s in skip):
        continue
    paths.append(p.replace('dist/', '', 1))
print('\n'.join(paths))
")

# ── Optional category filter ───────────────────────────────────────────────────
FILTER="${1:-}"
if [[ -n "$FILTER" ]]; then
  icons=$(echo "$icons" | grep -i "^${FILTER}/")
fi

total=$(echo "$icons" | grep -c '.' || true)
echo "Testing $total icons..."
echo ""

pass=0
fail=0
failed_paths=()

while IFS= read -r path; do
  [[ -z "$path" ]] && continue
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$path")
  if [[ "$code" == "200" ]]; then
    ((pass++))
  else
    ((fail++))
    failed_paths+=("$code  $path")
    echo "❌ $code  $path"
  fi
done <<< "$icons"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════"
echo "✅ Passed: $pass"
echo "❌ Failed: $fail"
echo "════════════════════════════════"

if [[ ${#failed_paths[@]} -gt 0 ]]; then
  echo ""
  echo "All failed paths:"
  for p in "${failed_paths[@]}"; do
    echo "  $p"
  done
  exit 1
fi
