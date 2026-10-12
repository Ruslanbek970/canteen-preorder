from fastapi import APIRouter

from app.api.deps import DB
from app.schemas.me import AllergensPut, MeResponse, MeUpdate, MyAllergensResponse
from app.security import CurrentUser
from app.services import users as users_service

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=MeResponse)
def get_me(user: CurrentUser, db: DB) -> MeResponse:
    return users_service.profile(db, user)


@router.patch("", response_model=MeResponse)
def patch_me(data: MeUpdate, user: CurrentUser, db: DB) -> MeResponse:
    users_service.update_profile(db, user, data)
    return users_service.profile(db, user)


@router.get("/allergens", response_model=MyAllergensResponse)
def get_allergens(user: CurrentUser, db: DB) -> MyAllergensResponse:
    return users_service.my_allergens(db, user)


@router.put("/allergens", response_model=MyAllergensResponse)
def put_allergens(data: AllergensPut, user: CurrentUser, db: DB) -> MyAllergensResponse:
    return users_service.set_allergens(db, user, data)


@router.delete("/health-consent", response_model=MyAllergensResponse)
def delete_consent(user: CurrentUser, db: DB) -> MyAllergensResponse:
    return users_service.revoke_consent(db, user)
