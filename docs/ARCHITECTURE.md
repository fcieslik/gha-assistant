# Architektura: przepływ grafu LangGraph

Stan na ticket 09 (`.scratch/review-agent/`). Źródło prawdy: `src/gha_assistant/graph.py`, limity: `src/gha_assistant/limits.py`.

```
                              START
                                │
                                ▼
                        ┌───────────────┐
                        │ collect_input │  git diff → change {intent, code, ignored}
                        └───────┬───────┘  retry: git lock (3 próby)
                                │  Command(goto=...)
             ┌──────────────────┼──────────────────────────┐
             │ code == []       │ code != []               │ intent != []
             ▼                  ▼ Send × N plików          ▼ (tylko wtedy)
   ┌───────────────────┐   ┌─────────────┐  ┌─────────────┐   ┌───────────────┐
   │ nothing_to_review │   │ review_code │  │ review_code │   │ review_intent │
   │ komentarz: brak   │   │  plik 1     │  │  plik N     │   │  (1 na PR)    │
   │ kodu do sprawdz.  │   │  Haiku      │  │  Haiku      │   │  Haiku, 1 run │
   └─────────┬─────────┘   └──────┬──────┘  └──────┬──────┘   └───────┬───────┘
             │                    │  candidates (reducer: operator.add)
             ▼                    └────────┬───────┴──────────────────┘
            END                            │  osobne krawędzie, ten sam krok grafu
                                           ▼
                                 ┌───────────────────┐
                                 │ validate_findings │  czysta funkcja, bez modelu
                                 │ plik spoza zmiany,│  → validated + warnings
                                 │ linia, cytat,     │
                                 │ spec_ref, duplikat│
                                 └─────────┬─────────┘
                                           │ route_after_validation
             ┌─────────────────────────────┼──────────────────────────────┐
             │ validated == []             │ validated != [],             │ są Findings `high`
             │                             │ żaden nie jest `high`        ▼ Send × M (tylko
             │                             │                              │ `high`, max 10)
             │                             │               ┌──────────────┴─────────────┐
             │                             │               ▼                            ▼
             │                             │      ┌────────────────┐           ┌────────────────┐
             │                             │      │ verify_finding │    ...    │ verify_finding │
             │                             │      │ Sonnet, 1 run  │           │ Sonnet, 1 run  │
             │                             │      └───────┬────────┘           └───────┬────────┘
             │                             │              └──────── verdicts ──────────┘
             │                             │                           ▼
             │                             │                 ┌────────────────┐
             │                             └────────────────►│ judge_findings │  bez modelu
             │                                               └────────┬───────┘  refuted out, sort, limit
             │                                                        │
             └──────────────────┐         ┌───────────────────────────┘
                                ▼         ▼
                            ┌─────────┐
                            │ publish │  upsert komentarza ze statusem
                            └────┬────┘  retry: GitHub (3 próby)
                                 ▼
                                END
```

## Stan nodów (wszystkie prawdziwe, bez stubów)

| Node | Stan | Ticket |
|---|---|---|
| `collect_input` | prawdziwy | 01–03 |
| `nothing_to_review`, `publish` | prawdziwe (upsert komentarza z Findings i ostrzeżeniami, `dry_run`) | 02 |
| `review_code` | prawdziwy: Haiku, `AGENT_RETRY`, timeout 120 s, po wyczerpaniu ostrzeżenie z nazwą pliku (graf zagnieżdżony z `error_handler`) | 04, 09 |
| `validate_findings` | prawdziwy, czysta funkcja | 05 |
| `review_intent` | prawdziwy: Haiku, jedno przejście (100 tur, $0.75), `AGENT_RETRY`, timeout 300 s, po wyczerpaniu ostrzeżenie (graf zagnieżdżony z `error_handler`) | 06 |
| `verify_finding` | prawdziwy: Sonnet, tylko Findings `high`, `AGENT_RETRY`, timeout 120 s, po wyczerpaniu `inconclusive` + ostrzeżenie (graf zagnieżdżony z `error_handler`) | 07 |
| `judge_findings` | prawdziwy, czysta funkcja bez modelu: odrzuca `refuted`, sortuje wg wagi, tnie do 15, `summary` z liczb | 08 |

## Parametry grafu

| Element | Wartość |
|---|---|
| Limity i budżet czasu | wszystkie w `limits.py`: `MAX_CONCURRENCY=5`, timeouty prób (120 s, `review_intent` 300 s), 2 próby, `MAX_VERIFICATIONS=10`, `MAX_FINDINGS=15`, `MAX_DIFF_CHARS` |
| Czas | bez awarii ok. 7 min dla 30 plików; najgorszy przypadek (każda próba do timeoutu) przekracza 15 min i nie jest obiecany |
| Degradacja | wspólny `compile_attempt` (`nodes/degradable.py`): po wyczerpaniu retry ostrzeżenie (`review_code`, `review_intent`) albo Verdict `inconclusive` (`verify_finding`); błąd trwały przerywa run |
| Ostrzeżenia | `publish` pokazuje je w komentarzu (max 10, każde jako jedna linia w code span), bo `judge_findings` bywa pomijany |
| Reducery | `candidates`, `verdicts`, `warnings` (łączenie list) |
| Limit weryfikacji | tylko Findings `high`, max 10; `medium`, `low` i `high` ponad limit idą do `judge_findings` niezweryfikowane |
| Limit Review | `MAX_FINDINGS = 15`, zostają najpoważniejsze |
| Pusta lista po walidacji | jawny routing do `publish`, bo pusty `Send` zakończyłby graf bez publikacji |
| Brak `high` po walidacji | jawny routing do `judge_findings` z tego samego powodu |
