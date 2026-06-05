# Payd Connect v2 Sandbox GHCR Autodeploy Blocker

Date: 2026-06-05
Owner: Sentinel/platform
Project: `payd-connect-v2-sandbox`
Domain: `connect-v2-sandbox.payd.money`
Connect repository: `getpayd-tech/payd-labs-connect-v1`
Current Connect `v2` SHA at triage: `5ff3f40470df5bd8f9df5b92ecae391a68ae221d`

## Summary

Payd Connect v2 has a Sentinel sandbox deployment workflow at
`getpayd-tech/payd-labs-connect-v1/.github/workflows/deploy-v2-sentinel.yml`.
The workflow triggered after Connect PR #192 merged to `v2`, but the run failed
before Sentinel received a deployment webhook because several GHCR image pushes
returned `403 Forbidden`.

This is now Sentinel-owned operational follow-up because the Connect repo wiring
for dashboard, hosted, Noah simulator, and Blockradar simulator has already
merged. The remaining work is package access repair, Sentinel deployment
verification, and a Sentinel deploy-system follow-up for custom multi-image
compose stacks.

No production mutation was performed during this triage. Do not deploy, rotate
tokens, edit DNS, or change host env without an explicit approval window.

## Impact

The live sandbox still serves the older route map:

| Route | Current result | Expected after fix |
| --- | --- | --- |
| `/healthz` | `200` | `200` |
| `/readyz` | `200` | `200` |
| `/dashboard/` | `501` | `200` |
| `/hosted/` | `501` | `200` |
| `/_health/noah-sim/healthz` | `404` | `200` |
| `/_health/blockradar-sim/healthz` | `404` | `200` |

Docs and the completion tracker are already live on the sandbox. This incident
does not prove or block provider-live acceptance by itself. Noah and Blockradar
provider-live acceptance still needs real provider sandbox credentials, webhook
keys, callback windows, and Team C evidence.

## Evidence

- Connect PR with merged Sentinel full-surface wiring:
  <https://github.com/getpayd-tech/payd-labs-connect-v1/pull/192>
- Failed workflow run:
  <https://github.com/getpayd-tech/payd-labs-connect-v1/actions/runs/26975162423>
- Failed run head SHA:
  `870d56a2e58ce6e8dcc576347d6c8d2fa8914851`
- Current `v2` SHA at triage:
  `5ff3f40470df5bd8f9df5b92ecae391a68ae221d`
- Connect status note:
  `docs-internal/status/2026-W23-tech-lead-session-45.md`
- Connect tracker gate:
  `docs-internal/tracker/v0-expanded-acceptance.yaml`, gate `sentinel-full-surface`

The workflow requested the correct baseline permissions:

```yaml
permissions:
  contents: read
  packages: write
```

The failed job log showed a successful GHCR login, then a push failure like:

```text
failed to push ghcr.io/getpayd-tech/payd-connect-v2-ledger:<sha>:
unexpected status from HEAD request ... 403 Forbidden
```

## Package Metadata Finding

The packages that pushed successfully were linked to the Connect repository:

| Package | Repository metadata |
| --- | --- |
| `payd-connect-v2-api-gateway` | `getpayd-tech/payd-labs-connect-v1` |
| `payd-connect-v2-noah-sim` | `getpayd-tech/payd-labs-connect-v1` |
| `payd-connect-v2-blockradar-sim` | `getpayd-tech/payd-labs-connect-v1` |
| `payd-connect-v2-dashboard-ui` | `getpayd-tech/payd-labs-connect-v1` |
| `payd-connect-v2-hosted-ui` | `getpayd-tech/payd-labs-connect-v1` |

The packages that failed were private packages with no linked repository:

| Package | Repository metadata |
| --- | --- |
| `payd-connect-v2-choice-sim` | `null` |
| `payd-connect-v2-ledger` | `null` |
| `payd-connect-v2-quikk-sim` | `null` |
| `payd-connect-v2-admin-ui` | `null` |
| `payd-connect-v2-provider-gateway` | `null` |
| `payd-connect-v2-treasury-recon` | `null` |
| `payd-connect-v2-docs-ui` | `null` |
| `payd-connect-v2-identity` | `null` |
| `payd-connect-v2-admin-api` | `null` |

The likely root cause is package-level Actions access, not the workflow YAML.
`GITHUB_TOKEN` can create or push packages associated with its workflow
repository, but it cannot update unrelated private packages unless the package
grants the workflow repository access.

Use this read-only check from an account with org/package visibility:

```bash
gh api /orgs/getpayd-tech/packages/container/payd-connect-v2-ledger \
  --jq '{name, visibility, repository: .repository.full_name}'
```

Expected after repair:

```json
{"name":"payd-connect-v2-ledger","visibility":"private","repository":"getpayd-tech/payd-labs-connect-v1"}
```

## Repair Procedure

1. In GitHub Packages, open each failed `payd-connect-v2-*` package.
2. Link or connect the package to `getpayd-tech/payd-labs-connect-v1`.
3. Under package Actions access, add `getpayd-tech/payd-labs-connect-v1` with
   write access.
4. Re-check package metadata for all failed packages. Do not proceed until each
   one is linked or otherwise grants the workflow write access.
5. Rerun `deploy-v2-sentinel.yml` on Connect branch `v2`. Prefer a fresh
   `workflow_dispatch` run so every image is built and pushed for the same SHA.
6. Confirm every image matrix job passes and the `Trigger Sentinel deployment`
   job is not skipped.
7. Check Sentinel deployment history for `payd-connect-v2-sandbox` and confirm
   the webhook carried the expected image tag.

## Sentinel Custom Compose Follow-Up

The Connect sandbox is a custom compose stack with many images and a shared
`CONNECT_IMAGE_TAG` variable. Sentinel's tagged deploy implementation rewrites
`image:` lines derived from one `project.ghcr_image` base, plus the generated
`-api` and `-ui` variants. For parameterized custom compose files, Sentinel also
supports `*IMAGE_TAG` variables referenced from compose `image:` lines and
updates those variables in the project `.env` before pulling.

The remaining follow-up is to make project ownership more explicit for custom
stacks that do not use a shared tag variable. The tracking issue is
<https://github.com/getpayd-tech/payd-labs-sentinel-v1/issues/1>.


- detect custom compose files where the requested tag rewrites zero or only part
  of the project-owned images and no `*IMAGE_TAG` fallback is available;
- surface a clear warning or failed preflight instead of silently pulling the old
  image set;
- support an explicit per-project image list for custom compose stacks that do
  not use a shared tag env var;
- add tests that cover generated single-service, generated blended, and custom
  multi-image compose behavior.

For Connect v2, the required tag strategy is `CONNECT_IMAGE_TAG`.

## Host File Verification

After GHCR permissions are fixed and the workflow publishes images, verify the
Sentinel project runtime files before declaring success:

- project: `payd-connect-v2-sandbox`
- compose path: `/apps/payd-connect-v2-sandbox`
- compose file: `deploy/sentinel/docker-compose.v2.sentinel.yml`

The host copy must include `dashboard-ui`, `hosted-ui`, `noah-sim`, and
`blockradar-sim` services plus the updated Caddy routes. If the host copy is
stale, publish only the deploy bundle required by the custom stack, preserving
the existing project `.env` and any Sentinel-managed secret material.

Do not paste raw `sentinel project show` output into public notes. It can include
project webhook material.

## Smoke Target

Run these after a successful deploy:

```bash
curl -fsS https://connect-v2-sandbox.payd.money/healthz
curl -fsS https://connect-v2-sandbox.payd.money/readyz
curl -fsS -o /dev/null -w "%{http_code}\n" https://connect-v2-sandbox.payd.money/dashboard/
curl -fsS -o /dev/null -w "%{http_code}\n" https://connect-v2-sandbox.payd.money/hosted/
curl -fsS https://connect-v2-sandbox.payd.money/_health/noah-sim/healthz
curl -fsS https://connect-v2-sandbox.payd.money/_health/blockradar-sim/healthz
python3 /apps/payd-connect-v2-sandbox/deploy/sentinel/smoke_api.py
```

Expected high-level result:

- `/dashboard/` returns `200`.
- `/hosted/` returns `200`.
- Noah and Blockradar simulator health return `200`.
- `smoke_api.py` ends with `api-smoke-ok`.

## Safety Notes

- Do not copy broad GitHub tokens to the Sentinel host. Prefer package-level
  permission repair or a deployer-scoped registry credential.
- Do not rotate the project webhook secret for this incident unless the package
  repair path fails for a confirmed secret-related reason.
- Do not claim provider-live acceptance from simulator route smokes.
- Do not mutate DNS, Sentinel env, project webhook material, or production host
  files without an explicit approval window.
