from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.db.models import Post
from app.db.posts import create_post
from app.config import Settings, load_settings


PINTEREST_CREATE_PIN_URL = "https://api.pinterest.com/v5/pins"


@dataclass(frozen=True)
class PinterestPublishResult:
    pin_id: str
    raw_response: dict[str, Any]


class PinterestApiClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        if not self.settings.pinterest_access_token:
            raise ValueError("PINTEREST_ACCESS_TOKEN is required for Pinterest autoposting")
        if not self.settings.pinterest_board_id:
            raise ValueError("PINTEREST_BOARD_ID is required for Pinterest autoposting")

    def create_pin(
        self,
        *,
        image_url: str,
        title: str,
        description: str,
        link: str | None = None,
    ) -> PinterestPublishResult:
        payload: dict[str, Any] = {
            "board_id": self.settings.pinterest_board_id,
            "title": title,
            "description": description,
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }
        if link:
            payload["link"] = link

        response = _post_json(
            PINTEREST_CREATE_PIN_URL,
            payload,
            bearer_token=self.settings.pinterest_access_token or "",
        )
        pin_id = response.get("id")
        if not isinstance(pin_id, str) or not pin_id:
            raise RuntimeError("Pinterest create pin response did not include id")
        return PinterestPublishResult(pin_id=pin_id, raw_response=response)


def create_local_pinterest_post(
    conn: sqlite3.Connection,
    *,
    concept_id: str | None = None,
    outfit_id: str | None,
    image_path: str,
    title: str,
    description: str,
    hashtags: list[str],
    status: str = "draft",
    scheduled_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Post:
    return create_post(
        conn,
        platform="pinterest",
        concept_id=concept_id,
        outfit_id=outfit_id,
        image_path=image_path,
        caption=description,
        status=status,
        published_at=scheduled_at,
        metadata={
            "local_only": True,
            "api_posting_enabled": False,
            "title": title,
            "hashtags": hashtags,
            "scheduled_at": scheduled_at,
            **(metadata or {}),
        },
    )


def _post_json(url: str, payload: dict[str, Any], *, bearer_token: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "affiliate-outfits/0.1",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
