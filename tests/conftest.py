"""Pytest configuration — ensures project root is on sys.path."""
from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
