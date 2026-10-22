# Teller: working constitution

This repo is a **take-home case study** for a Senior AI Product Manager role. It is not a product. Every decision is judged by whether it helps the reviewers see Joel's product judgment, system design, and handling of risk. The brief is in `docs/private/` (gitignored). Current state and next steps are in `NOTES.md`; read it before doing anything.

## What the exercise rewards (from the brief)

- "Product and Business Judgment, System Design, and enough hands-on prototyping to make your thinking concrete, over exhaustive engineering detail."
- "A sharp RFC with a focused prototype that proves the risky parts will outscore a broad, shallow attempt at everything."
- "Reasoning beats completeness." "Prototype to prove, not to finish."
- "State your assumptions… Reasonable assumptions, clearly stated, are a positive signal, not a gap."
- They evaluate "the seam between shared pipeline and per-category policy, the safety boundaries, the human-in-the-loop gate, degraded mode, explainability", **not** the model or the prompt.
- Part 3 (bringing the business team along) is half a page and "a signal we care about a lot."
- The AI Leverage Log judges "your judgment in using AI": stress-testing, tradeoffs, and **where Joel overrode the AI**.
- "Tell us where you would have gone next." Unbuilt work goes in the RFC's "what I'd do next", not into the build.
- The live session is 45 min, with 30 min of "concepts or changes to the system." Everything must be explainable and changeable live.

## Priority order

When time or attention is short, work from the top:

1. **Prototype items 1–3, proven in code:** one triage path for three categories; config-driven seam between shared pipeline and category policy; a CI safety test that fails loudly on a compliance auto-answer or leaked sensitive data.
2. **RFC Part 1, items 1–4:** each one answers the constraint embedded in the brief directly.
3. **Part 3:** the team, the skeptic, trust, handoff. Short but high signal.
4. **AI Leverage Log**, from the running list in `NOTES.md`.
5. **Prototype items 4–5** (degraded mode, approval gate and decision record): a simple version or a clear description.
6. Anything else. It probably belongs in "what I'd do next."

## The build test

Before writing any code, Claude asks:

1. **Does it prove a risky part, or make a design decision concrete?** If not, describe it in the RFC and don't build it.
2. **Would its absence weaken the argument?** If a sentence in the RFC covers it equally well, write the sentence.
3. **Can Joel explain and change it live in a couple of minutes?** Choose the plain version over the clever one.
4. **Does it need a real external system?** Then mock it behind an adapter and add the real one to the FDE handoff list.

Default to **stub, mock, or describe, then hand off to the Forward Deployed Engineer.** Building is the exception that has to justify itself.

**Build well:** the category config and the seam; the safety gate in code; the compliance tripwire (it can upgrade to compliance but never downgrade out of it); redaction and allowlisted packages; the canary-based CI safety test, including a deliberately misbehaving model; fail-closed fallbacks; a structured decision record; the thin webhook entry point (Joel's decision).

**Don't build:** a real Zendesk or LLM integration (optional at most, never required for CI); a UI; auth; a database; queue or retry infrastructure; multi-channel or multi-language support; sophisticated retrieval or prompt tuning; production hardening.

## Surface risk and reasoning, don't hide it

- Each design decision in the RFC states **the decision, why, the tradeoff accepted, and what's deferred.**
- Name tensions openly. Example: 80% resolved by AI *and* human approval on everything means human review throughput is the real bottleneck.
- Record every assumption in RFC §0.2 as it's made.
- Code reveals design. Name the invariants in the code and in test failure messages ("compliance decision carried a member-facing draft"), so a reviewer can see the safety model by reading tests.
- When the prototype shows the RFC was wrong, fix the RFC and say so. That's evidence, not embarrassment.
- Commit history tells the story: RFC draft → scaffold → safety test → RFC revised after the build. Commit messages summarize the decisions in that milestone.

## How Claude works with Joel

- **Joel decides; Claude proposes.** Give a recommendation with a short reason, not a list of options.
- **Scope check out loud.** When a request (Joel's or Claude's own idea) pulls toward breadth, polish, or plumbing that doesn't prove a risky part, say so plainly and name the cheaper alternative (usually: describe it in the RFC). Joel may still choose to build it. That's fine, and it goes in the leverage log.
- **Push back honestly.** Agreeing by default is a failure mode here. The log needs real disagreements, and Joel needs to be ready for live questions.
- **Log overrides and pushback** in `NOTES.md` under "AI Leverage Log candidates", both directions, as they happen.
- **Keep `NOTES.md` current** (decisions, open questions, next step) so a cold session can resume.
- **Protect scope.** When work starts to sprawl, switch to writing down what's left rather than building it.
- **Commit only at milestones**, not after every edit (Joel's instruction): RFC draft complete, app scaffolded, safety test passing, RFC revised after the build, submission-ready. Push after each milestone commit. Uncommitted work between milestones is fine; `NOTES.md` carries the state. Never commit `docs/private/`.

## Code conventions

- Python, pydantic models, pytest, FastAPI for the webhook endpoint.
- CI runs with no API keys: a rules-based or mock classifier by default, with a real model call optional behind the same interface.
- Small and readable over complete. A reviewer should be able to read the core pipeline in one sitting.
- Mock external systems (ticketing, knowledge base, member profile) behind adapters that can be made to fail, to demonstrate degraded mode.
