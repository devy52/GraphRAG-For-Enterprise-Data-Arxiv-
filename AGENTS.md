# AGENTS.md

## Global Rules

These rules apply by default to every software, research, data, automation, or product project in this repository. Project-specific rules may add constraints, but should not silently weaken these rules unless explicitly documented and approved.

## Communication

- Be terse. No unnecessary preamble or repetition.
- Give one concrete recommendation unless comparison is requested.
- Do not start implementation work until the user explicitly asks for it.
- If the user asks for explanation, review, or planning only, do not modify code.
- When editing code, report a per-file breakdown of what changed:
  `file.py — added X, removed Y, changed Z`.
- Never claim something works, is fixed, or is tested unless you actually ran it and observed the result.
- Distinguish clearly between verified facts, inference, assumptions, and unverified expectations.
- If something is uncertain, broken, incomplete, or unverified, say so explicitly.
- Keep responses structured and avoid cluttered prose.

## Documentation Gate

For any substantial project or feature, establish the project's documentation baseline before implementation. The required documents should match the project's scope, but normally include:

- `PRD.md`
- `TRD.md`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `FLOWS.md`
- `CODEBASE_MAP.md`
- `DECISIONS.md`
- `TASKS.md`
- `HARNESS.md`, `FENCE.md`, or `GUARDRAILS.md` where applicable
- `TESTS-INSTRUCTIONS.md`
- `ONTOLOGY.md` for graph/relational domains where applicable
- `README.md` at the repository root

Before starting substantial implementation:

- Confirm the required documentation baseline exists.
- Stop and name missing documents rather than silently scaffolding around the gap.
- If documents conflict with one another or with the user's request, surface the conflict before coding.
- Keep a top-level navigation banner in canonical documents that interlinks the relevant canonical document set.
- Use Mermaid diagrams in Markdown so diagrams remain diffable and editable.

Small isolated fixes may use a smaller documentation footprint when the full document set would not add meaningful clarity; record that exception when it materially affects traceability.

## Multi-Agent Handoff

Before starting work:

- Read `TASKS.md`, `DECISIONS.md`, and `CODEBASE_MAP.md` when they exist.
- Read the relevant project documentation and inspect the current implementation before modifying it.
- Check for context left by other agents or tools.
- Do not overwrite or discard another agent's work without understanding its purpose.
- Treat `TASKS.md` as the active handoff source, especially its `Current state / Next step` block.
- Update that block at the end of the session so the next agent can resume without guessing.

## Change Control

- Do not make a code change that contradicts `PRD.md`, `TRD.md`, `DESIGN.md`, or `ARCHITECTURE.md` without resolving the contradiction first.
- When a change affects an architectural or design decision, record the decision in `DECISIONS.md` before or with the implementation.
- Preserve older decisions; supersede them explicitly rather than deleting history.

## Living Documentation

Keep documentation synchronized with implementation changes.

- Update `README.md` when user-facing behavior, setup, usage, or project status changes.
- Update `TASKS.md` when work starts, changes state, or finishes.
- Update `DECISIONS.md` for technical or design decisions.
- Update `CODEBASE_MAP.md` whenever files or directories are created, renamed, moved, or substantially refactored.
- Update other canonical documents whenever their documented behavior becomes stale.
- Do not leave known documentation drift unresolved at the end of a task.

## DECISIONS.md

Every meaningful technical or design decision gets an entry containing:

- Date
- Title
- Status: `proposed`, `accepted`, or `superseded`
- Context: problem and constraints
- Options considered: realistic alternatives
- Trade-off matrix covering relevant criteria such as cost, complexity, performance, maintainability, lock-in, reliability, or risk
- Decision and rationale
- Consequences: what becomes easier, harder, or constrained
- `Supersedes` / `Superseded-by` links when applicable

If an important choice is made mid-build and is not represented, stop before continuing implementation and record it.

## Planning and Execution

For work that is more than a small edit:

1. State the plan briefly.
2. Identify assumptions, constraints, and verification checkpoints.
3. Implement in small, verifiable steps.
4. Run the relevant test or validation after each meaningful step.
5. Report the actual result before proceeding to the next step.

Do not hide failing tests, broken imports, warnings that materially affect the result, or unhandled cases.

When something fails:

- Show the actual error or relevant output.
- State whether it was fixed, intentionally left unresolved, or requires a decision.

Do not claim completion based only on static inspection when execution is required for verification.

## Command Execution

- Prefer running terminal commands directly when the environment permits.
- Use the project's virtual environment for Python execution and testing (for example `.venv`).
- Do not use the global Python interpreter when a project virtual environment exists.
- If a command must be given to the user, include one line explaining what it does.
- Do not invent CLI commands, flags, configuration keys, or library APIs. Inspect documentation or the installed code first when uncertain.

## Environment and Secrets

- Never print, log, expose, or commit secret keys, credentials, tokens, private certificates, or `.env` files.
- Keep secrets out of generated reports, logs, screenshots, and archives.
- When creating archives or review bundles, exclude virtual environments, database binaries, caches, build artifacts, and credentials unless explicitly required.
- Verify ignore rules before committing generated or environment-specific files.

## Code Standards

Apply the language and framework standards appropriate to the project.

For Python projects:

- Follow PEP 8.
- Use type hints on functions.
- Use docstrings on public functions.
- Prefer named constants over unexplained magic numbers.
- Use explicit error handling rather than silent failure or bare `except`.

For any language:

- Prefer clear, maintainable interfaces over unnecessary cleverness.
- Reuse existing architectural boundaries where appropriate.
- Create a new module when it establishes a meaningful boundary; do not fragment the codebase merely to satisfy a rule.
- Keep comments and documentation synchronized with behavior.

## Code Comprehensibility and Detailed Comments

The codebase should be understandable to a new engineer, researcher, reviewer, or maintainer without requiring them to reverse-engineer the project's intent from implementation details alone. Documentation and comments are part of the implementation quality, not optional decoration.

- Every module should have a clear header comment or module documentation stating its purpose, inputs, outputs, and where it fits in the architecture.
- Every public class, function, API, service, or major component should explain what it does, what it expects, what it returns or changes, and any important constraints.
- Non-trivial logic should contain detailed step-by-step comments explaining the reasoning and **why** the implementation takes that path, not merely restating the code.
- Explain domain-specific concepts, abbreviations, algorithms, invariants, compatibility workarounds, performance decisions, and unusual edge-case handling where a reader would otherwise need to infer them.
- Complex workflows should have comments or nearby documentation that explain the sequence of operations and how data moves through the system.
- When a decision depends on an external limitation, historical bug, benchmark finding, or architectural constraint, document that reason near the code and link to the relevant decision or design document when practical.
- Comments should answer the questions a future maintainer is likely to ask: **What is this? Why is it here? Why is it done this way? What must not be changed casually?**
- Avoid comments that merely translate obvious syntax into English. Prefer explanatory comments about intent, assumptions, invariants, and consequences.
- Update comments whenever behavior changes; stale comments are treated as documentation defects.
- Use examples in comments or docstrings when an interface, data structure, query, or algorithm is difficult to understand from the signature alone.
- Keep detailed comments factual and concise enough to remain maintainable; detail should increase understanding, not create noise.

## Testing and Verification

- Test behavior at the level appropriate to the change.
- Prefer focused tests first, then broader regression tests.
- Preserve a reproducible baseline for benchmark or performance work.
- When comparing experiments, change one meaningful variable at a time whenever practical.
- Record the exact configuration, dataset/version, model/version, and environment assumptions needed to reproduce important results.
- Do not silently replace ground truth, acceptance criteria, or benchmark definitions after seeing results.
- Treat proxy metrics as proxies; do not label them as accuracy or truth unless the evaluation actually establishes that claim.

## Research and Benchmark Integrity

For research, evaluation, or benchmark-heavy projects:

- Freeze baselines before causal comparisons.
- Separate retrieval, evidence availability, generation, evaluation, and infrastructure effects where possible.
- Preserve raw evidence and per-case audit information for important experiments.
- Pre-register important thresholds or decision rules when practical.
- Do not tune an intervention against the test set and then present the tuned result as an unbiased estimate.
- Distinguish observed performance from theoretical ceilings, oracle controls, and hypotheses.
- Report negative results and failed gates rather than hiding them.
- Do not overstate causal conclusions beyond what the experiment isolates.

## Naming and Normative Language

Use precise language.

- Prefer clear, testable requirements over vague wording.
- Avoid unnecessary absolute language in explanatory documentation.
- Use normative terms such as `MUST`, `SHOULD`, or `MAY` when a requirement, interface contract, safety condition, or invariant genuinely requires them.
- When uncertainty exists, express it explicitly instead of replacing it with false certainty.

## End-of-Task Checklist

Before finishing a substantive task:

- Verify the requested change or analysis.
- Run the relevant tests or validation.
- Report actual results and any unresolved issues.
- Update affected living documents.
- Update `CODEBASE_MAP.md` if repository structure changed.
- Update `TASKS.md` with the current state and next step.
- Record technical/design decisions in `DECISIONS.md` when applicable.
- State which documents were updated. If none were updated, state why.

## Default Principle

Optimize for truthful, reproducible, auditable progress rather than apparent completion.
