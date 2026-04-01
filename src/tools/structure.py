"""
Utility tools for previewing and pushing full campaign structures.
- preview_structure: human-readable summary of what will be created
- push_structure: create everything in correct order
"""

import json
from src.tools.campaigns import create_campaign
from src.tools.pmax import create_pmax_campaign, create_asset_group
from src.tools.ad_groups import create_ad_group
from src.tools.keywords import add_keywords, add_negative_keywords
from src.tools.ads import create_rsa
from src.tools.assets import (
    add_sitelinks,
    add_callouts,
    add_call_asset,
    add_structured_snippets,
)


def preview_structure(structure: dict) -> str:
    """
    Preview a full campaign structure without pushing anything live.
    Returns a human-readable summary of everything that would be created.

    Args:
        structure: A dict describing the full campaign structure. Expected format:
            {
                "campaign": {
                    "name": "My Campaign",
                    "campaign_type": "SEARCH",
                    "daily_budget_micros": 10000000,
                    "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                    ...
                },
                "ad_groups": [
                    {
                        "name": "Ad Group 1",
                        "cpc_bid_micros": 1000000,
                        "keywords": [
                            {"text": "buy shoes", "match_type": "EXACT"}
                        ],
                        "negative_keywords": [
                            {"text": "free", "match_type": "EXACT"}
                        ],
                        "ads": [
                            {
                                "headlines": [{"text": "Buy Shoes"}],
                                "descriptions": [{"text": "Great shoes."}],
                                "final_url": "https://example.com"
                            }
                        ]
                    }
                ],
                "sitelinks": [...],
                "callouts": [...],
                "call_asset": {"phone_number": "+18005551234"},
                "structured_snippets": {"header": "Types", "values": [...]}
            }
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  CAMPAIGN STRUCTURE PREVIEW")
    lines.append("  (Nothing will be created — review only)")
    lines.append("=" * 60)

    # Campaign
    campaign = structure.get("campaign", {})
    if campaign:
        budget = campaign.get("daily_budget_micros", 0) / 1_000_000
        lines.append(f"\n📋 CAMPAIGN: {campaign.get('name', 'Unnamed')}")
        lines.append(f"   Type: {campaign.get('campaign_type', 'SEARCH')}")
        lines.append(f"   Budget: ${budget:.2f}/day")
        lines.append(f"   Bidding: {campaign.get('bidding_strategy', 'MAXIMIZE_CONVERSIONS')}")
        lines.append(f"   Status: {campaign.get('status', 'PAUSED')}")
        if campaign.get("location_ids"):
            lines.append(f"   Locations: {', '.join(campaign['location_ids'])}")
        if campaign.get("language_ids"):
            lines.append(f"   Languages: {', '.join(campaign['language_ids'])}")
        if campaign.get("start_date"):
            lines.append(f"   Start: {campaign['start_date']}")
        if campaign.get("end_date"):
            lines.append(f"   End: {campaign['end_date']}")

    # Ad Groups
    ad_groups = structure.get("ad_groups", [])
    for i, ag in enumerate(ad_groups, 1):
        bid = ag.get("cpc_bid_micros", 0) / 1_000_000
        lines.append(f"\n  📁 AD GROUP {i}: {ag.get('name', 'Unnamed')}")
        lines.append(f"     Default CPC: ${bid:.2f}")
        lines.append(f"     Status: {ag.get('status', 'ENABLED')}")

        # Keywords
        keywords = ag.get("keywords", [])
        if keywords:
            lines.append(f"\n     🔑 Keywords ({len(keywords)}):")
            for kw in keywords:
                match = kw.get("match_type", "BROAD").upper()
                bid_str = ""
                if kw.get("cpc_bid_micros"):
                    bid_str = f" (bid: ${kw['cpc_bid_micros'] / 1_000_000:.2f})"
                lines.append(f"        [{match}] {kw['text']}{bid_str}")

        # Negative Keywords
        negatives = ag.get("negative_keywords", [])
        if negatives:
            lines.append(f"\n     🚫 Negative Keywords ({len(negatives)}):")
            for nk in negatives:
                match = nk.get("match_type", "EXACT").upper()
                lines.append(f"        -{nk['text']} [{match}]")

        # Ads
        ads = ag.get("ads", [])
        for j, ad in enumerate(ads, 1):
            lines.append(f"\n     📝 RSA {j}:")
            lines.append(f"        Final URL: {ad.get('final_url', 'N/A')}")
            for k, h in enumerate(ad.get("headlines", []), 1):
                pin = f" [pinned {h['pinned_to']}]" if h.get("pinned_to") else ""
                lines.append(f"        H{k}: \"{h['text']}\"{pin}")
            for k, d in enumerate(ad.get("descriptions", []), 1):
                pin = f" [pinned {d['pinned_to']}]" if d.get("pinned_to") else ""
                lines.append(f"        D{k}: \"{d['text']}\"{pin}")

    # Assets
    sitelinks = structure.get("sitelinks", [])
    if sitelinks:
        lines.append(f"\n  🔗 SITELINKS ({len(sitelinks)}):")
        for sl in sitelinks:
            lines.append(f"     \"{sl['link_text']}\" → {sl['final_url']}")

    callouts = structure.get("callouts", [])
    if callouts:
        lines.append(f"\n  💬 CALLOUTS ({len(callouts)}):")
        for c in callouts:
            lines.append(f"     \"{c}\"")

    call = structure.get("call_asset")
    if call:
        lines.append(f"\n  📞 CALL: {call.get('phone_number', 'N/A')}")

    snippets = structure.get("structured_snippets")
    if snippets:
        lines.append(f"\n  📋 STRUCTURED SNIPPETS:")
        lines.append(f"     Header: {snippets['header']}")
        lines.append(f"     Values: {', '.join(snippets['values'])}")

    lines.append("\n" + "=" * 60)
    total_kw = sum(len(ag.get("keywords", [])) for ag in ad_groups)
    total_ads = sum(len(ag.get("ads", [])) for ag in ad_groups)
    lines.append(
        f"  TOTALS: 1 campaign, {len(ad_groups)} ad groups, "
        f"{total_kw} keywords, {total_ads} ads, "
        f"{len(sitelinks)} sitelinks, {len(callouts)} callouts"
    )
    lines.append("=" * 60)
    lines.append("\nUse push_structure with this same JSON to create everything live.")

    return "\n".join(lines)


def push_structure(
    structure: dict,
    customer_id: str | None = None,
) -> str:
    """
    Push a full campaign structure to Google Ads in the correct order:
    campaign -> ad groups -> keywords -> ads -> assets.

    IMPORTANT: This will create real entities in Google Ads.
    Always use preview_structure first to review.

    Args:
        structure: Same format as preview_structure
        customer_id: Target account (uses active account if not specified)
    """
    results = []
    errors = []

    campaign_data = structure.get("campaign", {})
    campaign_id = None

    # Step 1: Create Campaign
    if campaign_data:
        campaign_type = campaign_data.get("campaign_type", "SEARCH").upper()

        if campaign_type == "PERFORMANCE_MAX" or campaign_type == "PMAX":
            result = create_pmax_campaign(
                name=campaign_data["name"],
                daily_budget_micros=campaign_data.get("daily_budget_micros", 10_000_000),
                bidding_strategy=campaign_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                target_cpa_micros=campaign_data.get("target_cpa_micros"),
                target_roas=campaign_data.get("target_roas"),
                location_ids=campaign_data.get("location_ids"),
                language_ids=campaign_data.get("language_ids"),
                start_date=campaign_data.get("start_date"),
                end_date=campaign_data.get("end_date"),
                status=campaign_data.get("status", "PAUSED"),
                customer_id=customer_id,
            )
        else:
            result = create_campaign(
                name=campaign_data["name"],
                campaign_type=campaign_type,
                daily_budget_micros=campaign_data.get("daily_budget_micros", 10_000_000),
                bidding_strategy=campaign_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                target_cpa_micros=campaign_data.get("target_cpa_micros"),
                target_roas=campaign_data.get("target_roas"),
                network_settings=campaign_data.get("network_settings"),
                location_ids=campaign_data.get("location_ids"),
                language_ids=campaign_data.get("language_ids"),
                ad_schedule=campaign_data.get("ad_schedule"),
                start_date=campaign_data.get("start_date"),
                end_date=campaign_data.get("end_date"),
                status=campaign_data.get("status", "PAUSED"),
                customer_id=customer_id,
            )

        results.append(f"CAMPAIGN:\n{result}")

        if "Failed" in result:
            errors.append("Campaign creation failed. Aborting.")
            return "\n\n".join(results) + "\n\nErrors:\n" + "\n".join(errors)

        # Extract campaign ID from result
        for line in result.split("\n"):
            if "customers/" in line and "/campaigns/" in line:
                campaign_id = line.split("/campaigns/")[-1].strip()
                break

    if not campaign_id:
        errors.append("Could not extract campaign ID. Aborting ad group creation.")
        return "\n\n".join(results) + "\n\nErrors:\n" + "\n".join(errors)

    # Step 2: Create Ad Groups, Keywords, Ads
    for ag_data in structure.get("ad_groups", []):
        ag_result = create_ad_group(
            name=ag_data["name"],
            campaign_id=campaign_id,
            cpc_bid_micros=ag_data.get("cpc_bid_micros", 1_000_000),
            status=ag_data.get("status", "ENABLED"),
            customer_id=customer_id,
        )
        results.append(f"AD GROUP:\n{ag_result}")

        if "Failed" in ag_result:
            errors.append(f"Ad group '{ag_data['name']}' failed. Skipping its keywords/ads.")
            continue

        # Extract ad group ID
        ad_group_id = None
        for line in ag_result.split("\n"):
            if "Ad Group ID:" in line:
                ad_group_id = line.split(":")[-1].strip()
                break

        if not ad_group_id:
            errors.append(f"Could not extract ad group ID for '{ag_data['name']}'.")
            continue

        # Keywords
        if ag_data.get("keywords"):
            kw_result = add_keywords(
                ad_group_id=ad_group_id,
                keywords=ag_data["keywords"],
                customer_id=customer_id,
            )
            results.append(f"KEYWORDS:\n{kw_result}")

        # Negative Keywords (ad group level)
        if ag_data.get("negative_keywords"):
            nk_result = add_negative_keywords(
                keywords=ag_data["negative_keywords"],
                ad_group_id=ad_group_id,
                customer_id=customer_id,
            )
            results.append(f"NEGATIVE KEYWORDS:\n{nk_result}")

        # RSA Ads
        for ad_data in ag_data.get("ads", []):
            rsa_result = create_rsa(
                ad_group_id=ad_group_id,
                headlines=ad_data["headlines"],
                descriptions=ad_data["descriptions"],
                final_url=ad_data["final_url"],
                path1=ad_data.get("path1", ""),
                path2=ad_data.get("path2", ""),
                tracking_template=ad_data.get("tracking_template", ""),
                customer_id=customer_id,
            )
            results.append(f"RSA:\n{rsa_result}")

    # Step 3: Campaign-level Assets
    if structure.get("sitelinks"):
        sl_result = add_sitelinks(
            sitelinks=structure["sitelinks"],
            campaign_id=campaign_id,
            customer_id=customer_id,
        )
        results.append(f"SITELINKS:\n{sl_result}")

    if structure.get("callouts"):
        co_result = add_callouts(
            callout_texts=structure["callouts"],
            campaign_id=campaign_id,
            customer_id=customer_id,
        )
        results.append(f"CALLOUTS:\n{co_result}")

    if structure.get("call_asset"):
        call_data = structure["call_asset"]
        call_result = add_call_asset(
            phone_number=call_data["phone_number"],
            country_code=call_data.get("country_code", "US"),
            campaign_id=campaign_id,
            customer_id=customer_id,
        )
        results.append(f"CALL ASSET:\n{call_result}")

    if structure.get("structured_snippets"):
        ss_data = structure["structured_snippets"]
        ss_result = add_structured_snippets(
            header=ss_data["header"],
            values=ss_data["values"],
            campaign_id=campaign_id,
            customer_id=customer_id,
        )
        results.append(f"STRUCTURED SNIPPETS:\n{ss_result}")

    # Summary
    summary = "\n\n---\n\n".join(results)
    if errors:
        summary += "\n\n⚠️ ERRORS:\n" + "\n".join(errors)
    else:
        summary += "\n\n✅ All operations completed successfully!"

    return summary
