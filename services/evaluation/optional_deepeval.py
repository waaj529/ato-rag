"""Classify the one optional dependency tolerated by evaluation exports."""


def deepeval_is_missing(error: ModuleNotFoundError) -> bool:
    """Return true only when the optional top-level package is unavailable."""
    return error.name == "deepeval"
