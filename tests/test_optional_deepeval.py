from services.evaluation.optional_deepeval import deepeval_is_missing


def test_accepts_only_the_missing_top_level_deepeval_package() -> None:
    assert deepeval_is_missing(ModuleNotFoundError(name="deepeval"))


def test_rejects_unrelated_missing_module() -> None:
    assert not deepeval_is_missing(ModuleNotFoundError(name="httpx"))
