# Changelog

## 1.0.0

- Specialized for Gemini FastAPI Multi-Account.
- No API network checks during Home Assistant startup.
- Automatic `/v1` URL normalization.
- SDK retries disabled; Docker multi-account failover remains authoritative.
- Aligned with Home Assistant OpenAI SDK `3.10.0`.
- Removed `demoji` and `webcolors`.
- Reduced streaming executor overhead and improved stream error handling.
- Added Vietnamese translation and CI validation.
