"""
Resource metadata tool — discover valid GAQL fields for a Google Ads resource.
Ported from Google's official MCP (https://github.com/googleads/google-ads-mcp).
"""

import logging
from src.utils.google_ads_client import get_client, get_service

logger = logging.getLogger(__name__)


def get_resource_metadata(resource_name: str) -> str:
    """
    Discover selectable, filterable, and sortable fields for a Google Ads resource.

    Use this BEFORE writing GAQL queries to avoid invalid field paths. Returns
    every valid field on the resource, plus compatible metrics and segments.

    Args:
        resource_name: Resource name (e.g. 'campaign', 'ad_group', 'recommendation')
    """
    client = get_client()
    ga_field_service = get_service("GoogleAdsFieldService")

    selectable: set[str] = set()
    filterable: set[str] = set()
    sortable: set[str] = set()

    # Query 1: resource attribute fields
    attributes_query = (
        f"SELECT name, selectable, filterable, sortable "
        f"WHERE name LIKE '{resource_name}.%' AND category = 'ATTRIBUTE'"
    )
    try:
        resp = ga_field_service.search_google_ads_fields(
            request={"query": attributes_query}
        )
        for field in resp:
            if field.selectable:
                selectable.add(field.name)
            if field.filterable:
                filterable.add(field.name)
            if field.sortable:
                sortable.add(field.name)
    except Exception as e:
        logger.warning(f"Attribute query failed, trying fallback: {e}")
        fallback_query = (
            f"SELECT name, selectable, filterable, sortable "
            f"WHERE name LIKE '{resource_name}.%'"
        )
        try:
            resp = ga_field_service.search_google_ads_fields(
                request={"query": fallback_query}
            )
            for field in resp:
                if not field.name.startswith(f"{resource_name}."):
                    continue
                if field.selectable:
                    selectable.add(field.name)
                if field.filterable:
                    filterable.add(field.name)
                if field.sortable:
                    sortable.add(field.name)
        except Exception as e2:
            return f"Failed to fetch metadata for '{resource_name}': {e2}"

    # Query 2: selectable metrics and segments for this resource
    metrics_segments_query = (
        f"SELECT name, selectable, filterable, sortable "
        f"WHERE selectable_with CONTAINS ANY('{resource_name}')"
    )
    try:
        resp = ga_field_service.search_google_ads_fields(
            request={"query": metrics_segments_query}
        )
        for field in resp:
            if field.selectable:
                selectable.add(field.name)
            if field.filterable:
                filterable.add(field.name)
            if field.sortable:
                sortable.add(field.name)
    except Exception as e:
        logger.warning(f"Metrics/segments query failed: {e}")

    if not selectable:
        return (
            f"No fields found for '{resource_name}'. "
            f"Check the resource name — common ones: campaign, ad_group, "
            f"ad_group_ad, ad_group_criterion, customer, recommendation, "
            f"change_event, keyword_view, search_term_view."
        )

    sel = sorted(selectable)
    fil = sorted(filterable)
    sor = sorted(sortable)

    # Split by category for readability
    attrs = [f for f in sel if f.startswith(f"{resource_name}.")]
    metrics = [f for f in sel if f.startswith("metrics.")]
    segments = [f for f in sel if f.startswith("segments.")]
    other = [f for f in sel if f not in attrs and f not in metrics and f not in segments]

    lines = [f"Metadata for resource: {resource_name}\n"]
    lines.append(f"## Selectable attributes ({len(attrs)}):")
    lines.extend(f"  - {f}" for f in attrs)
    if metrics:
        lines.append(f"\n## Compatible metrics ({len(metrics)}):")
        lines.extend(f"  - {f}" for f in metrics)
    if segments:
        lines.append(f"\n## Compatible segments ({len(segments)}):")
        lines.extend(f"  - {f}" for f in segments)
    if other:
        lines.append(f"\n## Other selectable fields ({len(other)}):")
        lines.extend(f"  - {f}" for f in other)
    lines.append(f"\n## Filterable: {len(fil)} fields | Sortable: {len(sor)} fields")

    return "\n".join(lines)
