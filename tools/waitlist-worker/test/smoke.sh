#!/usr/bin/env bash
# Smoke test against a running worker: smoke.sh <base-url>
# Needs ADMIN_TOKEN in the environment. Leaves the store with the test person deleted.
set -u
BASE="${1:?base url}"
ORIGIN="https://amgrobelnik.github.io"
BODY='{"name":"Test Entry","email":"test-entry@example.invalid","organisation":"test","build":"test","variant":"test"}'
fail=0
check() { if [ "$2" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1: got [${2:0:120}] want [$3]"; fail=1; fi; }

check "GET empty" "$(curl -s "$BASE/")" '{"count":0}'
post() { curl -s -H "Origin: $ORIGIN" -H "Content-Type: application/json" -d "$BODY" "$BASE/"; }
check "POST first" "$(post)" '{"ok":true,"count":1}'
check "POST again" "$(post)" '{"ok":true,"count":1}'
hdr=$(curl -s -D - -o /dev/null -H "Origin: $ORIGIN" -H "Content-Type: application/json" -d "$BODY" "$BASE/" | grep -ci '^access-control-allow-origin: https://amgrobelnik.github.io')
check "CORS allowed origin" "$hdr" "1"
for o in https://chipin.space https://www.chipin.space; do
  hdr=$(curl -s -D - -o /dev/null -H "Origin: $o" "$BASE/" | grep -ci "^access-control-allow-origin: $o")
  check "CORS allowed origin $o" "$hdr" "1"
done
hdr=$(curl -s -D - -o /dev/null -H "Origin: https://evil.example" -H "Content-Type: application/json" -d "$BODY" "$BASE/" | grep -ci '^access-control')
check "CORS other origin" "$hdr" "0"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Content-Type: application/json" -d '{"name":"X","email":"not-an-email"}' "$BASE/")
check "invalid email refused" "$code" "400"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/admin/export")
check "admin without token" "$code" "404"
rows=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin/export" | grep -c 'test-entry@example.invalid')
check "admin export has test person" "$rows" "1"
check "admin delete" "$(curl -s -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin/signup?email=Test-Entry@example.invalid")" '{"ok":true,"deleted":1,"count":0}'
check "GET empty again" "$(curl -s "$BASE/")" '{"count":0}'
exit $fail
