"""
Google Ads API client wrapper.
Provides a singleton-style client with active account management.
"""

import os
from pathlib import Path
from google.ads.googleads.client import GoogleAdsClient

# Resolve config path — check env var first, then default location
_DEFAULT_YAML = str(Path(__file__).resolve().parent.parent.parent / "google-ads.yaml")
GOOGLE_ADS_YAML = os.environ.get("GOOGLE_ADS_YAML_PATH", _DEFAULT_YAML)

# Module-level state
_client: GoogleAdsClient | None = None
_active_customer_id: str | None = None


def get_client() -> GoogleAdsClient:
    """Return the GoogleAdsClient, creating it on first call.
    Supports both yaml file (local) and environment variables (deployed).
    """
    global _client
    if _client is None:
        # If env vars are set, use them (for Railway/Render deployment)
        if os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
            _client = GoogleAdsClient.load_from_dict({
                "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
                "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
                "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
                "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
                "use_proto_plus": True,
            })
        else:
            _client = GoogleAdsClient.load_from_storage(GOOGLE_ADS_YAML)
    return _client


def get_active_customer_id() -> str:
    """Return the currently active customer ID, or raise if none is set."""
    if _active_customer_id is None:
        raise ValueError(
            "No active account set. Use set_active_account first, "
            "or pass customer_id explicitly."
        )
    return _active_customer_id


def set_active_customer_id(customer_id: str) -> None:
    """Set the active customer ID for subsequent operations."""
    global _active_customer_id
    _active_customer_id = customer_id.replace("-", "")


def resolve_customer_id(customer_id: str | None = None) -> str:
    """Resolve a customer ID — use explicit if given, otherwise active."""
    if customer_id:
        return customer_id.replace("-", "")
    return get_active_customer_id()


def get_service(service_name: str):
    """Get a Google Ads service by name."""
    return get_client().get_service(service_name)


def get_enum_type(enum_name: str):
    """Get a Google Ads enum type by name."""
    return get_client().enums.__getattr__(enum_name)


def search(customer_id: str, query: str):
    """Run a GAQL search query and return results."""
    ga_service = get_service("GoogleAdsService")
    return ga_service.search(customer_id=customer_id, query=query)


def search_stream(customer_id: str, query: str):
    """Run a GAQL search_stream query and yield results."""
    ga_service = get_service("GoogleAdsService")
    return ga_service.search_stream(customer_id=customer_id, query=query)


def mutate(customer_id: str, operations: list, partial_failure: bool = False):
    """Execute mutate operations via GoogleAdsService."""
    ga_service = get_service("GoogleAdsService")
    return ga_service.mutate(
        customer_id=customer_id,
        mutate_operations=operations,
        partial_failure=partial_failure,
    )
