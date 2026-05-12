"""Free stock media collection for Film Engine bootstrap assets."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, replace
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.studio import Chapter, FileItem, FileType, Project
from app.models.types import FileUsageKind
from app.services.studio.file_usages import upsert_file_usage

COMMONS_API_BASE = "https://api.wikimedia.org/core/v1/commons"
COMMONS_SEARCH_URL = f"{COMMONS_API_BASE}/search/page"
COMMONS_USER_AGENT = "CineForge/0.1 (local Film Engine asset bootstrap)"

_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class StockMediaItem:
    """Provider-neutral stock media record used by API, UI, and tests."""

    id: str
    media_type: str
    title: str
    provider: str
    source_url: str
    thumbnail_url: str
    license_page_url: str
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    description: str = ""
    file_id: str | None = None
    tags: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the media item for FastAPI responses."""
        payload = asdict(self)
        payload["tags"] = list(self.tags or [])
        return payload


class CommonsStockMediaClient:
    """Small Wikimedia Commons Core REST client with deterministic fallback."""

    async def collect(self, *, query: str, image_count: int, video_count: int) -> list[StockMediaItem]:
        """Collect image and video candidates without requiring API keys."""
        requested = max(0, image_count) + max(0, video_count)
        if requested == 0:
            return []

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=5.0),
                headers={"User-Agent": COMMONS_USER_AGENT},
                follow_redirects=True,
                # Stock bootstrap must run in dev machines without requiring optional httpx[socks].
                trust_env=False,
            ) as client:
                images = await self._search_media(
                    client,
                    query=query,
                    media_type="image",
                    limit=image_count,
                )
                videos = await self._search_media(
                    client,
                    query=query,
                    media_type="video",
                    limit=video_count,
                )
        except Exception:
            return _fallback_items(image_count=image_count, video_count=video_count)

        items = _dedupe_items([*images, *videos])
        if len(items) < requested:
            existing = {item.source_url for item in items}
            for item in _fallback_items(image_count=image_count, video_count=video_count):
                if item.source_url not in existing:
                    items.append(item)
                    existing.add(item.source_url)
                if len(items) >= requested:
                    break
        return items[:requested]

    async def _search_media(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        media_type: str,
        limit: int,
    ) -> list[StockMediaItem]:
        """Search page titles first, then hydrate each result with file URLs."""
        if limit <= 0:
            return []
        filetype = "bitmap" if media_type == "image" else "video"
        response = await client.get(
            COMMONS_SEARCH_URL,
            params={"q": f"{query} filetype:{filetype}", "limit": min(max(limit * 2, limit), 20)},
        )
        response.raise_for_status()
        pages = response.json().get("pages") or []

        items: list[StockMediaItem] = []
        for page in pages:
            if len(items) >= limit:
                break
            title = str(page.get("key") or page.get("title") or "").strip()
            if not title.startswith("File:"):
                continue
            hydrated = await self._hydrate_file(client, title=title, media_type=media_type, page=page)
            if hydrated is not None:
                items.append(hydrated)
        return items

    async def _hydrate_file(
        self,
        client: httpx.AsyncClient,
        *,
        title: str,
        media_type: str,
        page: dict[str, Any],
    ) -> StockMediaItem | None:
        """Fetch original/preferred URLs and normalize Commons metadata."""
        response = await client.get(f"{COMMONS_API_BASE}/file/{quote(title, safe='')}")
        response.raise_for_status()
        data = response.json()
        original = data.get("original") or {}
        preferred = data.get("preferred") or data.get("thumbnail") or {}
        source_url = str(original.get("url") or preferred.get("url") or "").strip()
        thumbnail_url = str(preferred.get("url") or source_url).strip()
        if not source_url:
            return None

        mediatype = str(original.get("mediatype") or preferred.get("mediatype") or "").upper()
        if media_type == "image" and mediatype not in {"BITMAP", "DRAWING", ""}:
            return None
        if media_type == "video" and mediatype not in {"VIDEO", "MULTIMEDIA", ""}:
            return None

        license_page_url = _absolute_commons_url(str(data.get("file_description_url") or ""))
        clean_title = str(data.get("title") or title.replace("File:", "")).replace("_", " ").strip()
        return StockMediaItem(
            id=_stable_item_id(source_url),
            media_type=media_type,
            title=_truncate(clean_title, 180),
            provider="wikimedia_commons",
            source_url=source_url,
            thumbnail_url=thumbnail_url,
            license_page_url=license_page_url,
            width=_optional_int(original.get("width") or preferred.get("width")),
            height=_optional_int(original.get("height") or preferred.get("height")),
            duration=_optional_int(original.get("duration") or preferred.get("duration")),
            description=_truncate(_clean_excerpt(str(page.get("excerpt") or "")), 280),
            tags=["stock", "wikimedia_commons", media_type],
        )


async def collect_stock_assets(
    db: AsyncSession,
    *,
    project_id: str | None,
    chapter_id: str | None,
    query: str | None,
    image_count: int,
    video_count: int,
    persist: bool,
    client: CommonsStockMediaClient | None = None,
) -> dict[str, Any]:
    """Collect stock media and optionally persist it as Jellyfish FileItem rows."""
    effective_query = await _resolve_query(db, project_id=project_id, chapter_id=chapter_id, query=query)
    provider = client or CommonsStockMediaClient()
    collected = await provider.collect(
        query=effective_query,
        image_count=max(0, image_count),
        video_count=max(0, video_count),
    )

    persisted_items: list[StockMediaItem] = []
    created_file_count = 0
    if persist and project_id:
        await _ensure_project_scope(db, project_id=project_id, chapter_id=chapter_id)
        for item in collected:
            persisted, created = await _upsert_stock_file(
                db,
                item=item,
                project_id=project_id,
                chapter_id=chapter_id,
            )
            persisted_items.append(persisted)
            created_file_count += 1 if created else 0
    else:
        persisted_items = [replace(item, file_id=_file_id_for_item(item)) for item in collected]

    return {
        "query": effective_query,
        "provider": "wikimedia_commons",
        "persisted": bool(persist and project_id),
        "created_file_count": created_file_count,
        "item_count": len(persisted_items),
        "items": [item.as_dict() for item in persisted_items],
        "sources": [
            {
                "name": "Wikimedia Commons",
                "api": COMMONS_SEARCH_URL,
                "license_note": "Use each item license_page_url for attribution and license review.",
            }
        ],
    }


async def _resolve_query(
    db: AsyncSession,
    *,
    project_id: str | None,
    chapter_id: str | None,
    query: str | None,
) -> str:
    """Derive a useful stock search query from project/chapter context."""
    cleaned_query = _clean_query(query)
    if cleaned_query:
        return cleaned_query

    parts: list[str] = []
    if chapter_id:
        chapter = await db.get(Chapter, chapter_id)
        if chapter is not None:
            parts.extend([chapter.title, chapter.condensed_text, chapter.raw_text])
    if project_id:
        project = await db.get(Project, project_id)
        if project is not None:
            parts.extend([project.name, project.description, str(project.style)])

    derived = _clean_query(" ".join(part for part in parts if part))
    return derived or "cinematic drama city night"


async def _ensure_project_scope(
    db: AsyncSession,
    *,
    project_id: str,
    chapter_id: str | None,
) -> None:
    """Validate the optional project/chapter persistence scope."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if chapter_id:
        chapter = await db.get(Chapter, chapter_id)
        if chapter is None or chapter.project_id != project_id:
            raise HTTPException(status_code=404, detail="Chapter not found in project")


async def _upsert_stock_file(
    db: AsyncSession,
    *,
    item: StockMediaItem,
    project_id: str,
    chapter_id: str | None,
) -> tuple[StockMediaItem, bool]:
    """Persist a remote stock reference without requiring object storage."""
    file_id = _file_id_for_item(item)
    file_type = FileType.image if item.media_type == "image" else FileType.video
    existing = await db.get(FileItem, file_id)
    created = existing is None
    tags = [*_dedupe_texts([*(item.tags or []), "film_engine_bootstrap", item.provider])]
    if existing is None:
        existing = FileItem(
            id=file_id,
            type=file_type,
            name=_truncate(item.title, 255),
            thumbnail=_truncate(item.thumbnail_url, 1024),
            tags=tags,
            storage_key=_truncate(item.source_url, 1024),
        )
        db.add(existing)
    else:
        existing.type = file_type
        existing.name = _truncate(item.title, 255)
        existing.thumbnail = _truncate(item.thumbnail_url, 1024)
        existing.tags = tags
        existing.storage_key = _truncate(item.source_url, 1024)
    await db.flush()
    await upsert_file_usage(
        db,
        file_id=file_id,
        project_id=project_id,
        chapter_id=chapter_id,
        shot_id=None,
        usage_kind=FileUsageKind.api,
        source_ref=_truncate(f"stock:{item.provider}:{item.id}", 128),
    )
    await db.flush()
    return replace(item, file_id=file_id, tags=tags), created


def _fallback_items(*, image_count: int, video_count: int) -> list[StockMediaItem]:
    """Return stable Commons references when network search is unavailable."""
    images = [
        StockMediaItem(
            id="commons_man_beside_neon_sign",
            media_type="image",
            title="Man beside neon sign",
            provider="wikimedia_commons_fallback",
            source_url="https://upload.wikimedia.org/wikipedia/commons/f/ff/Man_beside_neon_sign.jpg",
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/Man_beside_neon_sign.jpg/960px-Man_beside_neon_sign.jpg",
            license_page_url="https://commons.wikimedia.org/wiki/File:Man_beside_neon_sign.jpg",
            width=1054,
            height=728,
            description="Fallback image for neon street drama reference gathering.",
            tags=["stock", "wikimedia_commons", "image", "fallback"],
        ),
        StockMediaItem(
            id="commons_fronalpstock_big",
            media_type="image",
            title="Fronalpstock landscape reference",
            provider="wikimedia_commons_fallback",
            source_url="https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg",
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Fronalpstock_big.jpg/960px-Fronalpstock_big.jpg",
            license_page_url="https://commons.wikimedia.org/wiki/File:Fronalpstock_big.jpg",
            width=10109,
            height=4542,
            description="Fallback image for wide establishing scene references.",
            tags=["stock", "wikimedia_commons", "image", "fallback"],
        ),
    ]
    videos = [
        StockMediaItem(
            id="commons_roundhay_garden_scene",
            media_type="video",
            title="Roundhay Garden Scene",
            provider="wikimedia_commons_fallback",
            source_url="https://upload.wikimedia.org/wikipedia/commons/e/e6/Roundhay_Garden_Scene.ogv",
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Roundhay_Garden_Scene.ogv/330px--Roundhay_Garden_Scene.ogv.jpg",
            license_page_url="https://commons.wikimedia.org/wiki/File:Roundhay_Garden_Scene.ogv",
            description="Fallback video for motion-reference bootstrap.",
            tags=["stock", "wikimedia_commons", "video", "fallback"],
        ),
        StockMediaItem(
            id="commons_ocean_city_night_lights",
            media_type="video",
            title="Ocean Moon Glint and City Night Lights in 4K",
            provider="wikimedia_commons_fallback",
            source_url="https://upload.wikimedia.org/wikipedia/commons/b/b9/Ocean_Moon_Glint_and_City_Night_Lights_in_4K.webm",
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Ocean_Moon_Glint_and_City_Night_Lights_in_4K.webm/960px--Ocean_Moon_Glint_and_City_Night_Lights_in_4K.webm.jpg",
            license_page_url="https://commons.wikimedia.org/wiki/File:Ocean_Moon_Glint_and_City_Night_Lights_in_4K.webm",
            description="Fallback video for cinematic night-light references.",
            tags=["stock", "wikimedia_commons", "video", "fallback"],
        ),
    ]
    return [*images[: max(0, image_count)], *videos[: max(0, video_count)]]


def _stable_item_id(value: str) -> str:
    """Build a stable provider item ID from the canonical media URL."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:24]


def _file_id_for_item(item: StockMediaItem) -> str:
    """Build an idempotent Jellyfish FileItem ID for a stock media item."""
    return f"stock_{_stable_item_id(item.source_url)}"


def _dedupe_items(items: list[StockMediaItem]) -> list[StockMediaItem]:
    """Keep result order while removing duplicate URLs."""
    seen: set[str] = set()
    result: list[StockMediaItem] = []
    for item in items:
        key = item.source_url
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_texts(values: list[str]) -> list[str]:
    """Keep short tag lists stable and unique."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_query(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _clean_query(value: str | None) -> str:
    """Normalize user/project text for safe stock search."""
    text = _SPACES_RE.sub(" ", str(value or "").strip())
    return _truncate(text, 180)


def _clean_excerpt(value: str) -> str:
    """Remove HTML highlights from Commons search excerpts."""
    return _SPACES_RE.sub(" ", _TAG_RE.sub("", value)).strip()


def _absolute_commons_url(value: str) -> str:
    """Convert protocol-relative Commons URLs to absolute URLs."""
    if value.startswith("//"):
        return f"https:{value}"
    return value or "https://commons.wikimedia.org/"


def _optional_int(value: Any) -> int | None:
    """Convert provider number fields while tolerating null/unknown values."""
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _truncate(value: str, limit: int) -> str:
    """Bound values before writing them into fixed-width DB columns."""
    return value if len(value) <= limit else value[:limit]
