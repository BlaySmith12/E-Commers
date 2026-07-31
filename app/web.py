"""FastAPI application that serves both the REST API and the HTML frontend.

It mounts the JSON routers from ``app.api`` under ``/api`` and exposes
server-rendered pages (storefront, auth, admin, customer) using Jinja2.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, func, or_, text

from config import config
from app.db import init_db, dispose_engine, async_session_maker
from app.api import (
    auth, products, categories, brands, cart, orders, customers, admin,
    coupons, wishlists, testimonials, hero_banners, blog, newsletters,
    notifications, collections, audit, content, reviews,
    messages as messages_api, search as search_api, admin_profile,
    reports as reports_api, auth_extended, media as media_api,
    payments as payments_api, loyalty, analytics, email_admin,
    promotions as promotions_api,
)
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware, register_exception_handlers
from app.models.catalog import (
    Category, Brand, Product, Order, OrderItem, User,
    ProductReview, Payment, SiteSetting, ProductVariant, HeroBanner, PaymentEvent,
)
from app.models.catalog import Role, Permission
from app.security import decode_access_token

_non_admin_filter = or_(User.role_id.is_(None), User.role_id.notin_(
    select(Role.id).where(Role.permissions.op('&')(Permission.ADMIN) > 0).scalar_subquery()
))

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


class _AnonymousUser:
    is_authenticated = False
    username = ""
    email = ""


_anonymous = _AnonymousUser()


def url_for(endpoint: str, **kwargs) -> str:
    if endpoint == "static":
        filename = kwargs.get("filename", "")
        return f"/static/{filename}"
    return _ROUTES.get(endpoint, "/")


_ROUTES = {
    "main.index": "/",
    "shop.index": "/shop",
    "shop.product": "/product/{slug}",
    "auth.login": "/login",
    "auth.register": "/register",
    "auth.logout": "/logout",
    "customer.dashboard": "/customer/dashboard",
    "admin.dashboard": "/admin",
    "admin.product_list": "/admin/products",
    "admin.product_add": "/admin/products/add",
    "admin.product_edit": "/admin/products/edit/{product_id}",
    "admin.product_delete": "/admin/products/delete/{product_id}",
    "about": "/about",
    "contact": "/contact",
    "shipping_policy": "/shipping-policy",
    "returns_refunds": "/returns-refunds",
    "faq": "/faq",
    "order_tracking": "/order-tracking",
    "payment_security": "/payment-security",
}


from app.settings_cache import invalidate_site_settings_cache, get_cached_settings, get_cache_time, set_cache


async def _get_site_settings() -> dict:
    """Load site settings from DB (cached for 60 seconds)."""
    from datetime import datetime as _dt
    now = _dt.now()
    cached = get_cached_settings()
    cached_time = get_cache_time()
    if cached and cached_time and (now - cached_time).seconds < 60:
        return cached
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(SiteSetting))
            data = {s.key: s.value for s in result.scalars().all() if s.value}
            set_cache(data, now)
    except Exception:
        pass
    return get_cached_settings()


async def render(template_name: str, request: Request, **context) -> HTMLResponse:
    template = env.get_template(template_name)
    # Merge site settings into context so footer can use them
    merged = dict(context)
    merged['site_settings'] = await _get_site_settings()
    merged['config'] = config
    html = template.render(
        request=request,
        url_for=url_for,
        current_user=_anonymous,
        get_flashed_messages=lambda with_categories=False: [],
        **merged,
    )
    return HTMLResponse(html)


async def _check_admin_auth(request: Request) -> Optional[int]:
    """Check admin authentication from cookie. Returns user_id or None."""
    token = request.cookies.get('admin_token')
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    try:
        async with async_session_maker() as db:
            user = await db.execute(select(User).where(User.id == int(user_id), User.is_active == True))
            user = user.scalar_one_or_none()
            if user and user.is_admin:
                return user.id
    except Exception:
        pass
    return None


pages = APIRouter()


@pages.get("/", response_class=HTMLResponse)
async def home(request: Request):
    categories = []
    featured_products = []
    banners = []
    testimonials = []
    promotions = []
    try:
        async with async_session_maker() as db:
            from app.services.promotions_service import get_active_promotions, product_sale_info
            promotions = await get_active_promotions(db)
            cats = await db.execute(select(Category).order_by(Category.name))
            categories = cats.scalars().all()
            feat = await db.execute(
                select(Product, Category, Brand)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .join(Brand, Product.brand_id == Brand.id, isouter=True)
                .where(Product.is_featured == True, Product.status == 'active')
                .order_by(Product.created_at.desc()).limit(8)
            )
            for row in feat.all():
                p = row.Product
                imgs = [img.image_url for img in (p.images or [])]
                sale_price, sale_pct = product_sale_info(promotions, p)
                featured_products.append({
                    "id": p.id, "name": p.name, "slug": p.slug,
                    "price": p.price, "discount_price": p.discount_price,
                    "sale_price": sale_price, "sale_pct": sale_pct,
                    "stock": p.stock, "image": imgs[0] if imgs else "",
                    "category": row.Category.name if row.Category else "",
                    "brand": row.Brand.name if row.Brand else "",
                })
            ban_res = await db.execute(
                select(HeroBanner)
                .where(HeroBanner.is_active == True)
                .order_by(HeroBanner.position, HeroBanner.created_at.desc())
            )
            for b in ban_res.scalars().all():
                banners.append({
                    "id": b.id, "title": b.title, "subtitle": b.subtitle or "",
                    "image_url": b.image_url or "",
                    "desktop_image_url": b.desktop_image_url or "",
                    "tablet_image_url": b.tablet_image_url or "",
                    "mobile_image_url": b.mobile_image_url or "",
                    "link_url": b.link_url or "/shop",
                    "button_text": b.button_text or "Shop Now",
                })
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Home route error: %s", exc)
    return await render("index.html", request,
                   categories=categories,
                   featured_products=featured_products,
                   banners=banners,
                   promotions=promotions)


@pages.get("/shop", response_class=HTMLResponse)
async def shop(request: Request):
    products = []
    categories = []
    brands = []
    try:
        async with async_session_maker() as db:
            from app.services.promotions_service import get_active_promotions, product_sale_info
            promos = await get_active_promotions(db)
            cats = await db.execute(select(Category).order_by(Category.name))
            categories = cats.scalars().all()
            brs = await db.execute(select(Brand).order_by(Brand.name))
            brands = brs.scalars().all()
            prods = await db.execute(
                select(Product, Category, Brand)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .join(Brand, Product.brand_id == Brand.id, isouter=True)
                .where(Product.status == 'active')
                .order_by(Product.created_at.desc()).limit(50)
            )
            for row in prods.all():
                p = row.Product
                imgs = [img.image_url for img in (p.images or [])]
                sale_price, sale_pct = product_sale_info(promos, p)
                products.append({
                    "id": p.id, "name": p.name, "slug": p.slug,
                    "price": p.price, "discount_price": p.discount_price,
                    "sale_price": sale_price, "sale_pct": sale_pct,
                    "stock": p.stock, "image": imgs[0] if imgs else "",
                    "category_id": p.category_id,
                    "category": row.Category.name if row.Category else "",
                    "brand_id": p.brand_id,
                    "brand": row.Brand.name if row.Brand else "",
                })
    except Exception:
        pass
    return await render("shop/index.html", request,
                   products=products, categories=categories, brands=brands)


@pages.get("/product/{slug}", response_class=HTMLResponse)
async def product(request: Request, slug: str):
    product_data = None
    related = []
    product_promos = []
    try:
        async with async_session_maker() as db:
            from app.services.promotions_service import get_active_promotions, product_sale_info
            promos = await get_active_promotions(db)
            result = await db.execute(
                select(Product, Category, Brand)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .join(Brand, Product.brand_id == Brand.id, isouter=True)
                .where(Product.slug == slug, Product.status == 'active')
            )
            row = result.first()
            if row:
                p = row.Product
                imgs = [img.image_url for img in (p.images or [])]
                attrs = [{"name": a.name, "value": a.value} for a in (p.attributes or [])]
                variants = [{"id": v.id, "name": v.name, "sku": v.sku, "price_modifier": v.price_modifier, "stock": v.stock} for v in (p.variants or [])]
                reviews = [{"rating": r.rating, "comment": r.comment, "created_at": r.created_at} for r in (p.reviews or [])]
                sale_price, sale_pct = product_sale_info(promos, p)
                product_data = {
                    "id": p.id, "name": p.name, "slug": p.slug, "sku": p.sku,
                    "description": p.description or "",
                    "price": p.price, "discount_price": p.discount_price,
                    "sale_price": sale_price, "sale_pct": sale_pct,
                    "stock": p.stock, "is_featured": p.is_featured,
                    "images": imgs, "image": imgs[0] if imgs else "",
                    "category": row.Category.name if row.Category else "",
                    "category_slug": row.Category.slug if row.Category else "",
                    "brand": row.Brand.name if row.Brand else "",
                    "attributes": attrs, "variants": variants, "reviews": reviews,
                }
                product_promos = [pr for pr in promos
                                  if pr.promotion_type == 'percent_off'
                                  and (pr.scope == 'storewide'
                                       or (pr.scope == 'category' and pr.category_id == p.category_id)
                                       or (pr.scope == 'product' and (pr.product_id == p.id or (pr.product_ids and p.id in pr.product_ids))))]
                rel = await db.execute(
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.status == 'active', Product.id != p.id)
                    .order_by(Product.created_at.desc()).limit(4)
                )
                for rr in rel.all():
                    rp = rr.Product
                    rims = [img.image_url for img in (rp.images or [])]
                    r_sale, r_pct = product_sale_info(promos, rp)
                    related.append({
                        "id": rp.id, "name": rp.name, "slug": rp.slug,
                        "price": rp.price, "discount_price": rp.discount_price,
                        "sale_price": r_sale, "sale_pct": r_pct,
                        "image": rims[0] if rims else "",
                        "category": rr.Category.name if rr.Category else "",
                    })
    except Exception:
        pass
    if not product_data:
        return await render("404.html", request)
    return await render("shop/product.html", request, product=product_data, related=related, product_promos=product_promos)


@pages.get("/deals", response_class=HTMLResponse)
async def deals(request: Request):
    deals = []
    try:
        async with async_session_maker() as db:
            from app.services.promotions_service import get_active_promotions, product_sale_info
            promos = await get_active_promotions(db)
            for pr in promos:
                prods = []
                if pr.scope == 'product':
                    ids = []
                    if pr.product_id:
                        ids.append(pr.product_id)
                    if pr.product_ids:
                        ids.extend(pr.product_ids)
                    if ids:
                        res = await db.execute(
                            select(Product, Category, Brand)
                            .join(Category, Product.category_id == Category.id, isouter=True)
                            .join(Brand, Product.brand_id == Brand.id, isouter=True)
                            .where(Product.status == 'active', Product.id.in_(list(dict.fromkeys(ids))))
                        )
                        for r in res.all():
                            imgs = [i.image_url for i in (r.Product.images or [])]
                            sale, pct = product_sale_info(promos, r.Product)
                            prods.append({"id": r.Product.id, "name": r.Product.name, "slug": r.Product.slug,
                                          "price": r.Product.price, "discount_price": r.Product.discount_price,
                                          "sale_price": sale, "sale_pct": pct,
                                          "image": imgs[0] if imgs else "",
                                          "category": r.Category.name if r.Category else ""})
                elif pr.scope == 'category' and pr.category_id:
                    res = await db.execute(
                        select(Product, Category, Brand)
                        .join(Category, Product.category_id == Category.id, isouter=True)
                        .join(Brand, Product.brand_id == Brand.id, isouter=True)
                        .where(Product.status == 'active', Product.category_id == pr.category_id)
                        .order_by(Product.created_at.desc()).limit(8)
                    )
                    for r in res.all():
                        imgs = [i.image_url for i in (r.Product.images or [])]
                        sale, pct = product_sale_info(promos, r.Product)
                        prods.append({"id": r.Product.id, "name": r.Product.name, "slug": r.Product.slug,
                                      "price": r.Product.price, "discount_price": r.Product.discount_price,
                                      "sale_price": sale, "sale_pct": pct,
                                      "image": imgs[0] if imgs else "",
                                      "category": r.Category.name if r.Category else ""})
                else:
                    res = await db.execute(
                        select(Product, Category, Brand)
                        .join(Category, Product.category_id == Category.id, isouter=True)
                        .join(Brand, Product.brand_id == Brand.id, isouter=True)
                        .where(Product.status == 'active')
                        .order_by(Product.created_at.desc()).limit(8)
                    )
                    for r in res.all():
                        imgs = [i.image_url for i in (r.Product.images or [])]
                        sale, pct = product_sale_info(promos, r.Product)
                        prods.append({"id": r.Product.id, "name": r.Product.name, "slug": r.Product.slug,
                                      "price": r.Product.price, "discount_price": r.Product.discount_price,
                                      "sale_price": sale, "sale_pct": pct,
                                      "image": imgs[0] if imgs else "",
                                      "category": r.Category.name if r.Category else ""})
                deals.append({
                    "id": pr.id,
                    "name": pr.name,
                    "description": pr.description or "",
                    "promotion_type": pr.promotion_type,
                    "scope": pr.scope,
                    "discount_value": pr.discount_value,
                    "discount_amount": pr.discount_amount,
                    "min_spend": pr.min_spend,
                    "buy_qty": pr.buy_qty,
                    "get_qty": pr.get_qty,
                    "start_date": pr.start_date,
                    "end_date": pr.end_date,
                    "products": prods,
                })
    except Exception:
        pass
    return await render("deals.html", request, deals=deals)


@pages.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    return await render("cart/index.html", request)


@pages.get("/checkout", response_class=HTMLResponse)
async def checkout(request: Request):
    return await render("checkout/index.html", request)


@pages.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return await render("auth/login.html", request)


@pages.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return await render("auth/forgot_password.html", request)


@pages.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    return await render("auth/reset_password.html", request, token=token)


@pages.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return await render("auth/register.html", request)


@pages.get("/logout", response_class=HTMLResponse)
async def logout_page(request: Request):
    return RedirectResponse(url="/", status_code=302)


@pages.get("/customer/dashboard", response_class=HTMLResponse)
async def customer_dashboard(request: Request):
    return await render("customer/dashboard.html", request)


@pages.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        async with async_session_maker() as db:
            from datetime import datetime as _dt
            today = _dt.utcnow().date()
            start_of_today = _dt(today.year, today.month, today.day)
            start_of_month = _dt(today.year, today.month, 1)

            revenue_today = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= start_of_today))).scalar_one()
            revenue_month = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= start_of_month))).scalar_one()
            orders_today = (await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= start_of_today))).scalar_one()
            orders_month = (await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= start_of_month))).scalar_one()

            yesterday = today - timedelta(days=1)
            start_of_yesterday = _dt(yesterday.year, yesterday.month, yesterday.day)
            revenue_yesterday = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= start_of_yesterday, Order.created_at < start_of_today))).scalar_one()

            if today.month == 1:
                last_month_start = _dt(today.year - 1, 12, 1)
            else:
                last_month_start = _dt(today.year, today.month - 1, 1)
            revenue_last_month = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.created_at >= last_month_start, Order.created_at < start_of_month))).scalar_one()

            # Order status counts
            delivered_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == 'Delivered'))).scalar_one()

            # Recent orders
            recent_orders = (await db.execute(
                select(Order, User).join(User, Order.user_id == User.id, isouter=True)
                .order_by(Order.created_at.desc()).limit(5)
            )).all()
            recent_orders_data = [
                {"id": o.Order.id, "order_number": o.Order.order_number, "status": o.Order.status,
                 "total_amount": o.Order.total_amount, "customer": o.User, "created_at": o.Order.created_at}
                for o in recent_orders
            ]

            # Top products
            top_products = (await db.execute(
                select(Product).order_by(Product.stock.desc()).limit(5)
            )).scalars().all()

            # Revenue analytics (last 12 months)
            revenue_data = []
            now = datetime.now()
            for i in range(11, -1, -1):
                month_date = now.replace(day=1) - timedelta(days=i*30)
                month_start = month_date.replace(day=1)
                if month_date.month == 12:
                    month_end = month_date.replace(year=month_date.year+1, month=1, day=1)
                else:
                    month_end = month_date.replace(month=month_date.month+1, day=1)
                stmt = select(func.sum(Order.total_amount)).where(
                    Order.status != 'cancelled',
                    Order.created_at >= month_start,
                    Order.created_at < month_end
                )
                result = await db.execute(stmt)
                value = float(result.scalar() or 0)
                revenue_data.append({"label": month_start.strftime("%b %Y"), "value": value})
            
            # Category sales data
            category_stmt = (
                select(Category.name, func.sum(OrderItem.quantity * OrderItem.price).label("total"))
                .join(Product, OrderItem.product_id == Product.id)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .group_by(Category.name)
                .order_by(text("total DESC"))
                .limit(5)
            )
            category_result = await db.execute(category_stmt)
            category_rows = category_result.fetchall()
            category_data = [{"name": row[0] or "Unknown", "value": float(row[1])} for row in category_rows]
    except Exception:
        revenue_today, revenue_month = 0, 0
        revenue_yesterday, revenue_last_month = 0, 0
        orders_today, orders_month = 0, 0
        delivered_orders = 0
        recent_orders_data, top_products = [], []
        revenue_data = [{"label": f"Month {i}", "value": 0} for i in range(12)]
        category_data = []

    return await render("admin/dashboard.html", request,
        revenue_today=round(revenue_today, 2),
        revenue_month=round(revenue_month, 2),
        revenue_yesterday=round(revenue_yesterday, 2),
        revenue_last_month=round(revenue_last_month, 2),
        orders_today=orders_today,
        orders_month=orders_month,
        delivered_orders=delivered_orders,
        recent_orders=recent_orders_data,
        top_products=top_products,
        revenue_data=revenue_data,
        category_data=category_data,
    )


@pages.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return await render("admin/login.html", request)


@pages.get("/admin/forgot-password", response_class=HTMLResponse)
async def admin_forgot_password(request: Request):
    return await render("admin/forgot_password.html", request)


@pages.get("/admin/reset-password", response_class=HTMLResponse)
async def admin_reset_password(request: Request, token: str = ""):
    return await render("admin/reset_password.html", request, token=token)


@pages.get("/admin/products", response_class=HTMLResponse)
async def admin_products(request: Request):
    return await render("admin/products/index.html", request)


@pages.get("/admin/products/add", response_class=HTMLResponse)
async def admin_product_add(request: Request):
    return await render("admin/products/add.html", request)


@pages.get("/admin/products/edit/{product_id}", response_class=HTMLResponse)
async def admin_product_edit(request: Request, product_id: int):
    return await render("admin/products/edit.html", request, product_id=product_id)


@pages.get("/admin/categories", response_class=HTMLResponse)
async def admin_categories(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(Category).order_by(Category.name))
            categories = result.scalars().all()
    except Exception:
        categories = []
    return await render("admin/categories.html", request, categories=categories)


@pages.get("/admin/brands", response_class=HTMLResponse)
async def admin_brands(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(Brand).order_by(Brand.name))
            brands = result.scalars().all()
    except Exception:
        brands = []
    return await render("admin/brands.html", request, brands=brands)


@pages.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Order, User).join(User, Order.user_id == User.id, isouter=True).order_by(Order.created_at.desc())
            )
            orders = []
            for row in result.all():
                o = row.Order
                # Get payment info
                pay_result = await db.execute(
                    select(Payment).where(Payment.order_id == o.id).order_by(Payment.created_at.desc()).limit(1)
                )
                payment = pay_result.scalars().first()
                orders.append({
                    "id": o.id,
                    "order_number": o.order_number,
                    "status": o.status,
                    "payment_status": o.payment_status or (payment.status if payment else "N/A"),
                    "total_amount": o.total_amount,
                    "customer": row.User,
                    "created_at": o.created_at,
                    "payment_method": payment.payment_method if payment else None,
                    "payment_id": payment.id if payment else None,
                })
    except Exception:
        orders = []
    return await render("admin/orders.html", request, orders=orders)


@pages.get("/admin/orders/edit/{order_id}", response_class=HTMLResponse)
async def admin_order_edit(request: Request, order_id: int):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/orders?detail={order_id}", status_code=302)


@pages.get("/admin/customers", response_class=HTMLResponse)
async def admin_customers(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.is_admin == False).order_by(User.created_at.desc()))
            customers = result.scalars().all()
    except Exception:
        customers = []
    return await render("admin/customers.html", request, customers=customers)


@pages.get("/admin/notify", response_class=HTMLResponse)
async def admin_notify(request: Request):
    customers = []
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(User).where(User.is_admin == False).order_by(User.created_at.desc())
            )
            customers = result.scalars().all()
    except Exception:
        customers = []
    return await render("admin/notify.html", request, customers=customers)


@pages.get("/admin/reviews", response_class=HTMLResponse)
async def admin_reviews(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(ProductReview, Product, User)
                .join(Product, ProductReview.product_id == Product.id)
                .join(User, ProductReview.user_id == User.id, isouter=True)
                .order_by(ProductReview.created_at.desc())
            )
            reviews = []
            for row in result.all():
                r = row.ProductReview
                reviews.append({
                    "id": r.id,
                    "rating": r.rating,
                    "comment": r.comment,
                    "created_at": r.created_at,
                    "product_name": row.Product.name,
                    "username": row.User.username if row.User else "Guest",
                })
    except Exception:
        reviews = []
    return await render("admin/reviews.html", request, reviews=reviews)


@pages.get("/admin/inventory", response_class=HTMLResponse)
async def admin_inventory(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(ProductVariant, Product)
                .join(Product, ProductVariant.product_id == Product.id)
                .order_by(Product.name, ProductVariant.name)
            )
            variants = []
            for row in result.all():
                v = row.ProductVariant
                variants.append({
                    "id": v.id,
                    "product_name": row.Product.name,
                    "name": v.name,
                    "sku": v.sku,
                    "stock": v.stock,
                    "price_modifier": v.price_modifier,
                })
    except Exception:
        variants = []
    return await render("admin/inventory.html", request, variants=variants)


@pages.get("/admin/payments", response_class=HTMLResponse)
async def admin_payments(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Payment, Order, User)
                .join(Order, Payment.order_id == Order.id)
                .join(User, Order.user_id == User.id, isouter=True)
                .order_by(Payment.created_at.desc())
            )
            payments = []
            for row in result.all():
                p = row.Payment
                payments.append({
                    "id": p.id,
                    "order_number": row.Order.order_number if row.Order else "-",
                    "order_id": p.order_id,
                    "customer_name": f"{row.User.first_name or ''} {row.User.last_name or ''}".strip() if row.User else "Guest",
                    "customer_email": p.customer_email or (row.User.email if row.User else ""),
                    "amount": p.amount,
                    "currency": p.currency or 'GHS',
                    "status": p.status,
                    "payment_method": p.payment_method,
                    "transaction_id": p.transaction_reference or p.paystack_reference or "-",
                    "channel": p.channel or "",
                    "provider": p.provider or "paystack",
                    "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                    "failure_reason": p.failure_reason or "",
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                })
    except Exception:
        payments = []
    return await render("admin/payments.html", request, payments=payments)


@pages.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(SiteSetting).order_by(SiteSetting.key))
            rows = result.scalars().all()
            settings = [{"id": s.id, "key": s.key, "value": s.value or "", "description": s.description or ""} for s in rows]
    except Exception:
        settings = []
    return await render("admin/settings.html", request, settings=settings)


@pages.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(User).order_by(User.created_at.desc()))
            users = result.scalars().all()
    except Exception:
        users = []
    return await render("admin/users.html", request, users=users)


@pages.get("/admin/analytics", response_class=HTMLResponse)
async def admin_analytics(request: Request):
    return await render("admin/analytics.html", request)


@pages.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports(request: Request):
    return await render("admin/reports.html", request)


@pages.get("/admin/homepage", response_class=HTMLResponse)
async def admin_homepage(request: Request):
    return await render("admin/homepage.html", request)


@pages.get("/admin/coupons", response_class=HTMLResponse)
async def admin_coupons(request: Request):
    return await render("admin/coupons.html", request)


@pages.get("/admin/loyalty", response_class=HTMLResponse)
async def admin_loyalty(request: Request):
    return await render("admin/loyalty.html", request)


@pages.get("/admin/promotions", response_class=HTMLResponse)
async def admin_promotions(request: Request):
    return await render("admin/promotions.html", request)


@pages.get("/admin/search", response_class=HTMLResponse)
async def admin_search(request: Request, q: str = ""):
    results = {"products": [], "orders": [], "customers": [], "categories": [], "brands": []}
    if q and q.strip():
        try:
            term = f"%{q.strip()}%"
            async with async_session_maker() as db:
                products = (await db.execute(
                    select(Product).where(or_(Product.name.ilike(term), Product.sku.ilike(term)))
                    .order_by(Product.name).limit(10)
                )).scalars().all()
                orders = (await db.execute(
                    select(Order, User).join(User, Order.user_id == User.id, isouter=True)
                    .where(or_(Order.order_number.ilike(term), User.email.ilike(term)))
                    .order_by(Order.created_at.desc()).limit(10)
                )).all()
                customers = (await db.execute(
                    select(User).where(
                        or_(User.username.ilike(term), User.email.ilike(term), User.first_name.ilike(term))
                    ).order_by(User.username).limit(10)
                )).scalars().all()
                categories = (await db.execute(
                    select(Category).where(or_(Category.name.ilike(term), Category.slug.ilike(term)))
                    .order_by(Category.name).limit(10)
                )).scalars().all()
                brands = (await db.execute(
                    select(Brand).where(or_(Brand.name.ilike(term), Brand.slug.ilike(term)))
                    .order_by(Brand.name).limit(10)
                )).scalars().all()
            results["products"] = products
            results["orders"] = [
                {"id": o.Order.id, "order_number": o.Order.order_number, "status": o.Order.status,
                 "total_amount": o.Order.total_amount, "customer": o.User} for o in orders
            ]
            results["customers"] = customers
            results["categories"] = categories
            results["brands"] = brands
        except Exception:
            pass
    return await render("admin/search.html", request, q=q, results=results)


@pages.get("/order/success", response_class=HTMLResponse)
async def order_success(request: Request):
    return await render("order_success.html", request)


@pages.get("/order/failure", response_class=HTMLResponse)
async def order_failure(request: Request):
    return await render("order_failure.html", request)


@pages.get("/order/invoice", response_class=HTMLResponse)
async def order_invoice(request: Request):
    return await render("invoice.html", request)


@pages.get("/payment/callback", response_class=HTMLResponse)
async def payment_callback(request: Request):
    """Paystack redirect callback - verifies payment and shows result."""
    return await render("payment_callback.html", request)


@pages.get("/payment/failed", response_class=HTMLResponse)
async def payment_failed_page(request: Request):
    """Payment failed/cancelled page."""
    return await render("order_failure.html", request)


@pages.get("/wishlist", response_class=HTMLResponse)
async def wishlist_page(request: Request):
    return await render("wishlist.html", request)


@pages.get("/categories", response_class=HTMLResponse)
async def all_categories(request: Request):
    try:
        async with async_session_maker() as db:
            from sqlalchemy import select as sa_select
            from app.models.catalog import Category
            result = await db.execute(sa_select(Category).order_by(Category.name))
            categories = result.scalars().all()
    except Exception:
        categories = []
    return await render("categories.html", request, categories=categories)


ALL_CATEGORIES = [
    {
        "slug": "bathroom-sanitary", "name": "Bathroom & Sanitary",
        "image": "/static/images/cat_bathroom.png",
        "description": "Premium showers, faucets & accessories for modern bathrooms.",
        "subcategories": ["Shower Systems", "Faucets & Taps", "Wash Basins", "Toilets & Bidets", "Bathtubs", "Bathroom Accessories", "Mirrors & Cabinets", "Water Heaters"],
    },
    {
        "slug": "kitchen-appliances", "name": "Kitchen & Appliances",
        "image": "/static/images/cat_kitchen.png",
        "description": "Modern sinks, faucets, and kitchen appliances for every home.",
        "subcategories": ["Kitchen Sinks", "Kitchen Faucets", "Cooking Ranges", "Microwaves", "Blenders & Mixers", "Refrigerators", "Dishwashers", "Water Purifiers"],
    },
    {
        "slug": "plumbing-fittings", "name": "Plumbing & Fittings",
        "image": "/static/images/cat_plumbing.jpg",
        "description": "Reliable pipes, valves, and connectors for all plumbing needs.",
        "subcategories": ["PVC Pipes", "Copper Pipes", "Valves", "Elbows & Connectors", "Tee Joints", "Pipe Clamps", "Sealants & Tapes", "Fittings"],
    },
    {
        "slug": "tools-equipment", "name": "Tools & Equipment",
        "image": "/static/images/cat_tools.jpg",
        "description": "Professional-grade power tools and hand tools for every project.",
        "subcategories": ["Power Drills", "Wrenches", "Hammers", "Screwdrivers", "Pliers", "Measuring Tools", "Saws", "Tool Sets"],
    },
    {
        "slug": "home-appliances", "name": "Home Appliances",
        "image": "/static/images/cat_home_appliances.jpg",
        "description": "Essential appliances for comfort and convenience at home.",
        "subcategories": ["Fans", "Heaters", "Irons", "Vacuum Cleaners", "Air Conditioners", "Washing Machines", "Dryers", "Dehumidifiers"],
    },
    {
        "slug": "electrical-lighting", "name": "Electrical & Lighting",
        "image": "/static/images/cat_electrical.jpg",
        "description": "Quality wiring, switches, fixtures, and lighting solutions.",
        "subcategories": ["LED Panels", "Ceiling Lights", "Wall Sconces", "Switches & Sockets", "Extension Boards", "Wiring & Cables", "Circuit Breakers", "Solar Panels"],
    },
    {
        "slug": "hardware-building-materials", "name": "Hardware & Building Materials",
        "image": "/static/images/cat_hardware.jpg",
        "description": "Quality materials for construction and renovation projects.",
        "subcategories": ["Screws", "Nails", "Bolts", "Nuts", "Hinges", "Locks", "Door Hardware", "Construction Accessories", "Sealants", "Adhesives", "Building Hardware"],
    },
    {
        "slug": "home-improvement", "name": "Home Improvement",
        "image": "/static/images/cat_home_improvement.jpg",
        "description": "Everything you need to upgrade and enhance your living space.",
        "subcategories": ["Bathroom Renovation", "Kitchen Improvement", "Storage Solutions", "Home Organization", "Fixtures", "Fittings", "Decor", "DIY Products", "Renovation Essentials"],
    },
    {
        "slug": "water-solutions", "name": "Water Solutions",
        "image": "/static/images/cat_water.jpg",
        "description": "Reliable solutions for water supply, management, and treatment.",
        "subcategories": ["Water Pumps", "Water Tanks", "Pressure Pumps", "Filtration Systems", "Water Heaters", "Water Purifiers", "Water Treatment", "Plumbing Systems"],
    },
    {
        "slug": "garden-outdoor", "name": "Garden & Outdoor",
        "image": "/static/images/cat_garden.jpg",
        "description": "Tools and essentials for outdoor living and garden care.",
        "subcategories": ["Garden Tools", "Watering Equipment", "Hoses", "Outdoor Lighting", "Pressure Washers", "Lawn Equipment", "Outdoor Hardware"],
    },
]


@pages.get("/categories/{slug}", response_class=HTMLResponse)
async def category_detail(request: Request, slug: str):
    cat = None
    products = []
    all_cats = []
    try:
        async with async_session_maker() as db:
            cat_result = await db.execute(select(Category).where(Category.slug == slug))
            cat = cat_result.scalars().first()
            if not cat:
                return await render("404.html", request)
            all_cats_result = await db.execute(select(Category).order_by(Category.name))
            all_cats = all_cats_result.scalars().all()
            prods = await db.execute(
                select(Product, Category, Brand)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .join(Brand, Product.brand_id == Brand.id, isouter=True)
                .where(Product.status == 'active', Product.category_id == cat.id)
                .order_by(Product.created_at.desc()).limit(50)
            )
            for row in prods.all():
                p = row.Product
                imgs = [img.image_url for img in (p.images or [])]
                products.append({
                    "id": p.id, "name": p.name, "slug": p.slug,
                    "price": p.price, "discount_price": p.discount_price,
                    "stock": p.stock, "image": imgs[0] if imgs else "",
                    "category": row.Category.name if row.Category else "",
                    "brand": row.Brand.name if row.Brand else "",
                })
    except Exception:
        pass
    return await render("category_detail.html", request, category=cat, products=products, all_categories=all_cats)


@pages.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request):
    return await render("compare.html", request)


@pages.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return await render("about.html", request)


@pages.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return await render("contact.html", request)


@pages.get("/shipping-policy", response_class=HTMLResponse)
async def shipping_policy_page(request: Request):
    return await render("shipping-policy.html", request)


@pages.get("/returns-refunds", response_class=HTMLResponse)
async def returns_refunds_page(request: Request):
    return await render("returns-refunds.html", request)


@pages.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return await render("faq.html", request)


@pages.get("/order-tracking", response_class=HTMLResponse)
async def order_tracking_page(request: Request):
    return await render("order-tracking.html", request)


@pages.get("/payment-security", response_class=HTMLResponse)
async def payment_security_page(request: Request):
    return await render("payment-security.html", request)


@pages.get("/404", response_class=HTMLResponse)
async def not_found_page(request: Request):
    return await render("404.html", request)


@pages.get("/admin/testimonials", response_class=HTMLResponse)
async def admin_testimonials(request: Request):
    return await render("admin/testimonials.html", request)


@pages.get("/admin/banners", response_class=HTMLResponse)
async def admin_banners(request: Request):
    banners = []
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(HeroBanner).order_by(HeroBanner.position, HeroBanner.created_at.desc())
            )
            banners = result.scalars().all()
    except Exception:
        pass
    return await render("admin/banners.html", request, banners=banners)


@pages.get("/admin/blog", response_class=HTMLResponse)
async def admin_blog(request: Request):
    return await render("admin/blog.html", request)


@pages.get("/admin/newsletters", response_class=HTMLResponse)
async def admin_newsletters(request: Request):
    return await render("admin/newsletters.html", request)


@pages.get("/admin/audit-logs", response_class=HTMLResponse)
async def admin_audit_logs(request: Request):
    return await render("admin/audit-logs.html", request)


@pages.get("/admin/system-logs", response_class=HTMLResponse)
async def admin_system_logs(request: Request):
    return await render("admin/system-logs.html", request)


@pages.get("/admin/media", response_class=HTMLResponse)
async def admin_media(request: Request):
    return await render("admin/media.html", request)


@pages.get("/admin/profile", response_class=HTMLResponse)
async def admin_profile_page(request: Request):
    return await render("admin/profile.html", request)


@pages.get("/admin/preferences", response_class=HTMLResponse)
async def admin_preferences_page(request: Request):
    return await render("admin/preferences.html", request)


@pages.get("/admin/security", response_class=HTMLResponse)
async def admin_security_page(request: Request):
    return await render("admin/security.html", request)


@pages.get("/admin/activity", response_class=HTMLResponse)
async def admin_activity_page(request: Request):
    return await render("admin/activity.html", request)


@pages.get("/admin/notifications", response_class=HTMLResponse)
async def admin_notifications_page(request: Request):
    return await render("admin/notifications.html", request)


@pages.get("/admin/messages", response_class=HTMLResponse)
async def admin_messages_page(request: Request):
    return await render("admin/messages.html", request)


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.PROJECT_NAME,
        version="2.0.0",
    )

    # ─── Settings Cache Refresh Middleware ────────────────────────────────
    from starlette.middleware.base import BaseHTTPMiddleware

    class SettingsCacheMiddleware(BaseHTTPMiddleware):
        """Auto-refresh site settings cache when empty."""
        async def dispatch(self, request, call_next):
            from app.settings_cache import is_cache_empty
            if is_cache_empty():
                await _get_site_settings()
            return await call_next(request)

    app.add_middleware(SettingsCacheMiddleware)

    # ─── Maintenance Mode Middleware ─────────────────────────────────

    class MaintenanceModeMiddleware(BaseHTTPMiddleware):
        """Block storefront when maintenance mode is enabled. Admin and API routes pass through."""
        async def dispatch(self, request, call_next):
            path = request.url.path
            if path.startswith('/admin') or path.startswith('/api') or path.startswith('/static'):
                return await call_next(request)
            try:
                from app.settings_cache import get_cached_settings, is_cache_empty
                if is_cache_empty():
                    await _get_site_settings()
                settings = get_cached_settings()
                if settings and settings.get('maintenance_mode') == 'true':
                    msg = settings.get('maintenance_message', '')
                    socials = {
                        'facebook': settings.get('social_facebook', ''),
                        'instagram': settings.get('social_instagram', ''),
                        'twitter': settings.get('social_twitter', ''),
                        'tiktok': settings.get('social_tiktok', ''),
                        'whatsapp': settings.get('social_whatsapp', ''),
                    }
                    template = env.get_template('maintenance.html')
                    html = template.render(
                        request=request,
                        message=msg,
                        **socials,
                    )
                    from starlette.responses import HTMLResponse as StarletteHTMLResponse
                    return StarletteHTMLResponse(content=html)
            except Exception:
                import traceback, logging
                logging.getLogger(__name__).error('MaintenanceModeMiddleware error: %s', traceback.format_exc())
            return await call_next(request)

    app.add_middleware(MaintenanceModeMiddleware)

    # ─── Admin Auth Middleware ─────────────────────────────────────────
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import RedirectResponse as StarletteRedirect

    class AdminAuthMiddleware(BaseHTTPMiddleware):
        """Protect all /admin routes except auth pages."""
        EXEMPT_PATHS = {
            '/admin/login',
            '/admin/forgot-password',
            '/admin/reset-password',
        }

        async def dispatch(self, request: StarletteRequest, call_next):
            path = request.url.path
            # Only protect /admin routes
            if path.startswith('/admin') and path not in self.EXEMPT_PATHS:
                # Skip API routes (they handle their own auth)
                if path.startswith('/api/'):
                    return await call_next(request)
                # Skip static files
                if path.startswith('/static/'):
                    return await call_next(request)

                token = request.cookies.get('admin_token')
                if not token:
                    redirect_url = f"/admin/login?redirect={path}"
                    return StarletteRedirect(url=redirect_url, status_code=302)

                user_id = decode_access_token(token)
                if not user_id:
                    resp = StarletteRedirect(url="/admin/login", status_code=302)
                    resp.delete_cookie('admin_token')
                    return resp

                # Verify user exists and is admin
                try:
                    async with async_session_maker() as db:
                        user = await db.execute(
                            select(User).where(User.id == int(user_id), User.is_active == True)
                        )
                        user = user.scalar_one_or_none()
                        if not user or not user.is_admin:
                            resp = StarletteRedirect(url="/admin/login", status_code=302)
                            resp.delete_cookie('admin_token')
                            return resp
                except Exception:
                    return StarletteRedirect(url="/admin/login", status_code=302)

            return await call_next(request)

    app.add_middleware(AdminAuthMiddleware)

    app.add_middleware(
        __import__("fastapi.middleware.cors", fromlist=["CORSMiddleware"]).CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    from app.middleware.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(app)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    api_prefix = config.API_PREFIX or "/api"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(products.router, prefix=api_prefix)
    app.include_router(categories.router, prefix=api_prefix)
    app.include_router(brands.router, prefix=api_prefix)
    app.include_router(cart.router, prefix=api_prefix)
    app.include_router(orders.router, prefix=api_prefix)
    app.include_router(customers.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)
    app.include_router(coupons.router, prefix=api_prefix)
    app.include_router(wishlists.router, prefix=api_prefix)
    app.include_router(testimonials.router, prefix=api_prefix)
    app.include_router(hero_banners.router, prefix=api_prefix)
    app.include_router(blog.router, prefix=api_prefix)
    app.include_router(newsletters.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(collections.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)
    app.include_router(content.router, prefix=api_prefix)
    app.include_router(reviews.router, prefix=api_prefix)
    app.include_router(messages_api.router, prefix=api_prefix)
    app.include_router(search_api.router, prefix=api_prefix)
    app.include_router(admin_profile.router, prefix=api_prefix)
    app.include_router(reports_api.router, prefix=api_prefix)
    app.include_router(auth_extended.router, prefix=api_prefix)
    app.include_router(media_api.router, prefix=api_prefix)
    app.include_router(payments_api.router, prefix=api_prefix)
    app.include_router(loyalty.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(email_admin.router, prefix=api_prefix)
    app.include_router(promotions_api.router, prefix=api_prefix)

    app.include_router(pages)

    @app.on_event("startup")
    async def _startup():
        try:
            await init_db()
        except Exception as e:
            print(f"Warning: Database not available ({e}). Running in offline mode.")
        try:
            await _get_site_settings()
        except Exception:
            pass
        # Start email background worker
        try:
            from app.services.email_service import start_email_worker, retry_failed_emails
            await start_email_worker()
            await retry_failed_emails()
        except Exception:
            pass

    @app.on_event("shutdown")
    async def _shutdown():
        try:
            from app.services.email_service import stop_email_worker
            await stop_email_worker()
        except Exception:
            pass
        try:
            await dispose_engine()
        except Exception:
            pass

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
