"""Content management REST API - homepage data and site settings."""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import HeroBanner, Product, ProductImage, Testimonial, SiteSetting

router = APIRouter(prefix='/content', tags=['Content'])


class BannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    position: int


class FeaturedProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    price: float
    discount_price: Optional[float] = None
    image_url: Optional[str] = None


class TestimonialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_name: str
    customer_title: Optional[str] = None
    content: str
    rating: int


class HomepageOut(BaseModel):
    banners: List[BannerOut]
    featured_products: List[FeaturedProductOut]
    testimonials: List[TestimonialOut]


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: Optional[str] = None
    description: Optional[str] = None


@router.get('/homepage', response_model=HomepageOut)
async def get_homepage(db: AsyncSession = Depends(get_db)):
    banners_result = await db.execute(
        select(HeroBanner)
        .where(HeroBanner.is_active == True)  # noqa: E712
        .order_by(HeroBanner.position)
        .limit(5)
    )
    banners = banners_result.scalars().all()

    products_result = await db.execute(
        select(Product)
        .where(Product.is_featured == True, Product.status == 'active')  # noqa: E712
        .order_by(Product.created_at.desc())
        .limit(8)
    )
    products = products_result.scalars().all()

    featured = []
    for p in products:
        img_url = None
        for img in (p.images or []):
            if img.is_primary:
                img_url = img.image_url
                break
        if not img_url and p.images:
            img_url = p.images[0].image_url
        featured.append(FeaturedProductOut(
            id=p.id, name=p.name, slug=p.slug,
            price=p.price, discount_price=p.discount_price,
            image_url=img_url,
        ))

    testimonials_result = await db.execute(
        select(Testimonial)
        .where(Testimonial.is_active == True, Testimonial.is_featured == True)  # noqa: E712
        .order_by(Testimonial.created_at.desc())
        .limit(6)
    )
    testimonials = testimonials_result.scalars().all()

    return HomepageOut(
        banners=[BannerOut.model_validate(b) for b in banners],
        featured_products=featured,
        testimonials=[TestimonialOut.model_validate(t) for t in testimonials],
    )


@router.get('/settings', response_model=List[SettingOut])
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    # Only return non-sensitive, public-facing settings
    PUBLIC_KEYS = {
        'store_name', 'store_description', 'store_email', 'store_phone',
        'store_address', 'store_logo', 'store_favicon', 'currency',
        'currency_symbol', 'tax_rate', 'shipping_fee',
        'contact_email', 'contact_phone', 'contact_address',
        'social_facebook', 'social_instagram', 'social_twitter', 'social_tiktok',
        'maintenance_mode', 'maintenance_message',
        'about_mission_image', 'about_team_ceo_image', 'about_team_ops_image',
        'about_team_marketing_image', 'about_team_success_image',
        'hero_title', 'hero_subtitle', 'hero_image',
        'meta_title', 'meta_description', 'meta_keywords',
        'seo_meta_title', 'seo_meta_description',
    }
    result = await db.execute(select(SiteSetting).where(SiteSetting.key.in_(PUBLIC_KEYS)).order_by(SiteSetting.key))
    settings = result.scalars().all()
    return [SettingOut.model_validate(s) for s in settings]
