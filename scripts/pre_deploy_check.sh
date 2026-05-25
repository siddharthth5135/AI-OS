#!/bin/bash
set -e
echo "=== Pre-Deployment Checks ==="

FAIL=0
check() {
  if eval "$2"; then
    echo "✓ $1"
  else
    echo "✗ FAIL: $1"
    FAIL=1
  fi
}

check "No print() statements" "! grep -rn 'print(' app/ --include='*.py' | grep -v '#' | grep -vE 'e2e_|verify_|gemini_client'"
check "No pdb imports" "! grep -rn 'import pdb' app/ --include='*.py'"
check "No hardcoded secrets" "! grep -rn \"api_key = '\" app/ --include='*.py'"
check ".env not in git" "! git ls-files .env | grep -q .env"
check "All requirements pinned" "! grep -E '^[a-zA-Z].*[^0-9]$' requirements.txt | grep -v '^#'"
check "Black formatting" "black --check app/ -q"
check "Import ordering" "isort --check app/ -q"

if [ $FAIL -eq 0 ]; then
  echo "=== ALL CHECKS PASSED - Ready to deploy ==="
else
  echo "=== CHECKS FAILED - Fix before deploying ==="
  exit 1
fi
