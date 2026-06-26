import pytest

from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.body


class FakeSession:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        if url.endswith("/admin/oauth/access_token"):
            return FakeResponse({"access_token": "shpat_test", "scope": "read_products"})
        return FakeResponse({"data": {"products": {"edges": []}}})


def test_client_uses_client_credentials_to_fetch_access_token() -> None:
    session = FakeSession()
    config = ShopifyConfig(
        store_domain="example.myshopify.com",
        client_id="client-id",
        client_secret="client-secret",
    )
    client = ShopifyGraphQLClient(config=config, session=session)  # type: ignore[arg-type]

    data = client.execute("query { products(first: 1) { edges { node { id } } } }")

    assert data == {"products": {"edges": []}}
    assert session.posts[0]["url"] == (
        "https://example.myshopify.com/admin/oauth/access_token"
    )
    assert session.posts[0]["data"] == {
        "grant_type": "client_credentials",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    assert session.posts[1]["headers"] == {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": "shpat_test",
    }


def test_config_requires_token_or_client_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", "example.myshopify.com")
    monkeypatch.delenv("SHOPIFY_ADMIN_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SHOPIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SHOPIFY_CLIENT_SECRET", raising=False)

    with pytest.raises(ValueError, match="SHOPIFY_ADMIN_ACCESS_TOKEN"):
        ShopifyConfig.from_env()
