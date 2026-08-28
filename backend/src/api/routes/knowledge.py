from fastapi import Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin, get_current_user
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.knowledge import SearchTestRequest
from src.models.user import UserPublic
from src.repositories.knowledge import KnowledgeRepository
from src.services.knowledge import KnowledgeService, RagService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _service(db: AsyncSession) -> KnowledgeService:
    return KnowledgeService(KnowledgeRepository(db))


@router.get("/qa")
async def list_qa(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await _service(db).list_public_qa(keyword, page, page_size)
    return paginated([item.model_dump() for item in items], total, page, page_size)


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await _service(db).list_public_documents(page, page_size)
    return paginated([item.model_dump() for item in items], total, page, page_size)


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await _service(db).get_document_file(document_id)
    if result is None:
        return JSONResponse(status_code=404, content=error("文档不存在", code=404))
    file_path, filename, media_type = result
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _service(db).search(q)
    return success(data.model_dump())


admin_router = APIRouter(prefix="/api/admin", tags=["admin-knowledge"])


@admin_router.get("/documents")
async def admin_list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await _service(db).list_admin_documents(page, page_size)
    return paginated([item.model_dump() for item in items], total, page, page_size)


@admin_router.post("/documents")
async def admin_upload_document(
    file: UploadFile = File(...),
    admin: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        return JSONResponse(status_code=400, content=error("文件名无效", code=400))
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse(status_code=400, content=error("文件大小不能超过 50MB", code=400))
    try:
        data = await _service(db).upload_document(file.filename, content, admin.username)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=error(str(exc), code=400))
    return success(data.model_dump())


@admin_router.get("/documents/{document_id}/progress")
async def admin_document_progress(
    document_id: str,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await _service(db).get_progress(document_id)
    if data is None:
        return JSONResponse(status_code=404, content=error("文档不存在", code=404))
    return success(data.model_dump())


@admin_router.delete("/documents/{document_id}")
async def admin_delete_document(
    document_id: str,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await _service(db).delete_document(document_id)
    if data is None:
        return JSONResponse(status_code=404, content=error("文档不存在", code=404))
    return success(data.model_dump())


@admin_router.post("/documents/{document_id}/reindex")
async def admin_reindex_document(
    document_id: str,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await _service(db).reindex_document(document_id)
    if data is None:
        return JSONResponse(status_code=404, content=error("文档不存在", code=404))
    return success(data.model_dump())


@admin_router.get("/qa")
async def admin_list_qa(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await _service(db).list_admin_qa(keyword, page, page_size)
    return paginated([item.model_dump() for item in items], total, page, page_size)


@admin_router.post("/search-test")
async def admin_search_test(
    body: SearchTestRequest,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await RagService(KnowledgeRepository(db)).search_test(body.query)
    return success(data.model_dump())
