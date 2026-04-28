---
name: Frontend worktree build workaround
description: Turbopack panics on symlinked node_modules in git worktrees; build must be verified from main tree
type: project
---

The frontend is at `agent_app/frontend/`. When working in a git worktree (`.worktrees/<name>/`), the `node_modules` symlink points to `agent_app/frontend/node_modules` in the main tree. Turbopack (Next.js 16 default bundler) panics with "Symlink [project]/node_modules is invalid, it points out of the filesystem root" — this is a Turbopack bug with git worktrees, not a code error.

**Why:** Turbopack computes the filesystem root as the git worktree root, then rejects symlinks that resolve outside it.

**How to apply:** To verify a build, temporarily copy changed files into the main tree's `agent_app/frontend/`, run `npm run build` there, then restore. TypeScript type-checking via `node_modules/.bin/tsc --noEmit` does work from the worktree. There is no `npm run lint` script in this frontend — skip lint check.
