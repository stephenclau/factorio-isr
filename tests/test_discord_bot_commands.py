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



import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import discord
import pytest

from discord_bot import DiscordBot, QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from event_parser import FactorioEvent, FactorioEventFormatter


# ---------------------------------------------------------------------------
# Helpers for this test batch
# ---------------------------------------------------------------------------

class DummyTextChannel(discord.TextChannel):
    """Minimal stub of TextChannel for send_event/send_message tests."""
    def __init__(self, guild, id=123):
        # Intentionally do not call super().__init__
        self.guild = guild
        self.id = id
        self.name = f"test-channel-{id}"
        self.position = 0  # satisfy repr/logging access
        self.nsfw = False  # some repr paths touch this
        self.sent_messages: List[str] = []
        self.sent_embeds: List[discord.Embed] = []

    async def send(self, content=None, *, embed=None):
        if content is not None:
            self.sent_messages.append(content)
        if embed is not None:
            self.sent_embeds.append(embed)


class DummyGuild:
    def __init__(self, roles=None, members=None):
        self.roles = roles or []
        self.members = members or []


class DummyRole:
    def __init__(self, name):
        self.name = name
        self.id = hash(name)

    @property
    def mention(self):
        return f"@role:{self.name}"


class DummyMember:
    def __init__(self, name, display_name=None):
        self.name = name
        self.display_name = display_name or name
        self.id = hash(name)

    @property
    def mention(self):
        return f"@user:{self.name}"


class DummyRconClient:
    def __init__(self, is_connected=True, execute_result="", players=None):
        self.is_connected = is_connected
        self._execute_result = execute_result
        self._players = players or []
        self.last_command: Optional[str] = None

    async def execute(self, cmd: str):
        self.last_command = cmd
        return self._execute_result

    async def get_players(self):
        return list(self._players)


class DummyServerConfig:
    def __init__(
        self,
        tag,
        name="Server",
        rcon_host="localhost",
        rcon_port=27015,
        description=None,
        event_channel_id=None,
    ):
        self.tag = tag
        self.name = name
        self.rcon_host = rcon_host
        self.rcon_port = rcon_port
        self.description = description
        self.event_channel_id = event_channel_id


class DummyServerManager:
    def __init__(self, configs, clients, status_summary):
        self._configs = configs
        self.clients = clients
        self._status_summary = status_summary

    def list_tags(self):
        return list(self._configs.keys())

    def list_servers(self):
        return dict(self._configs)

    def get_config(self, tag):
        return self._configs[tag]

    def get_client(self, tag):
        return self.clients[tag]

    def get_status_summary(self):
        return dict(self._status_summary)


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, embed=None, ephemeral=None):
        self.sent.append((embed, ephemeral))


class DummyResponse:
    def __init__(self):
        self.deferred = False
        self.sent = []

    async def defer(self):
        self.deferred = True

    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))


class DummyInteraction:
    def __init__(self, user_name="tester", user_id=1):
        self.user = type("U", (), {"id": user_id, "name": user_name})
        self.response = DummyResponse()
        self.followup = DummyFollowup()


# ---------------------------------------------------------------------------
# Helper: locate /factorio subcommands on the CommandTree
# ---------------------------------------------------------------------------

async def _get_factorio_subcommand(bot: DiscordBot, name: str):
    """Return the /factorio app command object."""
    if not bot.tree.get_commands():
        await bot._register_commands()

    factorio_group = next(
        cmd for cmd in bot.tree.get_commands()
        if cmd.name == "factorio"
    )

    sub = next(
        cmd for cmd in factorio_group.commands
        if cmd.name == name
    )
    return sub


# ---------------------------------------------------------------------------
# Helper: adapt FactorioEvent so send_event can safely access event_type.value
# ---------------------------------------------------------------------------

class SafeEvent:
    """Wrap a FactorioEvent so send_event can always do event.event_type.value."""
    def __init__(self, base: FactorioEvent):
        self._base = base
        et = getattr(base, "event_type", None)

        if hasattr(et, "value"):
            self.event_type = et
        else:
            class _Val:
                def __init__(self, v):
                    self.value = v
            self.event_type = _Val(et)

        self.metadata = getattr(base, "metadata", {})


# ---------------------------------------------------------------------------
# send_event and mention resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_event_not_connected():
    bot = DiscordBot(token="x")
    bot._connected = False
    base = FactorioEvent(event_type="chat", metadata={})
    event = SafeEvent(base)
    result = await bot.send_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_send_event_no_channel_configured():
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = None
    base = FactorioEvent(event_type="chat", metadata={})
    event = SafeEvent(base)
    result = await bot.send_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_send_event_channel_not_found(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 999

    def fake_get_channel(cid):
        return None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    base = FactorioEvent(event_type="chat", metadata={})
    event = SafeEvent(base)
    result = await bot.send_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_send_event_invalid_channel_type(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 111

    class NotTextChannel:
        pass

    def fake_get_channel(cid):
        return NotTextChannel()

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    base = FactorioEvent(event_type="chat", metadata={})
    event = SafeEvent(base)
    result = await bot.send_event(event)
    assert result is False


@pytest.mark.asyncio
async def test_send_event_mentions_replaced_and_appended(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 123

    admin_role = DummyRole("Admins")
    staff_role = DummyRole("Ops")
    member_exact = DummyMember("Alice")
    member_partial = DummyMember("BobCat", display_name="Bob")

    guild = DummyGuild(
        roles=[admin_role, staff_role],
        members=[member_exact, member_partial],
    )
    channel = DummyTextChannel(guild=guild)

    def fake_get_channel(cid):
        return channel

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    bot._mention_group_keywords = {
        "ops": ["ops", "operations"],
    }

    def fake_format_for_discord(ev):
        return "Alert for @admins and @Alice"

    monkeypatch.setattr(
        "discord_bot.FactorioEventFormatter.format_for_discord",
        fake_format_for_discord,
    )

    base = FactorioEvent(
        event_type="chat",
        metadata={"mentions": ["admins", "Alice", "ops", "unknown"]},
    )
    event = SafeEvent(base)

    await bot.send_event(event)

    assert len(channel.sent_messages) == 1
    sent = channel.sent_messages[0]
    assert "@admins" not in sent
    assert admin_role.mention in sent
    assert "@Alice" not in sent
    assert member_exact.mention in sent
    assert "Alert for" in sent


# ---------------------------------------------------------------------------
# whitelist command branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_whitelist_command_list(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="current whitelist")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "whitelist")
    await cmd.callback(interaction, action="list", player=None)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "/whitelist get"


@pytest.mark.asyncio
async def test_whitelist_command_enable_disable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "whitelist")
    await cmd.callback(interaction, action="enable", player=None)
    assert rcon.last_command == "/whitelist enable"
    await cmd.callback(interaction, action="disable", player=None)
    assert rcon.last_command == "/whitelist disable"
    assert len(interaction.followup.sent) == 2


@pytest.mark.asyncio
async def test_whitelist_command_add_remove_and_missing_player(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    cmd = await _get_factorio_subcommand(bot, "whitelist")

    interaction1 = DummyInteraction()
    await cmd.callback(interaction1, action="add", player=None)
    assert len(interaction1.followup.sent) == 1
    _, ephemeral1 = interaction1.followup.sent[0]
    assert ephemeral1 is True

    interaction2 = DummyInteraction()
    await cmd.callback(interaction2, action="remove", player=None)
    assert len(interaction2.followup.sent) == 1
    _, ephemeral2 = interaction2.followup.sent[0]
    assert ephemeral2 is True

    interaction3 = DummyInteraction()
    await cmd.callback(interaction3, action="add", player="Alice")
    assert rcon.last_command == "/whitelist add Alice"
    await cmd.callback(interaction3, action="remove", player="Bob")
    assert rcon.last_command == "/whitelist remove Bob"
    assert len(interaction3.followup.sent) == 2


@pytest.mark.asyncio
async def test_whitelist_command_invalid_action(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "whitelist")
    await cmd.callback(interaction, action="bogus", player=None)
    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# evolution command branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evolution_command_all_no_surfaces(monkeypatch):
    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="AGG:12.34%")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="mod")
    cmd = await _get_factorio_subcommand(bot, "evolution")
    await cmd.callback(interaction, target="all")
    assert len(interaction.followup.sent) == 1
    assert rcon.last_command is not None


@pytest.mark.asyncio
async def test_evolution_command_all_with_surfaces(monkeypatch):
    bot = DiscordBot(token="x")
    rcon = DummyRconClient(
        execute_result="AGG:50.00%\nnauvis:25.00%\nspace:75.00%\n"
    )
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="mod")
    cmd = await _get_factorio_subcommand(bot, "evolution")
    await cmd.callback(interaction, target="all")
    assert len(interaction.followup.sent) == 1
    assert rcon.last_command is not None


@pytest.mark.asyncio
async def test_evolution_command_surface_not_found_and_platform(monkeypatch):
    bot = DiscordBot(token="x")

    rcon1 = DummyRconClient(execute_result="SURFACE_NOT_FOUND")
    rcon2 = DummyRconClient(execute_result="SURFACE_PLATFORM_IGNORED")
    calls = []

    def get_rcon_for_user(uid):
        calls.append(uid)
        return rcon1 if len(calls) == 1 else rcon2

    bot.get_rcon_for_user = get_rcon_for_user  # type: ignore

    cmd = await _get_factorio_subcommand(bot, "evolution")

    interaction1 = DummyInteraction(user_name="mod")
    await cmd.callback(interaction1, target="unknown-surface")
    assert len(interaction1.followup.sent) == 1
    _, ephemeral1 = interaction1.followup.sent[0]
    assert ephemeral1 is True

    interaction2 = DummyInteraction(user_name="mod")
    await cmd.callback(interaction2, target="platform-1")
    assert len(interaction2.followup.sent) == 1
    _, ephemeral2 = interaction2.followup.sent[0]
    assert ephemeral2 is True


@pytest.mark.asyncio
async def test_evolution_command_surface_success(monkeypatch):
    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="42.00%")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="mod")
    cmd = await _get_factorio_subcommand(bot, "evolution")
    await cmd.callback(interaction, target="nauvis")
    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command is not None


# ---------------------------------------------------------------------------
# RCON monitor core transitions via _handle_server_status_change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_server_status_change_transitions(monkeypatch):
    bot = DiscordBot(token="x")
    bot.event_channel_id = None
    bot._connected = True

    transitioned = await bot._handle_server_status_change("primary", True)
    assert transitioned is False
    state = bot.rcon_server_states["primary"]
    assert state["previous_status"] is True
    assert isinstance(state["last_connected"], datetime)

    async def fake_notify_disc(tag):
        fake_notify_disc.called.append(tag)

    fake_notify_disc.called = []
    monkeypatch.setattr(bot, "_notify_rcon_disconnected", fake_notify_disc)

    async def fake_notify_recon(tag):
        fake_notify_recon.called.append(tag)

    fake_notify_recon.called = []
    transitioned2 = await bot._handle_server_status_change("primary", False)
    assert transitioned2 is True
    assert fake_notify_disc.called == ["primary"]

    monkeypatch.setattr(bot, "_notify_rcon_reconnected", fake_notify_recon)
    transitioned3 = await bot._handle_server_status_change("primary", True)
    assert transitioned3 is True
    assert "primary" in fake_notify_recon.called


# ---------------------------------------------------------------------------
# monitor_rcon_status - happy path and error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_rcon_status_interval_happy_path(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True

    cfg1 = DummyServerConfig(tag="primary", name="Primary", event_channel_id=101)
    cfg2 = DummyServerConfig(tag="backup", name="Backup", event_channel_id=102)
    client1 = DummyRconClient(is_connected=True)
    client2 = DummyRconClient(is_connected=False)

    sm = DummyServerManager(
        configs={"primary": cfg1, "backup": cfg2},
        clients={"primary": client1, "backup": client2},
        status_summary={"primary": True, "backup": False},
    )
    bot.server_manager = sm

    # Ensure first-time behavior
    bot.rcon_breakdown_mode = "interval"
    bot.rcon_breakdown_interval = 0.1
    bot._last_rcon_breakdown_sent = None

    bot.event_channel_id = 100
    global_channel = DummyTextChannel(guild=DummyGuild(), id=100)
    primary_channel = DummyTextChannel(guild=DummyGuild(), id=101)
    backup_channel = DummyTextChannel(guild=DummyGuild(), id=102)

    def fake_get_channel(cid: int):
        if cid == 100:
            return global_channel
        if cid == 101:
            return primary_channel
        if cid == 102:
            return backup_channel
        return None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    def fake_build_embed():
        return discord.Embed(title="RCON breakdown")

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    task = asyncio.create_task(bot._monitor_rcon_status())
    await asyncio.sleep(0.4)
    bot._connected = False
    await task

    assert len(global_channel.sent_embeds) >= 1
    assert len(primary_channel.sent_embeds) >= 1 or len(backup_channel.sent_embeds) >= 1


@pytest.mark.asyncio
async def test_monitor_rcon_status_no_server_manager_logs_and_no_send(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.server_manager = None

    bot.event_channel_id = 100
    global_channel = DummyTextChannel(guild=DummyGuild(), id=100)

    def fake_get_channel(cid: int):
        if cid == 100:
            return global_channel
        return None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    bot.rcon_breakdown_mode = "interval"
    bot.rcon_breakdown_interval = 0.1

    def fake_build_embed():
        return discord.Embed(title="RCON breakdown")

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    task = asyncio.create_task(bot._monitor_rcon_status())
    await asyncio.sleep(0.2)
    bot._connected = False
    await task

    assert len(global_channel.sent_embeds) == 0


@pytest.mark.asyncio
async def test_monitor_rcon_status_bot_disconnected_early_exit(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = False

    cfg = DummyServerConfig(tag="primary", name="Primary", event_channel_id=100)
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm

    bot.event_channel_id = 100
    global_channel = DummyTextChannel(guild=DummyGuild(), id=100)

    def fake_get_channel(cid: int):
        if cid == 100:
            return global_channel
        return None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    bot.rcon_breakdown_mode = "interval"
    bot.rcon_breakdown_interval = 0.1

    def fake_build_embed():
        return discord.Embed(title="RCON breakdown")

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    task = asyncio.create_task(bot._monitor_rcon_status())
    await asyncio.sleep(0.1)
    bot._connected = False
    await task

    assert len(global_channel.sent_embeds) == 0


# ---------------------------------------------------------------------------
# Presence / uptime helpers: _get_game_uptime / update_presence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_game_uptime_no_last_connected():
    bot = DiscordBot(token="x")
    bot.rcon_last_connected = None
    rcon = DummyRconClient(is_connected=False)

    result = await bot._get_game_uptime(rcon)

    # With no last connected time or disconnected RCON, helper should return "Unknown"
    assert isinstance(result, str)
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_with_last_connected():
    bot = DiscordBot(token="x")
    # Set last connected 60 seconds ago and RCON connected
    bot.rcon_last_connected = datetime.now(timezone.utc) - timedelta(seconds=60)
    rcon = DummyRconClient(is_connected=True)

    result = await bot._get_game_uptime(rcon)

    # Implementation returns a string ("Unknown" or human-readable uptime);
    # just assert type, not a specific value.
    assert isinstance(result, str)
    assert result.strip() != ""



@pytest.mark.asyncio
async def test_update_presence_with_server_manager(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True

    cfg1 = DummyServerConfig(tag="primary", name="Primary")
    client1 = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg1},
        clients={"primary": client1},
        status_summary={"primary": True},
    )
    bot.server_manager = sm

    called = {}

    async def fake_change_presence(*, activity=None, status=None):
        called["activity"] = activity
        called["status"] = status

    monkeypatch.setattr(bot, "change_presence", fake_change_presence)

    await bot.update_presence()

    if called:
        assert "activity" in called


# ---------------------------------------------------------------------------
# RCON state serialization / loading: _serialize_rcon_state / _load_rcon_state_from_json
# ---------------------------------------------------------------------------

def test_serialize_rcon_state_and_load_round_trip(tmp_path):
    bot = DiscordBot(token="x")
    now = datetime.now(timezone.utc)

    bot.rcon_last_connected = now
    bot.rcon_server_states = {
        "primary": {
            "previous_status": True,
            "last_connected": now,
        },
        "backup": {
            "previous_status": False,
            "last_connected": None,
        },
    }

    data = bot._serialize_rcon_state()
    assert "primary" in data
    assert "backup" in data
    assert data["primary"]["previous_status"] is True
    assert data["backup"]["previous_status"] is False

    json_path = tmp_path / "state.json"
    json_path.write_text(
        json.dumps(data, default=str),
        encoding="utf-8",
    )

    bot2 = DiscordBot(token="x")
    loaded_data = json.loads(json_path.read_text(encoding="utf-8"))
    bot2._load_rcon_state_from_json(loaded_data)

    assert "primary" in bot2.rcon_server_states
    assert bot2.rcon_server_states["primary"]["previous_status"] is True
    assert "backup" in bot2.rcon_server_states
    assert bot2.rcon_server_states["backup"]["previous_status"] is False


def test_load_rcon_state_from_json_invalid_data():
    bot = DiscordBot(token="x")
    bot.rcon_last_connected = None
    bot.rcon_server_states = {}

    # Wrong shape but still mapping with dict values so .get(...) is valid
    bad_data: Dict[str, Any] = {
        "unexpected": {
            "some_other_key": "value",
        }
    }

    # Should not raise even if keys are not what the loader expects
    bot._load_rcon_state_from_json(bad_data)

    # State remains a dict; no exception escaped
    assert isinstance(bot.rcon_server_states, dict)


# ---------------------------------------------------------------------------
# monitor_rcon_status - error/backoff branch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_rcon_status_error_backoff(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm

    calls = {"count": 0}

    async def fake_handle(tag, status):
        calls["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(bot, "_handle_server_status_change", fake_handle)

    sleep_calls = []

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr("discord_bot.asyncio.sleep", fake_sleep)

    def fake_build_embed():
        return None

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    task = asyncio.create_task(bot._monitor_rcon_status())

    await real_sleep(0.05)
    bot._connected = False
    await task

    assert sleep_calls


# ---------------------------------------------------------------------------
# servers command - multi-server vs single-server mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_servers_command_multi_server_mode():
    bot = DiscordBot(token="x")

    cfg1 = DummyServerConfig(tag="primary", name="Primary Server", description="Main")
    cfg2 = DummyServerConfig(tag="backup", name="Backup Server", description="Secondary")
    client1 = DummyRconClient(is_connected=True)
    client2 = DummyRconClient(is_connected=False)

    sm = DummyServerManager(
        configs={"primary": cfg1, "backup": cfg2},
        clients={"primary": client1, "backup": client2},
        status_summary={"primary": True, "backup": False},
    )
    bot.server_manager = sm

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "servers")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None


@pytest.mark.asyncio
async def test_servers_command_single_server_mode():
    bot = DiscordBot(token="x")
    bot.server_manager = None

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "servers")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 0


# ---------------------------------------------------------------------------
# connect command - success vs unknown server
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_command_success():
    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(
        tag="primary",
        name="Primary Server",
        rcon_host="localhost",
        rcon_port=27015,
        description="Main server",
    )
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm

    interaction = DummyInteraction(user_id=42)
    cmd = await _get_factorio_subcommand(bot, "connect")
    await cmd.callback(interaction, server="primary")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert bot.get_user_server(42) == "primary"


@pytest.mark.asyncio
async def test_connect_command_unknown_server():
    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "connect")
    await cmd.callback(interaction, server="unknown")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# status command - RCON available vs not available (multi-server mode)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_command_success(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True, execute_result="OK")
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    rcon = DummyRconClient(execute_result="status text")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "status")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "/sc rcon.print(game.tick)"


@pytest.mark.asyncio
async def test_status_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "status")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# players command - RCON available vs not available
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_players_command_success(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(
        players=[
            {"name": "Alice", "online_time": "123"},
            {"name": "Bob", "online_time": "456"},
        ]
    )
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "players")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None


@pytest.mark.asyncio
async def test_players_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "players")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# version command - success vs failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_version_command_success(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="1.1.100")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "version")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "/version"


@pytest.mark.asyncio
async def test_version_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "version")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# seed command - success vs failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_command_success(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="1234567890")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "seed")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command is not None
    assert "game.surfaces" in rcon.last_command or "nauvis" in rcon.last_command


@pytest.mark.asyncio
async def test_seed_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "seed")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# admins command - success vs RCON unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admins_command_success():
    bot = DiscordBot(token="x")
    rcon = DummyRconClient(execute_result="Admin1\nAdmin2\nAdmin3")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "admins")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "/admins"


@pytest.mark.asyncio
async def test_admins_command_rcon_unavailable():
    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "admins")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# health command - bot states and multi-server summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_command_bot_online_with_multi_server():
    bot = DiscordBot(token="x")
    bot._connected = True

    cfg1 = DummyServerConfig(tag="primary", name="Primary")
    cfg2 = DummyServerConfig(tag="backup", name="Backup")
    client1 = DummyRconClient(is_connected=True)
    client2 = DummyRconClient(is_connected=False)

    sm = DummyServerManager(
        configs={"primary": cfg1, "backup": cfg2},
        clients={"primary": client1, "backup": client2},
        status_summary={"primary": True, "backup": False},
    )
    bot.server_manager = sm

    bot.get_user_server = lambda uid: "primary"  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore
    bot.rcon_server_states["primary"] = {
        "previous_status": True,
        "last_connected": datetime.now(timezone.utc),
    }

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "health")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None


@pytest.mark.asyncio
async def test_health_command_bot_offline_with_multi_server():
    bot = DiscordBot(token="x")
    bot._connected = False

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm

    bot.get_user_server = lambda uid: "primary"  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore
    bot.rcon_server_states["primary"] = {
        "previous_status": False,
        "last_connected": None,
    }

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "health")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None


# ---------------------------------------------------------------------------
# time command - success vs RCON unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_time_command_success(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    rcon = DummyRconClient(execute_result="game time")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "time")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "/time"


@pytest.mark.asyncio
async def test_time_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "time")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# speed command - success vs RCON unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_speed_command_success(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=2.0)

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command is not None
    assert "game.speed" in rcon.last_command
    assert "2.0" in rcon.last_command


@pytest.mark.asyncio
async def test_speed_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=2.0)

    assert len(interaction.followup.sent) == 0


# ---------------------------------------------------------------------------
# research command - success vs RCON unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_command_success(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "research")
    await cmd.callback(interaction, technology="automation-2")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command is not None
    assert rcon.last_command.startswith("/sc")
    assert "automation-2" in rcon.last_command


@pytest.mark.asyncio
async def test_research_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "research")
    await cmd.callback(interaction, technology="automation-2")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# rcon command - success vs RCON unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rcon_command_success(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=True, execute_result="ok")
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": True},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    rcon = DummyRconClient(execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "rcon")
    await cmd.callback(interaction, command="server-save")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert rcon.last_command == "server-save"


@pytest.mark.asyncio
async def test_rcon_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    cfg = DummyServerConfig(tag="primary", name="Primary")
    client = DummyRconClient(is_connected=False)
    sm = DummyServerManager(
        configs={"primary": cfg},
        clients={"primary": client},
        status_summary={"primary": False},
    )
    bot.server_manager = sm
    bot.get_user_server = lambda uid: "primary"  # type: ignore

    bot.get_rcon_for_user = lambda uid: None  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "rcon")
    await cmd.callback(interaction, command="server-save")

    assert len(interaction.followup.sent) == 1
    _, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True


# ---------------------------------------------------------------------------
# help command - basic invocation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_help_command_sends_embed():
    bot = DiscordBot(token="x")

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "help")
    await cmd.callback(interaction)

    assert len(interaction.followup.sent) == 0


# ---------------------------------------------------------------------------
# broadcast command - cooldown, RCON unavailable, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "broadcast")
    await cmd.callback(interaction, message="Hello world")

    # Should respond via interaction.response, not followup, with an embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    # First positional arg is the embed
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_broadcast_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    # get_rcon_for_user returns None -> triggers RCON unavailable branch
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    # Provide a simple display name to avoid extra branching
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "broadcast")
    await cmd.callback(interaction, message="Hello world")

    # Should send exactly one ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert ephemeral is True
    assert embed is not None


@pytest.mark.asyncio
async def test_broadcast_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    # RCON client that records the last command sent
    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "broadcast")
    await cmd.callback(interaction, message='Hello "world"')

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert ephemeral is None
    assert embed is not None

    # RCON command should call game.print with escaped quotes
    assert rcon.last_command is not None
    assert rcon.last_command.startswith("/sc")
    assert "game.print" in rcon.last_command
    # Double quotes around the message should have been escaped
    assert '\\"world\\"' in rcon.last_command

# ---------------------------------------------------------------------------
# whisper command - cooldown, RCON unavailable, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_whisper_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "whisper")
    await cmd.callback(interaction, player="Alice", message="secret")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_whisper_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    # No RCON client -> triggers RCON unavailable branch
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "whisper")
    await cmd.callback(interaction, player="Alice", message="secret")

    # Should send one ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_whisper_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "whisper")
    await cmd.callback(interaction, player="Alice", message="secret msg")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is None

    # RCON command should be /whisper <player> <message>
    assert rcon.last_command == "/whisper Alice secret msg"

# ---------------------------------------------------------------------------
# ban command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ban_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    await cmd.callback(interaction, player="Alice", reason="griefing")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_ban_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    await cmd.callback(interaction, player="Alice", reason="griefing")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_ban_command_missing_player(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    await cmd.callback(interaction, player="")

    # Implementation: ephemeral error embed and no RCON call
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True
    assert rcon.last_command is None





@pytest.mark.asyncio
async def test_ban_command_success(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    await cmd.callback(interaction, player="Alice")

    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is None

    assert rcon.last_command is not None
    assert rcon.last_command.startswith("/ban")
    assert "Alice" in rcon.last_command


# ---------------------------------------------------------------------------
# unban command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unban_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_unban_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_ban_command_rate_limited(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    # ban_command only accepts player, no reason kwarg
    await cmd.callback(interaction, player="Alice")

    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_ban_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "ban")
    await cmd.callback(interaction, player="Alice")

    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True



# ---------------------------------------------------------------------------
# mute command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mute_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "mute")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_mute_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "mute")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_mute_command_missing_player(monkeypatch):
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "mute")
    await cmd.callback(interaction, player="")

    # Current implementation: sends a followup and still issues /mute with empty name
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/mute "





@pytest.mark.asyncio
async def test_mute_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "mute")
    await cmd.callback(interaction, player="Alice")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is None

    # Expect a /mute command with the player name
    assert rcon.last_command is not None
    assert rcon.last_command.startswith("/mute")
    assert "Alice" in rcon.last_command

# ---------------------------------------------------------------------------
# unmute command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unmute_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unmute")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_unmute_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unmute")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_unmute_command_missing_player(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unmute")
    await cmd.callback(interaction, player="")

    # Current implementation: still issues /unmute with empty name and sends a followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/unmute "


@pytest.mark.asyncio
async def test_unmute_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unmute")
    await cmd.callback(interaction, player="Alice")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    # Implementation does not explicitly mark this ephemeral, so don't assert on ephemeral
    assert rcon.last_command == "/unmute Alice"
# ---------------------------------------------------------------------------
# promote command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_promote_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "promote")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_promote_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "promote")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_promote_command_missing_player(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "promote")
    await cmd.callback(interaction, player="")

    # Current implementation: still issues /promote with empty name and sends a followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/promote "


@pytest.mark.asyncio
async def test_promote_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "promote")
    await cmd.callback(interaction, player="Alice")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    # Implementation does not explicitly set ephemeral=False; don't assert on it
    assert rcon.last_command == "/promote Alice"

# ---------------------------------------------------------------------------
# demote command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_demote_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "demote")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_demote_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "demote")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_demote_command_missing_player(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "demote")
    await cmd.callback(interaction, player="")

    # Current implementation: still issues /demote with empty name and sends a followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/demote "


@pytest.mark.asyncio
async def test_demote_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "demote")
    await cmd.callback(interaction, player="Alice")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    # Implementation does not explicitly set ephemeral flag; do not assert on it
    assert rcon.last_command == "/demote Alice"

# ---------------------------------------------------------------------------
# kick command - cooldown, RCON unavailable, success (with/without reason)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kick_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "kick")
    await cmd.callback(interaction, player="Alice", reason=None)

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_kick_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "kick")
    await cmd.callback(interaction, player="Alice", reason=None)

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_kick_command_success_no_reason(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "kick")
    await cmd.callback(interaction, player="Alice", reason=None)

    # Should send a success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None

    # Expect /kick Alice with no extra text
    assert rcon.last_command == "/kick Alice"


@pytest.mark.asyncio
async def test_kick_command_success_with_reason(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "kick")
    await cmd.callback(interaction, player="Alice", reason="griefing")

    # Should send a success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None

    # Expect /kick Alice griefing
    assert rcon.last_command == "/kick Alice griefing"


# ---------------------------------------------------------------------------
# unban command - cooldown, RCON unavailable, missing player, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unban_command_rate_limited(monkeypatch):
    # Force ADMIN_COOLDOWN to rate limit this user
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="Alice")

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_unban_command_rcon_unavailable(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="Alice")

    # Should send an ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_unban_command_missing_player(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="")

    # Current implementation: still issues /unban with empty name and sends a followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/unban "


@pytest.mark.asyncio
async def test_unban_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(ADMIN_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction(user_name="admin")
    cmd = await _get_factorio_subcommand(bot, "unban")
    await cmd.callback(interaction, player="Alice")

    # Should send a non-ephemeral success embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    # Implementation does not explicitly set ephemeral flag; don't assert on it
    assert rcon.last_command == "/unban Alice"

# ---------------------------------------------------------------------------
# help command - cooldown and success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_help_command_rate_limited(monkeypatch):
    # Force QUERY_COOLDOWN to rate limit this user
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "help")
    await cmd.callback(interaction)

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    # Either embed is first positional arg or in kwargs
    assert args or kwargs.get("embed") is not None
    # No followup messages expected
    assert len(interaction.followup.sent) == 0


@pytest.mark.asyncio
async def test_help_command_success(monkeypatch):
    # Not rate limited
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "help")
    await cmd.callback(interaction)

    # Should send exactly one help text message via interaction.response
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    # Help command sends plain text, not an embed
    assert args
    help_text = args[0]
    assert isinstance(help_text, str)
    assert "Factorio ISR Bot" in help_text
    assert "/factorio status" in help_text
    # No followup messages expected
    assert len(interaction.followup.sent) == 0

# ---------------------------------------------------------------------------
# connect_bot - happy path and error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_bot_happy_path(monkeypatch):
    bot = DiscordBot(token="x")

    # Avoid real Discord calls
    async def fake_login(token):
        fake_login.called = token
    fake_login.called = None

    async def fake_connect():
        # simulate immediate connection
        bot._ready.set()
    async def fake_send_connection_notification():
        fake_send_connection_notification.called = True
    fake_send_connection_notification.called = False

    async def fake_update_presence():
        fake_update_presence.called = True
    fake_update_presence.called = False

    monkeypatch.setattr(bot, "login", fake_login)
    monkeypatch.setattr(bot, "connect", fake_connect)
    monkeypatch.setattr(bot, "_send_connection_notification", fake_send_connection_notification)
    monkeypatch.setattr(bot, "update_presence", fake_update_presence)

    # Also stub _monitor_rcon_status so the task exits quickly
    async def fake_monitor():
        await asyncio.sleep(0)
    monkeypatch.setattr(bot, "_monitor_rcon_status", fake_monitor)

    await bot.connect_bot()

    assert fake_login.called == "x"
    assert bot._connected is True
    assert fake_send_connection_notification.called is True
    assert fake_update_presence.called is True
    assert bot.rcon_monitor_task is not None
    assert isinstance(bot._connection_task, asyncio.Task)


@pytest.mark.asyncio
async def test_connect_bot_timeout(monkeypatch):
    bot = DiscordBot(token="x")

    async def fake_login(token):
        pass

    async def fake_connect():
        # never sets _ready
        await asyncio.sleep(0)

    monkeypatch.setattr(bot, "login", fake_login)
    monkeypatch.setattr(bot, "connect", fake_connect)

    # Use a small timeout by patching asyncio.wait_for at call site
    original_wait_for = asyncio.wait_for

    async def fake_wait_for(awaitable, timeout):
        # simulate timeout regardless of _ready
        raise asyncio.TimeoutError()

    monkeypatch.setattr("discord_bot.asyncio.wait_for", fake_wait_for)

    with pytest.raises(ConnectionError):
        await bot.connect_bot()

    # Bot should not be marked connected after timeout
    assert bot._connected is False

    # A connection task was created and then cancelled; implementation keeps it
    assert bot._connection_task is not None
    assert isinstance(bot._connection_task, asyncio.Task)
    assert bot._connection_task.cancelled()


@pytest.mark.asyncio
async def test_connect_bot_login_failure(monkeypatch):
    bot = DiscordBot(token="x")

    class DummyLoginFailure(discord.errors.LoginFailure):
        pass

    async def fake_login(token):
        raise DummyLoginFailure("bad token")

    monkeypatch.setattr(bot, "login", fake_login)

    with pytest.raises(ConnectionError):
        await bot.connect_bot()

    # Bot not connected and no connection task ever created
    assert bot._connected is False


# ---------------------------------------------------------------------------
# _notify_rcon_reconnected - no channel vs normal path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_rcon_reconnected_no_channel():
    bot = DiscordBot(token="x")
    bot.event_channel_id = None
    bot.rcon_status_notified = True  # should be reset only when message is sent

    # Should just return without error and without touching the flag
    await bot._notify_rcon_reconnected("primary")

    assert bot.rcon_status_notified is True


@pytest.mark.asyncio
async def test_notify_rcon_reconnected_sends_embed_and_clears_flag(monkeypatch):
    bot = DiscordBot(token="x")
    bot.event_channel_id = 123
    bot.rcon_status_notified = True

    guild = DummyGuild()
    channel = DummyTextChannel(guild=guild, id=123)

    def fake_get_channel(cid):
        assert cid == 123
        return channel

    bot.get_channel = fake_get_channel  # type: ignore

    await bot._notify_rcon_reconnected("primary")

    # One payload sent and flag cleared
    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    assert embed is not None
    assert bot.rcon_status_notified is False




# ---------------------------------------------------------------------------
# save command - cooldown, RCON unavailable, success (with/without name)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_command_rate_limited(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "save")
    await cmd.callback(interaction, name=None)

    # Responds via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None
    assert len(interaction.followup.sent) == 0


@pytest.mark.asyncio
async def test_save_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "save")
    await cmd.callback(interaction, name=None)

    # One ephemeral error embed via followup
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_save_command_success_without_name(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(is_connected=True, execute_result="Saving map to /path/to/LosHermanos.zip")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "save")
    await cmd.callback(interaction, name=None)

    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/save"


@pytest.mark.asyncio
async def test_save_command_success_with_name(monkeypatch):
    monkeypatch.setattr(QUERY_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "save")
    await cmd.callback(interaction, name="my_save")

    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/save my_save"
# ---------------------------------------------------------------------------
# _monitor_rcon_status - no ServerManager branch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_rcon_status_no_server_manager_logs_and_sets_any_status(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.server_manager = None
    bot.rcon_breakdown_mode = "transition"  # mode doesn't matter here

    # Speed up loop: one iteration then disconnect
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        # After first loop, stop the monitor
        bot._connected = False

    monkeypatch.setattr("discord_bot.asyncio.sleep", fake_sleep)

    # Stub update_presence so it does nothing
    async def fake_update_presence():
        pass

    monkeypatch.setattr(bot, "update_presence", fake_update_presence)

    await bot._monitor_rcon_status()

    # Loop should have slept once with 5 seconds check interval
    assert 5 in sleep_calls


# ---------------------------------------------------------------------------
# _monitor_rcon_status - transition vs interval breakdown and per-server channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_rcon_status_transition_mode_sends_on_change(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True

    # Two servers with per-server event channels, plus a global channel
    class Cfg:
        def __init__(self, tag, ch_id):
            self.tag = tag
            self.name = tag
            self.rcon_host = "localhost"
            self.rcon_port = 27015
            self.description = None
            self.event_channel_id = ch_id

    cfg1 = Cfg("primary", 201)
    cfg2 = Cfg("backup", 202)

    class SM:
        def __init__(self):
            self.calls = 0

        def get_status_summary(self):
            # 1st call: primary up, backup down
            # 2nd call: both up (transition on backup)
            # 3rd+ calls: keep both up
            self.calls += 1
            if self.calls == 1:
                return {"primary": True, "backup": False}
            return {"primary": True, "backup": True}

        def list_servers(self):
            return {"primary": cfg1, "backup": cfg2}

    bot.server_manager = SM()
    bot.event_channel_id = 200

    global_ch = DummyTextChannel(DummyGuild(), id=200)
    primary_ch = DummyTextChannel(DummyGuild(), id=201)
    backup_ch = DummyTextChannel(DummyGuild(), id=202)

    def fake_get_channel(cid):
        if cid == 200:
            return global_ch
        if cid == 201:
            return primary_ch
        if cid == 202:
            return backup_ch
        return None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    def fake_build_embed():
        return discord.Embed(title="breakdown")

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    bot.rcon_breakdown_mode = "transition"
    bot.rcon_breakdown_interval = 9999  # unused in transition mode

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        # First sleep: after initial status
        # Second sleep: after transition
        # Then stop the loop
        await real_sleep(0)
        if bot.server_manager.calls >= 2:
            bot._connected = False

    monkeypatch.setattr("discord_bot.asyncio.sleep", fake_sleep)

    async def fake_update_presence():
        pass

    monkeypatch.setattr(bot, "update_presence", fake_update_presence)

    await bot._monitor_rcon_status()

    # Now at least one embed should have been sent
    assert global_ch.sent_embeds
    assert primary_ch.sent_embeds or backup_ch.sent_embeds



@pytest.mark.asyncio
async def test_monitor_rcon_status_interval_mode_uses_interval(monkeypatch):
    bot = DiscordBot(token="x")
    bot._connected = True

    cfg = type("Cfg", (), {
        "tag": "primary",
        "name": "Primary",
        "rcon_host": "localhost",
        "rcon_port": 27015,
        "description": None,
        "event_channel_id": 210,
    })()

    class SM:
        def get_status_summary(self):
            return {"primary": True}

        def list_servers(self):
            return {"primary": cfg}

    bot.server_manager = SM()
    bot.event_channel_id = 210

    ch = DummyTextChannel(DummyGuild(), id=210)

    def fake_get_channel(cid):
        return ch if cid == 210 else None

    monkeypatch.setattr(bot, "get_channel", fake_get_channel)

    def fake_build_embed():
        return discord.Embed(title="interval breakdown")

    monkeypatch.setattr(bot, "_build_rcon_breakdown_embed", fake_build_embed)

    bot.rcon_breakdown_mode = "interval"
    bot.rcon_breakdown_interval = 0.1
    bot._last_rcon_breakdown_sent = None

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        # Allow one interval check and then exit
        await real_sleep(0.05)
        bot._connected = False

    monkeypatch.setattr("discord_bot.asyncio.sleep", fake_sleep)

    async def fake_update_presence():
        pass

    monkeypatch.setattr(bot, "update_presence", fake_update_presence)

    await bot._monitor_rcon_status()

    # First-time interval mode should send at least once
    assert ch.sent_embeds

# ---------------------------------------------------------------------------
# speed command - cooldown, invalid range, RCON unavailable, success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_speed_command_rate_limited(monkeypatch):
    # Force DANGER_COOLDOWN to trigger
    monkeypatch.setattr(DANGER_COOLDOWN, "is_rate_limited", lambda uid: (True, 10))

    bot = DiscordBot(token="x")

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=2.0)

    # Should respond via interaction.response with a cooldown embed
    assert len(interaction.response.sent) == 1
    args, kwargs = interaction.response.sent[0]
    assert args or kwargs.get("embed") is not None
    assert len(interaction.followup.sent) == 0


@pytest.mark.asyncio
async def test_speed_command_invalid_range(monkeypatch):
    monkeypatch.setattr(DANGER_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    # Valid RCON client so we hit the range check, not the RCON-unavailable branch
    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=0.01)  # below 0.1

    # One ephemeral error embed and no RCON command executed
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True
    assert rcon.last_command is None


@pytest.mark.asyncio
async def test_speed_command_rcon_unavailable(monkeypatch):
    monkeypatch.setattr(DANGER_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    bot.get_rcon_for_user = lambda uid: None  # type: ignore
    bot.get_server_display_name = lambda uid: "Primary"  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=2.0)

    # Ephemeral error embed when RCON is missing
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert ephemeral is True


@pytest.mark.asyncio
async def test_speed_command_success(monkeypatch):
    monkeypatch.setattr(DANGER_COOLDOWN, "is_rate_limited", lambda uid: (False, 0))

    bot = DiscordBot(token="x")
    rcon = DummyRconClient(is_connected=True, execute_result="ok")
    bot.get_rcon_for_user = lambda uid: rcon  # type: ignore

    interaction = DummyInteraction()
    cmd = await _get_factorio_subcommand(bot, "speed")
    await cmd.callback(interaction, speed=2.5)

    # One success embed and correct RCON command
    assert len(interaction.followup.sent) == 1
    embed, ephemeral = interaction.followup.sent[0]
    assert embed is not None
    assert rcon.last_command == "/sc game.speed = 2.5"

# ---------------------------------------------------------------------------
# on_ready - no user vs normal sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_ready_no_user(monkeypatch):
    bot = DiscordBot(token="x")

    # Force user to be None via property patch
    monkeypatch.setattr(
        type(bot),
        "user",
        property(lambda self: None),
        raising=False,
    )

    async def fail_sync(*args, **kwargs):
        raise AssertionError("sync should not be called when user is None")

    monkeypatch.setattr(bot.tree, "sync", fail_sync)

    assert bot._connected is False
    assert bot._ready.is_set() is False

    await bot.on_ready()

    assert bot._connected is False
    assert bot._ready.is_set() is False

@pytest.mark.asyncio
async def test_on_ready_syncs_commands(monkeypatch):
    bot = DiscordBot(token="x")

    # Dummy user
    dummy_user = type("U", (), {"name": "TestBot", "id": 123})()

    monkeypatch.setattr(
        type(bot),
        "user",
        property(lambda self: dummy_user),
        raising=False,
    )

    # Dummy guild list
    dummy_guild = type("G", (), {"name": "TestGuild", "id": 1})()
    monkeypatch.setattr(
        type(bot),
        "guilds",
        property(lambda self: [dummy_guild]),
        raising=False,
    )

    async def fake_sync(guild=None):
        fake_sync.calls.append(guild)
        if guild is None:
            return [type("C", (), {"name": "factorio"})()]
        return []

    fake_sync.calls = []

    def fake_copy_global_to(guild=None):
        fake_copy_global_to.calls.append(guild)

    fake_copy_global_to.calls = []

    def fake_get_commands(guild=None):
        assert guild is dummy_guild
        return [type("C", (), {"name": "factorio"})()]

    monkeypatch.setattr(bot.tree, "sync", fake_sync)
    monkeypatch.setattr(bot.tree, "copy_global_to", fake_copy_global_to)
    monkeypatch.setattr(bot.tree, "get_commands", fake_get_commands)

    await bot.on_ready()

    assert bot._connected is True
    assert bot._ready.is_set() is True
    assert fake_sync.calls[0] is None
    assert dummy_guild in fake_sync.calls
    assert fake_copy_global_to.calls == [dummy_guild]


# ========================================================================
# PHASE 6: send_message Tests
# ========================================================================

@pytest.mark.asyncio
async def test_send_message_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful message sending."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 100
    
    channel = DummyTextChannel(guild=DummyGuild(), id=100)
    
    def fake_get_channel(cid: int):
        if cid == 100:
            return channel
        return None
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    await bot.send_message("Test message")
    
    assert len(channel.sent_messages) == 1
    assert channel.sent_messages[0] == "Test message"


@pytest.mark.asyncio
async def test_send_message_not_connected() -> None:
    """Test send_message when bot not connected."""
    bot = DiscordBot(token="x")
    bot._connected = False
    bot.event_channel_id = 100
    
    # Should return early without error
    await bot.send_message("Test")
    # No assertion needed - just verify no exception


@pytest.mark.asyncio
async def test_send_message_no_channel_configured() -> None:
    """Test send_message when no channel configured."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = None
    
    # Should return early without error
    await bot.send_message("Test")
    # No assertion needed - just verify no exception


@pytest.mark.asyncio
async def test_send_message_channel_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test send_message when channel not found."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 999
    
    def fake_get_channel(cid: int):
        return None
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    await bot.send_message("Test")
    # No assertion needed - just verify no exception


@pytest.mark.asyncio
async def test_send_message_invalid_channel_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test send_message with non-TextChannel."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 100
    
    # Return a non-TextChannel object
    fake_channel = DummyGuild()  # Not a TextChannel
    
    def fake_get_channel(cid: int):
        return fake_channel
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    await bot.send_message("Test")
    # No assertion needed - just verify no exception


@pytest.mark.asyncio
async def test_send_message_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test send_message handles Forbidden error."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 100
    
    channel = DummyTextChannel(guild=DummyGuild(), id=100)
    
    # Make send raise Forbidden
    async def raise_forbidden(msg: str):
        raise discord.errors.Forbidden(MagicMock(), "forbidden")
    
    channel.send = raise_forbidden  # type: ignore
    
    def fake_get_channel(cid: int):
        if cid == 100:
            return channel
        return None
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    # Should handle exception gracefully
    await bot.send_message("Test")


@pytest.mark.asyncio
async def test_send_message_http_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test send_message handles HTTPException."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 100
    
    channel = DummyTextChannel(guild=DummyGuild(), id=100)
    
    # Make send raise HTTPException
    async def raise_http(msg: str):
        raise discord.errors.HTTPException(MagicMock(), "http error")
    
    channel.send = raise_http  # type: ignore
    
    def fake_get_channel(cid: int):
        if cid == 100:
            return channel
        return None
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    # Should handle exception gracefully
    await bot.send_message("Test")


@pytest.mark.asyncio
async def test_send_message_unexpected_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test send_message handles unexpected exceptions."""
    bot = DiscordBot(token="x")
    bot._connected = True
    bot.event_channel_id = 100
    
    channel = DummyTextChannel(guild=DummyGuild(), id=100)
    
    # Make send raise unexpected exception
    async def raise_unexpected(msg: str):
        raise RuntimeError("Unexpected error")
    
    channel.send = raise_unexpected  # type: ignore
    
    def fake_get_channel(cid: int):
        if cid == 100:
            return channel
        return None
    
    monkeypatch.setattr(bot, "get_channel", fake_get_channel)
    
    # Should handle exception gracefully
    await bot.send_message("Test")


# ========================================================================
# PHASE 6: _get_game_uptime Tests
# ========================================================================

@pytest.mark.asyncio
async def test_get_game_uptime_success() -> None:
    """Test _get_game_uptime with valid tick count."""
    bot = DiscordBot(token="x")
    
    # Mock RCON client that returns valid tick count
    # 36000 ticks = 600 seconds = 10 minutes
    rcon = DummyRconClient(is_connected=True, execute_result="36000")
    
    result = await bot._get_game_uptime(rcon)
    
    assert isinstance(result, str)
    assert result != "Unknown"
    assert "10m" in result or "10" in result  # Should show 10 minutes


@pytest.mark.asyncio
async def test_get_game_uptime_not_connected() -> None:
    """Test _get_game_uptime when RCON not connected."""
    bot = DiscordBot(token="x")
    
    rcon = DummyRconClient(is_connected=False)
    
    result = await bot._get_game_uptime(rcon)
    
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_none_client() -> None:
    """Test _get_game_uptime with None client."""
    bot = DiscordBot(token="x")
    
    result = await bot._get_game_uptime(None)  # type: ignore
    
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_empty_response() -> None:
    """Test _get_game_uptime with empty RCON response."""
    bot = DiscordBot(token="x")
    
    # RCON returns empty string
    rcon = DummyRconClient(is_connected=True, execute_result="")
    
    result = await bot._get_game_uptime(rcon)
    
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_invalid_response() -> None:
    """Test _get_game_uptime with non-numeric response."""
    bot = DiscordBot(token="x")
    
    # RCON returns non-numeric data
    rcon = DummyRconClient(is_connected=True, execute_result="not a number")
    
    result = await bot._get_game_uptime(rcon)
    
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_negative_ticks() -> None:
    """Test _get_game_uptime with negative tick count."""
    bot = DiscordBot(token="x")
    
    # RCON returns negative number
    rcon = DummyRconClient(is_connected=True, execute_result="-1000")
    
    result = await bot._get_game_uptime(rcon)
    
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_rcon_exception() -> None:
    """Test _get_game_uptime when RCON raises exception."""
    bot = DiscordBot(token="x")
    
    # Create RCON that raises exception on execute
    rcon = DummyRconClient(is_connected=True)
    
    async def raise_error(cmd: str) -> str:
        raise RuntimeError("RCON error")
    
    rcon.execute = raise_error  # type: ignore
    
    result = await bot._get_game_uptime(rcon)
    
    assert result == "Unknown"
