import json
from pathlib import Path

import pytest

from teller import build_mock_teller
from teller.config import load_config

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "tickets.json").read_text())


def by_id(name: str) -> str:
    return str(FIXTURES[name]["ticket"]["id"])


@pytest.fixture
def tickets():
    return {str(t["ticket"]["id"]): t for t in FIXTURES.values()}


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def teller(tickets, config):
    return build_mock_teller(tickets, config)


def with_stage(config, stage: str, categories=None):
    """A copy of config with rollout_stage set for some or all categories."""
    cats = {
        cid: p.model_copy(update={"rollout_stage": stage})
        if categories is None or cid in categories else p
        for cid, p in config.categories.items()
    }
    return config.model_copy(update={"categories": cats})
