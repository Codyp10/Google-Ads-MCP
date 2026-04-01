"""
Ad Group tools.
- create_ad_group: create an ad group linked to a campaign
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def create_ad_group(
    name: str,
    campaign_id: str,
    cpc_bid_micros: int = 1_000_000,
    status: str = "ENABLED",
    ad_group_type: str = "SEARCH_STANDARD",
    customer_id: str | None = None,
) -> str:
    """
    Create a new ad group linked to an existing campaign.

    Args:
        name: Ad group name
        campaign_id: The campaign ID (numeric) to attach to
        cpc_bid_micros: Default CPC bid in micros (1 dollar = 1,000,000). Default $1.00
        status: ENABLED (default) or PAUSED
        ad_group_type: SEARCH_STANDARD (default), DISPLAY_STANDARD, SHOPPING_PRODUCT_ADS
        customer_id: Target account (uses active account if not specified)
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    campaign_service = get_service("CampaignService")

    operation = client.get_type("MutateOperation")
    ad_group = operation.ad_group_operation.create
    ad_group.name = name
    ad_group.campaign = campaign_service.campaign_path(cid, campaign_id)
    ad_group.cpc_bid_micros = cpc_bid_micros

    # Status
    status_map = {
        "ENABLED": client.enums.AdGroupStatusEnum.ENABLED,
        "PAUSED": client.enums.AdGroupStatusEnum.PAUSED,
    }
    ad_group.status = status_map.get(status.upper(), client.enums.AdGroupStatusEnum.ENABLED)

    # Type
    type_map = {
        "SEARCH_STANDARD": client.enums.AdGroupTypeEnum.SEARCH_STANDARD,
        "DISPLAY_STANDARD": client.enums.AdGroupTypeEnum.DISPLAY_STANDARD,
        "SHOPPING_PRODUCT_ADS": client.enums.AdGroupTypeEnum.SHOPPING_PRODUCT_ADS,
    }
    ad_group.type_ = type_map.get(
        ad_group_type.upper(), client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    )

    try:
        response = mutate(cid, [operation])
        result = response.mutate_operation_responses[0]
        resource = result.ad_group_result.resource_name
        ad_group_id = resource.split("/")[-1]

        bid_str = f"${cpc_bid_micros / 1_000_000:.2f}"
        return (
            f"Ad group created successfully!\n\n"
            f"  Name: {name}\n"
            f"  Ad Group ID: {ad_group_id}\n"
            f"  Campaign: {campaign_id}\n"
            f"  Default CPC: {bid_str}\n"
            f"  Status: {status.upper()}\n"
            f"  Type: {ad_group_type}\n"
            f"  Resource: {resource}"
        )
    except Exception as e:
        return f"Failed to create ad group: {e}"
