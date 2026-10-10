# Third-party tooling

Every GitHub Action is pinned to a full commit SHA, with the release in a comment. A tag such as `v4` can be moved by whoever controls the action's repository; a commit SHA cannot.

**Why this is not theoretical:** in March 2026, attackers force-pushed most `aquasecurity/trivy-action` tags to malicious commits that stole CI secrets, and published a malicious Trivy binary, v0.69.4 (advisory GHSA-69fq-xp46-6x23). Workflows pinned to SHAs from before the incident were not affected.

**Version selection policy:** use the newest release that is **at least 14 days old** (resolved on 2026-10-10). Dependabot's `cooldown` setting enforces the same delay for future updates.

| Action / tool | Pinned version | Used for | Trust rationale |
|---|---|---|---|
| `actions/checkout` | v7.0.1 `3d3c42e5…` | Checkout (`persist-credentials: false`) | GitHub-maintained |
| `actions/setup-python` | v7.0.0 `5fda3b95…` | Python 3.12 with pip cache | GitHub-maintained |
| `actions/upload-artifact` / `download-artifact` | v7.0.1 `043fb46d…` / v8.0.1 `3e5f45b2…` | Pass the tested image to the publish job | GitHub-maintained |
| `actions/attest-build-provenance` | v4.2.2 `4d101475…` | SLSA provenance for published digests | GitHub-maintained |
| `docker/setup-buildx-action`, `build-push-action`, `login-action`, `metadata-action` | v4.4.1, v7.4.0, v4.6.0, v6.2.0 | Build, registry login, tag computation | Docker Inc. |
| `aquasecurity/trivy-action` | v0.36.0 `ed142fd0…`, Trivy binary v0.74.0 | Image vulnerability gate | Post-incident releases (fixed ≥ 0.35.0); binary version set explicitly |
| `hadolint/hadolint-action` | v3.5.0 `06be81ba…` | Dockerfile lint | Widely used, read-only |
| `trufflesecurity/trufflehog` | v3.97.9 `4dd8831c…` | Secret scan of new commits | Vendor-maintained. SELISE's public pipelines use TruffleHog too. |

| Python package (dev only unless noted) | Purpose |
|---|---|
| fastapi, uvicorn, prometheus-client (**runtime**) | Web framework, ASGI server, metrics exposition |
| pytest, pytest-cov, httpx2 | Tests and coverage. Starlette's TestClient now uses httpx2. |
| ruff | Lint and format |
| pip-audit | Known-vulnerability check of the runtime lock file (PyPA advisory database) |
| PyYAML | Parse workflows in the policy tests |

## Local tools (not in CI)

The project was verified locally with hadolint 2.15.1, shellcheck 0.9.0, actionlint 1.7.12, Trivy 0.74.0 and act 0.2.89. Each was installed from GitHub releases after its SHA-256 checksum was verified.
