# Copyright (c) 2025 Stephen Clau

# This file is part of Factorio ISR.

# Factorio ISR is dual-licensed:

# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms

# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com

# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""
Configuration module for Factorio ISR.

Multi-server architecture:
- servers.yml is MANDATORY (contains all server definitions)
- Discord bot token is REQUIRED (bot mode only)
- Per-server event channels and RCON endpoints
- Unified pattern loading across all servers
- Docker secrets support: reads from /run/secrets/* and env vars
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import os
import yaml
import structlog

logger = structlog.get_logger()


def _read_docker_secret(secret_name: str) -> Optional[str]:
    """
    Read a secret from Docker secrets location.
    
    Docker Swarm/Kubernetes mounts secrets at /run/secrets/{secret_name}.
    Falls back to environment variable if secret file not found.
    
    Args:
        secret_name: Name of the secret (e.g., 'discord_token')
        
    Returns:
        Secret value or None if not found
    """
    secret_path = Path(f"/run/secrets/{secret_name}")
    
    if secret_path.exists():
        try:
            return secret_path.read_text().strip()
        except (IOError, OSError) as e:
            logger.warning("docker_secret_read_error", secret=secret_name, error=str(e))
            return None
    
    return None


def get_config_value(
    env_var: str,
    secret_name: Optional[str] = None,
    required: bool = False,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Get configuration value from environment variables or Docker secrets.
    
    Tries in order:
    1. Docker secret file at /run/secrets/{secret_name}
    2. Environment variable {env_var}
    3. Default value if provided
    4. Raise error if required and not found
    
    This pattern enables:
    - Secure secret passing in Docker/Kubernetes
    - Standard environment variable fallback
    - Type-safe defaults
    - Clear error reporting for missing required values
    
    Example usage:
        token = get_config_value(
            env_var="DISCORD_BOT_TOKEN",
            secret_name="discord_bot_token",
            required=True,
        )
        rcon_password = get_config_value(
            env_var="RCON_PASSWORD",
            secret_name="rcon_password",  # reads from /run/secrets/rcon_password
            required=True,
        )
        debug_mode = get_config_value(
            env_var="DEBUG",
            default="false",
        )
    
    Args:
        env_var: Environment variable name (e.g., 'DISCORD_BOT_TOKEN')
        secret_name: Docker secret name (e.g., 'discord_token'). If not provided, uses env_var lowercased
        required: If True, raises ValueError when value not found
        default: Default value if not found in env or secrets
        
    Returns:
        Configuration value from secret, env var, or default
        
    Raises:
        ValueError: If required=True and value not found
    """
    # Use secret_name from parameter or derive from env_var
    if secret_name is None:
        secret_name = env_var.lower()
    
    # Try Docker secret first
    secret_value = _read_docker_secret(secret_name)
    if secret_value is not None:
        logger.debug("config_value_loaded_from_secret", source="docker_secret", var=env_var)
        return secret_value
    
    # Try environment variable
    env_value = os.getenv(env_var)
    if env_value is not None:
        logger.debug("config_value_loaded_from_env", source="environment", var=env_var)
        return env_value
    
    # Use default if provided
    if default is not None:
        logger.debug("config_value_loaded_from_default", source="default", var=env_var)
        return default
    
    # Raise error if required
    if required:
        raise ValueError(
            f"Required configuration value not found for '{env_var}'. "
            f"Checked: Docker secret '{secret_name}', environment variable '{env_var}'"
        )
    
    return None


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

    rcon_breakdown_mode: str = "transition"
    """RCON status reporting mode: 'transition' (on state change) or 'interval' (periodic)."""

    rcon_breakdown_interval: int = 300
    """Interval in seconds between RCON breakdown reports (for 'interval' mode). Default: 300s (5 min)."""

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

        # Validate breakdown mode
        if self.rcon_breakdown_mode.lower() not in ("transition", "interval"):
            raise ValueError(
                f"Server {self.tag}: rcon_breakdown_mode must be 'transition' or 'interval', "
                f"got '{self.rcon_breakdown_mode}'"
            )

        if self.rcon_breakdown_interval <= 0:
            raise ValueError(
                f"Server {self.tag}: rcon_breakdown_interval must be > 0, "
                f"got {self.rcon_breakdown_interval}"
            )


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
    """Host to bind health check server to. Default: 0.0.0.0"""

    health_check_port: int = 8080
    """Port to bind health check server to. Default: 8080"""

    # Logging configuration
    log_level: str = "info"
    """Logging level: debug, info, warning, error. Default: info"""

    log_format: str = "console"
    """Logging format: console or json. Default: console"""

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.discord_bot_token:
            raise ValueError("discord_bot_token is REQUIRED")

        if self.servers is None or not self.servers:
            raise ValueError(
                "servers configuration is REQUIRED. "
                "Multi-server mode requires servers.yml with at least one server."
            )

        if not isinstance(self.servers, dict):
            raise ValueError(
                f"servers must be a non-empty dictionary, got {type(self.servers).__name__}"
            )

        # Validate log level
        valid_levels = {"debug", "info", "warning", "error"}
        if self.log_level.lower() not in valid_levels:
            raise ValueError(
                f"Invalid log_level '{self.log_level}'. Must be one of: {', '.join(valid_levels)}"
            )

        # Validate health check port
        if not 1 <= self.health_check_port <= 65535:
            raise ValueError(
                f"Invalid health_check_port: {self.health_check_port}. Must be 1-65535"
            )

        # Validate log format
        valid_formats = {"console", "json"}
        if self.log_format.lower() not in valid_formats:
            raise ValueError(
                f"Invalid log_format '{self.log_format}'. Must be one of: {', '.join(valid_formats)}"
            )


def _expand_env_vars(value: str) -> str:
    """
    Expand environment variables in a string.
    
    Supports ${VAR_NAME} syntax.
    Falls back to original string if variable not found.
    
    Args:
        value: String potentially containing ${VAR_NAME} references
        
    Returns:
        String with environment variables expanded
    """
    if not isinstance(value, str):
        return value
    
    import re
    
    def replace_var(match: Any) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # Fall back to original if not found
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, value)


def load_config() -> Config:
    """
    Load configuration from environment variables and servers.yml.
    
    Priority order for each config value:
    1. Environment variable (or Docker secret for passwords)
    2. servers.yml YAML file
    3. Hardcoded defaults
    
    Returns:
        Fully populated Config object with validation
        
    Raises:
        FileNotFoundError: If servers.yml not found
        ValueError: If required config values missing
        yaml.YAMLError: If servers.yml invalid YAML
    """
    # Get config directory (defaults to current working directory)
    config_dir = os.getenv("CONFIG_DIR", ".")
    servers_yml_path = Path(config_dir) / "servers.yml"
    
    if not servers_yml_path.exists():
        raise FileNotFoundError(
            f"servers.yml not found at {servers_yml_path}. "
            f"Multi-server mode requires servers configuration."
        )
    
    # Load servers configuration from YAML
    with open(servers_yml_path) as f:
        servers_data = yaml.safe_load(f)
    
    if not servers_data or "servers" not in servers_data:
        raise ValueError("servers.yml must contain 'servers' key with server definitions")
    
    # Parse servers into ServerConfig objects
    servers: Dict[str, ServerConfig] = {}
    
    for tag, server_data in servers_data["servers"].items():
        # Expand environment variables in rcon_password
        rcon_password = server_data.get("rcon_password", "")
        rcon_password = _expand_env_vars(rcon_password)
        
        # Read from Docker secret if available
        secret_password = get_config_value(
            env_var=f"RCON_PASSWORD_{tag.upper()}",
            secret_name=f"rcon_password_{tag}",
            required=False,
        )
        if secret_password:
            rcon_password = secret_password
        
        server_config = ServerConfig(
            name=server_data.get("name", tag),
            tag=tag,
            log_path=Path(server_data.get("log_path", "console.log")),
            rcon_host=server_data.get("rcon_host", "localhost"),
            rcon_port=_safe_int(server_data.get("rcon_port", 27015), f"Server {tag} rcon_port", 27015),
            rcon_password=rcon_password,
            event_channel_id=int(server_data.get("event_channel_id", 0)),
            rcon_breakdown_mode=server_data.get("rcon_breakdown_mode", "transition"),
            rcon_breakdown_interval=_safe_int(
                server_data.get("rcon_breakdown_interval", 300),
                f"Server {tag} rcon_breakdown_interval",
                300,
            ),
        )
        servers[tag] = server_config
    
    # Load Discord bot token from secrets/env
    discord_bot_token = get_config_value(
        env_var="DISCORD_BOT_TOKEN",
        secret_name="discord_bot_token",
        required=True,
    )
    
    # Load other config from environment with defaults
    bot_name = get_config_value(
        env_var="BOT_NAME",
        default="Factorio ISR",
    )
    
    bot_avatar_url = get_config_value(
        env_var="BOT_AVATAR_URL",
        default=None,
    )
    
    health_check_host = get_config_value(
        env_var="HEALTH_CHECK_HOST",
        default="0.0.0.0",
    )
    
    health_check_port = _safe_int(
        get_config_value(
            env_var="HEALTH_CHECK_PORT",
            default="8080",
        ),
        "health_check_port",
        8080,
    )
    
    log_level = get_config_value(
        env_var="LOG_LEVEL",
        default="info",
    )
    
    log_format = get_config_value(
        env_var="LOG_FORMAT",
        default="console",
    )
    
    patterns_dir = Path(
        get_config_value(
            env_var="PATTERNS_DIR",
            default="config/patterns",
        )
    )
    
    # Create and return Config object
    config = Config(
        discord_bot_token=discord_bot_token or "",
        bot_name=bot_name or "Factorio ISR",
        bot_avatar_url=bot_avatar_url,
        servers=servers if servers else None,
        health_check_host=health_check_host or "0.0.0.0",
        health_check_port=health_check_port,
        log_level=log_level or "info",
        log_format=log_format or "console",
        patterns_dir=patterns_dir,
    )
    
    return config


def validate_config(config: Config) -> bool:
    """
    Validate a Config object for completeness.
    
    Args:
        config: Config object to validate
        
    Returns:
        True if config is valid, False otherwise
    """
    try:
        # Try to access config in __post_init__ validation happens during Config creation
        if not config.discord_bot_token:
            logger.error("config_validation_failed_no_token")
            return False
        
        if not config.servers:
            logger.error("config_validation_failed_no_servers")
            return False
        
        # Validate each server has event_channel_id set
        for tag, server in config.servers.items():
            if not server.event_channel_id or server.event_channel_id == 0:
                logger.error("config_validation_failed_no_event_channel", server=tag)
                return False
        
        # Warn if patterns dir missing (but don't fail)
        if not config.patterns_dir.exists():
            logger.warning(
                "config_patterns_dir_missing",
                patterns_dir=str(config.patterns_dir),
            )
        
        return True
    
    except Exception as e:
        logger.error("config_validation_error", error=str(e))
        return False
