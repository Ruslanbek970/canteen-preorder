from fastapi import APIRouter, status

from app.api.deps import DB
from app.notifications import push
from app.schemas.me import AllergensPut, MeResponse, MeUpdate, MyAllergensResponse
from app.schemas.notifications import PushSubscriptionIn, PushUnsubscribe, TelegramLinkCode
from app.security import CurrentUser
from app.services import telegram
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


@router.post("/telegram/link-code", response_model=TelegramLinkCode)
def telegram_link_code(user: CurrentUser) -> TelegramLinkCode:
    return telegram.create_link_code(user)


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
def telegram_unlink(user: CurrentUser, db: DB) -> None:
    telegram.unlink_user(db, user)


@router.post("/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def push_subscribe(data: PushSubscriptionIn, user: CurrentUser, db: DB) -> None:
    push.save_subscription(db, user, data)


@router.delete("/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def push_unsubscribe(data: PushUnsubscribe, user: CurrentUser, db: DB) -> None:
    push.delete_subscription(db, user, data.endpoint)
