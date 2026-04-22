---
name: tdd
description: Test-driven development with red-green-refactor loop. Use when user wants to build features or fix bugs using TDD, mentions "red-green-refactor", wants integration tests, or asks for test-first development.
---

# Test-Driven Development

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe _what_ the system does, not _how_ it does it. A good test reads like a specification - "user can checkout with valid cart" tells you exactly what capability exists. These tests survive refactors because they don't care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (like querying a database directly instead of using the interface). The warning sign: your test breaks when you refactor, but behavior hasn't changed. If you rename an internal function and tests fail, those tests were testing implementation, not behavior.

**Toolchain — Python**: pytest (`@pytest.mark`, `@pytest.fixture`), unittest.mock (`Mock`, `patch`, `MagicMock`), pytest-mock (`mocker` fixture). Verify with `pytest`.

**Toolchain — TypeScript/Next.js**: Vitest or Jest with React Testing Library (`@testing-library/react`, `@testing-library/user-event`). Use `screen` queries in priority order: `getByRole` → `getByLabelText` → `getByText` → `getByTestId`. Verify with `npm test` or `npx vitest`.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** This is "horizontal slicing" - treating RED as "write all tests" and GREEN as "write all code."

This produces **crap tests**:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes - they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets. One test -> one implementation -> repeat. Each test responds to what you learned from the previous cycle. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED->GREEN: test1->impl1
  RED->GREEN: test2->impl2
  RED->GREEN: test3->impl3
  ...
```

Run a **scoped** pytest after each RED->GREEN cycle to confirm exactly one new test turns green. Do **not** run the full suite on every cycle — see "Test Scoping" below.

## Test Scoping (shift-left against suite-thrash)

The full test suite runs many times in a typical task: once per TDD cycle, once at self-review, once per reviewer, once per fix loop, once at the final review. That is wasteful and slow.

**Default scoping for each phase:**

| Phase | What to run | Why |
|---|---|---|
| RED → GREEN (tracer bullet) | `pytest path/to/test_file.py::TestClass::test_name` | Confirm exactly one new test flips green |
| Incremental cycles within a task | `pytest path/to/test_file.py` (or the task's test directory) | Fast feedback on the slice you're building |
| After refactor | Same task-scoped path + `pytest --lf` | Catch regressions you just introduced |
| Pre-commit (final implementer gate) | `pytest` (full suite) | **Single authoritative run** per task — record the pass count in the commit message and report |
| Spec / quality review | **No re-run by default** — trust the committed pass count | See `subagent-driven-development/` reviewer prompts |
| Fix loop after a bounce | `pytest <failing nodeids>` + `pytest --lf` | Narrow to what actually regressed |
| Final feature review | `pytest` (full suite, once) | Authoritative end-to-end gate |

**Report format after pre-commit run:** record `N passed, M deselected` plus the explicit nodeids of tests *added in this task*. Reviewers use that list to spot-check claims without re-running everything.

**Use `pytest --lf --ff` in fix loops** to prioritize last-failed tests; this hits pytest's cache and skips what already passed.

## Workflow

### 1. Planning

Before writing any code:

- [ ] **Orient with jcodemunch** — use `mcp__jcodemunch__search_symbols` to locate existing classes and functions in scope; use `mcp__jcodemunch__find_references` to understand how the module is already called before designing a new interface
- [ ] Confirm with user what interface changes are needed
- [ ] Confirm with user which behaviors to test (prioritize)
- [ ] Identify opportunities for [deep modules](deep-modules.md) (small interface, deep implementation)
- [ ] Design interfaces for [testability](interface-design.md)
- [ ] List the behaviors to test (not implementation steps)
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most important to test?"

**You can't test everything.** Confirm with the user exactly which behaviors matter most. Focus testing effort on critical paths and complex logic, not every possible edge case.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   Write test for first behavior -> test fails
GREEN: Write minimal code to pass -> test passes
```

This is your tracer bullet - proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```
RED:   Write next test -> fails
GREEN: Minimal code to pass -> passes
```

Rules:

- One test at a time
- Only enough code to pass current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

### 4. Refactor

After all tests pass, look for [refactor candidates](refactoring.md):

- [ ] Extract duplication
- [ ] Deepen modules (move complexity behind simple interfaces)
- [ ] Apply SOLID principles where natural
- [ ] Consider what new code reveals about existing code
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```
