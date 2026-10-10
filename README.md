# gha-assistant

Code-review agent for GitHub pull requests, run from GitHub Actions. Built with LangGraph and the Claude Agent SDK.

This is a learning project. Goals and design decisions:

- [docs/LEARNING_GOAL.md](docs/LEARNING_GOAL.md)
- [docs/PROJECT_GOAL.md](docs/PROJECT_GOAL.md)

## Development

```bash
uv sync            # install dependencies
uv run pytest      # tests
uv run ruff check  # lint
uv run ruff format # format
```
