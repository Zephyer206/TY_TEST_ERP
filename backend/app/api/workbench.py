"""Personal and role work queues; identity always comes from server auth."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.schemas.workbench import DueFilter, TaskModule, TaskScope, WorkbenchPage
from app.services.workbench_service import build_page, load_tasks

router = APIRouter(prefix="/workbench", tags=["Workbench"])


@router.get("", response_model=WorkbenchPage)
async def get_workbench(
    db: DbSession, current_user: CurrentUser,
    scope: TaskScope = "mine", module: TaskModule | None = None,
    search: str = Query(default="", max_length=120), due: DueFilter = "all",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=15, ge=1, le=100),
) -> WorkbenchPage:
    return build_page(await load_tasks(db, current_user), current_user,
                      acceptance_mode=settings.AUTH_DISABLED, scope=scope, module=module,
                      search=search, due=due, page=page, page_size=page_size)
