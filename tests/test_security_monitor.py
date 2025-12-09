"""
Tests for security_monitor.py
"""

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
