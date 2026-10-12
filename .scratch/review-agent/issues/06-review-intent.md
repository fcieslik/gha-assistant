# 06: Prawdziwy `review_intent`

Spec: `.scratch/review-agent/spec.md`

**What to build:** `review_intent` ocenia zgodność zmiany z Intent files w dwóch etapach (prompt chaining): najpierw wyciąga z nich listę kryteriów z odwołaniem do pliku, potem sprawdza każde kryterium względem zmiany. Wynik to Findings ze `source` równym `spec` i wymaganym `spec_ref`, w tym uwagi ogólne dla niezrealizowanych kryteriów. Node ma własny `RetryPolicy`.

**Blocked by:** 05 (`validate_findings`).

**Status:** ready-for-agent

- [ ] Etap 1 zwraca listę kryteriów z odwołaniem do pliku Intent; etap 2 sprawdza je względem zmiany narzędziami tylko do odczytu
- [ ] Finding o niezrealizowanym kryterium nie ma `file` i `line`, ma `spec_ref`; sprzeczność ze Spec lub ADR jest zakotwiczona w pliku i linii, gdy się da
- [ ] Zmiana spoza deklarowanego zakresu jest zgłaszana jako Finding ze `spec_ref`
- [ ] Treść Intent files jest czytana narzędziem, nie trzymana w stanie; tytuł i opis PR są kontekstem o najniższym priorytecie i same nie uruchamiają node
- [ ] `AGENT_RETRY` (wspólna polityka z ticketu 04) i model `REVIEW_MODEL` (Haiku); dłuższy timeout noda niż `review_code` (dwa etapy), po wyczerpaniu ostrzeżenie i review bez części "spec"
- [ ] Testy na granicy z atrapą: PR z Intent files daje Findings `spec`; PR bez Intent files nie uruchamia node; awaria po retry nie przerywa grafu
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
