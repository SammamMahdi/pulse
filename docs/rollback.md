# Rollback procedure

**Principle:** a rollback is a deployment of the previous known-good artefact. It never rebuilds from source, because a rebuild can pull in different dependencies, base layers or code.

## 1. Environment tag in the registry (deploy.yml)

1. Open the last successful **Deploy (promote image)** run for the environment. Its summary shows `Previous digest: sha256:...`.
2. Run **Actions → Deploy (promote image) → Run workflow** with:
   - `environment`: the same environment;
   - `digest`: that previous digest.
3. The workflow:
   - re-verifies the old image (pull by digest + smoke test);
   - waits for approval;
   - moves the tag back;
   - checks that the tag resolves to the expected digest.
4. Confirm that the runtime picked it up. For example, `curl .../api/v1/info` should show the old version.

## 2. Docker Compose (local or a single host)

```bash
TAG=1.0.0 docker compose up -d --no-build --wait   # --no-build: deploy the existing image only
curl -s http://127.0.0.1:8000/api/v1/info           # verify "version": "1.0.0"
```

`scripts/rollback-demo.sh 1.0.0 1.1.0` runs the full cycle: deploy 1.0.0, deploy 1.1.0, roll back to 1.0.0, then verify readiness. The recorded output is in `docs/verification.md`.

## 3. Kubernetes (Helm), covered in pulse-helm

```bash
helm history pulse -n pulse      # find the last good REVISION
helm rollback pulse <REVISION> -n pulse --wait
kubectl rollout status deploy/pulse -n pulse
```

## When rollback is not enough

- **Database or schema changes:** rolling back the code does not undo a migration. Use backward-compatible (expand/contract) migrations so the previous version can still run.
- **Bad configuration or secrets:** these live outside the image. Revert the configuration change too.
