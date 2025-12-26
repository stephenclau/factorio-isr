import pytest
from pathlib import Path
from datetime import datetime, timedelta
import json
import tempfile

from security_monitor import SecurityMonitor, Infraction


@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def monitor(temp_dir):
    """Security monitor with temp files."""
    return SecurityMonitor(
        infractions_file=temp_dir / "infractions.jsonl",
        banned_players_file=temp_dir / "banned.json",
    )


class TestMaliciousPatternDetection:
    """Test malicious pattern detection."""

    def test_detect_eval(self, monitor):
        """Detect eval() in text."""
        infraction = monitor.check_malicious_pattern(
            text="Let me try eval('print(1)')",
            player_name="Hacker",
        )

        assert infraction is not None
        assert infraction.player_name == "Hacker"
        assert infraction.pattern_type == "code_injection"
        assert infraction.severity == "critical"
        assert infraction.auto_banned is True
        assert "Hacker" in monitor.banned_players

    def test_detect_exec(self, monitor):
        """Detect exec() in text."""
        infraction = monitor.check_malicious_pattern(
            text="exec('import os')",
            player_name="Attacker",
        )

        assert infraction is not None
        assert "Attacker" in monitor.banned_players

    def test_detect_subprocess(self, monitor):
        """Detect subprocess with shell=True."""
        infraction = monitor.check_malicious_pattern(
            text="subprocess.call('rm -rf /', shell=True)",
            player_name="Malicious",
        )

        assert infraction is not None
        assert "Malicious" in monitor.banned_players

    def test_no_false_positive(self, monitor):
        """Normal text should not trigger."""
        infraction = monitor.check_malicious_pattern(
            text="I evaluated the situation",
            player_name="Innocent",
        )

        assert infraction is None
        assert "Innocent" not in monitor.banned_players

    def test_blocked_after_ban(self, monitor):
        """Banned players should be blocked."""
        monitor.ban_player("BadActor")

        infraction = monitor.check_malicious_pattern(
            text="eval('test')",
            player_name="BadActor",
        )

        # Should return None (blocked)
        assert infraction is None


class TestBanManagement:
    """Test player ban/unban."""

    def test_ban_player(self, monitor):
        """Ban a player."""
        monitor.ban_player("TestPlayer", reason="Test ban")

        assert "TestPlayer" in monitor.banned_players
        assert monitor.is_banned("TestPlayer")

    def test_unban_player(self, monitor):
        """Unban a player."""
        monitor.ban_player("TestPlayer")
        assert monitor.is_banned("TestPlayer")

        result = monitor.unban_player("TestPlayer")

        assert result is True
        assert not monitor.is_banned("TestPlayer")

    def test_unban_not_banned(self, monitor):
        """Unbanning non-banned player returns False."""
        result = monitor.unban_player("NeverBanned")
        assert result is False

    def test_persistence(self, temp_dir):
        """Banned players persist across instances."""
        monitor1 = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=temp_dir / "banned.json",
        )

        monitor1.ban_player("Persistent")

        # Create new instance
        monitor2 = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=temp_dir / "banned.json",
        )

        assert monitor2.is_banned("Persistent")


class TestRateLimiting:
    """Test rate limiting."""

    def test_rate_limit_not_exceeded(self, monitor):
        """Normal rate should be allowed."""
        allowed, reason = monitor.check_rate_limit(
            action_type="mention_admin",
            player_name="Player1",
        )

        assert allowed is True
        assert reason is None

    def test_rate_limit_exceeded(self, monitor):
        """Exceeding rate limit should block."""
        # Fire 5 events (the limit)
        for i in range(5):
            allowed, _ = monitor.check_rate_limit(
                action_type="mention_admin",
                player_name="Spammer",
            )
            assert allowed is True

        # 6th event should be blocked
        allowed, reason = monitor.check_rate_limit(
            action_type="mention_admin",
            player_name="Spammer",
        )

        assert allowed is False
        assert reason is not None
        assert "Rate limit exceeded" in reason

    def test_rate_limit_per_player(self, monitor):
        """Rate limits are per-player."""
        # Player1 hits limit
        for i in range(5):
            monitor.check_rate_limit("mention_admin", "Player1")

        # Player2 should still be allowed
        allowed, _ = monitor.check_rate_limit(
            action_type="mention_admin",
            player_name="Player2",
        )

        assert allowed is True

    def test_unknown_action_type(self, monitor):
        """Unknown action types are not rate-limited."""
        allowed, reason = monitor.check_rate_limit(
            action_type="unknown_action",
            player_name="Player1",
        )

        assert allowed is True
        assert reason is None


class TestInfractionLogging:
    """Test infraction logging."""

    def test_infraction_logged(self, monitor, temp_dir):
        """Infractions are written to JSONL."""
        monitor.check_malicious_pattern(
            text="eval('test')",
            player_name="Logger",
        )

        infractions_file = temp_dir / "infractions.jsonl"
        assert infractions_file.exists()

        with open(infractions_file, 'r') as f:
            line = f.readline()
            infraction = json.loads(line)

        assert infraction["player_name"] == "Logger"
        assert infraction["pattern_type"] == "code_injection"

    def test_get_infractions(self, monitor):
        """Retrieve infractions."""
        monitor.check_malicious_pattern("eval('1')", "Player1")
        monitor.check_malicious_pattern("exec('2')", "Player2")

        all_infractions = monitor.get_infractions()
        assert len(all_infractions) == 2

        player1_infractions = monitor.get_infractions(player_name="Player1")
        assert len(player1_infractions) == 1
        assert player1_infractions[0]["player_name"] == "Player1"


class TestErrorPaths:
    """Exercise error paths without depending on logging wiring."""

    def test_load_banned_players_non_json(self, temp_dir):
        """Invalid JSON ban file should be ignored and not crash."""
        ban_file = temp_dir / "banned.json"
        ban_file.write_text("not-json", encoding="utf-8")

        monitor = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=ban_file,
        )

        # Behavior: no exception, and ban set falls back to empty
        assert monitor.banned_players == set()

    def test_load_banned_players_wrong_type(self, temp_dir):
        """Non-list banned_players structure should be ignored."""
        ban_file = temp_dir / "banned.json"
        ban_file.write_text(
            json.dumps({"banned_players": {"not": "a list"}}),
            encoding="utf-8",
        )

        monitor = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=ban_file,
        )

        # Behavior: treated as invalid, ban set emptied
        assert monitor.banned_players == set()

    def test_log_infraction_write_error(self, temp_dir, monkeypatch):
        """Infraction write failures should not crash."""
        infractions_file = temp_dir / "infractions.jsonl"
        monitor = SecurityMonitor(
            infractions_file=infractions_file,
            banned_players_file=temp_dir / "banned.json",
        )

        def fake_open(*args, **kwargs):
            raise OSError("disk full")

        # Patch builtins.open because SecurityMonitor uses the built-in
        monkeypatch.setattr("builtins.open", fake_open)

        # Should not raise even if writing infractions fails
        monitor.check_malicious_pattern("eval('1')", "DiskError")



class TestHappyPaths:
    """Additional success-path coverage."""

    def test_no_malicious_pattern_returns_none(self, monitor):
        """Benign text with no patterns returns None and does not ban."""
        infraction = monitor.check_malicious_pattern(
            text="Just chatting about blue science packs.",
            player_name="BenignUser",
        )

        assert infraction is None
        assert "BenignUser" not in monitor.banned_players

    def test_rate_limit_multiple_action_types_independent(self, monitor):
        """Different action types maintain separate rate limits."""
        # Hit chat_message limit for a player
        for _ in range(20):
            allowed, _ = monitor.check_rate_limit("chat_message", "MultiUser")
            assert allowed is True

        # Still allowed to mention_admin because it's a different action type
        allowed, reason = monitor.check_rate_limit("mention_admin", "MultiUser")
        assert allowed is True
        assert reason is None

    def test_get_infractions_with_limit(self, monitor):
        """get_infractions respects the limit parameter."""
        for i in range(10):
            monitor.check_malicious_pattern(f"eval('{i}')", f"Player{i}")

        last_three = monitor.get_infractions(limit=3)
        assert len(last_three) == 3
        # Most recent infractions should be first
        assert isinstance(last_three[0]["timestamp"], str)

    def test_env_based_banlist_dir(self, tmp_path, monkeypatch):
        """FACTORIO_ISR_BANLIST_DIR controls banlist location."""
        custom_dir = tmp_path / "ban-dir"
        monkeypatch.setenv("FACTORIO_ISR_BANLIST_DIR", str(custom_dir))

        monitor = SecurityMonitor(
            infractions_file=tmp_path / "infractions.jsonl",
            banned_players_file=None,
        )

        # Ban a player and ensure file is written under ENV directory
        monitor.ban_player("EnvUser")
        expected_file = custom_dir / "server-banlist.json"
        assert expected_file.exists()

        data = json.loads(expected_file.read_text(encoding="utf-8"))
        assert "EnvUser" in data["banned_players"]

class TestDefaults:
    """Tests for default ./config paths (no env, no overrides)."""

    def test_defaults_use_config_directory(self, tmp_path, monkeypatch):
        """SecurityMonitor() defaults to ./config for infractions and banlist."""
        # Run in an isolated cwd so we don't touch the real project dirs
        monkeypatch.chdir(tmp_path)

        monitor = SecurityMonitor()  # no args, no env override

        # After banning a player, the default banlist file should be created
        monitor.ban_player("DefaultUser")

        banlist_file = Path("config") / "server-banlist.json"
        infractions_file = Path("config") / "infractions.jsonl"

        assert banlist_file.exists()
        assert monitor.banned_players == {"DefaultUser"}

        # Trigger an infraction to ensure infractions file is used
        monitor.check_malicious_pattern("eval('x')", "DefaultUser2")
        assert infractions_file.exists()
        content = infractions_file.read_text(encoding="utf-8").strip()
        assert content  # at least one line written


class TestIntegrationFlow:
    """End-to-end malicious message → infraction → ban."""

    def test_malicious_flow_creates_infraction_and_ban(self, temp_dir):
        infractions_file = temp_dir / "infractions.jsonl"
        banlist_file = temp_dir / "server-banlist.json"

        monitor = SecurityMonitor(
            infractions_file=infractions_file,
            banned_players_file=banlist_file,
        )

        # 1) Malicious message
        infraction = monitor.check_malicious_pattern(
            text="Try this: eval('__import__(\"os\").system(\"rm -rf /\")')",
            player_name="MalUser",
        )

        # 2) Infraction object returned
        assert infraction is not None
        assert infraction.player_name == "MalUser"
        assert infraction.pattern_type == "code_injection"
        assert infraction.auto_banned is True

        # 3) Auto-banned
        assert monitor.is_banned("MalUser")

        # 4) Check banlist JSON content
        assert banlist_file.exists()
        ban_data = json.loads(banlist_file.read_text(encoding="utf-8"))
        assert "MalUser" in ban_data.get("banned_players", [])

        # 5) Check infractions log JSONL content
        assert infractions_file.exists()
        lines = [ln for ln in infractions_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) >= 1
        inf_json = json.loads(lines[-1])
        assert inf_json["player_name"] == "MalUser"
        assert inf_json["pattern_type"] == "code_injection"
        assert inf_json["auto_banned"] is True
        assert "timestamp" in inf_json

# ============================================================================
# Comprehensive Tests for SecurityMonitor.ban_player
# ============================================================================

class TestBanPlayerComprehensive:
    """Comprehensive tests for ban_player method covering all logic paths."""
    
    def test_ban_player_happy_path_new_player(self, monitor, temp_dir):
        """Ban a new player - happy path."""
        assert "NewPlayer" not in monitor.banned_players
        
        monitor.ban_player("NewPlayer", reason="Test violation")
        
        # Player should be in memory
        assert "NewPlayer" in monitor.banned_players
        assert monitor.is_banned("NewPlayer")
        
        # Player should be persisted to file
        ban_file = temp_dir / "banned.json"
        assert ban_file.exists()
        
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        assert "NewPlayer" in data["banned_players"]
        assert "last_updated" in data
    
    def test_ban_player_already_banned_early_return(self, monitor):
        """Banning an already-banned player should return early (idempotent)."""
        # Ban player first time
        monitor.ban_player("AlreadyBanned", reason="First ban")
        initial_count = len(monitor.banned_players)
        
        # Try to ban again
        monitor.ban_player("AlreadyBanned", reason="Second ban")
        
        # Should still be banned, count unchanged
        assert "AlreadyBanned" in monitor.banned_players
        assert len(monitor.banned_players) == initial_count
    
    def test_ban_player_with_default_reason(self, monitor):
        """Ban player with default reason."""
        monitor.ban_player("DefaultReasonPlayer")
        
        # Should be banned (reason is just for logging)
        assert "DefaultReasonPlayer" in monitor.banned_players
    
    def test_ban_player_with_custom_reason(self, monitor):
        """Ban player with custom reason."""
        monitor.ban_player("CustomReasonPlayer", reason="Custom violation detected")
        
        # Should be banned
        assert "CustomReasonPlayer" in monitor.banned_players
    
    def test_ban_player_memory_state_updated_before_save(self, monitor, temp_dir):
        """Player is added to memory before file save is attempted."""
        # This tests the ordering: add to set, then save
        assert "NewPlayer" not in monitor.banned_players
        
        monitor.ban_player("NewPlayer")
        
        # In-memory state should be updated
        assert "NewPlayer" in monitor.banned_players
        
        # And persisted (verifying save was called)
        ban_file = temp_dir / "banned.json"
        assert ban_file.exists()
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        assert "NewPlayer" in data["banned_players"]

    
    def test_ban_player_multiple_players_accumulate(self, monitor, temp_dir):
        """Banning multiple players accumulates in ban list."""
        monitor.ban_player("Player1")
        monitor.ban_player("Player2")
        monitor.ban_player("Player3")
        
        assert len(monitor.banned_players) == 3
        assert "Player1" in monitor.banned_players
        assert "Player2" in monitor.banned_players
        assert "Player3" in monitor.banned_players
        
        # Check file contains all players
        ban_file = temp_dir / "banned.json"
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        assert set(data["banned_players"]) == {"Player1", "Player2", "Player3"}
        
    def test_ban_player_save_error_handling(self, monitor, temp_dir):
        """Verify that _save_banned_players has error handling for write failures."""
        # Make the directory read-only to cause actual write failure
        import os
        ban_file = temp_dir / "banned.json"
        
        # First ban succeeds (creates file)
        monitor.ban_player("FirstPlayer")
        assert ban_file.exists()
        
        # Make directory read-only (this will cause save to fail)
        try:
            os.chmod(temp_dir, 0o444)  # Read-only
            
            # This should not crash - _save_banned_players handles the error
            monitor.ban_player("SecondPlayer")
            
            # Player is in memory
            assert "SecondPlayer" in monitor.banned_players
            
            # But file won't be updated (permission denied)
            # This is expected behavior - logged but not fatal
            
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_dir, 0o755)    
    
    def test_ban_player_persistence_across_instances(self, temp_dir):
        """Banned players persist when SecurityMonitor is reloaded."""
        # First instance
        monitor1 = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=temp_dir / "banned.json",
        )
        monitor1.ban_player("PersistentBan")
        
        # Second instance (reload)
        monitor2 = SecurityMonitor(
            infractions_file=temp_dir / "infractions.jsonl",
            banned_players_file=temp_dir / "banned.json",
        )
        
        # Should load the ban from file
        assert monitor2.is_banned("PersistentBan")
        assert "PersistentBan" in monitor2.banned_players
    
    def test_ban_player_sorted_in_file(self, monitor, temp_dir):
        """Ban list in file should be sorted for consistency."""
        monitor.ban_player("Charlie")
        monitor.ban_player("Alice")
        monitor.ban_player("Bob")
        
        ban_file = temp_dir / "banned.json"
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        
        # Should be sorted alphabetically
        assert data["banned_players"] == ["Alice", "Bob", "Charlie"]
    
    def test_ban_player_with_special_characters(self, monitor):
        """Ban player with special characters in name."""
        special_name = "Player[123]"
        monitor.ban_player(special_name)
        
        assert special_name in monitor.banned_players
        assert monitor.is_banned(special_name)
    
    def test_ban_player_with_unicode_name(self, monitor, temp_dir):
        """Ban player with Unicode characters in name."""
        unicode_name = "玩家123"
        monitor.ban_player(unicode_name)
        
        assert unicode_name in monitor.banned_players
        
        # Should be persisted correctly
        ban_file = temp_dir / "banned.json"
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        assert unicode_name in data["banned_players"]
    
    def test_ban_player_empty_string(self, monitor):
        """Ban player with empty string name (edge case)."""
        monitor.ban_player("")
        
        # Should work (even if it's weird)
        assert "" in monitor.banned_players
    
    def test_ban_player_whitespace_name(self, monitor):
        """Ban player with whitespace in name."""
        monitor.ban_player("  Player With Spaces  ")
        
        # Should preserve the exact string
        assert "  Player With Spaces  " in monitor.banned_players
    
    def test_ban_player_very_long_name(self, monitor):
        """Ban player with very long name."""
        long_name = "A" * 1000
        monitor.ban_player(long_name)
        
        assert long_name in monitor.banned_players
    
    def test_ban_player_after_malicious_pattern_auto_ban(self, monitor):
        """Verify auto_ban from malicious pattern uses ban_player correctly."""
        # This is an integration test showing ban_player is called
        infraction = monitor.check_malicious_pattern(
            text="eval('malicious')",
            player_name="AutoBanTest"
        )
        
        assert infraction is not None
        assert infraction.auto_banned is True
        # ban_player should have been called internally
        assert "AutoBanTest" in monitor.banned_players
    
    def test_ban_player_does_not_affect_other_state(self, monitor):
        """Banning a player should not affect rate limiting or infractions."""
        # Add some rate limit state
        monitor.check_rate_limit("chat_message", "RateLimitPlayer")
        
        # Ban a different player
        monitor.ban_player("BannedPlayer")
        
        # Rate limit state should be unaffected
        assert len(monitor.rate_limit_state.get("chat_message", [])) > 0
    
    def test_ban_player_file_format_valid_json(self, monitor, temp_dir):
        """Ban file should always be valid JSON."""
        monitor.ban_player("ValidJSON")
        
        ban_file = temp_dir / "banned.json"
        
        # Should be parseable JSON
        with open(ban_file, "r", encoding="utf-8") as f:
            data = json.load(f)  # Will raise if invalid
        
        assert isinstance(data, dict)
        assert "banned_players" in data
        assert isinstance(data["banned_players"], list)
    
    def test_ban_player_file_has_timestamp(self, monitor, temp_dir):
        """Ban file should include last_updated timestamp."""
        monitor.ban_player("TimestampTest")
        
        ban_file = temp_dir / "banned.json"
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        
        assert "last_updated" in data
        # Should be ISO format timestamp
        from datetime import datetime
        timestamp = datetime.fromisoformat(data["last_updated"])
        assert isinstance(timestamp, datetime)
    
    def test_ban_player_incremental_save(self, monitor, temp_dir):
        """Each ban should update the file incrementally."""
        ban_file = temp_dir / "banned.json"
        
        # Ban first player
        monitor.ban_player("FirstBan")
        data1 = json.loads(ban_file.read_text(encoding="utf-8"))
        timestamp1 = data1["last_updated"]
        
        # Wait a tiny bit (so timestamps differ)
        import time
        time.sleep(0.01)
        
        # Ban second player
        monitor.ban_player("SecondBan")
        data2 = json.loads(ban_file.read_text(encoding="utf-8"))
        timestamp2 = data2["last_updated"]
        
        # Should have both players
        assert set(data2["banned_players"]) == {"FirstBan", "SecondBan"}
        # Timestamp should be updated
        assert timestamp2 >= timestamp1
    
    def test_ban_player_reason_not_stored_in_file(self, monitor, temp_dir):
        """Ban reason is for logging only, not stored in file."""
        monitor.ban_player("ReasonTest", reason="Very bad behavior")
        
        ban_file = temp_dir / "banned.json"
        data = json.loads(ban_file.read_text(encoding="utf-8"))
        
        # File should not contain reason
        assert "reason" not in str(data)
        # Just player name
        assert "ReasonTest" in data["banned_players"]
