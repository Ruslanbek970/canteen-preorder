from datetime import datetime

from pydantic import BaseModel, Field


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewCreated(BaseModel):
    id: int
    order_item_id: int
    rating: int
    comment: str | None
    created_at: datetime
