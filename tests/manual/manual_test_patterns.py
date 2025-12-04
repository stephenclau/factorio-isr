#!/usr/bin/env python3
"""
Interactive pattern testing script.
Tests real Factorio log lines against your patterns.
"""

from pathlib import Path
import sys

import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from event_parser import EventParser, FactorioEventFormatter

# Sample Factorio log lines
TEST_LINES = [
    # Join/Leave
    "2025-11-14 15:53:25 [JOIN] Alice joined the game",
    "2025-11-14 15:53:25 [LEAVE] Bob left the game",
    
    # Chat
    "2025-11-11 01:12:09 [CHAT] Charlie: Hello everyone!",
    "2025-11-11 01:12:10 [CHAT] Dave: Anyone building a mall?",
    
    # Deaths
    "2025-11-11 01:12:09 Eve was killed by a small biter.",
    "2025-11-11 01:12:09 Frank was killed by a locomotive.",
    "2025-11-11 01:12:09 Grace was killed by their own gun turret.",
    "Ivan committed suicide.",
    
    # Research
    "[RESEARCH] Started researching Advanced electronics.",
    "[RESEARCH] Finished researching Advanced electronics.",
    
    # Achievements
    "[ACHIEVEMENT] Jack earned Iron throne 1.",
    "Kate launched a rocket!",
    
    # Server
    "[SERVER] Server started.",
    "[SERVER] Server restart in 5 minutes",
    "[ERROR] Something went wrong",
    "[WARNING] Low power in electrical network",
    
    # Non-matching lines
    "2025-11-30 17:44:59 Random debug output",
    "2025-11-30 17:44:59 [INFO] Some internal log",
]


def main():
    """Run pattern tests."""
    print("=" * 70)
    print("FACTORIO EVENT PATTERN TESTER")
    print("=" * 70)
    
    # Initialize parser with patterns directory
    patterns_dir = Path("patterns")
    if not patterns_dir.exists():
        print(f"❌ Error: {patterns_dir} directory not found!")
        return 1
    
    print(f"\n📂 Loading patterns from: {patterns_dir}")
    parser = EventParser(patterns_dir=patterns_dir)
    print(f"✅ Loaded {len(parser.compiled_patterns)} patterns\n")
    
    #Debug: List loaded patterns
    print("=" * 70)
    print("Pattern File Drilldown")
    print("=" * 70)
    import yaml

    patterns_dir = Path('patterns')

    for yaml_file in sorted(patterns_dir.glob('*.yml')) + sorted(patterns_dir.glob('*.yaml')):
        print(f"\n{'='*70}")
        print(f"File: {yaml_file.name}")
        print('='*70)
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                print("❌ File is empty or contains only comments")
                continue
                
            if not isinstance(data, dict):
                print(f"❌ Root is not dict: {type(data)}")
                continue
                
            if 'events' not in data:
                print(f"❌ No 'events' key found")
                print(f"   Available keys: {list(data.keys())}")
                continue
                
            if not isinstance(data['events'], dict):
                print(f"❌ 'events' is not dict: {type(data['events'])}")
                continue
                
            events_count = len(data['events'])
            print(f"✅ Valid structure with {events_count} events")
            print(f"   Event names: {list(data['events'].keys())}")
            
        except Exception as e:
            print(f"❌ Error loading file: {e}")
    
    
    # Test each line
    matched = 0
    unmatched = 0
    
    for line in TEST_LINES:
        print(f"\n📝 Testing: {line[:60]}...")
        event = parser.parse_line(line)
        
        if event:
            matched += 1
            discord_msg = FactorioEventFormatter.format_for_discord(event)
            print(f"   ✅ Match: {event.event_type.value}")
            print(f"   🎨 Emoji: {event.emoji}")
            print(f"   💬 Discord: {discord_msg}")
            if event.player_name:
                print(f"   👤 Player: {event.player_name}")
            if event.message:
                print(f"   📨 Message: {event.message}")
        else:
            unmatched += 1
            print(f"   ❌ No match")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"SUMMARY: {matched} matched, {unmatched} unmatched")
    print("=" * 70)  
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
