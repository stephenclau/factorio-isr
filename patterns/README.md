# Event Pattern Configurations

This directory will contain YAML files defining regex patterns for parsing Factorio events.

## Phase 2 Feature (Not Yet Implemented)

Currently, all event patterns are hard-coded in `src/event_parser.py`. In Phase 2, we'll migrate to YAML-based configuration for:

- **Easy customization** - Modify patterns without code changes
- **Mod support** - Add new mod event patterns via YAML
- **Community sharing** - Share pattern files with other users
- **Hot reload** - Update patterns without restarting

## Planned Files

- `vanilla.yml` - Core Factorio events (JOIN, LEAVE, CHAT, SERVER)
- `milestones.yml` - Milestones mod events
- `research.yml` - Research completion tracking
- `combat.yml` - Death events and combat tracking
- `custom.yml` - User-defined patterns

## Example Structure

events:
event_name:
pattern: "regex pattern here"
emoji: "🎮"
message: "Formatted message with {placeholders}"
enabled: true
priority: 10

## Status

⏳ **Placeholder** - Awaiting Phase 2 implementation

These patterns cover the most common Factorio events. You can enable/disable individual patterns in the YAML files and add custom patterns for modded servers!