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
    
    # Discord
    discord_webhook_url: str
    bot_name: str = "FactorioISR"
    bot_avatar_url: Optional[str] = None
    
    # Factorio
    factorio_log_path: Path = Path("/logs/console.log")
    
    # Health check
    health_check_host: str = "0.0.0.0"
    health_check_port: int = 8080
    
    # Logging
    log_level: str = "info"
    log_format: str = "json"  # json or console


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
    bot_name = get_config_value_safe("BOT_NAME", default="Factorio Bridge")
    bot_avatar_url = get_config_value("BOT_AVATAR_URL")  # Can be None
    
    factorio_log_path = Path(
        get_config_value_safe("FACTORIO_LOG_PATH", default="/logs/console.log")
    )
    
    health_host = get_config_value_safe("HEALTH_CHECK_HOST", default="0.0.0.0")
    health_port = int(get_config_value_safe("HEALTH_CHECK_PORT", default="8080"))
    
    log_level = get_config_value_safe("LOG_LEVEL", default="info").lower()
    log_format = get_config_value_safe("LOG_FORMAT", default="json").lower()
    
    config = Config(
        discord_webhook_url=discord_webhook_url,
        bot_name=bot_name,
        bot_avatar_url=bot_avatar_url,
        factorio_log_path=factorio_log_path,
        health_check_host=health_host,
        health_check_port=health_port,
        log_level=log_level,
        log_format=log_format,
    )
    
    logger.info(
        "config_loaded",
        log_level=config.log_level,
        log_format=config.log_format,
        health_port=config.health_check_port,
        factorio_log=str(config.factorio_log_path)
    )
    
    return config

# def load_config_old() -> Config:
#     """
#     Load application configuration from Docker secrets and environment variables.
    
#     Returns:
#         Config object with all settings
    
#     Raises:
#         ValueError: If required configuration is missing
#     """
#     # Load .env file if present (for local development)
#     try:
#         from dotenv import load_dotenv
#         env_file = Path(".env")
#         if env_file.exists():
#             load_dotenv()
#             logger.info("loaded_dotenv", path=str(env_file))
#     except ImportError:
#         logger.debug("python-dotenv_not_installed")
    
#     # Required fields
#     discord_webhook_url = get_config_value(
#         "DISCORD_WEBHOOK_URL",
#         required=True
#     )
    
#     # Optional fields with defaults
#     bot_name = get_config_value("BOT_NAME", default="FactorioISR")
#     bot_avatar_url = get_config_value("BOT_AVATAR_URL")
    
#     log_path_str = get_config_value(
#         "FACTORIO_LOG_PATH",
#         default="/logs/console.log"
#     )

#     if log_path_str is None:
#         log_path_str = "/logs/console.log"
#     factorio_log_path = Path(log_path_str)
    
#     health_host = get_config_value(
#         "HEALTH_CHECK_HOST",
#         default="0.0.0.0"
#     )
#     if health_host is None:
#         health_host = "0.0.0.0"

#     health_port_str = get_config_value(
#         "HEALTH_CHECK_PORT",
#         default="8080"
#     )
#     if health_port_str is None:
#         health_port_str = "8080"
#     health_port = int(health_port_str)

#     log_level_str = get_config_value("LOG_LEVEL", default="info")
#     if log_level_str is None:
#         log_level_str = "info"
#     log_level = log_level_str.lower()

#     log_format_str = get_config_value("LOG_FORMAT", default="json")
#     if log_format_str is None:
#         log_format_str = "json"
#     log_format = log_format_str.lower()

#     assert discord_webhook_url is not None
#     config = Config(
#         discord_webhook_url=discord_webhook_url,
#         bot_name=bot_name or "FactorioISR Agent",
#         bot_avatar_url=bot_avatar_url,
#         factorio_log_path=factorio_log_path,
#         health_check_host=health_host,
#         health_check_port=health_port,
#         log_level=log_level,
#         log_format=log_format,
#     )
    
#     logger.info(
#         "config_loaded",
#         log_level=config.log_level,
#         log_format=config.log_format,
#         health_port=config.health_check_port,
#         factorio_log=str(config.factorio_log_path)
#     )
    
#     return config


# Convenience function for testing
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
