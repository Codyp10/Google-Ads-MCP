"""
Account management tools.
- list_accessible_accounts: list all accounts under the MCC
- set_active_account: set which customer ID to target
"""

from src.utils.google_ads_client import (
    get_client,
    get_service,
    search,
    set_active_customer_id,
    get_active_customer_id,
    resolve_customer_id,
)


def list_accessible_accounts() -> str:
    """
    List all Google Ads accounts accessible under the MCC.
    Returns account name, customer ID, manager status, and account status.
    """
    client = get_client()
    customer_service = get_service("CustomerService")
    response = customer_service.list_accessible_customers()

    if not response.resource_names:
        return "No accessible accounts found."

    # Get login_customer_id from config for querying child accounts
    login_id = client.login_customer_id

    results = []
    for resource_name in response.resource_names:
        customer_id = resource_name.split("/")[-1]
        try:
            query = """
                SELECT
                    customer.id,
                    customer.descriptive_name,
                    customer.manager,
                    customer.status
                FROM customer
                LIMIT 1
            """
            rows = search(customer_id, query)
            for row in rows:
                status = row.customer.status.name
                manager_flag = " [MANAGER]" if row.customer.manager else ""
                results.append(
                    f"  {row.customer.id} — {row.customer.descriptive_name} "
                    f"(Status: {status}){manager_flag}"
                )
        except Exception:
            results.append(f"  {customer_id} — (no access to details)")

    # Show active account if set
    try:
        active = get_active_customer_id()
        header = f"Active account: {active}\n\n"
    except ValueError:
        header = "No active account set. Use set_active_account to pick one.\n\n"

    return header + f"Accessible accounts ({len(response.resource_names)}):\n" + "\n".join(results)


def set_active_account(customer_id: str) -> str:
    """
    Set which customer ID to target for all subsequent operations.
    All tools will default to this account unless overridden.

    Args:
        customer_id: The Google Ads customer ID (10 digits, dashes optional)
    """
    clean_id = customer_id.replace("-", "")
    if not clean_id.isdigit() or len(clean_id) != 10:
        return f"Invalid customer ID: {customer_id}. Must be 10 digits."

    # Verify we can access this account
    try:
        query = """
            SELECT customer.id, customer.descriptive_name
            FROM customer LIMIT 1
        """
        rows = search(clean_id, query)
        name = "Unknown"
        for row in rows:
            name = row.customer.descriptive_name
    except Exception as e:
        return f"Cannot access account {clean_id}: {e}"

    set_active_customer_id(clean_id)
    return f"Active account set to: {clean_id} — {name}"
