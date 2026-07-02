from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)
DEFAULT_API_VERSION = "2025-10"
REQUEST_TIMEOUT_SECONDS = 30


class ShopifyApiError(RuntimeError):
    """Raised when Shopify returns a transport or GraphQL error."""


@dataclass(frozen=True)
class ShopifyConfig:
    store_domain: str
    admin_access_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    api_version: str = DEFAULT_API_VERSION

    @classmethod
    def from_env(cls) -> "ShopifyConfig":
        store_domain = os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
        admin_access_token = os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN", "").strip()
        client_id = os.getenv("SHOPIFY_CLIENT_ID", "").strip()
        client_secret = os.getenv("SHOPIFY_CLIENT_SECRET", "").strip()
        api_version = os.getenv("SHOPIFY_API_VERSION", DEFAULT_API_VERSION).strip()

        if not store_domain:
            raise ValueError("Missing required environment variable: SHOPIFY_STORE_DOMAIN")
        if not admin_access_token and not (client_id and client_secret):
            raise ValueError(
                "Set SHOPIFY_ADMIN_ACCESS_TOKEN or both SHOPIFY_CLIENT_ID "
                "and SHOPIFY_CLIENT_SECRET"
            )

        return cls(
            store_domain=store_domain.replace("https://", "").rstrip("/"),
            admin_access_token=admin_access_token or None,
            client_id=client_id or None,
            client_secret=client_secret or None,
            api_version=api_version,
        )

    @property
    def graphql_url(self) -> str:
        return (
            f"https://{self.store_domain}/admin/api/"
            f"{self.api_version}/graphql.json"
        )

    @property
    def access_token_url(self) -> str:
        return f"https://{self.store_domain}/admin/oauth/access_token"


class ShopifyGraphQLClient:
    def __init__(
        self,
        config: ShopifyConfig,
        session: requests.Session | None = None,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._access_token: str | None = config.admin_access_token

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self._get_access_token(),
        }
        payload = {"query": query, "variables": variables or {}}

        try:
            response = self.session.post(
                self.config.graphql_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.exception("Shopify GraphQL request failed")
            raise ShopifyApiError("Shopify GraphQL request failed") from exc

        body = response.json()
        if body.get("errors"):
            LOGGER.error("Shopify GraphQL returned errors: %s", body["errors"])
            raise ShopifyApiError(f"Shopify GraphQL returned errors: {body['errors']}")

        data = body.get("data")
        if not isinstance(data, dict):
            raise ShopifyApiError("Shopify GraphQL response did not include data")
        return data

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.config.client_id or not self.config.client_secret:
            raise ShopifyApiError("Shopify client credentials are not configured")

        try:
            response = self.session.post(
                self.config.access_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.exception("Shopify access token request failed")
            raise ShopifyApiError("Shopify access token request failed") from exc

        body = response.json()
        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ShopifyApiError("Shopify access token response did not include a token")

        self._access_token = access_token
        return access_token
