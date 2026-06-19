from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


JsonDict = dict[str, Any]
Platform = Literal["tiktok", "pinterest", "local"]
PostStatus = Literal["draft", "scheduled", "published", "failed"]
ConceptStatus = Literal["active", "needs_review", "retired"]


@dataclass(frozen=True)
class Concept:
    id: str
    seed: str
    status: ConceptStatus
    source: str
    usage_count: int
    ranking_score: float
    last_posted_date_est: str | None
    created_at: str
    updated_at: str
    metadata: JsonDict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.seed


@dataclass(frozen=True)
class Product:
    id: str
    retailer: str
    name: str
    url: str
    category: str | None
    affiliate_url: str | None
    image_url: str | None
    local_image_path: str | None
    price_cents: int | None
    currency: str
    created_at: str
    updated_at: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Outfit:
    id: str
    concept_id: str | None
    concept_seed: str
    spec: JsonDict
    product_ids: list[str]
    created_at: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Collage:
    id: str
    outfit_id: str
    image_path: str
    collage_url: str | None
    layout: JsonDict
    created_at: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Post:
    id: str
    platform: Platform
    status: PostStatus
    concept_id: str | None
    outfit_id: str | None
    image_path: str | None
    caption: str | None
    platform_post_id: str | None
    published_at: str | None
    created_at: str
    updated_at: str
    scheduled_for: str | None = None
    queue_order: str | None = None
    is_manual_schedule: bool = False
    approved: bool = True
    link_check: JsonDict | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Metric:
    id: str
    post_id: str
    platform: Platform
    collected_at: str
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    clicks: int
    score: float
    metadata: JsonDict = field(default_factory=dict)
