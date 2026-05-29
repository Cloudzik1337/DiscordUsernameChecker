#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/pyinstaller \
    --onefile \
    --name CloudChecker \
    --add-data "showcase.gif:." \
    --hidden-import config \
    --hidden-import proxy \
    --hidden-import engine \
    --hidden-import ui \
    --hidden-import wizard \
    --hidden-import aiohttp \
    --hidden-import rich \
    checker.py

echo ""
echo "✅ Build done: dist/CloudChecker"
ls -lh dist/CloudChecker
