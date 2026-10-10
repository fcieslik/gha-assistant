# Zbieranie Change i kierowanie review

Status: ready-for-agent

## Problem Statement

Agent ma robić review pull requestu, ale graf nie wie jeszcze nic o tym, czym ten PR jest. Nie ma listy plików, które faktycznie się zmieniły, i nie odróżnia plików opisujących cel PR (Spec, Ticket, ADR) od zwykłego kodu ani od plików, których recenzować nie ma sensu (lockfile, obrazki, dokumentacja). Pracuję tak, że do PR dołączam pliki `.md` ze specyfikacją, ticketami i ADR-ami, więc cel PR jest w nim samym, ale agent musi umieć go z diffu wyciągnąć. Dodatkowo agent nie powinien się uruchamiać (ani nic komentować) na PR-ach, które zmieniają wyłącznie `.md` i dokumentację.

## Solution

Pierwszy węzeł grafu ustala **Change**: zbiór plików zmienionych w PR względem bazy, podzielony według roli pliku na trzy grupy: **intent** (Intent files, czyli cel PR), **code** (do recenzji) i **ignored** (nie recenzujemy). Robi to osobny moduł, który nie zna grafu ani stanu i jest wołany tylko z tego węzła. Wynik trafia do stanu i kolejne węzły budują na nim swoją pracę. Gdy w Change nie ma niczego do recenzji, graf kończy się od razu, bez wołania Agenta i bez publikowania czegokolwiek w PR. Workflow w repozytorium docelowym dodatkowo w ogóle nie startuje dla PR-ów zmieniających wyłącznie dokumentację.

## User Stories

1. Jako autor PR, chcę, żeby agent wiedział, które pliki naprawdę zmieniłem względem bazy, aby review dotyczyło mojej zmiany, a nie całego repozytorium.
2. Jako autor PR, chcę, żeby lista zmienionych plików była liczona względem miejsca, w którym moja gałąź rozeszła się z bazą, aby późniejsze zmiany na bazie nie trafiały do mojego review.
3. Jako autor PR, chcę, żeby agent traktował `spec.md` z `.scratch/` jako cel PR, aby ocenił kod pod kątem tego, co miał zrobić.
4. Jako autor PR, chcę, żeby agent traktował pliki ticketów z `.scratch/<feature>/issues/` jako cel PR, aby wiedział, które jednostki pracy ten PR realizuje.
5. Jako autor PR, chcę, żeby agent traktował ADR-y z `docs/adr/` dołączone do PR jako cel PR, aby znał decyzje, które właśnie podjąłem.
6. Jako autor PR, chcę, żeby tytuł i opis PR były częścią Intent o najniższym priorytecie, aby PR bez żadnych plików Spec/Ticket/ADR miał jakikolwiek cel.
7. Jako autor PR, chcę, żeby PR bez żadnego Intent file nadal był recenzowany, aby brak dokumentów nie blokował review.
8. Jako autor PR, chcę, żeby zmieniony `README.md`, `CONTEXT.md` lub `docs/agents/*.md` w PR z kodem nie był recenzowany jako kod, aby review nie zaśmiecały uwagi o dokumentacji.
9. Jako autor PR, chcę, żeby zmiana samego `uv.lock` lub innego lockfile'a nie była recenzowana, aby agent nie komentował plików generowanych.
10. Jako autor PR, chcę, żeby obrazki i inne binaria były pomijane, aby agent nie próbował ich czytać jak tekstu.
11. Jako autor PR, chcę, żeby pliki usunięte w PR nie były przekazywane do recenzji, aby agent nie szukał plików, których już nie ma.
12. Jako autor PR, chcę, żeby plik przeniesiony lub przemianowany liczył się pod nową ścieżką, aby review dotyczyło pliku, który istnieje.
13. Jako autor PR, chcę, żeby plik z `docs/adr/` był Intent file mimo że leży w `docs/`, aby ADR-y nie znikały wśród ignorowanej dokumentacji.
14. Jako autor PR, chcę, żeby pliki intencji nie były recenzowane jako kod, aby agent nie komentował własnego celu.
15. Jako autor PR, chcę, żeby PR zawierający tylko pliki intencji lub tylko pliki ignorowane kończył się bez żadnego komentarza, aby nie dostawać "nie ma czego recenzować".
16. Jako autor repozytorium, chcę, żeby workflow nie startował dla PR-ów zmieniających wyłącznie `.md` i `docs/`, aby nie zużywać minut runnera i nie zaśmiecać zakładki Actions.
17. Jako autor repozytorium, chcę, żeby jeden plik zmieniony poza `.md` i `docs/` wystarczył do uruchomienia workflow, aby PR mieszany był recenzowany.
18. Jako autor repozytorium, chcę, żeby ten sam plik workflow działał we wszystkich moich repozytoriach bez znajomości ich układu, aby nie utrzymywać konfiguracji per repozytorium.
19. Jako autor repozytorium, chcę, żeby agent nie był wymaganym status checkiem, aby pominięty przez filtr ścieżek workflow nie blokował merge'a.
20. Jako deweloper agenta, chcę, żeby moduł zbierający Change nie znał grafu ani stanu, aby dało się go testować i zmieniać niezależnie od LangGraph.
21. Jako deweloper agenta, chcę, żeby wynik zbierania Change był typowanym obiektem z rolami plików, a nie słownikiem z kluczami według formatu, aby kolejny węzeł nie musiał sam filtrować.
22. Jako deweloper agenta, chcę, żeby węzeł `collect_input` nie czytał zmiennych środowiskowych, aby test, `--dry-run` i Actions podawały te same dane wejściowe.
23. Jako deweloper agenta, chcę, żeby baza porównania, ścieżka repo, tytuł i opis PR były polami wejściowymi stanu, aby `invoke` mogło je dostać z dowolnego źródła.
24. Jako deweloper agenta, chcę, żeby klasyfikacja plików miała jedno źródło prawdy w kodzie, aby zmiana reguł była zmianą w jednym miejscu.
25. Jako deweloper agenta, chcę, żeby kolejność reguł klasyfikacji była jawna i testowana, aby plik pasujący do kilku wzorców zawsze trafiał do tej samej grupy.
26. Jako deweloper agenta, chcę, żeby decyzja o zakończeniu grafu przy pustym `code` była krawędzią warunkową, aby routing był widoczny w grafie, a nie ukryty w węźle.
27. Jako deweloper agenta, chcę, żeby przypadek "PR bez Intent" był jawnie przekazywany do promptu przyszłego Agenta, aby model nie zgadywał celu.
28. Jako deweloper agenta, chcę, żeby test sprawdzał semantykę diffu na prawdziwym repozytorium git z merge commitem i bazą, która poszła do przodu, aby założenie o `refs/pull/N/merge` było zweryfikowane, a nie tylko opisane.
29. Jako deweloper agenta, chcę, żeby Agent dostawał listę plików do recenzji i sam pobierał diff przez swoje narzędzie tylko do odczytu, aby stan i prompt nie rosły razem z rozmiarem PR.

## Implementation Decisions

- **Moduł zbierania Change.** Jeden moduł z jednym punktem wejścia: funkcja `collect_change(base_ref, repo)` zwracająca `Change`. Moduł jest właścicielem typu `Change` i nie importuje niczego z grafu, stanu ani węzłów. Zależności idą jednokierunkowo: stan zależy od modułu, węzły od stanu i modułu, graf od węzłów.
- **Kształt `Change`.** Typowany obiekt z trzema listami ścieżek (łańcuchów): `intent`, `code`, `ignored`. Same ścieżki, bez statusu pliku. Przy zmianie nazwy zapisujemy tylko nową ścieżkę.
- **Źródło listy plików.** Lokalny `git diff --name-status` z wykrywaniem zmian nazw, w wersji trzykropkowej względem `origin/<base>`. Nie używamy GitHub API; zostaje jako rezerwa, gdyby diff okazał się niewiarygodny. Wymaga pełnej historii (`fetch-depth: 0`). W Actions checkout dla `pull_request` daje merge commit PR do bazy, więc trzy kropki dają dokładnie zmiany PR, także gdy baza poszła do przodu.
- **Reguły klasyfikacji, w tej kolejności.** (1) Plik usunięty → `ignored`. (2) Ścieżka pasuje do konwencji Intent file (`.scratch/**/*.md`, `docs/adr/**/*.md`) → `intent`. (3) Ścieżka pasuje do wzorców ignorowanych → `ignored`. (4) Reszta → `code`. Wzorce ignorowane: lockfile'e (`*.lock`, `package-lock.json`, `pnpm-lock.yaml`), obrazki i inne binaria rozpoznawane po rozszerzeniu, `dist/`, `*.min.*`, a także dokumentacja spoza Intent: wszystkie `*.md` i `docs/**` (w tym `README.md`, `CONTEXT.md`, `docs/agents/*.md`). Intent wygrywa z `docs/**`, bo reguła (2) jest przed (3). Binaria wykrywamy po rozszerzeniu, nie przez `--numstat`.
- **Konfiguracja.** Wzorce są stałymi w module, bez konfiguracji per repozytorium. Wszystkie moje repozytoria używają tej samej konwencji (`.scratch/`, `docs/adr/`).
- **Struktura wewnętrzna.** Cienkie wywołanie gita oraz czysta funkcja parsująca i klasyfikująca tekst `name-status`. Parser jest wewnętrznym seamem modułu, używanym przez jego własne testy.
- **Filtr w workflow.** W workflow repozytorium docelowego trigger `pull_request` dostaje `paths-ignore` z `'**.md'` i `'docs/**'`. GitHub pomija workflow tylko wtedy, gdy wszystkie zmienione pliki pasują do wzorców, więc jeden plik spoza listy uruchamia agenta. `paths` i `paths-ignore` nie mogą być użyte razem, więc nie używamy allowlisty. Filtr żyje w workflow, nie w composite action, bo jest oceniany przed startem naszego kodu.
- **Duplikat reguły "dokumentacja".** Ten sam podział istnieje w `paths-ignore` (decyduje, czy ruszyć runner) i w stałych modułu (decyduje, co recenzować w PR mieszanym). Zostaje świadomie jako duplikat z komentarzem w obu miejscach. Źródłem prawdy dla klasyfikacji są stałe w module. Kanoniczna lista jest opisana w `PROJECT_GOAL.md` obok przykładowego workflow.
- **Agent nie jest wymaganym checkiem.** Review publikujemy jako `COMMENT`, nie jako status check. Pominięty przez filtr workflow zostawia wymagane checki w stanie "Pending" i blokuje merge, więc agenta nie ustawiamy jako wymaganego w branch protection.
- **Stan.** `ReviewState` zyskuje pola wejściowe `base_ref`, `repo_path`, `pr_title`, `pr_body` (wszystkie opcjonalne w typie, `total=False`), pole `change` typu `Change` ustawiane przez `collect_input` oraz dotychczasowe `summary` ustawiane przez `run_agent`. Dotychczasowe pole `diff` jest usuwane.
- **Węzeł `collect_input`.** Wywołuje moduł zbierania Change z wartościami ze stanu i zwraca aktualizację z polem `change`. Nie czyta `os.environ` ani payloadu zdarzenia GitHub; czytanie ich to zadanie przyszłego punktu wejścia CLI.
- **Routing grafu.** Po `collect_input` krawędź warunkowa: jeśli `change["code"]` nie jest puste, następny jest `run_agent`, w przeciwnym razie `END`. `run_agent` i `publish` wtedy się nie wykonują i nic nie jest publikowane. To siatka bezpieczeństwa także dla PR-ów, które filtr workflow przepuścił (np. sam lockfile), dla uruchomień lokalnych i repozytoriów bez filtra.
- **Kontrakt dla przyszłego `run_agent`.** (Poza zakresem tej specyfikacji, ale ustalony.) Prompt budowany z `change["intent"]` (treść plików), tytułu i opisu PR; tytuł i opis mają najniższy priorytet jako dane niezaufane. Przy braku plików intencji prompt zawiera jawną informację "brak Intent". Diff nie jest w stanie; Agent dostaje listę plików z `change["code"]` i pobiera diff swoim narzędziem tylko do odczytu.
- **Dokumentacja.** Po implementacji `PROJECT_GOAL.md` trzeba poprawić: przykładowy workflow dostaje `paths-ignore`, drzewo repozytorium moduł zbierania Change, a zdanie "agent dostaje listę plików i diff w prompcie" ma mówić, że diff pobiera sam Agent. Słownik w `CONTEXT.md` (Change, Intent, Intent file, Ticket) jest już zapisany i nie wymaga zmian.

## Testing Decisions

- **Dobry test** sprawdza zewnętrzne zachowanie na prawdziwych wejściach: jakie ścieżki trafiają do jakiej grupy i dokąd kieruje graf. Nie sprawdza kolejności wywołań wewnętrznych funkcji ani sposobu parsowania.
- **Seam 1, najwyższy: `invoke` skompilowanego grafu.** Test na tymczasowym repozytorium git z gałęzią PR: PR z kodem i Intent files daje wypełnione `change` i przechodzi przez `run_agent` do `publish`; PR bez plików `code` kończy się bez wykonania `run_agent` i `publish`.
- **Seam 2: interfejs `collect_change`.** Tabela przypadków klasyfikacji na tymczasowych repozytoriach: kod, Spec, Ticket, ADR, `README.md`, `CONTEXT.md`, `docs/agents/*.md`, lockfile, obrazek, plik usunięty, plik przeniesiony, `docs/adr/*.md` (Intent mimo `docs/**`).
- **Test integracyjny semantyki trzech kropek.** Jeden test z prawdziwym tymczasowym repozytorium (`tmp_path`): baza, gałąź PR, merge commit, baza poszła do przodu po utworzeniu merge commita; asercja, że zwrócone są dokładnie zmiany PR. To jedyny test weryfikujący twierdzenie o checkoucie `refs/pull/N/merge`.
- **Seam wewnętrzny: parser.** Czyste funkcje parsujące i klasyfikujące testowane na tekstowych fixture'ach `name-status` w katalogu fixture'ów (zgodnie z `LEARNING_GOAL.md`), bez gita, dla szybkich i gęstych przypadków brzegowych (zmiana nazwy, kilka wzorców naraz, pusty diff).
- **Prior art.** Istniejący test grafu wywołuje `build_graph().invoke(...)` i sprawdza kolejność wykonania węzłów oraz końcowy stan; ten sam wzorzec obowiązuje dla Seam 1. Istniejący smoke test importu pakietu pozostaje bez zmian.

## Out of Scope

- Prawdziwa implementacja `run_agent`: wywołanie Claude Agent SDK, budowa promptu, czytanie treści Intent files, structured output i `Finding`.
- Węzeł `publish` i Pull Request Reviews API.
- Punkt wejścia CLI (`__main__`), czytanie zmiennych środowiskowych i payloadu `$GITHUB_EVENT_PATH`, `--dry-run`.
- Fallback przez GitHub API (`GET /pulls/{n}/files`).
- Limity rozmiaru diffu lub liczby plików; dodamy jeden limit dopiero, gdy prawdziwy PR go przekroczy, i wtedy w `run_agent`, nie w module Change.
- Per-plik diff i fan-out przez Send (krok 3 nauki LangGraph).
- Jawne kontrole zgodności z Intent (pokrycie kryteriów akceptacji, konflikt z ADR, pliki spoza zakresu) jako osobna kategoria Finding.
- Osobny węzeł `build_intent`; na razie prompt buduje `run_agent`.
- Konfiguracja wzorców per repozytorium.
- Wykrywanie binariów przez `--numstat`.

## Further Notes

- Odpowiedzi na ostatnią rundę pytań (Q17–Q20) nie padły wprost; spec przyjmuje rekomendacje: duplikat reguły w workflow i w module (Q17), `paths-ignore` (Q18), korekta kubełków z dokumentacją do `ignored` (Q19), końcowy kształt typów (Q20).
- Istniejący test grafu woła `invoke({})`. Po tej zmianie graf wymaga danych wejściowych w stanie, więc test trzeba dostosować do Seam 1.
- Test z `tmp_path` wymaga dostępnego `git` w środowisku testowym; używa lokalnych repozytoriów, bez sieci.
- Po filtrze `paths-ignore` commit zmieniający tylko `.md` w PR, który ma już kod, prawdopodobnie i tak ponownie uruchomi review: filtr dla `pull_request` używa diffu trzykropkowego całego PR. Dokumentacja GitHuba nie mówi tego wprost, więc zachowanie warto potwierdzić w repozytorium testowym.
