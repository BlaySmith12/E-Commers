"""Pydantic schemas (request/response models) for the REST API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'UserOut'


class LoginRequest(BaseModel):
    # Accepts either email or username in the "username" field (OAuth2 form style)
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6)
    confirm_password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


# ---------------------------------------------------------------------------
# User / Role / Address
# ---------------------------------------------------------------------------
class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    default: bool
    permissions: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool
    role: Optional[RoleOut] = None
    created_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class AddressBase(BaseModel):
    street: str
    city: str
    state: Optional[str] = None
    country: str = 'Ghana'
    zip_code: Optional[str] = None
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(AddressBase):
    pass


class AddressOut(AddressBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    banner_url: Optional[str] = None
    icon_url: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    banner_url: Optional[str] = None
    icon_url: Optional[str] = None


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BrandBase(BaseModel):
    name: str
    slug: str
    image_url: Optional[str] = None
    cover_url: Optional[str] = None


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    image_url: Optional[str] = None
    cover_url: Optional[str] = None


class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductImageIn(BaseModel):
    image_url: str
    is_primary: bool = False
    alt_text: Optional[str] = None


class ProductVariantIn(BaseModel):
    name: str
    sku: Optional[str] = None
    price_modifier: float = 0.0
    stock: int = 0


class ProductAttributeIn(BaseModel):
    name: str
    value: str


class ProductBase(BaseModel):
    name: str
    sku: str
    slug: str
    price: float = Field(gt=0)
    discount_price: Optional[float] = None
    stock: int = 0
    description: Optional[str] = None
    is_featured: bool = False
    is_trending: bool = False
    status: str = 'active'
    category_id: Optional[int] = None
    brand_id: Optional[int] = None


class ProductCreate(ProductBase):
    images: List[ProductImageIn] = []
    variants: List[ProductVariantIn] = []
    attributes: List[ProductAttributeIn] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    slug: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    is_featured: Optional[bool] = None
    is_trending: Optional[bool] = None
    status: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_url: str
    is_primary: bool
    alt_text: Optional[str] = None


class ProductVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: Optional[str] = None
    price_modifier: float
    stock: int


class ProductAttributeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    value: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    name: str
    slug: str
    description: Optional[str] = None
    price: float
    discount_price: Optional[float] = None
    effective_price: Optional[float] = None
    stock: int
    is_featured: bool
    is_trending: bool
    status: str
    created_at: Optional[datetime] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    images: List[ProductImageOut] = []
    variants: List[ProductVariantOut] = []
    attributes: List[ProductAttributeOut] = []


class ProductListOut(ProductOut):
    """Same as ProductOut (images/variants included)."""

    pass


# ---------------------------------------------------------------------------
# Cart & Checkout
# ---------------------------------------------------------------------------
class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemOut(BaseModel):
    product_id: int
    name: str
    slug: str
    quantity: int
    unit_price: float
    original_price: float
    discount_price: Optional[float] = None
    line_total: float
    image_url: Optional[str] = None
    stock: int
    sku: str
    brand: Optional[str] = None
    category: Optional[str] = None


class CartOut(BaseModel):
    items: List[CartItemOut]
    subtotal: float
    item_count: int
    discount: float = 0.0
    coupon_code: Optional[str] = None
    shipping_fee: float = 0.0
    tax: float = 0.0
    total: float = 0.0


class CheckoutIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_id: Optional[int] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = 'Ghana'
    zip_code: Optional[str] = None
    payment_method: str = 'Cash on Delivery'
    shipping_fee: float = 0.0
    tax: float = 0.0
    coupon_code: Optional[str] = None
    points_used: int = 0
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quantity: int
    price: float
    product_id: int
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    product_slug: Optional[str] = None
    product_sku: Optional[str] = None
    product_brand: Optional[str] = None
    product_variant: Optional[str] = None
    line_total: Optional[float] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: Optional[str] = None
    transaction_reference: Optional[str] = None
    amount: float
    currency: Optional[str] = 'GHS'
    status: str
    payment_method: Optional[str] = None
    channel: Optional[str] = None
    customer_email: Optional[str] = None
    paid_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class PaymentInitOut(BaseModel):
    status: bool
    message: str
    authorization_url: Optional[str] = None
    access_code: Optional[str] = None
    reference: Optional[str] = None
    payment_id: Optional[int] = None
    order_id: Optional[int] = None


class CustomerBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quantity: int
    price: float
    product_id: Optional[int] = None
    snapshot_name: Optional[str] = None
    snapshot_image: Optional[str] = None
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    product_slug: Optional[str] = None
    product_brand: Optional[str] = None
    product_sku: Optional[str] = None


class PaymentBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    channel: Optional[str] = None
    provider: Optional[str] = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    status: str
    payment_status: Optional[str] = None
    currency: Optional[str] = 'GHS'
    discount: float = 0.0
    subtotal: float
    shipping_fee: float
    tax: float
    total_amount: float
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[OrderItemOut] = []
    payment: Optional[PaymentBriefOut] = None
    customer: Optional[CustomerBrief] = None
    shipping_address: Optional[AddressOut] = None
    payment_method: Optional[str] = None
    user_id: Optional[int] = None


class OrderStatusUpdate(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------
class MessageOut(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Coupons
# ---------------------------------------------------------------------------
class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = 'percentage'  # percentage, fixed
    discount_value: float
    min_order_amount: float = 0.0
    max_uses: int = 0
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    min_order_amount: float
    max_uses: int
    used_count: int
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponValidate(BaseModel):
    code: str
    cart_total: float


# ---------------------------------------------------------------------------
# Testimonials
# ---------------------------------------------------------------------------
class TestimonialCreate(BaseModel):
    customer_name: str
    customer_title: Optional[str] = None
    content: str
    rating: int = 5
    is_featured: bool = False
    is_active: bool = True


class TestimonialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_name: str
    customer_title: Optional[str] = None
    content: str
    rating: int
    is_featured: bool


# ---------------------------------------------------------------------------
# Hero Banners
# ---------------------------------------------------------------------------
class HeroBannerCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    desktop_image_url: Optional[str] = None
    tablet_image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    secondary_button_url: Optional[str] = None
    position: int = 0
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    open_new_tab: bool = False


class HeroBannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    desktop_image_url: Optional[str] = None
    tablet_image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    secondary_button_url: Optional[str] = None
    position: int
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    open_new_tab: bool = False
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Blog Posts
# ---------------------------------------------------------------------------
class BlogPostCreate(BaseModel):
    title: str
    slug: str
    content: Optional[str] = None
    excerpt: Optional[str] = None
    image_url: Optional[str] = None
    is_published: bool = False


class BlogPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    slug: str
    content: Optional[str] = None
    excerpt: Optional[str] = None
    image_url: Optional[str] = None
    is_published: bool
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
class CollectionCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    message: Optional[str] = None
    type: str
    is_read: bool
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------
class NewsletterSubscribe(BaseModel):
    email: EmailStr


# Resolve forward references
Token.model_rebuild()
