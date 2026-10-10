# 01: Tracer bullet: Change z prawdziwego PR przechodzi przez graf

Spec: `.scratch/change-collection/spec.md`

**What to build:** `invoke` skompilowanego grafu z `base_ref`, `repo_path`, `pr_title` i `pr_body` na prawdziwym repozytorium git (gałąź PR zmergowana do bazy, baza poszła do przodu po utworzeniu merge commita) zwraca w stanie `change` z listą plików zmienionych w PR. Zmiany nazw liczą się pod nową ścieżką. Klasyfikacja jest na razie minimalna: plik usunięty trafia do `ignored`, każdy inny do `code`; `intent` zostaje puste do ticketu 02. Przy okazji graf traci stubowe pole `diff` i redundantny smoke test importu, bo kolejne kroki budują już na czystszej bazie.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Osobny moduł udostępnia `collect_change(base_ref, repo)` zwracające `Change` z trzema listami ścieżek (`intent`, `code`, `ignored`); nie importuje niczego z grafu, stanu ani węzłów
- [ ] Lista plików pochodzi z lokalnego `git diff --name-status` z wykrywaniem zmian nazw, w wersji trzykropkowej względem `origin/<base>`; GitHub API nie jest używane
- [ ] Wewnątrz modułu: cienkie wywołanie gita oraz czysta funkcja parsująca tekst `name-status` (zmiana nazwy zapisuje tylko nową ścieżkę)
- [ ] `ReviewState` ma pola wejściowe `base_ref`, `repo_path`, `pr_title`, `pr_body` (opcjonalne w typie), pole `change` typu `Change` oraz `summary`; pole `diff` zostało usunięte, a stubowy `collect_input` go nie ustawia
- [ ] `collect_input` wywołuje `collect_change` z wartościami ze stanu i zwraca aktualizację z polem `change`; nie czyta `os.environ` ani payloadu zdarzenia
- [ ] Test na poziomie grafu (`invoke`) z tymczasowym repozytorium git: PR ze zmienionym, dodanym, usuniętym i przemianowanym plikiem daje w `change` oczekiwane ścieżki (usunięty w `ignored`, pozostałe w `code`)
- [ ] Test semantyki trzech kropek: baza poszła do przodu po utworzeniu merge commita, a wynik zawiera dokładnie zmiany PR
- [ ] Pierwsze tekstowe fixture'y `name-status` dla parsera (zmiana, dodanie, usunięcie, zmiana nazwy, pusty diff)
- [ ] Istniejący test grafu dostosowany do nowych danych wejściowych, a `test_package.py` usunięty (import pakietu pokrywa test grafu)
- [ ] `uv run ruff check`, `uv run ruff format --check` i `uv run pytest` przechodzą
