# 03: Findings w komentarzu ze statusem

Spec: `.scratch/action-entry/spec.md`

**What to build:** `render_status_comment` i `publish_status_comment` przyjmują `findings`; `publish` przekazuje `state["findings"]`. Sekcja „Uwagi” stoi między `summary` a „Ostrzeżeniami”.

**Blocked by:** nic.

**Status:** ready-for-agent

- [x] Każdy Finding: waga i miejsce (`plik:linia`, sam plik albo „uwaga ogólna”), treść, `Sugestia:` i `Wymaganie:` (`spec_ref`) gdy są
- [x] Pola z modelu i z PR w code span, jedna linia, ucięte do limitu; `@nick`, linki, obrazki, HTML i znaki sterujące nieaktywne (test z wrogim tekstem)
- [x] Brak Findings: brak sekcji
- [x] `CONTEXT.md` (Status comment) i `docs/PROJECT_GOAL.md` opisują komentarz z Findings
