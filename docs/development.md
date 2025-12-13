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

## Running Tests

Factorio ISR maintains comprehensive test coverage through automated test suites.

### Run Tests

```bash
pytest
```

### Run with Coverage Report

```bash
pytest --cov=src --cov-report=html --cov-report=term
```

View the generated coverage report:

```bash
open htmlcov/index.html      # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test File

```bash
pytest tests/test_event_parser.py -v
pytest tests/test_discord_bot.py -v
```

## Code Quality

The project uses industry-standard Python tools for code formatting and quality checks.

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

Local development uses relative paths for configuration:

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

# Run container
docker run --rm \
  --env-file .env \
  -v /path/to/factorio/logs:/factorio/logs:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v $(pwd)/config:/app/config:ro \
  -p 8080:8080 \
  factorio-isr:dev
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

Contributions are welcome! Factorio ISR is dual-licensed under AGPL-3.0 and commercial licensing.

### Contribution Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make changes**
   - Follow existing code style and type hints
   - Add tests for new functionality
   - Ensure all tests pass

3. **Run quality checks**
   ```bash
   pytest
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat(feature-name): brief description"
   ```

5. **Push and open a pull request**
   ```bash
   git push origin feature/amazing-feature
   ```

### Licensing

By contributing to this project, you agree to license your contributions under the same AGPL-3.0 / Commercial dual-license terms.

For commercial licensing questions or proprietary enhancement licensing, contact [licensing@laudiversified.com](mailto:licensing@laudiversified.com).

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
