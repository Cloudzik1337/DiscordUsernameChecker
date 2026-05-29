#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python checker.py "$@"
