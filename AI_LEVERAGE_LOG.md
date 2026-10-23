# AI Leverage Log

I used Claude Code (Opus, in VS Code) as design partner and builder. Before any design work, I had Claude turn the brief into a working constitution ([CLAUDE.md](CLAUDE.md), committed): what the exercise rewards, a priority order, a "build test" that defaults every feature to stub, describe, or hand off unless it proves a risky part, and a standing instruction to flag scope creep and disagree rather than agree. Decisions and disagreements were recorded as they happened in [captains-log.md](captains-log.md). I wrote the RFC first and used it as the build spec, so its safety rules became the test names. I used Claude Fable 5.1 in a separate session to critique the drafts of this log and Part 3, as a second opinion from a model that hadn't been in the build.

The judgment calls that mattered most were where I overrode or redirected Claude:

- Claude first treated the ticketing system as a box on a diagram. I pushed on how Teller reads from and writes to a system CSRs use all day, which produced "beside, not in front" and the design's biggest safety point: a public comment emails the member, so Teller's everyday writes can't post one.
- Claude proposed watching follow-up messages for late compliance concerns. I rejected that as an open-ended set of edge cases and noted the same race exists between fetch and post, so we replaced it with one rule: only write to the version of the ticket Teller read.
- From a similar help-center project for claims processors, I knew ingestion is a project in itself and that articles go stale, so we wrapped the existing search and added stale-content safeguards Claude hadn't proposed.
- Claude let the member profile service drop out of v1 without stating the cost. I pushed on it, and the RFC now says plainly that it's the path to resolving account issues, and so to the 80% goal.
- When Claude recommended a real LLM call for the drafter, I stopped the build partway: for this brief it would have been an LLM rabbit hole, and deliberately broken stand-ins prove the safety design better.
