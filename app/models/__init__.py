"""Re-export all active models so that ``from app.models import *`` works.

All models live in ``app.models.catalog`` (the unified async module).
The older per-file Flask-style modules (user.py, product.py, order.py,
setting.py) are obsolete and should NOT be used.
"""

from app.models.catalog import (  # noqa: F401
    # Auth / RBAC
    Permission,
    Role,
    User,
    Address,
    # Catalog
    Category,
    Brand,
    Product,
    ProductVariant,
    ProductAttribute,
    ProductImage,
    ProductReview,
    # Orders / Payments
    Order,
    OrderItem,
    Payment,
    PaymentEvent,
    # Settings / Audit
    SiteSetting,
    AuditLog,
    # Collections
    Collection,
    CollectionProduct,
    # Wishlist
    Wishlist,
    # Coupons / Promotions
    Coupon,
    CouponUsage,
    Promotion,
    # Newsletter
    NewsletterSubscriber,
    # Testimonials
    Testimonial,
    # Hero Banners
    HeroBanner,
    # Blog
    BlogPost,
    # Notifications
    Notification,
    # Messages
    Message,
    # Login Sessions
    LoginSession,
    # Warehouses / Inventory
    Warehouse,
    Inventory,
    # Media
    MediaLibrary,
    # System Logs
    SystemLog,
    # Store Visitors / Analytics
    StoreVisit,
    # Activity Logs
    ActivityLog,
    # Email System
    EmailLog,
    EmailPreference,
)
