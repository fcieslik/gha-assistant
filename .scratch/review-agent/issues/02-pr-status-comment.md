# 02: Komentarz w PR ze statusem i podsumowaniem (upsert)

Spec: `.scratch/review-agent/spec.md`

**What to build:** Każdy run kończy się informacją widoczną w PR, żeby zielony run nie wyglądał jak run bez wyniku. Jedna funkcja w `github_io.py` zostawia w PR komentarz (issue comment) i przy kolejnych runach nadpisuje go w miejscu: szuka własnego komentarza po ukrytym znaczniku, edytuje go, a gdy go nie ma, tworzy. Korzystają z niej oba nody kończące graf: `nothing_to_review` (status "nie ma kodu do sprawdzenia", z liczbami ignorowanych i Intent files) oraz `publish` (status "sprawdzono N plików" i `summary`, także gdy nie ma żadnych Findings). Komentarze przy liniach i Pull Request Reviews API są poza zakresem tego ticketu.

**Blocked by:** 01 (Wyjście bez kodu do recenzji przez `Command`).

**Status:** ready-for-agent

- [x] Cel publikacji wchodzi do stanu jako wejście: `repo` (`owner/name`), `pr_number`, `head_sha` i `dry_run`. Token pochodzi ze zmiennej środowiskowej, nie ze stanu, żeby nie trafiał do `stream_mode` ani logów
- [x] `head_sha` to ostatni commit gałęzi PR (`github.event.pull_request.head.sha`), nie `GITHUB_SHA`, który w `pull_request` wskazuje tymczasowy commit scalający nieobecny na liście commitów PR. Graf dostaje go jako gotowe wejście (jak `base_ref`); przekazanie z workflow lub `action.yml` jest poza zakresem tego ticketu. Lokalnie przy `dry_run` wystarczy `git rev-parse HEAD`
- [x] Brak celu lub tokenu bez `dry_run` kończy się `ValueError` z czytelnym komunikatem (run czerwony, nie zielony bez śladu); z `dry_run` treść komentarza jest drukowana zamiast wysyłana
- [x] Funkcja upsert: lista komentarzy PR, komentarz ze znacznikiem i autorem będącym botem jest edytowany, w przeciwnym razie tworzony; sam znacznik nie wystarcza, bo cudzy komentarz z tym tekstem nie może przejąć ani zablokować publikacji
- [x] Treść komentarza to czysta funkcja: status w jednej linii, `summary` gdy jest, SHA commita i czas; warianty "brak kodu do sprawdzenia" (z liczbami) i "sprawdzono N plików" (także przy zerze Findings, jako "brak uwag")
- [x] `nothing_to_review` wywołuje upsert ze statusem, nadal drukuje do logu i nie zmienia stanu
- [x] `publish` wywołuje upsert z podsumowaniem; brak Findings daje komentarz "brak uwag", nie ciszę
- [x] Test z atrapą: dwa runy na tym samym PR dają jeden komentarz (drugi to edycja); cudzy komentarz ze znacznikiem nie jest nadpisywany, powstaje własny
- [x] `RetryPolicy` na `nothing_to_review` i `publish` z predykatem błędów przejściowych GitHub API (5xx, timeout, błąd połączenia); błąd trwały (401/403/404) daje 1 wywołanie i czerwony run; ponowienie po błędzie przejściowym nie tworzy duplikatu (upsert jest idempotentny)
- [x] Testy na poziomie grafu (`stream_mode="updates"` i atrapa granicy GitHub): PR bez kodu daje jeden upsert z komunikatem "brak kodu"; PR z kodem daje jeden upsert z `summary`
- [x] Istniejące testy grafu dostosowane (przekazują `dry_run` albo atrapę granicy GitHub)
- [x] W komentarzu przy funkcji upsert opisane ograniczenia: PR z forka dostaje token tylko do odczytu (poza zakresem), a nadpisanie gubi poprzedni wynik, dlatego treść zawiera SHA i czas
- [x] `docs/PROJECT_GOAL.md`: opis publikacji uzupełniony o komentarz ze statusem, obok Review z komentarzami przy liniach
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
