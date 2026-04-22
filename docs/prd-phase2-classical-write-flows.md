# PRD — Phase 2: Classical App (Write Flows)

**Status**: Draft
**Owner**: Stephane
**Target phase**: Phase 2 (per `docs/BACKLOG.md`)
**Depends on**: Phase 1 (shared data layer + classical read flows, completed 2026-04-12)
**Blocks**: Phase 6 (side-by-side demo)

---

## 1. Executive Summary

### Problem Statement
The classical Flask app today only exposes read screens (Phase 1). To make the
agent-vs-forms contrast credible for the UC2 demo, we need the *status-quo*
write flow — the 8-screen delegate-creation wizard that the agent compresses
into ~3 conversational turns. Without it, there is nothing concrete to compare
the agent against.

### Proposed Solution
Build the complete classical write path: delegation list → delegation detail →
4-step "Add Delegate" wizard → confirmation. All writes go through the existing
`shared/business_rules.py` (single source of truth). Pending approvals are
recorded as DAR status flags only; the actual approver workflow is Phase 4.

### Success Criteria
1. A delegation editor can create a new delegate with DARs covering ≥ 2
   committees, in ≤ 8 screens, without the application crashing or producing
   invalid data.
2. 100% of DAR records created by the wizard route through
   `compute_default_access_level` and `determine_approval_route` — no
   wizard-local business logic.
3. All three approval routes are demo-reachable and visible on the confirmation
   screen: `approved`, `pending_delegation_head`, `pending_secretariat`.
4. Seed data exposes ≥ 1 delegation-editor persona per delegation (member +
   partner + partner-with-FA) — selectable from the existing delegate picker.
5. Test suite: ≥ 25 new tests covering wizard state, business-rule wiring,
   permission gating, and all three approval routes. Full project suite
   (Phase 1A + 1B + 2) remains green.

---

## 2. User Experience & Functionality

### User Personas

| Persona | Role | Access |
|---|---|---|
| **Delegation editor** (new) | Administrative user within a delegation; manages delegates | Read all Phase 1 screens + full write wizard for their own delegation |
| **Regular delegate** (existing) | Participates in committees; consumes documents | Read-only (Phase 1 screens only); blocked from write screens with 403 |
| **OECD secretariat** | Approves Confidential / retroactive DARs | Out of scope — Phase 4 |
| **Delegation head** | Approves Restricted DARs | Out of scope — Phase 4 |

Persona is encoded as a `role` field on the existing `Delegate` model
(values: `delegate`, `delegation_editor`). The delegate picker surfaces both
roles — editors are visually distinguished (badge or icon) so the demo audience
can see the role switch. The picker drives the session; no separate login.

### User Stories

**US-1 — Browse delegations**
> As a delegation editor, I want to see the list of delegations and drill into
> my own, so I can find the delegate roster I need to edit.

**AC:**
- `/delegations` shows a table: Name, Type (Member/Partner), Delegate count, Framework Agreements count.
- Clicking a row opens `/delegations/<id>`.
- Accessible to any logged-in persona (read-only listing).

**US-2 — View a delegation's delegate roster**
> As a delegation editor, I want to see all delegates in my delegation with
> their committees and a button to add new ones.

**AC:**
- `/delegations/<id>` shows delegation metadata (name, type, FAs) and a delegate table (name, email, function, committee count).
- "Add New Delegate" button visible only when the logged-in persona is a
  `delegation_editor` *of this delegation*. Otherwise hidden.
- Direct POST to the wizard from a non-editor returns **403**.

**US-3 — Create delegate (wizard, 4 steps)**
> As a delegation editor, I want a guided 4-step wizard to create a delegate
> with committee participations and DARs, so I don't miss required fields.

**AC:**
- **Step 1 (Personal Info)**: full name, email, function, title (optional).
  Email format validated; email uniqueness within delegation enforced on submit.
- **Step 2 (Committee Participations)**: multi-select checkbox list of all
  committees. At least 1 must be selected.
- **Step 3 (Document Access Rights)**: one row per selected committee with
  columns `Committee | Access Level | Retro?`. Access-level dropdown options
  are *restricted by membership type* (member → General/Restricted/Confidential;
  partner → General, or Restricted if a Framework Agreement covers the
  committee; Confidential always selectable but flagged as requiring secretariat
  approval). `Retro?` is a boolean checkbox.
- **Step 4 (Review & Submit)**: shows all entered data + the *computed*
  approval routing per DAR (e.g. "Education Policy — Restricted (pending
  delegation head approval)"). Approval text comes from
  `determine_approval_route`, not from wizard-local logic.
- On submit: one DB transaction creates the `Delegate`, the
  `MembershipParticipation` rows, and the `DAR` rows. If any write fails, the
  whole transaction rolls back and the user returns to Step 4 with a flash
  error.
- **Back** from any step preserves all prior-step data (server-side Flask
  session, scoped to this wizard only).
- **Cancel** at any step clears the wizard session and returns to the
  delegation detail page.

**US-4 — See confirmation with pending approvals**
> As a delegation editor, I want a confirmation screen that shows exactly which
> DARs are auto-approved vs pending, so I know what still needs action.

**AC:**
- `/delegations/<id>/delegates/new/confirmation` shows:
  - Newly created delegate ID and name.
  - One bullet per created DAR: `<committee> — <level> [+ retroactive] (<status>)`.
  - Status strings: `auto-approved`, `pending delegation head approval`, `pending OECD secretariat approval`.
- Two action buttons: "Back to Delegation" (→ US-2) and "Add Another Delegate"
  (→ Step 1, same delegation context).

**US-5 — Approval routing (the three demo paths)**

The wizard must produce all three routes during a single demo run, driven by
seed data + editor choices:

| Scenario | Access Level | Retro? | Expected route |
|---|---|---|---|
| Member + General | General | no | `approved` (auto) |
| Member + Restricted | Restricted | no | `pending_delegation_head` |
| Member + Confidential | Confidential | no | `pending_secretariat` |
| Partner (no FA) + General | General | no | `approved` (auto) |
| Partner (with FA) + Restricted | Restricted | no | `pending_delegation_head` |
| Any + Retroactive | any | yes | `pending_secretariat` |

### Non-Goals

- **No approver UI.** No screens for delegation heads or secretariat to
  approve/reject pending DARs. Pending rows sit in the DB with their status
  flag; Phase 4 consumes them.
- **No delegate edit / deactivate / delete.** Wizard creates only.
- **No email/notification** on pending approvals.
- **No bulk import** of delegates.
- **No cross-delegation editing.** A `delegation_editor` can only edit their
  own delegation (enforced by 403).
- **No audit log UI.** Existing `created_at` / `created_by` columns are enough;
  a log-viewer screen is out of scope.
- **No client-side wizard state.** Server-side Flask session only.
- **No agent.** This phase is the classical contrast tool; the agent UC2 is
  Phase 4.

---

## 3. Technical Specifications

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ classical_app/ (Flask)                                   │
│                                                          │
│  routes/                                                 │
│    delegations.py  — GET /delegations, /delegations/<id> │
│    wizard.py       — GET+POST /.../delegates/new/step{1..4}│
│                      GET /.../delegates/new/confirmation│
│                                                          │
│  forms/                                                  │
│    delegate_wizard.py  — 4 WTForms classes + validators │
│                                                          │
│  templates/                                              │
│    delegation_list.html, delegation_detail.html         │
│    wizard/step1..step4.html, wizard/confirmation.html   │
│                                                          │
│  permissions.py  — @editor_of_delegation_required       │
│                                                          │
└──────────────────────────┬──────────────────────────────┘
                           ▼
              ┌────────────────────────┐
              │ shared/ (Phase 1)      │
              │   business_rules.py    │
              │   database.py          │
              │   seed_data.py (+Φ2)   │
              └────────────────────────┘
```

### Data-model changes

Additive only — no renames, no breaking migrations:

1. **`Delegate.role`** — new `Enum('delegate', 'delegation_editor')` column.
   Default `'delegate'`. Nullable=False with server default so Phase 1 rows
   migrate cleanly.
2. **`DocumentAccessRight.retroactive`** — new `Boolean` column, default
   `False`, nullable=False.
3. **`ApprovalStatus` enum** — confirm values exist from Phase 1; expected set
   is `{approved, pending_delegation_head, pending_secretariat}`. If Phase 1
   used different names, align before proceeding (do not fork).

### Wizard state

- Stored in `flask.session['delegate_wizard']` as a dict keyed by delegation id
  to allow concurrent wizards in different tabs: `{delegation_id: {step1: {...}, step2: {...}, step3: {...}}}`.
- Cleared on cancel, on successful submit, and on a TTL of 30 minutes (soft).
- The POST handler for Step N only renders Step N+1 if Steps 1..N pass
  validation against the stored state. A user navigating directly to
  `/step3` without data in session is redirected to `/step1`.

### Business-rule integration (no duplication)

Every DAR row created by Step 4 submit must go through:

```python
level = validated_form_level  # already restricted by membership type in UI
approval = determine_approval_route(
    delegate=delegate,
    committee=committee,
    access_level=level,
    retroactive=row.retroactive,
)
dar = DocumentAccessRight(
    delegate_id=delegate.id,
    committee_id=committee.id,
    access_level=level,
    retroactive=row.retroactive,
    approval_status=approval,
)
```

The default-level dropdown uses `compute_default_access_level` to *preselect*
the level per committee, but the user can override within the allowed set.

### Seed data additions (`shared/seed_data.py`)

Incremental — must not rebuild Phase 1 data:

- Add `role='delegation_editor'` to **1 delegate per delegation** (member,
  partner-no-FA, partner-with-FA). Keep their names domain-realistic.
- Add **2–3 empty "target" delegations** the editor can add delegates into
  during a live demo, so the demo doesn't mutate the Phase 1 read fixtures.
- Idempotent: re-running the seeder must not duplicate these rows.

### Permissions / 403 gating

- `@editor_of_delegation_required(delegation_id)` decorator on all wizard
  routes and POST handlers.
- Reads (`/delegations`, `/delegations/<id>`) remain accessible to any
  impersonation — the "Add Delegate" button is simply hidden for non-editors.
- 403 page template reuses the Phase 1 403 (document insufficient-DAR) style.

### Security & Privacy
- Delegate PII (name, email) is already in Phase 1 seed data. No new data
  categories introduced.
- CSRF tokens on all POST handlers (Flask-WTF default).
- Email format + uniqueness validated server-side — never trust client.
- No external services called; PoC remains air-gapped.

---

## 4. Risks & Roadmap

### Phased rollout (within Phase 2)

| Sub-phase | Deliverable | Exit criterion |
|---|---|---|
| **2A — schema + seed** | `role`, `retroactive` columns, seed editors | Migrations apply on fresh DB and on Phase 1 DB; ≥ 3 editors visible in picker |
| **2B — read pages** | `/delegations`, `/delegations/<id>` | Both pages render; "Add Delegate" visibility gated correctly |
| **2C — wizard** | 4 steps + confirmation, full business-rule wiring | All 3 approval routes demonstrable end-to-end; all ACs pass |
| **2D — tests + smoke** | Unit + integration tests; manual demo dry-run | Full suite green; golden-path demo script runs without intervention |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `ApprovalStatus` enum values differ from Phase 1 | Medium | Medium | Verify in Phase 2A; align names before schema migration |
| `Delegate.role` migration breaks existing 102 Phase 1 tests | Low | High | Server default on the new column; run Phase 1 suite before touching wizard code |
| Wizard session state leaks between tabs / delegations | Medium | Low | Key by `delegation_id`; TTL eviction; explicit "cancel" path |
| Retroactive-flag business-rule gap (rule not yet in `determine_approval_route`) | Low | High | Verify in Phase 2A — if absent, extend the rule (tested) *before* wizard consumes it |
| Phase 4 agent needs a different `role` model (e.g. multi-role) | Low | Medium | Role is a single enum now; widening to an M2M later is a small migration |

### Open questions carried into Phase 2

- **OQ-9** (delegation head approval workflow): Phase 2 answer is "status flag
  only, no approver UI." Phase 4 must still decide the full UX.
- **OQ-1** (full RBAC model): deferred — Phase 2 uses a 2-value enum; full
  model is post-PoC.

---

## Acceptance — "Phase 2 is done" checklist

- [ ] `Delegate.role` + `DocumentAccessRight.retroactive` columns merged to main.
- [ ] Seed script produces ≥ 1 editor per seeded delegation, idempotent.
- [ ] `/delegations` and `/delegations/<id>` render for all personas.
- [ ] Add-Delegate button hidden for non-editors, 403 for direct POST.
- [ ] 4-step wizard completes end-to-end with back/cancel working.
- [ ] All 3 approval routes reachable and shown on the confirmation screen.
- [ ] Retroactive checkbox routes to `pending_secretariat` regardless of level.
- [ ] All DAR creation goes through `determine_approval_route` — verified by test.
- [ ] New tests ≥ 25; full project suite green (Phase 1A + 1B + 2).
- [ ] BACKLOG.md Phase 2 items checked off with completion date.
- [ ] DESIGN.md "Current state" note updated.
