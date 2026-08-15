# Contributing to TraceMind

Thank you for contributing to **TraceMind**! We welcome contributions to enhance simulation realism, ML models, graph analytics, and developer tooling.

---

## 1. Development Workflow

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/rishabh211200/TraceMind.git
   cd TraceMind
   ```

2. **Set up local Python environment**:
   ```bash
   uv venv .venv --python 3.12
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev,ml]"
   ```

3. **Set up frontend dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Create a feature branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## 2. Code Quality & Standards

All code must satisfy:
* **Linting**: Checked via Ruff (`ruff check .`)
* **Formatting**: Formatted via Ruff (`ruff format --check .`)
* **Typing**: Strict type hints passing Mypy (`mypy packages apps tests`)
* **Testing**: Comprehensive tests passing Pytest (`pytest tests/ -v`)
* **Frontend**: TypeScript type check (`npm run type-check` in `frontend/`)

Run the full validation suite locally before committing:
```bash
make check
```

---

## 3. Git Commit Conventions

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

* `feat:` New feature
* `fix:` Bug fix
* `docs:` Documentation updates
* `test:` Adding or updating tests
* `refactor:` Code refactoring without behavioral changes
* `perf:` Performance improvements
* `chore:` Build, CI, or dependency updates

---

## 4. Pull Request Checklist

Before submitting a PR:
- [ ] Code adheres to type hints and style guidelines.
- [ ] New unit and integration tests added for new features.
- [ ] All tests pass locally and in CI.
- [ ] Documentation and ADRs updated if architectural changes are introduced.
- [ ] No proprietary terminology or credentials included.
