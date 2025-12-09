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



"""Quick integration test for bot mode."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "src")

from config import load_config
from discord_interface import DiscordInterfaceFactory
from event_parser import FactorioEvent, EventType

async def main():
    config = load_config()
    
    print(f"✅ Config loaded")
    print(f"   Bot mode: {config.discord_bot_token is not None}")
    print(f"   Webhook mode: {config.discord_webhook_url is not None}")
    
    # Create Discord interface
    discord = DiscordInterfaceFactory.create_interface(config)
    print(f"✅ Discord interface created: {type(discord).__name__}")
    
    # Connect
    print("🤖 Connecting...")
    await discord.connect()
    print(f"✅ Connected: {discord.is_connected}")
    
    # Test sending an event
    if discord.is_connected:
        test_event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            raw_line="TestPlayer joined the game",
            emoji="👋",
            formatted_message="TestPlayer joined the server",
        )
        
        print("📤 Sending test event...")
        success = await discord.send_event(test_event)
        print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Keep running briefly
    await asyncio.sleep(3)
    
    # Disconnect
    print("🔌 Disconnecting...")
    await discord.disconnect()
    print("✅ Test complete")

if __name__ == "__main__":
    asyncio.run(main())
