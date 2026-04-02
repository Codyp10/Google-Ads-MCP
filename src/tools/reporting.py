"""
Performance reporting tools.
- get_campaign_performance: campaign-level metrics for a date range
- get_ad_group_performance: ad group-level metrics
- get_keyword_performance: keyword metrics with quality scores
- get_search_terms_report: actual search queries triggering ads
- get_ad_performance: RSA performance with asset-level data
"""

from src.utils.google_ads_client import resolve_customer_id, search


def _format_micros(micros: int) -> str:
    """Convert micros to dollar string."""
    return f"${micros / 1_000_000:,.2f}"


def _format_rate(numerator: int, denominator: int) -> str:
    """Calculate and format a percentage."""
    if denominator == 0:
        return "0.00%"
    return f"{(numerator / denominator) * 100:.2f}%"


def get_campaign_performance(
    date_range: str = "LAST_30_DAYS",
    campaign_id: str | None = None,
    customer_id: str | None = None,
) -> str:
    """
    Get campaign performance metrics.

    Args:
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH,
                   LAST_MONTH, or custom range as "YYYY-MM-DD,YYYY-MM-DD"
        campaign_id: Optional — filter to a specific campaign
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    # Build date clause
    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    campaign_filter = ""
    if campaign_id:
        campaign_filter = f"AND campaign.id = {campaign_id}"

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_per_conversion
        FROM campaign
        WHERE {date_clause}
            AND campaign.status != 'REMOVED'
            {campaign_filter}
        ORDER BY metrics.cost_micros DESC
    """

    try:
        rows = search(cid, query)
        results = []
        total_cost = 0
        total_clicks = 0
        total_impressions = 0
        total_conversions = 0
        total_conv_value = 0

        for row in rows:
            c = row.campaign
            m = row.metrics
            total_cost += m.cost_micros
            total_clicks += m.clicks
            total_impressions += m.impressions
            total_conversions += m.conversions
            total_conv_value += m.conversions_value

            roas = f"{m.conversions_value / (m.cost_micros / 1_000_000):.2f}x" if m.cost_micros > 0 else "N/A"
            cpc = _format_micros(m.average_cpc) if m.clicks > 0 else "N/A"
            cpa = _format_micros(int(m.cost_per_conversion)) if m.conversions > 0 else "N/A"

            results.append(
                f"  {c.name} ({c.status.name})\n"
                f"    ID: {c.id} | Type: {c.advertising_channel_type.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | CTR: {m.ctr:.2%}\n"
                f"    Cost: {_format_micros(m.cost_micros)} | Avg CPC: {cpc}\n"
                f"    Conversions: {m.conversions:.1f} | CPA: {cpa} | Conv Value: {_format_micros(int(m.conversions_value))}\n"
                f"    ROAS: {roas}"
            )

        if not results:
            return f"No campaign data found for {date_range}."

        total_roas = f"{total_conv_value / (total_cost / 1_000_000):.2f}x" if total_cost > 0 else "N/A"
        total_ctr = _format_rate(total_clicks, total_impressions)

        header = (
            f"Campaign Performance ({date_range})\n"
            f"{'=' * 50}\n"
            f"Total: {_format_micros(total_cost)} spent | {total_impressions:,} impr | "
            f"{total_clicks:,} clicks | {total_ctr} CTR\n"
            f"Conversions: {total_conversions:.1f} | Conv Value: {_format_micros(int(total_conv_value))} | ROAS: {total_roas}\n"
            f"{'=' * 50}\n\n"
        )

        return header + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get campaign performance: {e}"


def get_ad_group_performance(
    campaign_id: str | None = None,
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
) -> str:
    """
    Get ad group performance metrics.

    Args:
        campaign_id: Optional — filter to a specific campaign
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH,
                   LAST_MONTH, or "YYYY-MM-DD,YYYY-MM-DD"
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    campaign_filter = ""
    if campaign_id:
        campaign_filter = f"AND campaign.id = {campaign_id}"

    query = f"""
        SELECT
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_per_conversion
        FROM ad_group
        WHERE {date_clause}
            AND ad_group.status != 'REMOVED'
            {campaign_filter}
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """

    try:
        rows = search(cid, query)
        results = []

        for row in rows:
            ag = row.ad_group
            m = row.metrics
            cpc = _format_micros(m.average_cpc) if m.clicks > 0 else "N/A"
            cpa = _format_micros(int(m.cost_per_conversion)) if m.conversions > 0 else "N/A"

            results.append(
                f"  {ag.name} ({ag.status.name})\n"
                f"    Campaign: {row.campaign.name} | Ad Group ID: {ag.id}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | CTR: {m.ctr:.2%}\n"
                f"    Cost: {_format_micros(m.cost_micros)} | Avg CPC: {cpc}\n"
                f"    Conversions: {m.conversions:.1f} | CPA: {cpa}"
            )

        if not results:
            return f"No ad group data found for {date_range}."

        return f"Ad Group Performance ({date_range})\n{'=' * 50}\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get ad group performance: {e}"


def get_keyword_performance(
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
) -> str:
    """
    Get keyword performance with quality scores.

    Args:
        campaign_id: Optional campaign filter
        ad_group_id: Optional ad group filter
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH,
                   LAST_MONTH, or "YYYY-MM-DD,YYYY-MM-DD"
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    filters = ""
    if campaign_id:
        filters += f"AND campaign.id = {campaign_id} "
    if ad_group_id:
        filters += f"AND ad_group.id = {ad_group_id} "

    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM keyword_view
        WHERE {date_clause}
            AND ad_group_criterion.status != 'REMOVED'
            {filters}
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """

    try:
        rows = search(cid, query)
        results = []

        for row in rows:
            kw = row.ad_group_criterion
            m = row.metrics
            qs = kw.quality_info.quality_score if kw.quality_info.quality_score > 0 else "N/A"
            cpc = _format_micros(m.average_cpc) if m.clicks > 0 else "N/A"

            results.append(
                f"  [{kw.keyword.match_type.name}] {kw.keyword.text}\n"
                f"    Campaign: {row.campaign.name} | Ad Group: {row.ad_group.name}\n"
                f"    QS: {qs} | Ad Relevance: {kw.quality_info.creative_quality_score.name} | "
                f"Landing: {kw.quality_info.post_click_quality_score.name} | "
                f"CTR: {kw.quality_info.search_predicted_ctr.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | CTR: {m.ctr:.2%}\n"
                f"    Cost: {_format_micros(m.cost_micros)} | Avg CPC: {cpc} | Conv: {m.conversions:.1f}"
            )

        if not results:
            return f"No keyword data found for {date_range}."

        return f"Keyword Performance ({date_range})\n{'=' * 50}\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get keyword performance: {e}"


def get_search_terms_report(
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
) -> str:
    """
    Get search terms report — actual queries people typed.

    Args:
        campaign_id: Optional campaign filter
        ad_group_id: Optional ad group filter
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH,
                   LAST_MONTH, or "YYYY-MM-DD,YYYY-MM-DD"
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    filters = ""
    if campaign_id:
        filters += f"AND campaign.id = {campaign_id} "
    if ad_group_id:
        filters += f"AND ad_group.id = {ad_group_id} "

    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            search_term_view.search_term,
            search_term_view.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM search_term_view
        WHERE {date_clause}
            {filters}
        ORDER BY metrics.impressions DESC
        LIMIT 50
    """

    try:
        rows = search(cid, query)
        results = []

        for row in rows:
            st = row.search_term_view
            m = row.metrics
            status_label = st.status.name if st.status else ""

            results.append(
                f"  \"{st.search_term}\" [{status_label}]\n"
                f"    Campaign: {row.campaign.name} | Ad Group: {row.ad_group.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | CTR: {m.ctr:.2%}\n"
                f"    Cost: {_format_micros(m.cost_micros)} | Conv: {m.conversions:.1f}"
            )

        if not results:
            return f"No search term data found for {date_range}."

        return f"Search Terms Report ({date_range})\n{'=' * 50}\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get search terms report: {e}"


def get_ad_performance(
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    date_range: str = "LAST_30_DAYS",
    customer_id: str | None = None,
) -> str:
    """
    Get ad performance metrics.

    Args:
        campaign_id: Optional campaign filter
        ad_group_id: Optional ad group filter
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH,
                   LAST_MONTH, or "YYYY-MM-DD,YYYY-MM-DD"
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    filters = ""
    if campaign_id:
        filters += f"AND campaign.id = {campaign_id} "
    if ad_group_id:
        filters += f"AND ad_group.id = {ad_group_id} "

    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_ad.ad.id,
            ad_group_ad.ad.type,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.ad.final_urls,
            ad_group_ad.policy_summary.approval_status,
            ad_group_ad.ad_strength,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group_ad
        WHERE {date_clause}
            AND ad_group_ad.status != 'REMOVED'
            {filters}
        ORDER BY metrics.impressions DESC
        LIMIT 30
    """

    try:
        rows = search(cid, query)
        results = []

        for row in rows:
            ad = row.ad_group_ad.ad
            m = row.metrics
            cpc = _format_micros(m.average_cpc) if m.clicks > 0 else "N/A"

            # Get headlines
            headlines = []
            if ad.responsive_search_ad and ad.responsive_search_ad.headlines:
                headlines = [h.text for h in ad.responsive_search_ad.headlines[:5]]

            headline_str = " | ".join(headlines) if headlines else "N/A"
            ad_strength = row.ad_group_ad.ad_strength.name if row.ad_group_ad.ad_strength else "N/A"
            approval = row.ad_group_ad.policy_summary.approval_status.name if row.ad_group_ad.policy_summary else "N/A"

            results.append(
                f"  Ad {ad.id} ({ad.type_.name})\n"
                f"    Campaign: {row.campaign.name} | Ad Group: {row.ad_group.name}\n"
                f"    Headlines: {headline_str}\n"
                f"    Ad Strength: {ad_strength} | Approval: {approval}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | CTR: {m.ctr:.2%}\n"
                f"    Cost: {_format_micros(m.cost_micros)} | Avg CPC: {cpc} | Conv: {m.conversions:.1f}"
            )

        if not results:
            return f"No ad data found for {date_range}."

        return f"Ad Performance ({date_range})\n{'=' * 50}\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get ad performance: {e}"
