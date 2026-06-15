# Server Inventory and Cleanup Handoff - 2026-06-15

## Purpose

This note preserves the temporary server-inspection scripts created during the June 2026 operations cleanup. They are not runtime dependencies, but they are useful for future handover, server drift checks, and safe cleanup planning.

Do not store SSH passwords, API keys, `.env` contents, or NCP credentials in these scripts or in this document.

## Preserved Scripts

### `scratch/server_inventory_20260611.sh`

Role: full server inventory snapshot.

Main checks:

- disk usage for `/`
- depth-1 sizes for `/opt`, `/opt/busan`, and `/opt/advisor`
- systemd unit definitions and active/enabled state for:
  - `busan-api.service`
  - `busan-dashboard.service`
  - `busan-advisor-pilot.service`
  - `law-chatbot.service`
  - `korean-law-mcp.service`
  - `busan-company-cache-sync.service`
- systemd timers
- crontab entries for `busan-monitor`, `busan-chatbot`, and `root`
- key DB/cache file timestamps and sizes
- `/opt/advisor/cache/company` symlink targets and archive directories
- DB object counts for:
  - `chatbot_company_candidate_view`
  - `product_policy_summary`
  - `direct_production_certificate`
  - `company_license`
  - `company_license_construction_capacity`
  - `facility_material_item_dictionary`
  - `facility_material_price_current`
- Git branch, HEAD, and dirty status for `/opt/busan` and `/opt/advisor`

Output path on server:

```bash
/tmp/server_inventory_20260611.txt
```

Typical execution:

```bash
bash scratch/server_inventory_20260611.sh
```

Operational use:

- Run before changing server deployment, cache sync, cron, or DB pipeline configuration.
- Attach the generated inventory text to handover notes when comparing office/local/server state.
- Use it as a read-only baseline. It should not mutate services or databases.

### `scratch/server_cleanup_inventory_20260611.sh`

Role: focused disk-cleanup inventory.

Main checks:

- large directory sizes under:
  - `/root`
  - `/opt/backups`
  - `/opt/busan/backups`
  - `/opt/advisor/artifacts`
  - `/opt/advisor/.cache`
- large files under:
  - `/root/e2e_workspace`
  - `/root/_advisor_archives`
  - `/opt/backups`
  - `/opt/busan/backups`
- process references to cleanup-sensitive paths

Typical execution:

```bash
bash scratch/server_cleanup_inventory_20260611.sh
```

Operational use:

- Run before deleting old backups, archives, or QA artifacts.
- Treat output as a deletion candidate list only. It does not decide what is safe to remove.
- Do not remove `/opt/busan` or `/opt/advisor` DB/cache files from this output without a separate backup/restore check.

## Current Preservation Decision

These scripts should be kept as tracked handover artifacts because they encode the operating layout of the single Naver Cloud server:

- monitoring system: `/opt/busan`
- advisor/vendor recommendation system: `/opt/advisor`
- company DB cache handoff: `/opt/advisor/cache/company/cache_current`

They are diagnostic scripts, not deployment scripts. Future maintainers should prefer Git-based deployment and systemd-controlled services, and use these scripts only for inspection.

