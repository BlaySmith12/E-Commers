"""Admin REST API - dashboard stats and admin CRUD endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import (
    User, Product, Order, OrderItem, Category, Brand,
    ProductReview, Payment, SiteSetting, ProductImage,
    ProductVariant, AuditLog, Role, Permission,
)
from app.schemas import (
    CategoryCreate, CategoryUpdate, CategoryOut,
    BrandCreate, BrandUpdate, BrandOut,
    ProductCreate, ProductUpdate, ProductOut,
    UserOut, MessageOut,
)
from app.security import RequireAdmin, RequireCreator, RequireEditor, RequireViewer, RequireDeleter
from app.audit import log_audit
from app.activity import log_activity

router = APIRouter(prefix='/admin', tags=['Admin'])


def _invalidate_settings_cache():
    """Clear site settings cache. Lazy import to avoid circular dependency."""
    from app.settings_cache import invalidate_site_settings_cache
    invalidate_site_settings_cache()

# Subquery to identify admin role IDs (roles with ADMIN permission bit set)
_admin_role_ids_subq = select(Role.id).where(Role.permissions.op('&')(Permission.ADMIN) > 0).scalar_subquery()
_non_admin_filter = or_(User.role_id.is_(None), User.role_id.notin_(_admin_role_ids_subq))


# ------------------------------- Dashboard -------------------------------
@router.get('/dashboard')
async def admin_dashboard(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    from datetime import datetime as _dt
    today = _dt.utcnow().date()
    start_of_today = _dt(today.year, today.month, today.day)
    start_of_month = _dt(today.year, today.month, 1)

    orders_today = (await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= start_of_today))).scalar_one()
    orders_month = (await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= start_of_month))).scalar_one()

    revenue_today = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= start_of_today))).scalar_one()
    revenue_month = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= start_of_month))).scalar_one()

    processing_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == 'Processing'))).scalar_one()
    shipped_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == 'Shipped'))).scalar_one()
    delivered_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == 'Delivered'))).scalar_one()
    cancelled_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == 'Cancelled'))).scalar_one()
    total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()

    return {
        'revenue_today': round(revenue_today, 2),
        'revenue_month': round(revenue_month, 2),
        'orders_today': orders_today,
        'orders_month': orders_month,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'total_orders': total_orders,
    }


# ------------------------------- Categories -------------------------------
@router.get('/categories', response_model=List[CategoryOut])
async def admin_list_categories(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.post('/categories', response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def admin_create_category(payload: CategoryCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireCreator)):
    dup = await db.execute(select(Category).where(Category.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    category = Category(**payload.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Category",
        entity_id=category.id,
        user_id=admin.id,
        details=f"Created category: {category.name}"
    )
    return category


@router.put('/categories/{category_id}', response_model=CategoryOut)
async def admin_update_category(category_id: int, payload: CategoryUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    old_values = {c.name: getattr(category, c.name) for c in category.__table__.columns}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    new_values = {c.name: getattr(category, c.name) for c in category.__table__.columns}
    changes = {k: f"{old_values.get(k)} -> {new_values.get(k)}" for k in new_values if old_values.get(k) != new_values.get(k)}
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Category",
        entity_id=category.id,
        user_id=admin.id,
        details=f"Updated category: {category.name}. Changes: {', '.join(f'{k}: {v}' for k, v in changes.items())}"
    )
    return category


@router.delete('/categories/{category_id}', response_model=MessageOut)
async def admin_delete_category(category_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireDeleter)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    await db.delete(category)
    await db.commit()
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Category",
        entity_id=category_id,
        user_id=admin.id,
        details=f"Deleted category: {category.name if category else 'Unknown'} (ID: {category_id})"
    )
    return MessageOut(detail='Category deleted')


@router.delete('/categories', response_model=MessageOut)
async def admin_bulk_delete_categories(
    category_ids: List[int] = Query(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    """Bulk delete categories by ID list."""
    if not category_ids:
        raise HTTPException(status_code=400, detail='No category IDs provided')
    
    # Get the categories to delete for logging
    stmt = select(Category).where(Category.id.in_(category_ids))
    result = await db.execute(stmt)
    categories_to_delete = result.scalars().all()
    
    # Delete the categories
    delete_stmt = Category.__table__.delete().where(Category.id.in_(category_ids))
    await db.execute(delete_stmt)
    await db.commit()
    
    # Log audit for bulk deletion
    category_names = [c.name for c in categories_to_delete]
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Category",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk deleted {len(categories_to_delete)} categories: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully deleted {len(categories_to_delete)} categories')


@router.post('/categories/bulk-status-update', response_model=MessageOut)
async def bulk_update_category_status(
    category_ids: List[int],
    status: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update status for multiple categories."""
    if not category_ids:
        raise HTTPException(status_code=400, detail='No category IDs provided')
    if not status:
        raise HTTPException(status_code=400, detail='Status is required')
    
    # Get the categories to update for logging
    result = await db.execute(select(Category).where(Category.id.in_(category_ids)))
    categories_to_update = result.scalars().all()
    
    if not categories_to_update:
        raise HTTPException(status_code=404, detail='No categories found with provided IDs')
    
    # Update the categories
    update_stmt = (
        Category.__table__.update()
        .where(Category.id.in_(category_ids))
        .values(status=status)
    )
    await db.execute(update_stmt)
    await db.commit()
    
    # Log the bulk update
    category_names = [c.name for c in categories_to_update]
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Category",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk updated status to '{status}' for {len(categories_to_update)} categories: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully updated status for {len(categories_to_update)} categories')


# ------------------------------- Brands -------------------------------
@router.get('/brands', response_model=List[BrandOut])
async def admin_list_brands(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    result = await db.execute(select(Brand).order_by(Brand.name))
    return result.scalars().all()


@router.post('/brands', response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def admin_create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireCreator)):
    dup = await db.execute(select(Brand).where(Brand.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    brand = Brand(**payload.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Brand",
        entity_id=brand.id,
        user_id=admin.id,
        details=f"Created brand: {brand.name}"
    )
    return brand


@router.put('/brands/{brand_id}', response_model=BrandOut)
async def admin_update_brand(brand_id: int, payload: BrandUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    old_values = {c.name: getattr(brand, c.name) for c in brand.__table__.columns}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    await db.commit()
    await db.refresh(brand)
    new_values = {c.name: getattr(brand, c.name) for c in brand.__table__.columns}
    changes = {k: f"{old_values.get(k)} -> {new_values.get(k)}" for k in new_values if old_values.get(k) != new_values.get(k)}
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Brand",
        entity_id=brand.id,
        user_id=admin.id,
        details=f"Updated brand: {brand.name}. Changes: {', '.join(f'{k}: {v}' for k, v in changes.items())}"
    )
    return brand


@router.delete('/brands/{brand_id}', response_model=MessageOut)
async def admin_delete_brand(brand_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireDeleter)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    brand_name = brand.name
    await db.delete(brand)
    await db.commit()
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Brand",
        entity_id=brand_id,
        user_id=admin.id,
        details=f"Deleted brand: {brand_name}"
    )
    return MessageOut(detail='Brand deleted')


# ------------------------------- Bulk Operations -------------------------------
@router.post('/brands/bulk-delete', response_model=MessageOut)
async def bulk_delete_brands(
    brand_ids: List[int],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    """Bulk delete multiple brands."""
    if not brand_ids:
        raise HTTPException(status_code=400, detail='No brand IDs provided')
    
    # Get the brands to delete for logging
    result = await db.execute(select(Brand).where(Brand.id.in_(brand_ids)))
    brands_to_delete = result.scalars().all()
    
    if not brands_to_delete:
        raise HTTPException(status_code=404, detail='No brands found with provided IDs')
    
    # Delete the brands
    delete_stmt = Brand.__table__.delete().where(Brand.id.in_(brand_ids))
    await db.execute(delete_stmt)
    await db.commit()
    
    # Log the bulk deletion
    brand_names = [b.name for b in brands_to_delete]
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Brand",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk deleted {len(brands_to_delete)} brands: {', '.join(brand_names[:5])}{'...' if len(brand_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully deleted {len(brands_to_delete)} brands')


@router.post('/brands/bulk-status-update', response_model=MessageOut)
async def bulk_update_brand_status(
    brand_ids: List[int],
    status: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update status for multiple brands."""
    if not brand_ids:
        raise HTTPException(status_code=400, detail='No brand IDs provided')
    if not status:
        raise HTTPException(status_code=400, detail='Status is required')
    
    # Get the brands to update for logging
    result = await db.execute(select(Brand).where(Brand.id.in_(brand_ids)))
    brands_to_update = result.scalars().all()
    
    if not brands_to_update:
        raise HTTPException(status_code=404, detail='No brands found with provided IDs')
    
    # Update the brands
    update_stmt = (
        Brand.__table__.update()
        .where(Brand.id.in_(brand_ids))
        .values(status=status)
    )
    await db.execute(update_stmt)
    await db.commit()
    
    # Log the bulk update
    brand_names = [b.name for b in brands_to_update]
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Brand",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk updated status to '{status}' for {len(brands_to_update)} brands: {', '.join(brand_names[:5])}{'...' if len(brand_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully updated status for {len(brands_to_update)} brands')


# ------------------------------- Products -------------------------------
@router.get('/products', response_model=List[ProductOut])
async def admin_list_products(
    db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer),
    category_id: int = Query(None), brand_id: int = Query(None),
    search: str = Query(None), status: str = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=2000),
):
    stmt = select(Product)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(term), Product.sku.ilike(term)))
    if status:
        stmt = stmt.where(Product.status == status)
    stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post('/products', response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def admin_create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireCreator)):
    dup = await db.execute(select(Product).where(Product.sku == payload.sku))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='SKU already exists')
    product = Product(
        name=payload.name, sku=payload.sku, slug=payload.slug,
        price=payload.price, discount_price=payload.discount_price,
        stock=payload.stock, description=payload.description,
        is_featured=payload.is_featured, is_trending=payload.is_trending,
        status=payload.status, category_id=payload.category_id, brand_id=payload.brand_id,
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
    result = await db.execute(
        select(Product)
        .where(Product.id == product.id)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants),
            selectinload(Product.attributes),
        )
    )
    product = result.scalar_one()
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Product",
        entity_id=product.id,
        user_id=admin.id,
        details=f"Created product: {product.name} (SKU: {product.sku})"
    )
    await log_activity(
        db=db,
        activity_type="product_created",
        description=f"New product added: {product.name} (SKU: {product.sku})",
        entity_type="Product",
        entity_id=product.id,
        entity_number=product.sku,
        actor_name=((admin.first_name or '') + ' ' + (admin.last_name or '')).strip() or admin.email or "Admin",
        actor_id=admin.id,
    )
    await db.commit()
    return product


@router.put('/products/{product_id}', response_model=ProductOut)
async def admin_update_product(product_id: int, payload: ProductUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    old_values = {c.name: getattr(product, c.name) for c in product.__table__.columns}
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    new_values = {c.name: getattr(product, c.name) for c in product.__table__.columns}
    changes = {k: f"{old_values.get(k)} -> {new_values.get(k)}" for k in new_values if old_values.get(k) != new_values.get(k)}
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Product",
        entity_id=product.id,
        user_id=admin.id,
        details=f"Updated product: {product.name} (SKU: {product.sku}). Changes: {', '.join(f'{k}: {v}' for k, v in changes.items())}"
    )
    await log_activity(
        db=db,
        activity_type="product_updated",
        description=f"Product {product.name} was updated",
        entity_type="Product",
        entity_id=product.id,
        entity_number=product.sku,
        actor_name=((admin.first_name or '') + ' ' + (admin.last_name or '')).strip() or admin.email or "Admin",
        actor_id=admin.id,
    )
    await db.commit()
    return product


@router.delete('/products/{product_id}', response_model=MessageOut)
async def admin_delete_product(product_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireDeleter)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    product_name = product.name
    product_sku = product.sku
    await db.execute(text("DELETE FROM inventory WHERE product_id = :pid"), {"pid": product_id})
    await db.execute(text("UPDATE order_items SET product_id = NULL WHERE product_id = :pid"), {"pid": product_id})
    await db.execute(text("DELETE FROM wishlists WHERE product_id = :pid"), {"pid": product_id})
    await db.execute(text("DELETE FROM collection_products WHERE product_id = :pid"), {"pid": product_id})
    await db.delete(product)
    await db.commit()
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Product",
        entity_id=product_id,
        user_id=admin.id,
        details=f"Deleted product: {product_name} (SKU: {product_sku})"
    )
    await log_activity(
        db=db,
        activity_type="product_deleted",
        description=f"Product {product_name} was deleted",
        entity_type="Product",
        entity_id=product_id,
        entity_number=product_sku,
        actor_name=((admin.first_name or '') + ' ' + (admin.last_name or '')).strip() or admin.email or "Admin",
        actor_id=admin.id,
    )
    await db.commit()
    return MessageOut(detail='Product deleted')


# ------------------------------- Bulk Operations -------------------------------
@router.post('/products/bulk-delete', response_model=MessageOut)
async def bulk_delete_products(
    product_ids: List[int],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    """Bulk delete multiple products."""
    if not product_ids:
        raise HTTPException(status_code=400, detail='No product IDs provided')
    
    # Get the products to delete for logging
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_to_delete = result.scalars().all()
    
    if not products_to_delete:
        raise HTTPException(status_code=404, detail='No products found with provided IDs')
    
    # Delete inventory records first (FK constraint)
    await db.execute(text("DELETE FROM inventory WHERE product_id = ANY(:ids)"), {"ids": product_ids})
    # Nullify FK references that don't cascade
    await db.execute(text("UPDATE order_items SET product_id = NULL WHERE product_id = ANY(:ids)"), {"ids": product_ids})
    await db.execute(text("DELETE FROM wishlists WHERE product_id = ANY(:ids)"), {"ids": product_ids})
    await db.execute(text("DELETE FROM collection_products WHERE product_id = ANY(:ids)"), {"ids": product_ids})
    # Delete the products
    delete_stmt = Product.__table__.delete().where(Product.id.in_(product_ids))
    await db.execute(delete_stmt)
    await db.commit()
    
    # Log the bulk deletion
    product_names = [p.name for p in products_to_delete]
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Product",
        entity_id=0,  # Using 0 for bulk operations
        user_id=admin.id,
        details=f"Bulk deleted {len(products_to_delete)} products: {', '.join(product_names[:5])}{'...' if len(product_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully deleted {len(products_to_delete)} products')


@router.post('/products/bulk-status-update', response_model=MessageOut)
async def bulk_update_product_status(
    product_ids: List[int],
    status: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update status for multiple products."""
    if not product_ids:
        raise HTTPException(status_code=400, detail='No product IDs provided')
    if not status:
        raise HTTPException(status_code=400, detail='Status is required')
    
    # Get the products to update for logging
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_to_update = result.scalars().all()
    
    if not products_to_update:
        raise HTTPException(status_code=404, detail='No products found with provided IDs')
    
    # Update the products
    update_stmt = (
        Product.__table__.update()
        .where(Product.id.in_(product_ids))
        .values(status=status)
    )
    await db.execute(update_stmt)
    await db.commit()
    
    # Log the bulk update
    product_names = [p.name for p in products_to_update]
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Product",
        entity_id=0,  # Using 0 for bulk operations
        user_id=admin.id,
        details=f"Bulk updated status to '{status}' for {len(products_to_update)} products: {', '.join(product_names[:5])}{'...' if len(product_names) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully updated status for {len(products_to_update)} products')


# ------------------------------- Customers -------------------------------
@router.get('/customers')
async def admin_list_customers(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=2000),
    search: str = Query(None),
    status_filter: str = Query(None, alias='status'),
    sort_by: str = Query('created_at'),
    sort_dir: str = Query('desc'),
):
    stmt = (
        select(User)
        .where(_non_admin_filter)
        .options(selectinload(User.role))
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            User.first_name.ilike(like),
            User.last_name.ilike(like),
            User.email.ilike(like),
            User.phone.ilike(like),
            User.username.ilike(like),
        ))
    if status_filter == 'active':
        stmt = stmt.where(User.is_active == True)
    elif status_filter == 'inactive':
        stmt = stmt.where(User.is_active == False)

    sort_col = getattr(User, sort_by, User.created_at)
    if sort_dir == 'asc':
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    result = await db.execute(stmt.offset(skip).limit(limit))
    users = result.scalars().unique().all()

    user_ids = [u.id for u in users]
    order_stats = {}
    if user_ids:
        os_result = await db.execute(
            select(
                Order.user_id,
                func.count(Order.id).label('order_count'),
                func.coalesce(func.sum(Order.total_amount), 0).label('total_spent'),
                func.max(Order.created_at).label('last_order_at'),
            )
            .where(Order.user_id.in_(user_ids))
            .group_by(Order.user_id)
        )
        for row in os_result.all():
            order_stats[row.user_id] = {
                'order_count': row.order_count,
                'total_spent': float(row.total_spent or 0),
                'last_order_at': row.last_order_at.isoformat() if row.last_order_at else None,
            }

    out = []
    for u in users:
        stats = order_stats.get(u.id, {'order_count': 0, 'total_spent': 0, 'last_order_at': None})
        out.append({
            'id': u.id,
            'email': u.email,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'phone': u.phone,
            'is_active': u.is_active,
            'is_admin': u.is_admin,
            'role': {'id': u.role.id, 'name': u.role.name, 'permissions': u.role.permissions} if u.role else None,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'updated_at': u.updated_at.isoformat() if getattr(u, 'updated_at', None) else None,
            'order_count': stats['order_count'],
            'total_spent': stats['total_spent'],
            'last_order_at': stats['last_order_at'],
            'last_login_at': getattr(u, 'last_login_at', None),
        })
    return out


@router.get('/customers/{user_id}')
async def admin_get_customer(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.role)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail='Customer not found')

    orders_result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items), selectinload(Order.payment))
        .order_by(Order.created_at.desc())
    )
    orders = orders_result.scalars().unique().all()

    orders_list = []
    for o in orders:
        orders_list.append({
            'id': o.id,
            'order_number': o.order_number,
            'status': o.status,
            'total_amount': o.total_amount,
            'created_at': o.created_at.isoformat() if o.created_at else None,
            'payment_status': o.payment_status,
            'items_count': len(o.items) if o.items else 0,
        })

    total_spent = sum(o.total_amount for o in orders)
    last_order = orders[0].created_at.isoformat() if orders else None

    return {
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': user.phone,
        'is_active': user.is_active,
        'is_admin': user.is_admin,
        'role': {'id': user.role.id, 'name': user.role.name} if user.role else None,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'order_count': len(orders),
        'total_spent': float(total_spent),
        'last_order_at': last_order,
        'last_login_at': getattr(user, 'last_login_at', None),
        'orders': orders_list,
    }


@router.post('/customers', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def admin_create_customer(payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireCreator)):
    from app.security import hash_password
    email = (payload.get('email') or '').strip()
    password = payload.get('password') or ''
    if not email or not password:
        raise HTTPException(status_code=400, detail='Email and password are required')
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='A customer with this email already exists')

    role_name = (payload.get('role') or 'customer').strip().lower()
    role_result = await db.execute(select(Role).where(Role.name == role_name))
    role = role_result.scalar_one_or_none()
    if not role:
        role_result = await db.execute(select(Role).where(Role.name == 'customer'))
        role = role_result.scalar_one_or_none()

    user = User(
        email=email,
        username=email.split('@')[0],
        password_hash=hash_password(password),
        first_name=payload.get('first_name'),
        last_name=payload.get('last_name'),
        phone=payload.get('phone'),
        role_id=role.id if role else None,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


from pydantic import BaseModel as _PydanticBaseModel


class BulkDeleteIn(_PydanticBaseModel):
    user_ids: List[int]


class BulkStatusUpdateIn(_PydanticBaseModel):
    user_ids: List[int]
    is_active: bool


# ------------------------------- Bulk Operations -------------------------------
@router.post('/customers/bulk-delete', response_model=MessageOut)
async def bulk_delete_customers(
    payload: BulkDeleteIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    user_ids = payload.user_ids
    if not user_ids:
        raise HTTPException(status_code=400, detail='No user IDs provided')

    if admin.id in user_ids:
        raise HTTPException(status_code=400, detail='Cannot delete your own account')

    result = await db.execute(select(User).where(User.id.in_(user_ids), _non_admin_filter))
    users_to_delete = result.scalars().all()

    if not users_to_delete:
        raise HTTPException(status_code=404, detail='No non-admin users found with provided IDs')

    actual_ids = [u.id for u in users_to_delete]

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE orders SET user_id = NULL WHERE user_id = ANY(:ids)"), {'ids': actual_ids})
    except Exception:
        pass

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE orders SET shipping_address_id = NULL WHERE shipping_address_id IN (SELECT id FROM addresses WHERE user_id = ANY(:ids))"), {'ids': actual_ids})
    except Exception:
        pass

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE orders SET billing_address_id = NULL WHERE billing_address_id IN (SELECT id FROM addresses WHERE user_id = ANY(:ids))"), {'ids': actual_ids})
    except Exception:
        pass

    for tbl_name in ['wishlists', 'notifications', 'login_sessions', 'audit_logs', 'product_reviews']:
        try:
            async with db.begin_nested():
                await db.execute(text(f"DELETE FROM {tbl_name} WHERE user_id = ANY(:ids)"), {'ids': actual_ids})
        except Exception:
            pass

    for col_name in ['user_id', 'recipient_id']:
        try:
            async with db.begin_nested():
                await db.execute(text(f"DELETE FROM messages WHERE {col_name} = ANY(:ids)"), {'ids': actual_ids})
        except Exception:
            pass

    try:
        async with db.begin_nested():
            await db.execute(text("DELETE FROM addresses WHERE user_id = ANY(:ids)"), {'ids': actual_ids})
    except Exception:
        pass

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE blog_posts SET author_id = NULL WHERE author_id = ANY(:ids)"), {'ids': actual_ids})
    except Exception:
        pass

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE media_library SET uploaded_by = NULL WHERE uploaded_by = ANY(:ids)"), {'ids': actual_ids})
    except Exception:
        pass

    try:
        async with db.begin_nested():
            await db.execute(text("UPDATE loyalty_transactions SET admin_user_id = NULL WHERE admin_user_id = ANY(:ids)"), {'ids': actual_ids})
    except Exception:
        pass

    delete_stmt = User.__table__.delete().where(User.id.in_(actual_ids), _non_admin_filter)
    await db.execute(delete_stmt)
    await db.commit()

    usernames = [u.username for u in users_to_delete]
    await log_audit(
        db=db, action="DELETE", entity_type="User", entity_id=0,
        user_id=admin.id,
        details=f"Deleted {len(users_to_delete)} customers: {', '.join(usernames[:5])}{'...' if len(usernames) > 5 else ''}"
    )
    return MessageOut(detail=f'Successfully deleted {len(users_to_delete)} customers')


@router.post('/customers/bulk-status-update', response_model=MessageOut)
async def bulk_update_customer_status(
    payload: BulkStatusUpdateIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    user_ids = payload.user_ids
    is_active = payload.is_active
    if not user_ids:
        raise HTTPException(status_code=400, detail='No user IDs provided')

    if not is_active and admin.id in user_ids:
        raise HTTPException(status_code=400, detail='Cannot deactivate your own account')

    result = await db.execute(select(User).where(User.id.in_(user_ids), _non_admin_filter))
    users_to_update = result.scalars().all()

    if not users_to_update:
        raise HTTPException(status_code=404, detail='No non-admin users found with provided IDs')

    actual_ids = [u.id for u in users_to_update]
    update_stmt = (
        User.__table__.update()
        .where(User.id.in_(actual_ids), _non_admin_filter)
        .values(is_active=is_active)
    )
    await db.execute(update_stmt)
    await db.commit()

    usernames = [u.username for u in users_to_update]
    status_text = 'activated' if is_active else 'deactivated'
    await log_audit(
        db=db, action="UPDATE", entity_type="User", entity_id=0,
        user_id=admin.id,
        details=f"{'Activated' if is_active else 'Deactivated'} {len(users_to_update)} customers: {', '.join(usernames[:5])}"
    )
    return MessageOut(detail=f'Successfully {status_text} {len(users_to_update)} customers')
    
    return MessageOut(detail=f'Successfully {status_text} status for {len(users_to_update)} customers')


# ------------------------------- Reviews -------------------------------
@router.get('/reviews')
async def admin_list_reviews(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer), skip: int = 0, limit: int = 50):
    result = await db.execute(
        select(ProductReview, Product, User)
        .join(Product, ProductReview.product_id == Product.id)
        .join(User, ProductReview.user_id == User.id, isouter=True)
        .order_by(ProductReview.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": r.ProductReview.id,
            "rating": r.ProductReview.rating,
            "comment": r.ProductReview.comment,
            "created_at": r.ProductReview.created_at.isoformat() if r.ProductReview.created_at else None,
            "product_id": r.ProductReview.product_id,
            "product_name": r.Product.name,
            "user_id": r.ProductReview.user_id,
            "username": r.User.username if r.User else "Guest",
        }
        for r in rows
    ]


@router.delete('/reviews/{review_id}', response_model=MessageOut)
async def admin_delete_review(review_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireDeleter)):
    result = await db.execute(select(ProductReview).where(ProductReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail='Review not found')
    rating = review.rating
    comment_preview = (review.comment[:50] + '...') if review.comment and len(review.comment) > 50 else review.comment
    await db.delete(review)
    await db.commit()
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Review",
        entity_id=review_id,
        user_id=admin.id,
        details=f"Deleted review: {rating}-star rating (\"{comment_preview}\")"
    )
    return MessageOut(detail='Review deleted')


# ------------------------------- Settings -------------------------------
@router.get('/settings')
async def admin_list_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    result = await db.execute(select(SiteSetting).order_by(SiteSetting.key))
    settings = result.scalars().all()
    return [
        {"id": s.id, "key": s.key, "value": s.value, "description": s.description, "updated_at": s.updated_at.isoformat() if s.updated_at else None}
        for s in settings
    ]


@router.put('/settings/{setting_id}')
async def admin_update_setting(setting_id: int, payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor)):
    result = await db.execute(select(SiteSetting).where(SiteSetting.id == setting_id))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail='Setting not found')
    old_value = setting.value
    old_description = setting.description
    if 'value' in payload:
        setting.value = payload['value']
    if 'description' in payload:
        setting.description = payload['description']
    await db.commit()
    await db.refresh(setting)
    _invalidate_settings_cache()
    changes = []
    if old_value != setting.value:
        changes.append(f"value: '{old_value}' -> '{setting.value}'")
    if old_description != setting.description:
        changes.append(f"description: '{old_description}' -> '{setting.description}'")
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Setting",
        entity_id=setting.id,
        user_id=admin.id,
        details=f"Updated setting: {setting.key}. Changes: {', '.join(changes)}"
    )
    return {"id": setting.id, "key": setting.key, "value": setting.value, "description": setting.description}


@router.post('/settings', status_code=status.HTTP_201_CREATED)
async def admin_create_setting(payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireCreator)):
    key = payload.get('key')
    if not key:
        raise HTTPException(status_code=400, detail='Key is required')
    dup = await db.execute(select(SiteSetting).where(SiteSetting.key == key))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Setting key already exists')
    setting = SiteSetting(
        key=key,
        value=payload.get('value', ''),
        description=payload.get('description', ''),
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    _invalidate_settings_cache()
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Setting",
        entity_id=setting.id,
        user_id=admin.id,
        details=f"Created setting: {setting.key} = '{setting.value}'"
    )
    return {"id": setting.id, "key": setting.key, "value": setting.value, "description": setting.description}


# ------------------------------- Bulk Operations -------------------------------
@router.delete('/settings', response_model=MessageOut)
async def bulk_delete_settings(
    setting_ids: List[int],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    """Bulk delete multiple settings."""
    if not setting_ids:
        raise HTTPException(status_code=400, detail='No setting IDs provided')
    
    # Get the settings to delete for logging
    result = await db.execute(select(SiteSetting).where(SiteSetting.id.in_(setting_ids)))
    settings_to_delete = result.scalars().all()
    
    if not settings_to_delete:
        raise HTTPException(status_code=404, detail='No settings found with provided IDs')
    
    # Delete the settings
    delete_stmt = SiteSetting.__table__.delete().where(SiteSetting.id.in_(setting_ids))
    await db.execute(delete_stmt)
    await db.commit()
    _invalidate_settings_cache()
    
    # Log the bulk deletion
    setting_keys = [s.key for s in settings_to_delete]
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="Setting",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk deleted {len(settings_to_delete)} settings: {', '.join(setting_keys[:5])}{'...' if len(setting_keys) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully deleted {len(settings_to_delete)} settings')


@router.post('/settings/bulk-update', response_model=MessageOut)
async def bulk_update_settings(
    updates: List[dict],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update multiple settings."""
    if not updates:
        raise HTTPException(status_code=400, detail='No updates provided')
    
    # Process each update
    updated_count = 0
    updated_keys = []
    
    for update in updates:
        setting_id = update.get('id')
        if not setting_id:
            continue
            
        result = await db.execute(select(SiteSetting).where(SiteSetting.id == setting_id))
        setting = result.scalar_one_or_none()
        
        if not setting:
            continue
            
        old_values = {}
        if 'value' in update:
            old_values['value'] = setting.value
            setting.value = update['value']
        if 'description' in update:
            old_values['description'] = setting.description
            setting.description = update['description']
            
        if old_values:
            await db.commit()
            await db.refresh(setting)
            updated_count += 1
            updated_keys.append(setting.key)
    
    if updated_count == 0:
        raise HTTPException(status_code=404, detail='No valid settings found to update')
    
    _invalidate_settings_cache()
    
    # Log the bulk update
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Setting",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk updated {updated_count} settings: {', '.join(updated_keys[:5])}{'...' if len(updated_keys) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully updated {updated_count} settings')


# ------------------------------- Users & Roles -------------------------------
@router.get('/users')
async def admin_list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer), skip: int = 0, limit: int = 50):
    result = await db.execute(select(User).order_by(User.created_at.desc()).offset(skip).limit(limit))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "phone": u.phone,
            "is_active": u.is_active,
            "role_id": u.role_id,
            "role_name": u.role.name if u.role else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


# ------------------------------- Bulk Operations -------------------------------
@router.post('/users/bulk-delete', response_model=MessageOut)
async def bulk_delete_users(
    user_ids: List[int],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireDeleter),
):
    """Bulk delete multiple users (non-admins only, cannot delete self)."""
    if not user_ids:
        raise HTTPException(status_code=400, detail='No user IDs provided')
    
    # Prevent deleting self
    if admin.id in user_ids:
        raise HTTPException(status_code=400, detail='Cannot delete your own account')
    
    # Get the users to delete for logging (ensure they're not admins, except we already checked above)
    result = await db.execute(select(User).where(User.id.in_(user_ids), _non_admin_filter))
    users_to_delete = result.scalars().all()
    
    if not users_to_delete:
        raise HTTPException(status_code=404, detail='No non-admin users found with provided IDs')
    
    # Delete the users
    delete_stmt = User.__table__.delete().where(User.id.in_(user_ids), _non_admin_filter)
    await db.execute(delete_stmt)
    await db.commit()
    
    # Log the bulk deletion
    usernames = [u.username for u in users_to_delete]
    await log_audit(
        db=db,
        action="DELETE",
        entity_type="User",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk deleted {len(users_to_delete)} users: {', '.join(usernames[:5])}{'...' if len(usernames) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully deleted {len(users_to_delete)} users')


@router.post('/users/bulk-role-update', response_model=MessageOut)
async def bulk_update_user_role(
    user_ids: List[int],
    role_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update role for multiple users."""
    if not user_ids:
        raise HTTPException(status_code=400, detail='No user IDs provided')
    if role_id is None:
        raise HTTPException(status_code=400, detail='Role ID is required')
    
    # Prevent assigning role to self if it would remove admin privileges
    # (Optional: could add more sophisticated logic here)
    
    # Get the users to update for logging
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_to_update = result.scalars().all()
    
    if not users_to_update:
        raise HTTPException(status_code=404, detail='No users found with provided IDs')
    
    # Update the users
    update_stmt = (
        User.__table__.update()
        .where(User.id.in_(user_ids))
        .values(role_id=role_id)
    )
    await db.execute(update_stmt)
    await db.commit()
    
    # Get role name for logging
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalar_one_or_none()
    role_name = role.name if role else f"ID:{role_id}"
    
    # Log the bulk update
    usernames = [u.username for u in users_to_update]
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="User",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk updated role to '{role_name}' for {len(users_to_update)} users: {', '.join(usernames[:5])}{'...' if len(usernames) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully updated role for {len(users_to_update)} users')


@router.post('/users/bulk-status-update', response_model=MessageOut)
async def bulk_update_user_status(
    user_ids: List[int],
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireEditor),
):
    """Bulk update active status for multiple users."""
    if not user_ids:
        raise HTTPException(status_code=400, detail='No user IDs provided')
    
    # Prevent deactivating self
    if admin.id in user_ids and not is_active:
        raise HTTPException(status_code=400, detail='Cannot deactivate your own account')
    
    # Get the users to update for logging
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_to_update = result.scalars().all()
    
    if not users_to_update:
        raise HTTPException(status_code=404, detail='No users found with provided IDs')
    
    # Update the users
    update_stmt = (
        User.__table__.update()
        .where(User.id.in_(user_ids))
        .values(is_active=is_active)
    )
    await db.execute(update_stmt)
    await db.commit()
    
    # Log the bulk update
    usernames = [u.username for u in users_to_update]
    status_text = 'activated' if is_active else 'deactivated'
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="User",
        entity_id=0,  # Bulk operation
        user_id=admin.id,
        details=f"Bulk {status_text} {len(users_to_update)} users: {', '.join(usernames[:5])}{'...' if len(usernames) > 5 else ''}"
    )
    
    return MessageOut(detail=f'Successfully {status_text} status for {len(users_to_update)} users')


@router.patch('/users/{user_id}/role')
async def admin_update_user_role(user_id: int, payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    old_vals = {'role_id': user.role_id, 'is_active': user.is_active, 'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email, 'phone': user.phone}

    if 'first_name' in payload:
        user.first_name = payload['first_name']
    if 'last_name' in payload:
        user.last_name = payload['last_name']
    if 'email' in payload and payload['email']:
        existing = await db.execute(select(User).where(User.email == payload['email'], User.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail='Email already in use')
        user.email = payload['email']
    if 'phone' in payload:
        user.phone = payload['phone']
    if 'role_id' in payload and payload['role_id'] is not None:
        user.role_id = payload['role_id']
    elif 'role' in payload:
        role_name = payload['role']
        role_result = await db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role:
            user.role_id = role.id
    if 'is_active' in payload:
        if not payload['is_active'] and admin.id == user_id:
            raise HTTPException(status_code=400, detail='Cannot deactivate your own account')
        user.is_active = payload['is_active']

    await db.commit()
    await db.refresh(user)

    changes = []
    for key in ['role_id', 'is_active', 'first_name', 'last_name', 'email', 'phone']:
        if old_vals.get(key) != getattr(user, key):
            changes.append(f"{key}: {old_vals.get(key)} -> {getattr(user, key)}")

    if changes:
        await log_audit(
            db=db, action="UPDATE", entity_type="User", entity_id=user.id,
            user_id=admin.id,
            details=f"Updated customer {user.username}: {', '.join(changes)}"
        )

    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone, "role_id": user.role_id, "is_active": user.is_active}


# ------------------------------- Inventory -------------------------------
@router.get('/inventory')
async def admin_inventory(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer)):
    result = await db.execute(
        select(ProductVariant, Product)
        .join(Product, ProductVariant.product_id == Product.id)
        .order_by(Product.name, ProductVariant.name)
    )
    rows = result.all()
    return [
        {
            "id": r.ProductVariant.id,
            "product_id": r.ProductVariant.product_id,
            "product_name": r.Product.name,
            "product_sku": r.Product.sku,
            "name": r.ProductVariant.name,
            "sku": r.ProductVariant.sku,
            "stock": r.ProductVariant.stock,
            "price_modifier": r.ProductVariant.price_modifier,
        }
        for r in rows
    ]


@router.patch('/inventory/{variant_id}')
async def admin_update_inventory(variant_id: int, payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(RequireAdmin)):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail='Variant not found')
    old_stock = variant.stock
    old_price_modifier = variant.price_modifier
    if 'stock' in payload:
        variant.stock = payload['stock']
    if 'price_modifier' in payload:
        variant.price_modifier = payload['price_modifier']
    await db.commit()
    await db.refresh(variant)
    changes = []
    if old_stock != variant.stock:
        changes.append(f"stock: {old_stock} -> {variant.stock}")
    if old_price_modifier != variant.price_modifier:
        changes.append(f"price_modifier: {old_price_modifier} -> {variant.price_modifier}")
    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Inventory",
        entity_id=variant.id,
        user_id=admin.id,
        details=f"Updated inventory for variant: {variant.sku} - {variant.name}. Changes: {', '.join(changes)}"
    )
    return {"id": variant.id, "stock": variant.stock, "price_modifier": variant.price_modifier}


# ------------------------------- Payments -------------------------------
@router.get('/payments')
async def admin_list_payments(db: AsyncSession = Depends(get_db), admin: User = Depends(RequireViewer), skip: int = 0, limit: int = Query(50, ge=1, le=2000)):
    result = await db.execute(
        select(Payment, Order, User)
        .join(Order, Payment.order_id == Order.id)
        .join(User, Order.user_id == User.id, isouter=True)
        .order_by(Payment.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": r.Payment.id,
            "order_id": r.Payment.order_id,
            "order_number": r.Order.order_number if r.Order else None,
            "amount": r.Payment.amount,
            "currency": r.Payment.currency or "GHS",
            "status": r.Payment.status,
            "payment_method": r.Payment.payment_method,
            "transaction_id": r.Payment.transaction_reference or r.Payment.paystack_reference or str(r.Payment.id),
            "channel": r.Payment.channel or "",
            "provider": r.Payment.provider or "paystack",
            "customer_name": f"{r.User.first_name or ''} {r.User.last_name or ''}".strip() if r.User else "Guest",
            "customer_email": r.Payment.customer_email or (r.User.email if r.User else ""),
            "paid_at": r.Payment.paid_at.isoformat() if r.Payment.paid_at else None,
            "failure_reason": r.Payment.failure_reason or "",
            "created_at": r.Payment.created_at.isoformat() if r.Payment.created_at else None,
        }
        for r in rows
    ]
