class DependencyError(Exception):
    """A downstream dependency (model, knowledge base, ticketing API) failed or timed out."""


class VersionConflict(Exception):
    """The ticket changed between Teller reading it and writing to it (RFC §3)."""


class LockedOperation(Exception):
    """A member-visible write was attempted without all three locks open (RFC §3)."""
