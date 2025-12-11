#!/usr/bin/env python3
"""Smoke test for factorio command group registry.

Verifies that:
1. All imports are successful
2. Bot initializes with modular components
3. Factorio command group is registered
4. All 17 subcommands are present

Usage:
    python tests/smoke_test_factorio_commands.py
"""

import sys
import asyncio
from typing import Optional

try:
    from src.discord_bot_refactored import DiscordBot, DiscordBotFactory
    from src.bot import UserContextManager, RconMonitor, EventHandler, PresenceManager
    from src.bot.commands import register_factorio_commands
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Expected command structure
EXPECTED_COMMANDS = {
    # Multi-server (2)
    "servers",
    "connect",
    # Server information (7)
    "status",
    "players",
    "version",
    "seed",
    "evolution",
    "admins",
    "health",
    # Player management (7)
    "kick",
    "ban",
    "unban",
    "mute",
    "unmute",
    "promote",
    "demote",
    # Server management (4)
    "save",
    "broadcast",
    "whisper",
    "whitelist",
    # Game control (3)
    "time",
    "speed",
    "research",
    # Advanced (2)
    "rcon",
    "help",
}


def test_bot_creation() -> Optional[DiscordBot]:
    """Test bot creation with modular components."""
    try:
        bot = DiscordBotFactory.create_bot(token="test_token_smoke_test")
        print("✅ Bot creation successful")
        return bot
    except Exception as e:
        print(f"❌ Bot creation failed: {e}")
        return None


def test_modular_components(bot: DiscordBot) -> bool:
    """Test that all modular components are initialized."""
    checks = [
        ("UserContextManager", bot.user_context is not None),
        ("RconMonitor", bot.rcon_monitor is not None),
        ("EventHandler", bot.event_handler is not None),
        ("PresenceManager", bot.presence_manager is not None),
    ]

    all_ok = True
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {name}: {result}")
        all_ok = all_ok and result

    return all_ok


def test_factorio_command_registration(bot: DiscordBot) -> bool:
    """Test that factorio commands are properly registered."""
    print("\n📋 Testing factorio command group registration...")

    # Call setup_hook to trigger command registration
    try:
        # setup_hook is async, so we run it
        asyncio.run(bot.setup_hook())
        print("✅ setup_hook() executed successfully")
    except Exception as e:
        print(f"❌ setup_hook() failed: {e}")
        return False

    # Get the factorio command group from the tree
    factorio_group = None
    for command in bot.tree.get_commands():
        if command.name == "factorio":
            factorio_group = command
            break

    if factorio_group is None:
        print("❌ Factorio command group not found in command tree")
        return False

    print(f"✅ Factorio command group found: {factorio_group.name}")

    # Check subcommands
    if not hasattr(factorio_group, "commands"):
        print("❌ Factorio group has no 'commands' attribute")
        return False

    registered_commands = {cmd.name for cmd in factorio_group.commands}
    print(f"\n📊 Registered {len(registered_commands)} subcommands:")

    all_ok = True
    for cmd_name in sorted(EXPECTED_COMMANDS):
        if cmd_name in registered_commands:
            print(f"  ✅ /{cmd_name}")
        else:
            print(f"  ❌ /{cmd_name} MISSING")
            all_ok = False

    # Check for unexpected commands
    unexpected = registered_commands - EXPECTED_COMMANDS
    if unexpected:
        print(f"\n⚠️  Unexpected commands found: {unexpected}")
        all_ok = False

    missing = EXPECTED_COMMANDS - registered_commands
    if missing:
        print(f"\n❌ Missing commands: {missing}")
        all_ok = False
    else:
        print(f"\n✅ All {len(EXPECTED_COMMANDS)} expected commands registered")

    return all_ok


def main() -> int:
    """Run all smoke tests."""
    print("="*60)
    print("🔬 SMOKE TEST: Factorio Command Group Registry")
    print("="*60)

    # Test bot creation
    print("\n1️⃣ Testing bot creation...")
    bot = test_bot_creation()
    if bot is None:
        return 1

    # Test modular components
    print("\n2️⃣ Testing modular components...")
    if not test_modular_components(bot):
        return 1

    # Test factorio command registration
    print("\n3️⃣ Testing factorio command registration...")
    if not test_factorio_command_registration(bot):
        return 1

    print("\n" + "="*60)
    print("✅ ALL SMOKE TESTS PASSED")
    print("="*60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
