"""
Flexible GAQL query tool.
- run_gaql_query: run any custom Google Ads Query Language query
"""

from src.utils.google_ads_client import resolve_customer_id, search


def run_gaql_query(
    query: str,
    customer_id: str | None = None,
) -> str:
    """
    Run a custom GAQL (Google Ads Query Language) query.

    This is a power tool — you can query any resource in the Google Ads API.
    See https://developers.google.com/google-ads/api/fields/v17/overview for
    available fields.

    Args:
        query: A valid GAQL query string. Examples:
            - SELECT campaign.name, metrics.clicks FROM campaign WHERE segments.date DURING LAST_7_DAYS
            - SELECT ad_group.name, metrics.impressions FROM ad_group WHERE campaign.id = 123456
            - SELECT customer.descriptive_name, customer.id FROM customer
        customer_id: Target account

    Returns formatted results as a table.
    """
    cid = resolve_customer_id(customer_id)

    try:
        rows = search(cid, query)
        results = []
        row_count = 0

        for row in rows:
            row_count += 1
            if row_count > 100:
                results.append(f"\n... truncated at 100 rows (more results available)")
                break

            # Extract all fields from the row into a readable format
            row_data = _extract_row_fields(row)
            results.append(row_data)

        if not results:
            return "Query returned no results."

        return f"Query Results ({row_count} rows):\n{'=' * 50}\n\n" + "\n\n".join(results)
    except Exception as e:
        error_msg = str(e)
        if "QUERY_ERROR" in error_msg or "INVALID" in error_msg:
            return f"GAQL Query Error: {error_msg}\n\nCheck your query syntax and field names."
        return f"Failed to run query: {error_msg}"


def _extract_row_fields(row) -> str:
    """Recursively extract and format fields from a protobuf row."""
    lines = []
    _extract_message(row, "", lines)
    return "\n".join(f"  {line}" for line in lines)


def _extract_message(message, prefix: str, lines: list):
    """Walk a protobuf message and collect non-default field values."""
    try:
        # For proto-plus messages, iterate over set fields
        fields = []
        for field_name in dir(message):
            if field_name.startswith("_"):
                continue
            if field_name in ("DESCRIPTOR", "Meta"):
                continue
            try:
                value = getattr(message, field_name)
                if callable(value):
                    continue
                # Skip empty/default values
                if value is None or value == 0 or value == "" or value == [] or value == False:
                    continue
                if hasattr(value, "DESCRIPTOR"):
                    # Nested message
                    _extract_message(value, f"{prefix}{field_name}.", lines)
                elif hasattr(value, 'name') and hasattr(value, 'value'):
                    # Enum
                    lines.append(f"{prefix}{field_name}: {value.name}")
                elif isinstance(value, (list, tuple)):
                    if len(value) > 0:
                        items = [str(v) for v in value[:10]]
                        lines.append(f"{prefix}{field_name}: [{', '.join(items)}]")
                elif isinstance(value, (int, float)):
                    if "micros" in field_name:
                        lines.append(f"{prefix}{field_name}: {value} (${value / 1_000_000:,.2f})")
                    else:
                        lines.append(f"{prefix}{field_name}: {value:,}" if isinstance(value, int) and value > 999 else f"{prefix}{field_name}: {value}")
                else:
                    lines.append(f"{prefix}{field_name}: {value}")
            except (AttributeError, TypeError):
                continue
    except Exception:
        lines.append(f"{prefix}: {str(message)[:200]}")
