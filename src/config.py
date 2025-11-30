"""
Configuration management with support for both .env files and Docker secrets.
Prioritizes Docker secrets over environment variables for production security.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class Config:
    """Application configuration."""
    
    # Required fields (no defaults)
    discord_webhook_url: str
    bot_name: str
    
    # Optional fields with defaults (must come after required fields)
    bot_avatar_url: Optional[str] = None
    factorio_log_path: Path = Path("/logs/console.log")
    health_check_host: str = "0.0.0.0"
    health_check_port: int = 8080
    log_level: str = "info"
    log_format: str = "json"  # json or console
    send_test_message: bool = False
    
    # RCON fields (Phase 3)
    rcon_enabled: bool = False
    rcon_host: str = "factorio"
    rcon_port: int = 27015
    rcon_password: Optional[str] = None
    stats_interval: int = 300


def read_secret(secret_name: str) -> Optional[str]:
    """
    Read a secret from Docker secrets directory.
    
    Args:
        secret_name: Name of the secret (e.g., 'DISCORD_WEBHOOK_URL')
    
    Returns:
        Secret value as string, or None if not found
    """
    secret_path = Path(f"/run/secrets/{secret_name}")
    
    if secret_path.exists():
        try:
            value = secret_path.read_text().strip()
            logger.debug(
                "loaded_secret",
                secret_name=secret_name,
                source="docker_secrets"
            )
            return value
        except Exception as e:
            logger.warning(
                "failed_to_read_secret",
                secret_name=secret_name,
                error=str(e)
            )
            return None
    
    return None


def get_config_value(
    key: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Get configuration value with priority: Docker secrets > env vars > default.
    
    Args:
        key: Configuration key name (uppercase)
        default: Default value if not found
        required: Raise error if not found and no default
    
    Returns:
        Configuration value as string
    
    Raises:
        ValueError: If required=True and value not found
    """
    # Priority 1: Docker secrets
    value = read_secret(key)
    
    # Priority 2: Environment variable
    if value is None:
        value = os.getenv(key)
        if value:
            logger.debug(
                "loaded_config",
                key=key,
                source="environment"
            )
    
    # Priority 3: Default value
    if value is None:
        value = default
        if value:
            logger.debug(
                "loaded_config",
                key=key,
                source="default"
            )
    
    # Check if required
    if value is None and required:
        raise ValueError(
            f"Required configuration '{key}' not found in Docker secrets, "
            f"environment variables, or defaults"
        )
    
    return value


def get_config_value_safe(
    key: str,
    default: str,
    required: bool = False
) -> str:
    """
    Type-safe wrapper that guarantees non-None return.
    
    Args:
        key: Configuration key name (uppercase)
        default: Default value (non-None)
        required: Raise error if not found and no default
    
    Returns:
        Configuration value as string (never None)
    """
    value = get_config_value(key, default=default, required=required)
    # This should never happen with a non-None default, but satisfies type checker
    return value if value is not None else default


def load_config() -> Config:
    """
    Load application configuration from Docker secrets and environment variables.
    
    Returns:
        Config object with all settings
    
    Raises:
        ValueError: If required configuration is missing
    """
    # Load .env file if present (for local development)
    try:
        from dotenv import load_dotenv
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv()
            logger.info("loaded_dotenv", path=str(env_file))
    except ImportError:
        logger.debug("python-dotenv_not_installed")
    
    # Required fields (will raise if missing)
    discord_webhook_url = get_config_value("DISCORD_WEBHOOK_URL", required=True)
    assert discord_webhook_url is not None  # Type narrowing
    
    # Optional fields with safe defaults
    bot_name = get_config_value_safe("BOT_NAME", default="FactorioISR Bridge")
    bot_avatar_url = get_config_value("BOT_AVATAR_URL")  # Can be None
    
    factorio_log_path = Path(
        get_config_value_safe("FACTORIO_LOG_PATH", default="/logs/console.log")
    )
    
    health_host = get_config_value_safe("HEALTH_CHECK_HOST", default="0.0.0.0")
    health_port = int(get_config_value_safe("HEALTH_CHECK_PORT", default="8080"))
    
    log_level = get_config_value_safe("LOG_LEVEL", default="info").lower()
    log_format = get_config_value_safe("LOG_FORMAT", default="json").lower()
    
    # Test message flag
    send_test_message_str = get_config_value_safe("SEND_TEST_MESSAGE", default="false")
    send_test_message = send_test_message_str.lower() in ("true", "yes", "1")
    
    # RCON configuration (Phase 3)
    rcon_enabled_str = get_config_value_safe("RCON_ENABLED", default="false")
    rcon_enabled = rcon_enabled_str.lower() in ("true", "yes", "1")
    
    rcon_host = get_config_value_safe("RCON_HOST", default="factorio")
    rcon_port_str = get_config_value_safe("RCON_PORT", default="27015")
    rcon_port = int(rcon_port_str)
    
    rcon_password = get_config_value("RCON_PASSWORD")  # Optional
    
    stats_interval_str = get_config_value_safe("STATS_INTERVAL", default="300")
    stats_interval = int(stats_interval_str)
    
    config = Config(
        discord_webhook_url=discord_webhook_url,
        bot_name=bot_name,
        bot_avatar_url=bot_avatar_url,
        factorio_log_path=factorio_log_path,
        health_check_host=health_host,
        health_check_port=health_port,
        log_level=log_level,
        log_format=log_format,
        send_test_message=send_test_message,
        rcon_enabled=rcon_enabled,
        rcon_host=rcon_host,
        rcon_port=rcon_port,
        rcon_password=rcon_password,
        stats_interval=stats_interval,
    )
    
    logger.info(
        "config_loaded",
        log_level=config.log_level,
        log_format=config.log_format,
        health_port=config.health_check_port,
        factorio_log=str(config.factorio_log_path),
        rcon_enabled=config.rcon_enabled
    )
    
    return config


def validate_config(config: Config) -> bool:
    """
    Validate configuration values.
    
    Args:
        config: Config object to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not config.discord_webhook_url:
        logger.error("validation_failed", reason="missing_webhook_url")
        return False
    
    if not config.discord_webhook_url.startswith("https://discord.com/api/webhooks/"):
        logger.error("validation_failed", reason="invalid_webhook_url_format")
        return False
    
    if config.log_level not in ["debug", "info", "warning", "error", "critical"]:
        logger.warning(
            "invalid_log_level",
            level=config.log_level,
            defaulting_to="info"
        )
        config.log_level = "info"
    
    return True
