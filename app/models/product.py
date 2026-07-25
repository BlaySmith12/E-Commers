from app.flask_app import db
from datetime import datetime

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Brand(db.Model):
    __tablename__ = 'brands'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    image_url = db.Column(db.String(255))
    products = db.relationship('Product', backref='brand', lazy='dynamic')

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float)
    stock = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_trending = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'))
    
    images = db.relationship('ProductImage', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('ProductReview', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    variants = db.relationship('ProductVariant', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    attributes = db.relationship('ProductAttribute', backref='product', lazy='dynamic', cascade='all, delete-orphan')

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    name = db.Column(db.String(100), nullable=False) # e.g. "Color: Red, Size: M"
    sku = db.Column(db.String(50), unique=True)
    price_modifier = db.Column(db.Float, default=0.0)
    stock = db.Column(db.Integer, default=0)

class ProductAttribute(db.Model):
    __tablename__ = 'product_attributes'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    name = db.Column(db.String(100), nullable=False) # e.g. "Material"
    value = db.Column(db.String(255), nullable=False) # e.g. "Stainless Steel"

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))

class ProductReview(db.Model):
    __tablename__ = 'product_reviews'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
