# 06: Prawdziwy `review_intent`

Spec: `.scratch/review-agent/spec.md`

**What to build:** `review_intent` ocenia zgodność zmiany z Intent files w jednym przejściu: czyta Intent files z PR (Spec, Tickety, ADR) i sprawdza, czy zmiana robi to, o co w nich prosi. Prompt systemowy to `prompts/review_intent.md`; wiadomość użytkownika musi dostarczyć bloki, które ten prompt opisuje (patrz niżej). Wynik to Findings ze `source` równym `spec` i wymaganym `spec_ref`, w tym uwagi ogólne dla niezrealizowanych kryteriów. Node ma własny `RetryPolicy`.

**Blocked by:** 05 (`validate_findings`).

**Status:** ready-for-agent

- [ ] Wiadomość użytkownika ma bloki z `prompts/review_intent.md`: `<intent_files>` (ścieżki, treść czytana narzędziem), `<changed_files>` (`change["code"]`), `<diff path=...>` per plik (z limitem jak `MAX_DIFF_CHARS`) i `<pr>` (tytuł i opis, najniższy priorytet)
- [ ] Finding o niezrealizowanym kryterium nie ma `file` i `line`, ma `spec_ref`; sprzeczność ze Spec lub ADR jest zakotwiczona w pliku i linii, gdy się da
- [ ] Zmiana spoza deklarowanego zakresu jest zgłaszana jako Finding ze `spec_ref`
- [ ] Treść Intent files jest czytana narzędziem, nie trzymana w stanie; tytuł i opis PR są kontekstem o najniższym priorytecie i same nie uruchamiają node
- [ ] Wywołanie `run_agent` z `max_turns=REVIEW_INTENT_MAX_TURNS` (100) i `max_budget_usd=REVIEW_INTENT_MAX_BUDGET_USD` ($0.75), bo agent przechodzi przez wszystkie zmienione pliki w jednym przebiegu; stałe są już w `agent.py`
- [ ] `AGENT_RETRY` (wspólna polityka z ticketu 04) i model `REVIEW_MODEL` (Haiku); dłuższy timeout noda niż `review_code` (czyta Intent files i wiele plików w jednym przebiegu), po wyczerpaniu ostrzeżenie i review bez części "spec"
- [ ] Testy na granicy z atrapą: PR z Intent files daje Findings `spec`; PR bez Intent files nie uruchamia node; awaria po retry nie przerywa grafu
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
