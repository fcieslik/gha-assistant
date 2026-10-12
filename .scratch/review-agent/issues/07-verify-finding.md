# 07: Prawdziwy `verify_finding` (Send per Finding)

Spec: `.scratch/review-agent/spec.md`

**What to build:** Sonnet sprawdza każdy Finding osobno, w kodzie, narzędziami tylko do odczytu, i zwraca werdykt `confirmed`, `refuted` lub `inconclusive` z krótkim uzasadnieniem. Węzeł ma wspólną politykę `AGENT_RETRY`; po jej wyczerpaniu zwraca `inconclusive`, żeby prawdziwa uwaga nie ginęła przez awarię sieci.

**Blocked by:** 06 (Prawdziwy `review_intent`).

**Status:** ready-for-agent

- [ ] Jedno wywołanie na Finding, model `VERIFY_MODEL` (Sonnet) z serwisu Agenta, tylko narzędzia do odczytu (domyślne serwisu)
- [ ] Werdykt trafia do stanu reducerem, powiązany z Findingiem po `id`
- [ ] Limit liczby weryfikacji (stała); Findings ponad limit idą do sędziego jako niezweryfikowane, wybór wg wagi
- [ ] `AGENT_RETRY` i timeout noda 2 min: błąd przejściowy potem sukces daje 2 wywołania, trwały 1
- [ ] Po wyczerpaniu prób werdykt `inconclusive` z ostrzeżeniem; Finding nie jest tracony
- [ ] Treść Findingu i uzasadnienie traktowane jako dane, nie instrukcje
- [ ] Testy na granicy z atrapą: M Findings daje M wykonań (do limitu), awaria jednego nie wpływa na pozostałe
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
