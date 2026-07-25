"""Customer Reviews REST API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import ProductReview, Product, User
from app.schemas import MessageOut
from app.security import CurrentUser

router = APIRouter(prefix='/reviews', tags=['Reviews'])


class ReviewCreate(BaseModel):
    product_id: int
    rating: int
    comment: Optional[str] = None


class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rating: int
    comment: Optional[str] = None
    created_at: Optional[str] = None
    product_id: int
    user_id: int
    product_name: Optional[str] = None


@router.get('/me', response_model=List[ReviewOut])
async def list_my_reviews(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductReview, Product)
        .join(Product, ProductReview.product_id == Product.id)
        .where(ProductReview.user_id == current_user.id)
        .order_by(ProductReview.created_at.desc())
    )
    reviews = []
    for row in result.all():
        r = row.ProductReview
        reviews.append(ReviewOut(
            id=r.id, rating=r.rating, comment=r.comment,
            created_at=str(r.created_at) if r.created_at else None,
            product_id=r.product_id, user_id=r.user_id,
            product_name=row.Product.name,
        ))
    return reviews


@router.post('', response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    product = (await db.execute(select(Product).where(Product.id == payload.product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail='Rating must be between 1 and 5')
    existing = (
        await db.execute(
            select(ProductReview).where(
                ProductReview.user_id == current_user.id,
                ProductReview.product_id == payload.product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail='You already reviewed this product')
    review = ProductReview(
        rating=payload.rating, comment=payload.comment,
        product_id=payload.product_id, user_id=current_user.id,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return ReviewOut(
        id=review.id, rating=review.rating, comment=review.comment,
        created_at=str(review.created_at) if review.created_at else None,
        product_id=review.product_id, user_id=review.user_id,
        product_name=product.name,
    )


@router.put('/{review_id}', response_model=ReviewOut)
async def update_review(
    review_id: int,
    payload: ReviewUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductReview).where(ProductReview.id == review_id, ProductReview.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail='Review not found')
    if payload.rating is not None:
        if payload.rating < 1 or payload.rating > 5:
            raise HTTPException(status_code=400, detail='Rating must be between 1 and 5')
        review.rating = payload.rating
    if payload.comment is not None:
        review.comment = payload.comment
    await db.commit()
    await db.refresh(review)
    product = (await db.execute(select(Product).where(Product.id == review.product_id))).scalar_one_or_none()
    return ReviewOut(
        id=review.id, rating=review.rating, comment=review.comment,
        created_at=str(review.created_at) if review.created_at else None,
        product_id=review.product_id, user_id=review.user_id,
        product_name=product.name if product else None,
    )


@router.delete('/{review_id}', response_model=MessageOut)
async def delete_review(
    review_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductReview).where(ProductReview.id == review_id, ProductReview.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail='Review not found')
    await db.delete(review)
    await db.commit()
    return MessageOut(detail='Review deleted')
