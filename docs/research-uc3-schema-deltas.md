# Research — UC3 Schema Deltas (Approver Inbox)

> **Status:** Proposal (2026-05-02) · **Owner:** stephane.varin@gmail.com
> **Scope:** Three additive schema deltas required by `docs/prd-uc3-approver-inbox.md`
> §4 (TBD-SCHEMA-1, -2, -3). Review material — not implementation.
> **Targets (do NOT edit until plan is opened):** `shared/database.py`,
> `shared/seed_data.py`.
> **Cross-links:** OQ-1 (full RBAC, open) · OQ-9 Phase 4 (resolved 2026-05-01).

---

## 0. Conflict surfaced before recommendations

The task brief and the UC3 PRD disagree on **secretariat scope**:

- **Task brief:** "secretariat ... sees both `PENDING_DELEGATION_HEAD` and
  `PENDING_SECRETARIAT` rows."
- **PRD §3 `_dar_in_scope`:** secretariat sees **only**
  `PENDING_SECRETARIAT`. Delegation-head approval is the head's exclusive
  scope; secretariat handles the orthogonal CONFIDENTIAL / retroactive
  bucket per `shared.business_rules.determine_approval_route`.

This proposal follows the **PRD** (it declares itself authoritative).
Listed as a sign-off question in Delta 1 — narrow vs. union scope changes
the seeding plan and the helper's predicate but not the column shape.

---

## Delta 1 — Approver role(s)

### Current state

`shared/database.py` line 116:

```python
class DelegateRole(Enum):
    DELEGATE = "DELEGATE"
    DELEGATION_EDITOR = "DELEGATION_EDITOR"
```

Stored as `SQLEnum(DelegateRole, native_enum=False)` — i.e. as a `VARCHAR`
in SQLite, not a CHECK-constrained native enum. **Adding new values is
purely additive** — no migration script, no DDL change beyond the seed
rebuild path documented in `reference_db_reset.md`.

### Proposal A — Extend the enum (recommended for PoC)

```python
class DelegateRole(Enum):
    """Enumeration of delegate role types.

    Roles a delegate can have within (or across) delegations:
        DELEGATE: Standard delegate with basic privileges.
        DELEGATION_EDITOR: Delegate with delegation management privileges
            (UC2: create delegates, assign committees, request access).
        DELEGATION_HEAD: Approver for own-delegation DARs in
            PENDING_DELEGATION_HEAD state (UC3).
        SECRETARIAT: Approver for cross-delegation DARs in
            PENDING_SECRETARIAT state — CONFIDENTIAL or retroactive
            requests. Membership is global (see seed convention below).
    """

    DELEGATE = "DELEGATE"
    DELEGATION_EDITOR = "DELEGATION_EDITOR"
    DELEGATION_HEAD = "DELEGATION_HEAD"
    SECRETARIAT = "SECRETARIAT"
```

**Migration shape:** purely additive. `SQLEnum(..., native_enum=False)`
stores `VARCHAR`, so new values are valid the moment the Python enum
ships; existing rows untouched. SQLite dev DB rebuilt from seed per
`reference_db_reset.md`. No Alembic.

**Permission helper** mirrors `classical_app/permissions.py::is_editor_of`.
Single source of truth for the scope predicate (matches PRD §3) — both
the agent tools and any future Flask page consume it:

```python
# shared/business_rules.py (new helpers)

def is_approver_for_dar(
    db_session: Session,
    delegate_id: str,
    dar: DocumentAccessRight,
) -> bool:
    """Return True iff `delegate_id` may approve/reject `dar` per UC3
    scope rules. Mirrors PRD §3 `_dar_in_scope`."""
    approver = db_session.get(Delegate, delegate_id)
    if approver is None or not approver.is_active:
        return False
    if approver.role == DelegateRole.SECRETARIAT:
        return dar.approval_status == ApprovalStatus.PENDING_SECRETARIAT
    if approver.role == DelegateRole.DELEGATION_HEAD:
        return (
            dar.approval_status == ApprovalStatus.PENDING_DELEGATION_HEAD
            and dar.delegate.delegation_id == approver.delegation_id
        )
    return False
```

UC3 tools wrap this; `agent_app/tools/uc3_approver.py` reloads the
approver record per call (PRD §4 "reload from SQLite each call").

### Proposal B — Separate `Approver` table (production path, defer)

New `approvers` table: `(id, delegate_id FK, scope_kind, delegation_id
FK nullable, granted_at, granted_by)`. `scope_kind` ∈
{`DELEGATION_HEAD`, `SECRETARIAT`}; nullable `delegation_id` lets
`SECRETARIAT` rows be global while `DELEGATION_HEAD` rows scope to
one delegation. Decouples approver role from `Delegate`, allows
multiple approver hats per delegate, supports a future
`(scope_kind, delegation_id, committee_id)` matrix when OQ-1 lands.
Heavier: new table, new joins in every UC3 query, new seed fixture,
new permission-helper shape. Delta 2's audit columns still FK to
`delegates.id` regardless of A or B.

### Recommendation

**Proposal A.** Reasons:

1. **PoC remit.** OQ-1 is explicitly open. Designing production RBAC
   now is premature; existing `Delegate.role` already carries
   `DELEGATION_EDITOR` — adding approver roles continues the pattern.
2. **Minimal surface.** No new table, no new join in
   `list_pending_dars`. PRD §3 `_dar_in_scope` reads `approver.role`
   directly → predicate is one line.
3. **Reversible.** When OQ-1 lands, an `Approver` table can subsume
   the enum: each value maps to a row, migration is forward-only.

### Secretariat membership — global vs per-delegation

**Recommendation: secretariat is global.** A `SECRETARIAT` delegate's
`delegation_id` points at a sentinel **`OECD`** delegation (does not
exist today — must be added by Delta 3). The scope predicate ignores
`approver.delegation_id` for `SECRETARIAT` rows; only the role flag
gates access.

`shared/business_rules.determine_approval_route` already routes
CONFIDENTIAL / retroactive to `PENDING_SECRETARIAT` regardless of the
target delegate's delegation, so per-delegation secretariat scope would
be inconsistent with the routing rule. The phrase "pending OECD
secretariat approval" is already used in
`classical_app/routes/wizard_helpers.py` line 45 — `OECD` as the
sentinel home delegation matches the existing language without
introducing a new concept.

### Acceptance for sign-off

- **Q1.1** Confirm Proposal A (enum extension) over Proposal B
  (separate `Approver` table) for the PoC.
- **Q1.2** Confirm secretariat scope = `PENDING_SECRETARIAT` only
  (PRD §3) and NOT the union `{PENDING_DELEGATION_HEAD ∪
  PENDING_SECRETARIAT}` (task brief). This determines whether Delta 3
  needs `DELEGATION_HEAD` rows at all in delegations beyond FRA.
- **Q1.3** Confirm secretariat membership is global (one sentinel
  `OECD` delegation) — not per-delegation.

---

## Delta 2 — DAR audit columns

### Current state

`shared/database.py::DocumentAccessRight` (lines 334–381) has
`approval_status`, `created_at`, `created_by` only. No record of
**who** acted, **when**, or **why** — the PRD's AC-3 / AC-4 / AC-7
require all three on every approve/reject.

### Proposed columns (additive, all nullable)

```python
class DocumentAccessRight(Base):
    # ... existing columns unchanged ...

    # --- UC3 audit columns (added by TBD-SCHEMA-2) ---
    approved_by = Column(
        String,
        ForeignKey("delegates.id"),
        nullable=True,
    )
    approved_at = Column(DateTime, nullable=True)
    rejected_by = Column(
        String,
        ForeignKey("delegates.id"),
        nullable=True,
    )
    rejected_at = Column(DateTime, nullable=True)
    decision_comment = Column(String, nullable=True)
```

**Why one column (`decision_comment`), not two (`comment` + `reason`):**
The PRD §4 lists `comment` and `reason` separately, but the semantics
are identical free-text decision narrative — optional on approve,
required on reject. The required-on-reject rule is **already** a
tool-layer guard (`reject_dar` raises `ValueError("reason_required")`
on empty `reason.strip()`); pushing it into the DB schema as a CHECK
or split column duplicates the guard for no test gain. Single column
also gives `get_dar_details` a single field to render. **Recommendation:
single `decision_comment`.** Listed as Q2.2.

### Datatype: naive UTC `DateTime`

Match the existing pattern. `DocumentAccessRight.created_at`,
`Document.publication_date`, `Meeting.date` all use
`Column(DateTime, ...)` with no `timezone=True`. The codebase already
has the convention `datetime.now(timezone.utc).replace(tzinfo=None)`
(`shared/business_rules.py` line ~50) — UTC truth, naive storage.
Switching `_at` columns to `DateTime(timezone=True)` would mix shapes
and surprise the test fixtures that compare datetimes literally.

### FK back to `Delegate`

`approved_by` / `rejected_by` are FKs into `delegates.id` (`String`).
Permits an eager-load join so `get_dar_details` can render the
approver's full name. No cascade — deleted approver must not erase
audit history (production: `ondelete="RESTRICT"`; SQLite PoC default).

### Why columns, not "audit middleware log only"

The PRD already mandates a middleware log line per call (AC-7), but
that log is append-only and external — fine for forensic
reconstruction, useless for `get_dar_details` which must surface the
decision *inline* with the DAR ("approved by Marie Dupont on
2026-05-04, comment: 'looks fine'"). Columns also let
`list_pending_dars` filter cleanly and let integration tests assert
state without parsing log lines. **Columns + middleware log
together** — neither alone.

### Acceptance for sign-off

- **Q2.1** Confirm five new columns: `approved_by` (FK→delegates),
  `approved_at`, `rejected_by` (FK→delegates), `rejected_at`,
  `decision_comment`. All nullable.
- **Q2.2** Confirm single `decision_comment` over split
  `comment` + `reason`. Required-on-reject stays a tool-layer guard.
- **Q2.3** Confirm naive UTC `DateTime` (match existing convention)
  over `DateTime(timezone=True)`.
- **Q2.4** Confirm columns AND middleware log (not log-only).

---

## Delta 3 — Seed extension

### Goal

Minimum delta that makes the UC3 demo work:
- 1 sentinel **`OECD`** delegation (does not exist today).
- 1 `DELEGATION_HEAD` persona in **FRA** (the demo head).
- 1 `SECRETARIAT` persona in `OECD`.
- 4 pending DARs covering both `PENDING_DELEGATION_HEAD` and
  `PENDING_SECRETARIAT`, spanning at least two delegations.

### Sentinel `OECD` delegation

Current `MembershipType` enum has only `MEMBER` and `PARTNER`. Neither
literally describes the secretariat. **Pick `MEMBER`** (least-wrong:
secretariat is closer to a full-rights actor than a partner) and flag
as sign-off question — do **not** silently extend `MembershipType`.

Idempotent seeding follows the existing `session.merge()` pattern in
`seed_delegations` / `seed_target_delegations`.

```python
# shared/seed_data.py — extension to seed_delegations
session.merge(
    Delegation(
        id="OECD",
        name="OECD Secretariat",
        membership_type=MembershipType.MEMBER,
    ),
)
```

### Persona seed delta

Existing convention: delegate IDs are `DEL-2026-NNNN` (zero-padded
4-digit suffix), max id today is `DEL-2026-0009`. The PRD's draft
suggested `DEL-2026-HEAD-FRA` / `DEL-2026-SEC-001` — these break the
format. **Recommendation: keep the format**, document the role in the
`function` field. (Q3.1.)

DEL-2026-0001 (Marie Dupont, FRA) is currently `DELEGATION_EDITOR`.
**Do not repurpose her** — UC2 tests rely on her role. Add a fresh
delegate as the FRA head.

```python
# shared/seed_data.py — extension to seed_delegates.delegates_data
{
    "id": "DEL-2026-0010",
    "full_name": "Élise Bernard",
    "email": "e.bernard@fra.example",
    "function": "Head of Delegation (Approver)",
    "title": "Ambassador",
    "delegation_id": "FRA",
    "accreditation_date": datetime(2026, 1, 5),
    "last_login": datetime(2026, 4, 28),
    "role": DelegateRole.DELEGATION_HEAD,
    "committees": ["EDU", "TRADE", "DAC", "ENV", "SKILLS"],
},
{
    "id": "DEL-2026-0011",
    "full_name": "Henrik Larsson",
    "email": "h.larsson@oecd.example",
    "function": "Senior Secretariat Officer",
    "title": None,
    "delegation_id": "OECD",
    "accreditation_date": datetime(2026, 1, 1),
    "last_login": datetime(2026, 4, 30),
    "role": DelegateRole.SECRETARIAT,
    "committees": ["EDU", "TRADE", "DAC", "ENV", "SKILLS"],
},
```

Names follow the existing OECD-flavoured roster (Marie Dupont, Hans
Mueller, Carlos Silva, Priya Sharma — European + global mix).
`accreditation_date` for both is earlier than any existing delegate,
modelling pre-existing institutional roles.

### Pending DAR seed delta

Existing DAR rows assume one logical DAR per `(delegate_id,
committee_id)` (no DB unique constraint, but the seed honours it).
Combos picked to avoid collisions and to span both pending statuses
plus both delegations: Jean Martin (FRA) → DAC head-pending; Sophie
Weber (DEU) → ENV head-pending; Ana Souza (BRA) → TRADE
secretariat-pending via CONFIDENTIAL; Raj Patel (IND) → ENV
secretariat-pending via `retroactive=True` (forces
`PENDING_SECRETARIAT` per `determine_approval_route`). Max existing
DAR id = 24; new ids start at 25.

```python
# shared/seed_data.py — extension to seed_document_access_rights.dar_data
# Pending rows for UC3 approver inbox (TBD-SCHEMA-3):
(25, "DEL-2026-0002", "DAC", ClassificationLevel.RESTRICTED,
 ApprovalStatus.PENDING_DELEGATION_HEAD),
(26, "DEL-2026-0009", "ENV", ClassificationLevel.RESTRICTED,
 ApprovalStatus.PENDING_DELEGATION_HEAD),
(27, "DEL-2026-0006", "TRADE", ClassificationLevel.CONFIDENTIAL,
 ApprovalStatus.PENDING_SECRETARIAT),
(28, "DEL-2026-0008", "ENV", ClassificationLevel.RESTRICTED,
 ApprovalStatus.PENDING_SECRETARIAT),  # retroactive=True; see below
```

Row 28 needs `retroactive=True`; the existing seed loop hard-codes
`retroactive=False`, so the implementation plan must extend the tuple
shape OR split rows 25–28 into a second loop. (Q3.3.)

### Coverage check (matches PRD K2 / AC-5)

- Two delegations with delegation-head pending: FRA (row 25), DEU
  (row 26). Lets the FRA head test cross-delegation refusal: she sees
  row 25 only; row 26 returns `PermissionError("out_of_scope")`.
- Two pending secretariat rows: BRA (row 27, CONFIDENTIAL), IND (row 28,
  retroactive). Lets the secretariat persona action both.
- Empty queue exercised by logging in as the DEU head (none seeded) →
  PRD AC-1 *"No pending approvals in your queue."* — but no DEU head
  exists yet, so empty-queue is exercised by approving the FRA pending
  row first (state machine), or by adding a second head persona later
  (defer; flagged Q3.4).

### Idempotency

All three additions follow the pre-existing `session.merge()` patterns:
- `OECD` delegation merges by string PK.
- New delegates merge by string PK; committees pre-loaded then assigned
  before merge (matches `seed_delegates` lines 244–250).
- New DARs merge by integer PK (`id=25..28`).

Re-running `seed_all` is safe.

### Acceptance for sign-off

- **Q3.1** Confirm delegate ID format `DEL-2026-NNNN` (numeric) over
  PRD's draft suggestion `DEL-2026-HEAD-FRA` / `DEL-2026-SEC-001`.
- **Q3.2** Confirm `OECD` sentinel delegation with
  `MembershipType.MEMBER` (least-wrong of the existing two values).
  Alternative: extend `MembershipType` with a `SECRETARIAT` value —
  out of scope for Delta 1 but call it out if preferred.
- **Q3.3** Confirm one pending DAR uses `retroactive=True` to exercise
  the secretariat-via-retroactive path; this requires extending the
  tuple shape in `seed_document_access_rights`.
- **Q3.4** Confirm 4 pending DARs is sufficient for the demo, or
  request a second `DELEGATION_HEAD` persona (e.g. for DEU) to make
  the empty-queue case demonstrable without first acting on a row.
- **Q3.5** Confirm persona names (Élise Bernard for FRA head, Henrik
  Larsson for secretariat) — domain-realistic, OECD-flavoured per
  OQ-8's resolution.

---

## Summary table — delta surface

| Delta | Lines touched (estimate) | New columns | New rows | Test impact |
|---|---|---|---|---|
| 1 — `DelegateRole` enum | 2 in `database.py`; ~25 for permission helper in `business_rules.py` | 0 | 0 | New unit tests for `is_approver_for_dar` (mirror `test_permissions.py`); existing `is_editor_of` tests untouched |
| 2 — DAR audit columns | ~10 in `database.py` (`DocumentAccessRight`) | 5 | 0 | New columns asserted in UC3 tool-layer tests; existing classical-app DAR tests do not read these columns |
| 3 — Seed extension | ~30 in `seed_data.py` | 0 | 1 delegation, 2 delegates, 4 DARs | Existing seed counts shift (expect 5 delegations, 11 delegates, 28 DARs); count-asserting tests need updates |

**Combined risk:** all changes are additive. SQLite dev DB is rebuilt
from seed (`reference_db_reset.md`); no Alembic. The only existing-test
breakage vector is hard-coded entity counts in
`tests/classical_app/conftest.py` and similar — the implementation
plan should grep for `query(...).count()` assertions before merge.

---

## Cross-links

- `docs/prd-uc3-approver-inbox.md` §4 (TBD-SCHEMA-1/2/3) — this is the response.
- `docs/OPEN_QUESTIONS.md` OQ-1 (full RBAC, open) — Proposal B is the production landing.
- `docs/OPEN_QUESTIONS.md` OQ-9 Phase 4 (resolved 2026-05-01) — fixes UC3 to async-queue.
- `plan/phase3-agent-app-scaffold-1.md` §3 — UC3 blocks on these deltas; merge order: schema-delta plan → UC3 plan.
- `shared/business_rules.py::determine_approval_route` — routing rule the scope predicate must mirror.
- `classical_app/permissions.py::is_editor_of` — reference shape for `is_approver_for_dar`.
- `reference_db_reset.md` — DB rebuild path (no Alembic).
- `reference_schema_pitfalls.md` — `compute_default_access_level` never returns CONFIDENTIAL, so seed row 27's CONFIDENTIAL is a hand-authored exception (not rules-derived); call out in the implementation plan.
