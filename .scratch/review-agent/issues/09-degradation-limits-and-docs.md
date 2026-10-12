# 09: Degradacja, limity i dokumentacja

Spec: `.scratch/review-agent/spec.md`

**What to build:** Domknięcie odporności całego przepływu: awaria dowolnego recenzenta po wyczerpaniu retry nie kasuje pracy pozostałych, a podsumowanie mówi, czego nie sprawdzono. Policzony budżet czasu przy retry i `max_concurrency` mieści się w limicie runnera. Dokumentacja projektu opisuje nowy układ grafu.

**Blocked by:** 08 (Prawdziwy `judge_findings`).

**Status:** ready-for-agent

- [ ] Awaria `review_code` dla jednego pliku po retry zostawia wyniki pozostałych plików i ostrzeżenie; ostrzeżenia są widoczne w `summary`
- [ ] Awaria `review_intent` po retry daje Review z samym kodem i adnotacją w `summary`
- [ ] Błąd trwały (zły klucz API) nie jest ponawiany i kończy run czytelnym błędem, nie degradacją "pustego" review
- [ ] Budżet czasu: obliczenie z ticketu 04 (próby razy timeout razy rundy) uzupełnione o timeouty nodów `review_intent`, `verify_finding` i `judge_findings`; ścieżka bez awarii mieści się w `timeout-minutes`, a najgorszy przypadek jest opisany, nie obiecany
- [ ] `max_concurrency` i limity wartości ustawione w jednym miejscu, z opisem
- [ ] `PROJECT_GOAL.md`: drzewo modułów bez `run_agent`, zamknięta decyzja nr 3 (rola SDK), opis przepływu z nowymi nodami
- [ ] `CONTEXT.md`: terminy Candidate, Verdict, Judge oraz rozszerzony Finding
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
