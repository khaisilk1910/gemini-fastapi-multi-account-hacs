"""Model picker support independent of the Home Assistant runtime.

The gateway is the authority on supported models.  When listing fails or the
backend returns no models, keep the picker usable with common *candidates*;
this fallback is not a promise that the account/server supports every option.
"""

AUTO_MODEL_ID = "gemini-auto"
FALLBACK_MODEL_IDS = (
    AUTO_MODEL_ID,
    "gemini-flash",
    "gemini-flash-lite",
    "gemini-pro",
)


def model_selector_options(
    model_ids: list[str], selected_model: str | None = None
) -> list[dict[str, str]]:
    """Return unique choices, preserving current selection and avoiding empty menus.

    Use the server list if it is nonempty; otherwise expose a small stable
    fallback. A missing Auto ID in a *nonempty* server response is not invented.
    """
    available = list(dict.fromkeys(
        model_id.strip()
        for model_id in model_ids
        if isinstance(model_id, str) and model_id.strip()
    ))
    if not available:
        available = list(FALLBACK_MODEL_IDS)
    if isinstance(selected_model, str) and selected_model.strip():
        selected_model = selected_model.strip()
        if selected_model not in available:
            available.append(selected_model)

    return [
        {
            "label": "Gemini Auto (Google routing)" if name == AUTO_MODEL_ID else name,
            "value": name,
        }
        for name in sorted(available, key=lambda name: (name != AUTO_MODEL_ID, name))
    ]
