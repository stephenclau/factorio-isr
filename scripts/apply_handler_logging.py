#!/usr/bin/env python3
"""
Automatically apply handler entry logging to all 25 command handlers.

Usage:
    python scripts/apply_handler_logging.py
    git diff src/bot/commands/command_handlers.py  # Review changes
    git add src/bot/commands/command_handlers.py
    git commit -m "🔍 Add handler entry logging across all 25 command handlers"
"""

import re
from pathlib import Path
from typing import Tuple


HANDLERS = [
    ("StatusCommandHandler", None),
    ("PlayersCommandHandler", None),
    ("VersionCommandHandler", None),
    ("SeedCommandHandler", None),
    ("EvolutionCommandHandler", None),
    ("AdminsCommandHandler", None),
    ("HealthCommandHandler", None),
    ("KickCommandHandler", "player"),
    ("BanCommandHandler", "player"),
    ("UnbanCommandHandler", "player"),
    ("MuteCommandHandler", "player"),
    ("UnmuteCommandHandler", "player"),
    ("PromoteCommandHandler", "player"),
    ("DemoteCommandHandler", "player"),
    ("SaveCommandHandler", None),
    ("BroadcastCommandHandler", None),
    ("WhisperCommandHandler", "player"),
    ("WhitelistCommandHandler", "action"),
    ("ClockCommandHandler", None),
    ("SpeedCommandHandler", "speed"),
    ("ResearchCommandHandler", "force"),
    ("RconCommandHandler", None),
    ("HelpCommandHandler", None),
    ("ServersCommandHandler", None),
    ("ConnectCommandHandler", "server"),
]


def generate_log_statement(handler_name: str, extra_param: str | None) -> str:
    """Generate logger.info statement for handler."""
    if extra_param:
        return f'logger.info("handler_invoked", handler="{handler_name}", user=interaction.user.name, {extra_param}={extra_param})'
    else:
        return f'logger.info("handler_invoked", handler="{handler_name}", user=interaction.user.name)'


def patch_handler(content: str, handler_name: str, extra_param: str | None) -> Tuple[str, bool]:
    """Patch a single handler with entry logging.
    
    Returns (modified_content, was_modified)
    """
    # Pattern to match the execute method and its docstring
    # Matches: async def execute(...) -> CommandResult:
    #              \"\"\"Execute ... command.\"\"\"
    pattern = (
        f"(class {handler_name}.*?" +
        r"async def execute\(.*?\) -> CommandResult:\s*" +
        r'\"\"\"[^\"]*\"\"\")(\s*)'
    )
    
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return content, False
    
    log_stmt = generate_log_statement(handler_name, extra_param)
    docstring_end = match.end(1)
    whitespace = match.group(2)
    
    # Replace with docstring + log statement
    replacement = (
        match.group(1) + 
        "\n        " + log_stmt + 
        whitespace
    )
    
    new_content = (
        content[:docstring_end] +
        "\n        " + log_stmt +
        content[docstring_end:]
    )
    
    # Verify it worked by checking if we added the log statement
    if log_stmt not in new_content:
        # Try alternative pattern
        alt_pattern = (
            f"class {handler_name}[^{{]*\{{.*?" +
            r"async def execute\([^)]*\) -> CommandResult:\n" +
            r'\s*\"\"\"[^\"]*\"\"\"'
        )
        alt_match = re.search(alt_pattern, content, re.DOTALL)
        if alt_match:
            # Insert after docstring
            insert_pos = alt_match.end()
            new_content = (
                content[:insert_pos] +
                "\n        " + log_stmt +
                content[insert_pos:]
            )
            return new_content, True
        return content, False
    
    return new_content, True


def main():
    """Apply handler logging to all handlers."""
    file_path = Path("src/bot/commands/command_handlers.py")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return 1
    
    print(f"📖 Reading {file_path}...")
    content = file_path.read_text()
    
    modified_count = 0
    skipped_handlers = []
    
    for handler_name, extra_param in HANDLERS:
        print(f"  ➜ Patching {handler_name}...", end=" ")
        
        new_content, was_modified = patch_handler(content, handler_name, extra_param)
        
        if was_modified:
            content = new_content
            modified_count += 1
            print("✓")
        else:
            print("⊘ (already patched or not found)")
            skipped_handlers.append(handler_name)
    
    if modified_count == 0:
        print(f"\n⚠️  No handlers were modified. They may already have entry logging.")
        return 0
    
    print(f"\n✅ Modified {modified_count}/{len(HANDLERS)} handlers")
    
    if skipped_handlers:
        print(f"\n⊘  Skipped (already patched or not found):")
        for h in skipped_handlers:
            print(f"   - {h}")
    
    # Write back
    print(f"\n💾 Writing changes to {file_path}...")
    file_path.write_text(content)
    
    print("\n✨ Done! Review changes with:")
    print("   git diff src/bot/commands/command_handlers.py")
    print("\nCommit with:")
    print('   git commit -m "🔍 Add handler entry logging across all 25 command handlers"')
    
    return 0


if __name__ == "__main__":
    exit(main())