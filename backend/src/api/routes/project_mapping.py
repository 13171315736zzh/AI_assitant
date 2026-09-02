from fastapi import Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.project_mapping import ProjectMappingCreate, ProjectMappingUpdate
from src.models.user import UserPublic
from src.services.project_mapping import ProjectMappingService

router = APIRouter(prefix="/api/admin/project-mappings", tags=["admin-project-mapping"])


def _service(db: AsyncSession) -> ProjectMappingService:
    return ProjectMappingService(db)


@router.get("")
async def list_project_mappings(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await _service(db).list_mappings(keyword)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    return paginated([i.model_dump() for i in page_items], total, page, page_size)


@router.post("")
async def create_project_mapping(
    body: ProjectMappingCreate,
    admin: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await _service(db).create(body, admin.username)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=error(str(exc), code=400))
    return success(item.model_dump())


@router.put("/{mapping_id}")
async def update_project_mapping(
    mapping_id: str,
    body: ProjectMappingUpdate,
    admin: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await _service(db).update(mapping_id, body, admin.username)
    if item is None:
        return JSONResponse(status_code=404, content=error("映射不存在", code=404))
    return success(item.model_dump())


@router.delete("/{mapping_id}")
async def delete_project_mapping(
    mapping_id: str,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    deleted = await _service(db).delete(mapping_id)
    if not deleted:
        return JSONResponse(status_code=404, content=error("映射不存在", code=404))
    return success({"deleted": True})


@router.get("/template")
async def download_template(
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    content = _service(db).build_template_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="project_mapping_template.xlsx"'},
    )


@router.get("/export")
async def export_mappings(
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    content = await _service(db).export_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="project_mapping_export.xlsx"'},
    )


@router.post("/import")
async def import_mappings(
    file: UploadFile = File(...),
    replace: bool = Query(False),
    admin: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        return JSONResponse(
            status_code=400,
            content=error("请上传 .xlsx 格式的 Excel 文件", code=400),
        )
    content = await file.read()
    result = await _service(db).import_excel(content, admin.username, replace=replace)
    return success(result.model_dump())
