from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import DB, Admin, Page
from app.errors import ValidationError
from app.models import Building, Canteen, StudentGroup, UserRole
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserList,
    AdminUserOut,
    AdminUserUpdate,
    BuildingCreate,
    CanteenAdminOut,
    CanteenCreate,
    CanteenUpdate,
    GroupAdminOut,
    GroupCreate,
    ScheduleImportResult,
)
from app.schemas.reference import BuildingOut
from app.services import admin

router = APIRouter(prefix="/admin", tags=["admin"])

MAX_CSV_BYTES = 1_000_000


@router.get("/users", response_model=AdminUserList)
def list_users(
    _: Admin,
    db: DB,
    page: Page,
    q: str | None = None,
    role: UserRole | None = None,
    canteen_id: int | None = None,
) -> AdminUserList:
    limit, offset = page
    return admin.list_users(db, q=q, role=role, canteen_id=canteen_id, limit=limit, offset=offset)


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, _: Admin, db: DB) -> AdminUserOut:
    return admin.create_user(db, data)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: AdminUserUpdate, user: Admin, db: DB) -> AdminUserOut:
    return admin.update_user(db, user, user_id, data)


@router.get("/canteens", response_model=list[CanteenAdminOut])
def list_canteens(_: Admin, db: DB) -> list[Canteen]:
    return admin.list_canteens(db)


@router.post("/canteens", response_model=CanteenAdminOut, status_code=status.HTTP_201_CREATED)
def create_canteen(data: CanteenCreate, _: Admin, db: DB) -> Canteen:
    return admin.create_canteen(db, data)


@router.patch("/canteens/{canteen_id}", response_model=CanteenAdminOut)
def update_canteen(canteen_id: int, data: CanteenUpdate, _: Admin, db: DB) -> Canteen:
    return admin.update_canteen(db, canteen_id, data)


@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings(_: Admin, db: DB) -> list[Building]:
    return admin.list_buildings(db)


@router.post("/buildings", response_model=BuildingOut, status_code=status.HTTP_201_CREATED)
def create_building(data: BuildingCreate, _: Admin, db: DB) -> Building:
    return admin.create_building(db, data)


@router.get("/groups", response_model=list[GroupAdminOut])
def list_groups(_: Admin, db: DB) -> list[GroupAdminOut]:
    return [
        GroupAdminOut(
            id=g.id,
            code=g.code,
            faculty=g.faculty,
            study_year=g.study_year,
            students=students,
            lessons=lessons,
        )
        for g, students, lessons in admin.list_groups(db)
    ]


@router.post("/groups", response_model=GroupAdminOut, status_code=status.HTTP_201_CREATED)
def create_group(data: GroupCreate, _: Admin, db: DB) -> GroupAdminOut:
    g: StudentGroup = admin.create_group(db, data)
    return GroupAdminOut(
        id=g.id, code=g.code, faculty=g.faculty, study_year=g.study_year, students=0, lessons=0
    )


@router.post("/schedule/import", response_model=ScheduleImportResult)
def import_schedule(
    _: Admin, db: DB, file: Annotated[UploadFile, File()], dry_run: bool = False
) -> ScheduleImportResult:
    content = file.file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise ValidationError("file_too_large", "Файл больше 1 МБ")
    return admin.import_schedule(db, content, dry_run=dry_run)
