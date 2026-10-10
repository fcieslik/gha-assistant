# Code-review agent: główne założenia projektu

## Ustalone (mój wybór)

- **Wariant A: GitHub Actions.** Agent działa na runnerze GitHub. Nie buduję własnego serwera ani webhooków.
- **Jeden agent dla wszystkich moich repozytoriów.** W repozytorium docelowym dodaję tylko jeden plik workflow w `.github/workflows/`.
- **Konto GitHub Free** (nie Enterprise). To ogranicza widoczność akcji i sposób przechowywania klucza (patrz „Otwarte decyzje").
- **Claude Agent SDK** jest warstwą agenta pod spodem.
- **LangGraph** i Python są celem nauki.

## Przyjęte z rozmowy (propozycje bez sprzeciwu)

- **Trigger:** zdarzenie `pull_request` (`opened`, `synchronize`, `reopened`).
- **Współdzielenie kodu:** osobne repozytorium `gha-assistant` z composite action (`action.yml`). Repozytorium docelowe wywołuje je przez `uses: <owner>/gha-assistant@v1`.
- **Wersjonowanie:** tagi `v1.0.0` i ruchomy tag `v1`.
- **Checkout:** `actions/checkout` z `fetch-depth: 0`, żeby `git diff` do gałęzi bazowej działał.
- **Zmienione pliki:** kod Pythona liczy `git diff --name-only origin/<base>...HEAD` przed uruchomieniem agenta. Agent dostaje listę plików i diff w prompcie.
- **Uprawnienia agenta:** tylko odczyt (`Read`, `Grep`, `Glob`, `git diff`, `git log`, `git show`). Brak `git push`, `curl`, `gh`. Kod PR jest daną niezaufaną.
- **Publikacja review:** robi kod Pythona, nie agent. Używa Pull Request Reviews API, zdarzenie `COMMENT`, jeden review z podsumowaniem i komentarzami przy liniach.
- **Format wyniku modelu:** structured output (`Finding`: plik, linia, waga, treść, sugestia).
- **Testowanie:** głównie lokalnie przez `--dry-run`. Kod ma trzy części: `collect_input`, `run_agent`, `publish`. GitHub Actions służy do końcowego testu w repozytorium testowym, przed tagiem `v1`.
- **Ochrona kosztów:** `timeout-minutes: 10` i `concurrency` z `cancel-in-progress: true`.

## Struktura repozytorium `gha-assistant`

```
gha-assistant/
├── action.yml
├── pyproject.toml
├── tests/fixtures/        # zapisane diffy z prawdziwych PR
└── src/gha_assistant/
    ├── state.py           # ReviewState (stan grafu)
    ├── graph.py           # graf LangGraph: tylko budowa i połączenia
    ├── nodes/             # jeden plik na węzeł
    │   ├── collect_input.py
    │   ├── run_agent.py
    │   └── publish.py
    ├── github_io.py       # diff i publikacja review
    └── __main__.py        # punkt wejścia (CLI)
```

## Plik w repozytorium docelowym

`.github/workflows/gha-assistant.yml`:

```yaml
name: gha-assistant
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: gha-assistant-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: <owner>/gha-assistant@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Otwarte decyzje

1. **Widoczność repozytorium `gha-assistant`.** Zalecenie: publiczne (kod nie zawiera sekretów, działa we wszystkich repozytoriach bez ustawień). Opcję prywatną trzeba sprawdzić w _Settings → Actions → General → Access_.
2. **Klucz LLM.**
   - Opcja A: sekret `ANTHROPIC_API_KEY` w każdym repozytorium (skrypt `gh secret set`).
   - Opcja B: AWS Bedrock + OIDC, bez kluczy w repozytoriach.
3. **Połączenie LangGraph z Agent SDK.** Do ustalenia: czy węzeł `run_agent` wywołuje Agent SDK jako jedną funkcję `run_agent(prompt) -> list[Finding]`, czy Agent SDK pełni inną rolę w grafie.
4. **Nazwa konta (`<owner>`) i repozytorium testowego.**
