---
name: bms-speckit-auto
description: Full automated development workflow. This skill should be used when the user asks to "build an application", "create a dashboard", "develop a feature", "speckit", "bms-speckit", or provides a software requirement to implement end-to-end with TDD, specifications, and quality gates. Usage /bms-speckit:bms-speckit-auto <your requirement description>
---

# BMS Speckit — Chain Orchestrator

Chain blueprint: `blueprints/bms-speckit-pipeline.yaml`

## Autonomous Mode Contract — READ FIRST

This skill runs **fully autonomously**. Once invoked, it must not prompt the user for anything until the pipeline finishes or hits a hard error it cannot self-resolve.

**Hard rules — no exceptions:**

- **Never ask clarification questions.** Do not emit `[NEEDS CLARIFICATION: ...]` blocks, A/B/C option tables, or "what should I do?" prompts back to the user at any point in the pipeline, including inside Step 5 (specify).
- **Resolve all unknowns with documented defaults.** If a requirement is ambiguous, pick the industry-standard default, record it in the spec's `## Assumptions` section with a one-line rationale, and continue. The user can correct it later — blocking the pipeline on a question costs more than picking wrong.
- **Never request confirmation between steps.** No "proceed?", no "is this OK?". Commit and move on.
- **Never stop for optional choices.** Only stop for hard failures (build broken, tests failing after 3 retries, critical security issue the QC agent flagged). Everything else: pick a default, log it, continue.
- **Override sub-skill clarification behavior.** Skills like `speckit.specify` have their own "ask up to 3 clarification questions" logic. When invoked through this pipeline, that logic is **disabled** — the sub-skill must default the answers and record them as assumptions.

**Wrong entry point check:** if the user invoked this pipeline via `/speckit.specify`, `/speckit.plan`, or any other individual speckit slash command instead of `/bms-speckit:bms-speckit-auto`, those individual commands run only their single step. They will not execute the full 12-step chain. Only this skill (`bms-speckit-auto`) orchestrates the complete pipeline.

## Execution Rules

1. Execute steps **sequentially** in chain order — never skip steps
2. Use the **Skill tool** for all skill invocations (no slash commands in subagents)
3. On step failure, check the **error policy** before proceeding:
   - `on_failure: stop` → halt the chain and report which step failed
   - `on_failure: continue` → log the failure and proceed to next step
4. Pass `$ARGUMENTS` (the user's requirement) to step 1 (brainstorm). Step 5 (specify) receives the **output from step 1 enriched by step 2 research**
5. **Commit and push after every important step** — each artifact-producing step must commit its output before proceeding to the next step
6. **Report progress** to the user at every step transition
7. Do NOT ask for confirmation between steps

---

## Progress Reporting

Before dispatching the Phase 1 subagent, create a progress tracker so the user can follow along. Use TaskCreate to create one task per step:

```
TaskCreate: "Step 1: Brainstorm — explore requirements"
TaskCreate: "Step 2: Research — best practices & technology survey"
TaskCreate: "Step 3: Constitution — engineering principles"
TaskCreate: "Step 4: CLAUDE.md sync"
TaskCreate: "Step 5: Specify — feature specification"
TaskCreate: "Step 6: Plan — implementation plan"
TaskCreate: "Step 7: Tasks — task list"
TaskCreate: "Step 8: Analyze — consistency check"
TaskCreate: "Step 9: Implement with rolling QC"
TaskCreate: "Step 10: Final quality gate"
TaskCreate: "Step 11: Merge to main"
```

Then output a message to the user:

> Starting BMS Speckit pipeline for: "$ARGUMENTS"
> Phase 1 (specification & planning) running in subagent...

---

## Phase 1: Specification & Planning

> **Execution context:** Dispatch ALL Phase 1 steps in a single subagent to preserve the main context window for implementation.

Subagent prompt:

"""
You are running the BMS Speckit specification and planning chain. Execute each step in order using the Skill tool. Do NOT ask for confirmation. Follow error handling policies exactly. **Commit and push after every important step.**

**AUTONOMOUS MODE — NO USER PROMPTS.** This subagent runs without user interaction. You must not return control to the user with questions, option tables, or `[NEEDS CLARIFICATION]` markers under any circumstance. For every ambiguity: pick the industry-standard default, record it in the relevant artifact's `## Assumptions` section with a one-line rationale, and continue. Specifically, when invoking `speckit.specify` in Step 5, pass it the explicit instruction: "Do not emit `[NEEDS CLARIFICATION]` markers or option tables; resolve all ambiguities with documented defaults in an `## Assumptions` section and produce a complete spec in one pass." Verify the final `spec.md` contains zero clarification markers before committing. If the sub-skill still emits markers, the subagent must rewrite the spec to replace each marker with a default + assumption before committing.

**IMPORTANT — Progress reporting:** Before starting each step, output a progress message to the user in this format:

`[Step N/11] step_name — description...`

After completing each step, output:

`[Step N/11] DONE — brief result summary`

### Step 1 — Brainstorm `[on_failure: STOP]`
- **Progress:** Output `[Step 1/11] Brainstorm — exploring requirements and design...`
- **Skill:** `superpowers.brainstorm`
- **Input:** "$ARGUMENTS"
- **Purpose:** Explore intent, requirements, design alternatives, and edge cases
- **Knowledge lookup:** Use `mcp__bms-knowledge-mcp__search_knowledge` to search the `hosxp` collection for relevant data dictionaries, table schemas, and system architecture. Also search `bms`, `moph`, `nhso` collections if relevant.
- **Output:** Detailed specification document
- **Timeout:** 300s
- **Post-action:** Commit all files and push. Message: `feat(speckit): brainstorm — explore requirements and design`
- **Done:** Output `[Step 1/11] DONE — brainstorm complete`

### Step 2 — Research `[on_failure: CONTINUE]`
- **Progress:** Output `[Step 2/11] Research — surveying best practices and technologies...`
- **Purpose:** Research external best practices, proven patterns, recommended libraries/frameworks, and informative reference material relevant to the user's requirement. This grounds the pipeline in current industry knowledge before specification begins.
- **Tools:** Use `WebSearch` and `mcp__plugin_context7_context7__resolve-library-id` + `mcp__plugin_context7_context7__query-docs` for library documentation
- **Timeout:** 300s
- **Process:**
  1. **Identify research topics** from Step 1 output — extract key technologies, patterns, and domains that need external validation
  2. **Best practices search** — WebSearch for best practices, design patterns, and architecture guidance relevant to the feature (e.g., "real-time dashboard best practices", "patient data security standards", "React table performance optimization")
  3. **Library/framework survey** — For each technology identified in brainstorm:
     - WebSearch for current recommended libraries, compare alternatives (stars, maintenance, bundle size, license)
     - Use context7 `resolve-library-id` then `query-docs` to fetch current documentation for top candidates
  4. **Security & compliance research** — If the feature involves sensitive data (healthcare, financial, PII), search for relevant compliance standards and security guidelines
  5. **Prior art** — Search for similar implementations, open-source examples, or reference architectures that inform the design
- **Output:** A research brief saved as `specs/*/research.md` containing:
  - **Best practices summary** — key patterns and principles to follow
  - **Recommended libraries** — with rationale (why this over alternatives)
  - **Documentation references** — links and key API details from context7
  - **Security/compliance notes** — standards to adhere to (if applicable)
  - **Prior art** — reference implementations or architectures found
- **Post-action:** Commit all files and push. Message: `feat(speckit): research — best practices and technology survey`
- **Done:** Output `[Step 2/11] DONE — research brief created (N topics researched)`

### Step 3 — Constitution `[on_failure: STOP]`
- **Progress:** Output `[Step 3/11] Constitution — establishing engineering principles...`
- **Skill:** `speckit.constitution`
- **Input:** "Establish and enforce a comprehensive set of engineering principles that prioritize high code quality, strict adherence to Test-Driven Development (TDD) practices, and well-defined testing standards across unit, component, integration, and API levels to ensure system reliability and maintainability, maintain a consistent, user-friendly, and professional user interface aligned with strong user experience (UX) guidelines, optimize application performance through efficient architecture and resource management; enforce disciplined version control practices with frequent, atomic commits to minimize risk and improve traceability, promote the development and reuse of modular components and functions while centralizing business logic to avoid duplication and ensure consistency, provide clear, informative user feedback and progress reporting throughout system interactions, and leverage all available tools, frameworks, and domain-specific expertise to support developers in delivering robust, scalable, and high-quality applications."
- **Output:** `specs/constitution.md`
- **Timeout:** 300s
- **Done:** Output `[Step 3/11] DONE — constitution created`

### Step 4 — CLAUDE.md Sync `[on_failure: CONTINUE]`
- **Progress:** Output `[Step 4/11] CLAUDE.md Sync — verifying compliance...`
- **Action:** Read CLAUDE.md and verify it complies with the constitution in `specs/constitution.md`. Update CLAUDE.md if it conflicts with or is missing constitution rules.
- **Timeout:** 120s
- **Post-action:** Commit all files and push. Message: `feat(speckit): add constitution and sync CLAUDE.md`
- **Done:** Output `[Step 4/11] DONE — CLAUDE.md synced`

### Step 5 — Specify `[on_failure: STOP]`
- **Progress:** Output `[Step 5/11] Specify — creating feature specification...`
- **Skill:** `speckit.specify`
- **Input:** Use the detailed specification output from Step 1 (brainstorm) **enriched with the research findings from Step 2**. Include recommended libraries, best practices, and compliance requirements from the research brief in the specification input.
- **Knowledge lookup:** Use `mcp__bms-knowledge-mcp__search_knowledge` to search the `hosxp` collection for exact table names, field names, data types, and relationships needed by this feature. Reference actual HOSxP data structures in the spec.
- **Autonomy override (CRITICAL):** `speckit.specify` by default emits `[NEEDS CLARIFICATION]` markers and prompts the user with A/B/C option tables for ambiguous requirements. **This behavior is DISABLED in the auto pipeline.** Pass this instruction to the specify skill invocation verbatim:
  > "Do NOT emit any `[NEEDS CLARIFICATION]` markers or option tables. For every ambiguous requirement, pick the industry-standard default, write the chosen value into the spec directly, and record it in a new `## Assumptions` section at the end of the spec with a one-line rationale. The pipeline is running autonomously — the user will correct assumptions after the run if needed. Never block the pipeline with a question."
- **Output:** `specs/*/spec.md` — must contain zero `[NEEDS CLARIFICATION]` markers. Verify before commit; if any remain, resolve them with a default and record in `## Assumptions`.
- **Timeout:** 300s
- **Retry:** up to 2 attempts
- **Post-action:** Commit all files and push. Message: `feat(speckit): add feature specification`
- **Done:** Output `[Step 5/11] DONE — specification created`

### Step 6 — Plan `[on_failure: STOP]`
- **Progress:** Output `[Step 6/11] Plan — generating implementation plan...`
- **Skill:** `speckit.plan`
- **Input:** reads from step 5 artifacts
- **Output:** `specs/*/plan.md`
- **Timeout:** 300s
- **Retry:** up to 2 attempts
- **Post-action:** Commit all files and push. Message: `feat(speckit): add implementation plan`
- **Done:** Output `[Step 6/11] DONE — plan created`

### Step 7 — Tasks `[on_failure: STOP]`
- **Progress:** Output `[Step 7/11] Tasks — generating task list...`
- **Skill:** `speckit.tasks`
- **Input:** reads from step 6 artifacts
- **Output:** `specs/*/tasks.md`
- **Timeout:** 300s
- **Retry:** up to 2 attempts
- **Post-action:** Commit all files and push. Message: `feat(speckit): add task list`
- **Done:** Output `[Step 7/11] DONE — N tasks created`

### Step 8 — Analyze `[on_failure: CONTINUE]`
- **Progress:** Output `[Step 8/11] Analyze — cross-artifact consistency check...`
- **Skill:** `speckit.analyze`
- **Purpose:** Cross-artifact consistency check (spec ↔ plan ↔ tasks ↔ research). Non-destructive — report only.
- **Timeout:** 300s
- **Post-action:** Commit all files and push. Message: `feat(speckit): add cross-artifact analysis report`
- **Done:** Output `[Step 8/11] DONE — analysis complete`

### Completion Contract — DO NOT RETURN UNTIL THIS IS SATISFIED

Before returning to the main agent, perform these verification checks yourself using Bash/Read. Do NOT return a success message if any file is missing — exploration-only returns are a bug, not an acceptable outcome.

1. **Identify the feature directory.** Run `ls -dt specs/*/ | head -1` — this is your feature path (e.g. `specs/003-my-feature/`). Capture the feature slug (basename without trailing slash).
2. **Verify each required artifact exists and is non-empty** using `test -s <file>`:
   - `specs/constitution.md`
   - `specs/<slug>/research.md`
   - `specs/<slug>/spec.md`
   - `specs/<slug>/plan.md`
   - `specs/<slug>/tasks.md`
3. **Verify commits were made:** `git log --oneline -n 12` should show at least 5 speckit commits (brainstorm, research, constitution, specify, plan, tasks, analyze).
4. **If any artifact is missing or empty, do NOT return failure — write it directly.** The `Skill` tool sometimes fails inside subagents (tool-access restrictions, one-shot mode). Your job is to ensure the artifact exists on disk regardless of how it got there:
   - Read the relevant template from `.specify/templates/` (spec-template.md, plan-template.md, tasks-template.md)
   - Fill it in using the in-memory content you already produced from brainstorm/research/specify
   - `Write` the file, `git add`, `git commit`, `git push`
   - Re-run the verification check
5. **Return format — the LAST LINE of your response must be exactly this structured marker** (the main agent parses it; no prose after it):

   `FEATURE=<slug>|SPEC=<path>|PLAN=<path>|TASKS=<path>|STATUS=OK`

   If after the fallback write in step 4 some artifact is still missing, return:

   `FEATURE=<slug-or-unknown>|MISSING=<comma-separated-list>|STATUS=INCOMPLETE`
"""

### Phase 1 → Phase 2 Handoff — Verification Gate (MANDATORY)

The subagent is one-shot — the Task tool dispatches it, waits, and returns a single text response. There is no SendMessage chaining. So the main agent **must verify artifacts exist on disk before proceeding**. A subagent that did only read-only exploration will return success-looking prose but leave `specs/*/` empty — do not trust the prose.

**Step A — Parse the subagent marker.**
Find the line beginning with `FEATURE=` in the subagent's output. Extract `<slug>`, `<spec>`, `<plan>`, `<tasks>`, `<status>`. If no marker is present, treat as `STATUS=INCOMPLETE`.

**Step B — Verify artifacts on disk from the main context** (the subagent lies sometimes):

```
Bash: test -s specs/constitution.md \
  && test -s specs/<slug>/spec.md \
  && test -s specs/<slug>/plan.md \
  && test -s specs/<slug>/tasks.md \
  && echo "GATE=OK" || echo "GATE=MISSING"
```

**Step C — Branch:**
- `GATE=OK` and marker `STATUS=OK` → verification passed. Proceed to Step 9.
- Otherwise → run **Recovery Protocol**.

#### Recovery Protocol

**Attempt 1 — Retry subagent with a stricter recovery prompt.**

Re-dispatch via Task tool:

"""
RECOVERY RUN. A previous Phase 1 execution returned without producing artifacts on disk at `specs/<slug>/`. The existing files may be partial. Your job now is to produce the missing artifacts — not to re-explore, not to re-research, not to ask questions.

Required outputs (all must exist and be non-empty before you return):
- specs/constitution.md
- specs/<slug>/research.md
- specs/<slug>/spec.md
- specs/<slug>/plan.md
- specs/<slug>/tasks.md

Rules:
1. Read `$ARGUMENTS` and every existing file under `specs/` to pick up where the prior run left off.
2. If the `Skill` tool fails or is unavailable, do NOT retry it — `Write` the artifact directly using `.specify/templates/*.md` as the structure and content you know from the user requirement as the body.
3. Resolve every ambiguity with a documented default in an `## Assumptions` section. Never emit `[NEEDS CLARIFICATION]` markers.
4. After each file you write, `git add && git commit && git push` with message `feat(speckit): <step>`.
5. Before returning, `test -s` each required file and `git log --oneline -n 12` to confirm.
6. Return with the structured marker `FEATURE=<slug>|SPEC=<path>|PLAN=<path>|TASKS=<path>|STATUS=OK` as your final line, no prose after.
"""

After the retry returns, re-run Step B. If `GATE=OK`, proceed to Step 9.

**Attempt 2 — Main-context inline fallback** (runs only if the retry also fails).

Execute steps 5–8 directly in the main agent using Write/Edit/Bash, NOT via Task subagent and NOT via Skill tool:

1. Read `.specify/templates/spec-template.md`, `.specify/templates/plan-template.md`, `.specify/templates/tasks-template.md`.
2. Read `$ARGUMENTS` and any partial artifacts already on disk under `specs/`.
3. If the feature branch does not exist yet: `.specify/scripts/bash/create-new-feature.sh "$ARGUMENTS" --json --short-name <derived-slug> "$ARGUMENTS"` to create branch + spec directory.
4. `Write` `specs/<slug>/spec.md` filling in each template section from the requirement. Use `## Assumptions` for defaults. Zero `[NEEDS CLARIFICATION]` markers allowed.
5. `Write` `specs/<slug>/plan.md` with ordered steps, file paths, component boundaries, test strategy, rollback considerations.
6. `Write` `specs/<slug>/tasks.md` with atomic, dependency-ordered tasks, each with acceptance criteria.
7. Commit each as written: `git add <file> && git commit -m "feat(speckit): <step> (main-context fallback)" && git push`.
8. Re-run Step B verification. If still `GATE=MISSING`, halt the pipeline with a clear error listing the missing files — do NOT proceed to Phase 2 with a broken spec tree.

Only after the Verification Gate passes (`GATE=OK`), update tasks 1–8 as completed using TaskUpdate, then output:

> Phase 1 complete. N tasks at specs/<slug>/tasks.md
> Starting Phase 2 (implementation)...

---

## Phase 2: Implementation

> **Execution context:** Runs in main context after subagent completes.

### Step 9 — Implement with Rolling QC `[on_failure: CONTINUE | max_retries: 3]`
- **Progress:** Output `[Step 9/11] Implement — starting rolling QC loop (N tasks)...`
- **Engine:** `/oh-my-claudecode:ralph` — ralph persistence mode ("the boulder never stops"). It keeps working — parallel *ultrawork* execution plus mandatory architect verification — until the goal is fully met. It is an infinite-persistence / verify-fix loop, so completion is enforced by ralph's own architect sign-off, not by CLI flags.
- **Input:** Use the **tasks.md path returned by the Phase 1 subagent** (e.g. `specs/my-feature/tasks.md`). Replace `{TASKS_PATH}` below with the actual path.
- **Completion:** ralph runs its verify/fix loop until architect verification confirms the goal is met. It does **not** take `--completion-promise` or `--max-iterations` flags (those belonged to the old `ralph-loop`) — pass the task and the done-criteria as the prompt and ralph enforces completion itself. (Confirm options with `/omc-help` if a newer ralph adds bounding flags.)
- **Pattern:** Rolling Review — each task gets its own QC cycle before moving to the next
- **Per-task cycle:**
  1. **IMPLEMENT** — write code following TDD (tests first, then implementation). **Runtime safety rules:**
     - Always add explicit return type annotations on data transformation functions — never rely on type inference for functions whose return values are spread, iterated, or passed to collection methods
     - Never spread or iterate a function's return value without verifying it returns the expected collection type (e.g., array not object, list not dict)
     - Use strict equality, add null/undefined/None guards for external data (API responses, DB results, config, user input)
     - Add unit tests that actually execute data transformation functions and verify the output type and shape
     - **SQL validation:** before writing any SQL statement, verify the exact table and column names exist. Use `bms-session-mcp-server` tools (`list_tables`, `describe_table`) or `mcp__bms-knowledge-mcp__search_knowledge` (hosxp collection) to confirm every field reference. Never guess column names. After writing a query, test it with `query` tool using `EXPLAIN` or `LIMIT 0` to confirm it parses and executes.
     - **Business logic correctness:** before writing any SQL, state out loud what business question the query is supposed to answer. Then use `mcp__bms-knowledge-mcp__search_knowledge` on the `hosxp` collection to verify: (a) you're using the canonical table for this data (e.g., `ovst` vs `opd`), (b) you're applying the correct soft-delete/status filter (e.g., `vstatus != 'C'`), (c) you're using the right date column, (d) you're joining on the right key (hn vs vn vs an). For multi-table relationships use `graph_search` instead. For reporting queries, also check `moph` or `nhso` collections for regulatory inclusion/exclusion rules. Cite the HOSxP convention in a code comment (e.g., `// HOSxP: use vstdate not service_date`).
     - **Brand & layout quality (for UI tasks):** whenever a task creates or modifies the navbar, login page, or page layout: source the app name and description from `specs/*/spec.md` (never invent one or use framework defaults); make sure the navbar displays the app name, the login page identifies the system with a descriptive subtitle, nav items have clear labels (not "Page 1"), layouts have a header/main structure with consistent spacing, and typography uses a visible hierarchy. No Lorem ipsum, no "Hello World", no default framework colors in brand positions, no placeholder credentials in login forms.
  2. **INLINE QC** — immediately run: build, lint, ALL tests, security quick scan, UX check
  3. **INTEGRATION TEST (real database)** — for every task that touches database queries or data-dependent business logic, run an integration test that:
     - Uses the real `bms-session-mcp-server` `query` tool to execute the feature's actual SQL against the real HOSxP database (not mocks)
     - Flows the real result through the feature's actual code path (transformers, filters, aggregations) — not just the raw query
     - Asserts on concrete properties: row count is reasonable, required columns are populated, data types match the schema, masked fields are handled correctly (patient names, CIDs are pre-masked — do not flag as errors)
     - Uses a small `LIMIT` to avoid pulling large result sets during testing
     - Verifies edge cases with real data: empty results for narrow filters, NULL handling, encoding (Thai characters), date ranges
     - If the task produced a UI component that renders DB data, also verify the component renders without error using a real query result as the prop
     - **If the integration test fails:** investigate whether the bug is in the SQL, the transformer, or the assertion. Fix the actual cause. Do NOT relax the assertion to make it pass.
  4. **FIX** — fix every issue found in steps 2 and 3, re-run checks
  5. **COMMIT** — only commit when build + lint + unit tests + integration tests all pass with zero errors; then mark the task as `- [x]` in `{TASKS_PATH}`
  6. **NEXT** — move to the next unchecked task
- **Action:** Run — the task is passed as **plain text** after the command (no flags; ralph reads the whole remainder as the prompt):

`/oh-my-claudecode:ralph systematically execute speckit.implement via the Skill tool to complete every task defined in {TASKS_PATH} with strict adherence to specification requirements. IMPORTANT: apply rolling QC after EACH task — after implementing a task run build and fix build errors, run linter and fix lint errors, run ALL tests (not just new ones) and fix failures, check for hardcoded secrets and injection vulnerabilities in code you just wrote, verify UI code has actionable error messages and loading states. RUNTIME SAFETY: always add explicit return type annotations on data transformation functions, never spread or iterate a function return value without verifying it returns the expected collection type, use strict equality and null guards for external data, write tests that execute data transformers and verify output type and shape. SQL VALIDATION: before writing any SQL statement verify exact table and column names exist via bms-session-mcp-server list_tables/describe_table or bms-knowledge-mcp search_knowledge with hosxp collection, never guess column names, after writing test each query with EXPLAIN or LIMIT 0 via the query tool to confirm it executes without error. INTEGRATION TESTING: for every task that touches database or data-dependent logic run an integration test using the real bms-session-mcp-server query tool to execute the feature's SQL against the real HOSxP database (not mocks), flow the result through the actual code path, assert on concrete properties (row count, columns populated, types match, masked fields handled), use small LIMIT to avoid large result sets. If integration test fails investigate the real cause and fix it — do not relax the assertion. BUSINESS LOGIC: before writing any SQL state the business question it answers then consult bms-knowledge-mcp search_knowledge on hosxp collection to verify canonical table selection, soft-delete filters, correct date columns, join keys (hn/vn/an); use graph_search for multi-table relationships; for reporting queries also check moph or nhso collections for regulatory rules; cite the HOSxP convention in a code comment next to the query. Only commit when build plus lint plus tests all pass with zero errors then proceed to next task. Report progress to the user after each task: output [Task N/total] DONE — task_name. Do NOT batch QC at the end. Maintain atomic commits after each successful task with clear traceability, avoid requesting confirmation and proceed autonomously. Once all tasks are implemented invoke speckit.analyze via the Skill tool to perform a full validation pass, automatically apply all recommended improvements or corrections, and re-run all tests to confirm stability and zero regression before reporting completion.`

- **Done:** Update task 9 as completed. Output `[Step 9/11] DONE — all tasks implemented and verified`

### Step 10 — Final Quality Gate `[on_failure: STOP | max_retries: 3]`
- **Progress:** Output `[Step 10/11] Final QC — running comprehensive quality audit...`
- **Agent:** Dispatch `bms-speckit:quality-control` agent
- **Subagent execution rule (REMIND THE AGENT):** in your dispatch prompt, instruct the QC agent that it MUST run build, lint, test, audit, and SQL-validation commands **synchronously** as foreground `Bash` calls with a generous `timeout` parameter. **Forbid `sleep N && cat <output>`-style polling against backgrounded jobs** — the harness blocks long leading-sleep commands and sleep-based polling, which causes the QC pass to stall and self-recover, costing extra turns. The full rule is documented at the top of the QC agent file under "Execution Rules"; just remind the agent to follow it.
- **Purpose:** Final comprehensive sweep. Since inline QC already caught per-task issues, this focuses on **cross-cutting concerns** that can only be detected across the full codebase.
- **Timeout:** 900s
- **Focus areas:**
  - **A. Security deep scan** — `npm audit` / `pip audit`, auth flow review, CORS, secrets across all files
  - **B. Dependencies** — outdated packages, vulnerable deps, unused packages
  - **C. UX consistency & brand polish** — consistent error handling and feedback patterns across ALL features, empty states, responsive design. Brand consistency: app name matches across package.json, HTML title, meta tags, navbar, login page, manifest (all sourced from spec). No placeholder names (My App, React App, Hello World). Login page identifies the system with name + descriptive subtitle, real form labels, no demo credentials. Navbar has descriptive nav labels. Professional layout: defined structure, consistent spacing, no default framework colors in brand positions, dashboards show real data or informative empty states, typography hierarchy, customized favicon and page title.
  - **D. Accessibility** — alt text, form labels, keyboard nav, heading hierarchy
  - **E. Integration check** — verify all components work together end-to-end
  - **F. Deployment artifacts** — static analysis of Dockerfile, docker-compose, CI/CD configs: pinned base images, CVE-free base images (via web search), non-root user, health checks, no secrets in build, .dockerignore coverage (skipped if no deployment files exist)
  - **G. Database compatibility & SQL validation** — two-part check:
    - **G1-G5 (cross-compatibility):** enforce "write SQL once, run on both" — all SQL must use cross-compatible syntax that works on MySQL and PostgreSQL without dialect branching. Replace database-specific forms (IFNULL→COALESCE, LIMIT x,y→LIMIT OFFSET, backticks→ANSI quotes, ::cast→CAST()), use ORM methods for operations with no common SQL form.
    - **G6 (SQL schema validation — MOST IMPORTANT):** validate every SQL statement in the codebase against the real database schema. Hallucinated column names are the #1 QC failure — LLMs frequently reference columns that don't exist. For each SQL statement: use `bms-session-mcp-server` (`list_tables`, `describe_table`, `query` with EXPLAIN/LIMIT 0) or `mcp__mysql__mysql_query` / `mcp__postgres__query` to verify every table and column reference exists. Fall back to `mcp__bms-knowledge-mcp__search_knowledge` (hosxp collection) or grep migration files if live DB is unavailable. Fix every hallucinated reference. (skipped if no SQL in project)
  - **H. Integration testing (real database, end-to-end)** — run actual integration tests against the real HOSxP database via `bms-session-mcp-server`. For every DB-touching feature verify there's an integration test that: executes the feature's real SQL via the `query` tool, flows real data through the actual code path (transformers, filters, UI components), asserts on concrete properties (row count range, column presence, type correctness, masked field handling, Thai encoding). Create missing integration tests. Never fix failures by mocking responses, skipping tests, or loosening assertions. Flag slow queries for user review. (skipped if bms-session-mcp-server is not available)
  - **I. Business logic semantic validation** — verify every SQL statement actually retrieves the correct data per the user's intent and HOSxP conventions, not just that it runs without error. For each SQL: state the business question it should answer, cross-reference `mcp__bms-knowledge-mcp__search_knowledge` on `hosxp` collection for canonical table selection, soft-delete/status filters, correct date columns, join keys (hn/vn/an), code system usage (ICD-10/LOINC/TMT). Use `graph_search` for multi-table relationship questions. Check regulatory compliance via `moph` and `nhso` collections (43 files reporting, reimbursement rules). Verify Thai conventions (Buddhist calendar, CID validation, pre-masked fields). Fix semantic mismatches with code comments citing the HOSxP convention. Flag ambiguous intent for user review. (skipped if bms-knowledge-mcp is not available)
- The agent fixes everything it can. Major dependency updates are flagged for user review.
- **Completion rule:** When the QC agent returns its report, proceed to Step 11 **unless** the report contains unfixed build errors, unfixed test failures, or unfixed critical security vulnerabilities. Informational findings, flagged-for-review items, and already-fixed issues do NOT block progression. If uncertain, proceed — the QC agent already fixed what it could.
- **Post-action:** Commit all fixes and push. Message: `fix(speckit): final QC — security, deps, UX consistency, accessibility`
- **Done:** Update task 10 as completed. Output `[Step 10/11] DONE — quality gate passed`

### Step 11 — Merge to Main `[on_failure: STOP]`
- **Progress:** Output `[Step 11/11] Merge — merging to main branch...`
- **Action:** Switch to main branch, merge the feature branch (fast-forward if possible), push main to remote, then clean up the feature branch.
- **Timeout:** 120s
- **Done:** Update task 11 as completed. Output:

> Pipeline complete! Feature merged to main.

---

## Chain Summary

```
Phase 1 (subagent)                          Phase 2 (main context)
──────────────────────────────              ──────────────────────────────
Step 1: brainstorm ──STOP── commit          Step 9:  implement + rolling QC
        + knowledge search (hosxp)                   ┌─ implement task ─┐
Step 2: research ────────── commit                   │  inline QC       │
        + WebSearch + context7                       │  fix → commit    │
Step 3: constitution ─STOP─┐                         └─ next task ──────┘
Step 4: CLAUDE.md sync ───┘ commit          Step 10: final QC agent ── commit
Step 5: specify ──────STOP── commit                  (security/deps/UX/a11y/deploy)
        + knowledge search (hosxp)          Step 11: merge to main + push
Step 6: plan ─────────STOP── commit
Step 7: tasks ────────STOP── commit
Step 8: analyze ──────────── commit
```
