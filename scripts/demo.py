"""Run every fixture ticket through Teller and print what it decided and wrote.

    python scripts/demo.py            # summary table
    python scripts/demo.py --notes    # also print each internal note
"""

import json
import sys
from pathlib import Path

from teller import build_mock_teller

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tickets.json"


def main(show_notes: bool) -> None:
    named = json.loads(FIXTURES.read_text())
    tickets = {str(t["ticket"]["id"]): t for t in named.values()}
    teller = build_mock_teller(tickets)

    print(f"{'fixture':28} {'category':17} {'action':19} {'zone':15} reasons")
    for name, raw in named.items():
        d = teller.process(str(raw["ticket"]["id"]))
        print(f"{name:28} {str(d.category):17} {d.action:19} {d.compliance_zone:15} {', '.join(d.reasons)}")

    if show_notes:
        for update in teller.ticketing.updates:
            print(f"\n----- ticket {update.ticket_id} · move_to={update.move_to} · tags={update.add_tags}")
            print(update.internal_note)


if __name__ == "__main__":
    main("--notes" in sys.argv)
