# 06: Prawdziwy `review_intent`

Spec: `.scratch/review-agent/spec.md`

**What to build:** `review_intent` ocenia zgodność zmiany z Intent files w jednym przejściu: czyta Intent files z PR (Spec, Tickety, ADR) i sprawdza, czy zmiana robi to, o co w nich prosi. Prompt systemowy to `prompts/review_intent.md`; wiadomość użytkownika musi dostarczyć bloki, które ten prompt opisuje (patrz niżej). Wynik to Findings ze `source` równym `spec` i wymaganym `spec_ref`, w tym uwagi ogólne dla niezrealizowanych kryteriów. Node ma własny `RetryPolicy`.

**Blocked by:** 05 (`validate_findings`).

**Status:** ready-for-agent

- [x] Wiadomość użytkownika ma bloki z `prompts/review_intent.md`: `<intent_files>` (ścieżki, treść czytana narzędziem), `<changed_files>` (`change["code"]`), `<diff path=...>` per plik (z limitem jak `MAX_DIFF_CHARS`) i `<pr>` (tytuł i opis, najniższy priorytet)
- [x] Finding o niezrealizowanym kryterium nie ma `file` i `line`, ma `spec_ref`; sprzeczność ze Spec lub ADR jest zakotwiczona w pliku i linii, gdy się da
- [x] Zmiana spoza deklarowanego zakresu jest zgłaszana jako Finding ze `spec_ref`
- [x] Treść Intent files jest czytana narzędziem, nie trzymana w stanie; tytuł i opis PR są kontekstem o najniższym priorytecie i same nie uruchamiają node
- [x] Wywołanie `run_agent` z `max_turns=REVIEW_INTENT_MAX_TURNS` (100) i `max_budget_usd=REVIEW_INTENT_MAX_BUDGET_USD` ($0.75), bo agent przechodzi przez wszystkie zmienione pliki w jednym przebiegu; stałe są już w `agent.py`
- [x] `AGENT_RETRY` (wspólna polityka z ticketu 04) i model `REVIEW_MODEL` (Haiku); dłuższy timeout noda niż `review_code` (czyta Intent files i wiele plików w jednym przebiegu), po wyczerpaniu ostrzeżenie i review bez części "spec"
- [x] Testy na granicy z atrapą: PR z Intent files daje Findings `spec`; PR bez Intent files nie uruchamia node; awaria po retry nie przerywa grafu
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą

## Decyzje przy implementacji

- **Degradacja przez graf zagnieżdżony, nie zwykły `error_handler`.** `review_intent` zawsze startuje w tym samym kroku co workerzy `review_code`, a `add_node(error_handler=...)` w LangGraph 1.2.14 działa tylko dla taska samotnego w kroku: z rodzeństwem handler się wykonuje, rodzeństwo kończy pracę, a run i tak rzuca oryginalny błąd (spike w scratchpadzie: ten sam graf bez rodzeństwa kończy się poprawnie). Dlatego node to cienka funkcja, która woła jednowęzłowy graf zagnieżdżony (`attempt`) z `AGENT_RETRY`, timeoutem i `error_handler`, a zwraca tylko przyrost `candidates` i `warnings`. Testy pilnują, żeby nikt nie "uprościł" tego z powrotem do zwykłego `error_handler`. Spec miał "topologia płaska, bez subgraphów"; wyjątek jest zapisany w specu, a topologia widoczna z zewnątrz jest bez zmian.
- **Handler degraduje tylko błędy, które `AGENT_RETRY` ponawia** (`is_transient_agent_error`). Trwały (zły klucz API) leci dalej i kończy run, jak w `review_code`. Ostrzeżenie zawiera nazwę typu wyjątku, nie jego treść: ostrzeżenia trafią do publicznego komentarza (ticket 09). Ticket 09 może użyć tego samego wzorca dla `review_code`.
- **Timeout próby: 5 minut** (`REVIEW_INTENT_TIMEOUT_SECONDS`), czyli 10 minut dla 2 prób, równolegle z `review_code`; reszta z 15 minut runnera zostaje na `verify_finding`, `judge_findings` i `publish`. Nie potwierdzone z użytkownikiem. 100 tur Haiku może trwać dłużej niż 5 minut; nie zmierzone (jeden test z 4 turami: 5,6 s). Próba ucięta timeoutem jest ponawiana i kosztuje kolejny budżet, więc worst case to 2 x $0.75.
- **Diffy mają jeden wspólny budżet `MAX_DIFF_CHARS`** (60 000 znaków), nie limit na plik: ten jeden przebieg widzi wszystkie zmienione pliki, więc limit na plik nie chroniłby przed przepełnieniem kontekstu. Diff ucięty lub pominięty dostaje notkę i agent doczytuje plik narzędziem (bez numerów zmienionych linii, bo nie ma `git`).
- **Identyfikatory** to `spec:{n}` nadawane przez kod; schemat wymaga tylko `severity`, `message` i `spec_ref`, a `file`, `line`, `evidence` i `suggestion` są opcjonalne (uwaga ogólna ich nie ma).
- **Test z prawdziwym modelem** (`test_real_model_finds_a_requirement_the_change_does_not_meet`) potwierdza kształt wyniku na jednym małym zestawie, nie jakość przy wielu plikach.
