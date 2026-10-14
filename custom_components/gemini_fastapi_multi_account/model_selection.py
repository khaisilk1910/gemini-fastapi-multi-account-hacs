"""Model-picker helpers that do not depend on the Home Assistant runtime."""

AUTO_MODEL_ID = "gemini-auto"


def model_selector_options(model_ids: list[str]) -> list[dict[str, str]]:
    """Put account-routed Auto first; preserve the names of actual Gemini models."""
    return [
        {
            "label": "Gemini Auto (Google routing)" if name == AUTO_MODEL_ID else name,
            "value": name,
        }
        for name in sorted(model_ids, key=lambda model: model != AUTO_MODEL_ID)
    ]
