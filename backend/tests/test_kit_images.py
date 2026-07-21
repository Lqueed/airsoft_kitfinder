"""API-тесты фото китов: загрузка, лимит, обложка, удаление, каскад.

S3 замокан (autouse-фикстура) — реальное хранилище не требуется.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Kit, KitImage
from app.models.enums import KitStatus
from app.services import storage


@pytest.fixture(autouse=True)
def _mock_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        storage, "upload_image", lambda data, ct: f"kit-images/{uuid.uuid4().hex}.jpg"
    )
    monkeypatch.setattr(storage, "delete_object", lambda key: None)
    monkeypatch.setattr(storage, "public_url", lambda key: f"https://cdn.test/{key}")


async def _kit(session: AsyncSession) -> int:
    kit = Kit(slug=f"imgkit-{uuid.uuid4().hex}", name="Фото-кит", status=KitStatus.DRAFT)
    session.add(kit)
    await session.flush()
    return kit.id


def _files(n: int, content_type: str = "image/jpeg") -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (f"p{i}.jpg", b"fake-bytes", content_type)) for i in range(n)]


async def test_images_require_auth(client: AsyncClient) -> None:
    assert (await client.post("/api/admin/kits/1/images", files=_files(1))).status_code == 401
    assert (await client.delete("/api/admin/kit-images/1")).status_code == 401
    assert (await client.post("/api/admin/kit-images/1/cover")).status_code == 401


async def test_upload_sets_first_as_cover(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    resp = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(2))
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["images"]) == 2
    covers = [img for img in body["images"] if img["is_cover"]]
    assert len(covers) == 1  # ровно одна обложка
    assert body["image_url"] == covers[0]["url"]  # обложка = image_url кита
    assert covers[0]["url"] == body["images"][0]["url"]  # первое фото


async def test_upload_limit(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    ok = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(10))
    assert ok.status_code == 201
    over = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(1))
    assert over.status_code == 409


async def test_upload_bad_type(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    resp = await admin_client.post(
        f"/api/admin/kits/{kid}/images", files=_files(1, content_type="text/plain")
    )
    assert resp.status_code == 400


async def test_set_cover(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    up = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(2))
    second = up.json()["images"][1]
    assert not second["is_cover"]

    resp = await admin_client.post(f"/api/admin/kit-images/{second['id']}/cover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["image_url"] == second["url"]
    now_cover = next(img for img in body["images"] if img["id"] == second["id"])
    assert now_cover["is_cover"]


async def test_delete_cover_reassigns(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    up = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(2))
    imgs = up.json()["images"]
    cover_id = next(img["id"] for img in imgs if img["is_cover"])
    other_url = next(img["url"] for img in imgs if img["id"] != cover_id)

    resp = await admin_client.delete(f"/api/admin/kit-images/{cover_id}")
    assert resp.status_code == 204

    kit = await session.get(Kit, kid)
    await session.refresh(kit)
    assert kit.image_url == other_url  # обложка переназначена на оставшееся фото


async def test_delete_last_image_clears_cover(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    kid = await _kit(session)
    up = await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(1))
    img_id = up.json()["images"][0]["id"]
    await admin_client.delete(f"/api/admin/kit-images/{img_id}")
    kit = await session.get(Kit, kid)
    await session.refresh(kit)
    assert kit.image_url is None  # фото не осталось — обложка сброшена


async def test_kit_delete_cascades_images(admin_client: AsyncClient, session: AsyncSession) -> None:
    kid = await _kit(session)
    await admin_client.post(f"/api/admin/kits/{kid}/images", files=_files(3))
    assert (
        await session.scalar(select(func.count(KitImage.id)).where(KitImage.kit_id == kid))
    ) == 3
    resp = await admin_client.delete(f"/api/admin/kits/{kid}")
    assert resp.status_code == 204
    assert (
        await session.scalar(select(func.count(KitImage.id)).where(KitImage.kit_id == kid))
    ) == 0  # каскадное удаление фото вместе с китом
