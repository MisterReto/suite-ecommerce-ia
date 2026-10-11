"""Signed, short-lived requests between the UI and the sync service."""
from contextvars import ContextVar
import hashlib
import hmac
import os
import time

STORE_CONTEXT = ContextVar("store_context", default={})
TOOL_PATHS = {
    "/api/tools/inventory", "/api/tools/history", "/api/tools/review", "/api/tools/media-preview",
    "/api/tools/batch-status", "/api/tools/counts", "/api/tools/movement", "/api/tools/media-sync",
    "/api/tools/product-sync", "/api/tools/batch-create", "/api/tools/batch-step", "/api/tools/batch-resume",
    "/inventory-hub", "/inventory-manager", "/inventory-count",
    "/inventory-movement", "/inventory-count-bulk", "/inventory-history", "/inventory-review",
    "/inventory-sync", "/wc-health", "/wc-preview", "/wp-media-health",
    "/woocommerce-image-preview", "/woocommerce-product-sync",
    "/woocommerce-publish-preview", "/product-sync-one", "/image-sync-one",
    "/stock-preview-start", "/stock-preview-result", "/woocommerce-batch-sync",
    "/batch-create", "/batch-status", "/batch-step", "/batch-resume",
}
STORE_KEYS = (
    "WC_URL", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET", "WC_WRITE_ENABLED",
    "WP_URL", "WP_USERNAME", "WP_APP_PASSWORD", "WP_MEDIA_WRITE_ENABLED",
    "WP_MEDIA_METADATA_ENABLED",
)


def setting(key, default=""):
    aliases={"WC_URL":"WOOCOMMERCE_URL","WC_CONSUMER_KEY":"WOOCOMMERCE_CONSUMER_KEY","WC_CONSUMER_SECRET":"WOOCOMMERCE_CONSUMER_SECRET","WP_URL":"WORDPRESS_URL"}
    return STORE_CONTEXT.get().get(key, os.getenv(key,os.getenv(aliases.get(key,""),default)))


def signature(body: bytes, timestamp: str, nonce: str, key: str) -> str:
    message = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def verify(body, timestamp, nonce, supplied, key):
    if not key or len(key) < 32 or not nonce or len(nonce) > 100:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 120:
            return False
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(signature(body, timestamp, nonce, key), supplied or "")
