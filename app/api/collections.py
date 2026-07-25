"""Collection REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Collection, CollectionProduct, Product
from app.schemas import MessageOut
from app.security import AdminUser
from app.audit import log_audit

router = APIRouter(prefix='/collections', tags=['Collections'])


class CollectionCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None


class CollectionProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    price: float
    discount_price: Optional[float] = None


class CollectionDetailOut(CollectionOut):
    products: List[CollectionProductOut] = []


class AddProductIn(BaseModel):
    product_id: int
    position: int = 0


# ----------------------------- Public -----------------------------
@router.get('', response_model=List[CollectionOut])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Collection)
        .where(Collection.is_active == True)  # noqa: E712
        .order_by(Collection.name)
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/{slug}', response_model=CollectionDetailOut)
async def get_collection(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.slug == slug))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail='Collection not found')
    return collection


# ----------------------------- Admin CRUD -----------------------------
@router.post('', response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    dup = await db.execute(select(Collection).where(Collection.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    collection = Collection(**payload.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    await log_audit(
        db=db, action="CREATE", entity_type="Collection", entity_id=collection.id,
        user_id=admin.id, details=f"Created collection: {collection.name}"
    )
    return collection


@router.put('/{collection_id}', response_model=CollectionOut)
async def update_collection(
    collection_id: int, payload: CollectionUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail='Collection not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(collection, field, value)
    await db.commit()
    await db.refresh(collection)
    await log_audit(
        db=db, action="UPDATE", entity_type="Collection", entity_id=collection.id,
        user_id=admin.id, details=f"Updated collection: {collection.name}"
    )
    return collection


@router.delete('/{collection_id}', response_model=MessageOut)
async def delete_collection(
    collection_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail='Collection not found')
    name = collection.name
    await db.delete(collection)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="Collection", entity_id=collection_id,
        user_id=admin.id, details=f"Deleted collection: {name}"
    )
    return MessageOut(detail='Collection deleted')


# ----------------------------- Collection Products -----------------------------
@router.post('/{collection_id}/products', response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def add_product_to_collection(
    collection_id: int, payload: AddProductIn,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    collection = (
        await db.execute(select(Collection).where(Collection.id == collection_id))
    ).scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail='Collection not found')

    product = (
        await db.execute(select(Product).where(Product.id == payload.product_id))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    existing = (
        await db.execute(
            select(CollectionProduct).where(
                CollectionProduct.collection_id == collection_id,
                CollectionProduct.product_id == payload.product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail='Product already in collection')

    cp = CollectionProduct(
        collection_id=collection_id,
        product_id=payload.product_id,
        position=payload.position,
    )
    db.add(cp)
    await db.commit()
    await log_audit(
        db=db, action="CREATE", entity_type="CollectionProduct", entity_id=cp.id,
        user_id=admin.id,
        details=f"Added product {payload.product_id} to collection {collection.name}",
    )
    return MessageOut(detail='Product added to collection')


@router.delete('/{collection_id}/products/{product_id}', response_model=MessageOut)
async def remove_product_from_collection(
    collection_id: int, product_id: int,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(
        select(CollectionProduct).where(
            CollectionProduct.collection_id == collection_id,
            CollectionProduct.product_id == product_id,
        )
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail='Product not in collection')
    await db.delete(cp)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="CollectionProduct", entity_id=cp.id,
        user_id=admin.id,
        details=f"Removed product {product_id} from collection {collection_id}",
    )
    return MessageOut(detail='Product removed from collection')
