#!/usr/bin/env python3
"""Thin entry point: adds the plugin's lib/ to sys.path and runs the packloom CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from packloom.cli import main  # noqa: E402

main()
