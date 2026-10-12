# 02: `action.yml` (composite action)

Spec: `.scratch/action-entry/spec.md`

**What to build:** Akcja do użycia z innego repozytorium: `uses: <owner>/gha-assistant@v1`. Wejścia: `anthropic-api-key` (wymagane) i `github-token` (domyślnie `github.token`).

**Blocked by:** 01.

**Status:** ready-for-agent

- [x] `astral-sh/setup-uv` w przypiętej wersji, bez cache
- [x] Krok uruchamia `uv run --frozen --no-dev --project "$ACTION_PATH" python -m gha_assistant`; katalog roboczy zostaje checkoutem wywołującego
- [x] Sekrety trafiają przez `env`, nie przez argumenty
- [x] Komentarz w `action.yml`: wywołujący workflow musi zrobić `actions/checkout` z `fetch-depth: 0`
- [x] `README.md`: przykład workflow dla repozytorium docelowego i uruchomienie lokalne
- [ ] Test w prawdziwym repozytorium na GitHubie (repozytorium testowe, prawdziwy klucz): czas runa, koszt, uprawnienia tokenu, instalacja `claude` na runnerze Linux. Wykonuje użytkownik; dopiero potem tag `v1`
