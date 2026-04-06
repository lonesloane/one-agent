---
name: create-prd
description: Generate high-quality Product Requirements Documents (PRDs) for software systems and AI-powered features. Includes executive summaries, user stories, technical specifications, and risk analysis. Use when asked to "write a PRD", "document requirements", or "plan a feature".
argument-hint: "[feature-or-product-name]"
---

# Product Requirements Document (PRD)

Generate comprehensive, production-grade PRDs that bridge business vision and technical execution.

## Subject

$ARGUMENTS

If no arguments were provided, ask the user what feature or product the PRD should cover before proceeding.

---

## Workflow

### Phase 1: Ground in Reality (Before Asking the User Anything)

Read the project to avoid hallucinating constraints. Check for:

- `README.md`, `DESIGN.md`, `docs/` — architecture, goals, tech stack
- `pyproject.toml`, `package.json`, `requirements.txt` — actual dependencies
- Existing PRDs in `docs/prd-*.md` — prior decisions and patterns

This takes 2 minutes and prevents wasted interview questions like "what's your tech stack?" when it's already documented.

### Phase 2: Discovery Interview

Ask targeted questions to fill gaps the code can't answer. Cover:

- **The Core Problem**: Why are we building this now? What's the trigger?
- **Users**: Who uses this — internal devs, end users, both? What's their context?
- **Current Workaround**: How is the problem being handled today?
- **Success Metrics**: How do we know it worked? What's measurable?
- **Constraints**: Hard constraints the user knows that aren't in the docs (deadlines, external dependencies, non-negotiables)?

Don't ask about things you already read in the codebase. 2–4 focused questions beat a 10-item form.

### Phase 3: Draft the PRD

Generate the document using the schema below. Then present it and ask: "Any sections to adjust before I save this?"

### Phase 4: Save the Artifact

Save the final PRD as `docs/prd-<kebab-case-name>.md` in the project root. Example: `docs/prd-chunking-strategy.md`.

---

## PRD Schema

### 1. Executive Summary

- **Problem Statement**: 1–2 sentences on the pain point.
- **Proposed Solution**: 1–2 sentences on the fix.
- **Success Criteria**: 3–5 measurable KPIs.

### 2. User Experience & Functionality

- **User Personas**: Who is this for? What do they care about?
- **User Stories**: `As a [user], I want to [action] so that [benefit].`
- **Acceptance Criteria**: Bulleted "done" definitions per story.
- **Non-Goals**: What are we explicitly NOT building?

### 3. AI System Requirements *(if applicable)*

- **Tool Requirements**: What tools and APIs are needed?
- **Evaluation Strategy**: How to measure output quality and accuracy.

### 4. Technical Specifications

- **Architecture Overview**: Data flow and component interaction.
- **Integration Points**: APIs, databases, auth.
- **Security & Privacy**: Data handling, compliance.

### 5. Risks & Roadmap

- **Phased Rollout**: MVP → v1.1 → v2.0.
- **Technical Risks**: Latency, cost, dependency failures.

---

## Quality Bar

Write requirements that are concrete and measurable. Vague requirements cause scope drift and failed acceptance testing.

```diff
# BAD — not testable
- The search should be fast and return relevant results.

# GOOD — testable
+ Search must return results within 200ms for a 10k-record dataset.
+ Search algorithm must achieve >= 85% Precision@10 in benchmark evals.
```

If the user hasn't specified a metric, propose one and ask them to confirm — don't leave it as TBD unless it's genuinely unknown.

---

## Anti-patterns

- **Skip Discovery**: Don't write a PRD without at least 2 clarifying questions answered.
- **Hallucinate Constraints**: If a tech stack or deadline isn't in the docs or confirmed by the user, mark it `TBD` and flag it explicitly.
- **Forget Non-Goals**: Omitting non-goals is how scope creep starts.
