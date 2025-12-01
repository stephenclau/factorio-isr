"""Configuration management for Factorio ISR."""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def _read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a secret from multiple sources.
    
    Checks in order:
    1. .secrets/{secret_name}.txt (local development with .txt extension)
    2. .secrets/{secret_name} (local development without extension)
    3. /run/secrets/{secret_name} (Docker secrets)
    4. Environment variable
    5. Default value
    """
    # Try local .secrets folder with .txt extension first
    local_secret_path_txt = Path(".secrets") / f"{secret_name}.txt"
    if local_secret_path_txt.exists():
        try:
            content = local_secret_path_txt.read_text().strip()
            if content:
                return content
        except Exception:
            pass
    
    # Try local .secrets folder without extension
    local_secret_path = Path(".secrets") / secret_name
    if local_secret_path.exists():
        try:
            content = local_secret_path.read_text().strip()
            if content:
                return content
        except Exception:
            pass
    
    # Try Docker secret location
    docker_secret_path = Path("/run/secrets") / secret_name
    if docker_secret_path.exists():
        try:
            content = docker_secret_path.read_text().strip()
            if content:
                return content
        except Exception:
            pass
    
    # Fall back to environment variable
    env_value = os.getenv(secret_name)
    if env_value is not None:
        return env_value
    
    return default


@dataclass
class Config:
    """Configuration for Factorio ISR."""
    # Required
    discord_webhook_url: str
    factorio_log_path: Path
    
    # Optional with defaults
    bot_name: str = "Factorio ISR"
    bot_avatar_url: Optional[str] = None
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
    
    # Required fields - support secrets
    webhook_url = _read_secret("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL is required")
    
    factorio_log_path = _read_secret("FACTORIO_LOG_PATH")
    if not factorio_log_path:
        raise ValueError("FACTORIO_LOG_PATH is required")
    
    # Optional fields with guaranteed defaults
    bot_name = _read_secret("BOT_NAME") or "Factorio ISR"
    log_level = (_read_secret("LOG_LEVEL") or "info").lower()
    log_format = (_read_secret("LOG_FORMAT") or "console").lower()
    health_check_host = _read_secret("HEALTH_CHECK_HOST") or "0.0.0.0"
    health_check_port_str = _read_secret("HEALTH_CHECK_PORT") or "8080"
    patterns_dir_str = _read_secret("PATTERNS_DIR") or "patterns"
    rcon_host = _read_secret("RCON_HOST") or "localhost"
    rcon_port_str = _read_secret("RCON_PORT") or "27015"
    stats_interval_str = _read_secret("STATS_INTERVAL") or "300"
    
    # Boolean flags
    send_test_str = _read_secret("SEND_TEST_MESSAGE") or "false"
    rcon_enabled_str = _read_secret("RCON_ENABLED") or "false"
    
    # Parse webhook channels (support secrets)
    webhook_channels_str = _read_secret("WEBHOOK_CHANNELS") or "{}"
    
    return Config(
        discord_webhook_url=webhook_url,
        factorio_log_path=Path(factorio_log_path),
        bot_name=bot_name,
        bot_avatar_url=_read_secret("BOT_AVATAR_URL"),
        log_level=log_level,
        log_format=log_format,
        health_check_host=health_check_host,
        health_check_port=int(health_check_port_str),
        patterns_dir=Path(patterns_dir_str),
        pattern_files=_parse_pattern_files(_read_secret("PATTERN_FILES")),
        webhook_channels=_parse_webhook_channels(webhook_channels_str),
        send_test_message=send_test_str.lower() == "true",
        rcon_enabled=rcon_enabled_str.lower() == "true",
        rcon_host=rcon_host,
        rcon_port=int(rcon_port_str),
        rcon_password=_read_secret("RCON_PASSWORD"),
        stats_interval=int(stats_interval_str),
    )


def validate_config(config: Config) -> bool:
    """Validate configuration."""
    # Validate log level
    valid_levels = ["debug", "info", "warning", "error", "critical"]
    if config.log_level not in valid_levels:
        raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
    
    # Validate log format
    valid_formats = ["json", "console"]
    if config.log_format not in valid_formats:
        raise ValueError(f"LOG_FORMAT must be one of {valid_formats}")
    
    # Validate webhook URL
    if not config.discord_webhook_url.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("DISCORD_WEBHOOK_URL must be a valid Discord webhook URL")
    
    # Validate log path
    if not isinstance(config.factorio_log_path, Path):
        raise ValueError("FACTORIO_LOG_PATH must be a valid path")
    
    # Validate RCON settings if enabled
    if config.rcon_enabled:
        if not config.rcon_password:
            raise ValueError("RCON_PASSWORD is required when RCON_ENABLED is true")
        if config.rcon_port < 1 or config.rcon_port > 65535:
            raise ValueError("RCON_PORT must be between 1 and 65535")
    
    return True
