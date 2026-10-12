# gha-assistant

Agent robiący code review pull requestów w GitHubie, uruchamiany z GitHub Actions. Wynikiem jest Review opublikowane w PR.

## Language

**Review**:
To, co publikujemy do PR: jedno podsumowanie plus lista Findings.
_Avoid_: raport, report

**Finding**:
Pojedyncza uwaga do kodu: plik, linia, waga, treść, sugestia. Ten sam kształt na każdym etapie grafu. Ma `source` (`code` albo `spec`), a uwaga ze `source` `spec` ma też `spec_ref` (Intent file i kryterium). Uwaga bez pliku i linii jest uwagą ogólną. `id` i `source` nadaje kod, nigdy model.
_Avoid_: komentarz, issue, remark

**Candidate**:
Finding prosto od recenzenta (`review_code`, `review_intent`), jeszcze niezwalidowany. Staje się Findingiem w Review dopiero po `validate_findings` i `judge_findings`.
_Avoid_: kandydat na komentarz, draft

**Verdict**:
Wynik sprawdzenia jednego Findingu `high` przez `verify_finding`: `confirmed`, `refuted` albo `inconclusive`, z krótkim uzasadnieniem, powiązany z Findingiem po `id`. `refuted` wyrzuca Finding z Review; `inconclusive` oznacza też, że weryfikacja się nie powiodła mimo ponowień.
_Avoid_: ocena, decyzja sędziego

**Judge**:
Node `judge_findings`: zamyka Review. W v1 to czysta funkcja bez modelu (odrzuca `refuted`, sortuje wg wagi, tnie do limitu, buduje `summary`). Sędzia z modelem (scalanie duplikatów semantycznych, odrzucanie stylu) jest odłożony, patrz `.scratch/review-agent/issues/08-judge-findings.md`.
_Avoid_: reviewer, ewaluator

**Agent**:
Wywołanie Claude Agent SDK wewnątrz węzła grafu. Czyta kod i zwraca Findings; niczego nie publikuje.
_Avoid_: graf, pipeline

**Change**:
Zbiór plików faktycznie zmienionych w PR, czyli wynik diffu względem bazy.
_Avoid_: files affected, zmiany

**Intent**:
Dokumenty opisujące, po co jest PR: Intent files z Change oraz tytuł i opis PR.
_Avoid_: goal, cel PR

**Intent file**:
Plik w Change rozpoznany po konwencji ścieżek jako Spec, Ticket lub ADR.
_Avoid_: plik markdown, dokumentacja

**Ticket**:
Jedna jednostka pracy do wykonania w PR, opisana własnym plikiem.
_Avoid_: issue, task

**Status comment**:
Jeden komentarz w rozmowie PR, który każdy run tworzy albo nadpisuje: status runa (np. brak kodu do sprawdzenia), `summary`, lista Findings (każdy jako code span) i ostrzeżenia. Nie jest Review w sensie Reviews API: v1 nie ma komentarzy przy liniach.
_Avoid_: Review, raport
