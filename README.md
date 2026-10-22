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

The classifier, compliance check, and drafter are deliberately simple rules-based stand-ins behind model-shaped interfaces, as the brief allows. The architecture around them is what's being proven.
