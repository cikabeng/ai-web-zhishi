"""知识库接口测试：上传、去重、删除、重建索引、失败状态与检索联动。

每个用例用独立的临时目录 + 临时 Chroma 目录，互不污染。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.library.index import LibraryIndex
from app.library.store import LibraryStore

SAMPLE_MD = """# Python 闭包讲义

## 一、什么是闭包

闭包是指函数内部定义的函数，引用了外部函数的变量，并且外部函数返回了这个内部函数。

## 二、常见用途

闭包常用于保存状态，例如计数器。
"""


@pytest.fixture()
def store(tmp_path: Path) -> LibraryStore:
    return LibraryStore(root=tmp_path / "library", index=LibraryIndex(path=tmp_path / "chroma"))


@pytest.fixture()
def library_client(client: TestClient, store: LibraryStore, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.api.library.get_store", lambda: store)
    return client


def upload(client: TestClient, name: str = "closure.md", content: bytes = SAMPLE_MD.encode("utf-8")) -> dict:
    response = client.post(
        "/api/library/documents",
        files={"file": (name, content, "text/markdown")},
    )
    return response


def test_upload_and_index(library_client: TestClient) -> None:
    response = upload(library_client)
    assert response.status_code == 201

    payload = response.json()
    document = payload["document"]
    assert payload["duplicate"] is False
    assert document["status"] == "indexed"
    assert document["chunks"] > 0
    assert document["chars"] > 0
    assert document["error"] is None


def test_duplicate_upload_is_rejected(library_client: TestClient) -> None:
    first = upload(library_client).json()["document"]
    second = upload(library_client).json()

    assert second["duplicate"] is True
    assert second["document"]["id"] == first["id"]

    listing = library_client.get("/api/library/documents").json()
    assert len(listing["documents"]) == 1


def test_list_and_stats(library_client: TestClient) -> None:
    upload(library_client)
    listing = library_client.get("/api/library/documents").json()

    assert listing["stats"]["documents"] == 1
    assert listing["stats"]["indexed"] == 1
    assert listing["stats"]["status"] == "ready"
    assert listing["documents"][0]["name"] == "closure.md"


def test_retrieval_hits_uploaded_document(store: LibraryStore) -> None:
    record, _ = store.add_document("closure.md", SAMPLE_MD.encode("utf-8"))
    assert record["status"] == "indexed"

    hits = store.index.search("闭包是什么", top_k=3)
    assert hits, "上传的文档应当能被检索到"
    assert hits[0].doc_name == "closure.md"
    assert 0 <= hits[0].score <= 1


def test_delete_removes_vectors(library_client: TestClient, store: LibraryStore) -> None:
    document = upload(library_client).json()["document"]
    assert store.index.count() > 0

    assert library_client.delete(f"/api/library/documents/{document['id']}").status_code == 200
    assert store.index.count() == 0
    assert library_client.get("/api/library/documents").json()["documents"] == []

    assert library_client.delete(f"/api/library/documents/{document['id']}").status_code == 404


def test_reindex_restores_document(library_client: TestClient, store: LibraryStore) -> None:
    document = upload(library_client).json()["document"]
    assert library_client.delete(f"/api/library/documents/{document['id']}").status_code == 200

    # 直接重新入库（模拟重新上传相同内容后再重建）
    again = upload(library_client).json()
    assert again["document"]["id"] == document["id"]

    reindexed = library_client.post(f"/api/library/documents/{document['id']}/reindex")
    assert reindexed.status_code == 200
    assert reindexed.json()["document"]["status"] == "indexed"


def test_unsupported_format(library_client: TestClient) -> None:
    response = upload(library_client, "demo.exe", b"MZ\x00\x00")
    assert response.status_code == 415
    assert "格式" in response.json()["message"]


def test_empty_file(library_client: TestClient) -> None:
    response = upload(library_client, "empty.txt", b"")
    assert response.status_code == 400


def test_parse_failure_is_reported(library_client: TestClient) -> None:
    response = upload(library_client, "blank.txt", b"\n\n\n   \n")
    assert response.status_code == 201

    document = response.json()["document"]
    assert document["status"] == "failed"
    assert document["error"]


def test_chunk_preview(library_client: TestClient) -> None:
    document = upload(library_client).json()["document"]
    response = library_client.get(f"/api/library/documents/{document['id']}/chunks?limit=3")
    assert response.status_code == 200

    payload = response.json()
    assert payload["chunks"]
    assert payload["chunks"][0]["text"]


def test_health_reflects_library(store: LibraryStore, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    store.add_document("closure.md", SAMPLE_MD.encode("utf-8"))
    monkeypatch.setattr("app.api.health.get_store", lambda: store)

    data = client.get("/api/health").json()
    assert data["knowledge_base"]["status"] == "ready"
    assert data["knowledge_base"]["documents"] == 1
    assert data["knowledge_base"]["chunks"] > 0
