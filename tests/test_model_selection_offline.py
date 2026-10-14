"""Auto picker contract without requiring Home Assistant to be installed."""

import importlib.util
from pathlib import Path


def test_auto_option_is_first_without_discarding_real_models():
    path = Path(__file__).resolve().parents[1] / "custom_components/gemini_fastapi_multi_account/model_selection.py"
    spec = importlib.util.spec_from_file_location("hacs_model_selection", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    models = module.model_selector_options(["gemini-pro", "gemini-auto", "gemini-flash"])
    assert models[0] == {"label": "Gemini Auto (Google routing)", "value": "gemini-auto"}
    assert {item["value"] for item in models} == {"gemini-pro", "gemini-auto", "gemini-flash"}
    assert module.model_selector_options(["gemini-flash"]) == [{"label": "gemini-flash", "value": "gemini-flash"}]
