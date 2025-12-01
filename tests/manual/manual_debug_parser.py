"""Debug LEAVE event parsing."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from event_parser import EventParser


def debug_leave_events():
    """Debug LEAVE event parsing."""
    parser = EventParser()
    
    test_cases = [
        "2024-11-28 15:30:45 [LEAVE] PlayerOne left the game",
        "[LEAVE] PlayerTwo leaving",
        "PlayerThree left the game",
    ]
    
    for line in test_cases:
        print(f"\nTesting: {line}")
        event = parser.parse_line(line)
        
        if event is None:
            print(f"  ❌ Failed to parse (returned None)")
        else:
            print(f"  ✓ Type: {event.event_type}")
            print(f"  ✓ Player: {event.player_name}")


if __name__ == "__main__":
    debug_leave_events()
