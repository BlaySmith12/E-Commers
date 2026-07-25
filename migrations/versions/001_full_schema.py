"""Full schema – all tables.

Revision ID: 001_full_schema
Revises:
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001_full_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # roles
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(64), unique=True, nullable=False),
        sa.Column('default', sa.Boolean(), default=False, index=True),
        sa.Column('permissions', sa.Integer(), default=0),
    )

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(256), unique=True, index=True, nullable=False),
        sa.Column('username', sa.String(64), unique=True, index=True, nullable=False),
        sa.Column('password_hash', sa.String(256)),
        sa.Column('first_name', sa.String(64)),
        sa.Column('last_name', sa.String(64)),
        sa.Column('phone', sa.String(20)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id')),
        sa.Column('created_at', sa.DateTime()),
    )

    # addresses
    op.create_table(
        'addresses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('street', sa.String(255), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('state', sa.String(100)),
        sa.Column('country', sa.String(100), default='Ghana'),
        sa.Column('zip_code', sa.String(20)),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
    )

    # categories
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('image_url', sa.String(255)),
        sa.UniqueConstraint('slug', name='uq_categories_slug'),
    )

    # brands
    op.create_table(
        'brands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('image_url', sa.String(255)),
        sa.UniqueConstraint('slug', name='uq_brands_slug'),
    )

    # products
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('discount_price', sa.Float()),
        sa.Column('stock', sa.Integer(), default=0),
        sa.Column('is_featured', sa.Boolean(), default=False),
        sa.Column('is_trending', sa.Boolean(), default=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id')),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id')),
        sa.UniqueConstraint('sku', name='uq_products_sku'),
        sa.UniqueConstraint('slug', name='uq_products_slug'),
        sa.Index('ix_products_category_id', 'category_id'),
        sa.Index('ix_products_brand_id', 'brand_id'),
        sa.Index('ix_products_price', 'price'),
    )

    # product_variants
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('sku', sa.String(50)),
        sa.Column('price_modifier', sa.Float(), default=0.0),
        sa.Column('stock', sa.Integer(), default=0),
        sa.UniqueConstraint('sku', name='uq_product_variants_sku'),
    )

    # product_attributes
    op.create_table(
        'product_attributes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('value', sa.String(255), nullable=False),
    )

    # product_images
    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('image_url', sa.String(255), nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('alt_text', sa.String(255)),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id')),
    )

    # product_reviews
    op.create_table(
        'product_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id')),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Index('ix_product_reviews_product_id', 'product_id'),
    )

    # orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_number', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='Pending'),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('shipping_fee', sa.Float(), default=0.0),
        sa.Column('tax', sa.Float(), default=0.0),
        sa.Column('subtotal', sa.Float(), default=0.0),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('shipping_address_id', sa.Integer(), sa.ForeignKey('addresses.id')),
        sa.UniqueConstraint('order_number', name='uq_orders_order_number'),
        sa.Index('ix_orders_user_id', 'user_id'),
        sa.Index('ix_orders_created_at', 'created_at'),
    )

    # order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quantity', sa.Integer(), nullable=False, default=1),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id')),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id')),
    )

    # payments
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transaction_id', sa.String(100)),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), default='Pending'),
        sa.Column('payment_method', sa.String(50), default='Cash on Delivery'),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id')),
    )

    # site_settings
    op.create_table(
        'site_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, index=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime()),
        sa.UniqueConstraint('key', name='uq_site_settings_key'),
    )

    # audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), index=True),
    )

    # collections
    op.create_table(
        'collections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('image_url', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('slug', name='uq_collections_slug'),
    )

    # collection_products
    op.create_table(
        'collection_products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('collections.id'), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('position', sa.Integer(), default=0),
        sa.UniqueConstraint('collection_id', 'product_id', name='uq_collection_product'),
    )

    # wishlists
    op.create_table(
        'wishlists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_wishlist_user_product'),
    )

    # coupons
    op.create_table(
        'coupons',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('discount_type', sa.String(20), nullable=False, default='percentage'),
        sa.Column('discount_value', sa.Float(), nullable=False),
        sa.Column('min_order_amount', sa.Float(), default=0.0),
        sa.Column('max_uses', sa.Integer(), default=0),
        sa.Column('used_count', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('start_date', sa.DateTime()),
        sa.Column('end_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('code', name='uq_coupons_code'),
    )

    # promotions
    op.create_table(
        'promotions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('discount_type', sa.String(20), nullable=False, default='percentage'),
        sa.Column('discount_value', sa.Float(), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('start_date', sa.DateTime()),
        sa.Column('end_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime()),
    )

    # newsletter_subscribers
    op.create_table(
        'newsletter_subscribers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(256), unique=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
    )

    # testimonials
    op.create_table(
        'testimonials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_name', sa.String(100), nullable=False),
        sa.Column('customer_title', sa.String(100)),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('rating', sa.Integer(), default=5),
        sa.Column('is_featured', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
    )

    # hero_banners
    op.create_table(
        'hero_banners',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('subtitle', sa.Text()),
        sa.Column('image_url', sa.String(255)),
        sa.Column('link_url', sa.String(255)),
        sa.Column('button_text', sa.String(50)),
        sa.Column('position', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
    )

    # blog_posts
    op.create_table(
        'blog_posts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('excerpt', sa.Text()),
        sa.Column('image_url', sa.String(255)),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_published', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.UniqueConstraint('slug', name='uq_blog_posts_slug'),
    )

    # notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text()),
        sa.Column('type', sa.String(50), default='info'),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime()),
    )

    # warehouses
    op.create_table(
        'warehouses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
    )

    # inventory
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), sa.ForeignKey('warehouses.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), default=0),
        sa.Column('reserved', sa.Integer(), default=0),
        sa.Column('reorder_level', sa.Integer(), default=10),
        sa.Column('updated_at', sa.DateTime()),
        sa.UniqueConstraint('product_id', 'warehouse_id', name='uq_inventory_product_warehouse'),
    )

    # media_library
    op.create_table(
        'media_library',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('file_size', sa.Integer()),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('alt_text', sa.String(255)),
        sa.Column('folder', sa.String(100), default='uploads'),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )

    # system_logs
    op.create_table(
        'system_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('source', sa.String(100)),
        sa.Column('details', sa.JSON()),
        sa.Column('created_at', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('system_logs')
    op.drop_table('media_library')
    op.drop_table('inventory')
    op.drop_table('warehouses')
    op.drop_table('notifications')
    op.drop_table('blog_posts')
    op.drop_table('hero_banners')
    op.drop_table('testimonials')
    op.drop_table('newsletter_subscribers')
    op.drop_table('promotions')
    op.drop_table('coupons')
    op.drop_table('wishlists')
    op.drop_table('collection_products')
    op.drop_table('collections')
    op.drop_table('audit_logs')
    op.drop_table('site_settings')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('product_reviews')
    op.drop_table('product_images')
    op.drop_table('product_attributes')
    op.drop_table('product_variants')
    op.drop_table('products')
    op.drop_table('brands')
    op.drop_table('categories')
    op.drop_table('addresses')
    op.drop_table('users')
    op.drop_table('roles')
