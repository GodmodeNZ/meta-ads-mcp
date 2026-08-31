import os
import json
import httpx
from typing import Any, Optional

from fastmcp import FastMCP

mcp = FastMCP("Godmode Meta Ads")

META_API_VERSION = os.getenv("META_API_VERSION", "v23.0")
META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
META_AD_ACCOUNT_ID = os.getenv(
    "META_AD_ACCOUNT_ID",
    "act_2613654521995635",
)

BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


# -------------------------------------------------------------------
# HTTP HELPERS
# -------------------------------------------------------------------

async def meta_get(path: str, params: Optional[dict] = None):
    params = dict(params or {})
    params["access_token"] = META_ACCESS_TOKEN

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.get(
            f"{BASE_URL}/{path.lstrip('/')}",
            params=params,
        )

        if response.is_error:
            raise RuntimeError(
                f"Meta API error {response.status_code}: {response.text}"
            )

        return response.json()


async def meta_post(path: str, data: Optional[dict] = None):
    data = dict(data or {})
    data["access_token"] = META_ACCESS_TOKEN

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{BASE_URL}/{path.lstrip('/')}",
            data=data,
        )

        if response.is_error:
            raise RuntimeError(
                f"Meta API error {response.status_code}: {response.text}"
            )

        return response.json()


async def meta_get_all(path: str, params: Optional[dict] = None):
    result = await meta_get(path, params)

    rows = list(result.get("data", []))
    next_url = result.get("paging", {}).get("next")

    async with httpx.AsyncClient(timeout=90) as client:
        while next_url:
            response = await client.get(next_url)

            if response.is_error:
                raise RuntimeError(
                    f"Meta API pagination error "
                    f"{response.status_code}: {response.text}"
                )

            page = response.json()
            rows.extend(page.get("data", []))
            next_url = page.get("paging", {}).get("next")

    return {"data": rows, "count": len(rows)}


def insight_params(
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    breakdowns: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    params = {
        "fields": (
            "account_id,"
            "account_name,"
            "campaign_id,"
            "campaign_name,"
            "adset_id,"
            "adset_name,"
            "ad_id,"
            "ad_name,"
            "spend,"
            "impressions,"
            "reach,"
            "frequency,"
            "clicks,"
            "inline_link_clicks,"
            "ctr,"
            "cpc,"
            "cpm,"
            "cpp,"
            "actions,"
            "action_values,"
            "cost_per_action_type,"
            "purchase_roas"
        ),
        "limit": 500,
    }

    if since and until:
        params["time_range"] = json.dumps({
            "since": since,
            "until": until,
        })
    else:
        params["date_preset"] = date_preset

    if breakdowns:
        params["breakdowns"] = breakdowns

    if time_increment:
        params["time_increment"] = time_increment

    return params


def encode_meta_value(value: Any):
    """Encode structured values the way Meta's form API expects."""
    if isinstance(value, (dict, list, tuple, bool)):
        return json.dumps(value)
    return str(value)


def parse_json_object(value: str, field_name: str):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def parse_json_value(value: str, field_name: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc.msg}") from exc


def money_to_minor_units(amount_nzd: float, field_name: str):
    if amount_nzd <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return str(int(round(amount_nzd * 100)))


def planned_change(object_id: str, values: dict):
    """Return a non-mutating preview for tools that support dry_run."""
    return {
        "dry_run": True,
        "object_id": object_id,
        "changes": values,
        "message": "Validation preview only; no Meta Ads changes were made.",
    }


async def guarded_update(object_id: str, values: dict, dry_run: bool = True):
    encoded = {key: encode_meta_value(value) for key, value in values.items()}
    if dry_run:
        return planned_change(object_id, encoded)
    return await meta_post(object_id, encoded)


# -------------------------------------------------------------------
# ACCOUNT
# -------------------------------------------------------------------

@mcp.tool()
async def list_ad_accounts():
    """List Meta ad accounts accessible to the authenticated system user."""
    return await meta_get_all(
        "me/adaccounts",
        {
            "fields": (
                "id,name,account_status,currency,"
                "timezone_name,amount_spent,balance"
            ),
            "limit": 100,
        },
    )


@mcp.tool()
async def get_ad_account():
    """Get details for the configured Meta ad account."""
    return await meta_get(
        META_AD_ACCOUNT_ID,
        {
            "fields": (
                "id,name,account_status,currency,"
                "timezone_name,timezone_offset_hours_utc,"
                "amount_spent,balance"
            )
        },
    )


# -------------------------------------------------------------------
# CAMPAIGNS
# -------------------------------------------------------------------

@mcp.tool()
async def list_campaigns():
    """List campaigns in the configured Meta ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/campaigns",
        {
            "fields": (
                "id,name,status,effective_status,"
                "objective,buying_type,"
                "daily_budget,lifetime_budget,"
                "budget_remaining,"
                "created_time,updated_time,"
                "start_time,stop_time"
            ),
            "limit": 500,
        },
    )


@mcp.tool()
async def get_campaign(campaign_id: str):
    """Get details for one Meta campaign."""
    return await meta_get(
        campaign_id,
        {
            "fields": (
                "id,name,status,effective_status,"
                "objective,buying_type,"
                "daily_budget,lifetime_budget,"
                "budget_remaining,"
                "created_time,updated_time,"
                "start_time,stop_time"
            )
        },
    )


# -------------------------------------------------------------------
# AD SETS
# -------------------------------------------------------------------

@mcp.tool()
async def list_adsets(
    campaign_id: Optional[str] = None,
):
    """List ad sets, optionally restricted to one campaign."""
    parent = campaign_id or META_AD_ACCOUNT_ID

    return await meta_get_all(
        f"{parent}/adsets",
        {
            "fields": (
                "id,name,campaign_id,"
                "status,effective_status,"
                "daily_budget,lifetime_budget,"
                "budget_remaining,"
                "billing_event,"
                "optimization_goal,"
                "bid_strategy,"
                "bid_amount,"
                "start_time,end_time,"
                "created_time,updated_time,"
                "targeting"
            ),
            "limit": 500,
        },
    )


@mcp.tool()
async def get_adset(adset_id: str):
    """Get details for one Meta ad set."""
    return await meta_get(
        adset_id,
        {
            "fields": (
                "id,name,campaign_id,"
                "status,effective_status,"
                "daily_budget,lifetime_budget,"
                "budget_remaining,"
                "billing_event,"
                "optimization_goal,"
                "bid_strategy,"
                "bid_amount,"
                "start_time,end_time,"
                "targeting"
            )
        },
    )


# -------------------------------------------------------------------
# ADS
# -------------------------------------------------------------------

@mcp.tool()
async def list_ads(
    campaign_id: Optional[str] = None,
    adset_id: Optional[str] = None,
):
    """List ads at account, campaign, or ad-set level."""
    if adset_id:
        parent = adset_id
    elif campaign_id:
        parent = campaign_id
    else:
        parent = META_AD_ACCOUNT_ID

    return await meta_get_all(
        f"{parent}/ads",
        {
            "fields": (
                "id,name,"
                "campaign_id,adset_id,"
                "status,effective_status,"
                "created_time,updated_time,"
                "creative{id,name,thumbnail_url}"
            ),
            "limit": 500,
        },
    )


@mcp.tool()
async def get_ad(ad_id: str):
    """Get details for one Meta ad."""
    return await meta_get(
        ad_id,
        {
            "fields": (
                "id,name,"
                "campaign_id,adset_id,"
                "status,effective_status,"
                "created_time,updated_time,"
                "creative{id,name,thumbnail_url}"
            )
        },
    )


# -------------------------------------------------------------------
# CREATIVES
# -------------------------------------------------------------------

@mcp.tool()
async def list_ad_creatives():
    """List ad creatives in the configured ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/adcreatives",
        {
            "fields": (
                "id,name,"
                "title,body,"
                "thumbnail_url,"
                "image_url,"
                "object_story_spec,"
                "asset_feed_spec,"
                "effective_object_story_id,"
                "status"
            ),
            "limit": 500,
        },
    )


@mcp.tool()
async def get_ad_creative(creative_id: str):
    """Get one Meta ad creative."""
    return await meta_get(
        creative_id,
        {
            "fields": (
                "id,name,"
                "title,body,"
                "thumbnail_url,"
                "image_url,"
                "object_story_spec,"
                "asset_feed_spec,"
                "effective_object_story_id,"
                "status"
            )
        },
    )


# -------------------------------------------------------------------
# INSIGHTS
# -------------------------------------------------------------------

@mcp.tool()
async def get_account_insights(
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    level: str = "account",
    breakdowns: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    """
    Get Meta advertising insights.

    level:
      account
      campaign
      adset
      ad

    Optional breakdown examples:
      age
      gender
      country
      region
      device_platform
      publisher_platform
      platform_position

    since/until format:
      YYYY-MM-DD

    time_increment examples:
      1
      7
      monthly
    """

    params = insight_params(
        date_preset=date_preset,
        since=since,
        until=until,
        breakdowns=breakdowns,
        time_increment=time_increment,
    )

    params["level"] = level

    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/insights",
        params,
    )


@mcp.tool()
async def get_campaign_insights(
    campaign_id: str,
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    breakdowns: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    """Get performance for one Meta campaign."""

    return await meta_get_all(
        f"{campaign_id}/insights",
        insight_params(
            date_preset,
            since,
            until,
            breakdowns,
            time_increment,
        ),
    )


@mcp.tool()
async def get_adset_insights(
    adset_id: str,
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    breakdowns: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    """Get performance for one Meta ad set."""

    return await meta_get_all(
        f"{adset_id}/insights",
        insight_params(
            date_preset,
            since,
            until,
            breakdowns,
            time_increment,
        ),
    )


@mcp.tool()
async def get_ad_insights(
    ad_id: str,
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    breakdowns: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    """Get performance for one Meta ad."""

    return await meta_get_all(
        f"{ad_id}/insights",
        insight_params(
            date_preset,
            since,
            until,
            breakdowns,
            time_increment,
        ),
    )


# -------------------------------------------------------------------
# ASSETS, AUDIENCES, CATALOGS, TRACKING AND DELIVERY DIAGNOSTICS
# -------------------------------------------------------------------

@mcp.tool()
async def list_pixels():
    """List Meta Pixels owned by the configured ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/adspixels",
        {"fields": "id,name,creation_time,last_fired_time,is_unavailable", "limit": 500},
    )


@mcp.tool()
async def get_pixel(pixel_id: str):
    """Get one Meta Pixel and its recent firing status."""
    return await meta_get(
        pixel_id,
        {"fields": "id,name,creation_time,last_fired_time,is_unavailable"},
    )


@mcp.tool()
async def get_pixel_stats(
    pixel_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    aggregation: str = "event",
):
    """Inspect Pixel event activity. Times may be ISO-8601 or Unix timestamps."""
    params = {"aggregation": aggregation}
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    return await meta_get_all(f"{pixel_id}/stats", params)


@mcp.tool()
async def list_custom_conversions():
    """List custom conversions configured for the ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/customconversions",
        {
            "fields": "id,name,description,event_source_type,custom_event_type,rule,default_conversion_value,is_archived",
            "limit": 500,
        },
    )


@mcp.tool()
async def get_custom_conversion(custom_conversion_id: str):
    """Get one custom conversion definition."""
    return await meta_get(
        custom_conversion_id,
        {"fields": "id,name,description,event_source_type,custom_event_type,rule,default_conversion_value,is_archived"},
    )


@mcp.tool()
async def list_custom_audiences():
    """List custom and lookalike audiences available to the ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/customaudiences",
        {
            "fields": "id,name,description,subtype,approximate_count_lower_bound,approximate_count_upper_bound,delivery_status,operation_status,time_created,time_updated",
            "limit": 500,
        },
    )


@mcp.tool()
async def get_custom_audience(audience_id: str):
    """Get one custom or lookalike audience."""
    return await meta_get(
        audience_id,
        {"fields": "id,name,description,subtype,approximate_count_lower_bound,approximate_count_upper_bound,delivery_status,operation_status,time_created,time_updated"},
    )


@mcp.tool()
async def list_product_catalogs():
    """List product catalogs associated with the configured ad account."""
    return await meta_get_all(
        f"{META_AD_ACCOUNT_ID}/product_catalogs",
        {"fields": "id,name,vertical,product_count", "limit": 500},
    )


@mcp.tool()
async def list_product_sets(catalog_id: str):
    """List product sets in a Meta catalog."""
    return await meta_get_all(
        f"{catalog_id}/product_sets",
        {"fields": "id,name,filter,product_count", "limit": 500},
    )


@mcp.tool()
async def get_product_set(product_set_id: str):
    """Get one catalog product set and its filter."""
    return await meta_get(
        product_set_id,
        {"fields": "id,name,filter,product_count"},
    )


@mcp.tool()
async def list_lead_forms(page_id: str):
    """List lead-generation forms belonging to a Facebook Page."""
    return await meta_get_all(
        f"{page_id}/leadgen_forms",
        {"fields": "id,name,status,created_time,leads_count", "limit": 500},
    )


@mcp.tool()
async def get_delivery_estimate(
    targeting_spec_json: str,
    optimization_goal: str = "OFFSITE_CONVERSIONS",
):
    """Estimate audience size/delivery for a targeting spec without changing ads."""
    targeting = parse_json_object(targeting_spec_json, "targeting_spec_json")
    return await meta_get(
        f"{META_AD_ACCOUNT_ID}/delivery_estimate",
        {
            "targeting_spec": json.dumps(targeting),
            "optimization_goal": optimization_goal,
        },
    )


@mcp.tool()
async def search_targeting(
    query: str,
    targeting_type: str,
    country_code: str = "NZ",
    limit: int = 50,
):
    """Search valid Meta targeting entities such as interests, locations or employers."""
    if not query.strip():
        raise ValueError("query must not be empty")
    return await meta_get(
        "search",
        {
            "type": "adTargetingCategory" if targeting_type == "category" else "adgeolocation" if targeting_type == "location" else "adinterest",
            "q": query,
            "location_types": json.dumps(["country", "region", "city", "zip"]),
            "country_code": country_code,
            "limit": max(1, min(limit, 1000)),
        },
    )


@mcp.tool()
async def get_adset_attribution_settings(adset_id: str):
    """Read an ad set's attribution spec and optimization configuration."""
    return await meta_get(
        adset_id,
        {
            "fields": (
                "id,name,status,effective_status,attribution_spec,"
                "optimization_goal,billing_event,bid_strategy,bid_amount,"
                "promoted_object,targeting,start_time,end_time"
            )
        },
    )


@mcp.tool()
async def compare_attribution_windows(
    object_id: str,
    level: str = "campaign",
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    attribution_windows: str = "1d_click,7d_click,1d_view",
):
    """Report results split across requested attribution windows without changing delivery."""
    allowed_levels = {"account", "campaign", "adset", "ad"}
    if level not in allowed_levels:
        raise ValueError(f"level must be one of {sorted(allowed_levels)}")
    params = insight_params(date_preset, since, until)
    params["level"] = level
    params["action_attribution_windows"] = json.dumps(
        [window.strip() for window in attribution_windows.split(",") if window.strip()]
    )
    params["action_report_time"] = "conversion"
    params["use_unified_attribution_setting"] = "false"
    return await meta_get_all(f"{object_id}/insights", params)


@mcp.tool()
async def get_insights_advanced(
    object_id: str,
    level: str,
    fields: str,
    date_preset: str = "last_30d",
    since: Optional[str] = None,
    until: Optional[str] = None,
    breakdowns: Optional[str] = None,
    action_breakdowns: Optional[str] = None,
    attribution_windows: Optional[str] = None,
    time_increment: Optional[str] = None,
):
    """Run an advanced Insights query with caller-selected fields and breakdowns."""
    if level not in {"account", "campaign", "adset", "ad"}:
        raise ValueError("level must be account, campaign, adset, or ad")
    if not fields.strip():
        raise ValueError("fields must not be empty")
    params = {"fields": fields, "level": level, "limit": 500}
    if since and until:
        params["time_range"] = json.dumps({"since": since, "until": until})
    else:
        params["date_preset"] = date_preset
    if breakdowns:
        params["breakdowns"] = breakdowns
    if action_breakdowns:
        params["action_breakdowns"] = action_breakdowns
    if attribution_windows:
        params["action_attribution_windows"] = json.dumps(
            [window.strip() for window in attribution_windows.split(",") if window.strip()]
        )
    if time_increment:
        params["time_increment"] = time_increment
    return await meta_get_all(f"{object_id}/insights", params)


# -------------------------------------------------------------------
# CONTROLLED WRITE TOOLS
# -------------------------------------------------------------------

@mcp.tool()
async def pause_campaign(campaign_id: str):
    """Pause an existing Meta campaign."""
    return await meta_post(
        campaign_id,
        {"status": "PAUSED"},
    )


@mcp.tool()
async def enable_campaign(campaign_id: str):
    """Enable an existing Meta campaign."""
    return await meta_post(
        campaign_id,
        {"status": "ACTIVE"},
    )


@mcp.tool()
async def pause_adset(adset_id: str):
    """Pause an existing Meta ad set."""
    return await meta_post(
        adset_id,
        {"status": "PAUSED"},
    )


@mcp.tool()
async def enable_adset(adset_id: str):
    """Enable an existing Meta ad set."""
    return await meta_post(
        adset_id,
        {"status": "ACTIVE"},
    )


@mcp.tool()
async def pause_ad(ad_id: str):
    """Pause an existing Meta ad."""
    return await meta_post(
        ad_id,
        {"status": "PAUSED"},
    )


@mcp.tool()
async def enable_ad(ad_id: str):
    """Enable an existing Meta ad."""
    return await meta_post(
        ad_id,
        {"status": "ACTIVE"},
    )


@mcp.tool()
async def set_campaign_daily_budget(
    campaign_id: str,
    daily_budget_nzd: float,
):
    """
    Set campaign daily budget in NZD.

    Meta stores budgets in currency minor units,
    so NZ$70.00 becomes 7000.
    """
    if daily_budget_nzd <= 0:
        raise ValueError("daily_budget_nzd must be greater than zero")

    amount = int(round(daily_budget_nzd * 100))

    return await meta_post(
        campaign_id,
        {"daily_budget": str(amount)},
    )


@mcp.tool()
async def set_adset_daily_budget(
    adset_id: str,
    daily_budget_nzd: float,
):
    """Set an ad set daily budget in NZD."""

    if daily_budget_nzd <= 0:
        raise ValueError("daily_budget_nzd must be greater than zero")

    amount = int(round(daily_budget_nzd * 100))

    return await meta_post(
        adset_id,
        {"daily_budget": str(amount)},
    )


@mcp.tool()
async def set_adset_attribution(
    adset_id: str,
    click_window_days: int = 7,
    view_window_days: int = 0,
    dry_run: bool = True,
):
    """Set ad-set attribution. Use view_window_days=0 for click-only attribution."""
    if click_window_days not in {1, 7}:
        raise ValueError("click_window_days must be 1 or 7")
    if view_window_days not in {0, 1}:
        raise ValueError("view_window_days must be 0 or 1")
    spec = [{"event_type": "CLICK_THROUGH", "window_days": click_window_days}]
    if view_window_days:
        spec.append({"event_type": "VIEW_THROUGH", "window_days": view_window_days})
    return await guarded_update(adset_id, {"attribution_spec": spec}, dry_run)


@mcp.tool()
async def rename_campaign(campaign_id: str, name: str, dry_run: bool = True):
    """Rename an existing campaign."""
    if not name.strip():
        raise ValueError("name must not be empty")
    return await guarded_update(campaign_id, {"name": name.strip()}, dry_run)


@mcp.tool()
async def rename_adset(adset_id: str, name: str, dry_run: bool = True):
    """Rename an existing ad set."""
    if not name.strip():
        raise ValueError("name must not be empty")
    return await guarded_update(adset_id, {"name": name.strip()}, dry_run)


@mcp.tool()
async def rename_ad(ad_id: str, name: str, dry_run: bool = True):
    """Rename an existing ad."""
    if not name.strip():
        raise ValueError("name must not be empty")
    return await guarded_update(ad_id, {"name": name.strip()}, dry_run)


@mcp.tool()
async def set_campaign_lifetime_budget(
    campaign_id: str,
    lifetime_budget_nzd: float,
    dry_run: bool = True,
):
    """Set a campaign lifetime budget in NZD."""
    value = money_to_minor_units(lifetime_budget_nzd, "lifetime_budget_nzd")
    return await guarded_update(campaign_id, {"lifetime_budget": value}, dry_run)


@mcp.tool()
async def set_adset_lifetime_budget(
    adset_id: str,
    lifetime_budget_nzd: float,
    dry_run: bool = True,
):
    """Set an ad-set lifetime budget in NZD."""
    value = money_to_minor_units(lifetime_budget_nzd, "lifetime_budget_nzd")
    return await guarded_update(adset_id, {"lifetime_budget": value}, dry_run)


@mcp.tool()
async def set_campaign_schedule(
    campaign_id: str,
    start_time: Optional[str] = None,
    stop_time: Optional[str] = None,
    dry_run: bool = True,
):
    """Change a campaign start and/or stop time using ISO-8601 values."""
    values = {}
    if start_time:
        values["start_time"] = start_time
    if stop_time:
        values["stop_time"] = stop_time
    if not values:
        raise ValueError("provide start_time and/or stop_time")
    return await guarded_update(campaign_id, values, dry_run)


@mcp.tool()
async def set_adset_schedule(
    adset_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    dry_run: bool = True,
):
    """Change an ad set start and/or end time using ISO-8601 values."""
    values = {}
    if start_time:
        values["start_time"] = start_time
    if end_time:
        values["end_time"] = end_time
    if not values:
        raise ValueError("provide start_time and/or end_time")
    return await guarded_update(adset_id, values, dry_run)


@mcp.tool()
async def set_adset_bid_strategy(
    adset_id: str,
    bid_strategy: str,
    bid_amount_nzd: Optional[float] = None,
    dry_run: bool = True,
):
    """Set an ad set bid strategy and optional bid/cost cap in NZD."""
    allowed = {
        "LOWEST_COST_WITHOUT_CAP",
        "LOWEST_COST_WITH_BID_CAP",
        "COST_CAP",
        "LOWEST_COST_WITH_MIN_ROAS",
    }
    if bid_strategy not in allowed:
        raise ValueError(f"bid_strategy must be one of {sorted(allowed)}")
    values = {"bid_strategy": bid_strategy}
    if bid_amount_nzd is not None:
        values["bid_amount"] = money_to_minor_units(bid_amount_nzd, "bid_amount_nzd")
    return await guarded_update(adset_id, values, dry_run)


@mcp.tool()
async def set_adset_optimization(
    adset_id: str,
    optimization_goal: str,
    billing_event: Optional[str] = None,
    dry_run: bool = True,
):
    """Set an ad set optimization goal and optional billing event."""
    values = {"optimization_goal": optimization_goal}
    if billing_event:
        values["billing_event"] = billing_event
    return await guarded_update(adset_id, values, dry_run)


@mcp.tool()
async def set_adset_targeting(
    adset_id: str,
    targeting_json: str,
    dry_run: bool = True,
):
    """Replace an ad set targeting spec. Read the current spec first to avoid accidental loss."""
    targeting = parse_json_object(targeting_json, "targeting_json")
    return await guarded_update(adset_id, {"targeting": targeting}, dry_run)


@mcp.tool()
async def set_adset_promoted_object(
    adset_id: str,
    promoted_object_json: str,
    dry_run: bool = True,
):
    """Set the promoted object, Pixel, conversion event or product set for an ad set."""
    promoted_object = parse_json_object(promoted_object_json, "promoted_object_json")
    return await guarded_update(adset_id, {"promoted_object": promoted_object}, dry_run)


@mcp.tool()
async def set_ad_tracking(
    ad_id: str,
    tracking_specs_json: Optional[str] = None,
    url_tags: Optional[str] = None,
    dry_run: bool = True,
):
    """Set an ad's tracking specs and/or URL tags such as UTMs."""
    values = {}
    if tracking_specs_json:
        values["tracking_specs"] = parse_json_value(tracking_specs_json, "tracking_specs_json")
    if url_tags is not None:
        values["url_tags"] = url_tags
    if not values:
        raise ValueError("provide tracking_specs_json and/or url_tags")
    return await guarded_update(ad_id, values, dry_run)


@mcp.tool()
async def create_campaign(
    name: str,
    objective: str,
    special_ad_categories_json: str = "[]",
    buying_type: str = "AUCTION",
    status: str = "PAUSED",
    daily_budget_nzd: Optional[float] = None,
    lifetime_budget_nzd: Optional[float] = None,
    dry_run: bool = True,
):
    """Create a campaign, PAUSED by default. Supports campaign-level budget."""
    if status not in {"PAUSED", "ACTIVE"}:
        raise ValueError("status must be PAUSED or ACTIVE")
    values = {
        "name": name,
        "objective": objective,
        "buying_type": buying_type,
        "special_ad_categories": parse_json_value(special_ad_categories_json, "special_ad_categories_json"),
        "status": status,
    }
    if daily_budget_nzd is not None and lifetime_budget_nzd is not None:
        raise ValueError("provide only one of daily_budget_nzd or lifetime_budget_nzd")
    if daily_budget_nzd is not None:
        values["daily_budget"] = money_to_minor_units(daily_budget_nzd, "daily_budget_nzd")
    if lifetime_budget_nzd is not None:
        values["lifetime_budget"] = money_to_minor_units(lifetime_budget_nzd, "lifetime_budget_nzd")
    return await guarded_update(f"{META_AD_ACCOUNT_ID}/campaigns", values, dry_run)


@mcp.tool()
async def create_adset(
    campaign_id: str,
    name: str,
    optimization_goal: str,
    billing_event: str,
    targeting_json: str,
    promoted_object_json: Optional[str] = None,
    daily_budget_nzd: Optional[float] = None,
    lifetime_budget_nzd: Optional[float] = None,
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
    bid_amount_nzd: Optional[float] = None,
    attribution_click_days: int = 7,
    attribution_view_days: int = 0,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: str = "PAUSED",
    dry_run: bool = True,
):
    """Create a PAUSED ad set with explicit targeting, optimization and attribution."""
    if attribution_click_days not in {1, 7} or attribution_view_days not in {0, 1}:
        raise ValueError("attribution click days must be 1 or 7; view days must be 0 or 1")
    if daily_budget_nzd is not None and lifetime_budget_nzd is not None:
        raise ValueError("provide only one of daily_budget_nzd or lifetime_budget_nzd")
    attribution = [{"event_type": "CLICK_THROUGH", "window_days": attribution_click_days}]
    if attribution_view_days:
        attribution.append({"event_type": "VIEW_THROUGH", "window_days": attribution_view_days})
    values = {
        "campaign_id": campaign_id,
        "name": name,
        "optimization_goal": optimization_goal,
        "billing_event": billing_event,
        "targeting": parse_json_object(targeting_json, "targeting_json"),
        "bid_strategy": bid_strategy,
        "attribution_spec": attribution,
        "status": status,
    }
    if promoted_object_json:
        values["promoted_object"] = parse_json_object(promoted_object_json, "promoted_object_json")
    if daily_budget_nzd is not None:
        values["daily_budget"] = money_to_minor_units(daily_budget_nzd, "daily_budget_nzd")
    if lifetime_budget_nzd is not None:
        values["lifetime_budget"] = money_to_minor_units(lifetime_budget_nzd, "lifetime_budget_nzd")
    if bid_amount_nzd is not None:
        values["bid_amount"] = money_to_minor_units(bid_amount_nzd, "bid_amount_nzd")
    if start_time:
        values["start_time"] = start_time
    if end_time:
        values["end_time"] = end_time
    return await guarded_update(f"{META_AD_ACCOUNT_ID}/adsets", values, dry_run)


@mcp.tool()
async def create_ad_creative(
    name: str,
    object_story_spec_json: Optional[str] = None,
    asset_feed_spec_json: Optional[str] = None,
    degrees_of_freedom_spec_json: Optional[str] = None,
    url_tags: Optional[str] = None,
    dry_run: bool = True,
):
    """Create a reusable Meta ad creative from validated JSON specifications."""
    values = {"name": name}
    if object_story_spec_json:
        values["object_story_spec"] = parse_json_object(object_story_spec_json, "object_story_spec_json")
    if asset_feed_spec_json:
        values["asset_feed_spec"] = parse_json_object(asset_feed_spec_json, "asset_feed_spec_json")
    if degrees_of_freedom_spec_json:
        values["degrees_of_freedom_spec"] = parse_json_object(degrees_of_freedom_spec_json, "degrees_of_freedom_spec_json")
    if url_tags:
        values["url_tags"] = url_tags
    if len(values) == 1:
        raise ValueError("provide at least one creative specification")
    return await guarded_update(f"{META_AD_ACCOUNT_ID}/adcreatives", values, dry_run)


@mcp.tool()
async def create_ad(
    adset_id: str,
    name: str,
    creative_id: str,
    tracking_specs_json: Optional[str] = None,
    url_tags: Optional[str] = None,
    status: str = "PAUSED",
    dry_run: bool = True,
):
    """Create a PAUSED ad from an existing creative."""
    values = {
        "adset_id": adset_id,
        "name": name,
        "creative": {"creative_id": creative_id},
        "status": status,
    }
    if tracking_specs_json:
        values["tracking_specs"] = parse_json_value(tracking_specs_json, "tracking_specs_json")
    if url_tags:
        values["url_tags"] = url_tags
    return await guarded_update(f"{META_AD_ACCOUNT_ID}/ads", values, dry_run)


@mcp.tool()
async def duplicate_campaign(
    campaign_id: str,
    deep_copy: bool = True,
    status_option: str = "PAUSED",
    rename_options_json: Optional[str] = None,
    dry_run: bool = True,
):
    """Duplicate a campaign and optionally all child ad sets/ads, PAUSED by default."""
    values = {"deep_copy": deep_copy, "status_option": status_option}
    if rename_options_json:
        values["rename_options"] = parse_json_object(rename_options_json, "rename_options_json")
    return await guarded_update(f"{campaign_id}/copies", values, dry_run)


@mcp.tool()
async def duplicate_adset(
    adset_id: str,
    deep_copy: bool = True,
    status_option: str = "PAUSED",
    rename_options_json: Optional[str] = None,
    dry_run: bool = True,
):
    """Duplicate an ad set and optionally its ads, PAUSED by default."""
    values = {"deep_copy": deep_copy, "status_option": status_option}
    if rename_options_json:
        values["rename_options"] = parse_json_object(rename_options_json, "rename_options_json")
    return await guarded_update(f"{adset_id}/copies", values, dry_run)


@mcp.tool()
async def duplicate_ad(
    ad_id: str,
    status_option: str = "PAUSED",
    rename_options_json: Optional[str] = None,
    dry_run: bool = True,
):
    """Duplicate an ad, PAUSED by default."""
    values = {"status_option": status_option}
    if rename_options_json:
        values["rename_options"] = parse_json_object(rename_options_json, "rename_options_json")
    return await guarded_update(f"{ad_id}/copies", values, dry_run)


# -------------------------------------------------------------------
# SERVER
# -------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
