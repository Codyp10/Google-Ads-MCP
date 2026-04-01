"""
Performance Max campaign tools.
- create_pmax_campaign: create a PMax campaign with budget and bidding
- create_asset_group: create an asset group with all creative assets
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def create_pmax_campaign(
    name: str,
    daily_budget_micros: int = 10_000_000,
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    location_ids: list[str] | None = None,
    language_ids: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
) -> str:
    """
    Create a Performance Max campaign.

    Args:
        name: Campaign name
        daily_budget_micros: Daily budget in micros (default $10/day)
        bidding_strategy: MAXIMIZE_CONVERSIONS or MAXIMIZE_CONVERSION_VALUE
        target_cpa_micros: Target CPA in micros (optional, for MAXIMIZE_CONVERSIONS)
        target_roas: Target ROAS float (optional, for MAXIMIZE_CONVERSION_VALUE)
        location_ids: List of geo target IDs (default: ["2840"] for US)
        language_ids: List of language IDs (default: ["1000"] for English)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        status: PAUSED (default) or ENABLED
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()

    # Budget
    budget_operation = client.get_type("MutateOperation")
    budget = budget_operation.campaign_budget_operation.create
    budget.name = f"{name} Budget"
    budget.amount_micros = daily_budget_micros
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.explicitly_shared = False

    budget_temp_id = -1
    budget_service = get_service("CampaignBudgetService")
    budget.resource_name = budget_service.campaign_budget_path(cid, budget_temp_id)

    # Campaign
    campaign_operation = client.get_type("MutateOperation")
    campaign = campaign_operation.campaign_operation.create
    campaign.name = name
    campaign.campaign_budget = budget.resource_name
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX

    campaign_temp_id = -2
    campaign_service = get_service("CampaignService")
    campaign.resource_name = campaign_service.campaign_path(cid, campaign_temp_id)

    # Status
    status_map = {
        "PAUSED": client.enums.CampaignStatusEnum.PAUSED,
        "ENABLED": client.enums.CampaignStatusEnum.ENABLED,
    }
    campaign.status = status_map.get(status.upper(), client.enums.CampaignStatusEnum.PAUSED)

    # Bidding
    strategy = bidding_strategy.upper()
    if strategy == "MAXIMIZE_CONVERSIONS":
        campaign.maximize_conversions.target_cpa_micros = target_cpa_micros or 0
    elif strategy == "MAXIMIZE_CONVERSION_VALUE":
        campaign.maximize_conversion_value.target_roas = target_roas or 0.0
    else:
        return f"PMax only supports MAXIMIZE_CONVERSIONS or MAXIMIZE_CONVERSION_VALUE. Got: {bidding_strategy}"

    if start_date:
        campaign.start_date = start_date.replace("-", "")
    if end_date:
        campaign.end_date = end_date.replace("-", "")

    operations = [budget_operation, campaign_operation]

    # Location targeting
    locations = location_ids or ["2840"]
    for loc_id in locations:
        loc_op = client.get_type("MutateOperation")
        criterion = loc_op.campaign_criterion_operation.create
        criterion.campaign = campaign.resource_name
        criterion.location.geo_target_constant = (
            get_service("GeoTargetConstantService").geo_target_constant_path(loc_id)
        )
        operations.append(loc_op)

    # Language targeting
    languages = language_ids or ["1000"]
    for lang_id in languages:
        lang_op = client.get_type("MutateOperation")
        criterion = lang_op.campaign_criterion_operation.create
        criterion.campaign = campaign.resource_name
        criterion.language.language_constant = f"languageConstants/{lang_id}"
        operations.append(lang_op)

    try:
        response = mutate(cid, operations)
        budget_str = f"${daily_budget_micros / 1_000_000:.2f}/day"

        # Extract campaign resource name from response
        campaign_resource = ""
        for result in response.mutate_operation_responses:
            if result.campaign_result.resource_name:
                campaign_resource = result.campaign_result.resource_name
                break

        campaign_id = campaign_resource.split("/")[-1] if campaign_resource else "unknown"

        return (
            f"PMax campaign created successfully!\n\n"
            f"  Name: {name}\n"
            f"  Campaign ID: {campaign_id}\n"
            f"  Budget: {budget_str}\n"
            f"  Bidding: {strategy}\n"
            f"  Status: {status.upper()}\n"
            f"  Locations: {', '.join(locations)}\n"
            f"  Languages: {', '.join(languages)}\n"
            f"  Resource: {campaign_resource}\n\n"
            f"Next step: Create an asset group with create_asset_group using campaign_id={campaign_id}"
        )
    except Exception as e:
        return f"Failed to create PMax campaign: {e}"


def create_asset_group(
    name: str,
    campaign_id: str,
    final_url: str,
    headlines: list[str],
    long_headlines: list[str],
    descriptions: list[str],
    business_name: str,
    image_asset_ids: list[str] | None = None,
    logo_asset_ids: list[str] | None = None,
    youtube_video_ids: list[str] | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Create an asset group for a Performance Max campaign.

    Args:
        name: Asset group name
        campaign_id: PMax campaign ID to attach to
        final_url: Landing page URL
        headlines: List of headline texts (3-5 recommended, max 30 chars each)
        long_headlines: List of long headline texts (1-5, max 90 chars each)
        descriptions: List of description texts (2-5, max 90 chars each)
        business_name: Business name for the ad
        image_asset_ids: List of image asset resource names (upload with add_image_asset first)
        logo_asset_ids: List of logo asset resource names
        youtube_video_ids: List of YouTube video IDs (e.g. "dQw4w9WgXcQ")
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")
    asset_group_service = get_service("AssetGroupService")

    operations = []

    # Create asset group
    ag_temp_id = -10
    ag_operation = client.get_type("MutateOperation")
    ag = ag_operation.asset_group_operation.create
    ag.name = name
    ag.campaign = campaign_service.campaign_path(cid, campaign_id)
    ag.resource_name = asset_group_service.asset_group_path(cid, ag_temp_id)
    ag.final_urls.append(final_url)
    ag.status = client.enums.AssetGroupStatusEnum.PAUSED
    operations.append(ag_operation)

    # Helper to add text assets linked to the asset group
    text_asset_temp_id = -500

    def add_text_asset(text: str, field_type):
        nonlocal text_asset_temp_id
        asset_service = get_service("AssetService")

        # Create asset
        asset_op = client.get_type("MutateOperation")
        asset = asset_op.asset_operation.create
        asset.resource_name = asset_service.asset_path(cid, text_asset_temp_id)
        asset.text_asset.text = text
        operations.append(asset_op)

        # Link to asset group
        link_op = client.get_type("MutateOperation")
        link = link_op.asset_group_asset_operation.create
        link.asset_group = ag.resource_name
        link.asset = asset.resource_name
        link.field_type = field_type
        operations.append(link_op)

        text_asset_temp_id -= 1

    # Add headlines
    for h in headlines:
        add_text_asset(h, client.enums.AssetFieldTypeEnum.HEADLINE)

    # Add long headlines
    for lh in long_headlines:
        add_text_asset(lh, client.enums.AssetFieldTypeEnum.LONG_HEADLINE)

    # Add descriptions
    for d in descriptions:
        add_text_asset(d, client.enums.AssetFieldTypeEnum.DESCRIPTION)

    # Add business name
    add_text_asset(business_name, client.enums.AssetFieldTypeEnum.BUSINESS_NAME)

    # Link image assets (already uploaded)
    if image_asset_ids:
        for img_resource in image_asset_ids:
            link_op = client.get_type("MutateOperation")
            link = link_op.asset_group_asset_operation.create
            link.asset_group = ag.resource_name
            link.asset = img_resource
            link.field_type = client.enums.AssetFieldTypeEnum.MARKETING_IMAGE
            operations.append(link_op)

    # Link logo assets
    if logo_asset_ids:
        for logo_resource in logo_asset_ids:
            link_op = client.get_type("MutateOperation")
            link = link_op.asset_group_asset_operation.create
            link.asset_group = ag.resource_name
            link.asset = logo_resource
            link.field_type = client.enums.AssetFieldTypeEnum.LOGO
            operations.append(link_op)

    # Link YouTube videos
    if youtube_video_ids:
        yt_temp_id = -800
        asset_service = get_service("AssetService")
        for video_id in youtube_video_ids:
            asset_op = client.get_type("MutateOperation")
            asset = asset_op.asset_operation.create
            asset.resource_name = asset_service.asset_path(cid, yt_temp_id)
            asset.youtube_video_asset.youtube_video_id = video_id
            operations.append(asset_op)

            link_op = client.get_type("MutateOperation")
            link = link_op.asset_group_asset_operation.create
            link.asset_group = ag.resource_name
            link.asset = asset.resource_name
            link.field_type = client.enums.AssetFieldTypeEnum.YOUTUBE_VIDEO
            operations.append(link_op)
            yt_temp_id -= 1

    try:
        response = mutate(cid, operations)

        # Extract asset group resource from response
        ag_resource = ""
        for result in response.mutate_operation_responses:
            if result.asset_group_result.resource_name:
                ag_resource = result.asset_group_result.resource_name
                break

        return (
            f"Asset group created successfully!\n\n"
            f"  Name: {name}\n"
            f"  Campaign: {campaign_id}\n"
            f"  Final URL: {final_url}\n"
            f"  Headlines: {len(headlines)}\n"
            f"  Long Headlines: {len(long_headlines)}\n"
            f"  Descriptions: {len(descriptions)}\n"
            f"  Images: {len(image_asset_ids or [])}\n"
            f"  Logos: {len(logo_asset_ids or [])}\n"
            f"  Videos: {len(youtube_video_ids or [])}\n"
            f"  Resource: {ag_resource}"
        )
    except Exception as e:
        return f"Failed to create asset group: {e}"
