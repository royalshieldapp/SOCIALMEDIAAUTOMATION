# Contributing to SOCIALMEDIAAUTOMATION

Thank you for your interest in contributing to RoyalShield's Social Media Automation project! 🎉

## How to Get Started

### 1. Fork and Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/SOCIALMEDIAAUTOMATION.git
cd SOCIALMEDIAAUTOMATION
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -e ".[dev]"  # Install with dev dependencies
```

### 4. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### Running the Application Locally

```bash
cp .env.example .env
# Edit .env with your configuration
uvicorn SOCIALMEDIAAUTOMATION:app --reload
```

### Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=SOCIALMEDIAAUTOMATION  # With coverage
```

### Code Quality Checks

```bash
# Format code with Black
black SOCIALMEDIAAUTOMATION.py tests/

# Sort imports
isort SOCIALMEDIAAUTOMATION.py tests/

# Lint with flake8
flake8 SOCIALMEDIAAUTOMATION.py tests/
```

## Pull Request Process

1. **Update your branch** with the latest main
2. **Run all tests and checks** locally
3. **Push your branch** and create a Pull Request
4. **Reference related issues** if applicable

## Contribution Guidelines

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use [Black](https://github.com/psf/black) for formatting (88 character line length)
- Add docstrings to functions and classes
- Write tests for new features
- Update documentation
- Use conventional commit messages

## Commit Message Format

```
feat: Add new feature description
fix: Fix bug description
docs: Update documentation
test: Add/update tests
refactor: Refactor code section
chore: Update dependencies
```

## PR Checklist

- [ ] Tests pass locally
- [ ] Code is formatted with Black
- [ ] Imports are sorted with isort
- [ ] No flake8 warnings
- [ ] Documentation is updated
- [ ] Commit messages follow convention

## Testing Requirements

- All new features must include tests
- Maintain or improve code coverage
- Tests must pass on Python 3.11 and 3.12

## Questions?

- Open a GitHub Discussion
- Check [README.md](./README.md) for documentation
- Review [Issues](https://github.com/royalshieldapp/SOCIALMEDIAAUTOMATION/issues)

---

**Thank you for contributing to RoyalShield! 🚀**
