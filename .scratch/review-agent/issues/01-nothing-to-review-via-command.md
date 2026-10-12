# 01: Wyjście bez kodu do recenzji przez `Command` i node `nothing_to_review`

Spec: `.scratch/review-agent/spec.md`

**What to build:** PR, po którym nie zostaje nic w `change["code"]` (tylko dokumentacja, lockfile, binaria lub Intent files), kończy się w dedykowanym, ostatnim nodzie, który tylko wypisuje informację, że nie ma czego sprawdzać. `collect_input` zwraca `Command`: w `update` niesie `change`, a `goto` kieruje do `nothing_to_review`, gdy `change["code"]` jest puste, w przeciwnym razie do dotychczasowego następnego kroku (`run_agent`). Dotychczasowa krawędź warunkowa po `collect_input` jest usuwana, bo `Command` i krawędź z tego samego node wykonałyby się oba. Decyzja o wyjściu to jedna czysta funkcja na podstawie `change`.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [x] `collect_input` zwraca `Command` w obu ścieżkach, z `update` niosącym `change`; typ zwrotny deklaruje cele (`Command[Literal[...]]`), więc graf zna krawędzie
- [x] Krawędź warunkowa po `collect_input` (`_route_after_collect`) usunięta; cała decyzja o wyjściu jest w jednej czystej funkcji wybierającej cel z `change`
- [x] Nowy node `nothing_to_review` wypisuje komunikat z liczbą plików ignorowanych i Intent files, nie zmienia stanu i prowadzi do END
- [x] Test na poziomie grafu (`stream_mode="updates"`): PR zawierający tylko dokumentację i lockfile wykonuje wyłącznie `collect_input` i `nothing_to_review`; `run_agent` i `publish` nie wykonują się wcale (dowód, że nie ma podwójnego routingu)
- [x] Test na poziomie grafu: PR z kodem wykonuje `collect_input`, `run_agent`, `publish`, a `nothing_to_review` się nie wykonuje
- [x] Komunikat z `nothing_to_review` jest asertowany (zawiera liczby ignorowanych i intent)
- [x] Brak `base_ref` lub `repo_path` nadal kończy się `ValueError` z `collect_input`, a nie przekierowaniem; `RetryPolicy` na `collect_input` działa jak wcześniej (testy retry z `test_graph.py` przechodzą)
- [x] Istniejące testy grafu dostosowane (test "pusty `code` kończy graf" teraz oczekuje `nothing_to_review`)
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
