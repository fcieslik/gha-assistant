# Architektura: przepływ grafu LangGraph

Stan na ticket 07 (`.scratch/review-agent/`). Źródło prawdy: `src/gha_assistant/graph.py`.

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
             │                             └────────────────►│ judge_findings │  STUB
             │                                               └────────┬───────┘  findings + summary
             │                                                        │
             └──────────────────┐         ┌───────────────────────────┘
                                ▼         ▼
                            ┌─────────┐
                            │ publish │  upsert komentarza ze statusem
                            └────┬────┘  retry: GitHub (3 próby)
                                 ▼
                                END
```

## Co jest prawdziwe, a co stubem

| Node | Stan | Ticket |
|---|---|---|
| `collect_input` | prawdziwy | 01–03 |
| `nothing_to_review`, `publish` | prawdziwe (upsert komentarza, `dry_run`) | 02 |
| `review_code` | prawdziwy: Haiku, `AGENT_RETRY`, timeout 120 s | 04 |
| `validate_findings` | prawdziwy, czysta funkcja | 05 |
| `review_intent` | prawdziwy: Haiku, jedno przejście (100 tur, $0.75), `AGENT_RETRY`, timeout 300 s, po wyczerpaniu ostrzeżenie (graf zagnieżdżony z `error_handler`) | 06 |
| `verify_finding` | prawdziwy: Sonnet, tylko Findings `high`, `AGENT_RETRY`, timeout 120 s, po wyczerpaniu `inconclusive` + ostrzeżenie (graf zagnieżdżony z `error_handler`) | 07 |
| `judge_findings` | stub (zostawia wszystko, `"stub summary"`) | 08 |

## Parametry grafu

| Element | Wartość |
|---|---|
| Współbieżność | `max_concurrency=5` |
| Reducery | `candidates`, `verdicts`, `warnings` (łączenie list) |
| Limit weryfikacji | tylko Findings `high`, max 10; `medium`, `low` i `high` ponad limit idą do sędziego niezweryfikowane |
| Pusta lista po walidacji | jawny routing do `publish`, bo pusty `Send` zakończyłby graf bez publikacji |
| Brak `high` po walidacji | jawny routing do `judge_findings` z tego samego powodu |
