"""知识库管理接口：上传、列表、删除、重建索引、分块预览与统计。"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.library.store import LibraryError, get_store

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/stats", summary="知识库统计")
def library_stats() -> dict:
    return get_store().stats()


@router.get("/documents", summary="文档列表")
def list_documents() -> dict:
    store = get_store()
    return {"documents": store.list_documents(), "stats": store.stats()}


@router.post("/documents", status_code=201, summary="上传并解析文档")
async def upload_document(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        document, duplicate = get_store().add_document(file.filename or "未命名", raw)
    except LibraryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return {"document": document, "duplicate": duplicate}


@router.delete("/documents/{doc_id}", summary="删除文档及其向量")
def delete_document(doc_id: str) -> dict:
    try:
        get_store().delete(doc_id)
    except LibraryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return {"deleted": True, "id": doc_id}


@router.post("/documents/{doc_id}/reindex", summary="重新解析并重建索引")
def reindex_document(doc_id: str) -> dict:
    try:
        document = get_store().reindex(doc_id)
    except LibraryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return {"document": document}


@router.get("/documents/{doc_id}/chunks", summary="分块预览")
def preview_chunks(doc_id: str, limit: int = 5) -> dict:
    store = get_store()
    document = store.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = store.index.get_chunks(doc_id, limit=max(1, min(limit, 20)))
    return {"document": document, "chunks": chunks}
