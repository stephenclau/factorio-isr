"""
Configuration management for Factorio ISR.

Supports both single-server (legacy) and multi-server modes.
"""

import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dotenv import load_dotenv

import structlog

logger = structlog.get_logger()


def read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a secret from multiple sources (local dev + Docker).

    Checks in order:
    1. `.secrets/{secret_name}.txt` (local development)
    2. `.secrets/{secret_name}` (local development)
    3. `/run/secrets/{secret_name}` (Docker secrets)

    Returns:
        Secret value as string, or None if not found
    """
    # Local dev (.txt extension)
    local_txt = Path(".secrets") / f"{secret_name}.txt"
    if local_txt.exists():
        try:
            value = local_txt.read_text().strip()
            if value:  # Only return non-empty
                logger.debug("loaded_secret", secret_name=secret_name, source=str(local_txt))
                return value
        except Exception as e:
            logger.warning(
                "failed_to_read_secret",
                secret_name=secret_name,
                source=str(local_txt),
                error=str(e),
            )

    # Local dev (no extension)
    local_plain = Path(".secrets") / secret_name
    if local_plain.exists():
        try:
            value = local_plain.read_text().strip()
            if value:
                logger.debug("loaded_secret", secret_name=secret_name, source=str(local_plain))
                return value
        except Exception as e:
            logger.warning(
                "failed_to_read_secret",
                secret_name=secret_name,
                source=str(local_plain),
                error=str(e),
            )

    # Docker secrets
    docker_secret = Path("/run/secrets") / secret_name
    if docker_secret.exists():
        try:
            value = docker_secret.read_text().strip()
            if value:
                logger.debug(
                    "loaded_secret",
                    secret_name=secret_name,
                    source="docker_secrets",
                )
                return value
        except Exception as e:
            logger.warning(
                "failed_to_read_secret",
                secret_name=secret_name,
                source="docker_secrets",
                error=str(e),
            )

    return default


def get_config_value(
    key: str,
    default: Optional[str] = None,
    required: bool = False,
) -> Optional[str]:
    """
    Get configuration value with priority: secrets > env vars > default.
    """
    # Priority 1: Secrets (file-based)
    value = read_secret(key)

    # Priority 2: Environment variable
    if value is None:
        value = os.getenv(key)
        if value:
            logger.debug("loaded_config", key=key, source="environment")

    # Priority 3: Default
    if value is None:
        value = default
        if value is not None:
            logger.debug("loaded_config", key=key, source="default")

    if value is None and required:
        raise ValueError(f"Required configuration key not found: {key}")

    return value


@dataclass
class ServerConfig:
    """
    Configuration for a single Factorio server.
    """
    tag: str  # Primary ID (e.g., "prod", "stg", "lh")
    name: str  # Display name
    rcon_host: str
    rcon_port: int
    rcon_password: str
    description: Optional[str] = None
    event_channel_id: Optional[int] = None
    stats_interval: int = 300

    # RCON breakdown embed settings per server
    rcon_breakdown_mode: str = "transition"  # "transition" or "interval"
    rcon_breakdown_interval: int = 300  # seconds

    # Metrics collection flags
    collect_ups: bool = True
    collect_evolution: bool = True

    # Alert configuration
    enable_alerts: bool = True
    alert_check_interval: int = 60  # Check UPS every 60 seconds
    alert_samples_required: int = 3  # Require 3 consecutive bad samples
    ups_warning_threshold: float = 55.0  # Alert when UPS < 55
    ups_recovery_threshold: float = 58.0  # Recovery when UPS >= 58
    alert_cooldown: int = 300  # 5 min between repeat alerts
    ups_ema_alpha: float = 0.2  # EMA smoothing factor for UPS
    
    def __post_init__(self) -> None:
        """
        Validate tag format on initialization.
        """
        if not self.tag:
            raise ValueError("Server tag cannot be empty")

        # Lowercase alphanumeric + hyphens, 1–16 chars
        if not re.match(r"^[a-z0-9-]{1,16}$", self.tag):
            raise ValueError(
                f"Invalid tag {self.tag}: must be lowercase alphanumeric with "
                "hyphens only, 1-16 characters (e.g., 'prod', 'los-hermanos')"
            )

        if not self.name:
            raise ValueError(f"Server name cannot be empty for tag {self.tag}")

        if self.rcon_port < 1 or self.rcon_port > 65535:
            raise ValueError(f"Invalid RCON port {self.rcon_port} for server {self.tag}")

    @property
    def display_name(self) -> str:
        """
        Get display name with optional description.
        """
        if self.description:
            return f"{self.name} ({self.description})"
        return self.name


def parse_servers_from_yaml(yaml_path: Path) -> Optional[Dict[str, ServerConfig]]:
    """
    Parse servers from YAML file with secrets support.

    Expected format:
        servers:
          prod:
            name: "Production"
            description: "Main 24/7 server"
            rcon_host: "factorio-prod"
            rcon_port: 27015
            rcon_password: "secret123"  # Optional - falls back to secrets
            event_channel_id: 123456789
            stats_interval: 300

    Args:
        yaml_path: Path to YAML configuration file

    Returns:
        Dictionary of tag -> ServerConfig or None if file doesn't exist or parse fails.
    """
    if not yaml_path.exists():
        logger.debug("yaml_file_not_found", path=str(yaml_path))
        return None

    try:
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "servers" not in data:
            logger.warning("yaml_missing_servers_key", path=str(yaml_path))
            return None

        servers: Dict[str, ServerConfig] = {}

        for tag, server_data in data["servers"].items():
            try:
                # Enforce tag naming rules
                if not re.match(r"^[a-z0-9-]{1,16}$", tag):
                    raise ValueError(
                        f"Invalid tag '{tag}': must be lowercase alphanumeric "
                        "with hyphens only, 1–16 characters"
                    )

                # Get RCON password with fallback to secrets
                rcon_password = server_data.get("rcon_password")

                # If password is missing or empty in YAML, try secrets
                if not rcon_password:
                    # Try server-specific secret first: RCON_PASSWORD_{TAG}
                    secret_name = f"RCON_PASSWORD_{tag.upper()}"
                    rcon_password = read_secret(secret_name)

                    # Fall back to generic RCON_PASSWORD
                    if not rcon_password:
                        rcon_password = read_secret("RCON_PASSWORD")

                    if rcon_password:
                        logger.info(
                            "rcon_password_loaded_from_secrets",
                            tag=tag,
                            secret_name=secret_name if read_secret(secret_name) else "RCON_PASSWORD",
                        )

                # Coerce to empty string if still None to satisfy type checker;
                # validation later ensures servers require passwords in multi-server mode.
                rcon_password_value = rcon_password or ""

                servers[tag] = ServerConfig(
                    tag=tag,
                    name=server_data["name"],
                    rcon_host=server_data["rcon_host"],
                    rcon_port=server_data.get("rcon_port", 27015),
                    rcon_password=rcon_password_value,
                    description=server_data.get("description"),
                    event_channel_id=server_data.get("event_channel_id"),
                    stats_interval=server_data.get("stats_interval", 300),
                    rcon_breakdown_mode=server_data.get("rcon_breakdown_mode", "transition").lower(),
                    rcon_breakdown_interval=int(server_data.get("rcon_breakdown_interval", 300)),
                    
                    # Metrics and alert configuration
                    collect_ups=server_data.get("collect_ups", True),
                    collect_evolution=server_data.get("collect_evolution", True),
                    enable_alerts=server_data.get("enable_alerts", True),
                    alert_check_interval=int(server_data.get("alert_check_interval", 60)),
                    alert_samples_required=int(server_data.get("alert_samples_required", 3)),
                    ups_warning_threshold=float(server_data.get("ups_warning_threshold", 55.0)),
                    ups_recovery_threshold=float(server_data.get("ups_recovery_threshold", 58.0)),
                    alert_cooldown=int(server_data.get("alert_cooldown", 300)),
                    ups_ema_alpha=float(server_data.get("ups_ema_alpha", 0.2)),
                    
                )

            except Exception as e:
                logger.error(
                    "failed_to_parse_server_config",
                    tag=tag,
                    error=str(e),
                    path=str(yaml_path),
                )
                raise

        logger.info("servers_loaded_from_yaml", count=len(servers), path=str(yaml_path))
        return servers

    except ImportError:
        logger.error(
            "yaml_library_not_available",
            message="Install PyYAML: pip install pyyaml",
            path=str(yaml_path),
        )
        return None

    except Exception as e:
        logger.error("failed_to_parse_servers_yaml", path=str(yaml_path), error=str(e))
        return None


def parse_servers_from_json(json_str: Optional[str]) -> Optional[Dict[str, ServerConfig]]:
    """
    Parse servers from JSON environment variable.

    Expected format:
    {
        "prod": {
            "name": "Production",
            "rcon_host": "factorio-prod",
            "rcon_port": 27015,
            "rcon_password": "secret123"
        }
    }

    Args:
        json_str: JSON string with server configurations

    Returns:
        Dictionary of tag -> ServerConfig or None if parsing fails or input is None.
    """
    if not json_str:
        return None

    try:
        data = json.loads(json_str)
        servers: Dict[str, ServerConfig] = {}

        for tag, server_data in data.items():
            rcon_password_value = server_data.get("rcon_password") or ""

            servers[tag] = ServerConfig(
                tag=tag,
                name=server_data["name"],
                rcon_host=server_data["rcon_host"],
                rcon_port=server_data.get("rcon_port", 27015),
                rcon_password=rcon_password_value,
                description=server_data.get("description"),
                event_channel_id=server_data.get("event_channel_id"),
                stats_interval=server_data.get("stats_interval", 300),
                rcon_breakdown_mode=server_data.get("rcon_breakdown_mode", "transition").lower(),
                rcon_breakdown_interval=int(server_data.get("rcon_breakdown_interval", 300)),
                # Metrics and alert configuration
                collect_ups=server_data.get("collect_ups", True),
                collect_evolution=server_data.get("collect_evolution", True),
                enable_alerts=server_data.get("enable_alerts", True),
                alert_check_interval=int(server_data.get("alert_check_interval", 60)),
                alert_samples_required=int(server_data.get("alert_samples_required", 3)),
                ups_warning_threshold=float(server_data.get("ups_warning_threshold", 55.0)),
                ups_recovery_threshold=float(server_data.get("ups_recovery_threshold", 58.0)),
                alert_cooldown=int(server_data.get("alert_cooldown", 300)),
            )

        logger.info("servers_loaded_from_json", count=len(servers))
        return servers

    except json.JSONDecodeError as e:
        logger.error("invalid_json_in_servers_config", error=str(e))
        return None

    except Exception as e:
        logger.error("failed_to_parse_servers_json", error=str(e))
        return None


def parse_webhook_channels(channels_str: Optional[str]) -> Dict[str, str]:
    """
    Parse webhook channels from JSON string.
    """
    if not channels_str:
        return {}

    try:
        channels = json.loads(channels_str)
        if not isinstance(channels, dict):
            return {}
        return channels
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_pattern_files(files_str: Optional[str]) -> Optional[List[str]]:
    """
    Parse pattern files from JSON string.
    """
    if not files_str:
        return None

    try:
        files = json.loads(files_str)
        if not isinstance(files, list):
            return None
        return files
    except (json.JSONDecodeError, TypeError):
        return None


@dataclass
class Config:
    """
    Configuration for Factorio ISR.
    """
    # Discord
    discord_webhook_url: Optional[str] = None
    discord_bot_token: Optional[str] = None
    discord_event_channel_id: Optional[int] = None

    # Bot settings
    bot_name: str = "Factorio ISR"
    bot_avatar_url: Optional[str] = None

    # Factorio
    factorio_log_path: Path = Path("logs/console.log")

    # Logging
    log_level: str = "info"
    log_format: str = "console"

    # Health check
    health_check_host: str = "0.0.0.0"
    health_check_port: int = 8080

    # Event patterns
    patterns_dir: Path = field(default_factory=lambda: Path("patterns"))
    pattern_files: Optional[List[str]] = None

    # Webhook channels
    webhook_channels: Dict[str, str] = field(default_factory=dict)
    send_test_message: bool = False

    # RCON - Legacy single-server backward compatible
    rcon_enabled: bool = False
    rcon_host: str = "localhost"
    rcon_port: int = 27015
    rcon_password: Optional[str] = None
    stats_interval: int = 300

    # RCON breakdown embed settings (global)
    rcon_breakdown_mode: str = "transition"  # "transition" or "interval"
    rcon_breakdown_interval: int = 300  # seconds (5 minutes default)

    # Multi-server
    servers: Optional[Dict[str, ServerConfig]] = None  # tag -> ServerConfig

    @property
    def is_multi_server(self) -> bool:
        """
        Check if multi-server mode is enabled.
        """
        return self.servers is not None and len(self.servers) > 0


def load_config() -> Config:
    """
    Load configuration from environment variables and Docker secrets.
    """
    # Load .env from current working directory
    load_dotenv()

    # Discord configuration - at least one mode required
    webhook_url = get_config_value("DISCORD_WEBHOOK_URL")
    bot_token = get_config_value("DISCORD_BOT_TOKEN")

    if not webhook_url and not bot_token:
        raise ValueError("Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN must be configured")

    # Required: Factorio log path
    factorio_log_path = get_config_value("FACTORIO_LOG_PATH")
    if not factorio_log_path:
        raise ValueError("FACTORIO_LOG_PATH is required")

    # Optional fields with defaults
    bot_name = get_config_value("BOT_NAME") or "Factorio ISR"
    log_level = (get_config_value("LOG_LEVEL") or "info").lower()
    log_format = (get_config_value("LOG_FORMAT") or "console").lower()
    health_check_host = get_config_value("health_check_host") or "0.0.0.0"
    health_check_port_str = get_config_value("health_check_port") or "8080"
    patterns_dir_str = get_config_value("PATTERNS_DIR") or "patterns"

    # RCON legacy settings
    rcon_host = get_config_value("RCON_HOST") or "localhost"
    rcon_port_str = get_config_value("RCON_PORT") or "27015"
    stats_interval_str = get_config_value("STATS_INTERVAL") or "300"

    # RCON breakdown embed configuration
    breakdown_mode = get_config_value("RCON_BREAKDOWN_MODE") or "transition"
    breakdown_interval_str = get_config_value("RCON_BREAKDOWN_INTERVAL") or "300"

    # Boolean flags
    send_test_str = get_config_value("SEND_TEST_MESSAGE") or "false"
    rcon_enabled_str = get_config_value("RCON_ENABLED") or "false"

    # Parse complex fields
    webhook_channels_str = get_config_value("WEBHOOK_CHANNELS") or "{}"
    channel_id_str = get_config_value("DISCORD_EVENT_CHANNEL_ID")
    event_channel_id = int(channel_id_str) if channel_id_str else None

    # ===== MULTI-SERVER CONFIGURATION (NEW) =====
    servers: Optional[Dict[str, ServerConfig]] = None

    # Priority 1: Load from YAML file
    servers_config_path = get_config_value("SERVERS_CONFIG", default="servers.yml")
    if servers_config_path:
        yaml_path = Path(servers_config_path)
        servers = parse_servers_from_yaml(yaml_path)

    # Priority 2: Load from JSON environment variable
    if servers is None:
        servers_json = get_config_value("SERVERS")
        servers = parse_servers_from_json(servers_json)

    # Priority 3: Auto-convert legacy single-server config to multi-server
    if servers is None and rcon_enabled_str.lower() == "true":
        rcon_password = get_config_value("RCON_PASSWORD")
        if rcon_password:
            logger.info("auto_converting_legacy_single_server_to_multi_server")
            servers = {
                "primary": ServerConfig(
                    tag="primary",
                    name="Primary Server",
                    description="Legacy single-server configuration",
                    rcon_host=rcon_host,
                    rcon_port=int(rcon_port_str),
                    rcon_password=rcon_password,
                    event_channel_id=event_channel_id,
                    stats_interval=int(stats_interval_str),
                    rcon_breakdown_mode=breakdown_mode.lower(),
                    rcon_breakdown_interval=int(breakdown_interval_str),
                )
            }

    return Config(
        discord_webhook_url=webhook_url,
        discord_bot_token=bot_token,
        discord_event_channel_id=event_channel_id,
        factorio_log_path=Path(factorio_log_path),
        bot_name=bot_name,
        bot_avatar_url=get_config_value("BOT_AVATAR_URL"),
        log_level=log_level,
        log_format=log_format,
        health_check_host=health_check_host,
        health_check_port=int(health_check_port_str),
        patterns_dir=Path(patterns_dir_str),
        pattern_files=parse_pattern_files(get_config_value("PATTERN_FILES")),
        webhook_channels=parse_webhook_channels(webhook_channels_str),
        send_test_message=send_test_str.lower() == "true",
        rcon_enabled=rcon_enabled_str.lower() == "true",
        rcon_host=rcon_host,
        rcon_port=int(rcon_port_str),
        rcon_password=get_config_value("RCON_PASSWORD"),
        stats_interval=int(stats_interval_str),
        rcon_breakdown_mode=breakdown_mode.lower(),
        rcon_breakdown_interval=int(breakdown_interval_str),
        servers=servers,  # Multi-server support
    )


def validate_config(config: Config) -> bool:
    """
    Validate configuration values.

    Args:
        config: Config object to validate

    Returns:
        True if valid, False otherwise.
    """
    # Validate Discord configuration
    if config.discord_webhook_url is not None:
        if not config.discord_webhook_url.startswith("https://discord.com/api/webhooks"):
            logger.error(
                "validation_failed",
                reason="invalid_webhook_url_format",
            )
            return False

    if config.discord_bot_token is not None:
        if len(config.discord_bot_token) < 50:
            # Bot tokens are typically ~70 chars; this is a soft warning.
            logger.warning(
                "validation_warning",
                reason="bot_token_seems_too_short",
            )

    if not config.discord_webhook_url and not config.discord_bot_token:
        logger.error(
            "validation_failed",
            reason="no_discord_configuration",
        )
        return False

    # Validate log level
    if config.log_level not in ("debug", "info", "warning", "error", "critical"):
        logger.warning(
            "invalid_log_level",
            level=config.log_level,
            defaulting_to="info",
        )
        config.log_level = "info"

    # Validate RCON legacy configuration (single-server)
    if config.rcon_enabled and not config.rcon_password and not config.is_multi_server:
        logger.error(
            "validation_failed",
            reason="rcon_enabled_but_no_password",
        )
        return False

    # Validate multi-server configuration
    if config.is_multi_server and config.servers is not None:
        for tag, server_config in config.servers.items():
            if not server_config.rcon_password:
                logger.error(
                    "validation_failed",
                    reason="server_missing_rcon_password",
                    tag=tag,
                    name=server_config.name,
                )
                return False

    return True
