# Changelog

## 1.2.1

- Fix Home Assistant 2026.10 startup failure caused by the integration requirement `openai>=2.45.0,<3` conflicting with Home Assistant Core's `openai==3.10.0` package constraint.
- Widen the compatible SDK range to `openai>=2.45.0,<4`, allowing Home Assistant to use the OpenAI SDK version pinned by Core instead of forcing a conflicting major version.
- No API, entity, conversation, AI Task, reload-button, or backend-routing behavior changes from 1.2.0.

## 1.2.0

- Add a translated **Reload integration** button entity to every loaded config entry.
- Add the admin action `gemini_fastapi_multi_account.reload`, registered at domain setup so it remains available even when a config entry is `Not loaded`.
- Use Home Assistant `async_schedule_reload()` for button, action, and update-listener reloads to cancel pending setup retries and avoid reload races.
- Reload action targets all enabled Gemini FastAPI Multi-Account config entries and reports a clear validation error if none are reloadable.


## 1.1.0

- Increase OpenAI-compatible request timeout from 120s to 145s for Gemini FastAPI V4 failover headroom.
- Generate a unique Home Assistant-side request ID for every backend chat/tool iteration and image request.
- Send the ID as `X-Request-ID`, which Gemini FastAPI V4 reuses in backend scheduler/failover logs.
- Add `request_id` to Home Assistant start/completion/error logs for direct cross-log correlation.
- Keep OpenAI SDK retries disabled (`max_retries=0`); backend multi-account failover remains authoritative.

## 1.0.3

- Fix Hassfest manifest key ordering.
- Fix Home Assistant exception translation schema for `unsupported_attachment_type`.
- Apply the same exception mapping format to English, Vietnamese, and source translation files.
- No API behavior changes from 1.0.2.

## 1.0.2

- Fixed config-flow 500 caused by an incompatible OpenAI SDK pin.
- Changed the SDK requirement from `openai==3.10.0` to `openai>=2.45.0,<3`, avoiding the OpenAI 3.x conflict seen on Home Assistant 2026.9.x while retaining the broader HACS compatibility floor.
- Changed `pylatexenc` to a compatible range `>=2.11,<3`.
- Config flow now uses Home Assistant's standard `voluptuous` schema directly.
- Removed unnecessary OpenAI platform-header warm-up from Home Assistant startup.
- Kept API validation out of Home Assistant startup; server connectivity is checked only when the user submits the config form.

## 1.0.1

- Added local Home Assistant brand icon at `custom_components/gemini_fastapi_multi_account/brand/icon.png`.
- Icon is PNG, exactly 250x250 px, with transparent outer corners.
- Home Assistant 2026.3+ can load this icon directly from the custom integration without a separate brands repository.

## 1.0.0

- Specialized for Gemini FastAPI Multi-Account.
- No API network checks during Home Assistant startup.
- Automatic `/v1` URL normalization.
- SDK retries disabled; Docker multi-account failover remains authoritative.
- Uses an OpenAI-compatible SDK client (dependency compatibility corrected in 1.0.2).
- Removed `demoji` and `webcolors`.
- Reduced streaming executor overhead and improved stream error handling.
- Added Vietnamese translation and CI validation.
