# 03: Szkielet grafu: puste nody i topologia

Spec: `.scratch/review-agent/spec.md`

**What to build:** Sama topologia recenzji w LangGraph, bez żadnego modelu. Węzeł `run_agent` znika, a graf ma nody `review_code`, `review_intent`, `validate_findings`, `verify_finding`, `judge_findings` i dotychczasowy `publish`. Nody są puste: nie mają logiki, tylko zwracają stały, deterministyczny wynik, żeby każda gałąź topologii się wykonała. `review_code` jest uruchamiany `Send` raz na plik z `change["code"]`, `review_intent` raz, tylko gdy są Intent files, `verify_finding` `Send` raz na Finding. `collect_input` w ścieżce z kodem kieruje `goto` do tego fan-outu. Wyniki równoległych nodów łączą reducery.

**Blocked by:** 02 (Komentarz w PR ze statusem i podsumowaniem).

**Status:** ready-for-agent

- [x] `Finding` ma docelowy, typowany kształt ze specyfikacji (`id`, `source`, `severity`, `message`, `file`, `line`, `evidence`, `suggestion`, `spec_ref`); `ReviewState` ma pola etapów (kandydaci, zwalidowane, werdykty, końcowe Findings, ostrzeżenia) z reducerami tam, gdzie piszą równoległe nody
- [x] Nody z modelem są `async`, graf jest uruchamiany przez `ainvoke`; testy uruchamiają go bez nowej zależności (np. `asyncio.run`) lub z `pytest-asyncio`, jedna decyzja opisana w tickecie
  - Decyzja: `asyncio.run(graph.ainvoke(...))` w helperach testów (`_invoke`, `_updates`), bez `pytest-asyncio`. Testy są synchroniczne, a async jest tylko tam, gdzie wymaga go graf; nowa zależność nie jest potrzebna.
- [x] Stuby: `review_code` zwraca jedną zakotwiczoną uwagę na pierwszą linię pliku, `review_intent` jedną uwagę ogólną, `validate_findings` przepuszcza bez zmian, `verify_finding` zwraca werdykt `confirmed`, `judge_findings` zostawia wszystko i ustawia `summary` na stały tekst
- [x] `review_code` wykonuje się dokładnie raz na plik z `change["code"]`; `review_intent` raz, tylko gdy `change["intent"]` jest niepuste
- [x] Fan-in: `validate_findings` wykonuje się raz po wszystkich recenzentach, także gdy `review_intent` został pominięty (osobne krawędzie, nie bariera listowa)
- [x] Brak Findings po walidacji: graf przechodzi wprost do `publish`, z pominięciem `verify_finding` i `judge_findings` (puste `Send` nie może po cichu zakończyć grafu)
- [x] `verify_finding` wykonuje się raz na Finding (do stałej limitu), a pozostałe Findings przechodzą dalej jako niezweryfikowane
- [x] Testy na poziomie grafu (`stream_mode="updates"`): liczba wykonań każdego node dla PR z N plikami, z i bez Intent files, z zerem Findings
- [x] `max_concurrency` grafu ustawione stałą
- [x] Istniejące testy grafu zmienione z asercji na wydruk na asercje na `stream_mode="updates"`
- [x] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
