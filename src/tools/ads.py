"""
Ad creation tools.
- create_rsa: create a Responsive Search Ad
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
    mutate,
)


def create_rsa(
    ad_group_id: str,
    headlines: list[dict],
    descriptions: list[dict],
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
        headlines: List of headline dicts (max 15), each with:
            - text: headline text (max 30 chars)
            - pinned_to: optional pin position (1, 2, or 3)
        descriptions: List of description dicts (max 4), each with:
            - text: description text (max 90 chars)
            - pinned_to: optional pin position (1 or 2)
        final_url: The landing page URL
        path1: Display URL path 1 (max 15 chars)
        path2: Display URL path 2 (max 15 chars)
        tracking_template: Tracking URL template (optional)
        customer_id: Target account (uses active account if not specified)

    Example:
        create_rsa(
            ad_group_id="123456",
            headlines=[
                {"text": "Buy Shoes Online", "pinned_to": 1},
                {"text": "Free Shipping Today"},
                {"text": "Best Running Shoes"}
            ],
            descriptions=[
                {"text": "Shop our collection of premium shoes. Free shipping on orders over $50."},
                {"text": "Find your perfect pair. 30-day returns. Trusted since 2010."}
            ],
            final_url="https://example.com/shoes"
        )
    """
    # Validation
    if len(headlines) < 3:
        return "RSA requires at least 3 headlines."
    if len(headlines) > 15:
        return "RSA allows a maximum of 15 headlines."
    if len(descriptions) < 2:
        return "RSA requires at least 2 descriptions."
    if len(descriptions) > 4:
        return "RSA allows a maximum of 4 descriptions."

    for i, h in enumerate(headlines):
        if len(h["text"]) > 30:
            return f"Headline {i+1} exceeds 30 chars: '{h['text']}' ({len(h['text'])} chars)"
    for i, d in enumerate(descriptions):
        if len(d["text"]) > 90:
            return f"Description {i+1} exceeds 90 chars: '{d['text']}' ({len(d['text'])} chars)"

    cid = resolve_customer_id(customer_id)
    client = get_client()
    ad_group_service = get_service("AdGroupService")

    pin_map = {
        1: client.enums.ServedAssetFieldTypeEnum.HEADLINE_1,
        2: client.enums.ServedAssetFieldTypeEnum.HEADLINE_2,
        3: client.enums.ServedAssetFieldTypeEnum.HEADLINE_3,
    }
    desc_pin_map = {
        1: client.enums.ServedAssetFieldTypeEnum.DESCRIPTION_1,
        2: client.enums.ServedAssetFieldTypeEnum.DESCRIPTION_2,
    }

    operation = client.get_type("MutateOperation")
    ad_group_ad = operation.ad_group_ad_operation.create
    ad_group_ad.ad_group = ad_group_service.ad_group_path(cid, ad_group_id)
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED

    ad = ad_group_ad.ad
    ad.final_urls.append(final_url)

    if path1:
        ad.responsive_search_ad.path1 = path1
    if path2:
        ad.responsive_search_ad.path2 = path2
    if tracking_template:
        ad.tracking_url_template = tracking_template

    # Headlines
    for h in headlines:
        headline_asset = client.get_type("AdTextAsset")
        headline_asset.text = h["text"]
        if h.get("pinned_to") and h["pinned_to"] in pin_map:
            headline_asset.pinned_field = pin_map[h["pinned_to"]]
        ad.responsive_search_ad.headlines.append(headline_asset)

    # Descriptions
    for d in descriptions:
        desc_asset = client.get_type("AdTextAsset")
        desc_asset.text = d["text"]
        if d.get("pinned_to") and d["pinned_to"] in desc_pin_map:
            desc_asset.pinned_field = desc_pin_map[d["pinned_to"]]
        ad.responsive_search_ad.descriptions.append(desc_asset)

    try:
        response = mutate(cid, [operation])
        result = response.mutate_operation_responses[0]
        resource = result.ad_group_ad_result.resource_name

        headline_summary = "\n".join(
            f"    H{i+1}: \"{h['text']}\""
            + (f" [pinned to position {h['pinned_to']}]" if h.get('pinned_to') else "")
            for i, h in enumerate(headlines)
        )
        desc_summary = "\n".join(
            f"    D{i+1}: \"{d['text']}\""
            + (f" [pinned to position {d['pinned_to']}]" if d.get('pinned_to') else "")
            for i, d in enumerate(descriptions)
        )

        return (
            f"RSA created successfully!\n\n"
            f"  Ad Group: {ad_group_id}\n"
            f"  Final URL: {final_url}\n"
            f"  Display Path: /{path1}/{path2}\n"
            f"  Resource: {resource}\n\n"
            f"  Headlines ({len(headlines)}):\n{headline_summary}\n\n"
            f"  Descriptions ({len(descriptions)}):\n{desc_summary}"
        )
    except Exception as e:
        return f"Failed to create RSA: {e}"
