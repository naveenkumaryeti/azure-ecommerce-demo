"""Configuration - everything comes from environment variables (no secrets)."""
import os

STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME", "")
BLOB_ENDPOINT = os.environ.get("BLOB_ENDPOINT") or f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
# Only needed for USER-assigned identities; leave empty for system-assigned.
MANAGED_IDENTITY_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID") or None

CONTAINERS = {
    "products": "products",
    "images": "product-images",
    "orders": "orders",
    "audit": "audit-logs",
    "backups": "application-backups",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
