"""
conftest.py — Shared fixtures for kingai_commie_flasher tests.
"""
import sys
from pathlib import Path

# Ensure the parent directory is on sys.path so we can import the main module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
