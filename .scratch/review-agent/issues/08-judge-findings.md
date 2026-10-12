# 08: Prawdziwy `judge_findings`

Spec: `.scratch/review-agent/spec.md`

**What to build:** Sonnet, bez narzędzi, dostaje Findings i werdykty jako dane, a zasady w prompcie systemowym. Zwraca decyzje po `id` (zostaw, odrzuć, scal, z wagą i powodem) oraz `summary`. Kod stosuje decyzje do oryginalnych Findings, więc sędzia nie dopisze Findingu ani nie zmieni miejsca w kodzie. Węzeł ma wspólną politykę `AGENT_RETRY` i Review awaryjne po jego wyczerpaniu.

**Blocked by:** 07 (Prawdziwy `verify_finding`).

**Status:** ready-for-agent

- [ ] Sędzia nie ma żadnych narzędzi (`tools=[]` w serwisie Agenta); Findings i werdykty podane jako blok danych, zasady jako stała w prompcie systemowym
- [ ] Wyjście: lista decyzji (`id`, werdykt, `merge_into`, waga, powód) i `summary`
- [ ] Funkcja stosująca decyzje jest czysta: odrzuć, scal, zmień wagę, nieznane `id` ignorowane, próba dopisania Findingu ignorowana; tabela przypadków
- [ ] Zasady: odrzucaj `refuted`, scalaj duplikaty semantyczne, wagę wg wpływu, nie stylu, odrzucaj czysty styl, nie dopisuj nowych Findings, limit uwag w Review (stała)
- [ ] Model sędziego (`JUDGE_MODEL`, Sonnet) jako stała w serwisie Agenta
- [ ] `AGENT_RETRY`; po wyczerpaniu Review awaryjne: zwalidowane Findings posortowane wg wagi, z adnotacją w `summary`
- [ ] Test na granicy z atrapą: sędzia próbujący dopisać Finding lub podmienić linię nie zmienia wyniku; awaria sędziego daje Review awaryjne
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` i `uv run pytest` przechodzą
