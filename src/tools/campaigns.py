"""
Campaign creation tools.
- create_campaign: create a Search, Display, or generic campaign (not PMax)
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def create_campaign(
    name: str,
    campaign_type: str = "SEARCH",
    daily_budget_micros: int = 10_000_000,
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    network_settings: dict | None = None,
    location_ids: list[str] | None = None,
    language_ids: list[str] | None = None,
    ad_schedule: list[dict] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "PAUSED",
    customer_id: str | None = None,
) -> str:
    """
    Create a new campaign. Always PAUSED by default.

    Args:
        name: Campaign name
        campaign_type: SEARCH, DISPLAY, or SHOPPING
        daily_budget_micros: Daily budget in micros (1 dollar = 1,000,000 micros). Default $10/day
        bidding_strategy: MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE, MANUAL_CPC,
                         TARGET_CPA, TARGET_ROAS, MAXIMIZE_CLICKS, TARGET_IMPRESSION_SHARE
        target_cpa_micros: Target CPA in micros (for TARGET_CPA strategy)
        target_roas: Target ROAS as float e.g. 3.0 for 300% (for TARGET_ROAS strategy)
        network_settings: Dict with keys: search_network (bool), content_network (bool),
                         partner_search_network (bool). Defaults to search only.
        location_ids: List of geo target constant IDs (e.g. ["2840"] for US). Default: US
        language_ids: List of language criterion IDs (e.g. ["1000"] for English). Default: English
        ad_schedule: List of schedule dicts with keys: day_of_week, start_hour, start_minute,
                    end_hour, end_minute. e.g. [{"day_of_week": "MONDAY", "start_hour": 9,
                    "start_minute": "ZERO", "end_hour": 17, "end_minute": "ZERO"}]
        start_date: Campaign start date YYYY-MM-DD
        end_date: Campaign end date YYYY-MM-DD
        status: PAUSED (default) or ENABLED
        customer_id: Target account (uses active account if not specified)
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()

    # --- Step 1: Create Campaign Budget ---
    budget_operation = client.get_type("MutateOperation")
    budget_op = budget_operation.campaign_budget_operation.create
    budget_op.name = f"{name} Budget"
    budget_op.amount_micros = daily_budget_micros
    budget_op.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget_op.explicitly_shared = False

    # Use a temporary resource name for linking
    budget_temp_id = -1
    budget_op.resource_name = client.get_service(
        "CampaignBudgetService"
    ).campaign_budget_path(cid, budget_temp_id)

    # --- Step 2: Create Campaign ---
    campaign_operation = client.get_type("MutateOperation")
    campaign_op = campaign_operation.campaign_operation.create
    campaign_op.name = name
    campaign_op.campaign_budget = budget_op.resource_name

    # Campaign type
    type_map = {
        "SEARCH": client.enums.AdvertisingChannelTypeEnum.SEARCH,
        "DISPLAY": client.enums.AdvertisingChannelTypeEnum.DISPLAY,
        "SHOPPING": client.enums.AdvertisingChannelTypeEnum.SHOPPING,
    }
    campaign_type_upper = campaign_type.upper()
    if campaign_type_upper not in type_map:
        return f"Unsupported campaign type: {campaign_type}. Use SEARCH, DISPLAY, or SHOPPING."
    campaign_op.advertising_channel_type = type_map[campaign_type_upper]

    # Status
    status_map = {
        "PAUSED": client.enums.CampaignStatusEnum.PAUSED,
        "ENABLED": client.enums.CampaignStatusEnum.ENABLED,
    }
    campaign_op.status = status_map.get(status.upper(), client.enums.CampaignStatusEnum.PAUSED)

    # Bidding strategy
    strategy = bidding_strategy.upper()
    if strategy == "MAXIMIZE_CONVERSIONS":
        campaign_op.maximize_conversions.target_cpa_micros = target_cpa_micros or 0
    elif strategy == "MAXIMIZE_CONVERSION_VALUE":
        campaign_op.maximize_conversion_value.target_roas = target_roas or 0.0
    elif strategy == "MAXIMIZE_CLICKS":
        campaign_op.maximize_clicks.cpc_bid_ceiling_micros = 0
    elif strategy == "MANUAL_CPC":
        campaign_op.manual_cpc.enhanced_cpc_enabled = False
    elif strategy == "TARGET_CPA":
        campaign_op.maximize_conversions.target_cpa_micros = target_cpa_micros or 0
    elif strategy == "TARGET_ROAS":
        campaign_op.maximize_conversion_value.target_roas = target_roas or 0.0
    elif strategy == "TARGET_IMPRESSION_SHARE":
        campaign_op.target_impression_share.location = (
            client.enums.TargetImpressionShareLocationEnum.ANYWHERE_ON_PAGE
        )
        campaign_op.target_impression_share.location_fraction_micros = 500_000
        campaign_op.target_impression_share.cpc_bid_ceiling_micros = 5_000_000
    else:
        return f"Unsupported bidding strategy: {bidding_strategy}"

    # Network settings (Search campaigns)
    if campaign_type_upper == "SEARCH":
        ns = network_settings or {}
        campaign_op.network_settings.target_google_search = ns.get("search_network", True)
        campaign_op.network_settings.target_search_network = ns.get("partner_search_network", False)
        campaign_op.network_settings.target_content_network = ns.get("content_network", False)

    # Dates
    if start_date:
        campaign_op.start_date = start_date.replace("-", "")
    if end_date:
        campaign_op.end_date = end_date.replace("-", "")

    operations = [budget_operation, campaign_operation]

    # --- Step 3: Location targeting ---
    locations = location_ids or ["2840"]  # Default: United States
    campaign_temp_id = -2
    campaign_service = get_service("CampaignService")
    campaign_op.resource_name = campaign_service.campaign_path(cid, campaign_temp_id)

    for loc_id in locations:
        loc_operation = client.get_type("MutateOperation")
        loc_criterion = loc_operation.campaign_criterion_operation.create
        loc_criterion.campaign = campaign_op.resource_name
        loc_criterion.location.geo_target_constant = (
            client.get_service("GeoTargetConstantService").geo_target_constant_path(loc_id)
        )
        operations.append(loc_operation)

    # --- Step 4: Language targeting ---
    languages = language_ids or ["1000"]  # Default: English
    for lang_id in languages:
        lang_operation = client.get_type("MutateOperation")
        lang_criterion = lang_operation.campaign_criterion_operation.create
        lang_criterion.campaign = campaign_op.resource_name
        lang_criterion.language.language_constant = (
            f"languageConstants/{lang_id}"
        )
        operations.append(lang_operation)

    # --- Step 5: Ad schedule ---
    if ad_schedule:
        day_map = {
            "MONDAY": client.enums.DayOfWeekEnum.MONDAY,
            "TUESDAY": client.enums.DayOfWeekEnum.TUESDAY,
            "WEDNESDAY": client.enums.DayOfWeekEnum.WEDNESDAY,
            "THURSDAY": client.enums.DayOfWeekEnum.THURSDAY,
            "FRIDAY": client.enums.DayOfWeekEnum.FRIDAY,
            "SATURDAY": client.enums.DayOfWeekEnum.SATURDAY,
            "SUNDAY": client.enums.DayOfWeekEnum.SUNDAY,
        }
        minute_map = {
            "ZERO": client.enums.MinuteOfHourEnum.ZERO,
            "FIFTEEN": client.enums.MinuteOfHourEnum.FIFTEEN,
            "THIRTY": client.enums.MinuteOfHourEnum.THIRTY,
            "FORTY_FIVE": client.enums.MinuteOfHourEnum.FORTY_FIVE,
        }
        for sched in ad_schedule:
            sched_operation = client.get_type("MutateOperation")
            sched_criterion = sched_operation.campaign_criterion_operation.create
            sched_criterion.campaign = campaign_op.resource_name
            sched_criterion.ad_schedule.day_of_week = day_map[sched["day_of_week"].upper()]
            sched_criterion.ad_schedule.start_hour = sched.get("start_hour", 0)
            sched_criterion.ad_schedule.start_minute = minute_map.get(
                sched.get("start_minute", "ZERO"), client.enums.MinuteOfHourEnum.ZERO
            )
            sched_criterion.ad_schedule.end_hour = sched.get("end_hour", 24)
            sched_criterion.ad_schedule.end_minute = minute_map.get(
                sched.get("end_minute", "ZERO"), client.enums.MinuteOfHourEnum.ZERO
            )
            operations.append(sched_operation)

    # --- Execute ---
    try:
        response = mutate(cid, operations)
        results = []
        for result in response.mutate_operation_responses:
            if result.campaign_budget_result.resource_name:
                results.append(f"Budget: {result.campaign_budget_result.resource_name}")
            if result.campaign_result.resource_name:
                results.append(f"Campaign: {result.campaign_result.resource_name}")
            if result.campaign_criterion_result.resource_name:
                results.append(f"Criterion: {result.campaign_criterion_result.resource_name}")

        budget_str = f"${daily_budget_micros / 1_000_000:.2f}/day"
        return (
            f"Campaign created successfully!\n\n"
            f"  Name: {name}\n"
            f"  Type: {campaign_type_upper}\n"
            f"  Budget: {budget_str}\n"
            f"  Bidding: {strategy}\n"
            f"  Status: {status.upper()}\n"
            f"  Locations: {', '.join(locations)}\n"
            f"  Languages: {', '.join(languages)}\n\n"
            f"Resources created:\n" + "\n".join(f"  {r}" for r in results)
        )
    except Exception as e:
        return f"Failed to create campaign: {e}"
