# Jak użyć gha-assistant w swoim repozytorium

Ten dokument opisuje krok po kroku, jak podłączyć agenta do **innego** repozytorium (nazywam je „repozytorium docelowym”). Agent recenzuje każdy pull request w tym repozytorium i zostawia w nim jeden komentarz.

## Jak to działa (w skrócie)

```
repozytorium docelowe                     repozytorium gha-assistant
┌──────────────────────────┐              ┌──────────────────────────┐
│ .github/workflows/       │   uses:      │ action.yml               │
│   gha-assistant.yml  ────┼─────────────▶│ src/gha_assistant/...    │
│ sekret ANTHROPIC_API_KEY │              └──────────────────────────┘
└──────────────────────────┘
```

1. W repozytorium docelowym dodajesz jeden plik workflow i jeden sekret.
2. Gdy ktoś otworzy PR, GitHub uruchamia job na swoim runnerze.
3. Job pobiera kod PR (`actions/checkout`), a potem kod agenta z repozytorium `gha-assistant` (`uses:`).
4. Agent czyta zmiany, a wynik zapisuje w jednym komentarzu w PR. Kolejny push do PR **edytuje** ten sam komentarz.

## Odpowiedź na pytanie o sekret

Tak: sekret `ANTHROPIC_API_KEY` ma być w **repozytorium docelowym** (tam, gdzie działa workflow), a workflow przekazuje go do akcji przez `with:`.

| Pytanie | Odpowiedź |
|---|---|
| Gdzie dodać sekret? | W repozytorium docelowym: _Settings → Secrets and variables → Actions → New repository secret_. **Nie** w `gha-assistant`. |
| Dlaczego trzeba go przekazać? | Akcja jest uruchamiana w kontekście Twojego joba i nie widzi sekretów własnego repozytorium. Dostaje tylko to, co przekażesz w `with:`. |
| Czy dodawać `GITHUB_TOKEN`? | Nie. GitHub tworzy go sam dla każdego runa. Akcja bierze go domyślnie (`github.token`). Musisz tylko dać uprawnienie `pull-requests: write` w `permissions:`. |
| Mam wiele repozytoriów, czy muszę dodawać sekret w każdym? | Na koncie osobistym tak (to robi jedna komenda, patrz niżej). Na koncie organizacji możesz użyć sekretu organizacji i wskazać repozytoria, które go widzą. |
| Czy klucz wycieknie w logach? | GitHub maskuje wartości sekretów w logach joba. Agent ma tylko narzędzia do odczytu (`Read`, `Grep`, `Glob`), bez `Bash`. Komentarza w PR GitHub nie maskuje; czy prompt wstrzyknięty w kodzie PR mógłby wydobyć klucz ze środowiska, nie jest jeszcze sprawdzone (patrz „Ograniczenia v1”). |

## Krok 1: wypchnij `gha-assistant` na GitHub

Kod akcji musi być dostępny dla repozytoriów, które go używają. Adres to `fcieslik/gha-assistant`.

| Widoczność repozytorium `gha-assistant` | Co zrobić |
|---|---|
| **Publiczne** (zalecane) | Nic więcej. Kod nie zawiera sekretów. |
| Prywatne | W repozytorium `gha-assistant`: _Settings → Actions → General → Access_, wybierz „Accessible from repositories owned by the user”. |

```bash
git push origin main
```

## Krok 2: dodaj sekret w repozytorium docelowym

Przez przeglądarkę (_Settings → Secrets and variables → Actions_) albo komendą:

```bash
gh secret set ANTHROPIC_API_KEY --repo fcieslik/NAZWA-REPOZYTORIUM
```

Komenda poprosi o wklejenie klucza i nic nie zostawi w historii terminala.

## Krok 3: dodaj workflow w repozytorium docelowym

Utwórz plik `.github/workflows/gha-assistant.yml`:

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
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: fcieslik/gha-assistant@main
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Co robi każda część:

| Część | Po co |
|---|---|
| `on: pull_request` | Uruchamia agenta przy otwarciu PR, nowym pushu i ponownym otwarciu. Inne zdarzenia (np. `push`) kończą się błędem. |
| `permissions` | `contents: read` pozwala pobrać kod, `pull-requests: write` pozwala zapisać komentarz. Bez drugiego komentarz się nie pojawi (błąd 403). |
| `concurrency` | Nowy push anuluje trwający run tego samego PR, więc nie płacisz za dwa równoległe. |
| `timeout-minutes: 15` | Ochrona kosztów: zawieszony run zostanie zabity. |
| `actions/checkout` z `fetch-depth: 0` | Agent liczy diff względem gałęzi bazowej, więc potrzebuje pełnej historii. **Bez tego nie zadziała.** |
| `uses: fcieslik/gha-assistant@main` | Kod agenta. Patrz „Wersja akcji” niżej. |
| `anthropic-api-key` | Tu przekazujesz sekret do akcji. |

### Opcjonalnie: nie uruchamiaj agenta dla samej dokumentacji

Dodaj w `on.pull_request` filtr, a PR zmieniający tylko dokumenty nie zużyje runnera:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

Te same wzorce agent stosuje sam w `IGNORED_PATTERNS` (`src/gha_assistant/change.py`). Bez filtra PR z samą dokumentacją i tak kończy się komentarzem „brak kodu do sprawdzenia”.

## Krok 4: otwórz PR i sprawdź wynik

1. Utwórz gałąź, zmień jakiś plik z kodem i otwórz PR.
2. W zakładce _Checks_ (albo _Actions_) zobaczysz run `gha-assistant`. Trwa od kilkudziesięciu sekund do kilku minut.
3. W rozmowie PR pojawi się komentarz **gha-assistant**.

Jak go czytać:

| Fragment komentarza | Znaczenie |
|---|---|
| `sprawdzono plików: 3, uwagi: 2` | Agent przejrzał 3 pliki z kodem i ma 2 uwagi. |
| `brak kodu do sprawdzenia` | W PR są tylko dokumenty, pliki blokad (`*.lock`), binaria albo pliki Intent. |
| **Uwagi:** | Lista: waga (`high`, `medium`, `low`), plik i linia, treść, sugestia. Najpoważniejsze są na górze, maksymalnie 15. |
| **Ostrzeżenia:** | Któryś etap się nie udał mimo ponowień (np. timeout), więc wynik może być niepełny. To nie jest „brak uwag”. |
| `commit abc1234, 2026-10-12 14:30 UTC` | Którego commita dotyczy wynik. Komentarz jest nadpisywany, więc to jedyny ślad. |

Uwagi o wadze `high` agent sprawdza drugi raz osobnym przebiegiem. Uwagi, które ten przebieg obalił, nie trafiają do komentarza, a liczba odrzuconych jest w podsumowaniu.

## Krok 5 (po pierwszym udanym runie): przypnij wersję

`@main` oznacza „zawsze najnowszy kod z gałęzi `main`”. Każdy Twój push do `gha-assistant` zmienia więc działanie wszystkich repozytoriów naraz. Gdy test z kroku 4 przejdzie, utwórz tag i używaj `@v1`:

```bash
git tag v1.0.0
git tag -f v1            # ruchomy tag: wskazuje najnowsze v1.x
git push origin v1.0.0
git push origin v1 --force
```

W workflow zmień `fcieslik/gha-assistant@main` na `fcieslik/gha-assistant@v1`. Poprawki w obrębie `v1` publikujesz, przesuwając ruchomy tag `v1`.

## Krok 6 (opcjonalnie): własna nazwa i awatar komentarzy

Domyślnie komentarz pisze wbudowany bot `github-actions[bot]`. Jego nazwy ani awatara nie zmienisz. Jeśli chcesz, żeby komentarze miały Twoją nazwę i logo, utwórz **GitHub App** i przekaż akcji jego token zamiast `GITHUB_TOKEN`. Kod agenta nie wymaga zmian: wejście `github-token` już istnieje.

| # | Krok | Gdzie |
|---|---|---|
| 1 | Utwórz GitHub App: nazwa, logo (awatar), opis. Wyłącz webhook, bo nie jest potrzebny. Nazwa musi być unikalna w całym GitHubie. | _Settings → Developer settings → GitHub Apps → New GitHub App_ |
| 2 | Uprawnienia repozytorium: **Pull requests: Read and write**. Resztę zostaw domyślną. | Ustawienia aplikacji |
| 3 | Wygeneruj klucz prywatny (plik `.pem`) i zapisz **App ID**. | Ustawienia aplikacji |
| 4 | Zainstaluj aplikację na repozytoriach, które mają jej używać (np. „Only select repositories”). | _Install App_ w ustawieniach aplikacji |
| 5 | W repozytorium docelowym dodaj sekret `GHA_ASSISTANT_PRIVATE_KEY` (zawartość pliku `.pem`) i zmienną `GHA_ASSISTANT_APP_ID`. | _Settings → Secrets and variables → Actions_ (sekret w _Secrets_, App ID w _Variables_) |
| 6 | W workflow wygeneruj token aplikacji i przekaż go do akcji (niżej). | `.github/workflows/gha-assistant.yml` |

Krok `uses: fcieslik/gha-assistant` z kroku 3 zastąp tymi dwoma krokami:

```yaml
      - uses: actions/create-github-app-token@v3.2.0
        id: app
        with:
          app-id: ${{ vars.GHA_ASSISTANT_APP_ID }}
          private-key: ${{ secrets.GHA_ASSISTANT_PRIVATE_KEY }}
      - uses: fcieslik/gha-assistant@v1
        with:
          github-token: ${{ steps.app.outputs.token }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Efekt: komentarz ma autora `nazwa-aplikacji[bot]` i awatar aplikacji. Token aplikacji wygasa po godzinie i obejmuje tylko to repozytorium, w którym działa run.

| Uwaga | Szczegóły |
|---|---|
| Nie używaj osobnego konta użytkownika z tokenem PAT | Agent rozpoznaje własny komentarz po autorze typu `Bot`. Konto użytkownika ma typ `User`, więc każdy run dodawałby nowy komentarz zamiast edytować poprzedni. Aplikacja ma typ `Bot` i działa bez zmian. |
| Co się nie zmienia | Zakładka _Checks_ i nazwa joba nadal pochodzą z GitHub Actions i z `name:` w workflow. |
| Sekrety w każdym repozytorium | Klucz prywatny i App ID dodajesz w każdym repozytorium docelowym, tak jak `ANTHROPIC_API_KEY`. Na koncie organizacji możesz użyć sekretu i zmiennej organizacji. |
| Nagłówek w treści komentarza | Nadal `**gha-assistant:**`. Zmienia się go w `render_status_comment` w `src/gha_assistant/github_io.py`. |
| Po zmianie tokenu stary komentarz | Komentarz utworzony wcześniej przez `github-actions[bot]` nie jest edytowany przez aplikację, bo ma innego autora. Pojawi się nowy, a stary zostanie w historii PR (dotyczy tylko PR otwartych przed zmianą). |

## Uruchomienie lokalne (bez GitHuba)

Dobry sposób, żeby zobaczyć wynik bez PR i bez zostawiania komentarza. Komentarz zostanie tylko wypisany w terminalu.

```bash
cd /ścieżka/do/innego/repo        # repozytorium z gałęzią PR, bazą jest origin/main
uv run --env-file /Users/fc47/workspace/projects/gha-assistant/.env \
  --project /Users/fc47/workspace/projects/gha-assistant \
  python -m gha_assistant --dry-run --base-ref origin/main
```

Plik `.env` musi zawierać `ANTHROPIC_API_KEY`. Ta komenda **wywołuje model**, więc kosztuje.

## Gdy coś nie działa

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| Job czerwony: `ANTHROPIC_API_KEY is not set` | Sekretu nie ma w repozytorium docelowym, nazwa się nie zgadza, albo brakuje linii `anthropic-api-key:` w workflow. | Sprawdź nazwę sekretu i krok 2. PR od Dependabota ma osobne sekrety (_Settings → Secrets → Dependabot_). |
| Job czerwony: `Invalid API key` | Klucz jest błędny lub unieważniony. | Wygeneruj nowy klucz i ustaw sekret jeszcze raz. |
| Job czerwony: `HTTP Error 403` przy komentarzu | Brak `pull-requests: write` w `permissions:` albo organizacja ogranicza uprawnienia tokenu. | Dodaj blok `permissions:` z kroku 3. W organizacji sprawdź _Settings → Actions → General → Workflow permissions_. |
| Job czerwony na kroku `create-github-app-token` (krok 6) | Aplikacja nie jest zainstalowana na tym repozytorium, albo `GHA_ASSISTANT_APP_ID` lub klucz prywatny są błędne. | Sprawdź instalację aplikacji (krok 6.4) oraz nazwy sekretu i zmiennej. |
| Job czerwony: `HTTP Error 403` przy komentarzu, a używasz aplikacji | Aplikacja nie ma uprawnienia **Pull requests: Read and write**. | Dodaj uprawnienie w ustawieniach aplikacji i zatwierdź je w instalacji. |
| Job czerwony: `the event has no pull_request` | Workflow działa na innym zdarzeniu niż `pull_request`. | Popraw `on:` jak w kroku 3. |
| Job czerwony: `CalledProcessError: Command '['git', ... 'diff' ...` z kodem 128 | Brak `fetch-depth: 0` w `actions/checkout`, więc `origin/<baza>` nie istnieje. | Dodaj `fetch-depth: 0`. |
| Job zielony, w logu `PR from a fork ... skipped` | PR z forka nie ma sekretów i ma token tylko do odczytu. | Tak ma być, to jest poza zakresem v1. |
| Job nie pojawia się w ogóle | Filtr `paths-ignore` pominął PR albo plik nie leży w `.github/workflows/`. | Sprawdź filtr i ścieżkę pliku. |
| Job nie może pobrać akcji (`repository not found`) | `gha-assistant` jest prywatne i nie ma dostępu z innych repozytoriów. | Patrz krok 1. |
| Run przerwany po 15 minutach, brak komentarza | Bardzo duży PR i wiele timeoutów. Przy takim przebiegu zabity proces nic nie publikuje. | Rozbij PR na mniejsze albo wypchnij kolejny commit (nowy run). |

Pierwszą linią błędu jest zawsze `::error::gha-assistant: ...`. Szczegóły i ślad stosu są poniżej niej w logu joba.

## Ograniczenia v1

| Ograniczenie | Szczegóły |
|---|---|
| Brak komentarzy przy liniach | Wszystko jest w jednym komentarzu w rozmowie PR. |
| PR z forków | Pomijane bez błędu (brak sekretów i token tylko do odczytu). |
| Nie ustawiaj agenta jako wymaganego checka | Przy `paths-ignore` wymagany check zostaje w stanie „Pending” i blokuje merge. Agent publikuje komentarz, nie blokuje. |
| Koszt | Każde wywołanie modelu ma twardy limit (0,50 USD, a dla analizy Intent 0,75 USD), ale suma za run zależy od liczby plików i nie jest ograniczona jedną liczbą. Typowy koszt nie jest jeszcze zmierzony: sprawdź go w konsoli Anthropic po pierwszych runach. |
| Czas | Typowy run to kilka minut, 30 plików to około 7 minut. Szczegóły i najgorszy przypadek: `src/gha_assistant/limits.py`. |
| Sekret w środowisku | Kod PR jest daną niezaufaną. Agent nie ma `Bash`, ale nie sprawdziliśmy jeszcze, czy wstrzyknięty w PR tekst nie skłoni go do odczytu środowiska (np. `/proc/self/environ`) i wpisania klucza do uwagi. Do czasu sprawdzenia używaj klucza z niskim limitem wydatków i tylko w repozytoriach, w których ufasz autorom PR. |
| Prywatność | Diff i pliki z PR trafiają do API Anthropic. Nie używaj agenta w repozytoriach, których kodu nie wolno tam wysyłać. |
