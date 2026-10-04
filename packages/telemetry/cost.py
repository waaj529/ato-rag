"""Model call pricing calculator for OpenTelemetry and Langfuse."""

RATES_PER_MILLION_INPUT_TOKENS: dict[str, float] = {
    "kanon-2-embedder": 0.35,
    "kanon-2-reranker": 0.35,
}

RATES_PER_MILLION_OUTPUT_TOKENS: dict[str, float] = {
    "kanon-2-embedder": 0.0,
    "kanon-2-reranker": 0.0,
}


def calculate_model_cost(
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
) -> float | None:
    """Calculate US dollar cost for a model call."""
    if model not in RATES_PER_MILLION_INPUT_TOKENS:
        return None
    rate_in = RATES_PER_MILLION_INPUT_TOKENS[model]
    rate_out = RATES_PER_MILLION_OUTPUT_TOKENS.get(model, 0.0)
    cost_in = (max(0, input_tokens) / 1_000_000.0) * rate_in
    cost_out = (max(0, output_tokens) / 1_000_000.0) * rate_out
    return round(cost_in + cost_out, 8)
