"""Administration (SPEC 8.9, 9.5): users and roles, canteens, buildings, groups, timetable."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import time

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Building,
    Canteen,
    ClassSchedule,
    RefreshToken,
    StudentGroup,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserList,
    AdminUserOut,
    AdminUserUpdate,
    BuildingCreate,
    CanteenCreate,
    CanteenUpdate,
    GroupCreate,
    ScheduleImportResult,
    ScheduleRowError,
)
from app.security import hash_password
from app.utils import time as clock

STAFF = (UserRole.cook, UserRole.cashier, UserRole.canteen_manager)
MAX_IMPORT_ROWS = 5000
COLUMNS = ["group_code", "day_of_week", "starts_at", "ends_at", "building", "subject"]


# ---- users ---------------------------------------------------------------------------------


def user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        group_id=user.group_id,
        group_code=user.group.code if user.group else None,
        canteen_id=user.canteen_id,
        canteen_name=user.canteen.name if user.canteen else None,
        is_active=user.is_active,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


def list_users(
    db: Session,
    *,
    q: str | None,
    role: UserRole | None,
    canteen_id: int | None,
    limit: int,
    offset: int,
) -> AdminUserList:
    conditions = []
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    if role is not None:
        conditions.append(User.role == role)
    if canteen_id is not None:
        conditions.append(User.canteen_id == canteen_id)
    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    users = db.scalars(
        select(User)
        .options(joinedload(User.group), joinedload(User.canteen))
        .where(*conditions)
        .order_by(User.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AdminUserList(items=[user_out(u) for u in users], total=total)


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("user", "Пользователь не найден")
    return user


def _check_links(db: Session, role: UserRole, canteen_id: int | None, group_id: int | None):
    """Staff work in a canteen, a student belongs to a group (the same rules as the DB)."""
    if role in STAFF and canteen_id is None:
        raise ValidationError("canteen_required", "Для сотрудника выберите столовую")
    if role == UserRole.student and group_id is None:
        raise ValidationError("group_required", "Для студента выберите группу")
    if canteen_id is not None and db.get(Canteen, canteen_id) is None:
        raise NotFoundError("canteen", "Столовая не найдена")
    if group_id is not None and db.get(StudentGroup, group_id) is None:
        raise NotFoundError("group", "Группа не найдена")


def _commit_unique(db: Session, code: str, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(code, message) from exc


def create_user(db: Session, data: AdminUserCreate) -> AdminUserOut:
    """Staff accounts are created here (SPEC 7.1); their e-mail counts as verified."""
    canteen_id = data.canteen_id if data.role in STAFF else None
    group_id = data.group_id if data.role == UserRole.student else None
    _check_links(db, data.role, canteen_id, group_id)
    user = User(
        full_name=data.full_name.strip(),
        email=data.email.lower(),
        phone=data.phone or None,
        password_hash=hash_password(data.password),
        role=data.role,
        canteen_id=canteen_id,
        group_id=group_id,
        email_verified_at=clock.now_utc(),
    )
    db.add(user)
    _commit_unique(db, "email_taken", "Пользователь с такой почтой или телефоном уже есть")
    return user_out(_get_user(db, user.id))


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> AdminUserOut:
    user = _get_user(db, user_id)
    fields = data.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        fields.get("is_active") is False or fields.get("role", UserRole.admin) != UserRole.admin
    ):
        raise ConflictError(
            "self_lockout", "Нельзя заблокировать себя или снять с себя роль админа"
        )
    role = fields.get("role", user.role)
    canteen_id = fields.get("canteen_id", user.canteen_id)
    group_id = fields.get("group_id", user.group_id)
    if role not in STAFF:
        canteen_id = None
    if role != UserRole.student:
        group_id = None
    _check_links(db, role, canteen_id, group_id)
    if "full_name" in fields and fields["full_name"] is not None:
        user.full_name = fields["full_name"].strip()
    if "phone" in fields:
        user.phone = fields["phone"] or None
    if fields.get("password"):
        user.password_hash = hash_password(fields["password"])
    user.role, user.canteen_id, user.group_id = role, canteen_id, group_id
    if "is_active" in fields and fields["is_active"] is not None:
        user.is_active = fields["is_active"]
    if not user.is_active or fields.get("password") or "role" in fields:
        # Blocked, new password or new role: sign them out everywhere.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=clock.now_utc())
        )
    _commit_unique(db, "phone_taken", "Такой телефон уже у другого пользователя")
    return user_out(_get_user(db, user.id))


# ---- canteens, buildings, groups -----------------------------------------------------------


def list_canteens(db: Session) -> list[Canteen]:
    return list(db.scalars(select(Canteen).order_by(Canteen.id)))


def _check_canteen(db: Session, canteen: Canteen) -> None:
    if db.get(Building, canteen.building_id) is None:
        raise NotFoundError("building", "Корпус не найден")
    if canteen.opens_at >= canteen.closes_at:
        raise ValidationError(
            "invalid_hours", "Столовая должна открываться раньше, чем закрываться"
        )


def create_canteen(db: Session, data: CanteenCreate) -> Canteen:
    canteen = Canteen(**data.model_dump(exclude_none=True))
    _check_canteen(db, canteen)
    db.add(canteen)
    _commit_unique(db, "slug_taken", "Такой адрес столовой уже занят")
    return canteen


def update_canteen(db: Session, canteen_id: int, data: CanteenUpdate) -> Canteen:
    canteen = db.get(Canteen, canteen_id)
    if canteen is None:
        raise NotFoundError("canteen", "Столовая не найдена")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key != "slug":
            continue
        setattr(canteen, key, value)
    _check_canteen(db, canteen)
    _commit_unique(db, "slug_taken", "Такой адрес столовой уже занят")
    return canteen


def list_buildings(db: Session) -> list[Building]:
    return list(db.scalars(select(Building).order_by(Building.name)))


def create_building(db: Session, data: BuildingCreate) -> Building:
    building = Building(name=data.name.strip(), address=data.address or None)
    db.add(building)
    _commit_unique(db, "building_exists", "Корпус с таким названием уже есть")
    return building


def list_groups(db: Session) -> list[tuple[StudentGroup, int, int]]:
    """Groups with the number of students and of lessons in the timetable."""
    students = select(func.count(User.id)).where(User.group_id == StudentGroup.id).scalar_subquery()
    lessons = (
        select(func.count(ClassSchedule.id))
        .where(ClassSchedule.group_id == StudentGroup.id)
        .scalar_subquery()
    )
    return [
        (g, s, n)
        for g, s, n in db.execute(
            select(StudentGroup, students, lessons).order_by(StudentGroup.code)
        ).all()
    ]


def create_group(db: Session, data: GroupCreate) -> StudentGroup:
    group = StudentGroup(
        code=data.code.strip().upper(), faculty=data.faculty or None, study_year=data.study_year
    )
    db.add(group)
    _commit_unique(db, "group_exists", "Группа с таким кодом уже есть")
    return group


# ---- timetable import ----------------------------------------------------------------------


@dataclass
class Lesson:
    group_id: int
    day_of_week: int
    starts_at: time
    ends_at: time
    building_id: int
    subject: str | None


TIME = re.compile(r"^\d{1,2}:\d{2}$")


def _parse_time(value: str) -> time | None:
    value = value.strip()
    if not TIME.match(value):
        return None
    try:
        return time.fromisoformat(value.zfill(5))
    except ValueError:
        return None


def _reader(text: str) -> csv.reader:
    first = text.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    return csv.reader(io.StringIO(text), delimiter=delimiter)


def import_schedule(db: Session, content: bytes, *, dry_run: bool) -> ScheduleImportResult:
    """CSV `group_code,day_of_week,starts_at,ends_at,building,subject`.

    The timetable of every group in the file is replaced by the file's lessons. Any error
    and nothing is written: the admin fixes the file and tries again.
    """
    errors: list[ScheduleRowError] = []

    def error(line: int, code: str, message: str) -> None:
        errors.append(ScheduleRowError(line=line, code=code, message=message))

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        error(0, "encoding", "Файл должен быть в кодировке UTF-8")
        return ScheduleImportResult(
            rows=0, groups=[], errors=errors, imported=False, deleted=0, created=0
        )
    groups = {g.code.upper(): g.id for g in db.scalars(select(StudentGroup))}
    buildings = {b.name.strip().lower(): b.id for b in db.scalars(select(Building))}
    lessons: list[Lesson] = []
    seen: dict[tuple[int, int, time], int] = {}
    rows = 0
    for line, row in enumerate(_reader(text), start=1):
        if not row or not "".join(row).strip():
            continue
        cells = [c.strip() for c in row]
        if line == 1 and cells[0].lower() == "group_code":
            continue  # header
        rows += 1
        if rows > MAX_IMPORT_ROWS:
            error(line, "too_many_rows", f"Не больше {MAX_IMPORT_ROWS} строк за раз")
            break
        if len(cells) < 5:
            error(line, "columns", "Нужно 5–6 колонок: " + ",".join(COLUMNS))
            continue
        code, day, start, end, building = cells[:5]
        subject = cells[5] if len(cells) > 5 and cells[5] else None
        group_id = groups.get(code.upper())
        if group_id is None:
            error(line, "unknown_group", f"Группа «{code}» не найдена")
        building_id = buildings.get(building.lower())
        if building_id is None:
            error(line, "unknown_building", f"Корпус «{building}» не найден")
        if not day.isdigit() or not 1 <= int(day) <= 7:
            error(line, "day_of_week", "День недели — число от 1 (пн) до 7 (вс)")
            continue
        starts_at, ends_at = _parse_time(start), _parse_time(end)
        if starts_at is None or ends_at is None:
            error(line, "time", "Время в формате ЧЧ:ММ, например 09:00")
            continue
        if starts_at >= ends_at:
            error(line, "time_order", "Пара должна заканчиваться позже, чем начинается")
            continue
        if subject and len(subject) > 150:
            error(line, "subject", "Название предмета не длиннее 150 символов")
            continue
        if group_id is None or building_id is None:
            continue
        key = (group_id, int(day), starts_at)
        if key in seen:
            error(line, "duplicate", f"Повтор строки {seen[key]}: та же группа, день и начало")
            continue
        seen[key] = line
        lessons.append(Lesson(group_id, int(day), starts_at, ends_at, building_id, subject))
    if rows == 0 and not errors:
        error(0, "empty", "В файле нет строк расписания")

    group_ids = sorted({lesson.group_id for lesson in lessons})
    codes = sorted(code for code, gid in groups.items() if gid in group_ids)
    deleted = (
        db.scalar(select(func.count(ClassSchedule.id)).where(ClassSchedule.group_id.in_(group_ids)))
        or 0
    )
    result = ScheduleImportResult(
        rows=rows,
        groups=codes,
        errors=errors,
        imported=False,
        deleted=deleted,
        created=len(lessons),
    )
    if errors or dry_run:
        return result
    db.execute(delete(ClassSchedule).where(ClassSchedule.group_id.in_(group_ids)))
    db.add_all(
        ClassSchedule(
            group_id=lesson.group_id,
            day_of_week=lesson.day_of_week,
            starts_at=lesson.starts_at,
            ends_at=lesson.ends_at,
            building_id=lesson.building_id,
            subject=lesson.subject,
        )
        for lesson in lessons
    )
    db.commit()
    result.imported = True
    return result
