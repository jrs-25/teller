"""S10: config can make a category stricter than the safety floor, never looser (RFC §1)."""

import pytest

from teller.config import ConfigError, check_routes, check_safety_floor, load_routes


def change(config, category, **fields):
    cats = dict(config.categories)
    cats[category] = cats[category].model_copy(update=fields)
    return config.model_copy(update={"categories": cats})


def test_the_shipped_config_passes_the_floor(config):
    check_safety_floor(config)  # load_config already ran it; this keeps it explicit


FORBIDDEN = [
    ("compliance", {"member_response_allowed": True}, "member_response_allowed"),
    ("compliance", {"rollout_stage": "send"}, "send"),
    ("general_qa", {"precedence": 100}, "precedence"),
    ("general_qa", {"confidence_threshold": 0.1}, "threshold"),
    ("compliance", {"package_fields": ["summary", "account_number"]}, "package_fields"),
    ("general_qa", {"member_response_allowed": False, "rollout_stage": "send"}, "send"),
]


@pytest.mark.parametrize("category,fields,message", FORBIDDEN)
def test_s10_config_that_breaks_the_floor_fails_to_load(config, category, fields, message):
    with pytest.raises(ConfigError, match=message):
        check_safety_floor(change(config, category, **fields))


def test_s10_compliance_category_must_exist(config):
    cats = {k: v for k, v in config.categories.items() if k != "compliance"}
    with pytest.raises(ConfigError, match="must exist"):
        check_safety_floor(config.model_copy(update={"categories": cats}))


def test_stricter_than_the_floor_is_fine(config):
    check_safety_floor(change(config, "general_qa", confidence_threshold=0.95, rollout_stage="shadow"))


def test_every_destination_is_an_existing_route(config):
    check_routes(config, load_routes("zendesk"))


def test_unknown_destination_fails_to_load(config):
    with pytest.raises(ConfigError, match="not a known route"):
        check_routes(change(config, "product_feedback", destination="nowhere_queue"), load_routes("zendesk"))
