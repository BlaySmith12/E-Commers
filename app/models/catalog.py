"""SQLAlchemy async models for the e-commerce platform.

All models inherit from ``app.db.Base`` (DeclarativeBase) and use the
async SQLAlchemy 2.0 style. Password hashing is delegated to the security
module to avoid coupling models to the web framework.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Permissions (bit-flags) for Role model
# ---------------------------------------------------------------------------
class Permission:
    VIEW = 1
    CREATE = 2
    EDIT = 4
    DELETE = 8
    ADMIN = 16
    ALL = 0xFF


# ---------------------------------------------------------------------------
# User / Role / Address
# ---------------------------------------------------------------------------
class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    default = Column(Boolean, default=False, index=True)
    permissions = Column(Integer, default=0)

    users = relationship('User', back_populates='role', lazy='select')

    def has_permission(self, perm: int) -> bool:
        return bool(self.permissions & perm)

    def __repr__(self) -> str:
        return f'<Role {self.name}>'


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(256), unique=True, index=True, nullable=False)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256))
    first_name = Column(String(64))
    last_name = Column(String(64))
    phone = Column(String(20))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    role_id = Column(Integer, ForeignKey('roles.id'))
    preferences = Column(JSON, default=dict)
    two_factor_enabled = Column(Boolean, default=False)
    last_login = Column(DateTime)
    last_login_ip = Column(String(45))

    created_at = Column(DateTime, default=utcnow)

    role = relationship('Role', back_populates='users', lazy='joined')
    addresses = relationship(
        'Address', back_populates='user', lazy='select',
        cascade='all, delete-orphan',
    )
    orders = relationship('Order', back_populates='customer', lazy='select')
    reviews = relationship('ProductReview', back_populates='user', lazy='select')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password: str):
        from app.security import hash_password
        self.password_hash = hash_password(password)

    def verify_password(self, password: str) -> bool:
        from app.security import verify_password
        return verify_password(password, self.password_hash)

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.has_permission(Permission.ADMIN)

    def __repr__(self) -> str:
        return f'<User {self.username}>'


class Address(Base):
    __tablename__ = 'addresses'

    id = Column(Integer, primary_key=True)
    street = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    country = Column(String(100), default='Ghana')
    zip_code = Column(String(20))
    is_default = Column(Boolean, default=False)

    user_id = Column(Integer, ForeignKey('users.id'))

    user = relationship('User', back_populates='addresses', lazy='joined')

    def __repr__(self) -> str:
        return f'<Address {self.id} - {self.city}>'


# ---------------------------------------------------------------------------
# Catalog: Category / Brand / Product (+ variants, attributes, images, reviews)
# ---------------------------------------------------------------------------
class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (UniqueConstraint('slug', name='uq_categories_slug'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text)
    image_url = Column(String(500))
    banner_url = Column(String(500))
    icon_url = Column(String(500))

    products = relationship('Product', back_populates='category', lazy='select')

    def __repr__(self) -> str:
        return f'<Category {self.name}>'


class Brand(Base):
    __tablename__ = 'brands'
    __table_args__ = (UniqueConstraint('slug', name='uq_brands_slug'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), nullable=False)
    image_url = Column(String(500))
    cover_url = Column(String(500))

    products = relationship('Product', back_populates='brand', lazy='select')

    def __repr__(self) -> str:
        return f'<Brand {self.name}>'


class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (
        UniqueConstraint('sku', name='uq_products_sku'),
        UniqueConstraint('slug', name='uq_products_slug'),
        Index('ix_products_category_id', 'category_id'),
        Index('ix_products_brand_id', 'brand_id'),
        Index('ix_products_price', 'price'),
    )

    id = Column(Integer, primary_key=True)
    sku = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    discount_price = Column(Float)
    stock = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_trending = Column(Boolean, default=False)
    status = Column(String(20), default='active')  # active, draft, archived
    created_at = Column(DateTime, default=utcnow)

    category_id = Column(Integer, ForeignKey('categories.id'))
    brand_id = Column(Integer, ForeignKey('brands.id'))

    category = relationship('Category', back_populates='products', lazy='joined')
    brand = relationship('Brand', back_populates='products', lazy='joined')
    images = relationship(
        'ProductImage', back_populates='product', lazy='selectin',
        cascade='all, delete-orphan',
    )
    reviews = relationship(
        'ProductReview', back_populates='product', lazy='selectin',
        cascade='all, delete-orphan',
    )
    variants = relationship(
        'ProductVariant', back_populates='product', lazy='selectin',
        cascade='all, delete-orphan',
    )
    attributes = relationship(
        'ProductAttribute', back_populates='product', lazy='selectin',
        cascade='all, delete-orphan',
    )

    @property
    def effective_price(self) -> float:
        return self.discount_price if self.discount_price else self.price

    def __repr__(self) -> str:
        return f'<Product {self.name}>'


class ProductVariant(Base):
    __tablename__ = 'product_variants'
    __table_args__ = (UniqueConstraint('sku', name='uq_product_variants_sku'),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    name = Column(String(100), nullable=False)  # e.g. "Color: Red, Size: M"
    sku = Column(String(50))
    price_modifier = Column(Float, default=0.0)
    stock = Column(Integer, default=0)

    product = relationship('Product', back_populates='variants', lazy='selectin')


class ProductAttribute(Base):
    __tablename__ = 'product_attributes'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    name = Column(String(100), nullable=False)   # e.g. "Material"
    value = Column(String(255), nullable=False)  # e.g. "Stainless Steel"

    product = relationship('Product', back_populates='attributes', lazy='selectin')


class ProductImage(Base):
    __tablename__ = 'product_images'

    id = Column(Integer, primary_key=True)
    image_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    is_primary = Column(Boolean, default=False)
    alt_text = Column(String(255))
    sort_order = Column(Integer, default=0)
    file_size = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    product_id = Column(Integer, ForeignKey('products.id'))

    product = relationship('Product', back_populates='images', lazy='selectin')


class ProductReview(Base):
    __tablename__ = 'product_reviews'
    __table_args__ = (Index('ix_product_reviews_product_id', 'product_id'),)

    id = Column(Integer, primary_key=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    product_id = Column(Integer, ForeignKey('products.id'))
    user_id = Column(Integer, ForeignKey('users.id'))

    product = relationship('Product', back_populates='reviews', lazy='selectin')
    user = relationship('User', back_populates='reviews', lazy='selectin')


# ---------------------------------------------------------------------------
# Orders / OrderItems / Payments
# ---------------------------------------------------------------------------
class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        UniqueConstraint('order_number', name='uq_orders_order_number'),
        Index('ix_orders_user_id', 'user_id'),
        Index('ix_orders_created_at', 'created_at'),
    )

    id = Column(Integer, primary_key=True)
    order_number = Column(String(50), nullable=False)
    status = Column(String(50), default='Pending Payment')  # Pending Payment, Payment Processing, Paid, Processing, Shipped, Delivered, Cancelled, Refunded
    payment_status = Column(String(50), default='Pending')  # Pending, Processing, Paid, Failed, Refunded, Abandoned
    currency = Column(String(10), default='GHS')
    discount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user_id = Column(Integer, ForeignKey('users.id'))
    shipping_address_id = Column(Integer, ForeignKey('addresses.id'))

    customer = relationship('User', back_populates='orders', lazy='selectin')
    shipping_address = relationship('Address', lazy='selectin')
    items = relationship(
        'OrderItem', back_populates='order', lazy='selectin',
        cascade='all, delete-orphan',
    )
    payment = relationship(
        'Payment', back_populates='order', lazy='selectin',
        uselist=False, cascade='all, delete-orphan',
    )


class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Float, nullable=False)  # unit price at time of purchase

    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('products.id'))

    # Snapshot fields — preserved at time of purchase
    snapshot_name = Column(String(200))
    snapshot_image = Column(String(255))
    snapshot_slug = Column(String(200))
    snapshot_sku = Column(String(50))
    snapshot_brand = Column(String(100))
    snapshot_variant = Column(String(100))

    order = relationship('Order', back_populates='items', lazy='selectin')
    product = relationship('Product', lazy='selectin')

    @property
    def product_name(self) -> str:
        return self.snapshot_name or (self.product.name if self.product else None)

    @property
    def product_slug(self) -> str:
        return self.snapshot_slug or (self.product.slug if self.product else None)

    @property
    def product_sku(self) -> str:
        return self.snapshot_sku or (self.product.sku if self.product else None)

    @property
    def product_image(self) -> str:
        if self.snapshot_image:
            return self.snapshot_image
        if self.product and self.product.images:
            primary = next((i for i in self.product.images if i.is_primary), None)
            if primary:
                return primary.image_url
            return self.product.images[0].image_url
        return None

    @property
    def product_brand(self) -> str:
        return self.snapshot_brand or (self.product.brand.name if self.product and self.product.brand else None)

    @property
    def product_variant(self) -> str:
        return self.snapshot_variant or None

    @property
    def line_total(self) -> float:
        if self.price is None or self.quantity is None:
            return 0.0
        return round(self.price * self.quantity, 2)


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, index=True)

    # Payment provider
    provider = Column(String(50), default='paystack')  # paystack, cod, etc.
    transaction_reference = Column(String(100), unique=True, index=True)
    access_code = Column(String(200))

    # Amount & currency
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='GHS')

    # Status: Pending, Processing, Completed, Failed, Refunded, Abandoned
    status = Column(String(50), default='Pending', index=True)
    payment_method = Column(String(50))  # card, bank, mobile_money, ussd, cod

    # Paystack-specific
    paystack_reference = Column(String(100), index=True)
    paystack_access_code = Column(String(200))
    channel = Column(String(50))  # card, bank, ussd, mobile_money
    customer_email = Column(String(256))
    ip_address = Column(String(45))

    # Result data
    gateway_response = Column(Text)
    paid_at = Column(DateTime)
    failure_reason = Column(Text)

    # Refund
    refund_reference = Column(String(100))
    refund_amount = Column(Float, default=0.0)
    refund_reason = Column(Text)

    metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    order = relationship('Order', back_populates='payment', lazy='selectin')
    events = relationship(
        'PaymentEvent', back_populates='payment', lazy='selectin',
        cascade='all, delete-orphan',
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SiteSetting(Base):
    __tablename__ = 'site_settings'
    __table_args__ = (UniqueConstraint('key', name='uq_site_settings_key'),)

    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f'<SiteSetting {self.key}>'


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, etc.
    entity_type = Column(String(50), nullable=False, index=True)  # Product, Order, User, etc.
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    user = relationship('User', backref='audit_logs', lazy='select')

    def __repr__(self) -> str:
        return f'<AuditLog {self.action} {self.entity_type}:{self.entity_id}>'


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
class Collection(Base):
    __tablename__ = 'collections'
    __table_args__ = (UniqueConstraint('slug', name='uq_collections_slug'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text)
    image_url = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    products = relationship('Product', secondary='collection_products', backref='collections', lazy='selectin')


class CollectionProduct(Base):
    __tablename__ = 'collection_products'

    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    position = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('collection_id', 'product_id', name='uq_collection_product'),
    )


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------
class Wishlist(Base):
    __tablename__ = 'wishlists'
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uq_wishlist_user_product'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship('User', backref='wishlist_items', lazy='selectin')
    product = relationship('Product', lazy='selectin')


# ---------------------------------------------------------------------------
# Coupons & Promotions
# ---------------------------------------------------------------------------
class Coupon(Base):
    __tablename__ = 'coupons'
    __table_args__ = (UniqueConstraint('code', name='uq_coupons_code'),)

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    description = Column(Text)
    discount_type = Column(String(20), nullable=False, default='percentage')  # percentage, fixed
    discount_value = Column(Float, nullable=False)
    min_order_amount = Column(Float, default=0.0)
    max_uses = Column(Integer, default=0)  # 0 = unlimited
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)


class Promotion(Base):
    __tablename__ = 'promotions'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    discount_type = Column(String(20), nullable=False, default='percentage')
    discount_value = Column(Float, nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)

    product = relationship('Product', lazy='selectin')
    category = relationship('Category', lazy='selectin')


# ---------------------------------------------------------------------------
# Newsletter Subscribers
# ---------------------------------------------------------------------------
class NewsletterSubscriber(Base):
    __tablename__ = 'newsletter_subscribers'

    id = Column(Integer, primary_key=True)
    email = Column(String(256), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Testimonials
# ---------------------------------------------------------------------------
class Testimonial(Base):
    __tablename__ = 'testimonials'

    id = Column(Integer, primary_key=True)
    customer_name = Column(String(100), nullable=False)
    customer_title = Column(String(100))
    content = Column(Text, nullable=False)
    rating = Column(Integer, default=5)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Hero Banners
# ---------------------------------------------------------------------------
class HeroBanner(Base):
    __tablename__ = 'hero_banners'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(Text)
    description = Column(Text)
    image_url = Column(String(500))
    desktop_image_url = Column(String(500))
    tablet_image_url = Column(String(500))
    mobile_image_url = Column(String(500))
    link_url = Column(String(255))
    button_text = Column(String(50))
    secondary_button_text = Column(String(50))
    secondary_button_url = Column(String(255))
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    open_new_tab = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Blog Posts
# ---------------------------------------------------------------------------
class BlogPost(Base):
    __tablename__ = 'blog_posts'
    __table_args__ = (UniqueConstraint('slug', name='uq_blog_posts_slug'),)

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False)
    content = Column(Text)
    excerpt = Column(Text)
    image_url = Column(String(255))
    author_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    author = relationship('User', lazy='selectin')


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text)
    type = Column(String(50), default='info')  # info, success, warning, error
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship('User', backref='notifications', lazy='selectin')


# ---------------------------------------------------------------------------
# Warehouses & Inventory
# ---------------------------------------------------------------------------
class Warehouse(Base):
    __tablename__ = 'warehouses'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    location = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class Inventory(Base):
    __tablename__ = 'inventory'
    __table_args__ = (
        UniqueConstraint('product_id', 'warehouse_id', name='uq_inventory_product_warehouse'),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=False)
    quantity = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    reorder_level = Column(Integer, default=10)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    product = relationship('Product', lazy='selectin')
    warehouse = relationship('Warehouse', lazy='selectin')


# ---------------------------------------------------------------------------
# Media Library
# ---------------------------------------------------------------------------
class MediaLibrary(Base):
    __tablename__ = 'media_library'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)  # bytes
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    alt_text = Column(String(255))
    media_type = Column(String(50), default='image')  # image, banner, logo, icon, etc.
    folder = Column(String(100), default='uploads')
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    uploader = relationship('User', lazy='selectin')


# ---------------------------------------------------------------------------
# Messages (Admin Inbox)
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    sender_name = Column(String(200), nullable=False)
    sender_email = Column(String(256))
    subject = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(50), default='general')  # general, support, order, system
    is_read = Column(Boolean, default=False)
    recipient_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    recipient = relationship('User', backref='messages', lazy='selectin')


# ---------------------------------------------------------------------------
# Login Sessions (Security)
# ---------------------------------------------------------------------------
class LoginSession(Base):
    __tablename__ = 'login_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    browser = Column(String(100))
    os = Column(String(100))
    device = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_active = Column(DateTime, default=utcnow)

    user = relationship('User', backref='login_sessions', lazy='selectin')


# ---------------------------------------------------------------------------
# System Logs
# ---------------------------------------------------------------------------
class SystemLog(Base):
    __tablename__ = 'system_logs'

    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    source = Column(String(100))
    details = Column(JSON)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Payment Events (webhook / audit trail)
# ---------------------------------------------------------------------------
class PaymentEvent(Base):
    __tablename__ = 'payment_events'

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)  # charge.success, charge.failed, etc.
    event_reference = Column(String(100))
    gateway_response = Column(Text)
    payload = Column(JSON)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    payment = relationship('Payment', back_populates='events', lazy='selectin')
