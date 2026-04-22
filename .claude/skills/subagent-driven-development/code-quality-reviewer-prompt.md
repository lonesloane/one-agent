# Code Quality Reviewer Prompt Template

Use this template when dispatching a code quality reviewer subagent.

**Purpose:** Verify implementation is well-built (clean, tested, maintainable)

**Only dispatch after spec compliance review passes.**

```
Agent tool (subagent_type: "code-reviewer"):
  description: "Review code quality for Task N"
  prompt: |
    Review the following implementation for production readiness.

    ## What Was Implemented

    {DESCRIPTION}

    ## Requirements/Plan

    {PLAN_OR_REQUIREMENTS}

    ## Git Range to Review

    Base: {BASE_SHA}
    Head: {HEAD_SHA}

    Run:
      git diff --stat {BASE_SHA}..{HEAD_SHA}
      git diff {BASE_SHA}..{HEAD_SHA}

    ## Test Execution Policy

    **Do NOT re-run the full pytest suite.** The implementer ran it at pre-commit
    and reported pass counts + nodeids of newly-added tests. Trust those numbers.

    You MAY run a **specific new test nodeid** from the implementer's report if
    you need to audit how that test asserts behavior (e.g. to check that it
    verifies observable behavior and not mock state). Even then, prefer *reading*
    the test code over executing it.

    Escalate (do not silently re-run the suite) if:
    - Pass counts are missing or look inconsistent with the diff.
    - The diff deletes or weakens an existing test without a written justification.
    - A task that changed behavior has no corresponding new test in the nodeid list.

    Flag these as Blocking issues. Your time is better spent on semantic review
    (naming, cohesion, docstring intent, abstraction fit) than on re-proving green.
```

**Review scope — use the three-tier taxonomy from `.claude/agents/code-reviewer.md`:**
- **Blocking** — correctness, security, broken tests, spec deviations
- **Semantic** — naming intent, abstraction fit, public-API docstring content, cohesion, test assertion strength, 500-line/50-line/100-line limits
- **Mechanical** — DO NOT enumerate. Assume `ruff format && ruff check` ran before commit. If they didn't, return the single line:
  > Formatter not run. Please execute `ruff format . && ruff check --fix .` and re-commit.

**Do not flag any of the following** (ruff owns them):
- Line length, blank-line spacing, indentation, trailing whitespace
- Import order / unused imports
- Quote style, f-string style
- PEP 8 case conventions (ruff-N)
- Trailing commas, parenthesization
- `Optional[X]` vs `X | None`, `typing.Dict` vs `dict` (ruff-UP)

**DO check (semantic):**
- Does each file have one clear responsibility with a well-defined interface?
- Are units decomposed so they can be understood and tested independently?
- Is the implementation following the file structure from the plan?
- Did this implementation create new files that are already large, or significantly grow existing files? (Don't flag pre-existing file sizes — focus on what this change contributed.)
- Does each public function have a docstring that explains *intent* (not just restates the signature)?
- Do tests assert *observable behavior* rather than mock/internal state?

**Code reviewer returns:** Strengths, Issues (Blocking/Semantic), Assessment. If more than 3 mechanical nits exist, return the short-circuit line instead of enumerating.
