# 07: Prawdziwy `verify_finding` (Send per Finding)

Spec: `.scratch/review-agent/spec.md`

**What to build:** Sonnet sprawdza każdy Finding o wadze `high` osobno, w kodzie, narzędziami tylko do odczytu, i zwraca werdykt `confirmed`, `refuted` lub `inconclusive` z krótkim uzasadnieniem. Węzeł ma wspólną politykę `AGENT_RETRY`; po jej wyczerpaniu zwraca `inconclusive`, żeby prawdziwa uwaga nie ginęła przez awarię sieci.

**Blocked by:** 06 (Prawdziwy `review_intent`).

**Status:** ready-for-agent

- [x] Jedno wywołanie na Finding, model `VERIFY_MODEL` (Sonnet) z serwisu Agenta, tylko narzędzia do odczytu (domyślne serwisu)
- [x] Werdykt trafia do stanu reducerem, powiązany z Findingiem po `id`
- [x] Weryfikowane są tylko Findings `high`, nie więcej niż stała `MAX_VERIFICATIONS` (10); bez żadnego `high` graf idzie wprost do `judge_findings`; pozostałe Findings idą do sędziego jako niezweryfikowane
- [x] `AGENT_RETRY` i timeout noda 2 min: błąd przejściowy potem sukces daje 2 wywołania, trwały 1
- [x] Po wyczerpaniu prób werdykt `inconclusive` z ostrzeżeniem; Finding nie jest tracony
- [x] Treść Findingu i uzasadnienie traktowane jako dane, nie instrukcje
- [x] Testy na granicy z atrapą: M Findings `high` daje M wykonań (do limitu), awaria jednego nie wpływa na pozostałe
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą

## Decyzje przy implementacji

- **Tylko `high`, limit 10 (zmiana wobec pierwotnego ticketu).** `route_after_validation` wybiera Findings z `severity == "high"` i bierze pierwsze `MAX_VERIFICATIONS` (10). Sortowanie po wadze znika, bo wszystkie mają tę samą wagę; przy remisie wygrywa kolejność z `validated`. Bez żadnego `high` routing idzie do `judge_findings`, bez Findings do `publish`. `medium`, `low` i `high` ponad limit zostają w `validated`, więc sędzia dostaje je bez werdyktu.
- **Degradacja tym samym wzorcem co `review_intent`: graf zagnieżdżony z `error_handler`.** Workerzy `Send` działają w jednym kroku, więc zwykły `error_handler` nie zatrzymałby błędu (LangGraph 1.2.14). Node `make_verify_finding(retry_policy, timeout)` woła jednowęzłowy graf z `attempt`. Po wyczerpaniu prób handler zwraca werdykt `inconclusive` i ostrzeżenie z nazwą typu wyjątku (nie jego treścią) oraz `id` Findingu. Błąd trwały (zły klucz API) jest rzucany dalej i kończy run. Wzorzec powtarza się teraz w dwóch miejscach; wspólny helper ma sens dopiero w tickecie 09, gdy dojdzie `review_code`.
- **Payload `Send` niesie `repo_path`**, bo agent czyta pliki z checkoutu (`cwd`). Prompt użytkownika to sam blok `<finding>` z JSON-em bez `id`: model nie widzi `id` i nie może go podać. `finding_id` werdyktu ustawia kod.
- **Prompt `prompts/verify_finding.md`** każe sprawdzić samo twierdzenie (wywołania, obsługa wyżej, Intent file ze `spec_ref`), nie tylko cytat; `inconclusive` jest dozwolone dopiero po sprawdzeniu.
- **Timeout 120 s (`NODE_TIMEOUT_SECONDS`)** jest wspólny z `review_code`, więc test timeoutu używa 0,5 s, nie 0,05 s.
- **Test z prawdziwym modelem** (`test_real_model_confirms_a_true_claim_and_refutes_a_false_one`, ok. 14 s): jedna prawdziwa i jedna fałszywa uwaga o dzieleniu przez zero; potwierdza kształt i kierunek werdyktu na dwóch próbkach, nie jakość na większym PR.
