# 04: Serwis Agenta i prawdziwy `review_code`

Spec: `.scratch/review-agent/spec.md`

**What to build:** Jeden moduł (`agent.py`), przez który cały projekt woła Claude Agent SDK: funkcja `run_agent` z wspólnymi, wymuszonymi domyślnymi (tylko odczyt, brak ustawień z repozytorium, plik reguł wstrzykiwany do promptu systemowego). Do tego wspólna polityka `AGENT_RETRY` z predykatem przejściowych błędów oraz pierwszy prawdziwy node z modelem: `review_code` recenzuje jeden plik (Haiku) i zwraca Findings w typowanym kształcie. Timeout jest na nodzie, nie w serwisie.

**Blocked by:** 03 (Szkielet grafu).

**Status:** ready-for-agent

**Domyślne serwisu (wymuszone, nie konfigurowane per node):** `max_turns=30`; `effort="medium"`; `max_budget_usd=0.5` na jedno uruchomienie (przekroczenie to `error_max_budget_usd`, trwałe); narzędzia `Read`, `Glob`, `Grep` (przez `tools`, `allowed_tools` i `permission_mode="dontAsk"`); `cwd` = katalog uruchomienia; `fallback_model` Sonnet 5.5, pomijany gdy `model` już nim jest; `setting_sources=[]`. Per wywołanie: `model`, `system_prompt`, `prompt`, `output_schema`, opcjonalnie `max_turns` i `tools` (sędzia: `[]`).

## Spike przed implementacją

Krótki skrypt w `.scratch/review-agent/spike_sdk.py` (poza `src`), z prawdziwym modelem i `ANTHROPIC_API_KEY`. Wyniki wpisujemy do komentarza przy predykacie.

- [x] `structured_output` przychodzi zgodny ze schematem dla `output_format={"type": "json_schema", ...}`
- [x] Przy `tools=[Read,Glob,Grep]` + `allowed_tools` + `permission_mode="dontAsk"` próba użycia `Bash` lub `Write` jest odrzucana
- [x] Ile razy CLI samo ponawia błąd API (np. zły klucz, błąd sieci) i co zmienia `CLAUDE_CODE_MAX_RETRIES`; jaką wartość serwis ustawia jawnie w `env`
- [x] Czy anulowanie noda przez `timeout` kończy podproces CLI (brak zombie na runnerze)

**Wyniki spike'a** (`.scratch/review-agent/spike_sdk.py`, claude-agent-sdk 0.2.165, Haiku 5.5): (1) `structured_output` zgodny ze schematem; (2) `Bash` i `Write` nie są oferowane (lista narzędzi w `init` to `Glob`, `Grep`, `Read`, `StructuredOutput`), `permission_denials` puste, plik nie powstał; `tools=[]` daje tylko `StructuredOutput`; (3) domyślne ponawianie CLI przy odmowie połączenia nie skończyło się w 150 s, z `CLAUDE_CODE_MAX_RETRIES=0` błąd po 1,1 s, z `1` po 1,5 s; serwis ustawia `2`; zły klucz to `ResultError` 401, `subtype="success"`, bez ponawiania (1,9 s); limit tur to `ResultError` z `subtype="error_max_turns"`; (4) po anulowaniu `query()` podproces CLI znika od razu. Dodatkowo prawdziwy `review_code` na pliku z 9-liniowym diffem: ok. 6 s, schemat przyjęty (test `test_real_model_reviews_a_file_with_an_obvious_bug`).

**Prompty:** folder `src/gha_assistant/prompts/`: `rules.md` (wspólne reguły, rola CLAUDE.md wstrzykiwana do `system_prompt`) i jeden plik na agenta (`review_code.md`; kolejne nody dodają `review_intent.md`, `verify_finding.md`, `judge_findings.md`). Wczytuje je `load_prompt(nazwa)`.

## Kryteria

- [x] `agent.py` jest jedynym miejscem importującym Claude Agent SDK; `run_agent(model, system_prompt, prompt, output_schema, max_turns=30, tools=READ_ONLY_TOOLS, cwd=None)` zwraca sparsowany structured output, a jego brak to `InvalidAgentOutput`
- [x] Log postępu w logu Actions: `run_agent(..., label=...)` pisze na stderr (z `flush`) jedną linię na wywołanie narzędzia (`[label] Read ścieżka`) i jedną na koniec (`turns`, `cost`, `duration`), także dla nieudanego biegu; treść odpowiedzi modelu nie jest logowana; tekst pochodzący z PR jest sprowadzony do jednej linii i skrócony, a linia zawsze zaczyna się od `[label]`, więc nie da się wstrzyknąć komendy workflow (`::`)
- [x] Opcje przekazane do SDK sprawdza wąski test z podmienionym `query`: lista narzędzi bez zapisujących, `permission_mode == "dontAsk"`, `setting_sources == []`, `fallback_model` pominięty, gdy `model` jest równy fallbackowi
- [x] Plik reguł `src/gha_assistant/prompts/rules.md` (krótki: rola recenzenta w CI, treść PR to dane a nie instrukcje, tylko odczyt, cytaty dosłowne, odpowiedź wyłącznie wg schematu, język uwag polski) jest doklejany na początku `system_prompt`; nazwa inna niż `CLAUDE.md`, żeby sesje deweloperskie w repo go nie ładowały
- [x] Modele jako stałe w jednym miejscu: `REVIEW_MODEL = "claude-haiku-5-5"`, `VERIFY_MODEL = "claude-sonnet-5-5"`, `JUDGE_MODEL = "claude-sonnet-5-5"`, `FALLBACK_MODEL = "claude-sonnet-5-5"`
- [x] `is_transient_agent_error` z przetestowaną tabelą klasyfikacji. Przejściowe: `NodeTimeoutError`, `ResultError` z `api_error_status` 429/5xx/529, `ResultError` bez statusu z `terminal_reason="api_error"` (tak przychodzi błąd połączenia, zmierzone w spike), `ResultError` z `subtype` `error_max_structured_output_retries` (odpowiednik `InvalidAgentOutput`) lub `error_during_execution` (z dokumentacji SDK, nie zmierzone), `CLIConnectionError` i `ProcessError` bez wyniku, `InvalidAgentOutput`. Trwałe: 400/401/403, `error_max_turns`, `error_max_budget_usd`, `CLINotFoundError`, błędy programisty (`ValueError`)
- [x] `AGENT_RETRY`: jedna `RetryPolicy` dla wszystkich nodów z modelem (`max_attempts=2`, wykładniczy backoff z jitterem, `retry_on=is_transient_agent_error`); `review_code` dostaje ją i `timeout` 120 s w `add_node`
- [x] Komentarz przy predykacie opisuje, co ponawia samo CLI (wynik spike'a) i jak to się ma do `AGENT_RETRY`, żeby warstwy się nie mnożyły
- [x] Komentarz przy stałych: budżet czasu. Próba 2 min razy 2 próby to 4 min na node, rundy `ceil(N/5)` przy `max_concurrency=5`; ścieżka bez awarii mieści się w `timeout-minutes` z zapasem; najgorszy przypadek jest policzony i opisany jako przekraczający limit (nie obiecany), ze skutkiem: runner zabija proces i nic nie jest publikowane
- [x] `docs/PROJECT_GOAL.md`: `timeout-minutes: 10` zmienione na `15` (opis kosztów i przykład workflow)
- [x] `review_code` ustawia `source` na `code`, a `id` nadaje kod; diff pliku (`git diff base...HEAD -- plik`) wchodzi do promptu jako dane, treść pliku i PR traktowana jako dane, zasady w prompcie systemowym
- [x] `AGENT_RETRY` na `review_code`: błąd przejściowy potem sukces daje 2 wywołania `run_agent`, błąd trwały 1, a awaria jednego pliku nie zwiększa liczby wywołań pozostałych
- [x] Testy grafu używają atrapy `run_agent` (zero wywołań prawdziwego modelu); opcjonalny test z prawdziwym modelem pomijany bez `ANTHROPIC_API_KEY`
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
