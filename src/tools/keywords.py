"""
Keyword tools.
- add_keywords: add positive keywords to an ad group
- add_negative_keywords: add negative keywords at campaign or ad group level
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def add_keywords(
    ad_group_id: str,
    keywords: list[dict],
    customer_id: str | None = None,
) -> str:
    """
    Add keywords to an ad group.

    Args:
        ad_group_id: The ad group ID to add keywords to
        keywords: List of keyword dicts, each with:
            - text: keyword text (required)
            - match_type: BROAD, PHRASE, or EXACT (default: BROAD)
            - cpc_bid_micros: optional bid override in micros
        customer_id: Target account (uses active account if not specified)

    Example:
        add_keywords("123456", [
            {"text": "buy shoes online", "match_type": "EXACT", "cpc_bid_micros": 2000000},
            {"text": "best running shoes", "match_type": "PHRASE"},
            {"text": "shoes", "match_type": "BROAD"}
        ])
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    ad_group_service = get_service("AdGroupService")

    match_type_map = {
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
    }

    operations = []
    for kw in keywords:
        operation = client.get_type("MutateOperation")
        criterion = operation.ad_group_criterion_operation.create
        criterion.ad_group = ad_group_service.ad_group_path(cid, ad_group_id)
        criterion.keyword.text = kw["text"]
        criterion.keyword.match_type = match_type_map.get(
            kw.get("match_type", "BROAD").upper(),
            client.enums.KeywordMatchTypeEnum.BROAD,
        )
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED

        if kw.get("cpc_bid_micros"):
            criterion.cpc_bid_micros = kw["cpc_bid_micros"]

        operations.append(operation)

    try:
        response = mutate(cid, operations)
        results = []
        for i, result in enumerate(response.mutate_operation_responses):
            resource = result.ad_group_criterion_result.resource_name
            kw = keywords[i]
            match = kw.get("match_type", "BROAD").upper()
            bid = ""
            if kw.get("cpc_bid_micros"):
                bid = f" (bid: ${kw['cpc_bid_micros'] / 1_000_000:.2f})"
            results.append(f"  [{match}] {kw['text']}{bid}")

        return (
            f"Added {len(results)} keyword(s) to ad group {ad_group_id}:\n\n"
            + "\n".join(results)
        )
    except Exception as e:
        return f"Failed to add keywords: {e}"


def add_negative_keywords(
    keywords: list[dict],
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add negative keywords at campaign or ad group level.

    Args:
        keywords: List of keyword dicts, each with:
            - text: keyword text (required)
            - match_type: BROAD, PHRASE, or EXACT (default: EXACT)
        campaign_id: Campaign ID (for campaign-level negatives)
        ad_group_id: Ad group ID (for ad group-level negatives)
        customer_id: Target account (uses active account if not specified)

    You must specify either campaign_id or ad_group_id (not both).
    """
    if not campaign_id and not ad_group_id:
        return "Must specify either campaign_id or ad_group_id."
    if campaign_id and ad_group_id:
        return "Specify only one of campaign_id or ad_group_id."

    cid = resolve_customer_id(customer_id)
    client = get_client()

    match_type_map = {
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
    }

    operations = []
    for kw in keywords:
        operation = client.get_type("MutateOperation")

        if campaign_id:
            criterion = operation.campaign_criterion_operation.create
            campaign_service = get_service("CampaignService")
            criterion.campaign = campaign_service.campaign_path(cid, campaign_id)
            criterion.negative = True
            criterion.keyword.text = kw["text"]
            criterion.keyword.match_type = match_type_map.get(
                kw.get("match_type", "EXACT").upper(),
                client.enums.KeywordMatchTypeEnum.EXACT,
            )
        else:
            criterion = operation.ad_group_criterion_operation.create
            ad_group_service = get_service("AdGroupService")
            criterion.ad_group = ad_group_service.ad_group_path(cid, ad_group_id)
            criterion.negative = True
            criterion.keyword.text = kw["text"]
            criterion.keyword.match_type = match_type_map.get(
                kw.get("match_type", "EXACT").upper(),
                client.enums.KeywordMatchTypeEnum.EXACT,
            )

        operations.append(operation)

    level = f"campaign {campaign_id}" if campaign_id else f"ad group {ad_group_id}"
    try:
        response = mutate(cid, operations)
        results = []
        for i, kw in enumerate(keywords):
            match = kw.get("match_type", "EXACT").upper()
            results.append(f"  -{kw['text']} [{match}]")

        return (
            f"Added {len(results)} negative keyword(s) to {level}:\n\n"
            + "\n".join(results)
        )
    except Exception as e:
        return f"Failed to add negative keywords to {level}: {e}"
