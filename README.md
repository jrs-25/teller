# Teller

A prototype support triage & resolution agent for Customer Support. Teller sits beside the ticketing system: it reads each new ticket, decides what it is, and writes one internal note (a cited draft reply, or a routing decision with context) for a human to act on. In v1, nothing reaches a member without a CSR sending it.

- **[RFC.md](RFC.md)**: the design. Start here.
- **[CLAUDE.md](CLAUDE.md)**: the working constitution used to steer AI-assisted development.
- **[NOTES.md](NOTES.md)**: decision log and AI Leverage Log candidates.

## Run it

Requires Python 3.11+. No API keys: every external system is mocked.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m pytest -v              # the test suite (also runs in CI)
python scripts/demo.py --notes   # run every fixture ticket and print what Teller wrote
```

## What's here

| Path | What |
|---|---|
| `config/categories/` | One policy file per category, each owned by its team (`.github/CODEOWNERS`) |
| `config/teller.yaml`, `config/compliance_keywords.yaml` | Global settings and the compliance keyword list |
| `src/teller/pipeline.py` | The one shared pipeline; the seam is `_resolve_policy` |
| `src/teller/config.py` | Config loading and the safety floor |
| `src/teller/gate.py` | The safety gate |
| `src/teller/ticketing.py` | Vendor-neutral ticketing adapter, plus a Zendesk mock |
| `src/teller/webhook.py` | The thin new-ticket webhook |
| `tests/fixtures/tickets.json` | Zendesk-shaped tickets with fake "canary" values |

## The safety test

[`tests/test_safety.py`](tests/test_safety.py) and [`tests/test_config.py`](tests/test_config.py) implement rules S1–S17 from RFC §5. Each assertion names the rule it guards, so a breach fails CI with a message like `S1: compliance or gray-zone decision carried a member-facing draft`.

**How we know the tests work:** each safety mechanism was broken on purpose, and the suite caught it.

| Broken on purpose | Caught by |
|---|---|
| Safety gate disabled | S1 (a buggy handler drafting for compliance), S7, gate fails closed |
| Redaction disabled | S5 (canary values in logs, records, ticket writes, model inputs), S6 |
| Keyword tripwire disabled | S1, S2, S4 |
| Send lock 3 removed | S9 |
| Safety floor rule removed | S10 |

The classifier, compliance check, and drafter are deliberately simple rules-based stand-ins behind model-shaped interfaces, as the brief allows. The architecture around them is what's being proven.
