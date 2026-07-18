# Phase 0 — Prep Checklist

> **Note:** The runnable helper scripts referenced below (inventory, provision, db-migrate, cutover, env-import) describe a migration methodology. The original versions were specific to one environment and are NOT bundled in this template; implement them against your own Coolify API and infrastructure.

Two-month runway before the December migration. Each item is independently valuable.

## Week 1 (October) — Stop the bleeding

- [ ] **Configure S3 backups on all 5 databases.** Coolify dashboard → each DB resource → Backups → S3 destination + daily schedule.
- [ ] Trigger one manual backup per DB, verify file appears in S3.
- [ ] Test restore on a throwaway DB to validate the loop end-to-end.
- [ ] Delete orphan Maillayer Coolify entry (`<RESOURCE_UUID>`). Confirm `example.com` still resolves after.

## Week 2-3 (October-November) — Tooling

- [ ] Create Coolify API token on old VPS with read scope. Save to `.env.migration` as `COOLIFY_OLD_TOKEN`.
- [ ] Create Cloudflare API token: Zone → DNS Edit, Zone → Zone Read, scoped to your 4 zones. Save as `CLOUDFLARE_API_TOKEN`.
- [ ] Add Cloudflare MCP server to `.mcp.json` (see `../README.md` § Cloudflare MCP Configuration).
- [ ] Restart Claude Code, verify Cloudflare tools appear in deferred tools list.
- [ ] Smoke-test MCP: list zones, list DNS records, create+delete a test record (`example.com`).

## Week 4 (mid-November) — Inventory dry run

- [ ] Run `01-inventory.mjs` against old VPS, produce `migration-inventory.json`.
- [ ] Manually review JSON for completeness:
  - Every domain captured?
  - Every env var decrypted?
  - Every DB connection string present?
  - Every persistent volume noted?
- [ ] Add anything missed to `migration-inventory-manual.json`.

## Week 5-6 (late November) — Practice run

- [ ] Provision a $5 test VPS (Hetzner CX22 or Lightsail nano).
- [ ] Install matching Coolify version (`4.0.0-beta.459`).
- [ ] Run `02-provision.mjs` with a filter targeting **only example Website** (lowest risk, stateless).
- [ ] Time each step. Note any failures. Iterate the script.
- [ ] Confirm Cloudflare placeholder DNS works end-to-end.
- [ ] Tear down the test VPS.

## Cutover-week prep (early December)

- [ ] T-48h: Lower Cloudflare TTL on all production A records to **60 seconds**.
- [ ] T-24h: Take a Lightsail snapshot of the old VPS (this is the Option A fallback).
- [ ] T-24h: Re-run `01-inventory.mjs`, diff against the November version, resolve any new env vars or domains.
- [ ] T-12h: Final dry-run of `04-cutover.mjs --dry-run` against production cutover plan.

## Day-of cutover

- [ ] Two terminals open: one with `04-cutover.mjs --apply`, one with `04-cutover.mjs --rollback receipt.json` pre-typed.
- [ ] DB delta sync ran within last 2 hours.
- [ ] All `*-new.*` smoke tests green.
- [ ] Cloudflare Analytics dashboard open.
- [ ] Pull the trigger.

## Open questions to resolve

- [ ] Destination provider chosen (Lightsail vs Hetzner)?
- [ ] example DB dependency confirmed?
- [ ] MX records location confirmed (Cloudflare or upstream)?
- [ ] Static IP attached on target VPS?
