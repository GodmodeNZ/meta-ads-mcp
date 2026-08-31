# Godmode Meta Ads MCP

FastMCP service for read-only Meta Ads reporting, diagnostics and controlled changes.

## Safety model

- Existing status and daily-budget tools retain their original behaviour for compatibility.
- New mutation tools default to `dry_run=True` and return an exact change preview.
- Pass `dry_run=False` only after reviewing the preview.
- Newly created campaigns, ad sets and ads default to `PAUSED`.
- Targeting replacement is explicit and requires a complete JSON object.

## Tool coverage

The server exposes 58 tools covering:

- Accounts, campaigns, ad sets, ads and creatives
- Standard and advanced Insights queries
- Attribution-window comparison and ad-set attribution control
- Pixel activity and custom conversions
- Custom audiences, catalogs and product sets
- Targeting search and delivery estimates
- Budgets, schedules, bidding, optimization and promoted objects
- Tracking specs and URL tags
- Campaign, ad-set, creative and ad creation
- Safe duplication workflows

## Attribution example

Preview a seven-day-click-only attribution change:

```json
{
  "adset_id": "120221375975090708",
  "click_window_days": 7,
  "view_window_days": 0,
  "dry_run": true
}
```

After reviewing the returned plan, repeat with `dry_run: false` to apply it.

## Run locally

```bash
pip install -r requirements.txt
export META_ACCESS_TOKEN="..."
export META_AD_ACCOUNT_ID="act_2613654521995635"
python3 server.py
```

