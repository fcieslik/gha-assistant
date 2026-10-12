# 05: `validate_findings`: deterministyczna walidacja Findings

Spec: `.scratch/review-agent/spec.md`

**What to build:** Zamiana przepuszczalnika `validate_findings` na prawdziwą, czystą funkcję bez modelu, która odrzuca Findings wskazujące nieistniejące miejsca. Powód każdego odrzucenia trafia do ostrzeżeń, żeby dało się go zobaczyć.

**Blocked by:** 04 (Granica wykonania Agenta i prawdziwy `review_code`).

**Status:** ready-for-agent

- [ ] Funkcja odrzuca Finding, gdy plik nie należy do `change["code"]`, linia wykracza poza plik, `evidence` nie występuje we wskazanej linii, albo brakuje `spec_ref` przy `source` równym `spec`
- [ ] Finding bez `file` i `line` (uwaga ogólna) jest przepuszczany, jeśli ma `spec_ref`
- [ ] Dokładne duplikaty (ten sam plik, linia i źródło) są usuwane, zostaje jeden
- [ ] Powód odrzucenia trafia do ostrzeżeń w stanie
- [ ] Tabela przypadków na czystej funkcji: plik spoza zmiany, linia poza plikiem, cytat nieobecny, brak `spec_ref`, duplikat, uwaga ogólna
- [ ] Test na poziomie grafu: recenzent zwracający zmyślony plik daje Review bez tego Findingu i z ostrzeżeniem
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
