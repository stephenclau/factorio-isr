#!/bin/bash
set -e  # Exit on any error
python -c "
from pathlib import Path
from src.pattern_loader import PatternLoader

loader = PatternLoader(Path('patterns'))
count = loader.load_patterns()
print(f'Loaded {count} patterns')

for pattern in loader.get_patterns():
    print(f'  {pattern.name}: {pattern.event_type} (priority {pattern.priority})')
"