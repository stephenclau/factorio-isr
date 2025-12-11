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
│   ├── discord_bot.py           # Discord bot with slash commands
│   ├── discord_interface.py     # Unified Discord interface
│   ├── log_tailer.py            # Real-time log monitoring
│   ├── rcon_client.py           # RCON client with metrics/stats
│   ├── server_manager.py        # Multi-server coordination
│   ├── security_monitor.py      # Security monitoring and rate limiting
│   ├── mention_resolver.py      # @mention parsing and resolution
│   └── health.py                # Health check server
├── tests/
│   ├── test_main.py
│   ├── ...                      # Comprehensive test suite
├── patterns/                    # YAML event patterns
├── config/                      # Configuration files
│   ├── servers.yml              # Multi-server configuration
│   ├── mentions.yml             # Role mention vocabulary
│   └── secmon.yml               # Security monitor settings
└── docs/                        # Documentation
```

## Running Tests

### Coverage Target

We maintain a strict code coverage standard. The default target for code coverage is **91%**.

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

### Type Checking with mypy

```bash
mypy src/
```

## Running Locally

### Create Environment File

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables for Bot mode:

```env
DISCORD_BOT_TOKEN=your-bot-token
LOG_LEVEL=info
LOG_FORMAT=json
HEALTH_CHECK_PORT=8080
```

### Configuration Setup

Local development mimics the production environment by using relative paths for configuration:

1. Ensure `config/servers.yml` exists and is configured.
2. Ensure `patterns/` contains valid YAML pattern files.

### Run the Application

```bash
python -m src.main
```

### Run with Docker

```bash
# Build local image
docker build -t factorio-isr:dev .

# Run container (mounting config and patterns to /app/...)
docker run --rm \
  --env-file .env \
  -v /path/to/factorio/logs:/factorio/logs:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v $(pwd)/config:/app/config:ro \
  -p 8080:8080 \
  factorio-isr:dev
```

## Working with the Discord Bot

### Local Bot Smoke Test

```python
import asyncio
from discord_bot import DiscordBot

async def main():
    bot = DiscordBot(token="YOUR_TEST_TOKEN")
    await bot.connect_bot()
    # Let it run briefly
    await asyncio.sleep(10)
    await bot.disconnect_bot()

asyncio.run(main())
```

## Debugging

### VS Code Debugging

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Main (Bot)",
      "type": "python",
      "request": "launch",
      "module": "src.main",
      "env": {
        "DISCORD_BOT_TOKEN": "YOUR_BOT_TOKEN",
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
   - Add tests for new behavior (maintain >91% coverage).

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

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
