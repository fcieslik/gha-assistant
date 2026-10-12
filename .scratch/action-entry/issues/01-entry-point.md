# 01: Punkt wejścia `python -m gha_assistant`

Spec: `.scratch/action-entry/spec.md`

**What to build:** `__main__.py` buduje `ReviewState` z eventu `pull_request` (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, `GITHUB_WORKSPACE`), uruchamia graf i zwraca kod wyjścia. Lokalnie `--dry-run --base-ref origin/main --repo-path .` działa bez eventu.

**Blocked by:** nic.

**Status:** ready-for-agent

- [x] Stan z eventu: `base_ref=origin/<base.ref>`, `head_sha` z `pull_request.head.sha`, `pr_number`, `pr_title`, `pr_body` (`null` jako pusty), `repo`, `repo_path`
- [x] Event bez `pull_request`, brak eventu bez `--dry-run --base-ref`, brak `ANTHROPIC_API_KEY`: kod 2, linia `::error::` w Actions, model i GitHub nietknięte
- [x] PR z forka: kod 0 i komunikat, bez wywołania modelu i GitHuba, także bez klucza
- [x] Błąd runa (trwały błąd API): kod 1, pierwsza linia stderr to `::error::gha-assistant: <Typ>: <komunikat>`, bez komentarza; poza Actions linia zaczyna się od `error:`
- [x] Usunięte pozostałe `print("... hello world")` z `collect_input` i `publish`
- [x] Testy (`tests/test_main.py`) na atrapach agenta i GitHuba
