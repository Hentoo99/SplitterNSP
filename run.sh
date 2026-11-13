#!/bin/bash
# Doppio clic su macOS per avviare SplitterNSP (la prima volta installa PySide6).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Prima installazione: preparo l'ambiente Python…"
  python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt || exit 1
fi
exec .venv/bin/python -m splitter_nsp "$@"
