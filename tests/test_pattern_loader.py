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
# EventPattern Tests
# ============================================================================

class TestEventPattern:
    """Test EventPattern class."""
    
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
    
    def test_repr(self):
        """Test EventPattern string representation."""
        pattern = EventPattern(
            name="test",
            pattern=r"test",
            event_type="chat",
            priority=15,
            enabled=False
        )
        
        repr_str = repr(pattern)
        
        assert "test" in repr_str
        assert "chat" in repr_str
        assert "False" in repr_str
        assert "15" in repr_str
    
    # Type assertion tests
    def test_name_must_be_string(self):
        """Test that name must be a string."""
        with pytest.raises(AssertionError, match="name must be str"):
            EventPattern(name=123, pattern="test", event_type="chat")  # type: ignore[arg-type]
    
    def test_pattern_must_be_string(self):
        """Test that pattern must be a string."""
        with pytest.raises(AssertionError, match="pattern must be str"):
            EventPattern(name="test", pattern=123, event_type="chat")  # type: ignore[arg-type]
    
    def test_event_type_must_be_string(self):
        """Test that event_type must be a string."""
        with pytest.raises(AssertionError, match="event_type must be str"):
            EventPattern(name="test", pattern="test", event_type=123)  # type: ignore[arg-type]
    
    def test_emoji_must_be_string(self):
        """Test that emoji must be a string."""
        with pytest.raises(AssertionError, match="emoji must be str"):
            EventPattern(name="test", pattern="test", event_type="chat", emoji=123)  # type: ignore[arg-type]
    
    def test_message_template_must_be_string(self):
        """Test that message_template must be a string."""
        with pytest.raises(AssertionError, match="message_template must be str"):
            EventPattern(name="test", pattern="test", event_type="chat", message_template=123)  # type: ignore[arg-type]
    
    def test_enabled_must_be_bool(self):
        """Test that enabled must be a boolean."""
        with pytest.raises(AssertionError, match="enabled must be bool"):
            EventPattern(name="test", pattern="test", event_type="chat", enabled="true")  # type: ignore[arg-type]
    
    def test_priority_must_be_int(self):
        """Test that priority must be an integer."""
        with pytest.raises(AssertionError, match="priority must be int"):
            EventPattern(name="test", pattern="test", event_type="chat", priority="10")  # type: ignore[arg-type]
    
    def test_channel_must_be_string_or_none(self):
        """Test that channel must be string or None."""
        with pytest.raises(AssertionError, match="channel must be None or str"):
            EventPattern(name="test", pattern="test", event_type="chat", channel=123)  # type: ignore[arg-type]
    
    # Value assertion tests
    def test_name_cannot_be_empty(self):
        """Test that name cannot be empty."""
        with pytest.raises(AssertionError, match="name cannot be empty"):
            EventPattern(name="", pattern="test", event_type="chat")
    
    def test_pattern_cannot_be_empty(self):
        """Test that pattern cannot be empty."""
        with pytest.raises(AssertionError, match="pattern cannot be empty"):
            EventPattern(name="test", pattern="", event_type="chat")
    
    def test_event_type_cannot_be_empty(self):
        """Test that event_type cannot be empty."""
        with pytest.raises(AssertionError, match="event_type cannot be empty"):
            EventPattern(name="test", pattern="test", event_type="")
    
    def test_priority_must_be_non_negative(self):
        """Test that priority must be non-negative."""
        with pytest.raises(AssertionError, match="priority must be non-negative"):
            EventPattern(name="test", pattern="test", event_type="chat", priority=-1)
    
    def test_priority_zero_is_valid(self):
        """Test that priority can be zero."""
        pattern = EventPattern(name="test", pattern="test", event_type="chat", priority=0)
        assert pattern.priority == 0


# ============================================================================
# PatternLoader Initialization Tests
# ============================================================================

class TestPatternLoaderInit:
    """Test PatternLoader initialization."""
    
    def test_init_with_default_path(self):
        """Test PatternLoader with default patterns directory."""
        loader = PatternLoader()
        
        assert loader.patterns_dir == Path("patterns")
        assert isinstance(loader.patterns, list)
        assert len(loader.patterns) == 0
        assert isinstance(loader._loaded_files, list)
        assert len(loader._loaded_files) == 0
    
    def test_init_with_custom_path(self, temp_patterns_dir):
        """Test PatternLoader with custom patterns directory."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        assert loader.patterns_dir == temp_patterns_dir
        assert isinstance(loader.patterns, list)
        assert len(loader.patterns) == 0
    
    def test_init_patterns_dir_must_be_path(self):
        """Test that patterns_dir must be a Path object."""
        with pytest.raises(AssertionError, match="patterns_dir must be Path"):
            PatternLoader(patterns_dir="not_a_path")  # type: ignore[arg-type]


# ============================================================================
# load_patterns() Tests
# ============================================================================

class TestLoadPatterns:
    """Test PatternLoader.load_patterns() method."""
    
    def test_load_all_yml_files(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading all .yml files from directory."""
        create_yaml_file("test1.yml", sample_pattern_yaml)
        create_yaml_file("test2.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        # Should load from both files (3 events each, but duplicate names)
        assert count >= 3
        assert len(loader._loaded_files) == 2
    
    def test_load_all_yaml_files(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading .yaml extension files."""
        create_yaml_file("test.yaml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count >= 1
        assert "test.yaml" in loader._loaded_files
    
    def test_load_specific_files(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading specific pattern files."""
        create_yaml_file("file1.yml", sample_pattern_yaml)
        create_yaml_file("file2.yml", sample_pattern_yaml)
        create_yaml_file("file3.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns(pattern_files=["file1.yml", "file3.yml"])
        
        # Should only load file1 and file3
        assert count >= 3
        assert len(loader._loaded_files) == 2
        assert "file1.yml" in loader._loaded_files
        assert "file3.yml" in loader._loaded_files
        assert "file2.yml" not in loader._loaded_files
    
    def test_load_nonexistent_directory(self, tmp_path):
        """Test loading from non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        
        loader = PatternLoader(patterns_dir=nonexistent)
        count = loader.load_patterns()
        
        assert count == 0
        assert len(loader.patterns) == 0
    
    def test_load_empty_directory(self, temp_patterns_dir):
        """Test loading from empty directory."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count == 0
        assert len(loader.patterns) == 0
    
    def test_load_nonexistent_file(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading with non-existent file in list."""
        create_yaml_file("exists.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns(pattern_files=["exists.yml", "missing.yml"])
        
        # Should load exists.yml, skip missing.yml
        assert count >= 1
        assert "exists.yml" in loader._loaded_files
        assert "missing.yml" not in loader._loaded_files
    
    def test_patterns_sorted_by_priority(self, temp_patterns_dir, create_yaml_file):
        """Test that patterns are sorted by priority."""
        yaml_data = {
            "events": {
                "high_priority": {
                    "pattern": "test",
                    "type": "test",
                    "priority": 1,
                },
                "low_priority": {
                    "pattern": "test",
                    "type": "test",
                    "priority": 100,
                },
                "medium_priority": {
                    "pattern": "test",
                    "type": "test",
                    "priority": 50,
                },
            }
        }
        create_yaml_file("priorities.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        # Verify sorted by priority
        assert len(loader.patterns) == 3
        priorities = [p.priority for p in loader.patterns]
        assert priorities == sorted(priorities)
        assert loader.patterns[0].name == "high_priority"
        assert loader.patterns[1].name == "medium_priority"
        assert loader.patterns[2].name == "low_priority"
    
    def test_pattern_files_must_be_list_or_none(self, temp_patterns_dir):
        """Test that pattern_files must be list or None."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        with pytest.raises(AssertionError, match="pattern_files must be None or list"):
            loader.load_patterns(pattern_files="not_a_list")  # type: ignore[arg-type]
    
    def test_pattern_files_elements_must_be_strings(self, temp_patterns_dir):
        """Test that all pattern_files elements must be strings."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        with pytest.raises(AssertionError, match="All pattern_files must be strings"):
            loader.load_patterns(pattern_files=["valid.yml", 123])  # type: ignore[list-item]


# ============================================================================
# _load_file() Tests
# ============================================================================

class TestLoadFile:
    """Test PatternLoader._load_file() method."""
    
    def test_load_valid_file(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test loading a valid YAML file."""
        yaml_file = create_yaml_file("valid.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 3
        assert len(loader.patterns) == 3
    
    def test_load_empty_yaml(self, temp_patterns_dir, create_yaml_file):
        """Test loading empty YAML file."""
        yaml_file = create_yaml_file("empty.yml", {})
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_load_yaml_with_null_content(self, temp_patterns_dir):
        """Test loading YAML file with null content."""
        yaml_file = temp_patterns_dir / "null.yml"
        yaml_file.write_text("")  # Empty file results in None from yaml.safe_load
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_load_yaml_root_not_dict(self, temp_patterns_dir, create_yaml_file):
        """Test loading YAML where root is not a dict."""
        yaml_file = temp_patterns_dir / "list_root.yml"
        with open(yaml_file, 'w') as f:
            yaml.dump(["item1", "item2"], f)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_load_yaml_missing_events_key(self, temp_patterns_dir, create_yaml_file):
        """Test loading YAML without 'events' key."""
        yaml_file = create_yaml_file("no_events.yml", {"other_key": "value"})
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_load_yaml_events_not_dict(self, temp_patterns_dir, create_yaml_file):
        """Test loading YAML where 'events' is not a dict."""
        yaml_file = create_yaml_file("events_list.yml", {"events": ["event1", "event2"]})
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_invalid_event_name_type(self, temp_patterns_dir):
        """Test loading YAML with non-string event name."""
        yaml_file = temp_patterns_dir / "invalid_name.yml"
        # YAML allows numeric keys
        with open(yaml_file, 'w') as f:
            f.write("events:\n  123:\n    pattern: 'test'\n    type: 'chat'\n")
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        # Should skip invalid event name
        assert count == 0
    
    def test_invalid_event_config_type(self, temp_patterns_dir):
        """Test loading YAML where event config is not a dict."""
        yaml_data = {
            "events": {
                "invalid_event": "not_a_dict"
            }
        }
        yaml_file = temp_patterns_dir / "invalid_config.yml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_data, f)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_missing_pattern_field(self, temp_patterns_dir, create_yaml_file):
        """Test loading event without required 'pattern' field."""
        yaml_data = {
            "events": {
                "no_pattern": {
                    "type": "chat",
                    "emoji": "💬",
                }
            }
        }
        yaml_file = create_yaml_file("no_pattern.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_pattern_not_string(self, temp_patterns_dir, create_yaml_file):
        """Test loading event with non-string pattern."""
        yaml_data = {
            "events": {
                "bad_pattern": {
                    "pattern": 123,  # Not a string
                    "type": "chat",
                }
            }
        }
        yaml_file = create_yaml_file("bad_pattern.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_type_not_string(self, temp_patterns_dir, create_yaml_file):
        """Test loading event with non-string type."""
        yaml_data = {
            "events": {
                "bad_type": {
                    "pattern": "test",
                    "type": 123,  # Not a string
                }
            }
        }
        yaml_file = create_yaml_file("bad_type.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 0
    
    def test_emoji_not_string_uses_default(self, temp_patterns_dir, create_yaml_file):
        """Test that non-string emoji falls back to default."""
        yaml_data = {
            "events": {
                "bad_emoji": {
                    "pattern": "test",
                    "type": "chat",
                    "emoji": 123,  # Not a string
                }
            }
        }
        yaml_file = create_yaml_file("bad_emoji.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        # Should load with default empty emoji
        assert count == 1
        assert loader.patterns[0].emoji == ""
    
    def test_message_not_string_uses_default(self, temp_patterns_dir, create_yaml_file):
        """Test that non-string message falls back to default."""
        yaml_data = {
            "events": {
                "bad_message": {
                    "pattern": "test",
                    "type": "chat",
                    "message": 123,  # Not a string
                }
            }
        }
        yaml_file = create_yaml_file("bad_message.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        # Should load with default message template
        assert count == 1
        assert loader.patterns[0].message_template == "{player}: {message}"
    
    def test_priority_not_int_uses_default(self, temp_patterns_dir, create_yaml_file):
        """Test that non-int priority falls back to default."""
        yaml_data = {
            "events": {
                "bad_priority": {
                    "pattern": "test",
                    "type": "chat",
                    "priority": "not_an_int",
                }
            }
        }
        yaml_file = create_yaml_file("bad_priority.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        # Should load with default priority
        assert count == 1
        assert loader.patterns[0].priority == 10
    
    def test_enabled_not_bool_uses_default(self, temp_patterns_dir, create_yaml_file):
        """Test that non-bool enabled falls back to default."""
        yaml_data = {
            "events": {
                "bad_enabled": {
                    "pattern": "test",
                    "type": "chat",
                    "enabled": "not_a_bool",
                }
            }
        }
        yaml_file = create_yaml_file("bad_enabled.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        # Should load with default enabled=True
        assert count == 1
        assert loader.patterns[0].enabled is True
    
    def test_channel_field_loaded(self, temp_patterns_dir, create_yaml_file):
        """Test that channel field is properly loaded."""
        yaml_data = {
            "events": {
                "with_channel": {
                    "pattern": "test",
                    "type": "chat",
                    "channel": "admin",
                }
            }
        }
        yaml_file = create_yaml_file("with_channel.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 1
        assert loader.patterns[0].channel == "admin"
    
    def test_channel_none_when_not_specified(self, temp_patterns_dir, create_yaml_file):
        """Test that channel is None when not specified."""
        yaml_data = {
            "events": {
                "no_channel": {
                    "pattern": "test",
                    "type": "chat",
                }
            }
        }
        yaml_file = create_yaml_file("no_channel.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 1
        assert loader.patterns[0].channel is None
    
    def test_duplicate_event_name_warning(self, temp_patterns_dir, create_yaml_file):
        yaml_data = {
            "events": {
                "duplicate": {
                    "pattern": "test1",
                    "type": "chat",
                },
                "duplicate": {  # second one in same file
                    "pattern": "test2",
                    "type": "chat",
                },
            }
        }
        yaml_file = create_yaml_file("duplicate.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)

        # Now that loader skips duplicates, only one should be loaded
        assert count == 1
        assert len(loader.patterns) == 1
        assert loader.patterns[0].name == "duplicate"

    
    def test_default_type_from_event_name(self, temp_patterns_dir, create_yaml_file):
        """Test that event type defaults to event name if not specified."""
        yaml_data = {
            "events": {
                "custom_event_name": {
                    "pattern": "test",
                    # No 'type' specified
                }
            }
        }
        yaml_file = create_yaml_file("default_type.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 1
        assert loader.patterns[0].event_type == "custom_event_name"
    
    def test_default_message_template(self, temp_patterns_dir, create_yaml_file):
        """Test default message template."""
        yaml_data = {
            "events": {
                "no_message": {
                    "pattern": "test",
                    "type": "chat",
                }
            }
        }
        yaml_file = create_yaml_file("default_msg.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 1
        assert loader.patterns[0].message_template == "{player}: {message}"
    
    def test_disabled_pattern_loaded_but_marked(self, temp_patterns_dir, create_yaml_file):
        """Test that disabled patterns are loaded but marked as disabled."""
        yaml_data = {
            "events": {
                "disabled_event": {
                    "pattern": "test",
                    "type": "chat",
                    "enabled": False,
                }
            }
        }
        yaml_file = create_yaml_file("disabled.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)
        
        assert count == 1
        assert loader.patterns[0].enabled is False


# ============================================================================
# get_patterns() Tests
# ============================================================================

class TestGetPatterns:
    """Test PatternLoader.get_patterns() method."""
    
    def test_get_all_patterns(self, temp_patterns_dir, create_yaml_file):
        """Test getting all patterns including disabled."""
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
        
        all_patterns = loader.get_patterns(enabled_only=False)
        
        assert len(all_patterns) == 3
    
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
    
    def test_get_patterns_default_is_enabled_only(self, temp_patterns_dir, create_yaml_file):
        """Test that default behavior returns only enabled patterns."""
        yaml_data = {
            "events": {
                "enabled": {"pattern": "test1", "type": "chat", "enabled": True},
                "disabled": {"pattern": "test2", "type": "chat", "enabled": False},
            }
        }
        create_yaml_file("mixed.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        patterns = loader.get_patterns()
        
        assert len(patterns) == 1
        assert patterns[0].enabled is True
    
    def test_get_patterns_returns_copy(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test that get_patterns returns a new list, not reference."""
        create_yaml_file("test.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        patterns1 = loader.get_patterns()
        patterns2 = loader.get_patterns()
        
        # Should be different list objects
        assert patterns1 is not patterns2
        # But contain same patterns
        assert len(patterns1) == len(patterns2)
    
    def test_get_patterns_enabled_only_must_be_bool(self, temp_patterns_dir):
        """Test that enabled_only must be boolean."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        with pytest.raises(AssertionError, match="enabled_only must be bool"):
            loader.get_patterns(enabled_only="true")  # type: ignore[arg-type]


# ============================================================================
# get_patterns_by_type() Tests
# ============================================================================

class TestGetPatternsByType:
    """Test PatternLoader.get_patterns_by_type() method."""
    
    def test_get_patterns_by_type(self, temp_patterns_dir, create_yaml_file):
        """Test getting patterns filtered by event type."""
        yaml_data = {
            "events": {
                "join1": {"pattern": "joined", "type": "join"},
                "join2": {"pattern": "entered", "type": "join"},
                "leave1": {"pattern": "left", "type": "leave"},
                "chat1": {"pattern": "chat", "type": "chat"},
            }
        }
        create_yaml_file("types.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        join_patterns = loader.get_patterns_by_type("join")
        
        assert len(join_patterns) == 2
        assert all(p.event_type == "join" for p in join_patterns)
    
    def test_get_patterns_by_type_only_enabled(self, temp_patterns_dir, create_yaml_file):
        """Test that get_patterns_by_type returns only enabled patterns."""
        yaml_data = {
            "events": {
                "chat1": {"pattern": "test1", "type": "chat", "enabled": True},
                "chat2": {"pattern": "test2", "type": "chat", "enabled": False},
                "chat3": {"pattern": "test3", "type": "chat", "enabled": True},
            }
        }
        create_yaml_file("chat.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        chat_patterns = loader.get_patterns_by_type("chat")
        
        assert len(chat_patterns) == 2
        assert all(p.enabled for p in chat_patterns)
    
    def test_get_patterns_by_type_no_matches(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test getting patterns by type with no matches."""
        create_yaml_file("test.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        patterns = loader.get_patterns_by_type("nonexistent_type")
        
        assert len(patterns) == 0
        assert isinstance(patterns, list)
    
    def test_get_patterns_by_type_must_be_string(self, temp_patterns_dir):
        """Test that event_type must be string."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        with pytest.raises(AssertionError, match="event_type must be str"):
            loader.get_patterns_by_type(123)  # type: ignore[arg-type]
    
    def test_get_patterns_by_type_cannot_be_empty(self, temp_patterns_dir):
        """Test that event_type cannot be empty."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        with pytest.raises(AssertionError, match="event_type cannot be empty"):
            loader.get_patterns_by_type("")


# ============================================================================
# reload() Tests
# ============================================================================

class TestReload:
    """Test PatternLoader.reload() method."""
    
    def test_reload_clears_and_reloads(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test that reload clears existing patterns and reloads."""
        yaml_file = create_yaml_file("initial.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        initial_count = loader.load_patterns()
        
        assert initial_count == 3
        
        # Add another file
        create_yaml_file("additional.yml", sample_pattern_yaml)
        
        # Reload
        reload_count = loader.reload()
        
        # Should have patterns from both files now
        assert reload_count >= 3
        assert len(loader.patterns) >= 3
    
    def test_reload_clears_loaded_files(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test that reload clears _loaded_files list."""
        create_yaml_file("test.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        loader.load_patterns()
        
        assert len(loader._loaded_files) > 0
        
        loader.reload()
        
        # _loaded_files should be repopulated
        assert len(loader._loaded_files) > 0
    
    def test_reload_with_removed_file(self, temp_patterns_dir, create_yaml_file, sample_pattern_yaml):
        """Test reload after removing a pattern file."""
        yaml_file = create_yaml_file("temp.yml", sample_pattern_yaml)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        initial_count = loader.load_patterns()
        
        assert initial_count == 3
        
        # Remove the file
        yaml_file.unlink()
        
        # Reload
        reload_count = loader.reload()
        
        # Should have no patterns now
        assert reload_count == 0
        assert len(loader.patterns) == 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow(self, temp_patterns_dir, create_yaml_file):
        """Test complete pattern loading workflow."""
        # Create multiple pattern files
        yaml1 = {
            "events": {
                "join": {"pattern": r"\[JOIN\]", "type": "join", "priority": 5},
                "leave": {"pattern": r"\[LEAVE\]", "type": "leave", "priority": 10},
            }
        }
        yaml2 = {
            "events": {
                "chat": {"pattern": r"\[CHAT\]", "type": "chat", "priority": 15, "channel": "chat"},
                "milestone": {"pattern": "achieved", "type": "milestone", "priority": 1},
            }
        }
        
        create_yaml_file("basic.yml", yaml1)
        create_yaml_file("advanced.yml", yaml2)
        
        # Load patterns
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count == 4
        
        # Verify sorting by priority
        assert loader.patterns[0].priority == 1  # milestone
        assert loader.patterns[1].priority == 5  # join
        assert loader.patterns[2].priority == 10  # leave
        assert loader.patterns[3].priority == 15  # chat
        
        # Get by type
        chat_patterns = loader.get_patterns_by_type("chat")
        assert len(chat_patterns) == 1
        assert chat_patterns[0].channel == "chat"
        
        # Get all enabled
        enabled = loader.get_patterns(enabled_only=True)
        assert len(enabled) == 4
    
    def test_mixed_valid_and_invalid_patterns(self, temp_patterns_dir, create_yaml_file):
        """Test loading file with mix of valid and invalid patterns."""
        yaml_data = {
            "events": {
                "valid1": {"pattern": "test1", "type": "chat"},
                "invalid_no_pattern": {"type": "chat"},  # Missing pattern
                "valid2": {"pattern": "test2", "type": "join"},
                "invalid_bad_type": {"pattern": "test3", "type": 123},  # Bad type
                "valid3": {"pattern": "test4", "type": "leave"},
            }
        }
        create_yaml_file("mixed.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        # Should load only valid patterns
        assert count == 3
        assert len(loader.patterns) == 3
        assert all(p.name in ["valid1", "valid2", "valid3"] for p in loader.patterns)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_high_priority(self, temp_patterns_dir, create_yaml_file):
        """Test pattern with very high priority number."""
        yaml_data = {
            "events": {
                "high_pri": {"pattern": "test", "type": "chat", "priority": 999999},
            }
        }
        create_yaml_file("high_pri.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count == 1
        assert loader.patterns[0].priority == 999999
    
    def test_zero_priority(self, temp_patterns_dir, create_yaml_file):
        """Test pattern with priority zero."""
        yaml_data = {
            "events": {
                "zero_pri": {"pattern": "test", "type": "chat", "priority": 0},
            }
        }
        create_yaml_file("zero_pri.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count == 1
        assert loader.patterns[0].priority == 0
    
    def test_unicode_in_pattern(self, temp_patterns_dir, create_yaml_file):
        """Test pattern with unicode characters."""
        yaml_data = {
            "events": {
                "unicode": {
                    "pattern": "玩家.*加入",
                    "type": "join",
                    "emoji": "🎮",
                    "message": "{player} 加入了服务器",
                },
            }
        }
        create_yaml_file("unicode.yml", yaml_data)
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()
        
        assert count == 1
        assert "玩家" in loader.patterns[0].pattern
        assert "🎮" in loader.patterns[0].emoji
    
    def test_very_long_pattern(self, temp_patterns_dir, create_yaml_file):
        long_pattern = "x" * 501  # > MAX_PATTERN_LENGTH
        yaml_data = {
            "events": {
                "too_long": {
                    "pattern": long_pattern,
                    "type": "chat",
                }
            }
        }
        yaml_file = create_yaml_file("too_long.yml", yaml_data)
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader._load_file(yaml_file)

        # With security hardening, this should now be rejected
        assert count == 0
        assert len(loader.patterns) == 0
    
    def test_empty_patterns_list(self, temp_patterns_dir):
        """Test get_patterns on empty loader."""
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        patterns = loader.get_patterns()
        
        assert isinstance(patterns, list)
        assert len(patterns) == 0
    
    def test_malformed_yaml_syntax(self, temp_patterns_dir):
        """Test loading file with malformed YAML syntax."""
        yaml_file = temp_patterns_dir / "malformed.yml"
        # Create truly malformed YAML
        yaml_file.write_text("events:\n  bad:\n    - invalid: [\n")
        
        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        
        # Should raise YAML parsing error
        with pytest.raises(yaml.YAMLError):
            loader._load_file(yaml_file)


# ============================================================================
# Code Security
# ============================================================================

def test_pattern_too_long():
    """Pattern exceeding MAX_PATTERN_LENGTH should be rejected."""
    with pytest.raises(AssertionError, match="pattern too long"):
        EventPattern(name="test", pattern="x" * 501, event_type="test")

def test_invalid_template_placeholder():
    """Templates with non-whitelisted placeholders should be rejected."""
    with pytest.raises(AssertionError, match="disallowed placeholders"):
        EventPattern(
            name="test",
            pattern=".*",
            event_type="test",
            message_template="{player} {__import__}"
        )

def test_yaml_key_injection():
    """YAML with unexpected keys should be rejected."""
    # Create test YAML with 'handler: evil.py'
    # Assert it's logged and skipped

def test_file_too_large():
    """Files exceeding MAX_FILE_SIZE_BYTES should be rejected."""
    # Create 2MB YAML file
    # Assert load_patterns returns 0 and logs error
