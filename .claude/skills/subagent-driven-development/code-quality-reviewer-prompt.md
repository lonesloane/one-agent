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
```

**In addition to standard code quality concerns, the reviewer should check:**
- Does each file have one clear responsibility with a well-defined interface?
- Are units decomposed so they can be understood and tested independently?
- Is the implementation following the file structure from the plan?
- Did this implementation create new files that are already large, or significantly grow existing files? (Don't flag pre-existing file sizes — focus on what this change contributed.)

**Code reviewer returns:** Strengths, Issues (Critical/Important/Minor), Assessment
