# Execution and acceptance protocol

For this project, Codex directly performs authorized implementation, repair, service-lifecycle, and browser-operation work, then independently verifies the result.

1. Translate every user requirement into small, ordered, independently verifiable stages before changing state.
2. Execute authorized work directly. After each stage, inspect non-sensitive command results and validate the relevant database, API, UI, or Excel outcome.
3. Do not mark a stage complete until acceptance evidence passes. Report the implementation result and acceptance result separately.
4. Once the user has authorized a task, autonomously repair newly discovered in-scope errors. Ask before actions involving secrets, external coordination, destructive data loss, or a material scope expansion.
5. Never expose credentials, DATABASE_URL passwords, SECRET_KEY values, or other secrets in prompts, logs, commits, or reports.

# Browser identity and handoff protocol

This workspace has both Microsoft Edge and Google Chrome in active use. Treat them as distinct browser applications and never infer browser identity from an icon, a tab title, a plugin label, or a returned tab list alone.

**Local frontend/UI acceptance:** When performing local frontend or UI browser acceptance testing and the user has not explicitly specified a browser, Codex may use any controllable browser session (Chrome or Edge) without performing browser identity verification or matching. The strict browser identity requirements below apply only when the user explicitly specifies which browser to use.

Before any browser automation when the user explicitly specifies a browser, the agent must perform its own Windows application-identity check:

1. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\inspect_browser_windows.ps1` and use its `Executable` field as the source of truth: `chrome.exe` means Google Chrome; `msedge.exe` means Microsoft Edge. This bypass applies only to that one inspection process and must not change a system execution-policy setting.
2. Match the target window title from that output with the tab title exposed by the Chrome control integration. A plugin label, browser icon, or a similarly named tab is not sufficient.
3. Record the verified target in the task update as: application, executable, matching title, and tab URL. Do not use another browser or profile as a substitute.
4. Use the Chrome control integration only after it exposes the exact matching tab. If the title or executable does not match, stop and report the mismatch; do not navigate, authenticate, or edit target settings there.
5. Default for this project: when the user says "Chrome", use Google Chrome only; never operate Microsoft Edge unless the user explicitly changes that instruction.

# Frontend acceptance testing requirements

Any work involving frontend code, page layout, interactions, display logic, labels, tables, detail dialogs, or other user-visible changes must complete real browser acceptance testing before the stage can be marked as complete.

1. Code review, static analysis, compilation, build processes, or API endpoint verification cannot substitute for browser acceptance testing.
2. For local frontend/UI acceptance testing where the user has not explicitly specified a browser, browser acceptance may be performed in any controllable browser session (Chrome or Edge) without requiring browser identity verification.
3. When the user explicitly specifies a browser, browser acceptance must be performed in a browser session that complies with the browser identity and handoff protocol above.
4. If no controllable browser session is available or accessible (or no compliant session when identity verification is required), the browser acceptance step must be marked as BLOCKED or incomplete. Do not claim full acceptance has passed.
5. Acceptance includes verifying the feature works as intended in the actual running application, not just that the code compiles or the API responds correctly.
6. Report browser acceptance results separately from code implementation results. State what was tested, in which browser session, and what the observed behavior was.

# Frontend API architecture requirements

The frontend uses one API registry and one request client. These rules apply to all new code and to every file touched during maintenance:

1. Register every backend endpoint in `frontend/src/api/registry.ts` before using it from a page or component.
2. Pages and business components must call domain API modules from `frontend/src/api/`; they must not write backend paths directly.
3. Pages and business components must not import `axios` or use native `fetch` for backend calls.
4. `frontend/src/utils/request.ts` (or its replacement under `frontend/src/api/`) is the only low-level HTTP client.
5. `/api/v1` is configured once in the request client. Callers must use paths relative to that base URL.
6. Every registry entry must declare its key, HTTP method, path, authentication requirement, lifecycle status (`active`, `deprecated`, or `removed`), and description.
7. Endpoint changes must update the registry, domain API wrapper, request/response types, backend route contract, and relevant tests together.
8. Before removing an endpoint or field, run `scripts/check_api_usage.ps1` and confirm that no active caller remains.

The API usage scan is an acceptance check for new work. Existing violations are migration debt and must be reported until migrated; new violations must not be added.
