# Visual verification notes — for future skill design

Logging obstacles, surprises, and recoveries during chrome-devtools-driven
e2e verification of bug-delegate-identity-leak Phase 4.

## Setup

- Backend: `uvicorn agent_app.server:app --port 8001` (background)
- Frontend: `npm run dev` in `agent_app/frontend/` (background)
- Browser: chrome-devtools MCP
- Goal: select Alice Leblanc → verify brief greeting cites "Alice Leblanc"

## Log

### Obstacle 1 — pre-existing services bound to ports
Backend already on 8001 (PID 94904) and frontend on 3000 (PID 95562) from
prior main-checkout dev session. New worktree code won't be live until those
are killed. **Lesson:** before visual verification, `ss -tlnp | grep -E
':(3000|8001) '` and explicitly stop pre-existing dev processes; otherwise
you test old code while believing you tested the fix.

### Obstacle 2 — venv editable install points to main, not worktree
`.venv` lives at project root and `pip install -e .` registered the
main-checkout `agent_app/` package path. Per memory
`reference_worktree_dev_stack_bootstrap.md`, running uvicorn with cwd =
worktree means cwd-import precedence wins and worktree code loads. So no
re-install needed, but **must launch uvicorn from the worktree directory**.

### Obstacle 4 — backgrounded uvicorn via plain `&` worked here
`source .venv && uvicorn ... &` from a Bash tool call kept running after
the bash invocation returned. Verified by `ss -tlnp` showing port still
bound. Not always reliable across environments — prefer `run_in_background`
parameter on the Bash tool when available, but the `&` approach worked.

### Obstacle 5 — wait_for needs exact text candidates
First check used `["Hello Marie Dupont", "Marie Dupont,"]` and timed out
even though text "Good day, Marie Dupont" was present. The candidate list
must include the exact prefix the model produced. **Lesson:** for brief
verification, use a broad anchor like the bare name `"Marie Dupont"` rather
than guessing at the salutation phrasing. Or: take_snapshot first, grep the
content, only use wait_for for known sentinel strings.

### Obstacle 5b — bare name anchor matches the dropdown <option>
Discovered during 2026-04-25 skill dry-run on main. `wait_for
["Alice Leblanc"]` returned instantly because the combobox's `<option
value="Alice Leblanc (...)">` matched. False positive — brief had not
streamed. **Correct anchor**: greeting prefix + name (`"Good day, Alice"`
/ `"Hello Alice"` / `"Dear Alice"`) or one of the known closing phrases
(`"nothing new"` / `"no new"`). Skill updated.

### Obstacle 6 — `fill` on native <select> works without click-to-open
Setting the combobox value via `fill(uid, "Option text")` triggered the
React-Select onChange and the brief re-ran. No need to click-then-click
through the menu. Saves 2 round trips.

### Obstacle 7 — brief takes 30-45s end-to-end
4 tool calls (whoami → get_upcoming_meetings → 2-3 × get_agenda_documents)
then streaming tokens. `wait_for` timeout must be ≥45s for safety.

### Obstacle 3 — frontend .env.local missing in worktree
`agent_app/frontend/.env.local` does not exist in worktree (only
`agent_app/.env` exists). Need to copy from main checkout or recreate
before `npm run dev`. (Or reuse the main-checkout frontend on :3000 since
the bug is purely backend-side; frontend just renders whatever brief the
backend streams.)

## Verdict

Fix verified end-to-end:
- Alice Leblanc selected → first tool call `whoami COMPLETE` →
  greeting "Hello Alice Leblanc,"
- Switched to Marie Dupont → first tool call `whoami COMPLETE` →
  greeting "Good day, Marie Dupont." with her committees (Edu/Env/Trade)
- No "Marie Dupont" leak when Alice was selected
- `lookup_delegate` was NOT called (model honoured prompt instruction)

## Skill design checklist (for future visual-verification skill)

1. **Pre-flight**: `ss -tlnp | grep -E ':(3000|8001) '` and explicitly
   stop pre-existing dev processes (record their PIDs in case the user
   wants to restart them later).
2. **Worktree binding**: launch uvicorn from the worktree cwd so
   cwd-import precedence picks up modified package code; venv at project
   root remains usable.
3. **Env**: `set -a && source agent_app/.env && set +a` before uvicorn
   so FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_MODEL are present.
4. **Smoke API**: `curl /api/delegates` to confirm seed data and harvest
   exact full names for use in `wait_for`.
5. **Frontend reuse**: if bug is backend-only, reuse the existing
   localhost:3000 frontend; don't bother with `.env.local` + `npm
   install` in the worktree.
6. **First brief assertion**: `wait_for` with the bare delegate name
   ("Alice Leblanc") not a guessed greeting prefix.
7. **Switch test**: `fill(combobox_uid, "Full Option Text")` re-triggers
   the brief on the new delegate; assert opposite name appears.
8. **Negative assertion**: snapshot should NOT contain previously-leaked
   identity (e.g. "Marie Dupont" when Alice is selected).
9. **Tool-call check**: snapshot the DisclosureTriangle tool-call
   accordion; verify first tool fired is the expected one (`whoami` not
   `lookup_delegate`).
10. **Cleanup**: kill the worktree-launched uvicorn, optionally restart
    main-checkout backend at the original PID command line.
