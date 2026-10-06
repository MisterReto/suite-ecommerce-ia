"""Service boundaries reuse existing clients and permanent IDs instead of SKU scans."""

from app_security import clean_html
from woocommerce_client import WooCommerceClient
from wordpress_media import WordPressMediaClient


class WordPressMediaService:
    def __init__(self, client=None):
        self.client = client or WordPressMediaClient()

    def upload(self, data, name, alt_text):
        return self.client.upload_media(
            name, data, mime_type="image/jpeg", alt_text=alt_text, title=alt_text
        )

    def get(self, media_id):
        return self.client._request("GET", f"media/{int(media_id)}")

    def download(self, media_id):
        from urllib.parse import urlparse
        import os
        import requests
        from app_security import checked_image_type, validate_service_url

        info = self.get(media_id)
        url = info.get("source_url", "")
        validate_service_url(url)
        allowed = {
            urlparse(self.client.base_url).hostname,
            *os.getenv("MEDIA_ALLOWED_HOSTS", "").split(","),
        }
        if urlparse(url).hostname not in allowed:
            raise ValueError("El origen de medios no está autorizado.")
        with requests.get(
            url, timeout=(10, 60), stream=True, allow_redirects=False
        ) as response:
            if response.status_code != 200:
                raise ValueError("No se pudo leer el medio de WordPress.")
            chunks = bytearray()
            for chunk in response.iter_content(512 * 1024):
                chunks.extend(chunk)
                if len(chunks) > 12000000:
                    raise ValueError("La imagen de WordPress supera 12 MB.")
        raw = bytes(chunks)
        checked_image_type(urlparse(url).path.rsplit("/", 1)[-1], raw)
        return raw

    def update_alt(self, media_id, alt_text):
        import json

        return self.client._request(
            "POST",
            f"media/{int(media_id)}",
            body=json.dumps({"alt_text": str(alt_text)[:300]}).encode(),
            require_write=True,
        )


class WooCommerceService:
    def __init__(self, client=None):
        self.client = client or WooCommerceClient()
        if client is None:
            # New queued writes are verified explicitly, never blindly retried.
            for adapter in self.client.session.adapters.values():
                adapter.max_retries.allowed_methods = frozenset({"GET"})

    def product(self, product_id):
        return self.client.request("GET", f"products/{int(product_id)}")

    def variation(self, parent, variation):
        return self.client.request(
            "GET", f"products/{int(parent)}/variations/{int(variation)}"
        )

    def resolve(self, product):
        if product.woocommerce_variation_id and product.woocommerce_product_id:
            result = self.variation(
                product.woocommerce_product_id, product.woocommerce_variation_id
            )
            if str(result.get("sku", "")) != product.sku:
                raise ValueError(
                    "El mapping de WooCommerce ya no coincide con el SKU. Revísalo antes de escribir."
                )
            return result
        if product.woocommerce_product_id:
            result = self.product(product.woocommerce_product_id)
            if str(result.get("sku", "")) != product.sku:
                raise ValueError(
                    "El mapping de WooCommerce ya no coincide con el SKU. Revísalo antes de escribir."
                )
            return result
        return self.client.find_entity_by_sku(product.sku)

    def categories(self):
        return self.client.request(
            "GET", "products/categories", params={"per_page": 100}
        )

    def orders(self, since=None, page=1):
        return self.client.request(
            "GET",
            "orders",
            params={
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "desc",
                **({"after": since} if since else {}),
            },
        )

    def publish(self, product, media_ids, parent=None, terms=None):
        payload = {
            "name": product.name,
            "sku": product.sku,
            "description": clean_html(product.long_description),
            "short_description": clean_html(product.short_description),
            "status": "publish",
        }
        if media_ids:
            payload["images"] = [{"id": int(mid)} for mid in media_ids]
        if terms:
            payload.update(terms)
        if product.product_type == "variable":
            payload.update(type="variable", manage_stock=False)
            if product.attributes:
                payload["attributes"] = [
                    {
                        "name": k,
                        "visible": True,
                        "variation": True,
                        "options": v if isinstance(v, list) else [str(v)],
                    }
                    for k, v in product.attributes.items()
                ]
        else:
            payload["regular_price"] = str(product.price or 0)
            # Stock is published separately with an identified inventory operation.
        entity = self.resolve(product)
        if product.product_type == "variation":
            if not parent or not parent.woocommerce_product_id:
                raise ValueError("Publica primero el padre de esta variación.")
            payload.pop("short_description", None)
            payload["attributes"] = [
                {"name": k, "option": str(v)} for k, v in product.attributes.items()
            ]
            if media_ids:
                payload["image"] = {"id": int(media_ids[0])}
                payload.pop("images", None)
            if entity:
                return self.client.update_variation(
                    parent.woocommerce_product_id, int(entity["id"]), payload
                )
            return self.client.request(
                "POST",
                f"products/{parent.woocommerce_product_id}/variations",
                payload=payload,
            )
        if entity:
            return self.client.update_product(int(entity["id"]), payload)
        payload["type"] = product.product_type
        return self.client.request("POST", "products", payload=payload)
