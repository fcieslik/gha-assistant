# Code-review agent: cel nauki

## Typ projektu

Ten projekt służy do nauki. Nie jest to produkt dla klientów.
Celem jest ćwiczenie Pythona i LangGraph na prawdziwym przypadku użycia.

## Co buduję

Agent robi code review pull requestu w GitHub.
GitHub uruchamia agenta przez trigger. Wynikiem jest review (podsumowanie i Findings) opublikowane w PR.

## Czego chcę się nauczyć

- Python w projekcie z kilkoma modułami: pakiet instalowalny przez pip, CLI, testy pytest.
- LangGraph: budowa grafu agenta (zakres w tabeli poniżej).
- Claude Agent SDK jako warstwa agenta pod spodem.
- GitHub Actions: workflow, composite action, uprawnienia, secrets, `concurrency`.
- GitHub API: pobieranie diffu, Pull Request Reviews API (komentarze przy liniach).
- Testowanie agenta lokalnie: tryb `--dry-run`, zapisane diffy (fixtures), atrapa modelu.
- Bezpieczeństwo agentów: prompt injection, minimalne uprawnienia narzędzi.

## Zakres nauki LangGraph

### Uczę się teraz

| Koncept                             | Do czego służy w tym projekcie                                      |
| ----------------------------------- | ------------------------------------------------------------------- |
| State (TypedDict lub Pydantic)      | Diff, lista plików, lista `Finding`, podsumowanie                   |
| Nodes                               | Funkcje: `fetch_pr`, `review_file`, `post_review`                   |
| Edges i conditional edges           | Kolejność kroków i rozgałęzienia                                    |
| Reducers                            | Łączenie wyników z równoległych węzłów w jedną listę                |
| Send API (map-reduce)               | Jeden węzeł na zmieniony plik                                       |
| compile / invoke / ainvoke          | Uruchomienie grafu z punktu wejścia                                 |
| Structured output                   | Model zwraca obiekt `Finding` (plik, linia, waga, treść)            |
| Tool calling i ToolNode             | Etap 2: narzędzia `read_file` i `grep`                              |
| Streaming (`stream_mode="updates"`) | Podgląd wyników węzłów podczas debugowania                          |
| Command                             | Opcjonalnie: zmiana stanu i wybór następnego węzła w jednym miejscu |
| RetryPolicy                         | Powtórzenie wywołania po błędzie LLM lub GitHub                     |
| Rysowanie grafu                     | Diagram grafu w README                                              |

### Uczę się później

- Checkpointer, threads, persistence (agent w Actions nie ma stanu między uruchomieniami).
- Interrupt i human-in-the-loop.
- Subgraphs.
- Input/output schema i runtime context.
- LangGraph Studio i LangSmith.
- Prebuilt ReAct agent (najpierw zbuduję pętlę ręcznie, raz).

### Pomijam

- Store i pamięć długoterminowa.
- Time travel.
- Functional API (używam tylko StateGraph).
- Biblioteki multi-agent (supervisor, swarm).
- LangGraph Platform, Server, Cloud.
- Wewnętrzne mechanizmy (Pregel, channels).
- Cache węzłów, deferred nodes.
- Własne serializery checkpointów.

Uwaga: nazwy modułów w wersji 1.x trzeba sprawdzić w aktualnej dokumentacji.

## Kolejność nauki

1. State, nodes, edges, `compile`, `invoke`. Graf z trzech węzłów.
2. Structured output. `Finding` i `review_file` dla jednego pliku.
3. Reducers i Send API. Równoległe review wielu plików.
4. Streaming i rysowanie grafu.
5. RetryPolicy.
6. Tool calling (`read_file`, `grep`).

Kroki 1–4 dają działającą wersję agenta. Kroki 5–6 są rozszerzeniem.
