---
name: project-status
description: Summarize current project state from docs. Use when starting a new conversation, resuming work, or when the user says "/project-status", "where were we", "what's the status", "catch me up", "shall we continue", "let's pick up where we left off", "let's resume", "continuing from last time", "can we continue working on", "shall we continue working on".
---

# Project Status

Produce a concise, scannable status summary by reading the project documentation files. This is the "orientation tool" for resuming work across conversations.

## When This Activates

- User says `/project-status`
- User uses any resume phrase: "shall we continue", "let's pick up where we left off", "let's resume", "continuing from last time", "can we continue working on X", "shall we continue working on X"
- Start of a new conversation when context needs rebuilding

## Instructions

Read all four project docs in parallel, then synthesize (do not dump):

1. `docs/DESIGN.md` — architecture overview
2. `docs/DECISIONS.md` — decision log
3. `docs/BACKLOG.md` — task tracker with phases
4. `docs/OPEN_QUESTIONS.md` — deferred questions

These paths are relative to the project root. Use the Read tool, not Bash.

### Output Format

Produce a summary with exactly these sections:

**Current Phase** — Which phase from BACKLOG.md we're in, one line.

**Recently Completed** — What's been done (marked `[x]` in BACKLOG). Only list items completed since the last major milestone, not everything ever done.

**Next Steps** — The immediate 2-3 tasks to work on (first unchecked items in the current phase). Be specific.

**Blocked / Waiting** — Anything marked `[!]` in BACKLOG, or dependencies that prevent progress. Say "Nothing blocked" if clear.

**Recent Decisions** — Last 2-3 entries from DECISIONS.md, summarized in one line each. Skip if there are no recent additions since last check-in.

**Open Questions Becoming Urgent** — Any items from OPEN_QUESTIONS.md that are relevant to the current or next phase. Skip if none are urgent yet.

### Principles

- **Synthesize, don't regurgitate.** The user can read the files themselves. The value of this skill is the summary and editorial judgment about what matters right now.
- **Be brief.** The entire output should fit in one screenful — roughly 20-30 lines.
- **Flag drift.** If the backlog and design doc seem inconsistent (e.g., a decision was made but not reflected in the design), call it out.
- **No action without asking.** This skill only reports status. It does not modify files, create tasks, or start work. If something needs doing, say so and let the user decide.
