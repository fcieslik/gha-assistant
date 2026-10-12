# 08: `judge_findings` zamyka Review (bez modelu)

Spec: `.scratch/review-agent/spec.md`

**What to build:** `judge_findings` zamyka Review czystą funkcją, bez wywołania modelu: odrzuca Findings obalone przez weryfikatora, sortuje wg wagi, tnie do limitu i buduje `summary` z liczb. Node zostaje w grafie pod tą samą nazwą, więc routing i krawędzie się nie zmieniają. Pierwotny ticket opisywał sędziego z modelem (Sonnet, bez narzędzi, decyzje po `id`); odłożony, patrz niżej.

**Blocked by:** 07 (Prawdziwy `verify_finding`).

**Status:** ready-for-agent

- [x] Finding z werdyktem `refuted` nie trafia do Review; `confirmed`, `inconclusive` i brak werdyktu zostają
- [x] Findings są posortowane wg wagi (`high`, `medium`, `low`), przy równej wadze zachowują kolejność
- [x] Limit `MAX_FINDINGS` (15) tnie listę po sortowaniu, więc zostają najpoważniejsze
- [x] `summary` podaje liczbę uwag wg wagi oraz liczbę odrzuconych i pominiętych ponad limit; bez uwag i bez odrzuceń jest pusty
- [x] Werdykt z nieznanym `id` jest ignorowany; funkcja nie zmienia danych wejściowych
- [x] Funkcja `finalize_review` jest czysta; tabela przypadków w `tests/test_judge_findings.py`
- [x] Test na granicy grafu: Finding obalony nie trafia do komentarza, a limit zostawia najpoważniejsze
- [x] Martwa stała `JUDGE_MODEL` usunięta z serwisu Agenta
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą

## Decyzje przy implementacji

- **Bez modelu (zmiana wobec pierwotnego ticketu).** Dwa agenty recenzują na dwóch osiach, a weryfikator sprawdza Findings `high`. Sędzia bez narzędzi nie sprawdza prawdy, tylko porządkuje listę, a koszt to jedno wywołanie Sonneta na PR, opóźnienie i kolejny punkt awarii. Z jego zadań zostaje w kodzie to, co da się zrobić regułą: odrzucenie `refuted`, sortowanie, limit, `summary`. To dokładnie dawne „Review awaryjne”, które i tak było potrzebne; teraz jest jedyną ścieżką.
- **Co tracimy.** Duplikaty semantyczne (ta sama usterka innymi słowami, w innej linii, albo `code` i `spec` o tym samym) nie są scalane; `validate_findings` łapie tylko to samo miejsce i to samo źródło. Czysty styl nie jest filtrowany po stronie modelu: da się go ograniczyć promptem `review_code`. `medium` i `low` nikt nie weryfikuje, ale sędzia bez narzędzi też by tego nie zrobił.
- **Kiedy wracamy do sędziego z modelem.** Gdy prawdziwe runy pokażą duplikaty lub szum. Wzorzec (`AGENT_RETRY`, `error_handler`, schemat decyzji po `id`) jest opisany w specu, a parametr `tools=[]` w serwisie Agenta zostaje z testem.
- **Nazwa node bez zmian.** `judge_findings` nie woła modelu; nazwa zostaje, żeby nie ruszać grafu, diagramu ani routingu z ticketu 07.
- **`summary` to liczby, nie proza.** Komentarz ma już linię statusu („sprawdzono plików: N, uwagi: M”), więc `summary` dodaje rozkład wag i to, co odrzucono. Zdanie o całym PR wymagałoby modelu.
- **`inconclusive` zostaje w Review bez adnotacji.** Finding nie jest tracony; wyróżnienie niezweryfikowanych uwag czeka na renderowanie Findings w komentarzu (dziś komentarz pokazuje tylko liczbę i `summary`).
- **`SEVERITY_RANK` w `finding.py`.** Ranga wag była prywatna w `validate_findings`; używają jej teraz dwa moduły.
