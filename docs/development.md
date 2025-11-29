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

```
factorio-isr/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration loader
│   ├── event_parser.py      # Event parsing logic
│   ├── discord_client.py    # Discord webhook client
│   ├── log_tailer.py        # Real-time log monitoring
│   └── health.py            # Health check server
├── tests/
│   ├── test_main.py
│   ├── test_event_parser.py
│   ├── test_discord_client.py
│   ├── test_log_tailer.py
│   └── test_config.py
├── docs/                    # Documentation
├── .env.example             # Example environment file
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Development dependencies
├── Dockerfile               # Production container
├── docker-compose.yml       # Docker Compose config
├── pyproject.toml          # Python project configuration
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
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Run Specific Test File

```bash
pytest tests/test_event_parser.py -v
```

### Run Specific Test

```bash
pytest tests/test_event_parser.py::test_parse_join_event -v
```

### Run in Watch Mode

```bash
pytest-watch
```

### Run with Debugging

```bash
pytest -v -s  # Show print statements
pytest --pdb  # Drop into debugger on failure
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
  -v /path/to/factorio/log:/factorio/log:ro \
  -p 8080:8080 \
  factorio-isr:dev
```

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=debug python -m src.main
```

### Use Python Debugger

Add breakpoint in code:
```python
import pdb; pdb.set_trace()
```

Or use the built-in breakpoint():
```python
breakpoint()
```

### Debug in VS Code

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Main",
      "type": "python",
      "request": "launch",
      "module": "src.main",
      "env": {
        "DISCORD_WEBHOOK_URL": "YOUR_WEBHOOK_URL",
        "FACTORIO_LOG_PATH": "/path/to/console.log",
        "LOG_LEVEL": "debug"
      },
      "console": "integratedTerminal"
    }
  ]
}
```

## Contributing

### Contribution Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make your changes**
   - Write code following the project style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests and linting**
   ```bash
   pytest
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add amazing feature"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/amazing-feature
   ```

6. **Open a Pull Request**
   - Go to GitHub and create a PR from your fork
   - Describe your changes clearly
   - Link any related issues

### Commit Message Guidelines

Follow conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(parser): add support for death events
fix(tailer): handle log rotation correctly
docs: update installation guide
```

### Code Review Checklist

Before submitting a PR, ensure:

- [ ] All tests pass
- [ ] Code coverage hasn't decreased
- [ ] Code is formatted with Black
- [ ] No linting errors from Ruff
- [ ] Type hints are correct (mypy passes)
- [ ] Documentation is updated
- [ ] Commit messages follow guidelines
- [ ] PR description explains the changes

## Adding New Features

### Adding a New Event Type

1. **Update event parser** (`src/event_parser.py`):
   ```python
   def parse_custom_event(self, line: str) -> Optional[Dict[str, Any]]:
       pattern = r"\[CUSTOM\] (.*)"
       match = re.search(pattern, line)
       if match:
           return {
               "type": "custom",
               "message": match.group(1)
           }
       return None
   ```

2. **Add tests** (`tests/test_event_parser.py`):
   ```python
   def test_parse_custom_event():
       parser = EventParser()
       result = parser.parse_custom_event("[CUSTOM] Something happened")
       assert result["type"] == "custom"
       assert result["message"] == "Something happened"
   ```

3. **Update Discord formatting** (`src/discord_client.py`):
   ```python
   def format_custom_event(self, event: Dict[str, Any]) -> str:
       return f"🎯 **Custom Event**: {event['message']}"
   ```

### Adding Configuration Options

1. Update `src/config.py`
2. Add environment variable to `.env.example`
3. Document in `docs/configuration.md`
4. Add tests for the new configuration

## Release Process

### Version Bumping

Update version in:
- `pyproject.toml`
- `src/__init__.py`

### Creating a Release

```bash
# Tag the release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# GitHub Actions will automatically:
# - Run tests
# - Build Docker image
# - Push to Docker Hub
# - Create GitHub release
```

## Getting Help

- 💬 **Discussions**: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 🐛 **Issues**: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 📧 **Email**: stephen.c.lau@gmail.com
