
from unittest.mock import MagicMock
from typing import Any
from datetime import datetime

import sys
from pathlib import Path

# Add src/ to Python path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
