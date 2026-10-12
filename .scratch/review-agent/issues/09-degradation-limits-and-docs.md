# 09: Degradacja, limity i dokumentacja

Spec: `.scratch/review-agent/spec.md`

**What to build:** Domknięcie odporności całego przepływu: awaria dowolnego recenzenta po wyczerpaniu retry nie kasuje pracy pozostałych, a podsumowanie mówi, czego nie sprawdzono. Policzony budżet czasu przy retry i `max_concurrency` mieści się w limicie runnera. Dokumentacja projektu opisuje nowy układ grafu.

**Blocked by:** 08 (Prawdziwy `judge_findings`).

**Status:** ready-for-agent

- [x] Awaria `review_code` dla jednego pliku po retry zostawia wyniki pozostałych plików i ostrzeżenie; ostrzeżenia są widoczne w komentarzu (sekcja „Ostrzeżenia”, nie w `summary`, patrz niżej)
- [x] Awaria `review_intent` po retry daje Review z samym kodem i adnotacją w komentarzu
- [x] Błąd trwały (zły klucz API) nie jest ponawiany i kończy run czytelnym błędem, nie degradacją "pustego" review
- [x] Budżet czasu: obliczenie z ticketu 04 (próby razy timeout razy rundy) uzupełnione o timeouty nodów `review_intent`, `verify_finding` i `judge_findings`; ścieżka bez awarii mieści się w `timeout-minutes`, a najgorszy przypadek jest opisany, nie obiecany
- [x] `max_concurrency` i limity wartości ustawione w jednym miejscu (`limits.py`), z opisem
- [x] `PROJECT_GOAL.md`: drzewo modułów bez `run_agent`, zamknięta decyzja nr 3 (rola SDK), opis przepływu z nowymi nodami
- [x] `CONTEXT.md`: terminy Candidate, Verdict, Judge oraz rozszerzony Finding
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą

## Decyzje przy implementacji

- **Ostrzeżenia w komentarzu, nie w `summary`.** `judge_findings` jest pomijany, gdy po walidacji nie ma Findings, a to właśnie wtedy awaria wszystkich recenzentów wyglądałaby jak czyste review („brak uwag”). `publish` renderuje `warnings` zawsze: sekcja „Ostrzeżenia”, max 10 pozycji i „i N więcej”.
- **Ostrzeżenia są danymi, nie markdownem.** Zawierają ścieżki i `id` Findingów (od modelu lub z PR), a komentarz jest publiczny. Każde ostrzeżenie to jedna linia (znaki sterujące i backticki zamienione, max 200 znaków) w code span, więc `@nick`, linki i HTML się nie renderują.
- **Wszystkie ostrzeżenia, także z `validate_findings`.** Odrzucone uwagi („plik spoza zmiany”, „duplikat”) też są w komentarzu. Jeśli okażą się szumem, wystarczy je odfiltrować w `publish`; nie ma osobnego pola w stanie.
- **Wspólny `compile_attempt` (`nodes/degradable.py`)** dla `review_code`, `review_intent` i `verify_finding`. Przejmuje cały wzorzec: graf zagnieżdżony z `retry_policy`, `timeout` i `error_handler`, który degraduje tylko błędy ponawiane przez `AGENT_RETRY`, a trwałe rzuca dalej. Każdy node dostarcza tylko swoją próbę i `degrade(state, exc)`. Zachowanie `review_intent` i `verify_finding` nie zmieniło się; pilnują go testy z 06 i 07.
- **`review_code` w grafie przez `make_review_code(retry, timeout)`.** Surowa funkcja `review_code` zostaje jedną próbą (testy wołają ją wprost). Testy podmieniają teraz `graph_module.make_review_code`, a nie `review_code`.
- **`limits.py`**: jedno miejsce na limity (tury i budżet agentów, timeouty prób, liczba prób, `MAX_CONCURRENCY`, `MAX_VERIFICATIONS`, `MAX_FINDINGS`, `MAX_DIFF_CHARS`) i na policzony budżet czasu. Moduły importują stałe po nazwie, więc testy nadal podmieniają je w module, który ich używa. `CLI_MAX_RETRIES` i polityki retry dla gita i GitHuba zostają przy swoich modułach (to szczegóły ich warstw, nie limity runa).
- **Budżet czasu.** Bez awarii run z 30 plikami to ok. 6 rund recenzji i 2 rundy weryfikacji, czyli ok. 7 min (zakładając minutę na plik; zmierzono tylko 6 s na mały diff). Najgorszy przypadek, gdy każda próba dochodzi do timeoutu, przekracza 15 min (już od jednego pliku z Intent files, bo `review_intent` to 10 min, a weryfikacja dokłada 8). Nie jest obiecany: runner zabija proces i nic nie jest publikowane. Sędzia nie dokłada czasu (kod).
- **Błąd trwały bez „czytelnego błędu”.** Run kończy się wyjątkiem SDK i bez komentarza (testy: `review_code`, `review_intent`, `verify_finding`). Czytelny komunikat wymaga punktu wejścia (`__main__.py`), którego jeszcze nie ma; dojdzie razem z nim.
- **Dokumentacja:** `PROJECT_GOAL.md` (drzewo modułów, zamknięta decyzja nr 3, sekcja „Przepływ grafu”, poprawione uprawnienia agenta i opis diffu), `CONTEXT.md` (Candidate, Verdict, Judge, rozszerzony Finding), `ARCHITECTURE.md`.
