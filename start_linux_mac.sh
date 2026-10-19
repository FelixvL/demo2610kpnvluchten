#!/usr/bin/env sh
set -e
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -r requirements.txt
if [ ! -f instance/vluchtwinkel.sqlite ]; then python seed.py; fi
python run.py
