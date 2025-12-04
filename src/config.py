"""Configuration management for Factorio ISR."""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger() 

def _read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a secret from multiple sources (local dev + Docker).
    
    Checks in order:
    1. .secrets/{secret_name}.txt (local development)
    2. .secrets/{secret_name} (local development)
    3. /run/secrets/{secret_name} (Docker secrets)
    
    Returns:
        Secret value as string, or None if not found
    """
    # Local dev: .txt extension
    local_txt = Path(".secrets") / f"{secret_name}.txt"
    if local_txt.exists():
        try:
            value = local_txt.read_text().strip()
            if value:  # Only return non-empty
                logger.debug("loaded_secret", secret_name=secret_name, source="local_txt")
                return value
        except Exception as e:
            logger.warning("failed_to_read_secret", secret_name=secret_name, source="local_txt", error=str(e))
    
    # Local dev: no extension
    local_plain = Path(".secrets") / secret_name
    if local_plain.exists():
        try:
            value = local_plain.read_text().strip()
            if value:
                logger.debug("loaded_secret", secret_name=secret_name, source="local_plain")
                return value
        except Exception as e:
            logger.warning("failed_to_read_secret", secret_name=secret_name, source="local_plain", error=str(e))
    
    # Docker secrets
    docker_secret = Path("/run/secrets") / secret_name
    if docker_secret.exists():
        try:
            value = docker_secret.read_text().strip()
            if value:
                logger.debug("loaded_secret", secret_name=secret_name, source="docker_secrets")
                return value
        except Exception as e:
            logger.warning("failed_to_read_secret", secret_name=secret_name, source="docker_secrets", error=str(e))
    
    return None


def get_config_value(
    key: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Get configuration value with priority: secrets > env vars > default.
    """
    # Priority 1: Secrets (file-based)
    value = _read_secret(key)
    
    # Priority 2: Environment variable
    if value is None:
        value = os.getenv(key)
        if value:
            logger.debug("loaded_config", key=key, source="environment")
    
    # Priority 3: Default
    if value is None:
        value = default
        if value:
            logger.debug("loaded_config", key=key, source="default")
    
    # Validate required
    if value is None and required:
        raise ValueError(f"Required configuration '{key}' not found")
    
    return value


@dataclass
class Config:
    """Configuration for Factorio ISR."""
    # Required
    discord_webhook_url: Optional[str] = None
    discord_bot_token: Optional[str] = None
    discord_event_channel_id: Optional[int] = None  
    
    # Optional with defaults
    bot_name: str = "Factorio ISR"
    bot_avatar_url: Optional[str] = None
    factorio_log_path: Path = Path("/logs/console.log")
    log_level: str = "info"
    log_format: str = "console"
    health_check_host: str = "0.0.0.0"
    health_check_port: int = 8080
    patterns_dir: Path = field(default_factory=lambda: Path("patterns"))
    pattern_files: Optional[List[str]] = None
    webhook_channels: Dict[str, str] = field(default_factory=dict)
    send_test_message: bool = False
    
    # RCON (Phase 3)
    rcon_enabled: bool = False
    rcon_host: str = "localhost"
    rcon_port: int = 27015
    rcon_password: Optional[str] = None
    stats_interval: int = 300


def _parse_webhook_channels(channels_str: Optional[str]) -> Dict[str, str]:
    """Parse webhook channels from JSON string."""
    if not channels_str:
        return {}
    
    try:
        channels = json.loads(channels_str)
        if not isinstance(channels, dict):
            return {}
        return channels
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_pattern_files(files_str: Optional[str]) -> Optional[List[str]]:
    """Parse pattern files from JSON string."""
    if not files_str:
        return None
    
    try:
        files = json.loads(files_str)
        if not isinstance(files, list):
            return None
        return files
    except (json.JSONDecodeError, TypeError):
        return None


def load_config() -> Config:
    """Load configuration from environment variables and Docker secrets."""
    load_dotenv()

    # Discord configuration - at least one mode required
    webhook_url = get_config_value("DISCORD_WEBHOOK_URL")
    bot_token = get_config_value("DISCORD_BOT_TOKEN")
    
    # Validate that at least one Discord mode is configured
    if not webhook_url and not bot_token:
        raise ValueError(
            "Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN must be configured"
        )
    
    # Required: Factorio log path
    factorio_log_path = get_config_value("FACTORIO_LOG_PATH")
    if not factorio_log_path:
        raise ValueError("FACTORIO_LOG_PATH is required")

    # Optional fields with guaranteed defaults
    bot_name = get_config_value("BOT_NAME") or "Factorio ISR"
    log_level = (get_config_value("LOG_LEVEL") or "info").lower()
    log_format = (get_config_value("LOG_FORMAT") or "console").lower()
    health_check_host = get_config_value("HEALTH_CHECK_HOST") or "0.0.0.0"
    health_check_port_str = get_config_value("HEALTH_CHECK_PORT") or "8080"
    patterns_dir_str = get_config_value("PATTERNS_DIR") or "patterns"
    rcon_host = get_config_value("RCON_HOST") or "localhost"
    rcon_port_str = get_config_value("RCON_PORT") or "27015"
    stats_interval_str = get_config_value("STATS_INTERVAL") or "300"

    # Boolean flags
    send_test_str = get_config_value("SEND_TEST_MESSAGE") or "false"
    rcon_enabled_str = get_config_value("RCON_ENABLED") or "false"
    # Parse webhook channels (support secrets)
    webhook_channels_str = get_config_value("WEBHOOK_CHANNELS") or "{}"
    channel_id_str = get_config_value("DISCORD_EVENT_CHANNEL_ID")
    event_channel_id = int(channel_id_str) if channel_id_str else None
    
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
        pattern_files=_parse_pattern_files(get_config_value("PATTERN_FILES")),
        webhook_channels=_parse_webhook_channels(webhook_channels_str),
        send_test_message=send_test_str.lower() == "true",
        rcon_enabled=rcon_enabled_str.lower() == "true",
        rcon_host=rcon_host,
        rcon_port=int(rcon_port_str),
        rcon_password=get_config_value("RCON_PASSWORD"),
        stats_interval=int(stats_interval_str),
    )



def validate_config(config: Config) -> bool:
    """
    Validate configuration values.
    
    Args:
        config: Config object to validate
    
    Returns:
        True if valid, False otherwise
    """
    # Validate Discord configuration
    if config.discord_webhook_url is not None:
        if not config.discord_webhook_url.startswith("https://discord.com/api/webhooks/"):
            logger.error("validation_failed", reason="invalid_webhook_url_format")
            return False
    
    if config.discord_bot_token is not None:
        if len(config.discord_bot_token) < 50:  # Bot tokens are typically 70+ chars
            logger.warning("validation_warning", reason="bot_token_seems_too_short")
    
    # At least one Discord mode must be configured
    if not config.discord_webhook_url and not config.discord_bot_token:
        logger.error("validation_failed", reason="no_discord_configuration")
        return False
    
    # Validate log level
    if config.log_level not in ("debug", "info", "warning", "error", "critical"):
        logger.warning(
            "invalid_log_level",
            level=config.log_level,
            defaulting_to="info"
        )
        config.log_level = "info"
    
    # Validate RCON configuration
    if config.rcon_enabled and not config.rcon_password:
        logger.error("validation_failed", reason="rcon_enabled_but_no_password")
        return False
    
    return True

