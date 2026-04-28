---
goal: Tighten typography of assistant markdown in CopilotKit chat pane
version: 1.0
date_created: 2026-04-24
last_updated: 2026-04-24
owner: frontend
status: 'Planned'
tags: ['feature', 'ui-polish', 'phase3-followup', 'css']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Phase 3 shipped end-to-end brief rendering through CopilotKit v2, but the
rendered assistant markdown lacks typographic hierarchy: paragraphs, list
sections, and the meeting-lead lines all render with identical weight and
cramped vertical rhythm (see screenshot captured 2026-04-24). This plan
introduces a small, CSS-scoped polish pass — plus one targeted prompt tweak
— that gives the brief the document-like structure it needs. No behaviour
change, no new tools, no redesign.

## 1. Requirements & Constraints

- **REQ-001**: Assistant message body must show clear vertical rhythm
  between paragraphs and between lists and surrounding paragraphs.
- **REQ-002**: Meeting-lead lines ("For the X Committee Y Meeting on
  DATE:") must read as section headers, visually distinct from body copy.
- **REQ-003**: List items must have comfortable indent and inter-item
  spacing; bullet glyph must sit clearly to the left of item text.
- **REQ-004**: Overall reading line-height inside assistant bubbles must
  be ≥ 1.55 for body copy.
- **CON-001**: All style changes MUST be scoped under `.copilotKitChat`
  (or narrower). No edits to global `p`, `ul`, `li` selectors.
- **CON-002**: CopilotKit v2 renders markdown internally; the React
  component cannot be overridden. Styling must be purely CSS descendant
  rules on emitted class names / tag names.
- **CON-003**: Must not break existing user-bubble, input, or tool-call
  (accordion) styles shipped in P1/P2/P3.
- **CON-004**: No change to Next.js, CopilotKit, or Agent Framework
  versions. No new dependencies.
- **GUD-001**: Prefer prompt-level markdown (emit `**bold**` for meeting
  leads) over CSS heuristics that pattern-match text content.
- **GUD-002**: Keep diff small — target single CSS block appended to
  `agent_app/frontend/app/globals.css` and a single prompt edit.
- **PAT-001**: Follow the existing `.copilotKitChat {}` override block
  pattern already in `globals.css` (lines 66–86).
- **PAT-002**: Use existing OECD design tokens (`--space-*`,
  `--color-*`) where applicable; do not introduce raw px/hex values.

## 2. Implementation Steps

### Implementation Phase 1 — DOM probe

- GOAL-001: Capture the exact HTML class names and tag structure
  CopilotKit v2 emits inside `.copilotKitAssistantMessage` for a rendered
  markdown brief, so Phase 2 selectors target real classes, not guesses.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Start `uvicorn agent_app.server:app --port 8001` and `npm run dev` (port 3000) in `agent_app/frontend`. Verify `.env` contains `FOUNDRY_MODEL=gpt-4.1-mini`. | | |
| TASK-002 | In browser at `http://localhost:3000`, select a delegate, wait for brief to render. Open DevTools → Elements, locate `.copilotKitMessage.copilotKitAssistantMessage` and record its descendant structure: which element holds the markdown (likely a `.copilotKitMarkdown` or direct children), and the tag names / classes of `p`, `ul`, `ol`, `li`, `strong`, `h1`-`h3` inside it. | | |
| TASK-003 | Write the observed selector path (e.g. `.copilotKitChat .copilotKitAssistantMessage .copilotKitMarkdown > p`) into the PR description or a scratch note so Phase 2 uses verified selectors. Do NOT rely on `reference_copilotkit_v2_css_vars.md` memory for emitted class names — confirm against live DOM. | | |

### Implementation Phase 2 — Typography CSS

- GOAL-002: Append a scoped "assistant markdown typography" block to
  `agent_app/frontend/app/globals.css` that gives assistant messages clear
  vertical rhythm, comfortable lists, and heading-like lead lines.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | In `agent_app/frontend/app/globals.css`, after the existing `.copilotKitMessage.copilotKitAssistantMessage { ... }` block (~line 93), add a section comment `/* ── Assistant markdown body ─── */` and a rule setting `line-height: 1.6` and `font-size: 15px` (or the existing body size) on the markdown container selector identified in TASK-002. | | |
| TASK-005 | Add `margin-block: var(--space-3) 0` to the first paragraph inside the assistant markdown container and `margin-block: var(--space-3) 0` to subsequent `p` siblings — verify that first child has no top margin using `:first-child`. Goal: paragraph-to-paragraph gap ≈ 12px, no leading gap above first line. | | |
| TASK-006 | Style `ul, ol` inside the container: `margin-block: var(--space-2) var(--space-3)`, `padding-inline-start: var(--space-5)` (24px indent). Style `li`: `margin-block: var(--space-1)` for comfortable inter-item rhythm. | | |
| TASK-007 | Style `strong` inside the container: `font-weight: 600`, `color: var(--color-text)`. This gives meeting-lead lines (emitted as `**…**` — see Phase 3) a visible weight without becoming a true `h3`. | | |
| TASK-008 | Add a defensive rule that `h1, h2, h3, h4` inside the container fall back to `font-size: 15px; font-weight: 600; margin-block: var(--space-3) var(--space-1)` in case the model emits headings — prevents oversized browser-default heading sizes from breaking the card. | | |
| TASK-009 | Confirm no rule leaks to `.copilotKitUserMessage` or `.copilotKitInput` by keeping every selector prefixed with `.copilotKitChat .copilotKitAssistantMessage`. | | |

### Implementation Phase 3 — Prompt emits semantic bold

- GOAL-003: Encourage the model to emit `**Meeting-lead**` markdown so
  TASK-007's `strong` rule creates the section-header effect, rather than
  relying on CSS content-matching heuristics.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | In `agent_app/agent.py` `SYSTEM_PROMPT`, under "Proactive Session Brief" step 5 (line ~65), add a one-line formatting directive: "Format the brief in Markdown. Render each meeting-lead line (e.g. `For the X Committee Y Meeting on DATE:`) in bold using `**...**`. Separate each meeting block with a blank line." | | |
| TASK-011 | Re-run eval harness (`python -m eval.harness`) if it is wired to compare brief output shape, OR confirm manually that new wording does not regress the `Good day, <name>.` greeting path used by e2e test `e2e_agent`. | | |

### Implementation Phase 4 — Verify

- GOAL-004: Confirm the typography reads as intended and existing tests
  still pass.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Reload `http://localhost:3000`, re-run the "start" flow used for the 2026-04-24 screenshot, and capture a new screenshot at the same viewport. Visually verify: (a) gap between "Good day…" and "I have reviewed…" ≈ 12px; (b) "For the Education Committee…" line is bold; (c) bullet `•` sits at 24px indent; (d) bullet-to-bullet gap is visible; (e) closing "Please let me know…" separated from list above by a full paragraph gap. | | |
| TASK-013 | Run `pytest tests/` — all 203 unit tests must still pass. | | |
| TASK-014 | Run `pytest tests/e2e/` with uvicorn+npm dev server up — the 4 brief e2e tests (`e2e_agent`) must still pass within budget (~46s baseline). | | |
| TASK-015 | Attach before/after screenshots to the PR description; reference this plan filename. | | |

## 3. Alternatives

- **ALT-001**: Wrap `<CopilotChat>` with a custom `MessageRenderer` that
  owns markdown rendering (e.g. `react-markdown`). Rejected — CopilotKit
  v2 does not expose a stable markdown-override prop at the level we use
  (`useCoAgent` was dropped; see `reference_copilotkit_v2_migration`), and
  this would pull in a new dep plus a second markdown pipeline. CSS-only
  reaches the same result for 10% of the code.
- **ALT-002**: Pattern-match meeting-lead lines in CSS via a content
  regex (`p:has(...)` or attribute selector). Rejected — fragile, no
  cross-browser guarantee for the string test, and couples visual
  structure to exact English wording from the model.
- **ALT-003**: Switch the brief to a React-rendered structured component
  (cards per meeting) via a dedicated tool. Rejected as out of scope —
  that is a Phase 4+ product decision, not a typography fix.

## 4. Dependencies

- **DEP-001**: CopilotKit v2 preview packages already installed
  (`@copilotkit/react-core/v2`, `@copilotkit/react-ui`). No new deps.
- **DEP-002**: Existing OECD design tokens declared at `:root` in
  `agent_app/frontend/app/globals.css` (lines 1–32).

## 5. Files

- **FILE-001**: `agent_app/frontend/app/globals.css` — append one CSS
  block (~25 lines) after the existing assistant-bubble rule. Only file
  touched in the frontend.
- **FILE-002**: `agent_app/agent.py` — one added sentence in
  `SYSTEM_PROMPT` step 5 directing bold meeting leads.
- **FILE-003**: `plan/feature-phase3-chat-typography-fix-1.md` — this
  plan file (new).

## 6. Testing

- **TEST-001**: Visual regression via side-by-side screenshot comparison
  at 1440×900 viewport. Before = `Capture08-53-57.png`; After = new
  capture from TASK-012. Criteria enumerated in TASK-012 (a)–(e).
- **TEST-002**: Existing unit test suite (`pytest tests/`, 203 tests)
  must remain green. Only prompt text changed; any test that asserts
  exact prompt string would need a one-line update.
- **TEST-003**: Existing e2e brief suite (`pytest tests/e2e/`, 4 tests)
  must remain green — especially `e2e_agent` which asserts the brief
  reaches the DOM. Any `textContent`-based assertions must not depend on
  HTML tags, only the visible text — verify assertions still match after
  markdown bolds parts of the output.

## 7. Risks & Assumptions

- **RISK-001**: CopilotKit v2 markdown emits class names that differ
  from `reference_copilotkit_v2_css_vars.md`. Mitigation: TASK-002
  requires live-DOM inspection before writing selectors.
- **RISK-002**: A pre-existing unit test asserts the exact SYSTEM_PROMPT
  string and will fail after TASK-010. Mitigation: grep for
  `"Proactive Session Brief"` before editing; update the assertion in
  the same commit.
- **RISK-003**: E2E test assertions on brief text match the model
  output loosely; if they currently assert against a literal non-bold
  substring, no impact. If they assert on DOM (e.g. role=paragraph), the
  added `<strong>` wrapping could shift text node boundaries.
  Mitigation: run e2e in TASK-014 and inspect any failures.
- **ASSUMPTION-001**: The model reliably honours the "bold the
  meeting-lead line" instruction. If flaky, CSS still improves vertical
  rhythm; the bold is additive, not load-bearing for readability.
- **ASSUMPTION-002**: CopilotKit's markdown renderer emits real
  `<strong>`, `<ul>`, `<li>`, `<p>` tags (standard remark/rehype output).
  Verified during TASK-002.

## 8. Related Specifications / Further Reading

- `plan/completed/feature-ui-polish-phase4-oecd-1.md` — P1/P2/P3 OECD
  theming plan (completed). This fix lives on the same surface.
- `agent_app/frontend/app/globals.css` lines 66–113 — existing
  `.copilotKitChat` override block pattern to follow.
- Memory: `reference_copilotkit_v2_css_vars.md` — CopilotKit v2 CSS
  custom properties and class names (context only; verify live DOM
  before writing selectors).
- Memory: `reference_copilotkit_v2_migration.md` — v2 API migration
  notes; explains why custom markdown renderer override is not viable.
- Screenshot: `/home/stephane/Téléchargements/Capture08-53-57.png` —
  baseline "before" capture.
