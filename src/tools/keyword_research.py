"""
Keyword research tools.
- get_keyword_ideas: generate keyword suggestions from seed keywords or URL
- get_search_volume: get search volume for specific keywords
- get_keyword_forecasts: get click/impression/cost forecasts for keywords
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    resolve_customer_id,
)


def get_keyword_ideas(
    seed_keywords: list[str] | None = None,
    page_url: str | None = None,
    language_id: str = "1000",
    location_ids: list[str] | None = None,
    include_adult_keywords: bool = False,
    customer_id: str | None = None,
) -> str:
    """
    Generate keyword ideas from seed keywords and/or a URL.

    Args:
        seed_keywords: List of seed keyword strings (e.g. ["house painting", "exterior painter"])
        page_url: URL to extract keyword ideas from (e.g. "https://example.com/painting-services")
        language_id: Language criterion ID (default "1000" for English)
        location_ids: List of geo target IDs (default ["2840"] for US)
        include_adult_keywords: Include adult keywords (default False)
        customer_id: Target account
    """
    if not seed_keywords and not page_url:
        return "Must provide either seed_keywords or page_url (or both)."

    cid = resolve_customer_id(customer_id)
    client = get_client()
    keyword_plan_idea_service = get_service("KeywordPlanIdeaService")
    geo_service = get_service("GeoTargetConstantService")

    locations = location_ids or ["2840"]
    location_resources = [
        geo_service.geo_target_constant_path(loc_id) for loc_id in locations
    ]
    language_resource = f"languageConstants/{language_id}"

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = cid
    request.language = language_resource
    request.geo_target_constants.extend(location_resources)
    request.include_adult_keywords = include_adult_keywords
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    )

    if seed_keywords and page_url:
        request.keyword_and_url_seed.url = page_url
        request.keyword_and_url_seed.keywords.extend(seed_keywords)
    elif seed_keywords:
        request.keyword_seed.keywords.extend(seed_keywords)
    elif page_url:
        request.url_seed.url = page_url

    try:
        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

        results = []
        count = 0
        for idea in response:
            if count >= 50:  # Limit to top 50 ideas
                break
            metrics = idea.keyword_idea_metrics
            competition = metrics.competition.name if metrics.competition else "UNKNOWN"
            avg_searches = metrics.avg_monthly_searches or 0
            low_bid = (metrics.low_top_of_page_bid_micros or 0) / 1_000_000
            high_bid = (metrics.high_top_of_page_bid_micros or 0) / 1_000_000

            results.append(
                f"  {idea.text}\n"
                f"    Avg monthly searches: {avg_searches:,}\n"
                f"    Competition: {competition}\n"
                f"    Bid range: ${low_bid:.2f} - ${high_bid:.2f}"
            )
            count += 1

        if not results:
            return "No keyword ideas found. Try different seed keywords or URL."

        header = f"Keyword Ideas ({count} results):\n"
        if seed_keywords:
            header += f"  Seeds: {', '.join(seed_keywords)}\n"
        if page_url:
            header += f"  URL: {page_url}\n"
        header += f"  Location: {', '.join(locations)} | Language: {language_id}\n"

        return header + "\n" + "\n\n".join(results)

    except Exception as e:
        return f"Failed to get keyword ideas: {e}"


def get_search_volume(
    keywords: list[str],
    language_id: str = "1000",
    location_ids: list[str] | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Get search volume and competition data for specific keywords.

    Args:
        keywords: List of keywords to check (e.g. ["house painting", "exterior painter"])
        language_id: Language criterion ID (default "1000" for English)
        location_ids: List of geo target IDs (default ["2840"] for US)
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    keyword_plan_idea_service = get_service("KeywordPlanIdeaService")
    geo_service = get_service("GeoTargetConstantService")

    locations = location_ids or ["2840"]
    location_resources = [
        geo_service.geo_target_constant_path(loc_id) for loc_id in locations
    ]
    language_resource = f"languageConstants/{language_id}"

    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = cid
    request.keywords.extend(keywords)
    request.language = language_resource
    request.geo_target_constants.extend(location_resources)
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    )

    try:
        response = keyword_plan_idea_service.generate_keyword_historical_metrics(
            request=request
        )

        results = []
        for result in response.results:
            metrics = result.keyword_metrics
            competition = metrics.competition.name if metrics.competition else "UNKNOWN"
            avg_searches = metrics.avg_monthly_searches or 0
            low_bid = (metrics.low_top_of_page_bid_micros or 0) / 1_000_000
            high_bid = (metrics.high_top_of_page_bid_micros or 0) / 1_000_000

            # Monthly breakdown
            monthly = ""
            if metrics.monthly_search_volumes:
                recent_months = list(metrics.monthly_search_volumes)[-6:]
                monthly_strs = []
                for m in recent_months:
                    month_name = m.month.name if m.month else "?"
                    monthly_strs.append(f"{month_name[:3]} {m.year}: {m.monthly_searches:,}")
                monthly = "\n    Recent months: " + " | ".join(monthly_strs)

            results.append(
                f"  \"{result.text}\"\n"
                f"    Avg monthly searches: {avg_searches:,}\n"
                f"    Competition: {competition}\n"
                f"    Bid range: ${low_bid:.2f} - ${high_bid:.2f}{monthly}"
            )

        if not results:
            return "No search volume data found for these keywords."

        return (
            f"Search Volume Data ({len(results)} keywords):\n"
            f"  Location: {', '.join(locations)} | Language: {language_id}\n\n"
            + "\n\n".join(results)
        )

    except Exception as e:
        return f"Failed to get search volume: {e}"


def get_keyword_forecasts(
    keywords: list[dict],
    language_id: str = "1000",
    location_ids: list[str] | None = None,
    forecast_period_days: int = 30,
    customer_id: str | None = None,
) -> str:
    """
    Get click, impression, and cost forecasts for keywords.
    Uses a temporary keyword plan to generate forecasts.

    Args:
        keywords: List of keyword dicts with:
            - text: keyword text
            - match_type: BROAD, PHRASE, or EXACT (default BROAD)
            - cpc_bid_micros: bid in micros (default 2000000 = $2.00)
        language_id: Language criterion ID (default "1000" for English)
        location_ids: List of geo target IDs (default ["2840"] for US)
        forecast_period_days: Forecast period in days (default 30)
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)
    client = get_client()
    keyword_plan_service = get_service("KeywordPlanService")
    keyword_plan_campaign_service = get_service("KeywordPlanCampaignKeywordService")
    forecast_service = get_service("KeywordPlanService")

    locations = location_ids or ["2840"]

    # Step 1: Create a temporary keyword plan
    plan_op = client.get_type("MutateOperation")
    plan = plan_op.keyword_plan_operation.create
    plan.name = f"_temp_forecast_{cid}_{id(keywords)}"

    from datetime import datetime, timedelta
    start = datetime.now()
    end = start + timedelta(days=forecast_period_days)
    plan.forecast_period.start_date = start.strftime("%Y-%m-%d")
    plan.forecast_period.end_date = end.strftime("%Y-%m-%d")

    plan_temp_id = -1
    plan.resource_name = keyword_plan_service.keyword_plan_path(cid, plan_temp_id)

    # Step 2: Create a keyword plan campaign
    campaign_op = client.get_type("MutateOperation")
    kp_campaign = campaign_op.keyword_plan_campaign_operation.create
    kp_campaign.name = "_temp_campaign"
    kp_campaign.keyword_plan = plan.resource_name
    kp_campaign.cpc_bid_micros = 2_000_000

    kp_campaign_service = get_service("KeywordPlanCampaignService")
    campaign_temp_id = -2
    kp_campaign.resource_name = kp_campaign_service.keyword_plan_campaign_path(
        cid, campaign_temp_id
    )

    # Set targeting
    for loc_id in locations:
        geo_target = client.get_type("KeywordPlanGeoTarget")
        geo_service = get_service("GeoTargetConstantService")
        geo_target.geo_target_constant = geo_service.geo_target_constant_path(loc_id)
        kp_campaign.geo_targets.append(geo_target)

    kp_campaign.language_constants.append(f"languageConstants/{language_id}")

    # Step 3: Create keyword plan ad group
    ad_group_op = client.get_type("MutateOperation")
    kp_ad_group = ad_group_op.keyword_plan_ad_group_operation.create
    kp_ad_group.name = "_temp_ad_group"
    kp_ad_group.keyword_plan_campaign = kp_campaign.resource_name

    kp_ad_group_service = get_service("KeywordPlanAdGroupService")
    ad_group_temp_id = -3
    kp_ad_group.resource_name = kp_ad_group_service.keyword_plan_ad_group_path(
        cid, ad_group_temp_id
    )

    operations = [plan_op, campaign_op, ad_group_op]

    # Step 4: Add keywords
    match_type_map = {
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
    }

    kw_temp_id = -100
    kp_keyword_service = get_service("KeywordPlanAdGroupKeywordService")
    for kw in keywords:
        kw_op = client.get_type("MutateOperation")
        kp_keyword = kw_op.keyword_plan_ad_group_keyword_operation.create
        kp_keyword.keyword_plan_ad_group = kp_ad_group.resource_name
        kp_keyword.text = kw["text"]
        kp_keyword.match_type = match_type_map.get(
            kw.get("match_type", "BROAD").upper(),
            client.enums.KeywordMatchTypeEnum.BROAD,
        )
        kp_keyword.cpc_bid_micros = kw.get("cpc_bid_micros", 2_000_000)
        kp_keyword.resource_name = kp_keyword_service.keyword_plan_ad_group_keyword_path(
            cid, kw_temp_id
        )
        operations.append(kw_op)
        kw_temp_id -= 1

    try:
        from src.utils.google_ads_client import mutate

        # Create the keyword plan
        response = mutate(cid, operations)

        # Extract the keyword plan resource name
        plan_resource = None
        for result in response.mutate_operation_responses:
            if result.keyword_plan_result.resource_name:
                plan_resource = result.keyword_plan_result.resource_name
                break

        if not plan_resource:
            return "Failed to create keyword plan for forecasting."

        # Generate forecasts
        forecast_response = keyword_plan_service.generate_forecast_metrics(
            keyword_plan=plan_resource
        )

        results = []
        for i, forecast in enumerate(forecast_response.keyword_forecasts):
            kw = keywords[i] if i < len(keywords) else {"text": "unknown"}
            metrics = forecast.keyword_forecast

            clicks = metrics.clicks or 0
            impressions = metrics.impressions or 0
            cost_micros = metrics.cost_micros or 0
            ctr = metrics.ctr or 0
            avg_cpc = metrics.average_cpc or 0

            results.append(
                f"  \"{kw['text']}\" [{kw.get('match_type', 'BROAD').upper()}]\n"
                f"    Clicks: {clicks:,.0f}\n"
                f"    Impressions: {impressions:,.0f}\n"
                f"    CTR: {ctr:.2%}\n"
                f"    Avg CPC: ${avg_cpc / 1_000_000:.2f}\n"
                f"    Total Cost: ${cost_micros / 1_000_000:.2f}"
            )

        # Clean up: remove the temp keyword plan
        try:
            remove_op = client.get_type("MutateOperation")
            remove_op.keyword_plan_operation.remove = plan_resource
            mutate(cid, [remove_op])
        except Exception:
            pass  # Best effort cleanup

        if not results:
            return "No forecast data available for these keywords."

        total_clicks = sum(
            (f.keyword_forecast.clicks or 0) for f in forecast_response.keyword_forecasts
        )
        total_cost = sum(
            (f.keyword_forecast.cost_micros or 0) for f in forecast_response.keyword_forecasts
        )
        total_impressions = sum(
            (f.keyword_forecast.impressions or 0) for f in forecast_response.keyword_forecasts
        )

        return (
            f"Keyword Forecasts ({forecast_period_days}-day period):\n"
            f"  Location: {', '.join(locations)} | Language: {language_id}\n\n"
            + "\n\n".join(results)
            + f"\n\n  TOTALS:\n"
            f"    Clicks: {total_clicks:,.0f}\n"
            f"    Impressions: {total_impressions:,.0f}\n"
            f"    Cost: ${total_cost / 1_000_000:,.2f}"
        )

    except Exception as e:
        return f"Failed to get keyword forecasts: {e}"
