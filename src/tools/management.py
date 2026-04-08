"""
Campaign and ad group management tools.
- update_campaign: change budget, bidding, status, name
- set_ad_schedule: set day/time ad schedule on a campaign
- set_location_targeting: add/exclude geos, set presence mode
- remove_keywords: delete keyword criteria from ad groups
- remove_campaign: soft-delete a campaign
- update_ad_group: change bids, status, name on ad groups
- manage_conversion_actions: list/create conversion actions
"""

import json
from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    search,
    mutate,
)


def update_campaign(
    campaign_id: str,
    name: str | None = None,
    daily_budget_micros: int | None = None,
    bidding_strategy: str | None = None,
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    status: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Update properties on an existing campaign.

    Args:
        campaign_id: Campaign ID to update
        name: New campaign name
        daily_budget_micros: New daily budget in micros
        bidding_strategy: New bidding strategy (MANUAL_CPC, MAXIMIZE_CLICKS, MAXIMIZE_CONVERSIONS, etc.)
        target_cpa_micros: Target CPA for applicable strategies
        target_roas: Target ROAS for applicable strategies
        status: ENABLED or PAUSED
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")

    changes = []

    # Update budget if requested (separate resource)
    if daily_budget_micros is not None:
        # First, get the campaign's budget resource name
        budget_query = f"""
            SELECT campaign.campaign_budget
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """
        rows = list(search(cid, budget_query))
        if not rows:
            return f"Campaign {campaign_id} not found."

        budget_resource = rows[0].campaign.campaign_budget

        budget_operation = client.get_type("MutateOperation")
        budget_op = budget_operation.campaign_budget_operation.update
        budget_op.resource_name = budget_resource
        budget_op.amount_micros = daily_budget_micros

        field_mask = client.get_type("FieldMask")
        field_mask.paths.append("amount_micros")
        budget_operation.campaign_budget_operation.update_mask.CopyFrom(field_mask)

        try:
            mutate(cid, [budget_operation])
            changes.append(f"  Budget: ${daily_budget_micros / 1_000_000:.2f}/day")
        except Exception as e:
            return f"Failed to update budget: {e}"

    # Update campaign fields
    campaign_operation = client.get_type("MutateOperation")
    campaign_op = campaign_operation.campaign_operation.update
    campaign_op.resource_name = campaign_service.campaign_path(cid, campaign_id)

    update_fields = []

    if name is not None:
        campaign_op.name = name
        update_fields.append("name")
        changes.append(f"  Name: {name}")

    if status is not None:
        status_map = {
            "PAUSED": client.enums.CampaignStatusEnum.PAUSED,
            "ENABLED": client.enums.CampaignStatusEnum.ENABLED,
        }
        campaign_op.status = status_map.get(status.upper(), client.enums.CampaignStatusEnum.PAUSED)
        update_fields.append("status")
        changes.append(f"  Status: {status.upper()}")

    if bidding_strategy is not None:
        strategy = bidding_strategy.upper()
        if strategy == "MAXIMIZE_CONVERSIONS":
            campaign_op.maximize_conversions.target_cpa_micros = target_cpa_micros or 0
            update_fields.append("maximize_conversions")
        elif strategy == "MAXIMIZE_CONVERSION_VALUE":
            campaign_op.maximize_conversion_value.target_roas = target_roas or 0.0
            update_fields.append("maximize_conversion_value")
        elif strategy == "MAXIMIZE_CLICKS":
            campaign_op.target_spend.target_spend_micros = 0
            update_fields.append("target_spend")
        elif strategy == "MANUAL_CPC":
            campaign_op.manual_cpc.enhanced_cpc_enabled = False
            update_fields.append("manual_cpc")
        elif strategy == "TARGET_CPA":
            campaign_op.maximize_conversions.target_cpa_micros = target_cpa_micros or 0
            update_fields.append("maximize_conversions")
        elif strategy == "TARGET_ROAS":
            campaign_op.maximize_conversion_value.target_roas = target_roas or 0.0
            update_fields.append("maximize_conversion_value")
        elif strategy == "TARGET_IMPRESSION_SHARE":
            campaign_op.target_impression_share.location = (
                client.enums.TargetImpressionShareLocationEnum.ANYWHERE_ON_PAGE
            )
            campaign_op.target_impression_share.location_fraction_micros = 500_000
            campaign_op.target_impression_share.cpc_bid_ceiling_micros = 5_000_000
            update_fields.append("target_impression_share")
        else:
            return f"Unsupported bidding strategy: {bidding_strategy}"
        changes.append(f"  Bidding: {strategy}")

    if update_fields:
        field_mask = client.get_type("FieldMask")
        for f in update_fields:
            field_mask.paths.append(f)
        campaign_operation.campaign_operation.update_mask.CopyFrom(field_mask)

        try:
            mutate(cid, [campaign_operation])
        except Exception as e:
            return f"Failed to update campaign: {e}"

    if not changes:
        return "No changes specified."

    return f"Campaign {campaign_id} updated:\n" + "\n".join(changes)


def set_ad_schedule(
    campaign_id: str,
    schedules: list[dict],
    customer_id: str | None = None,
) -> str:
    """
    Set day/time ad schedule on a campaign.

    Args:
        campaign_id: Campaign to set schedule on
        schedules: List of schedule dicts with keys:
            day_of_week (MONDAY-SUNDAY), start_hour (0-24), start_minute (ZERO/FIFTEEN/THIRTY/FORTY_FIVE),
            end_hour (0-24), end_minute (ZERO/FIFTEEN/THIRTY/FORTY_FIVE)
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")
    campaign_criterion_service = get_service("CampaignCriterionService")

    # First, remove existing ad schedule criteria
    existing_query = f"""
        SELECT campaign_criterion.resource_name
        FROM campaign_criterion
        WHERE campaign.id = {campaign_id}
            AND campaign_criterion.type = 'AD_SCHEDULE'
    """
    try:
        existing = list(search(cid, existing_query))
        if existing:
            remove_ops = []
            for row in existing:
                remove_op = client.get_type("MutateOperation")
                remove_op.campaign_criterion_operation.remove = row.campaign_criterion.resource_name
                remove_ops.append(remove_op)
            mutate(cid, remove_ops)
    except Exception:
        pass  # No existing schedules to remove

    # Add new schedule criteria
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

    operations = []
    campaign_resource = campaign_service.campaign_path(cid, campaign_id)

    for sched in schedules:
        op = client.get_type("MutateOperation")
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = campaign_resource
        criterion.ad_schedule.day_of_week = day_map[sched["day_of_week"].upper()]
        criterion.ad_schedule.start_hour = sched.get("start_hour", 0)
        criterion.ad_schedule.start_minute = minute_map.get(
            sched.get("start_minute", "ZERO"), client.enums.MinuteOfHourEnum.ZERO
        )
        criterion.ad_schedule.end_hour = sched.get("end_hour", 24)
        criterion.ad_schedule.end_minute = minute_map.get(
            sched.get("end_minute", "ZERO"), client.enums.MinuteOfHourEnum.ZERO
        )
        operations.append(op)

    try:
        mutate(cid, operations)
        schedule_lines = []
        for s in schedules:
            schedule_lines.append(
                f"  {s['day_of_week']}: {s.get('start_hour', 0)}:{s.get('start_minute', 'ZERO')} - "
                f"{s.get('end_hour', 24)}:{s.get('end_minute', 'ZERO')}"
            )
        return (
            f"Ad schedule set on campaign {campaign_id}:\n" +
            "\n".join(schedule_lines)
        )
    except Exception as e:
        return f"Failed to set ad schedule: {e}"


def set_location_targeting(
    campaign_id: str,
    location_ids: list[str] | None = None,
    excluded_location_ids: list[str] | None = None,
    targeting_mode: str = "PRESENCE",
    customer_id: str | None = None,
) -> str:
    """
    Set geographic targeting on a campaign.

    Args:
        campaign_id: Campaign to target
        location_ids: List of geo target constant IDs to target (e.g. ["2840"] for US, ["1014044"] for Sacramento CA)
        excluded_location_ids: List of geo target constant IDs to exclude
        targeting_mode: PRESENCE (people IN the area) or PRESENCE_OR_INTEREST. Default PRESENCE.
        customer_id: Target account

    Tip: Find geo IDs via GAQL:
        SELECT geo_target_constant.id, geo_target_constant.name
        FROM geo_target_constant WHERE geo_target_constant.name LIKE '%Sacramento%'
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")
    geo_service = get_service("GeoTargetConstantService")

    operations = []
    campaign_resource = campaign_service.campaign_path(cid, campaign_id)

    # Add targeted locations
    if location_ids:
        for loc_id in location_ids:
            op = client.get_type("MutateOperation")
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_resource
            criterion.location.geo_target_constant = geo_service.geo_target_constant_path(loc_id)
            operations.append(op)

    # Add excluded locations
    if excluded_location_ids:
        for loc_id in excluded_location_ids:
            op = client.get_type("MutateOperation")
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_resource
            criterion.negative = True
            criterion.location.geo_target_constant = geo_service.geo_target_constant_path(loc_id)
            operations.append(op)

    # Update targeting mode on the campaign
    mode_upper = targeting_mode.upper()
    campaign_operation = client.get_type("MutateOperation")
    campaign_op = campaign_operation.campaign_operation.update
    campaign_op.resource_name = campaign_resource

    if mode_upper == "PRESENCE":
        campaign_op.geo_target_type_setting.positive_geo_target_type = (
            client.enums.PositiveGeoTargetTypeEnum.PRESENCE
        )
    else:
        campaign_op.geo_target_type_setting.positive_geo_target_type = (
            client.enums.PositiveGeoTargetTypeEnum.SEARCH_INTEREST
        )

    field_mask = client.get_type("FieldMask")
    field_mask.paths.append("geo_target_type_setting.positive_geo_target_type")
    campaign_operation.campaign_operation.update_mask.CopyFrom(field_mask)
    operations.append(campaign_operation)

    try:
        mutate(cid, operations)
        targeted = ", ".join(location_ids) if location_ids else "none"
        excluded = ", ".join(excluded_location_ids) if excluded_location_ids else "none"
        return (
            f"Location targeting updated on campaign {campaign_id}:\n"
            f"  Targeted: {targeted}\n"
            f"  Excluded: {excluded}\n"
            f"  Mode: {mode_upper}"
        )
    except Exception as e:
        return f"Failed to set location targeting: {e}"


def remove_keywords(
    criterion_ids: list[str],
    ad_group_id: str,
    customer_id: str | None = None,
) -> str:
    """
    Remove keywords from an ad group.

    Args:
        criterion_ids: List of criterion IDs to remove (from get_keyword_performance output)
        ad_group_id: Ad group containing the keywords
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()

    operations = []
    for crit_id in criterion_ids:
        op = client.get_type("MutateOperation")
        resource_name = f"customers/{cid}/adGroupCriteria/{ad_group_id}~{crit_id}"
        op.ad_group_criterion_operation.remove = resource_name
        operations.append(op)

    try:
        mutate(cid, operations)
        return f"Removed {len(criterion_ids)} keyword(s) from ad group {ad_group_id}."
    except Exception as e:
        return f"Failed to remove keywords: {e}"


def remove_campaign(
    campaign_id: str,
    customer_id: str | None = None,
) -> str:
    """
    Remove (soft-delete) a campaign. Sets status to REMOVED.

    Args:
        campaign_id: Campaign to remove
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")

    # Get campaign name first
    try:
        query = f"SELECT campaign.name FROM campaign WHERE campaign.id = {campaign_id}"
        rows = list(search(cid, query))
        campaign_name = rows[0].campaign.name if rows else "Unknown"
    except Exception:
        campaign_name = "Unknown"

    operation = client.get_type("MutateOperation")
    operation.campaign_operation.remove = campaign_service.campaign_path(cid, campaign_id)

    try:
        mutate(cid, [operation])
        return f"Campaign removed: \"{campaign_name}\" (ID: {campaign_id})"
    except Exception as e:
        return f"Failed to remove campaign: {e}"


def update_ad_group(
    ad_group_id: str,
    name: str | None = None,
    cpc_bid_micros: int | None = None,
    status: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Update ad group properties.

    Args:
        ad_group_id: Ad group to update
        name: New name
        cpc_bid_micros: New default CPC bid in micros
        status: ENABLED, PAUSED, or REMOVED
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    ad_group_service = get_service("AdGroupService")

    operation = client.get_type("MutateOperation")
    ad_group_op = operation.ad_group_operation.update
    ad_group_op.resource_name = ad_group_service.ad_group_path(cid, ad_group_id)

    update_fields = []
    changes = []

    if name is not None:
        ad_group_op.name = name
        update_fields.append("name")
        changes.append(f"  Name: {name}")

    if cpc_bid_micros is not None:
        ad_group_op.cpc_bid_micros = cpc_bid_micros
        update_fields.append("cpc_bid_micros")
        changes.append(f"  CPC Bid: ${cpc_bid_micros / 1_000_000:.2f}")

    if status is not None:
        status_map = {
            "ENABLED": client.enums.AdGroupStatusEnum.ENABLED,
            "PAUSED": client.enums.AdGroupStatusEnum.PAUSED,
            "REMOVED": client.enums.AdGroupStatusEnum.REMOVED,
        }
        ad_group_op.status = status_map.get(status.upper(), client.enums.AdGroupStatusEnum.ENABLED)
        update_fields.append("status")
        changes.append(f"  Status: {status.upper()}")

    if not update_fields:
        return "No changes specified."

    field_mask = client.get_type("FieldMask")
    for f in update_fields:
        field_mask.paths.append(f)
    operation.ad_group_operation.update_mask.CopyFrom(field_mask)

    try:
        mutate(cid, [operation])
        return f"Ad group {ad_group_id} updated:\n" + "\n".join(changes)
    except Exception as e:
        return f"Failed to update ad group: {e}"


def manage_conversion_actions(
    action: str = "list",
    name: str | None = None,
    type: str | None = None,
    category: str | None = None,
    counting_type: str = "ONE_PER_CLICK",
    value: float | None = None,
    value_type: str = "USE_DEFAULT_VALUE",
    customer_id: str | None = None,
) -> str:
    """
    List or create conversion actions.

    Args:
        action: "list" to list all, "create" to create a new one
        name: Conversion action name (for create)
        type: WEBPAGE, PHONE_CALL, UPLOAD, etc. (for create)
        category: PURCHASE, LEAD, PHONE_CALL_LEAD, SUBMIT_LEAD_FORM, etc. (for create)
        counting_type: ONE_PER_CLICK or MANY_PER_CLICK (for create)
        value: Default conversion value (for create)
        value_type: USE_DEFAULT_VALUE or USE_VALUE_FROM_TAG (for create)
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()

    if action.lower() == "list":
        query = """
            SELECT
                conversion_action.id,
                conversion_action.name,
                conversion_action.type,
                conversion_action.status,
                conversion_action.category,
                conversion_action.counting_type
            FROM conversion_action
            WHERE conversion_action.status != 'REMOVED'
            ORDER BY conversion_action.name
        """
        try:
            rows = list(search(cid, query))
            if not rows:
                return "No conversion actions found."

            results = []
            for row in rows:
                ca = row.conversion_action
                results.append(
                    f"  {ca.name}\n"
                    f"    ID: {ca.id} | Type: {ca.type_.name} | Status: {ca.status.name}\n"
                    f"    Category: {ca.category.name} | Counting: {ca.counting_type.name}"
                )
            return f"Conversion Actions ({len(results)}):\n\n" + "\n\n".join(results)
        except Exception as e:
            return f"Failed to list conversion actions: {e}"

    elif action.lower() == "create":
        if not name or not type or not category:
            return "For create, name, type, and category are required."

        conversion_action_service = get_service("ConversionActionService")

        operation = client.get_type("MutateOperation")
        ca = operation.conversion_action_operation.create
        ca.name = name

        # Type
        type_enum = getattr(client.enums.ConversionActionTypeEnum, type.upper(), None)
        if type_enum is None:
            return f"Invalid type: {type}"
        ca.type_ = type_enum

        # Category
        cat_enum = getattr(client.enums.ConversionActionCategoryEnum, category.upper(), None)
        if cat_enum is None:
            return f"Invalid category: {category}"
        ca.category = cat_enum

        # Counting type
        count_enum = getattr(client.enums.ConversionActionCountingTypeEnum, counting_type.upper(), None)
        if count_enum:
            ca.counting_type = count_enum

        # Value settings
        if value is not None:
            ca.value_settings.default_value = value
        if value_type == "USE_DEFAULT_VALUE":
            ca.value_settings.always_use_default_value = True
        else:
            ca.value_settings.always_use_default_value = False

        ca.status = client.enums.ConversionActionStatusEnum.ENABLED

        try:
            mutate(cid, [operation])
            return (
                f"Conversion action created:\n"
                f"  Name: {name}\n"
                f"  Type: {type.upper()}\n"
                f"  Category: {category.upper()}\n"
                f"  Counting: {counting_type}\n"
                f"  Default Value: {value or 'None'}"
            )
        except Exception as e:
            return f"Failed to create conversion action: {e}"

    else:
        return f"Unknown action: {action}. Use 'list' or 'create'."
