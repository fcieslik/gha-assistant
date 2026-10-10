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
