# Feature Plan: UI Polish — OECD-corporate theme (Phase 4)

**Status:** Draft — 2026-04-22
**Scope:** `agent_app/frontend/` only. Read-only elsewhere.
**Approach:** 3 sequential passes, one PR each. Subagent-driven via `ui-developer`.
**No new deps.** Plain CSS + CSS vars. Keep CSS Modules convention.

## Design tokens (OECD-corporate)

Defined in `app/globals.css` as `:root` vars, reused by all components.

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#0060A9` | OECD blue — buttons, accents, focus ring |
| `--color-primary-hover` | `#004C87` | Hover state |
| `--color-primary-contrast` | `#FFFFFF` | Text on primary |
| `--color-bg` | `#F5F7FA` | App background |
| `--color-surface` | `#FFFFFF` | Card/container bg |
| `--color-border` | `#E1E5EB` | Subtle separators |
| `--color-text` | `#1A1F2E` | Body text |
| `--color-text-muted` | `#5A6578` | Secondary text |
| `--color-tool-bg` | `#EEF3F8` | Tool call block bg |
| `--radius-sm` | `4px` | Inputs |
| `--radius-md` | `8px` | Cards, buttons |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)` | Card elevation |
| `--font-sans` | Next `Inter` (already loaded) | Body |
| `--space-*` | `4/8/12/16/24/32/48px` | Layout rhythm |

## Pass P1 — App shell (branded header + layout)

**Goal:** Replace bare `<select>` + floating "start" with a real app shell.

**Files:**
- `app/layout.tsx` — confirm `Inter` font loader applied body-wide
- `app/globals.css` — add design tokens + reset (body bg/color/font)
- `app/page.module.css` — new shell classes (`.appShell`, `.header`, `.main`, `.container`)
- `app/page.tsx` — wrap in shell markup
- `app/components/DelegatePicker.tsx` — replace inline `style={{opacity}}` with CSS module class; style the `<select>` to match OECD

**Shell structure:**
```
<div class=appShell>
  <header class=header>
    <div class=brand>  <!-- OECD wordmark + "ONE-MP Read Agent" subtitle -->
  </header>
  <aside class=personaBar>  <!-- styled DelegatePicker + label "Acting as" -->
  <main class=main>
    <div class=container>  <!-- max-width 900px, centered, card -->
      <ChatPane />
```

**Acceptance:**
- Page renders with OECD blue header band (~64px), white wordmark
- Persona picker labeled "Acting as", styled select (border, padding, focus ring)
- Chat area sits in centered card (max-width 900px, `--shadow-card`)
- Body bg = `--color-bg`, font = Inter
- No layout shift on load; select doesn't overlap header
- **Manual check:** run dev server, hit `localhost:3000`, screenshot before/after

**Tests:** existing e2e_agent suite (4 tests) must still pass — no markup changes that break selectors (`select`, `[data-testid='copilot-assistant-message']`, `details`).

## Pass P2 — CopilotKit chat theming

**Goal:** Skin the CopilotKit chat to match OECD tokens.

**Files:**
- `app/globals.css` — override CopilotKit CSS vars (`--copilot-kit-primary-color`, `--copilot-kit-background-color`, `--copilot-kit-separator-color`, `--copilot-kit-muted-color`, etc.)
- `app/page.module.css` — wrap/override for assistant bubble, user bubble, input bar

**CopilotKit v2 CSS vars to set (verify via Context7 `/copilotkit/copilotkit` before writing):**
- Primary color → `--color-primary`
- Background → `--color-surface`
- Border radius → `--radius-md`
- Font → inherit

**Acceptance:**
- Assistant messages: white bg, subtle border, body text color
- User messages: OECD blue bg, white text
- Input bar: bordered, focus ring matches primary
- Disclaimer text color = `--color-text-muted`
- Send button = primary

**Tests:** e2e_agent still green.

## Pass P3 — Tool call blocks

**Goal:** The `<details>` accordion listing `lookup_delegate`, `get_agenda_documents` etc. is currently raw. Style it readable + collapsible with intent.

**Files:**
- `app/page.module.css` (or new `tool-call.module.css`) — classes for `details`, `summary`, `pre`
- If tool blocks are rendered by CopilotKit internals: use global CSS descendant selector on `.chatPane details`

**Acceptance:**
- `<summary>` shows: chevron icon (CSS-only, rotates on open), tool name bold, status badge `[complete]` in muted pill
- Border-left accent in `--color-primary` when open
- `<pre>` result: `--color-tool-bg`, monospace, `--radius-sm`, scrolls horizontally on overflow
- Collapsed tools stack tightly (no double-margin)

**Tests:**
- `test_tool_call_blocks_visible` still asserts `details` count — selectors unchanged
- Visual: 4 tool calls stack cleanly, open/close animates

## Execution order

1. Branch `feature/ui-polish-p1-shell`
2. Subagent `ui-developer` → implement P1 against this plan
3. Manual verify + screenshot + `pytest tests/e2e_agent/`
4. Merge to main
5. Repeat for P2, P3

## Out of scope (Phase 5+)

- Dark mode
- Tailwind migration
- Classical Flask app restyle
- Wizard UI rework
- Mobile responsive pass (keep desktop-first for demo)
