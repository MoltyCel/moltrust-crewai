# Changelog

All notable changes to `moltrust-crewai` are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [0.1.2] — 2026-07-01

### Added
- Branded `User-Agent` header (`moltrust-crewai/<version>`) on every trust-score
  request, so MolTrust can attribute API traffic to the framework
  integration. Sent in both keyless (Tier 1) and keyed (Tier 2) modes.

## [0.1.1] — 2026-07-01

### Fixed
- Classic license metadata for PyPI compatibility: `license = { text = "MIT" }`
  emits `License: MIT` instead of `License-Expression: MIT`.
- Suppress hatchling's `License-File` metadata generation via `license-files = []`
  (PEP 639) — verified: built METADATA no longer carries a `License-File` entry.

## [0.1.0] — 2026-07-01

Initial release. Skeleton + working code (not yet published to PyPI).

### Added
- `MolTrustGuardrail` — trust verification via CrewAI 1.x hooks
  (`crewai.hooks.register_before_tool_call_hook` /
  `register_before_llm_call_hook`).
  - `before_tool_call` checks the calling agent's MolTrust trust score against
    `min_score`; returns `False` to block per the CrewAI hook contract.
  - `action` modes: `block` | `warn` | `log` | `raise`.
  - DID resolution via `agent_did_map` or `tool_input[did_key]`.
  - `install()` / `uninstall()` lifecycle + context-manager support.
  - Fails open on registry/transport errors; treats unregistered agents as
    failing the check.
- `TrustClient` — direct HTTP client for `GET /skill/trust-score/{did}` (the
  0–100 behavioral `trust_score`; returns `None` when `withheld`/`null`).
  Authenticated with `X-API-Key`. (Uses `requests`, not the `moltrust` SDK, so
  it reads the 0–100 trust score rather than the SDK's 0–5 reputation average.)
- Exceptions: `MolTrustCrewAIError`, `AgentNotRegistered`, `TrustCheckFailed`.
- Mock-based test suite (no live API calls).
