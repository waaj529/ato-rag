"""Rate limiting and per-tenant spend quota management."""

import time


class RateLimitExceededError(Exception):
    """Raised when tenant or user exceeds request rate limits."""


class SpendLimitExceededError(Exception):
    """Raised when tenant exceeds dollar budget quota."""


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def acquire(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        history = self._requests.setdefault(key, [])
        # Prune old requests outside window
        self._requests[key] = [t for t in history if t > window_start]
        if len(self._requests[key]) >= self.max_requests:
            raise RateLimitExceededError(
                f"Rate limit exceeded for key '{key}': {len(self._requests[key])}/{self.max_requests} in {self.window_seconds}s"
            )
        self._requests[key].append(now)
        return True


class SpendBudgetManager:
    def __init__(self, default_budget_usd: float = 100.0) -> None:
        self.default_budget = default_budget_usd
        self._budgets: dict[str, float] = {}
        self._spend: dict[str, float] = {}

    def set_budget(self, tenant_id: str, budget_usd: float) -> None:
        self._budgets[tenant_id] = budget_usd

    def record_spend(self, tenant_id: str, cost_usd: float) -> float:
        current = self._spend.get(tenant_id, 0.0)
        budget = self._budgets.get(tenant_id, self.default_budget)
        if current + cost_usd > budget:
            raise SpendLimitExceededError(
                f"Spend limit exceeded for tenant '{tenant_id}': attempted ${cost_usd:.4f} but current ${current:.4f} + cost > budget ${budget:.2f}"
            )
        self._spend[tenant_id] = current + cost_usd
        return self._spend[tenant_id]

    def get_remaining_budget(self, tenant_id: str) -> float:
        budget = self._budgets.get(tenant_id, self.default_budget)
        return max(0.0, budget - self._spend.get(tenant_id, 0.0))
