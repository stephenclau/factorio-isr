# Copyright (c) 2025 Stephen Clau

# This file is part of Factorio ISR.

# Factorio ISR is dual-licensed:

# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for full terms

# 2. Commercial License
# For proprietary use without AGPL requirements
# Contact: licensing@laudiversified.com

# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""
Configuration module for Factorio ISR.

Multi-server architecture:
- servers.yml is MANDATORY (contains all server definitions)
- Discord bot token is REQUIRED (bot mode only)
- Per-server event channels and RCON endpoints
- Unified pattern loading across all servers
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import os
import yaml
import structlog

logger = structlog.get_logger()


def _safe_int(value: Any, field_name: str, default: int) -> int:
    """
    Safely convert value to int with proper type checking.
    
    Args:
        value: Value to convert (can be None, int, or str)
        field_name: Field name for error messages
        default: Default value if None
        
    Returns:
        Converted int value
        
    Raises:
        ValueError: If conversion fails
    """
    if value is None:
        return default
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Invalid integer for {field_name}: {value}")
    
    raise ValueError(f"Cannot convert {field_name} to int: {type(value).__name__}")


def _safe_float(value: Any, field_name: str, default: float) -> float:
    """
    Safely convert value to float with proper type checking.
    
    Args:
        value: Value to convert (can be None, float, int, or str)
        field_name: Field name for error messages
        default: Default value if None
        
    Returns:
        Converted float value
        
    Raises:
        ValueError: If conversion fails
    """
    if value is None:
        return default
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"Invalid float for {field_name}: {value}")
    
    raise ValueError(f"Cannot convert {field_name} to float: {type(value).__name__}")


@dataclass
class ServerConfig:
    """Per-server configuration."""

    name: str
    """Server friendly name (e.g., 'Production', 'Staging')."""

    tag: str
    """Server tag for routing (e.g., 'prod', 'dev'). Must be unique across servers.yml."""

    log_path: Path
    """Path to Factorio console.log file for this server."""

    rcon_host: str
    """RCON host address."""

    rcon_port: int
    """RCON port."""

    rcon_password: str
    """RCON password."""

    event_channel_id: int
    """Discord channel ID for game events (joins, chats, deaths, etc.)."""

    def __post_init__(self) -> None:
        """Validate server config after initialization."""
        if not isinstance(self.log_path, Path):
            self.log_path = Path(self.log_path)

        if not self.tag or not self.tag.replace("_", "").isalnum():
            raise ValueError(
                f"Server tag must be alphanumeric (with underscores): {self.tag}"
            )

        if not 1 <= self.rcon_port <= 65535:
            raise ValueError(f"Invalid RCON port: {self.rcon_port}")

        if not self.rcon_password:
            raise ValueError(f"Server {self.tag}: RCON password cannot be empty")


@dataclass
class Config:
    """Main application configuration."""

    # Discord configuration (bot mode only)
    discord_bot_token: str
    """Discord bot token (required for multi-server mode)."""

    bot_name: str
    """Discord bot display name."""

    bot_avatar_url: Optional[str] = None
    """Optional Discord bot avatar URL."""

    discord_webhook_url: Optional[str] = None
    """Deprecated: webhook mode is not supported. Use bot mode only."""

    # Factorio log configuration
    factorio_log_path: Path = field(default_factory=lambda: Path("/tmp/console.log"))
    """Legacy: single server log path (deprecated - use servers.yml)."""

    # Servers configuration (REQUIRED for multi-server mode)
    servers: Optional[Dict[str, ServerConfig]] = None
    """Dictionary of server tag -> ServerConfig. REQUIRED for multi-server operation."""

    # Event parsing configuration
    patterns_dir: Path = field(default_factory=lambda: Path("config/patterns"))
    """Directory containing YAML event pattern files."""

    pattern_files: Optional[list[str]] = None
    """Optional list of specific pattern files to load (defaults to all .yml in patterns_dir)."""

    # Health check configuration
    health_check_host: str = "0.0.0.0"
    """Health check server bind address."""

    health_check_port: int = 8080
    """Health check server port."""

    # Logging configuration
    log_level: str = "info"
    """Logging level: debug, info, warning, error, critical."""

    log_format: str = "console"
    """Logging format: 'console' or 'json'."""

    # Optional test mode
    send_test_message: bool = False
    """Send test message on Discord connect (for validation)."""

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Convert log_path to Path if needed
        if isinstance(self.factorio_log_path, str):
            self.factorio_log_path = Path(self.factorio_log_path)

        # Convert patterns_dir to Path if needed
        if isinstance(self.patterns_dir, str):
            self.patterns_dir = Path(self.patterns_dir)

        # Validate servers config is present
        if not self.servers:
            raise ValueError("servers configuration is REQUIRED - multi-server mode is mandatory")

        if not isinstance(self.servers, dict) or len(self.servers) == 0:
            raise ValueError("servers must be a non-empty dictionary")

        # Validate each server config
        for tag, server_config in self.servers.items():
            if not isinstance(server_config, ServerConfig):
                raise ValueError(f"servers['{tag}'] must be ServerConfig instance")

            if server_config.tag != tag:
                raise ValueError(
                    f"Server tag mismatch: key '{tag}' vs config.tag '{server_config.tag}'"
                )

        # Validate Discord bot token
        if not self.discord_bot_token:
            raise ValueError("discord_bot_token is REQUIRED (bot mode only)")

        # Warn if webhook URL is provided (legacy)
        if self.discord_webhook_url:
            logger.warning(
                "webhook_mode_deprecated",
                message="Webhook mode is deprecated - use discord_bot_token for bot mode",
            )

        # Validate logging settings
        valid_levels = {"debug", "info", "warning", "error", "critical"}
        if self.log_level.lower() not in valid_levels:
            raise ValueError(f"Invalid log_level: {self.log_level}")

        valid_formats = {"console", "json"}
        if self.log_format.lower() not in valid_formats:
            raise ValueError(f"Invalid log_format: {self.log_format}")

        # Validate health check settings
        if not 1 <= self.health_check_port <= 65535:
            raise ValueError(f"Invalid health_check_port: {self.health_check_port}")

        logger.info(
            "config_validated",
            servers_count=len(self.servers),
            patterns_dir=str(self.patterns_dir),
            log_level=self.log_level,
        )


def load_config() -> Config:
    """
    Load configuration from environment and servers.yml.

    Environment variables:
    - DISCORD_BOT_TOKEN: Discord bot token (required)
    - BOT_NAME: Discord bot display name (default: "Factorio ISR")
    - BOT_AVATAR_URL: Discord bot avatar URL (optional)
    - FACTORIO_LOG_PATH: Legacy single server log path (deprecated)
    - PATTERNS_DIR: Event patterns directory (default: config/patterns)
    - PATTERN_FILES: Comma-separated pattern filenames to load (optional)
    - HEALTH_CHECK_HOST: Health check bind address (default: 0.0.0.0)
    - HEALTH_CHECK_PORT: Health check port (default: 8080)
    - LOG_LEVEL: Logging level (default: info)
    - LOG_FORMAT: Logging format (default: console)
    - SEND_TEST_MESSAGE: Send test Discord message (default: false)
    - CONFIG_DIR: Configuration directory (default: config)

    servers.yml location: CONFIG_DIR/servers.yml

    Returns:
        Config instance with all settings loaded and validated.

    Raises:
        ValueError: If required configuration is missing or invalid.
        FileNotFoundError: If servers.yml does not exist.
    """
    config_dir = Path(os.getenv("CONFIG_DIR", "config"))
    servers_yml = config_dir / "servers.yml"

    logger.info("loading_config", config_dir=str(config_dir))

    # Load servers.yml (REQUIRED)
    if not servers_yml.exists():
        raise FileNotFoundError(
            f"servers.yml not found at {servers_yml}. "
            "Multi-server configuration is REQUIRED. "
            f"Create {servers_yml} with at least one server definition."
        )

    try:
        with open(servers_yml, "r") as f:
            servers_data = yaml.safe_load(f)

        if not servers_data or "servers" not in servers_data:
            raise ValueError("servers.yml must contain 'servers' section")

        servers_dict: Dict[str, ServerConfig] = {}

        for tag, server_def in servers_data["servers"].items():
            if not isinstance(server_def, dict):
                raise ValueError(f"servers.{tag} must be a dictionary")

            # Convert log_path to absolute if relative
            log_path = Path(server_def.get("log_path", "console.log"))
            if not log_path.is_absolute():
                log_path = config_dir / log_path

            # Convert env vars in RCON password (support ${VAR_NAME})
            rcon_password = server_def.get("rcon_password", "")
            if isinstance(rcon_password, str) and rcon_password.startswith("${") and rcon_password.endswith("}"):
                env_var = rcon_password[2:-1]
                rcon_password = os.getenv(env_var, "")
                if not rcon_password:
                    raise ValueError(
                        f"servers.{tag}: rcon_password references ${env_var} but it's not set"
                    )

            # ✅ FIX: Use safe conversion functions for all int fields
            servers_dict[tag] = ServerConfig(
                name=server_def.get("name", tag),
                tag=tag,
                log_path=log_path,
                rcon_host=server_def.get("rcon_host", "localhost"),
                rcon_port=_safe_int(server_def.get("rcon_port"), "rcon_port", 27015),
                rcon_password=rcon_password,
                event_channel_id=_safe_int(server_def.get("event_channel_id"), "event_channel_id", 0),
            )

        logger.info(
            "servers_yml_loaded",
            servers_count=len(servers_dict),
            servers=list(servers_dict.keys()),
        )

    except yaml.YAMLError as e:
        raise ValueError(f"servers.yml parse error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load servers.yml: {e}")

    # Load from environment
    discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_bot_token:
        raise ValueError(
            "DISCORD_BOT_TOKEN environment variable is REQUIRED (bot mode only)"
        )

    bot_name = os.getenv("BOT_NAME", "Factorio ISR")
    bot_avatar_url = os.getenv("BOT_AVATAR_URL")

    factorio_log_path = Path(
        os.getenv("FACTORIO_LOG_PATH", "/tmp/console.log")
    )

    patterns_dir = Path(os.getenv("PATTERNS_DIR", str(config_dir / "patterns")))

    pattern_files_str = os.getenv("PATTERN_FILES")
    pattern_files = (
        [f.strip() for f in pattern_files_str.split(",")]
        if pattern_files_str
        else None
    )

    health_check_host = os.getenv("HEALTH_CHECK_HOST", "0.0.0.0")
    health_check_port_str = os.getenv("HEALTH_CHECK_PORT", "8080")

    log_level = os.getenv("LOG_LEVEL", "info")
    log_format = os.getenv("LOG_FORMAT", "console")

    send_test_message = os.getenv("SEND_TEST_MESSAGE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # ✅ FIX: Use safe conversion for port
    health_check_port = _safe_int(health_check_port_str, "health_check_port", 8080)

    logger.info(
        "config_loaded_from_env",
        bot_name=bot_name,
        health_check_port=health_check_port,
        log_level=log_level,
    )

    # Create and validate Config
    config = Config(
        discord_bot_token=discord_bot_token,
        bot_name=bot_name,
        bot_avatar_url=bot_avatar_url,
        factorio_log_path=factorio_log_path,
        servers=servers_dict,
        patterns_dir=patterns_dir,
        pattern_files=pattern_files,
        health_check_host=health_check_host,
        health_check_port=health_check_port,
        log_level=log_level,
        log_format=log_format,
        send_test_message=send_test_message,
    )

    return config


def validate_config(config: Config) -> bool:
    """
    Validate configuration consistency.

    Args:
        config: Config instance to validate

    Returns:
        True if config is valid, False otherwise.
    """
    try:
        # Check servers are non-empty
        if not config.servers or len(config.servers) == 0:
            logger.error("config_validation_failed", reason="no_servers_configured")
            return False

        # Check each server has required fields
        for tag, server_config in config.servers.items():
            if not server_config.rcon_host or not server_config.rcon_port:
                logger.error(
                    "config_validation_failed",
                    reason=f"server_{tag}_missing_rcon",
                )
                return False

            if not server_config.event_channel_id:
                logger.error(
                    "config_validation_failed",
                    reason=f"server_{tag}_missing_event_channel_id",
                )
                return False

        # Check Discord bot token
        if not config.discord_bot_token:
            logger.error(
                "config_validation_failed", reason="missing_discord_bot_token"
            )
            return False

        # Check patterns directory exists
        if not config.patterns_dir.exists():
            logger.warning(
                "patterns_directory_not_found",
                path=str(config.patterns_dir),
            )
            # Don't fail - patterns will be loaded empty or created on demand

        logger.info("config_validation_passed")
        return True

    except Exception as e:
        logger.error("config_validation_error", error=str(e), exc_info=True)
        return False
