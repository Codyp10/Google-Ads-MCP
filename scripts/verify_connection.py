"""
Verify Google Ads API connection by listing all accessible accounts under the MCC.
"""

from pathlib import Path
from google.ads.googleads.client import GoogleAdsClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOOGLE_ADS_YAML = str(PROJECT_ROOT / "google-ads.yaml")


def main():
    print("=== Google Ads Connection Verification ===\n")

    client = GoogleAdsClient.load_from_storage(GOOGLE_ADS_YAML)
    print("Client loaded successfully.\n")

    customer_service = client.get_service("CustomerService")
    response = customer_service.list_accessible_customers()
    print(f"Found {len(response.resource_names)} accessible account(s):\n")

    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT
            customer.id,
            customer.descriptive_name,
            customer.manager,
            customer.status
        FROM customer
        LIMIT 1
    """

    for resource_name in response.resource_names:
        customer_id = resource_name.split("/")[-1]
        try:
            rows = ga_service.search(customer_id=customer_id, query=query)
            for row in rows:
                status = row.customer.status.name if row.customer.status else "UNKNOWN"
                manager_flag = " [MANAGER]" if row.customer.manager else ""
                print(
                    f"  {row.customer.id} — {row.customer.descriptive_name}"
                    f" (Status: {status}){manager_flag}"
                )
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 120:
                error_msg = error_msg[:120] + "..."
            print(f"  {customer_id} — Could not fetch details: {error_msg}")

    print("\nConnection verified successfully!")


if __name__ == "__main__":
    main()
