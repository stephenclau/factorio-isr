"""Configuration management with multi-channel support."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
import os
import structlog

logger = structlog.get_logger()


@dataclass
class Config:
    """Application configuration with multi-channel routing."""
    
    # Discord - primary webhook (backward compatible)
    discord_webhook_url: str
    bot_name: str = "Factorio ISR Bridge"
    bot_avatar_url: Optional[str] = None
    
    # Multi-channel webhooks (NEW)
    webhook_channels: Dict[str, str] = field(default_factory=dict)   # channel_name -> webhook_url
    
    # Factorio
    factorio_log_path: Path = Path("logs/console.log")
    
    # Pattern Configuration
    patterns_dir: Path = Path("patterns")
    pattern_files: Optional[List[str]] = None
    
    # Health check
    healthcheck_host: str = "0.0.0.0"
    healthcheck_port: int = 8080
    
    # Logging
    loglevel: str = "info"
    logformat: str = "json"
    
    def __post_init__(self):
        """Initialize webhook_channels dict if None."""
        if self.webhook_channels is None:
            self.webhook_channels = {}


def get_config_value_safe(key: str, default: str = "") -> str:
    """Get config value from environment or Docker secrets."""
    # Check environment variable first
    value = os.getenv(key)
    if value:
        return value
    
    # Check Docker secrets
    secret_file = Path(f"/run/secrets/{key}")
    if secret_file.exists():
        try:
            return secret_file.read_text().strip()
        except Exception as e:
            logger.warning("secret_read_failed", key=key, error=str(e))
    
    return default


def load_config() -> Config:
    """Load configuration from environment and secrets."""
    
    # Required: Primary Discord webhook
    discord_webhook_url = get_config_value_safe("DISCORD_WEBHOOK_URL")
    if not discord_webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL is required")
    
    # Optional configuration
    bot_name = get_config_value_safe("BOT_NAME", default="Factorio ISR Bridge")
    bot_avatar_url_str = get_config_value_safe("BOT_AVATAR_URL", default="")
    bot_avatar_url = bot_avatar_url_str if bot_avatar_url_str else None
    
    factorio_log_path = Path(get_config_value_safe("FACTORIO_LOG_PATH", default="logs/console.log"))
    
    # Pattern configuration
    patterns_dir_str = get_config_value_safe("PATTERNS_DIR", default="patterns")
    patterns_dir = Path(patterns_dir_str)
    
    pattern_files_str = get_config_value_safe("PATTERN_FILES", default="")
    pattern_files: Optional[List[str]] = None
    if pattern_files_str:
        pattern_files = [f.strip() for f in pattern_files_str.split(",")]
    
    # Multi-channel webhooks (NEW)
    webhook_channels: Dict[str, str] = {}
    
    # Parse WEBHOOK_CHANNELS environment variable
    # Format: channel1=URL1,channel2=URL2,channel3=URL3
    webhook_channels_str = get_config_value_safe("WEBHOOK_CHANNELS", default="")
    if webhook_channels_str:
        for mapping in webhook_channels_str.split(","):
            if "=" in mapping:
                channel_name, webhook_url = mapping.split("=", 1)
                webhook_channels[channel_name.strip()] = webhook_url.strip()
    
    # Health check
    healthcheck_host = get_config_value_safe("HEALTHCHECK_HOST", default="0.0.0.0")
    healthcheck_port = int(get_config_value_safe("HEALTHCHECK_PORT", default="8080"))
    
    # Logging
    loglevel = get_config_value_safe("LOG_LEVEL", default="info").lower()
    logformat = get_config_value_safe("LOG_FORMAT", default="json").lower()
    
    config = Config(
        discord_webhook_url=discord_webhook_url,
        bot_name=bot_name,
        bot_avatar_url=bot_avatar_url,
        webhook_channels=webhook_channels,
        factorio_log_path=factorio_log_path,
        patterns_dir=patterns_dir,
        pattern_files=pattern_files,
        healthcheck_host=healthcheck_host,
        healthcheck_port=healthcheck_port,
        loglevel=loglevel,
        logformat=logformat,
    )
    
    logger.info(
        "config_loaded",
        factorio_log=str(factorio_log_path),
        patterns_dir=str(patterns_dir),
        pattern_files=pattern_files,
        webhook_channels=list(webhook_channels.keys())
    )
    
    return config


def validate_config(config: Config) -> bool:
    """Validate configuration values."""
    if not config.discord_webhook_url:
        logger.error("validation_failed", reason="missing_webhook_url")
        return False
    
    if not config.discord_webhook_url.startswith("https://discord.com/api/webhooks/"):
        logger.error("validation_failed", reason="invalid_webhook_url_format")
        return False
    
    # Validate additional webhook channels
    for channel_name, webhook_url in config.webhook_channels.items():
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            logger.error(
                "validation_failed",
                reason="invalid_webhook_channel_url",
                channel=channel_name
            )
            return False
    
    return True
