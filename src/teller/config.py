"""Loads category policy and enforces the safety floor (RFC §1).

Config can make a category stricter than the floor, never looser. A config that
breaks the floor raises ConfigError at load time, so the deploy (and CI) fails.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from teller.models import CategoryPolicy

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

# Fields a context package can contain. Each is built from redacted data only
# (see handlers.PACKAGE_BUILDERS). A category may only allowlist these.
SAFE_PACKAGE_FIELDS = {"category", "summary", "compliance_signals", "intake_ref"}

COMPLIANCE = "compliance"


class ConfigError(Exception):
    pass


class ComplianceBands(BaseModel):
    route_at: float
    gray_at: float


class KnowledgeBaseSettings(BaseModel):
    min_relevance: float
    stale_after_days: int


class GlobalSettings(BaseModel):
    auto_send_enabled: bool
    compliance_check: ComplianceBands
    knowledge_base: KnowledgeBaseSettings
    max_write_attempts: int


class TellerConfig(BaseModel):
    settings: GlobalSettings
    categories: dict[str, CategoryPolicy]
    compliance_keywords: list[str]
    version: str


def load_config(config_dir: Path = CONFIG_DIR) -> TellerConfig:
    settings = GlobalSettings(**_read(config_dir / "teller.yaml"))
    keywords = _read(config_dir / "compliance_keywords.yaml")["keywords"]
    categories = {}
    for path in sorted((config_dir / "categories").glob("*.yaml")):
        policy = CategoryPolicy(**_read(path))
        categories[policy.id] = policy
    config = TellerConfig(
        settings=settings,
        categories=categories,
        compliance_keywords=keywords,
        version=_fingerprint(config_dir),
    )
    check_safety_floor(config)
    return config


def check_safety_floor(config: TellerConfig) -> None:
    """Raise ConfigError if any category loosens the shared safety floor."""
    cats = config.categories
    if COMPLIANCE not in cats:
        raise ConfigError("safety floor: the compliance category must exist")
    compliance = cats[COMPLIANCE]

    if compliance.member_response_allowed:
        raise ConfigError("safety floor: compliance must have member_response_allowed: false")
    if compliance.rollout_stage == "send":
        raise ConfigError("safety floor: compliance can never be set to rollout_stage: send")

    for policy in cats.values():
        if policy.id != COMPLIANCE:
            if policy.precedence >= compliance.precedence:
                raise ConfigError(
                    f"safety floor: {policy.id} precedence must be below compliance's"
                )
            if policy.confidence_threshold < compliance.confidence_threshold:
                raise ConfigError(
                    f"safety floor: {policy.id} threshold must not be below compliance's"
                )
        if policy.rollout_stage == "send" and not policy.member_response_allowed:
            raise ConfigError(
                f"safety floor: {policy.id} cannot use send without member_response_allowed"
            )
        unknown = set(policy.package_fields) - SAFE_PACKAGE_FIELDS
        if unknown:
            raise ConfigError(
                f"safety floor: {policy.id} package_fields not allowed: {sorted(unknown)}"
            )


def _read(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _fingerprint(config_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(config_dir.rglob("*.yaml")):
        digest.update(path.read_bytes())
    return f"cfg-{digest.hexdigest()[:10]}"
