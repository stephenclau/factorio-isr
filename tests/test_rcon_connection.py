"""Quick test to verify RCON connectivity."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from rcon_client import RconClient

async def test_connection():
    client = RconClient(
        host="lab.divebored.com",  # or "localhost" if testing locally
        port=27015,
        password="slau"
    )
    
    try:
        print("🔌 Connecting to RCON...")
        await client.connect()
        print("✅ Connected!")
        
        print("\n📊 Testing queries...")
        
        # Test player count
        count = await client.get_player_count()
        print(f"👥 Player count: {count}")
        
        # Test player list
        players = await client.get_players_online()
        print(f"📝 Online players: {players}")
        
        # Test server time
        time = await client.get_server_time()
        print(f"⏰ Server time: {time}")
        
        print("\n✅ All RCON queries successful!")
        # Debug what Factorio actually returns
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()
        print("🔌 Disconnected")


if __name__ == "__main__":
    asyncio.run(test_connection())

