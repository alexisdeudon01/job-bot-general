#!/usr/bin/env bash
set -euo pipefail

echo "=== FETCH ==="
git fetch origin master --prune

echo
echo "=== BRANCHE COURANTE ==="
git branch --show-current

echo
echo "=== STATUS ==="
git status -sb

echo
echo "=== COMMITS LOCAL VS REMOTE ==="
COUNTS="$(git rev-list --left-right --count HEAD...origin/master)"
echo "$COUNTS"

echo
echo "=== HASHES ==="
echo "HEAD:          $(git rev-parse HEAD)"
echo "origin/master: $(git rev-parse origin/master)"

echo
echo "=== BRANCHES LOCALES ==="
git branch --list

echo
echo "=== BRANCHES REMOTE ==="
git branch -r

echo
echo "=== INTERPRETATION ==="
LEFT="$(echo "$COUNTS" | awk '{print $1}')"
RIGHT="$(echo "$COUNTS" | awk '{print $2}')"

if [ "$LEFT" = "0" ] && [ "$RIGHT" = "0" ]; then
  echo "OK: le repo local est synchronisé avec origin/master"
else
  echo "ATTENTION: le repo n'est pas synchronisé avec origin/master"
  echo "Commits seulement en local : $LEFT"
  echo "Commits seulement en remote : $RIGHT"
fi
