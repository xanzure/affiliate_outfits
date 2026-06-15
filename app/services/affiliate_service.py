from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DEFAULT_TRACKING_ID = "local-dev"


@dataclass(frozen=True)
class AffiliateLink:
    original_url: str
    affiliate_url: str
    network: str
    tracking_id: str


class AffiliateResolver(Protocol):
    def resolve(
        self,
        url: str,
        *,
        retailer: str,
        tracking_id: str = DEFAULT_TRACKING_ID,
    ) -> AffiliateLink:
        ...


class NoAffiliateResolver:
    def resolve(
        self,
        url: str,
        *,
        retailer: str,
        tracking_id: str = DEFAULT_TRACKING_ID,
    ) -> AffiliateLink:
        return AffiliateLink(
            original_url=url,
            affiliate_url="",
            network="none",
            tracking_id=tracking_id,
        )


def build_affiliate_link(
    url: str,
    *,
    network: str = "local",
    tracking_id: str = DEFAULT_TRACKING_ID,
) -> AffiliateLink:
    """Create a deterministic placeholder affiliate URL.

    Real affiliate network APIs will replace this later. For now, keeping the
    shape stable lets the product pipeline work without outside services.
    """

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["aff_network"] = network
    query["aff_id"] = tracking_id
    affiliate_url = urlunparse(parsed._replace(query=urlencode(query)))

    return AffiliateLink(
        original_url=url,
        affiliate_url=affiliate_url,
        network=network,
        tracking_id=tracking_id,
    )


def affiliate_resolver_from_name(name: str) -> AffiliateResolver:
    if name == "none":
        return NoAffiliateResolver()
    if name == "local":
        return LocalTrackingResolver()
    raise ValueError(f"unsupported AFFILIATE_PROVIDER: {name}")


class LocalTrackingResolver:
    def resolve(
        self,
        url: str,
        *,
        retailer: str,
        tracking_id: str = DEFAULT_TRACKING_ID,
    ) -> AffiliateLink:
        return build_affiliate_link(url, network="local", tracking_id=tracking_id)
