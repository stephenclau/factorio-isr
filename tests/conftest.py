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



from unittest.mock import MagicMock
from typing import Any
from datetime import datetime

import sys
from pathlib import Path

# Add src/ to Python path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
