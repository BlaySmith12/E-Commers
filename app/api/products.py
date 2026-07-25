"""Product, Category and Brand REST APIs."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Product, Category, Brand, ProductImage
from app.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    ProductImageOut,
    ProductVariantOut,
    ProductAttributeOut,
    CategoryCreate,
    CategoryUpdate,
    CategoryOut,
    BrandCreate,
    BrandUpdate,
    BrandOut,
    MessageOut,
)
from app.security import AdminUser

router = APIRouter(prefix='/products', tags=['Products'])


# ----------------------------- Query helpers -----------------------------
def _apply_filters(stmt, *, category_id, brand_id, min_price, max_price,
                   search, featured, trending, in_stock, status):
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id is not None:
        stmt = stmt.where(Product.brand_id == brand_id)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(term), Product.description.ilike(term)))
    if featured is not None:
        stmt = stmt.where(Product.is_featured == featured)
    if trending is not None:
        stmt = stmt.where(Product.is_trending == trending)
    if in_stock:
        stmt = stmt.where(Product.stock > 0)
    if status:
        stmt = stmt.where(Product.status == status)
    return stmt


# ----------------------------- Public endpoints -----------------------------
@router.get('', response_model=List[ProductOut])
async def list_products(
    db: AsyncSession = Depends(get_db),
    category_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None),
    featured: Optional[bool] = Query(None),
    trending: Optional[bool] = Query(None),
    in_stock: bool = Query(False),
    status: str = Query('active'),
    sort: str = Query('newest'),  # newest, price_asc, price_desc, name
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Product)
    stmt = _apply_filters(
        stmt, category_id=category_id, brand_id=brand_id, min_price=min_price,
        max_price=max_price, search=search, featured=featured, trending=trending,
        in_stock=in_stock, status=status,
    )
    if sort == 'price_asc':
        stmt = stmt.order_by(Product.price.asc())
    elif sort == 'price_desc':
        stmt = stmt.order_by(Product.price.desc())
    elif sort == 'name':
        stmt = stmt.order_by(Product.name.asc())
    else:
        stmt = stmt.order_by(Product.created_at.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/count', response_model=dict)
async def count_products(
    db: AsyncSession = Depends(get_db),
    category_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    status: str = Query('active'),
):
    stmt = select(func.count()).select_from(Product)
    stmt = _apply_filters(
        stmt, category_id=category_id, brand_id=brand_id, min_price=None,
        max_price=None, search=search, featured=None, trending=None,
        in_stock=False, status=status,
    )
    total = await db.execute(stmt)
    return {'total': total.scalar_one()}


@router.get('/{product_id}', response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return product


@router.get('/slug/{slug}', response_model=ProductOut)
async def get_product_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.slug == slug))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return product


# ----------------------------- Admin CRUD -----------------------------
@router.post('', response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    dup = await db.execute(select(Product).where(Product.sku == payload.sku))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='SKU already exists')

    product = Product(
        name=payload.name, sku=payload.sku, slug=payload.slug,
        price=payload.price, discount_price=payload.discount_price,
        stock=payload.stock, description=payload.description,
        is_featured=payload.is_featured, is_trending=payload.is_trending,
        status=payload.status, category_id=payload.category_id,
        brand_id=payload.brand_id,
    )
    db.add(product)
    await db.flush()

    for img in payload.images:
        db.add(ProductImage(product_id=product.id, **img.model_dump()))
    for var in payload.variants:
        from app.models.catalog import ProductVariant
        db.add(ProductVariant(product_id=product.id, **var.model_dump()))
    for attr in payload.attributes:
        from app.models.catalog import ProductAttribute
        db.add(ProductAttribute(product_id=product.id, **attr.model_dump()))

    await db.commit()
    await db.refresh(product)
    return product


@router.put('/{product_id}', response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete('/{product_id}', response_model=MessageOut)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    await db.delete(product)
    await db.commit()
    return MessageOut(detail='Product deleted')
