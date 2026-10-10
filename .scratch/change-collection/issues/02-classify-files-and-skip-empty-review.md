# 02: Klasyfikacja plików i zakończenie grafu bez kodu do recenzji

Spec: `.scratch/change-collection/spec.md`

**What to build:** PR z kodem i dołączonymi plikami Spec, Ticket i ADR daje w stanie `change` wyraźny podział: Intent files w `intent`, pliki do recenzji w `code`, a lockfile'e, binaria i dokumentacja spoza Intent w `ignored`. Gdy po klasyfikacji nie zostaje nic w `code`, graf kończy się od razu: nie wołamy `run_agent` ani `publish` i nic nie trafia do PR. Dokumentacja projektu opisuje trigger z `paths-ignore` i nowy układ modułów.

**Blocked by:** 01 (Tracer bullet: Change z prawdziwego PR przechodzi przez graf).

**Status:** ready-for-agent

- [ ] Pliki pasujące do `.scratch/**/*.md` i `docs/adr/**/*.md` trafiają do `intent` i nie występują w `code`
- [ ] Do `ignored` trafiają: lockfile'e (`*.lock`, `package-lock.json`, `pnpm-lock.yaml`), binaria rozpoznawane po rozszerzeniu, `dist/`, `*.min.*` oraz dokumentacja spoza Intent (`*.md` i `docs/**`, w tym `README.md`, `CONTEXT.md`, `docs/agents/*.md`)
- [ ] Kolejność reguł jest jawna: usunięty → intent → ignorowane → code; `docs/adr/*.md` jest Intent mimo dopasowania do `docs/**`, a usunięty Intent file trafia do `ignored`
- [ ] Wzorce są stałymi w module zbierania Change, bez konfiguracji per repozytorium
- [ ] Tabela przypadków klasyfikacji na tymczasowych repozytoriach (kod, Spec, Ticket, ADR, `README.md`, `CONTEXT.md`, `docs/agents/*.md`, lockfile, obrazek, plik usunięty, plik przeniesiony) oraz fixture'y parsera dla przypadków z kilkoma pasującymi wzorcami
- [ ] Po `collect_input` krawędź warunkowa kieruje do `run_agent`, gdy `change["code"]` nie jest puste, a w przeciwnym razie do `END`
- [ ] Test na poziomie grafu: PR z kodem i Intent files przechodzi przez `run_agent` i `publish`; PR zawierający tylko dokumentację i lockfile kończy się bez wykonania `run_agent` i `publish`
- [ ] `PROJECT_GOAL.md`: przykładowy workflow z `paths-ignore` (`'**.md'`, `'docs/**'`) i kanoniczną listą wzorców, drzewo repozytorium z modułem Change, zdanie o diffie zmienione na "diff pobiera sam Agent swoim narzędziem tylko do odczytu"
- [ ] W `PROJECT_GOAL.md` zaznaczone, że agent nie jest wymaganym status checkiem (pominięty przez filtr workflow zostawia checki w stanie "Pending")
- [ ] `uv run ruff check`, `uv run ruff format --check` i `uv run pytest` przechodzą
