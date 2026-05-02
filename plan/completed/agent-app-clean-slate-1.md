---
status: Draft
created: 2026-04-28
owner: stephane
goal: Quarantine all artifacts from the failed agent_app attempt so the rebuild starts unbiased. Keep Phase 0 (model selection), Phase 1 (shared layer), Phase 2 (classical app). Keep Microsoft Agent Framework as the agent runtime. Re-decide everything downstream (frontend, HITL, identity threading specifics) in a fresh research phase.
---

# Agent App Clean-Slate Reset

## Scope

Drop all in-repo + in-memory traces of the Phase 3 / 3.5 / 4 / spike attempt that
might steer the rebuild back to the same dead ends (AG-UI + CopilotKit + HITL
replay + multi-turn 400). Preserve forensic copies under `_archived/` (gitignored).

## Constraints

- **Keep**: Microsoft Agent Framework as agent runtime; `gpt-4.1-mini` as model;
  `shared/` data layer; `classical_app/`; Phase 0–2 docs and plans.
- **Drop on disk**: `agent_app/` source tree (entirely).
- **Quarantine, not delete**: failed PRDs, plans, and memory entries → `_archived/`,
  gitignored, retrievable but out of working set.
- **Re-decide**: frontend stack (was AG-UI + CopilotKit), HITL UX (was
  `approval_mode="always_require"` via AG-UI), approver UX (was OQ-9 option B),
  identity threading specifics.

## Step 1 — On-disk archive scaffolding

```bash
mkdir -p docs/_archived/failed-attempt-2026-04
mkdir -p plan/_archived/failed-attempt-2026-04
```

Append to `.gitignore`:
```
_archived/
docs/_archived/
plan/_archived/
```

## Step 2 — Move docs to archive

| From | To |
|---|---|
| `docs/prd-phase3-read-agent.md` | `docs/_archived/failed-attempt-2026-04/` |
| `docs/prd-phase4-write-agent.md` | `docs/_archived/failed-attempt-2026-04/` |
| `docs/visual-verify-chrome-devtools-notes.md` | `docs/_archived/failed-attempt-2026-04/` |

## Step 3 — Move plans to archive

From `plan/completed/`:
- `feature-phase3a-tools-agent-1.md`
- `feature-phase3b-ag-ui-server-1.md`
- `feature-phase3c-copilotkit-frontend-1.md`
- `feature-phase3d-brief-logic-and-tests-1.md`
- `feature-phase3e-copilotkit-e2e-playwright-1.md`
- `feature-phase3-chat-typography-fix-1.md`
- `feature-phase4a-create-write-tools-1.md`
- `feature-phase4b-create-server-prompt-1.md`
- `feature-phase4c-create-frontend-hitl-1.md`
- `feature-phase4c-fix-message-ordering-1.md`
- `feature-phase4d-create-integration-tests-1.md`
- `feature-phase4e-approver-seed-list-tool-1.md`
- `feature-phase4f-approver-write-tools-1.md`
- `feature-phase4g-approver-prompt-brief-badge-1.md`
- `feature-phase4h-approver-integration-tests-1.md`
- `feature-ui-polish-phase4-oecd-1.md`
- `bug-delegate-identity-leak-1.md`
- `bug-phase4c-hitl-orphan-tool-result-1.md`
- `bug-phase4c-hitl-prompt-and-ux-1.md`

From `plan/`:
- `spike-stock-stack-validation-1.md`

All → `plan/_archived/failed-attempt-2026-04/`.

`plan/completed/` retains only Phase 0–2 plans + `prd-phase1-shared-layer-and-classical-read.md` + `feature-e2e-playwright-phase2-demo-1.md`.

## Step 4 — Wipe agent_app source tree

```bash
git rm -r agent_app/
```

Includes `agent.py`, `tools.py`, `middleware.py`, `server.py`, `__init__.py`, `frontend/`. Recreated from scratch in a future phase per new PRD.

## Step 5 — Edit DESIGN.md

- Strip "Current state (2026-04-23)" block (lines ~113–124).
- Replace with: "Current state (2026-04-28): Phase 0 (model selection) + Phase 1 (shared data layer) + Phase 2 (classical app write flows) shipped. `agent_app/` rebuild pending fresh research and PRDs."
- Stack table: change "Agent frontend" row from `Next.js + CopilotKit (AG-UI protocol)` → `TBD — research phase pending`.

## Step 6 — Edit DECISIONS.md

Move to archive (via deletion in main file, copy preserved in archive doc):
- `[2026-04-19] Agent frontend: AG-UI + CopilotKit (OQ-7 resolved)` entry — entire block.
- `[2026-04-24] Phase 4 approver workflow — agent-centric (OQ-9 resolved)` entry — entire block.

Append a new entry at top of decision log:
```
### [2026-04-28] Agent app reset — quarantine failed attempt, re-decide stack

First agent_app implementation (Phase 3/3.5/4 + spikes) abandoned 2026-04-28
after AG-UI + CopilotKit HITL/multi-turn fragility could not be resolved within
the package boundaries. All artifacts moved to `_archived/`. Rebuild starts from
the standing classical app + shared layer + selected model (gpt-4.1-mini).
Microsoft Agent Framework retained as runtime. Frontend stack, HITL UX, and
approver UX are open again — see OQ-7 and OQ-9 (Phase 4 portion).
```

## Step 7 — Edit OPEN_QUESTIONS.md

- **Re-open OQ-7** (agent frontend technology): strike "✓ Resolved (2026-04-19)" + decision body. Replace with: "Re-opened 2026-04-28 after first agent_app attempt. Pending fresh research phase — see `docs/research-agent-stack.md` (TBD)."
- **Re-open OQ-9 Phase 4 portion**: keep Phase 2 status-flag decision; strike Phase 4 agent-centric resolution. Replace with: "Re-opened 2026-04-28. Approver UX TBD pending agent stack decision."

## Step 8 — Edit BACKLOG.md

Truncate everything from `## Phase 3 — Agent App` onward. Replace with:

```
## Phase 3+ — Agent App (rebuild pending)

First attempt abandoned 2026-04-28; artifacts under `_archived/`.

Pre-implementation work required:
- [ ] Research phase — agent frontend stack (`docs/research-agent-stack.md`)
- [ ] Research phase — HITL approach (`docs/research-hitl-approach.md`)
- [ ] New PRD — read agent (UC1, proactive meeting brief)
- [ ] New PRD — write agent (UC2, delegate creation + DAR + approver flow)
- [ ] Implementation plans per phase

## Phase 5 — MCP Knowledge Base
[unchanged]

## Phase 6 — Trust Calibration + Demo
[unchanged]
```

## Step 9 — Memory purge

Move from `~/.claude/projects/-home-stephane-Playground-GenAI-copilot/memory/` to
`~/.claude/projects/-home-stephane-Playground-GenAI-copilot/memory/_archived/`:

**Project status (failed attempt):**
- `project_delegate_identity_leak_bug.md`
- `project_e2e_agent_timeout_root_cause.md`
- `project_finding_4c_007.md`
- `project_oq9_phase4_approver.md`
- `project_phase3a_status.md`
- `project_phase3_status.md`
- `project_phase3_plans.md`
- `project_phase3_typography_fix.md`
- `project_phase4a_status.md`
- `project_phase4b_status.md`
- `project_phase4c_status.md`
- `project_phase4_plans.md`
- `project_phase4_ui_polish.md`
- `project_phase4_spike_pivot.md`
- `project_spike01_pass.md`
- `project_spike01_multiturn_blocker.md`
- `project_spike02_partial.md`

**References (stack-specific to failed attempt):**
- `reference_agui_hitl_sse_shape.md`
- `reference_ag_ui_integration.md`
- `reference_copilotkit_hitl_finding.md`
- `reference_copilotkit_known_log_noise.md`
- `reference_copilotkit_v2_css_vars.md`
- `reference_copilotkit_v2_migration.md`
- `reference_copilotkit_v2_useagent_signature.md`
- `reference_forwarded_props_stringified.md`
- `reference_function_invocation_context.md`
- `reference_phase3b_server_pattern.md`
- `reference_streamdown_dom_structure.md`
- `reference_sqlite_fastapi_threading.md`
- `reference_turbopack_worktree_symlink.md`
- `reference_upstream_pr_4946.md`
- `reference_worktree_dev_stack_bootstrap.md`
- `reference_visual_verify_chrome_devtools.md`
- `reference_agent_app_startup.md`

**Feedback (stack-specific):**
- `feedback_context7_for_preview_libs.md`
- `feedback_copilotkit_agent_brief_trigger.md`
- `feedback_agent_tool_testing.md`
- `feedback_invisible_identity_tool_param.md`

**Keep (framework- or classical-app-level, not poisoned):**
- All `feedback_*` for ruff/jinja/wtforms/pytest/jcodemunch/subagent/worktree/python-coder/test-quality
- `reference_agent_framework_docs.md` (framework still in stack)
- `reference_foundry_model_config.md` (model still selected; env var still load-bearing)
- `reference_db_reset.md`, `reference_email_validator_dep.md`, `reference_flask_auth_session.md`,
  `reference_hplip_port8000.md`, `reference_jcodemunch_index.md`, `reference_mempalace_*`,
  `reference_phase2b_permissions_pattern.md`, `reference_plan_subagent_readonly.md`,
  `reference_playwright_cli.md`, `reference_schema_pitfalls.md`, `reference_visual_verify_skill.md`
- All `project_phase1*` and `project_phase2*` status entries
- `project_e2e_playwright_suite.md` (classical-app e2e)
- `project_mempalace_architecture_decision.md`

After move, edit `MEMORY.md`: drop every line whose target file moved to `_archived/`.
Add a single index entry: `- [Failed agent_app attempt](../memory/_archived/) — Phase 3/4/spike artifacts quarantined 2026-04-28; consult only with explicit user request.`

## Step 10 — Verification

- `git status` — confirm only the intended deletes/edits.
- `tree -L 2 docs plan` — confirm archive scaffolding correct.
- `pytest tests/shared tests/classical_app` — must still be green (Phase 1 + 2 tests untouched).
- Spot-check `MEMORY.md` — no dangling links to archived files.

## Step 11 — Commit

Single commit, message:
```
chore: reset agent_app — quarantine failed Phase 3/4 attempt

- Move failed PRDs, plans, and memory entries to _archived/ (gitignored)
- Wipe agent_app/ source tree (rebuild from new PRDs)
- Re-open OQ-7 (frontend stack) and OQ-9 Phase 4 (approver UX)
- Truncate BACKLOG Phase 3+ to research/PRD prerequisites
- Keep: shared/, classical_app/, Phase 0 model selection, MS Agent Framework
```

## Out of scope (future work)

- Drafting `docs/research-agent-stack.md` (separate session, no prior-attempt evidence cited).
- Drafting `docs/research-hitl-approach.md`.
- New `prd-phase3-*.md` and `prd-phase4-*.md` after research lands.
- New implementation plans per phase.
