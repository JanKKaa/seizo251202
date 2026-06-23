# 設備・部品在庫管理 App - Production Note

This app started as a development/test version for Hayashi Techno equipment and spare-part inventory.

As of 2026-05-25 it is enabled in production Docker.

Production URL:

```text
/setsubi-zaiko/
```

Legacy development URL:

```text
/dev/setsubi-zaiko/
```

The legacy URL redirects to the production URL.

Current scope:
- Equipment/category master.
- MISUMI-style part master fields.
- Item photo and nameplate/label photo upload.
- Stock in/out/adjustment ledger.
- IATF audit/readiness alerts.
- Current inventory dashboard.
- CSV export with audit header.
- Pagination 10 rows per page.
- No hard-delete workflow for ledger records.
