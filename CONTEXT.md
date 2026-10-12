# gha-assistant

Agent robiący code review pull requestów w GitHubie, uruchamiany z GitHub Actions. Wynikiem jest Review opublikowane w PR.

## Language

**Review**:
To, co publikujemy do PR: jedno podsumowanie plus lista Findings.
_Avoid_: raport, report

**Finding**:
Pojedyncza uwaga do kodu: plik, linia, waga, treść, sugestia.
_Avoid_: komentarz, issue, remark

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
Jeden komentarz w rozmowie PR, który każdy run tworzy albo nadpisuje: status runa (np. brak kodu do sprawdzenia) i `summary`. Nie jest Review ani Findingiem.
_Avoid_: Review, raport
