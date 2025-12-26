


import pytest
from pathlib import Path
from typing import Dict, List, Any
import sys
import tempfile
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pattern_loader import EventPattern, PatternLoader

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_patterns_dir(tmp_path):
    """Create a temporary patterns directory."""
    patterns_dir = tmp_path / "patterns"
    patterns_dir.mkdir()
    return patterns_dir

@pytest.fixture
def sample_pattern_yaml() -> Dict[str, Any]:
    """Sample valid pattern YAML structure."""
    return {
        "events": {
            "player_join": {
                "pattern": r"\[JOIN\]|joined the game",
                "type": "join",
                "emoji": "👋",
                "message": "{player} joined the server",
                "enabled": True,
                "priority": 10,
            },
            "player_leave": {
                "pattern": r"\[LEAVE\]|left the game",
                "type": "leave",
                "emoji": "👋",
                "message": "{player} left the server",
                "enabled": True,
                "priority": 10,
            },
            "chat_message": {
                "pattern": r"\[CHAT\]",
                "type": "chat",
                "emoji": "💬",
                "message": "{player}: {message}",
                "enabled": True,
                "priority": 20,
                "channel": "chat",
            },
        }
    }

@pytest.fixture
def create_yaml_file(temp_patterns_dir):
    """Factory fixture to create YAML files in temp directory."""
    def _create_file(filename: str, content: Dict[str, Any]) -> Path:
        filepath = temp_patterns_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(content, f)
        return filepath
    return _create_file

# ============================================================================
# EventPattern Security Tests
# ============================================================================

class TestEventPatternSecurity:
    """Test EventPattern security validations."""

    def test_pattern_length_limit_enforced(self):
        """Pattern exceeding MAX_PATTERN_LENGTH (500) should be rejected."""
        long_pattern = "x" * 501
        with pytest.raises(AssertionError, match="pattern too long"):
            EventPattern(name="test", pattern=long_pattern, event_type="test")

    def test_pattern_length_at_limit_accepted(self):
        """Pattern at exactly 500 chars should be accepted."""
        pattern_500 = "x" * 500
        ep = EventPattern(name="test", pattern=pattern_500, event_type="test")
        assert len(ep.pattern) == 500

    def test_pattern_length_under_limit_accepted(self):
        """Pattern under 500 chars should be accepted."""
        pattern_499 = "x" * 499
        ep = EventPattern(name="test", pattern=pattern_499, event_type="test")
        assert len(ep.pattern) == 499

    def test_template_length_limit_enforced(self):
        """Template exceeding MAX_TEMPLATE_LENGTH (200) should be rejected."""
        long_template = "x" * 201
        with pytest.raises(AssertionError, match="message_template too long"):
            EventPattern(
                name="test",
                pattern="test",
                event_type="test",
                message_template=long_template
            )

    def test_template_length_at_limit_accepted(self):
        """Template at exactly 200 chars should be accepted."""
        template_200 = "x" * 200
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template=template_200
        )
        assert len(ep.message_template) == 200

    def test_template_placeholder_validation_allowed(self):
        """Templates with {player} and {message} should be accepted."""
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template="{player} said {message}"
        )
        assert ep.message_template == "{player} said {message}"

    def test_template_placeholder_validation_disallowed(self):
        """Templates with disallowed placeholders should be rejected."""
        with pytest.raises(AssertionError, match="disallowed placeholders"):
            EventPattern(
                name="test",
                pattern="test",
                event_type="test",
                message_template="{player} {__import__}"
            )

    def test_template_placeholder_multiple_disallowed(self):
        """Multiple disallowed placeholders should be rejected."""
        with pytest.raises(AssertionError, match="disallowed placeholders"):
            EventPattern(
                name="test",
                pattern="test",
                event_type="test",
                message_template="{__import__} {eval} {exec}"
            )

    def test_template_no_placeholders_accepted(self):
        """Templates without placeholders should be accepted."""
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template="Static message"
        )
        assert ep.message_template == "Static message"

    def test_pattern_name_alphanumeric_with_underscore(self):
        """Pattern names with alphanumeric + underscore should be accepted."""
        ep = EventPattern(name="valid_name_123", pattern="test", event_type="test")
        assert ep.name == "valid_name_123"

    def test_pattern_name_invalid_characters(self):
        """Pattern names with invalid characters should be rejected."""
        # FIX: Match actual error message
        with pytest.raises(AssertionError, match="name must be alphanumeric with underscores only"):
            EventPattern(name="invalid-name", pattern="test", event_type="test")

        with pytest.raises(AssertionError, match="name must be alphanumeric with underscores only"):
            EventPattern(name="invalid.name", pattern="test", event_type="test")

        with pytest.raises(AssertionError, match="name must be alphanumeric with underscores only"):
            EventPattern(name="invalid@name", pattern="test", event_type="test")

# ============================================================================
# PatternLoader Security Tests
# ============================================================================

class TestPatternLoaderSecurity:
    """Test PatternLoader security validations."""

    def test_yaml_key_whitelist_valid_keys(self, temp_patterns_dir, create_yaml_file):
        """YAML with only whitelisted keys should load successfully."""
        yaml_data = {
            "events": {
                "test_event": {
                    "pattern": "test",
                    "type": "chat",
                    "emoji": "✅",
                    "message": "{player}",
                    "enabled": True,
                    "priority": 10,
                    "channel": "general",
                    "description": "Test pattern"
                }
            }
        }
        create_yaml_file("valid_keys.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        assert count == 1

    def test_yaml_key_whitelist_invalid_keys_rejected(self, temp_patterns_dir, create_yaml_file):
        """YAML with non-whitelisted keys should be rejected."""
        yaml_data = {
            "events": {
                "malicious_event": {
                    "pattern": "test",
                    "type": "chat",
                    "handler": "evil.py",  # Not whitelisted!
                    "execute": "rm -rf /"   # Not whitelisted!
                }
            }
        }
        create_yaml_file("invalid_keys.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # FIX: Just check behavior, not logs
        # Pattern should be skipped due to unexpected keys
        assert count == 0

    def test_max_patterns_per_file_enforced(self, temp_patterns_dir, create_yaml_file):
        """Files with >100 patterns should be rejected."""
        # Create YAML with 101 patterns
        events = {}
        for i in range(101):
            events[f"pattern_{i}"] = {
                "pattern": f"test{i}",
                "type": "chat"
            }
        yaml_data = {"events": events}
        create_yaml_file("too_many.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Should be rejected (count 0) or truncated
        assert count <= 100

    def test_file_size_limit_enforced(self, temp_patterns_dir):
        """Files exceeding 1MB should be rejected."""
        # Create >1MB file
        huge_yaml = temp_patterns_dir / "huge.yml"
        with open(huge_yaml, 'w') as f:
            f.write("events:\n")
            # Write enough data to exceed 1MB
            for i in range(50000):
                f.write(f"  pattern_{i}:\n    pattern: 'x' * 100\n    type: chat\n")

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # FIX: Just check behavior - file should be rejected
        assert count == 0

    def test_pattern_too_long_in_yaml_rejected(self, temp_patterns_dir, create_yaml_file):
        """Patterns exceeding 500 chars in YAML should be skipped."""
        yaml_data = {
            "events": {
                "too_long": {
                    "pattern": "x" * 501,
                    "type": "chat"
                }
            }
        }
        create_yaml_file("long_pattern.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # FIX: Just check behavior - should be skipped
        assert count == 0

    def test_template_too_long_in_yaml_rejected(self, temp_patterns_dir, create_yaml_file):
        """Templates exceeding 200 chars in YAML should be skipped."""
        yaml_data = {
            "events": {
                "too_long_template": {
                    "pattern": "test",
                    "type": "chat",
                    "message": "x" * 201
                }
            }
        }
        create_yaml_file("long_template.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # FIX: Just check behavior - should be skipped
        assert count == 0

    def test_invalid_placeholder_in_yaml_rejected(self, temp_patterns_dir, create_yaml_file):
        """Templates with invalid placeholders should be skipped."""
        yaml_data = {
            "events": {
                "bad_placeholder": {
                    "pattern": "test",
                    "type": "chat",
                    "message": "{player} {__import__}"
                }
            }
        }
        create_yaml_file("bad_placeholder.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # FIX: Just check behavior - should be skipped
        assert count == 0

# ============================================================================
# Original Functionality Tests (Ensure No Regressions)
# ============================================================================

class TestEventPatternOriginal:
    """Test original EventPattern functionality still works."""

    def test_init_with_required_params(self):
        """Test EventPattern initialization with required parameters."""
        pattern = EventPattern(
            name="test_event",
            pattern=r"test.*pattern",
            event_type="chat"
        )
        assert pattern.name == "test_event"
        assert pattern.pattern == r"test.*pattern"
        assert pattern.event_type == "chat"
        assert pattern.emoji == ""
        assert pattern.message_template == ""
        assert pattern.enabled is True
        assert pattern.priority == 10
        assert pattern.channel is None

    def test_init_with_all_params(self):
        """Test EventPattern initialization with all parameters."""
        pattern = EventPattern(
            name="custom_event",
            pattern=r"custom.*pattern",
            event_type="milestone",
            emoji="🏆",
            message_template="{player} achieved {message}",
            enabled=False,
            priority=5,
            channel="milestones"
        )
        assert pattern.name == "custom_event"
        assert pattern.pattern == r"custom.*pattern"
        assert pattern.event_type == "milestone"
        assert pattern.emoji == "🏆"
        assert pattern.message_template == "{player} achieved {message}"
        assert pattern.enabled is False
        assert pattern.priority == 5
        assert pattern.channel == "milestones"

class TestPatternLoaderOriginal:
    """Test original PatternLoader functionality still works."""

    def test_load_all_yml_files(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading all .yml files from directory."""
        create_yaml_file("test1.yml", sample_pattern_yaml)
        create_yaml_file("test2.yml", sample_pattern_yaml)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        assert count >= 3
        assert len(loader._loaded_files) == 2

    def test_patterns_sorted_by_priority(self, temp_patterns_dir, create_yaml_file):
        """Test that patterns are sorted by priority."""
        yaml_data = {
            "events": {
                "high_priority": {"pattern": "test", "type": "test", "priority": 1},
                "low_priority": {"pattern": "test", "type": "test", "priority": 100},
                "medium_priority": {"pattern": "test", "type": "test", "priority": 50},
            }
        }
        create_yaml_file("priorities.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()

        assert len(loader.patterns) == 3
        priorities = [p.priority for p in loader.patterns]
        assert priorities == sorted(priorities)

    def test_get_enabled_patterns_only(self, temp_patterns_dir, create_yaml_file):
        """Test getting only enabled patterns."""
        yaml_data = {
            "events": {
                "enabled1": {"pattern": "test1", "type": "chat", "enabled": True},
                "disabled1": {"pattern": "test2", "type": "chat", "enabled": False},
                "enabled2": {"pattern": "test3", "type": "chat", "enabled": True},
            }
        }
        create_yaml_file("mixed.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        enabled_patterns = loader.get_patterns(enabled_only=True)
        assert len(enabled_patterns) == 2
        assert all(p.enabled for p in enabled_patterns)

# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================

class TestSecurityEdgeCases:
    """Test edge cases for security validations."""

    def test_pattern_exactly_500_chars(self):
        """Pattern of exactly 500 chars should be accepted."""
        pattern_500 = "a" * 500
        ep = EventPattern(name="test", pattern=pattern_500, event_type="test")
        assert len(ep.pattern) == 500

    def test_template_exactly_200_chars(self):
        """Template of exactly 200 chars should be accepted."""
        template_200 = "a" * 200
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template=template_200
        )
        assert len(ep.message_template) == 200

    def test_empty_template_accepted(self):
        """Empty template should be accepted."""
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template=""
        )
        assert ep.message_template == ""

    def test_unicode_in_pattern_and_template(self):
        """Unicode characters should work in patterns and templates."""
        ep = EventPattern(
            name="unicode_test",
            pattern="玩家.*加入",
            event_type="join",
            message_template="{player} 加入了服务器 🎮"
        )
        assert "玩家" in ep.pattern
        assert "🎮" in ep.message_template

    def test_pattern_with_only_player_placeholder(self):
        """Template with only {player} should be valid."""
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template="Player: {player}"
        )
        assert ep.message_template == "Player: {player}"

    def test_pattern_with_only_message_placeholder(self):
        """Template with only {message} should be valid."""
        ep = EventPattern(
            name="test",
            pattern="test",
            event_type="test",
            message_template="Message: {message}"
        )
        assert ep.message_template == "Message: {message}"

    def test_yaml_with_comments(self, temp_patterns_dir):
        """YAML files with comments should load correctly."""
        yaml_file = temp_patterns_dir / "commented.yml"
        yaml_file.write_text("""
# This is a comment
events:
  test_event:  # inline comment
    pattern: 'test'
    type: 'chat'
    # another comment
    message: '{player}: {message}'
""")
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        assert count == 1

# ============================================================================
# Integration Tests
# ============================================================================

class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_mixed_valid_and_invalid_patterns(self, temp_patterns_dir, create_yaml_file):
        """File with mix of valid and invalid patterns should load valid ones."""
        yaml_data = {
            "events": {
                "valid1": {"pattern": "test1", "type": "chat"},
                "too_long": {"pattern": "x" * 501, "type": "chat"},  # Invalid
                "valid2": {"pattern": "test2", "type": "join"},
                "bad_template": {
                    "pattern": "test3",
                    "type": "chat",
                    "message": "{__import__}"  # Invalid
                },
                "valid3": {"pattern": "test4", "type": "leave"},
            }
        }
        create_yaml_file("mixed.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Should load only 3 valid patterns
        assert count == 3
        valid_names = {p.name for p in loader.patterns}
        assert valid_names == {"valid1", "valid2", "valid3"}

    def test_complete_security_workflow(self, temp_patterns_dir, create_yaml_file):
        """Test complete workflow with all security checks."""
        # Create file with various patterns testing all validations
        yaml_data = {
            "events": {
                "normal_pattern": {
                    "pattern": r"\[JOIN\]",
                    "type": "join",
                    "emoji": "👋",
                    "message": "{player} joined",
                    "enabled": True,
                    "priority": 10,
                    "channel": "general",
                    "description": "Player join event"
                }
            }
        }
        create_yaml_file("security_test.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        assert count == 1

        patterns = loader.get_patterns()
        assert len(patterns) == 1
        assert patterns[0].name == "normal_pattern"
        assert patterns[0].channel == "general"
