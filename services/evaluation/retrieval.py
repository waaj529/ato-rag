"""Passage-level Recall@K grading for the provisional retrieval benchmark."""

from dataclasses import dataclass, field

from services.retrieval import SearchResult


RECALL_CUTOFFS = (1, 5, 10, 20, 60, 100)


def relevant_rank(case: dict, result: SearchResult) -> int | None:
    if case.get("must_abstain"):
        return 1 if not result.chunks else None
    passages = case.get("expected_passages") or []
    for rank, retrieved in enumerate(result.chunks, start=1):
        candidate = retrieved.candidate
        for passage in passages:
            if candidate.document_id != passage.get("document_id"):
                continue
            if candidate.version_id != passage.get("version_id"):
                continue
            locator = candidate.source_locator
            if locator.get("section_id") != passage.get("section_id"):
                continue
            start, end = locator.get("char_start"), locator.get("char_end")
            if isinstance(start, int) and isinstance(end, int):
                if start <= passage.get("char_start", -1) and end >= passage.get("char_end", -1):
                    return rank
            elif locator.get("table_id") == passage.get("table_id"):
                return rank
    return None


@dataclass
class RetrievalBenchmark:
    total: int = 0
    positive: int = 0
    abstention: int = 0
    ranks: list[int | None] = field(default_factory=list)
    positive_ranks: list[int | None] = field(default_factory=list)
    abstention_ranks: list[int | None] = field(default_factory=list)

    def add(self, case: dict, result: SearchResult) -> int | None:
        rank = relevant_rank(case, result)
        self.total += 1
        self.ranks.append(rank)
        if case.get("must_abstain"):
            self.abstention += 1
            self.abstention_ranks.append(rank)
        else:
            self.positive += 1
            self.positive_ranks.append(rank)
        return rank

    def report(self) -> dict:
        def recalls(values: list[int | None]) -> dict[str, float]:
            denominator = len(values) or 1
            return {f"recall_at_{cutoff}": sum(
                rank is not None and rank <= cutoff for rank in values
            ) / denominator for cutoff in RECALL_CUTOFFS}

        return {
            "cases": self.total,
            "positive_cases": self.positive,
            "abstention_cases": self.abstention,
            "overall": recalls(self.ranks),
            "positive": recalls(self.positive_ranks),
            "abstention_accuracy": sum(rank is not None for rank in self.abstention_ranks)
            / (len(self.abstention_ranks) or 1),
        }
