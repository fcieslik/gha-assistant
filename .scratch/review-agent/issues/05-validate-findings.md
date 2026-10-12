# 05: `validate_findings`: deterministyczna walidacja Findings

Spec: `.scratch/review-agent/spec.md`

**What to build:** Zamiana przepuszczalnika `validate_findings` na prawdziwą, czystą funkcję bez modelu, która odrzuca Findings wskazujące nieistniejące miejsca. Powód każdego odrzucenia trafia do ostrzeżeń, żeby dało się go zobaczyć.

**Blocked by:** 04 (Granica wykonania Agenta i prawdziwy `review_code`).

**Status:** ready-for-agent

- [x] Funkcja odrzuca Finding, gdy plik nie należy do `change["code"]`, linia wykracza poza plik, `evidence` nie występuje we wskazanej linii, albo brakuje `spec_ref` przy `source` równym `spec`
- [x] Finding bez `file` i `line` (uwaga ogólna) jest przepuszczany, jeśli ma `spec_ref`
- [x] Dokładne duplikaty (ten sam plik, linia i źródło) są usuwane, zostaje jeden
- [x] Powód odrzucenia trafia do ostrzeżeń w stanie
- [x] Tabela przypadków na czystej funkcji: plik spoza zmiany, linia poza plikiem, cytat nieobecny, brak `spec_ref`, duplikat, uwaga ogólna
- [x] Test na poziomie grafu: recenzent zwracający zmyślony plik daje Review bez tego Findingu i z ostrzeżeniem
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą

## Decyzje przy implementacji

Ticket i spec nie rozstrzygały tych przypadków; wybrane najprostsze zachowanie, do zmiany, jeśli się nie sprawdzi:

- **Numeracja linii** odnosi się do pliku w katalogu roboczym (`repo_path`), czyli tego, który czytają agenci. Linie liczone jak w GitHubie (podział po `\n`); nieczytelny plik ma zero linii.
- **`evidence`** to dosłowny podciąg wskazanej linii (po `strip()`); cytat wieloliniowy jest odrzucany. Brak `evidence` lub `line` oznacza brak tego sprawdzenia.
- **`file` bez `line`** przechodzi, jeśli plik jest w `change["code"]`; **`line` bez `file`** jest odrzucane.
- **Uwaga ogólna bez `spec_ref`** jest odrzucana także przy `source` równym `code`.
- **Duplikaty:** klucz (plik, linia, źródło); zostaje najpoważniejszy, a przy remisie pierwszy. Uwagi ogólne nie mają miejsca, więc ich klucz to (źródło, `spec_ref`, `message`), żeby dwa różne niespełnione kryteria nie zlały się w jedno. Usunięty duplikat też trafia do ostrzeżeń.
- **Ostrzeżenia** są po polsku, jak reszta tekstów dla czytelnika Review; renderowanie ich w komentarzu to ticket 09.
