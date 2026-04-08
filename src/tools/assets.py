"""
Asset tools for Google Ads.
- add_sitelinks: create sitelink assets and link to campaign/ad group
- add_callouts: create callout assets and link to campaign/ad group
- add_call_asset: create call asset (phone number) and link to campaign/ad group
- add_structured_snippets: create structured snippet assets and link to campaign/ad group
- add_image_asset: upload an image asset from file path or URL
"""

import requests as http_requests
from pathlib import Path

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def _link_asset_to_entity(
    client, cid: str, asset_resource_name: str, field_type,
    campaign_id: str | None = None, ad_group_id: str | None = None,
):
    """Helper: link an asset to a campaign or ad group."""
    operation = client.get_type("MutateOperation")

    if campaign_id:
        link = operation.campaign_asset_operation.create
        campaign_service = get_service("CampaignService")
        link.campaign = campaign_service.campaign_path(cid, campaign_id)
        link.asset = asset_resource_name
        link.field_type = field_type
    elif ad_group_id:
        link = operation.ad_group_asset_operation.create
        ad_group_service = get_service("AdGroupService")
        link.ad_group = ad_group_service.ad_group_path(cid, ad_group_id)
        link.asset = asset_resource_name
        link.field_type = field_type
    else:
        return None

    return operation


def add_sitelinks(
    sitelinks: list[dict],
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add sitelink assets and link them to a campaign or ad group.

    Args:
        sitelinks: List of sitelink dicts, each with:
            - link_text: sitelink headline (max 25 chars)
            - description1: first description line (max 35 chars)
            - description2: second description line (max 35 chars)
            - final_url: landing page URL
        campaign_id: Campaign to link sitelinks to
        ad_group_id: Ad group to link sitelinks to
        customer_id: Target account (uses active account if not specified)
    """
    if not campaign_id and not ad_group_id:
        return "Must specify either campaign_id or ad_group_id."

    cid = resolve_customer_id(customer_id)
    client = get_client()

    operations = []
    temp_id = -100
    asset_resource_names = []

    # Create sitelink assets
    for sl in sitelinks:
        operation = client.get_type("MutateOperation")
        asset = operation.asset_operation.create
        asset_service = get_service("AssetService")
        asset.resource_name = asset_service.asset_path(cid, temp_id)
        asset.sitelink_asset.link_text = sl["link_text"]
        asset.sitelink_asset.description1 = sl.get("description1", "")
        asset.sitelink_asset.description2 = sl.get("description2", "")
        asset.final_urls.append(sl["final_url"])
        operations.append(operation)
        asset_resource_names.append(asset.resource_name)
        temp_id -= 1

    # Link assets
    field_type = client.enums.AssetFieldTypeEnum.SITELINK
    for resource_name in asset_resource_names:
        link_op = _link_asset_to_entity(
            client, cid, resource_name, field_type,
            campaign_id=campaign_id, ad_group_id=ad_group_id,
        )
        if link_op:
            operations.append(link_op)

    try:
        response = mutate(cid, operations)
        level = f"campaign {campaign_id}" if campaign_id else f"ad group {ad_group_id}"
        details = "\n".join(
            f"  \"{sl['link_text']}\" → {sl['final_url']}" for sl in sitelinks
        )
        return (
            f"Added {len(sitelinks)} sitelink(s) to {level}:\n\n{details}"
        )
    except Exception as e:
        return f"Failed to add sitelinks: {e}"


def add_callouts(
    callout_texts: list[str],
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add callout assets and link to a campaign or ad group.

    Args:
        callout_texts: List of callout strings (max 25 chars each)
        campaign_id: Campaign to link callouts to
        ad_group_id: Ad group to link callouts to
        customer_id: Target account
    """
    if not campaign_id and not ad_group_id:
        return "Must specify either campaign_id or ad_group_id."

    cid = resolve_customer_id(customer_id)
    client = get_client()

    operations = []
    temp_id = -200
    asset_resource_names = []

    for text in callout_texts:
        if len(text) > 25:
            return f"Callout exceeds 25 chars: '{text}' ({len(text)} chars)"
        operation = client.get_type("MutateOperation")
        asset = operation.asset_operation.create
        asset_service = get_service("AssetService")
        asset.resource_name = asset_service.asset_path(cid, temp_id)
        asset.callout_asset.callout_text = text
        operations.append(operation)
        asset_resource_names.append(asset.resource_name)
        temp_id -= 1

    field_type = client.enums.AssetFieldTypeEnum.CALLOUT
    for resource_name in asset_resource_names:
        link_op = _link_asset_to_entity(
            client, cid, resource_name, field_type,
            campaign_id=campaign_id, ad_group_id=ad_group_id,
        )
        if link_op:
            operations.append(link_op)

    try:
        mutate(cid, operations)
        level = f"campaign {campaign_id}" if campaign_id else f"ad group {ad_group_id}"
        details = "\n".join(f"  \"{t}\"" for t in callout_texts)
        return f"Added {len(callout_texts)} callout(s) to {level}:\n\n{details}"
    except Exception as e:
        return f"Failed to add callouts: {e}"


def add_call_asset(
    phone_number: str,
    country_code: str = "US",
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add a call (phone number) asset and link to a campaign or ad group.

    Args:
        phone_number: Phone number string (e.g. "+18005551234")
        country_code: Two-letter country code (default: US)
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    if not campaign_id and not ad_group_id:
        return "Must specify either campaign_id or ad_group_id."

    cid = resolve_customer_id(customer_id)
    client = get_client()

    operations = []
    temp_id = -300

    operation = client.get_type("MutateOperation")
    asset = operation.asset_operation.create
    asset_service = get_service("AssetService")
    asset.resource_name = asset_service.asset_path(cid, temp_id)
    asset.call_asset.phone_number = phone_number
    asset.call_asset.country_code = country_code
    operations.append(operation)

    field_type = client.enums.AssetFieldTypeEnum.CALL
    link_op = _link_asset_to_entity(
        client, cid, asset.resource_name, field_type,
        campaign_id=campaign_id, ad_group_id=ad_group_id,
    )
    if link_op:
        operations.append(link_op)

    try:
        mutate(cid, operations)
        level = f"campaign {campaign_id}" if campaign_id else f"ad group {ad_group_id}"
        return f"Added call asset ({country_code} {phone_number}) to {level}"
    except Exception as e:
        return f"Failed to add call asset: {e}"


def add_structured_snippets(
    header: str,
    values: list[str],
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Add a structured snippet asset and link to a campaign or ad group.

    Args:
        header: Snippet header type. One of: Amenities, Brands, Courses, Degree programs,
               Destinations, Featured hotels, Insurance coverage, Neighborhoods, Service catalog,
               Shows, Styles, Types
        values: List of snippet values (min 3 recommended)
        campaign_id: Campaign to link to
        ad_group_id: Ad group to link to
        customer_id: Target account
    """
    if not campaign_id and not ad_group_id:
        return "Must specify either campaign_id or ad_group_id."

    cid = resolve_customer_id(customer_id)
    client = get_client()

    operations = []
    temp_id = -400

    operation = client.get_type("MutateOperation")
    asset = operation.asset_operation.create
    asset_service = get_service("AssetService")
    asset.resource_name = asset_service.asset_path(cid, temp_id)
    asset.structured_snippet_asset.header = header
    for v in values:
        asset.structured_snippet_asset.values.append(v)
    operations.append(operation)

    field_type = client.enums.AssetFieldTypeEnum.STRUCTURED_SNIPPET
    link_op = _link_asset_to_entity(
        client, cid, asset.resource_name, field_type,
        campaign_id=campaign_id, ad_group_id=ad_group_id,
    )
    if link_op:
        operations.append(link_op)

    try:
        mutate(cid, operations)
        level = f"campaign {campaign_id}" if campaign_id else f"ad group {ad_group_id}"
        vals = ", ".join(values)
        return f"Added structured snippet to {level}:\n  Header: {header}\n  Values: {vals}"
    except Exception as e:
        return f"Failed to add structured snippets: {e}"


def add_image_asset(
    name: str,
    image_source: str,
    customer_id: str | None = None,
) -> str:
    """
    Upload an image asset from a local file path or URL.

    Args:
        name: Asset name
        image_source: Local file path or URL to the image
        customer_id: Target account

    Returns the asset resource name for use in other operations.
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()

    # Load image bytes
    if image_source.startswith("http://") or image_source.startswith("https://"):
        resp = http_requests.get(image_source, timeout=30)
        resp.raise_for_status()
        image_data = resp.content
    else:
        path = Path(image_source)
        if not path.exists():
            return f"File not found: {image_source}"
        image_data = path.read_bytes()

    operation = client.get_type("MutateOperation")
    asset = operation.asset_operation.create
    asset.name = name
    asset.image_asset.data = image_data

    try:
        response = mutate(cid, [operation])
        result = response.mutate_operation_responses[0]
        resource = result.asset_result.resource_name
        size_kb = len(image_data) / 1024
        return (
            f"Image asset uploaded successfully!\n\n"
            f"  Name: {name}\n"
            f"  Size: {size_kb:.1f} KB\n"
            f"  Resource: {resource}\n\n"
            f"Use this resource name to attach the image to asset groups or ads."
        )
    except Exception as e:
        return f"Failed to upload image asset: {e}"
