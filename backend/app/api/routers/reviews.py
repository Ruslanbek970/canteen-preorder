from fastapi import APIRouter, status

from app.api.deps import DB, Customer
from app.schemas.reviews import ReviewCreated, ReviewIn
from app.services import reviews

router = APIRouter(tags=["reviews"])


@router.post(
    "/order-items/{item_id}/review",
    response_model=ReviewCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_review(item_id: int, data: ReviewIn, user: Customer, db: DB) -> ReviewCreated:
    return reviews.create_review(db, user, item_id, data)
