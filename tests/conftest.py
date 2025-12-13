# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Pytest configuration for real command harness tests.

This module provides:
- Async test markers
- Session-level fixtures for mocking
- Teardown for cooldown resets
- Real command invocation harness
"""

from unittest.mock import MagicMock
from typing import Any, Generator
from datetime import datetime
import sys
from pathlib import Path
import asyncio
import pytest

# Add src/ to Python path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

pytest_plugins = ['pytest_asyncio']


def pytest_configure(config):
    """Configure pytest with async support."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
