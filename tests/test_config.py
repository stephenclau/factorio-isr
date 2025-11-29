#!/usr/bin/env python3
"""
Test script for config.py
Run with: python test_config.py
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Set up basic logging first
import os
import structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
import config
from config import load_config, validate_config, get_config_value, read_secret

def test_read_secret():
    """Test Docker secrets reading"""
    print("\n=== Testing Docker Secrets ===")
    
    # This will fail unless you're in a container with secrets
    secret = read_secret("DISCORD_WEBHOOK_URL")
    if secret:
        print(f"✓ Found secret: {secret[:50]}...")
    else:
        print("✗ No Docker secret found (expected in dev)")

def test_get_config_value():
    """Test config value priority"""
    print("\n=== Testing Config Value Priority ===")
    
    # Test 1: Environment variable
    os.environ["TEST_VAR"] = "from_env"
    value = get_config_value("TEST_VAR")
    assert value == "from_env", f"Expected 'from_env', got '{value}'"
    print("✓ Environment variable priority works")
    
    # Test 2: Default value
    value = get_config_value("NONEXISTENT_VAR", default="default_value")
    assert value == "default_value", f"Expected 'default_value', got '{value}'"
    print("✓ Default value works")
    
    # Test 3: Required but missing
    try:
        get_config_value("MISSING_REQUIRED", required=True)
        print("✗ Should have raised ValueError for required missing value")
    except ValueError as e:
        print(f"✓ Required validation works: {e}")
    
    # Cleanup
    del os.environ["TEST_VAR"]

def test_load_config():
    """Test full config loading"""
    print("\n=== Testing Config Loading ===")
    
    # Set required environment variable
    os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/123/test"
    
    try:
        config = load_config()
        print(f"✓ Config loaded successfully")
        print(f"  - Discord webhook: {config.discord_webhook_url[:50]}...")
        print(f"  - Log path: {config.factorio_log_path}")
        print(f"  - Log level: {config.log_level}")
        print(f"  - Health port: {config.health_check_port}")
        print(f"  - Bot name: {config.bot_name}")
        
        # Test validation
        is_valid = validate_config(config)
        if is_valid:
            print("✓ Config validation passed")
        else:
            print("✗ Config validation failed")
            
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if "DISCORD_WEBHOOK_URL" in os.environ:
            del os.environ["DISCORD_WEBHOOK_URL"]

def test_invalid_webhook():
    """Test webhook validation"""
    print("\n=== Testing Webhook Validation ===")
    
    os.environ["DISCORD_WEBHOOK_URL"] = "https://invalid-url.com"
    
    try:
        config = load_config()
        is_valid = validate_config(config)
        if not is_valid:
            print("✓ Invalid webhook URL detected correctly")
        else:
            print("✗ Should have failed validation for invalid webhook")
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        del os.environ["DISCORD_WEBHOOK_URL"]

def test_with_env_file():
    """Test loading from .env file"""
    print("\n=== Testing .env File Loading ===")
    
    env_path = Path(".env")
    if env_path.exists():
        print(f"✓ Found .env file at {env_path}")
        try:
            config = load_config()
            print(f"✓ Loaded config from .env")
            print(f"  - Webhook configured: {bool(config.discord_webhook_url)}")
        except ValueError as e:
            print(f"✗ Missing required config: {e}")
    else:
        print("⚠ No .env file found (copy .env.example to .env)")

if __name__ == "__main__":
    print("=" * 60)
    print("Config Module Test Suite")
    print("=" * 60)
    
    test_read_secret()
    test_get_config_value()
    test_load_config()
    test_invalid_webhook()
    test_with_env_file()
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
