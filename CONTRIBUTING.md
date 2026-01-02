# Contributing to RAG LLM Drive Connector

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/rag-llm-drive-connector.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Submit a pull request

## Development Setup

### Using Conda (Recommended)

```bash
# Create conda environment
conda env create -f environment.yml

# Activate environment
conda activate rag-llm-drive-connector

# Install development dependencies
pip install pytest pytest-cov black isort flake8 mypy
```

### Using Virtual Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black isort flake8 mypy
```

See the [README.md](README.md) for more detailed setup instructions.

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints where possible
- Maximum line length: 127 characters
- Use black for formatting
- Use isort for import sorting

### Code Formatting

```bash
# Format code
black .

# Sort imports
isort .

# Check formatting
black --check .
isort --check-only .
```

### Linting

```bash
# Run linter
flake8 .

# With configuration
flake8 . --max-line-length=127 --extend-ignore=E203
```

## Testing

- Write tests for new features
- Ensure all tests pass
- Aim for good test coverage

```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

## Commit Messages

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Other changes

Example:
```
feat: Add support for Dropbox integration
fix: Resolve OAuth token refresh issue
docs: Update deployment documentation
```

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure CI/CD pipeline passes
4. Update CHANGELOG.md if applicable
5. Request review from maintainers

## Questions?

Open an issue or contact the maintainers.

