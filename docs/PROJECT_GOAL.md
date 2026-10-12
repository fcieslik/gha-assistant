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
- **Zmienione pliki:** kod Pythona liczy `git diff --name-status -M origin/<base>...HEAD` przed uruchomieniem agenta i dzieli pliki na Intent (cel PR), kod do recenzji i ignorowane. Agent dostaje listę plików, a diff pobiera sam Agent swoim narzędziem tylko do odczytu.
- **Uprawnienia agenta:** tylko odczyt (`Read`, `Grep`, `Glob`, `git diff`, `git log`, `git show`). Brak `git push`, `curl`, `gh`. Kod PR jest daną niezaufaną.
- **Publikacja review:** robi kod Pythona, nie agent. Używa Pull Request Reviews API, zdarzenie `COMMENT`, jeden review z podsumowaniem i komentarzami przy liniach.
- **Komentarz ze statusem:** każdy run kończy się jednym komentarzem w rozmowie PR (issue comment), żeby zielony run nie wyglądał jak run bez wyniku: "brak kodu do sprawdzenia" albo "sprawdzono N plików" z podsumowaniem, także gdy nie ma uwag. Komentarz jest rozpoznawany po ukrytym znaczniku i autorze będącym botem, a kolejny run edytuje go w miejscu zamiast dodawać nowy; treść zawiera SHA commita i czas, bo nadpisanie gubi poprzedni wynik. Token ze zmiennej `GITHUB_TOKEN`; brak tokenu lub celu bez `--dry-run` kończy run błędem. PR z forka (token tylko do odczytu) jest poza zakresem.
- **Format wyniku modelu:** structured output (`Finding`: plik, linia, waga, treść, sugestia).
- **Testowanie:** głównie lokalnie przez `--dry-run`. Kod ma trzy części: `collect_input`, `run_agent`, `publish`. GitHub Actions służy do końcowego testu w repozytorium testowym, przed tagiem `v1`.
- **Ochrona kosztów:** `timeout-minutes: 15` i `concurrency` z `cancel-in-progress: true`.

## Struktura repozytorium `gha-assistant`

```
gha-assistant/
├── action.yml
├── pyproject.toml
├── tests/fixtures/        # zapisane diffy z prawdziwych PR
└── src/gha_assistant/
    ├── state.py           # ReviewState (stan grafu)
    ├── graph.py           # graf LangGraph: tylko budowa i połączenia
    ├── change.py          # zbieranie Change: pliki PR i ich podział (bez grafu)
    ├── nodes/             # jeden plik na węzeł
    │   ├── collect_input.py
    │   ├── run_agent.py
    │   └── publish.py
    ├── github_io.py       # komentarz ze statusem w PR (upsert); później Review
    └── __main__.py        # punkt wejścia (CLI)
```

## Plik w repozytorium docelowym

`.github/workflows/gha-assistant.yml`:

```yaml
name: gha-assistant
on:
  pull_request:
    types: [opened, synchronize, reopened]
    # Filtr ścieżek w workflow: PR zmieniający tylko dokumentację nie uruchamia runnera.
    # Te same wzorce dokumentacji są w `IGNORED_PATTERNS` (change.py), które decydują,
    # co agent recenzuje w PR mieszanym. Trzymać oba miejsca w zgodzie ręcznie.
    paths-ignore:
      - '**.md'
      - 'docs/**'
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: gha-assistant-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: <owner>/gha-assistant@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Kanoniczne wzorce klasyfikacji (`change.py`)

Reguły działają w kolejności: usunięty plik → `ignored`; Intent → `intent`; wzorzec ignorowany lub binarny → `ignored`; reszta → `code`.

- **Intent:** `.scratch/**/*.md`, `docs/adr/**/*.md` (ADR wygrywa z `docs/**`).
- **Ignorowane:** `**/*.lock`, `**/package-lock.json`, `**/pnpm-lock.yaml`, `**/dist/**`, `**/*.min.*`, `**/*.md` (w tym `README.md`, `CONTEXT.md`, `docs/agents/*.md`), `docs/**`, oraz binaria po rozszerzeniu (obrazki, czcionki, archiwa, pliki wykonywalne).

Wzorce są stałymi w kodzie, bez konfiguracji per repozytorium.

**Agent nie jest wymaganym status checkiem.** Review publikujemy jako `COMMENT`. Gdy filtr `paths-ignore` pominie workflow, wymagany check zostaje w stanie „Pending" i blokuje merge, więc agenta nie ustawiamy jako wymaganego w branch protection.

## Otwarte decyzje

1. **Widoczność repozytorium `gha-assistant`.** Zalecenie: publiczne (kod nie zawiera sekretów, działa we wszystkich repozytoriach bez ustawień). Opcję prywatną trzeba sprawdzić w _Settings → Actions → General → Access_.
2. **Klucz LLM.**
   - Opcja A: sekret `ANTHROPIC_API_KEY` w każdym repozytorium (skrypt `gh secret set`).
   - Opcja B: AWS Bedrock + OIDC, bez kluczy w repozytoriach.
3. **Połączenie LangGraph z Agent SDK.** Do ustalenia: czy węzeł `run_agent` wywołuje Agent SDK jako jedną funkcję `run_agent(prompt) -> list[Finding]`, czy Agent SDK pełni inną rolę w grafie.
4. **Nazwa konta (`<owner>`) i repozytorium testowego.**
