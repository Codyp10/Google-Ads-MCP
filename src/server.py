"""
Google Ads MCP Server.

A remote MCP server that wraps the Google Ads API, exposing tools
for campaign creation and management across multiple client accounts.

Designed for deployment on Railway/Render and connection to Claude.ai
as a custom MCP connector.
"""

import os
import json
import logging
from mcp.server.fastmcp import FastMCP

# Import all tool modules
from src.tools.accounts import list_accessible_accounts, set_active_account
from src.tools.campaigns import create_campaign
from src.tools.ad_groups import create_ad_group
from src.tools.keywords import add_keywords, add_negative_keywords
from src.tools.ads import create_rsa
from src.tools.assets import (
    add_sitelinks,
    add_callouts,
    add_call_asset,
    add_structured_snippets,
    add_image_asset,
)
from src.tools.pmax import create_pmax_campaign, create_asset_group
from src.tools.structure import preview_structure, push_structure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    "Google Ads Manager",
    instructions=(
        "Manage Google Ads campaigns across multiple accounts. "
        "Create campaigns, ad groups, keywords, ads, and assets. "
        "Supports Search, Display, and Performance Max campaigns."
    ),
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", 8000)),
)


# ============================================================
# ACCOUNT TOOLS
# ============================================================

@mcp.tool()
def tool_list_accessible_accounts() -> str:
    """
    List all Google Ads accounts accessible under the MCC.
    Returns account name, customer ID, manager status, and status.
    Call this first to see what accounts you can work with.
    """
    return list_accessible_accounts()


@mcp.tool()
def tool_set_active_account(customer_id: str) -> str:
    """
    Set which Google Ads customer account to target for all subsequent operations.
    All tools will default to this account unless you pass customer_id explicitly.

    Args:
        customer_id: The 10-digit Google Ads customer ID (dashes optional, e.g. "123-456-7890")
    """
    return set_active_account(customer_id)


# ============================================================
# CAMPAIGN TOOLS
# ============================================================

@mcp.tool()
def tool_create_campaign(
    name: str,
    campaign_type: str = "SEARCH",
    daily_budget_micros: int = 10_000_000,
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    network_settings: str | None = None,
    location_ids: str | None = None,
    language_ids: str | None = None,
    ad_schedule: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
) -> str:
    """
    Create a new Google Ads campaign. Always PAUSED by default.

    Args:
        name: Campaign name
        campaign_type: SEARCH, DISPLAY, or SHOPPING (use tool_create_pmax_campaign for PMax)
        daily_budget_micros: Daily budget in micros (1 dollar = 1,000,000). Default $10/day
        bidding_strategy: MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE, MANUAL_CPC,
                         TARGET_CPA, TARGET_ROAS, MAXIMIZE_CLICKS, TARGET_IMPRESSION_SHARE
        target_cpa_micros: Target CPA in micros (for TARGET_CPA/MAXIMIZE_CONVERSIONS with target)
        target_roas: Target ROAS float e.g. 3.0 (for TARGET_ROAS/MAXIMIZE_CONVERSION_VALUE)
        network_settings: JSON string with keys: search_network, content_network, partner_search_network
        location_ids: Comma-separated geo target IDs (e.g. "2840" for US, "2826" for UK)
        language_ids: Comma-separated language IDs (e.g. "1000" for English)
        ad_schedule: JSON string — list of schedule objects with day_of_week, start_hour, end_hour, etc.
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        status: PAUSED (default) or ENABLED
        customer_id: Target account (uses active if not set)
    """
    return create_campaign(
        name=name,
        campaign_type=campaign_type,
        daily_budget_micros=daily_budget_micros,
        bidding_strategy=bidding_strategy,
        target_cpa_micros=target_cpa_micros,
        target_roas=target_roas,
        network_settings=json.loads(network_settings) if network_settings else None,
        location_ids=location_ids.split(",") if location_ids else None,
        language_ids=language_ids.split(",") if language_ids else None,
        ad_schedule=json.loads(ad_schedule) if ad_schedule else None,
        start_date=start_date,
        end_date=end_date,
        status=status,
        customer_id=customer_id,
    )


# ============================================================
# AD GROUP TOOLS
# ============================================================

@mcp.tool()
def tool_create_ad_group(
    name: str,
    campaign_id: str,
    cpc_bid_micros: int = 1_000_000,
    status: str = "ENABLED",
    ad_group_type: str = "SEARCH_STANDARD",
    customer_id: str | None = None,
) -> str:
    """
    Create a new ad group linked to a campaign.

    Args:
        name: Ad group name
        campaign_id: The campaign ID (numeric) to attach this ad group to
        cpc_bid_micros: Default CPC bid in micros. Default $1.00
        status: ENABLED (default) or PAUSED
        ad_group_type: SEARCH_STANDARD (default), DISPLAY_STANDARD, or SHOPPING_PRODUCT_ADS
        customer_id: Target account
    """
    return create_ad_group(
        name=name,
        campaign_id=campaign_id,
        cpc_bid_micros=cpc_bid_micros,
        status=status,
        ad_group_type=ad_group_type,
        customer_id=customer_id,
    )


# ============================================================
# KEYWORD TOOLS
# ============================================================

@mcp.tool()
def tool_add_keywords(
    ad_group_id: str,
    keywords: str,
    customer_id: str | None = None,
) -> str:
    """
    Add keywords to an ad group.

    Args:
        ad_group_id: The ad group ID
        keywords: JSON string — list of objects with keys:
            - text: keyword text (required)
            - match_type: BROAD, PHRASE, or EXACT (default BROAD)
            - cpc_bid_micros: optional bid override
          Example: [{"text": "buy shoes", "match_type": "EXACT"}, {"text": "shoes online", "match_type": "PHRASE"}]
        customer_id: Target account
    """
    return add_keywords(
        ad_group_id=ad_group_id,
        keywords=json.loads(keywords),
        customer_id=customer_id,
    )


@mcp.tool()
def tool_add_negative_keywords(
    keywords: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add negative keywords at campaign or ad group level.

    Args:
        keywords: JSON string — list of objects with text and optional match_type (default EXACT)
          Example: [{"text": "free"}, {"text": "cheap", "match_type": "BROAD"}]
        campaign_id: Campaign ID (for campaign-level negatives)
        ad_group_id: Ad group ID (for ad group-level negatives)
        customer_id: Target account
    """
    return add_negative_keywords(
        keywords=json.loads(keywords),
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        customer_id=customer_id,
    )


# ============================================================
# AD TOOLS
# ============================================================

@mcp.tool()
def tool_create_rsa(
    ad_group_id: str,
    headlines: str,
    descriptions: str,
    final_url: str,
    path1: str = "",
    path2: str = "",
    tracking_template: str = "",
    customer_id: str | None = None,
) -> str:
    """
    Create a Responsive Search Ad (RSA).

    Args:
        ad_group_id: The ad group to create the ad in
        headlines: JSON string — list of headline objects (3-15 required):
            - text: headline text (max 30 chars)
            - pinned_to: optional pin position (1, 2, or 3)
          Example: [{"text": "Buy Shoes Online", "pinned_to": 1}, {"text": "Free Shipping"}]
        descriptions: JSON string — list of description objects (2-4 required):
            - text: description text (max 90 chars)
            - pinned_to: optional pin position (1 or 2)
        final_url: The landing page URL
        path1: Display URL path 1 (max 15 chars)
        path2: Display URL path 2 (max 15 chars)
        tracking_template: Tracking URL template
        customer_id: Target account
    """
    return create_rsa(
        ad_group_id=ad_group_id,
        headlines=json.loads(headlines),
        descriptions=json.loads(descriptions),
        final_url=final_url,
        path1=path1,
        path2=path2,
        tracking_template=tracking_template,
        customer_id=customer_id,
    )


# ============================================================
# ASSET TOOLS
# ============================================================

@mcp.tool()
def tool_add_sitelinks(
    sitelinks: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add sitelink assets and link to a campaign or ad group.

    Args:
        sitelinks: JSON string — list of sitelink objects:
            - link_text: headline (max 25 chars)
            - description1: first line (max 35 chars)
            - description2: second line (max 35 chars)
            - final_url: landing page URL
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    return add_sitelinks(
        sitelinks=json.loads(sitelinks),
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        customer_id=customer_id,
    )


@mcp.tool()
def tool_add_callouts(
    callout_texts: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add callout assets and link to a campaign or ad group.

    Args:
        callout_texts: Comma-separated callout texts (max 25 chars each)
          Example: "Free Shipping,24/7 Support,Easy Returns"
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    texts = [t.strip() for t in callout_texts.split(",")]
    return add_callouts(
        callout_texts=texts,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        customer_id=customer_id,
    )


@mcp.tool()
def tool_add_call_asset(
    phone_number: str,
    country_code: str = "US",
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add a call (phone number) asset and link to a campaign or ad group.

    Args:
        phone_number: Phone number (e.g. "+18005551234")
        country_code: Two-letter country code (default US)
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    return add_call_asset(
        phone_number=phone_number,
        country_code=country_code,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        customer_id=customer_id,
    )


@mcp.tool()
def tool_add_structured_snippets(
    header: str,
    values: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add a structured snippet asset and link to a campaign or ad group.

    Args:
        header: Snippet header type (Amenities, Brands, Courses, Degree programs,
               Destinations, Featured hotels, Insurance coverage, Neighborhoods,
               Service catalog, Shows, Styles, Types)
        values: Comma-separated snippet values (min 3 recommended)
          Example: "Residential,Commercial,Industrial"
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    value_list = [v.strip() for v in values.split(",")]
    return add_structured_snippets(
        header=header,
        values=value_list,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        customer_id=customer_id,
    )


@mcp.tool()
def tool_add_image_asset(
    name: str,
    image_source: str,
    customer_id: str | None = None,
) -> str:
    """
    Upload an image asset from a local file path or URL.

    Args:
        name: Asset name for reference
        image_source: Local file path or URL to the image
        customer_id: Target account

    Returns the asset resource name for use in PMax asset groups.
    """
    return add_image_asset(
        name=name,
        image_source=image_source,
        customer_id=customer_id,
    )


# ============================================================
# PERFORMANCE MAX TOOLS
# ============================================================

@mcp.tool()
def tool_create_pmax_campaign(
    name: str,
    daily_budget_micros: int = 10_000_000,
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    location_ids: str | None = None,
    language_ids: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
) -> str:
    """
    Create a Performance Max campaign. Always PAUSED by default.

    Args:
        name: Campaign name
        daily_budget_micros: Daily budget in micros (default $10/day)
        bidding_strategy: MAXIMIZE_CONVERSIONS or MAXIMIZE_CONVERSION_VALUE
        target_cpa_micros: Target CPA in micros (optional)
        target_roas: Target ROAS float (optional)
        location_ids: Comma-separated geo target IDs (default "2840" for US)
        language_ids: Comma-separated language IDs (default "1000" for English)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        status: PAUSED (default) or ENABLED
        customer_id: Target account
    """
    return create_pmax_campaign(
        name=name,
        daily_budget_micros=daily_budget_micros,
        bidding_strategy=bidding_strategy,
        target_cpa_micros=target_cpa_micros,
        target_roas=target_roas,
        location_ids=location_ids.split(",") if location_ids else None,
        language_ids=language_ids.split(",") if language_ids else None,
        start_date=start_date,
        end_date=end_date,
        status=status,
        customer_id=customer_id,
    )


@mcp.tool()
def tool_create_asset_group(
    name: str,
    campaign_id: str,
    final_url: str,
    headlines: str,
    long_headlines: str,
    descriptions: str,
    business_name: str,
    image_asset_ids: str | None = None,
    logo_asset_ids: str | None = None,
    youtube_video_ids: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Create an asset group for a Performance Max campaign.

    Args:
        name: Asset group name
        campaign_id: PMax campaign ID to attach to
        final_url: Landing page URL
        headlines: JSON string — list of headline texts (3-5, max 30 chars each)
          Example: ["Buy Shoes", "Free Shipping", "Shop Now"]
        long_headlines: JSON string — list of long headline texts (1-5, max 90 chars)
        descriptions: JSON string — list of description texts (2-5, max 90 chars)
        business_name: Business name
        image_asset_ids: Comma-separated image asset resource names (upload with tool_add_image_asset first)
        logo_asset_ids: Comma-separated logo asset resource names
        youtube_video_ids: Comma-separated YouTube video IDs
        customer_id: Target account
    """
    return create_asset_group(
        name=name,
        campaign_id=campaign_id,
        final_url=final_url,
        headlines=json.loads(headlines),
        long_headlines=json.loads(long_headlines),
        descriptions=json.loads(descriptions),
        business_name=business_name,
        image_asset_ids=image_asset_ids.split(",") if image_asset_ids else None,
        logo_asset_ids=logo_asset_ids.split(",") if logo_asset_ids else None,
        youtube_video_ids=youtube_video_ids.split(",") if youtube_video_ids else None,
        customer_id=customer_id,
    )


# ============================================================
# UTILITY TOOLS
# ============================================================

@mcp.tool()
def tool_preview_structure(structure: str) -> str:
    """
    Preview a full campaign structure without pushing anything live.
    Returns a human-readable summary of everything that would be created.
    Always use this before push_structure to review.

    Args:
        structure: JSON string describing the full campaign structure.
          See push_structure for the expected format.
    """
    return preview_structure(json.loads(structure))


@mcp.tool()
def tool_push_structure(
    structure: str,
    customer_id: str | None = None,
) -> str:
    """
    Push a full campaign structure to Google Ads.
    Creates everything in order: campaign -> ad groups -> keywords -> ads -> assets.

    IMPORTANT: This creates real entities. Always preview_structure first.

    Args:
        structure: JSON string — full campaign structure:
            {
                "campaign": {
                    "name": "My Campaign", "campaign_type": "SEARCH",
                    "daily_budget_micros": 10000000, "bidding_strategy": "MAXIMIZE_CONVERSIONS"
                },
                "ad_groups": [
                    {
                        "name": "Ad Group 1", "cpc_bid_micros": 1000000,
                        "keywords": [{"text": "buy shoes", "match_type": "EXACT"}],
                        "negative_keywords": [{"text": "free"}],
                        "ads": [{
                            "headlines": [{"text": "Buy Shoes Online"}, ...],
                            "descriptions": [{"text": "Great selection..."}, ...],
                            "final_url": "https://example.com"
                        }]
                    }
                ],
                "sitelinks": [{"link_text": "Shop", "final_url": "https://..."}],
                "callouts": ["Free Shipping", "24/7 Support"],
                "call_asset": {"phone_number": "+18005551234"},
                "structured_snippets": {"header": "Types", "values": ["A", "B", "C"]}
            }
        customer_id: Target account
    """
    return push_structure(
        structure=json.loads(structure),
        customer_id=customer_id,
    )
