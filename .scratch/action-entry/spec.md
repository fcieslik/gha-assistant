# Spec: agent uruchamialny z GitHub Actions w innym repozytorium

## Problem

Graf działa lokalnie i w testach, ale nie ma jak go uruchomić z workflow w innym repozytorium, a komentarz w PR pokazuje tylko liczbę uwag, nie same uwagi.

## Rozwiązanie

1. Punkt wejścia `python -m gha_assistant`: czyta event `pull_request` z Actions (albo `--dry-run --base-ref` lokalnie), buduje stan, uruchamia graf i kończy się czytelnym kodem wyjścia.
2. `action.yml` (composite action) w tym repozytorium: instaluje `uv`, uruchamia punkt wejścia kodem z `github.action_path`, a recenzuje checkout wywołującego workflow (katalog roboczy).
3. Komentarz ze statusem pokazuje Findings.

## Decyzje

- **Kod i recenzowane repozytorium są rozdzielone:** `uv run --project "$ACTION_PATH"` uruchamia kod akcji, a katalog roboczy zostaje checkoutem repozytorium docelowego (`GITHUB_WORKSPACE`). Agent czyta tylko ten checkout.
- **Checkout robi wywołujący workflow** (`fetch-depth: 0`), nie akcja. `base_ref` to `origin/<base.ref>` z eventu; `head_sha`, `pr_number`, tytuł i opis też z eventu (`body` bywa `null`).
- **Sekrety przez `env`, nie przez argumenty:** `GITHUB_TOKEN` (domyślnie `github.token`) i `ANTHROPIC_API_KEY`.
- **Kody wyjścia:** 0 gotowe lub pominięte (PR z forka), 1 błąd runa (np. zły klucz; linia `::error::` z komunikatem SDK, bez komentarza), 2 złe uruchomienie (brak klucza, event bez `pull_request`, brak `--dry-run` bez eventu). Kod 2 nie wywołuje modelu.
- **PR z forka jest pomijany bez błędu:** token tylko do odczytu i brak sekretów, więc publikacja i tak by się nie udała.
- **Findings w komentarzu:** waga, miejsce, treść, sugestia i `spec_ref`, każde pole jako jedna linia w code span (jak ostrzeżenia), bo treść pochodzi z modelu i z PR, a komentarz jest publiczny (`@nick`, linki, obrazki, HTML pozostają nieaktywne). Bez limitu w rendererze: `judge_findings` tnie do 15.
- **Bez cache `uv`** (`enable-cache: false`): repozytorium docelowe nie ma `uv.lock`, a cache zależy od jego plików.

## Poza zakresem

Komentarze przy liniach (Reviews API), sędzia z modelem, PR z forków, własny proxy do klucza (Bedrock), wersjonowanie `v1` (tag po teście w repozytorium testowym).
