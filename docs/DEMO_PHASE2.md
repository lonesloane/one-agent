# Phase 2 — Golden-Path Demo Dry-Run

Manual walkthrough of the ONE-MP classical write flows: picker → delegation
detail → add-delegate wizard (Steps 1–4) → confirmation. Covers all three
approval routes and one retroactive scenario.

---

## Prerequisites

### 1. Environment

```bash
cd /path/to/copilot
source .venv/bin/activate
```

### 2. Fresh database with seed data

```bash
# Reset to a clean seeded state
flask --app classical_app.app db-reset   # drops + recreates tables
flask --app classical_app.app seed-data  # loads Phase 2 seed
```

> If `db-reset` / `seed-data` CLI commands are not wired, run directly:
>
> ```python
> from shared.database import Base, engine
> from shared.seed_data import seed_all
> from sqlalchemy.orm import sessionmaker
>
> Base.metadata.drop_all(engine)
> Base.metadata.create_all(engine)
> session = sessionmaker(bind=engine)()
> seed_all(session)
> session.commit()
> ```

### 3. Start the dev server

```bash
flask --app classical_app.app run --debug
```

Server listens on <http://127.0.0.1:5000>.

### 4. Seed personas (reference)

| ID | Name | Role | Delegation |
|----|------|------|------------|
| DEL-2026-0001 | Marie Dupont | `DELEGATION_EDITOR` | FRA (France) |
| DEL-2026-0002 | Jean Martin | `DELEGATE` | FRA |
| DEL-2026-0005 | Carlos Silva | `DELEGATION_EDITOR` | BRA (Brazil) |
| DEL-2026-0007 | Priya Sharma | `DELEGATION_EDITOR` | IND (India) |

Target delegations (no editor assigned — safe to add delegates):
`TGT-ALPHA` (MEMBER), `TGT-BETA` (PARTNER), `TGT-GAMMA` (PARTNER).

Committees: `EDU`, `TRADE`, `DAC`, `ENV`, `SKILLS`.

---

## Scenario A — AUTO_APPROVED (GENERAL, non-retroactive)

**Actor:** Marie Dupont (`DEL-2026-0001`) — editor of FRA.

### A-1. Open delegation picker

1. Navigate to <http://127.0.0.1:5000/delegations>.
2. Verify the delegation list renders (FRA, DEU, BRA, IND, TGT-ALPHA, …).

### A-2. Open FRA detail and find the "Add New Delegate" button

1. Click **France (FRA)** or navigate to
   <http://127.0.0.1:5000/delegations/FRA>.
2. In the session cookie / login fixture set `current_user = DEL-2026-0001`.
3. Confirm the **Add New Delegate** link is visible
   (`/delegations/FRA/delegates/new/step1`).

   > The button is guarded by `is_editor_of_delegation(delegation.id)`.
   > It must **not** appear for Jean Martin (`DEL-2026-0002`).

### A-3. Step 1 — Personal details

1. Click **Add New Delegate** → lands on
   `GET /delegations/FRA/delegates/new/step1`.
2. Fill in:
   - **Full name**: `Alice Leblanc`
   - **Email**: `alice.leblanc@example.com`
   - **Function**: `Policy Analyst`
   - **Title**: `Ms`
3. Click **Next** (POST).
4. Verify redirect to Step 2.

### A-4. Step 2 — Committee selection

1. Select committees: **EDU**, **TRADE**.
2. Click **Next** (POST).
3. Verify redirect to Step 3.

### A-5. Step 3 — Access levels

The page pre-selects the default level per committee from
`compute_default_access_level`.

1. For **EDU**: select `GENERAL`, leave **Retroactive** unchecked.
2. For **TRADE**: select `GENERAL`, leave **Retroactive** unchecked.
3. Click **Next** (POST).
4. Verify redirect to Step 4.

### A-6. Step 4 — Review & Submit

1. Confirm the summary shows both committees with `GENERAL / non-retroactive`.
2. Click **Submit**.
3. Verify redirect to
   `GET /delegations/FRA/delegates/new/confirmation`.

### A-7. Confirmation page

Expected state in the database:

- One new `Delegate` row for Alice Leblanc.
- Two `DocumentAccessRight` rows, both with
  `approval_status = AUTO_APPROVED`.

```
✓ Scenario A complete — AUTO_APPROVED route verified.
```

---

## Scenario B — PENDING_SECRETARIAT (CONFIDENTIAL, non-retroactive)

**Actor:** Marie Dupont (`DEL-2026-0001`).

Repeat Steps A-3 through A-7 with these changes:

| Step | Field | Value |
|------|-------|-------|
| Step 1 | Full name | `Bob Renard` / email `bob.renard@example.com` |
| Step 3 | EDU access level | `CONFIDENTIAL` |
| Step 3 | TRADE access level | `CONFIDENTIAL` |

**Expected confirmation:** both DARs show `approval_status = PENDING_SECRETARIAT`.

```
✓ Scenario B complete — PENDING_SECRETARIAT route verified.
```

---

## Scenario C — PENDING_DELEGATION_HEAD (RESTRICTED, non-retroactive)

**Actor:** Marie Dupont (`DEL-2026-0001`).

Repeat with:

| Step | Field | Value |
|------|-------|-------|
| Step 1 | Full name | `Claire Morel` / email `claire.morel@example.com` |
| Step 3 | EDU access level | `RESTRICTED` |
| Step 3 | TRADE access level | `RESTRICTED` |

**Expected confirmation:** both DARs show
`approval_status = PENDING_DELEGATION_HEAD`.

```
✓ Scenario C complete — PENDING_DELEGATION_HEAD route verified.
```

---

## Scenario D — PENDING_SECRETARIAT via retroactive override

**Actor:** Marie Dupont (`DEL-2026-0001`).

Retroactive requests are always escalated to the secretariat regardless of
classification level.

Repeat with:

| Step | Field | Value |
|------|-------|-------|
| Step 1 | Full name | `Denis Fontaine` / email `denis.fontaine@example.com` |
| Step 3 | EDU access level | `GENERAL` |
| Step 3 | EDU retroactive | ✓ checked |
| Step 3 | TRADE access level | `RESTRICTED` |
| Step 3 | TRADE retroactive | ✓ checked |

**Expected confirmation:** both DARs show
`approval_status = PENDING_SECRETARIAT`
(GENERAL+retroactive and RESTRICTED+retroactive both escalate).

```
✓ Scenario D complete — retroactive-override route verified.
```

---

## Scenario E — Permission gates

### E-1. Non-editor cannot see the "Add New Delegate" button

1. Log in as Jean Martin (`DEL-2026-0002`).
2. Navigate to `/delegations/FRA`.
3. Verify the **Add New Delegate** link is **absent**.

### E-2. Non-editor POST returns 403

1. As Jean Martin, POST directly to
   `/delegations/FRA/delegates/new/step1`.
2. Verify HTTP 403 response.

### E-3. Editor of another delegation cannot POST

1. Log in as Carlos Silva (`DEL-2026-0005`, editor of BRA).
2. POST to `/delegations/FRA/delegates/new/step1`.
3. Verify HTTP 403 response.

```
✓ Scenario E complete — permission gates verified.
```

---

## Scenario F — Cancel clears session

1. Start the wizard for FRA as Marie Dupont (complete Steps 1–2).
2. On Step 3, click **Cancel**.
3. Verify redirect to `/delegations/FRA`.
4. Navigate back to `/delegations/FRA/delegates/new/step3`.
5. Verify redirect back to Step 1 (session cleared).

```
✓ Scenario F complete — cancel/session-clear verified.
```

---

## Rollback verification (optional manual check)

If you want to manually verify transactional rollback:

1. Temporarily break the DB commit in `wizard_helpers.py`
   (e.g. raise `IntegrityError` before `session.commit()`).
2. Complete the wizard through Step 4 → Submit.
3. Verify that:
   - The confirmation page is **not** reached; Step 4 re-renders with an
     error flash.
   - No new `Delegate` or `DocumentAccessRight` rows were inserted.

---

## Approval-route decision table (reference)

| Classification | Retroactive | `approval_status` |
|----------------|-------------|-------------------|
| `GENERAL` | No | `AUTO_APPROVED` |
| `CONFIDENTIAL` | No | `PENDING_SECRETARIAT` |
| `RESTRICTED` | No | `PENDING_DELEGATION_HEAD` |
| `GENERAL` | Yes | `PENDING_SECRETARIAT` |
| `CONFIDENTIAL` | Yes | `PENDING_SECRETARIAT` |
| `RESTRICTED` | Yes | `PENDING_SECRETARIAT` |

Source: `shared/business_rules.py::determine_approval_route`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| 403 on wizard POST | Logged-in user is not the delegation editor | Switch to the correct editor persona |
| Redirect loop on Step 3 | Wizard session expired (>30 min) | Restart the wizard from Step 1 |
| CSRF token error | `WTF_CSRF_ENABLED=True` in non-test config | Set `WTF_CSRF_ENABLED=False` in dev config or submit with valid token |
| `approval_status` unexpected | Retroactive checkbox state mismatch | Check Step 3 form submission; retroactive=True overrides any level to `PENDING_SECRETARIAT` |
| "Add New Delegate" button missing | `is_editor_of_delegation` returns False | Confirm the logged-in delegate's `role = DELEGATION_EDITOR` for this delegation |

---

Last verified: 2026-04-19 by Stephane
