# Verification evidence

- **Environment:** Windows 11, WSL2 Ubuntu 24.04, Docker Engine 29.8.1 (Compose 5.5.1), Python 3.12.
- **Date:** 2026-10-10.
- **Tools:** ruff 0.17.0, pytest 9.1.1, pip-audit 2.10.1, hadolint 2.15.1, shellcheck 0.9.0, actionlint 1.7.12, Trivy 0.74.0, TruffleHog 3.97.9, act 0.2.89.
- **Full logs:** `evidence/test-results/` and `evidence/execution-logs/` folders.

**Status labels:**
- **Executed successfully:** the behaviour was run and observed.
- **Statically validated:** checked without being executed.
- **Blocked by environment:** could not run here, with the reason.

## Summary

| Requirement | Status | Evidence |
|---|---|---|
| App tests pass (46) with coverage ≥ 90% | Executed successfully | §1 |
| Lint: ruff, hadolint, shellcheck, actionlint | Executed successfully | §1, §6 |
| Container starts, healthcheck healthy, endpoints respond, non-root | Executed successfully | §2 |
| Broken container startup is detected | Executed successfully | §2 |
| Dependency and image vulnerability scanning | Executed successfully | §3 |
| Secret scanning | Executed successfully | §3 |
| CI workflow runs on a pull request event | Executed successfully **with act, locally**: test and secret-scan jobs succeeded; build job succeeded through smoke and broken-start checks | §4 |
| Deliberately failing test blocks the pipeline | Executed successfully (act) | §5 |
| No publishing from pull requests; minimal token scopes; SHA pins | Executed successfully (policy tests + mutation check) | §6 |
| Compose deployment and rollback | Executed successfully | §7 |
| Trivy step *inside act* | Blocked by environment: act provides no `github.token` for `setup-trivy`. The same Trivy version and flags were run directly (§3). | §4 |
| GitHub-hosted runs, GHCR push, provenance attestation, environment approval | Blocked by environment (repo not pushed). Statically validated (actionlint, policy tests). | §6 |

## 1. Lint and unit tests

```
$ ruff check . && ruff format --check .
All checks passed!
11 files already formatted
$ pytest --cov
Name                   Stmts   Miss Branch BrPart  Cover
app/config.py             52      1     16      1    97%
app/faults.py             50      0      6      0   100%
app/main.py              102      3     16      0    97%
app/observability.py      37      1      4      1    95%
TOTAL                    241      5     42      2    98%
Required test coverage of 90.0% reached. Total coverage: 97.53%
46 passed
```

## 2. Container smoke test and broken-start detection (`scripts/smoke-test.sh`)

```
[smoke] starting pulse-api:1.0.0 as smoke-1793-8393
[smoke] healthy; probing http://127.0.0.1:32768
[smoke] GET /health -> 200
[smoke] GET /ready -> 200
[smoke] GET /api/v1/primes/10 -> 200
[smoke] GET /api/v1/primes/-1 -> 422
[smoke] metrics exposed
[smoke] running as uid 10001 (non-root)
[smoke] PASS
```

The same image started with `MAX_PRIME_LIMIT=not-a-number` must make the smoke test **fail**, and it does:

```
[smoke] FAIL: container stopped during startup
[smoke] container state: exited exit=1 health=unhealthy
    app.config.ConfigError: MAX_PRIME_LIMIT must be an integer, got 'not-a-number'
exit=1
```

Image facts: 202 MB, `User=10001:10001`, a HEALTHCHECK is defined, and there is no `pip` in the runtime venv.

## 3. Scanning

- **pip-audit:** `No known vulnerabilities found`, on the runtime lock file.
- **Trivy image gate** (`--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`): 0 findings, exit 0. Every OS and Python package layer reports 0.
- **Trivy informational scan** (all severities, including unfixed): 172 findings: HIGH 44, MEDIUM 63, LOW 62, UNKNOWN 3. Only 8 have a fix available (LOW 1, MEDIUM 5, UNKNOWN 2). The 44 HIGH findings are Debian 13 packages with no patched version yet. That is why the gate uses `--ignore-unfixed`: it blocks the build on what can be fixed now and reports the rest.
- **Trivy config** (Dockerfile): 0 misconfigurations.
- **TruffleHog** (git history, `--results=verified,unknown`): `verified_secrets: 0, unverified_secrets: 0`.

## 4. CI workflow executed locally with act (pull_request event)

This is the workflow exactly as committed, run with `catthehacker/ubuntu:act-24.04` runner images. It is *not* a GitHub-hosted run.

```
[CI/Lint and unit tests     ]   | 46 passed in 4.29s
[CI/Lint and unit tests     ]   ✅  Success - Main Dependency vulnerability audit
[CI/Lint and unit tests     ]   ✅  Success - Main Shellcheck
[CI/Lint and unit tests     ]   ✅  Success - Main Dockerfile lint
[CI/Lint and unit tests     ] 🏁  Job succeeded
[CI/Secret scan (TruffleHog)]   ✅  Success - Main Fail on verified or unverifiable credentials
[CI/Secret scan (TruffleHog)] 🏁  Job succeeded
[CI/Build, smoke test and scan image]   ✅  Success - Main Build image
[CI/Build, smoke test and scan image]   | [smoke] PASS
[CI/Build, smoke test and scan image]   ✅  Success - Main Smoke test (container must start healthy and serve)
[CI/Build, smoke test and scan image]   ✅  Success - Main Broken startup must be detected
[CI/Build, smoke test and scan image]   ❗  ::error::Input required and not supplied: token
[CI/Build, smoke test and scan image]   ❌  Failure - Main Vulnerability scan (fail on fixable HIGH/CRITICAL)
```

The last failure comes from act: GitHub provides `github.token` automatically, act does not. The real GitHub token was deliberately not passed into local action containers. Trivy itself was verified in §3.

## 5. A failing test blocks the pipeline (act)

An off-by-one bug was injected into the prime counter (`return sum(sieve) + 1, ...`) in a throwaway copy of the repo:

```
FAILED tests/test_endpoints.py::test_primes_endpoint[10-4-7]
FAILED tests/test_endpoints.py::test_count_primes_matches_known_value - assert (78499, 999983) == (78498, 999983)
5 failed, 32 passed
❌  Failure - Main Unit tests with coverage gate (90%)
🏁  Job failed
```

The `build` job (`needs: test`) never started, so no image was built, scanned or published.

## 6. Pipeline policy as tests, with a mutation check

`tests/test_workflow_policy.py` asserts:
- read-only default permissions;
- SHA-pinned actions;
- `persist-credentials: false` on checkout;
- `publish` runs only on push;
- `packages: write` only in `publish`;
- promotion gated by an environment.

To prove the tests can fail, the workflow was weakened five ways in a copy of the repo:

```
caught: publish allowed on any event
caught: action pinned to a mutable tag
caught: checkout persists credentials
caught: workflow-wide write token
caught: packages:write granted to build job
```

`actionlint` on both workflows: no findings.

## 7. Compose deploy and rollback (`scripts/rollback-demo.sh 1.0.0 1.1.0`)

```
--- deploying pulse-api:1.0.0
api       pulse-api:1.0.0   Up 11 seconds (healthy)
running version: 1.0.0
--- deploying pulse-api:1.1.0
api       pulse-api:1.1.0   Up 10 seconds (healthy)
running version: 1.1.0
--- simulated bad release detected; rolling back to 1.0.0
api       pulse-api:1.0.0   Up 14 seconds (healthy)
running version: 1.0.0
readiness after rollback: OK
```

## Not yet demonstrated (needs the repo on GitHub)

- A pull request on GitHub-hosted runners showing the `publish` job as *skipped*.
- A push to `main` publishing `ghcr.io/sammammahdi/pulse-api:sha-…` with a provenance attestation.
- `deploy.yml` pausing for a required reviewer on `production`.

To reproduce after pushing:
1. Open a PR.
2. Merge it.
3. Run **Deploy (promote image)** with the digest from the CI summary.
