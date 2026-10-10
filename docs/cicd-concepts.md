# CI, continuous delivery and continuous deployment

| Practice | What happens automatically | Who decides when production changes | In this repo |
|---|---|---|---|
| **Continuous integration (CI)** | Every change (pull request, push) is built and tested against the main line. Broken changes are rejected before merge. | n/a | `ci.yml` jobs `test`, `secret-scan` and `build`. Branch protection requires them before merging to `main`. |
| **Continuous delivery** | Every change that passes CI produces a **releasable artefact** that could go to production at any time. Releasing it is a deliberate, low-effort decision. | A human (an approval, a button) | `ci.yml` `publish` pushes an immutable, attested image for every push to `main` or each version tag. `deploy.yml` releases it after **environment approval**. |
| **Continuous deployment** | Every change that passes the pipeline goes to production with no human step. | The pipeline | Not used here. Turning it on would mean triggering `deploy.yml` from `ci.yml` and removing the required reviewers from `production`. That is only reasonable with strong automated tests, progressive rollout and automatic rollback on bad metrics. |

## Why continuous delivery, not continuous deployment, for this project

- There is no production traffic or alerting yet that could catch a bad release automatically, so a human approval is the safety net.
- Promotion works on **immutable digests**. The approver approves an exact artefact, not "whatever `latest` is right now".
- Rollback uses the same mechanism: approve the previous digest. Rolling back is therefore as practised and as fast as releasing.

## Vocabulary used in interviews

| Term | Meaning |
|---|---|
| **Artefact** | The output of a build that gets deployed (here: an OCI image identified by its `sha256:` digest). |
| **Promotion** | Moving the same artefact from one environment to the next without rebuilding it. |
| **Gate** | A check that must pass before the pipeline continues: tests, scans, approvals. |
| **Trusted event** | A trigger from someone with write access (push or tag), as opposed to a pull request from a fork, which must never get publish credentials. |
