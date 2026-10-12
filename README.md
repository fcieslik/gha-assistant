# gha-assistant

Code-review agent for GitHub pull requests, run from GitHub Actions. Built with LangGraph and the Claude Agent SDK.

This is a learning project. Goals and design decisions:

- [docs/LEARNING_GOAL.md](docs/LEARNING_GOAL.md)
- [docs/PROJECT_GOAL.md](docs/PROJECT_GOAL.md)

## Użycie w innym repozytorium

Workflow w repozytorium docelowym (`.github/workflows/gha-assistant.yml`):

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: gha-assistant-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: <owner>/gha-assistant@v1
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Wymagania: sekret `ANTHROPIC_API_KEY` w repozytorium docelowym, repozytorium `gha-assistant` publiczne (albo z włączonym dostępem w _Settings → Actions → General_). PR z forka jest pomijany.

Lokalnie, na dowolnym repozytorium z gałęzią PR (komentarz tylko się wypisuje):

```bash
cd /ścieżka/do/innego/repo
uv run --env-file /ścieżka/do/gha-assistant/.env --project /ścieżka/do/gha-assistant \
  python -m gha_assistant --dry-run --base-ref origin/main
```

## Development

```bash
uv sync            # install dependencies
uv run pytest      # tests
uv run ruff check  # lint
uv run ruff format # format
```
