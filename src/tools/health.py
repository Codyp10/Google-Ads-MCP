"""
Account health and status tools.
- get_campaign_status: overview of all campaigns with status, budget, spend
- get_recommendations: Google's optimization recommendations
- get_change_history: recent changes in the account
"""

from src.utils.google_ads_client import resolve_customer_id, search


def _format_micros(micros: int) -> str:
    return f"${micros / 1_000_000:,.2f}"


def get_campaign_status(
    customer_id: str | None = None,
) -> str:
    """
    Get an overview of all campaigns with status, type, budget, and recent spend.

    Args:
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    query = """
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            campaign_budget.amount_micros,
            campaign.start_date,
            campaign.end_date,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions
        FROM campaign
        WHERE campaign.status != 'REMOVED'
            AND segments.date DURING LAST_30_DAYS
        ORDER BY metrics.cost_micros DESC
    """

    try:
        rows = search(cid, query)
        results = []
        total_budget = 0
        total_spend = 0

        for row in rows:
            c = row.campaign
            m = row.metrics
            budget = row.campaign_budget.amount_micros
            total_budget += budget
            total_spend += m.cost_micros

            dates = ""
            if c.start_date:
                dates += f" | Start: {c.start_date}"
            if c.end_date:
                dates += f" | End: {c.end_date}"

            results.append(
                f"  {c.name}\n"
                f"    ID: {c.id} | Status: {c.status.name} | Type: {c.advertising_channel_type.name}\n"
                f"    Daily Budget: {_format_micros(budget)} | Bidding: {c.bidding_strategy_type.name}\n"
                f"    Last 30 Days — Spend: {_format_micros(m.cost_micros)} | "
                f"Impr: {m.impressions:,} | Clicks: {m.clicks:,} | Conv: {m.conversions:.1f}"
                f"{dates}"
            )

        if not results:
            return "No campaigns found in this account."

        header = (
            f"Campaign Status Overview\n{'=' * 50}\n"
            f"Total Campaigns: {len(results)}\n"
            f"Combined Daily Budget: {_format_micros(total_budget)}\n"
            f"Total Spend (Last 30 Days): {_format_micros(total_spend)}\n"
            f"{'=' * 50}\n\n"
        )

        return header + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get campaign status: {e}"


def get_recommendations(
    customer_id: str | None = None,
) -> str:
    """
    Get Google's optimization recommendations for the account.

    Args:
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    query = """
        SELECT
            recommendation.type,
            recommendation.impact.base_metrics.impressions,
            recommendation.impact.base_metrics.clicks,
            recommendation.impact.base_metrics.cost_micros,
            recommendation.impact.base_metrics.conversions,
            recommendation.impact.potential_metrics.impressions,
            recommendation.impact.potential_metrics.clicks,
            recommendation.impact.potential_metrics.cost_micros,
            recommendation.impact.potential_metrics.conversions,
            recommendation.campaign
        FROM recommendation
        ORDER BY recommendation.type
        LIMIT 30
    """

    try:
        rows = search(cid, query)
        results = []
        type_counts = {}

        for row in rows:
            rec = row.recommendation
            rec_type = rec.type_.name
            type_counts[rec_type] = type_counts.get(rec_type, 0) + 1

            base = rec.impact.base_metrics
            potential = rec.impact.potential_metrics

            impr_change = ""
            if base.impressions > 0 and potential.impressions > 0:
                pct = ((potential.impressions - base.impressions) / base.impressions) * 100
                impr_change = f" (+{pct:.0f}% impressions)"

            campaign_name = rec.campaign.split("/")[-1] if rec.campaign else "Account-level"

            results.append(
                f"  [{rec_type}] Campaign: {campaign_name}{impr_change}"
            )

        if not results:
            return "No recommendations found. Your account is well-optimized!"

        # Summary by type
        summary_lines = [f"  {t}: {c}" for t, c in sorted(type_counts.items(), key=lambda x: -x[1])]
        summary = "\n".join(summary_lines)

        header = (
            f"Optimization Recommendations\n{'=' * 50}\n"
            f"Total: {len(results)} recommendations\n\n"
            f"By Type:\n{summary}\n"
            f"{'=' * 50}\n\n"
        )

        return header + "\n".join(results)
    except Exception as e:
        return f"Failed to get recommendations: {e}"


def get_change_history(
    date_range: str = "LAST_7_DAYS",
    customer_id: str | None = None,
) -> str:
    """
    Get recent changes made in the account.

    Args:
        date_range: LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, or "YYYY-MM-DD,YYYY-MM-DD"
        customer_id: Target account
    """
    cid = resolve_customer_id(customer_id)

    if "," in date_range:
        start, end = date_range.split(",")
        date_clause = f"change_event.change_date_time BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        # Map friendly names to actual date logic
        date_clause = f"change_event.change_date_time DURING {date_range}"

    query = f"""
        SELECT
            change_event.change_date_time,
            change_event.change_resource_type,
            change_event.resource_change_operation,
            change_event.user_email,
            change_event.client_type,
            change_event.campaign,
            change_event.ad_group,
            change_event.changed_fields
        FROM change_event
        WHERE {date_clause}
        ORDER BY change_event.change_date_time DESC
        LIMIT 50
    """

    try:
        rows = search(cid, query)
        results = []
        change_counts = {}

        for row in rows:
            ce = row.change_event
            resource_type = ce.change_resource_type.name
            operation = ce.resource_change_operation.name
            change_counts[resource_type] = change_counts.get(resource_type, 0) + 1

            user = ce.user_email or ce.client_type.name
            campaign = ce.campaign.split("/")[-1] if ce.campaign else "N/A"

            # Format changed fields
            fields = ""
            if ce.changed_fields:
                field_list = str(ce.changed_fields.paths[:3])
                fields = f" | Fields: {field_list}"

            results.append(
                f"  [{ce.change_date_time[:19]}] {operation} {resource_type}\n"
                f"    By: {user} | Campaign: {campaign}{fields}"
            )

        if not results:
            return f"No changes found for {date_range}."

        summary_lines = [f"  {t}: {c} changes" for t, c in sorted(change_counts.items(), key=lambda x: -x[1])]
        summary = "\n".join(summary_lines)

        header = (
            f"Change History ({date_range})\n{'=' * 50}\n"
            f"Total: {len(results)} changes\n\n"
            f"By Resource Type:\n{summary}\n"
            f"{'=' * 50}\n\n"
        )

        return header + "\n\n".join(results)
    except Exception as e:
        return f"Failed to get change history: {e}"
