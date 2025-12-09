---
layout: default
title: Development
---

# 🔧 Development

This guide covers local development, testing, and contributing to Factorio ISR.

## Development Setup

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/factorio-isr.git
cd factorio-isr
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

## Project Structure

```text
factorio-isr/
├── src/
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   ├── config.py                # Configuration loader
│   ├── event_parser.py          # Event parsing with security hardening
│   ├── pattern_loader.py        # YAML pattern configuration loader
│   ├── discord_client.py        # Discord webhook client
│   ├── discord_bot.py           # Discord bot with slash commands
│   ├── discord_interface.py     # Unified Discord interface (webhook/bot)
│   ├── log_tailer.py            # Real-time log monitoring
│   ├── rcon_client.py           # RCON client with metrics/stats
│   ├── server_manager.py        # Multi-server coordination
│   ├── security_monitor.py      # Security monitoring and rate limiting
│   ├── mention_resolver.py      # @mention parsing and resolution
│   └── health.py                # Health check server
├── tests/
│   ├── test_main.py
│   ├── test_config.py
│   ├── test_event_parser.py
│   ├── test_pattern_loader.py
│   ├── test_discord_client.py
│   ├── test_discord_bot.py
│   ├── test_discord_interface.py
│   ├── test_log_tailer.py
│   ├── test_rcon_client.py
│   ├── test_server_manager.py
│   ├── test_security_monitor.py
│   └── test_mention_resolver.py
├── patterns/                    # YAML event patterns
│   ├── vanilla.yml              # Core Factorio events
│   ├── research.yml             # Research completion events
│   ├── achievements.yml         # Achievement unlocks
│   ├── server.yml               # Server status events
│   └── custom.yml               # User-defined patterns
├── config/                      # Configuration files
│   ├── servers.yml              # Multi-server configuration
│   ├── mentions.yml             # Role mention vocabulary
│   └── secmon.yml               # Security monitor settings
├── docs/                        # Documentation
│   ├── README.md
│   ├── installation.md
│   ├── configuration.md
│   ├── PATTERNS.md
│   ├── RCON_SETUP.md
│   ├── MULTI_CHANNEL.md
│   ├── mentions.md
│   ├── secmon.md
│   ├── TROUBLESHOOTING.md
│   └── architecture.md
├── .env.example                 # Example environment file
├── .secrets/                    # Docker secrets (gitignored)
├── requirements.txt             # Python dependencies
├── requirements-dev.txt         # Development dependencies
├── Dockerfile                   # Production container
├── docker-compose.yml           # Docker Compose config
├── pyproject.toml               # Python project configuration
└── README.md
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=src --cov-report=html --cov-report=term
```

View coverage report:

```bash
open htmlcov/index.html      # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test File

```bash
pytest tests/test_event_parser.py -v
pytest tests/test_discord_bot.py -v
pytest tests/test_rcon_client.py -v
```

### Run Specific Test

```bash
pytest tests/test_event_parser.py::TestEventParser::test_parse_join -v
```

### Run in Watch Mode

```bash
pytest-watch
```

### Run with Debugging

```bash
pytest -v -s     # Show print statements
pytest --pdb     # Drop into debugger on failure
```

### Async Tests

The project uses `pytest-asyncio` for async code:

```python
import pytest
from rcon_client import RconClient

@pytest.mark.asyncio
async def test_rcon_connection():
    client = RconClient("localhost", 27015, "password")
    await client.connect()
    assert client.is_connected
    await client.disconnect()
```

## Code Style and Linting

### Format Code with Black

```bash
black src/ tests/
```

### Check Formatting

```bash
black --check src/ tests/
```

### Lint with Ruff

```bash
ruff check src/ tests/
```

### Fix Auto-fixable Issues

```bash
ruff check --fix src/ tests/
```

### Type Checking with mypy

```bash
mypy src/
```

## Pre-commit Hooks

### Install Pre-commit

```bash
pip install pre-commit
pre-commit install
```

### Run Manually

```bash
pre-commit run --all-files
```

## Running Locally

### Create Environment File

```bash
cp .env.example .env
# Edit .env with your configuration
```

At minimum for webhook mode:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
HEALTH_CHECK_PORT=8080
```

For bot mode and RCON, add:

```env
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

### Run the Application (Webhook or Bot)

```bash
python -m src.main
```

The mode (webhook vs bot) is selected via config (`DISCORD_WEBHOOK_URL` vs `DISCORD_BOT_TOKEN`).

### Run with Docker

```bash
# Build local image
docker build -t factorio-isr:dev .

# Run container as a sidecar to Factorio
docker run --rm \
  --env-file .env \
  -v /path/to/factorio/log:/factorio/log:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v $(pwd)/config:/app/config:ro \
  -p 8080:8080 \
  factorio-isr:dev
```

## Working with Patterns

### Create a Custom Pattern File

```bash
cat > patterns/custom.yml << 'EOF'
events:
  rocket_launch:
    pattern: 'rocket.*launched'
    type: milestone
    emoji: "🚀"
    message: "Rocket launched by {player}!"
    enabled: true
    priority: 5
    channel: milestones
EOF
```

### Test Pattern Loading

```bash
python - << 'EOF'
from pathlib import Path
from pattern_loader import PatternLoader

loader = PatternLoader(Path("patterns"))
count = loader.load_patterns(["custom.yml"])
print(f"Loaded {count} patterns")
EOF
```

### Test Parsing with Custom Pattern

```python
from pathlib import Path
from event_parser import EventParser

parser = EventParser(patterns_dir=Path("patterns"))
line = "[GAME] PlayerName's rocket was launched"
event = parser.parse_line(line)
print(event)
```

## Working with RCON

### Quick RCON Smoke Test

```python
import asyncio
from rcon_client import RconClient

async def main():
    client = RconClient("localhost", 27015, "your-password")
    try:
        await client.connect()
        print("✅ RCON connected")
        stats = await client.get_server_stats()
        print(stats)
    finally:
        await client.disconnect()

asyncio.run(main())
```

### Mock RCON in Tests

```python
from unittest.mock import AsyncMock
import pytest

@pytest.fixture
def mock_rcon():
    rcon = AsyncMock()
    rcon.is_connected = True
    rcon.execute.return_value = "5 players online"
    return rcon
```

## Working with the Discord Bot

### Local Bot Smoke Test

```python
import asyncio
from discord_bot import DiscordBot

async def main():
    bot = DiscordBot(token="YOUR_TEST_TOKEN", bot_name="Factorio ISR Dev")
    # Optionally set event channel
    # bot.set_event_channel(YOUR_CHANNEL_ID)
    await bot.connect_bot()
    # Let it run briefly
    await asyncio.sleep(10)
    await bot.disconnect_bot()

asyncio.run(main())
```

### Testing Slash Commands

Use `AsyncMock` for interactions:

```python
import pytest
from unittest.mock import AsyncMock
import discord
from discord_bot import DiscordBot

@pytest.mark.asyncio
async def test_status_command():
    bot = DiscordBot(token="test", bot_name="Test")
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    await bot.status_command(interaction)

    interaction.followup.send.assert_called_once()
```

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=debug python -m src.main
```

### Breakpoints

```python
import pdb; pdb.set_trace()
# or
breakpoint()
```

### VS Code Debugging

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Main (Webhook)",
      "type": "python",
      "request": "launch",
      "module": "src.main",
      "env": {
        "DISCORD_WEBHOOK_URL": "YOUR_WEBHOOK_URL",
        "FACTORIO_LOG_PATH": "/path/to/console.log",
        "LOG_LEVEL": "debug"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "Python: Main (Bot)",
      "type": "python",
      "request": "launch",
      "module": "src.main",
      "env": {
        "DISCORD_BOT_TOKEN": "YOUR_BOT_TOKEN",
        "DISCORD_EVENT_CHANNEL_ID": "YOUR_CHANNEL_ID",
        "FACTORIO_LOG_PATH": "/path/to/console.log",
        "RCON_ENABLED": "true",
        "RCON_HOST": "localhost",
        "RCON_PORT": "27015",
        "LOG_LEVEL": "debug"
      },
      "console": "integratedTerminal"
    }
  ]
}
```

## Contributing

### Workflow

1. **Create a feature branch**

   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make changes**

   - Follow existing style and type hints.
   - Add tests for new behavior.
   - Update docs where relevant.
   - Consider security implications (regex, RCON, Discord actions).

3. **Run checks**

   ```bash
   pytest
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

4. **Commit**

   ```bash
   git add .
   git commit -m "feat(rcon): add UPS monitoring and alerts"
   ```

5. **Push and open PR**

   ```bash
   git push origin feature/amazing-feature
   ```

### Commit Messages

Use conventional commits:

```text
type(scope): subject
```

Examples:

```text
feat(parser): add support for milestone events
fix(tailer): handle log rotation on Windows
docs(patterns): document mentions.yml and secmon.yml
security(parser): tighten regex validation for user patterns
```

Types:

- `feat` – new feature
- `fix` – bug fix
- `docs` – documentation
- `style` – formatting only
- `refactor` – refactoring
- `test` – tests only
- `chore` – build/infra
- `security` – security-related changes

### Code Review Checklist

Before opening a PR:

- [ ] All tests pass
- [ ] Coverage is acceptable
- [ ] `black` and `ruff` clean
- [ ] `mypy` passes
- [ ] New config options documented
- [ ] Security considerations addressed
- [ ] Clear PR description

## Adding New Features

### New Event Pattern (YAML)

1. **Add to `patterns/*.yml`**:

   ```yaml
   events:
     low_ups_warning:
       pattern: 'UPS dropped below (\\d+)'
       type: server
       emoji: "⚠️"
       message: "Server performance degraded: {message}"
       enabled: true
       priority: 10
       channel: admin
   ```

2. **Add tests** in `tests/test_event_parser.py`.

3. **Reload patterns** via config (`PATTERN_FILES`) or restart.

### New Bot Command

1. Implement in `discord_bot.py` under the `factorio` command group.
2. Add tests in `tests/test_discord_bot.py`.
3. Ensure permissions and rate limiting are respected.

## Release Process

### Version Bump

Update:

- `pyproject.toml`
- `src/__init__.py`

### Tag and Push

```bash
git tag -a v2.0.0 -m "Release v2.0.0 - Bot + RCON + Metrics"
git push origin v2.0.0
```

Your CI (if configured) should:

- Run tests
- Build and push Docker image
- Create GitHub release

## Getting Help

- 💬 Discussions: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 🐛 Issues: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)

---

_Current project status: Phases 1–6 implemented (log tailing, YAML patterns, multi-channel routing, RCON stats, Discord bot with slash commands, admin commands, multi-server support, and metrics/alerts) with high test coverage across core modules._
