import os
import json
import httpx
from typing import Optional

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


# -------------------------------------------------------------------
# SERVER
# -------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
