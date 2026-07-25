# API Endpoint Reference

Base URL: `http://localhost:8000/api`

All endpoints accept and return JSON. Authentication is via Bearer token in the `Authorization` header.

---

## Table of Contents

- [Authentication](#authentication)
- [Products](#products)
- [Categories](#categories)
- [Brands](#brands)
- [Cart](#cart)
- [Orders](#orders)
- [Customers](#customers)
- [Admin](#admin)
- [Coupons](#coupons)
- [Wishlists](#wishlists)
- [Blog](#blog)
- [Newsletters](#newsletters)
- [Notifications](#notifications)
- [Collections](#collections)
- [Testimonials](#testimonials)
- [Hero Banners](#hero-banners)
- [Audit Logs](#audit-logs)
- [Content](#content)

---

## Authentication

### Register
```
POST /api/auth/register
```
**Auth:** None

**Request:**
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890"
}
```

**Response:** `201 Created`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "username": "johndoe",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "is_admin": false
  }
}
```

**Errors:** `400` - Email or username already taken

---

### Login
```
POST /api/auth/login
```
**Auth:** None

**Request:**
```json
{
  "username": "john@example.com",
  "password": "securepass123"
}
```
> The `username` field accepts either email or username.

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": { "..." }
}
```

**Errors:** `401` - Invalid credentials

---

### Get Current User
```
GET /api/auth/me
```
**Auth:** Bearer token

**Response:** `200 OK`
```json
{
  "id": 1,
  "email": "john@example.com",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "is_active": true,
  "is_admin": false,
  "role": { "id": 1, "name": "Customer", "default": true, "permissions": 1 },
  "created_at": "2026-01-15T10:30:00"
}
```

---

### Logout
```
POST /api/auth/logout
```
**Auth:** Bearer token

**Response:** `200 OK`
```json
{ "detail": "Logged out successfully" }
```

---

## Products

### List Products
```
GET /api/products
```
**Auth:** None

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `category_id` | int | Filter by category |
| `brand_id` | int | Filter by brand |
| `min_price` | float | Minimum price |
| `max_price` | float | Maximum price |
| `search` | string | Search in name/description |
| `featured` | bool | Filter featured products |
| `trending` | bool | Filter trending products |
| `in_stock` | bool | Only in-stock items |
| `status` | string | Filter by status (default: `active`) |
| `sort` | string | `newest`, `price_asc`, `price_desc`, `name` |
| `skip` | int | Pagination offset (default: 0) |
| `limit` | int | Page size 1-100 (default: 20) |

**Response:** `200 OK` - Array of `ProductOut`

---

### Get Product Count
```
GET /api/products/count
```
**Auth:** None

**Response:** `200 OK`
```json
{ "total": 42 }
```

---

### Get Product by ID
```
GET /api/products/{product_id}
```
**Auth:** None

**Response:** `200 OK` - `ProductOut`

```json
{
  "id": 1,
  "sku": "PHONE-001",
  "name": "Test Phone",
  "slug": "test-phone",
  "price": 599.99,
  "discount_price": 549.99,
  "effective_price": 549.99,
  "stock": 100,
  "is_featured": true,
  "is_trending": false,
  "status": "active",
  "category_id": 1,
  "brand_id": 1,
  "images": [{ "id": 1, "image_url": "/static/uploads/phone.jpg", "is_primary": true }],
  "variants": [{ "id": 1, "name": "Color: Black", "sku": "PHONE-001-BLK", "price_modifier": 0, "stock": 50 }],
  "attributes": [{ "id": 1, "name": "Material", "value": "Glass" }]
}
```

**Errors:** `404` - Product not found

---

### Get Product by Slug
```
GET /api/products/slug/{slug}
```
**Auth:** None

**Response:** `200 OK` - `ProductOut`

---

### Create Product
```
POST /api/products
```
**Auth:** Admin (ADMIN permission)

**Request:**
```json
{
  "name": "New Laptop",
  "sku": "LAPTOP-001",
  "slug": "new-laptop",
  "price": 1299.99,
  "stock": 25,
  "description": "A powerful laptop",
  "is_featured": true,
  "status": "active",
  "category_id": 2,
  "brand_id": 3,
  "images": [{ "image_url": "/static/uploads/laptop.jpg", "is_primary": true }],
  "variants": [{ "name": "16GB RAM", "sku": "LAPTOP-001-16", "price_modifier": 200, "stock": 10 }],
  "attributes": [{ "name": "Processor", "value": "Intel i7" }]
}
```

**Response:** `201 Created` - `ProductOut`

**Errors:** `400` - SKU already exists

---

### Update Product
```
PUT /api/products/{product_id}
```
**Auth:** Admin (ADMIN permission)

**Request:** Partial update (only send fields to change)
```json
{
  "price": 1199.99,
  "stock": 30
}
```

**Response:** `200 OK` - `ProductOut`

---

### Delete Product
```
DELETE /api/products/{product_id}
```
**Auth:** Admin (ADMIN permission)

**Response:** `200 OK`
```json
{ "detail": "Product deleted" }
```

---

## Categories

### List Categories
```
GET /api/categories
```
**Auth:** None

**Response:** `200 OK` - Array of `CategoryOut`
```json
[
  { "id": 1, "name": "Electronics", "slug": "electronics", "description": "...", "image_url": null }
]
```

---

### Get Category
```
GET /api/categories/{category_id}
```
**Auth:** None

---

### Create Category
```
POST /api/categories
```
**Auth:** Admin (ADMIN permission)

**Request:**
```json
{ "name": "Clothing", "slug": "clothing", "description": "Fashion items", "image_url": "/static/uploads/cat.jpg" }
```

**Response:** `201 Created`

---

### Update Category
```
PUT /api/categories/{category_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Category
```
DELETE /api/categories/{category_id}
```
**Auth:** Admin (ADMIN permission)

---

## Brands

### List Brands
```
GET /api/brands
```
**Auth:** None

---

### Get Brand
```
GET /api/brands/{brand_id}
```
**Auth:** None

---

### Create Brand
```
POST /api/brands
```
**Auth:** Admin (ADMIN permission)

**Request:**
```json
{ "name": "Nike", "slug": "nike", "image_url": "/static/uploads/nike.png" }
```

---

### Update Brand
```
PUT /api/brands/{brand_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Brand
```
DELETE /api/brands/{brand_id}
```
**Auth:** Admin (ADMIN permission)

---

## Cart

### Get Cart
```
GET /api/cart?cart_id={cart_id}
```
**Auth:** None (session-based)

**Response:** `200 OK`
```json
{
  "items": [
    {
      "product_id": 1,
      "name": "Test Phone",
      "slug": "test-phone",
      "quantity": 2,
      "unit_price": 599.99,
      "line_total": 1199.98,
      "image_url": "/static/uploads/phone.jpg",
      "stock": 100
    }
  ],
  "subtotal": 1199.98,
  "item_count": 2
}
```

---

### Add Item to Cart
```
POST /api/cart/items?cart_id={cart_id}
```
**Auth:** None

**Request:**
```json
{ "product_id": 1, "quantity": 2 }
```

**Response:** `200 OK` - Updated `CartOut`

**Errors:** `400` - Insufficient stock | `404` - Product not found

---

### Update Cart Item
```
PUT /api/cart/items/{product_id}?cart_id={cart_id}&qty={quantity}
```
**Auth:** None

**Errors:** `400` - Quantity must be >= 1 | `404` - Item not in cart

---

### Remove Cart Item
```
DELETE /api/cart/items/{product_id}?cart_id={cart_id}
```
**Auth:** None

---

### Clear Cart
```
DELETE /api/cart?cart_id={cart_id}
```
**Auth:** None

---

## Orders

### List My Orders
```
GET /api/orders
```
**Auth:** Bearer token

**Query:** `status`, `skip`, `limit`

---

### Get Order
```
GET /api/orders/{order_id}
```
**Auth:** Bearer token (must own order or be admin)

---

### Checkout
```
POST /api/orders/checkout?cart_id={cart_id}
```
**Auth:** Bearer token

**Request:**
```json
{
  "address_id": 1,
  "payment_method": "Cash on Delivery",
  "shipping_fee": 5.0,
  "tax": 2.0
}
```
> Or provide inline address: `street`, `city`, `state`, `country`, `zip_code`

**Response:** `201 Created` - `OrderOut`
```json
{
  "id": 1,
  "order_number": "ORD-20260115103000",
  "status": "Pending",
  "subtotal": 0.0,
  "shipping_fee": 5.0,
  "tax": 2.0,
  "total_amount": 0.0,
  "items": [],
  "payment": null
}
```

---

### Update Order Status (Admin)
```
PATCH /api/orders/{order_id}/status
```
**Auth:** Admin (VIEW + EDIT permission)

**Request:**
```json
{ "status": "Processing" }
```

**Valid statuses:** `Pending`, `Processing`, `Shipped`, `Delivered`, `Cancelled`, `Refunded`

---

### Admin List All Orders
```
GET /api/orders/admin
```
**Auth:** Admin (VIEW permission)

**Query:** `status`, `user_id`, `skip`, `limit`

---

## Customers

### Get My Profile
```
GET /api/customers/me
```
**Auth:** Bearer token

---

### Update My Profile
```
PATCH /api/customers/me
```
**Auth:** Bearer token

**Request:**
```json
{ "first_name": "John", "last_name": "Smith", "phone": "+1987654321" }
```

---

### List My Addresses
```
GET /api/customers/me/addresses
```
**Auth:** Bearer token

---

### Create Address
```
POST /api/customers/me/addresses
```
**Auth:** Bearer token

**Request:**
```json
{
  "street": "123 Main St",
  "city": "Accra",
  "state": "Greater Accra",
  "country": "Ghana",
  "zip_code": "00233",
  "is_default": true
}
```

---

### Update Address
```
PUT /api/customers/me/addresses/{address_id}
```
**Auth:** Bearer token

---

### Delete Address
```
DELETE /api/customers/me/addresses/{address_id}
```
**Auth:** Bearer token

---

## Admin

### Dashboard Stats
```
GET /api/admin/dashboard
```
**Auth:** Admin (VIEW permission)

**Response:** `200 OK`
```json
{
  "revenue_today": 1250.00,
  "revenue_month": 35000.00,
  "orders_today": 12,
  "orders_month": 156,
  "product_count": 245,
  "customer_count": 1023,
  "pending_orders": 8,
  "low_stock_alerts": 3
}
```

---

### List All Users
```
GET /api/admin/users
```
**Auth:** Admin (VIEW permission)

---

### List Customers
```
GET /api/admin/customers
```
**Auth:** Admin (VIEW permission)

---

### Update User Role
```
PATCH /api/admin/users/{user_id}/role
```
**Auth:** Admin (VIEW + EDIT permission)

**Request:**
```json
{ "role_id": 2, "is_active": true }
```

---

### Admin Products CRUD
```
GET    /api/admin/products          # List (VIEW)
POST   /api/admin/products          # Create (CREATE)
PUT    /api/admin/products/{id}     # Update (EDIT)
DELETE /api/admin/products/{id}     # Delete (DELETE)
```

### Admin Categories CRUD
```
GET    /api/admin/categories          # List (VIEW)
POST   /api/admin/categories          # Create (CREATE)
PUT    /api/admin/categories/{id}     # Update (EDIT)
DELETE /api/admin/categories/{id}     # Delete (DELETE)
```

### Admin Brands CRUD
```
GET    /api/admin/brands          # List (VIEW)
POST   /api/admin/brands          # Create (CREATE)
PUT    /api/admin/brands/{id}     # Update (EDIT)
DELETE /api/admin/brands/{id}     # Delete (DELETE)
```

### Admin Reviews
```
GET    /api/admin/reviews          # List all reviews (VIEW)
DELETE /api/admin/reviews/{id}     # Delete review (DELETE)
```

### Admin Settings
```
GET    /api/admin/settings              # List (VIEW)
POST   /api/admin/settings              # Create (CREATE)
PUT    /api/admin/settings/{id}         # Update (EDIT)
DELETE /api/admin/settings              # Bulk delete (DELETE)
```

### Admin Inventory
```
GET    /api/admin/inventory             # List variants (VIEW)
PATCH  /api/admin/inventory/{variant_id} # Update stock (ADMIN)
```

### Admin Payments
```
GET    /api/admin/payments              # List (VIEW)
```

---

## Coupons

### List Coupons
```
GET /api/coupons
```
**Auth:** Admin (ADMIN permission)

---

### Get Coupon
```
GET /api/coupons/{coupon_id}
```
**Auth:** Admin (ADMIN permission)

---

### Create Coupon
```
POST /api/coupons
```
**Auth:** Admin (ADMIN permission)

**Request:**
```json
{
  "code": "SUMMER20",
  "description": "Summer sale 20% off",
  "discount_type": "percentage",
  "discount_value": 20,
  "min_order_amount": 50,
  "max_uses": 100,
  "is_active": true,
  "start_date": "2026-06-01T00:00:00",
  "end_date": "2026-08-31T23:59:59"
}
```

---

### Update Coupon
```
PUT /api/coupons/{coupon_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Coupon
```
DELETE /api/coupons/{coupon_id}
```
**Auth:** Admin (ADMIN permission)

---

### Validate Coupon
```
POST /api/coupons/validate
```
**Auth:** None

**Request:**
```json
{ "code": "SUMMER20", "cart_total": 100.00 }
```

**Response:** `200 OK`
```json
{
  "valid": true,
  "discount_type": "percentage",
  "discount_value": 20,
  "discount_amount": 20.00
}
```

**Errors:** `404` - Invalid code | `400` - Expired / usage limit / min amount not met

---

## Wishlists

### List Wishlist
```
GET /api/wishlists
```
**Auth:** Bearer token

---

### Add to Wishlist
```
POST /api/wishlists
```
**Auth:** Bearer token

**Request:**
```json
{ "product_id": 1 }
```

**Errors:** `400` - Already in wishlist | `404` - Product not found

---

### Remove from Wishlist
```
DELETE /api/wishlists/{product_id}
```
**Auth:** Bearer token

---

## Blog

### List Published Posts
```
GET /api/blog
```
**Auth:** None

**Query:** `skip`, `limit`

---

### Get Post by Slug
```
GET /api/blog/{slug}
```
**Auth:** None

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Getting Started with Our Store",
  "slug": "getting-started",
  "content": "...",
  "excerpt": "...",
  "image_url": null,
  "author_id": 1,
  "is_published": true,
  "created_at": "2026-01-15T10:30:00",
  "author": { "id": 1, "username": "admin" }
}
```

---

### Create Post
```
POST /api/blog
```
**Auth:** Admin (ADMIN permission)

---

### Update Post
```
PUT /api/blog/{post_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Post
```
DELETE /api/blog/{post_id}
```
**Auth:** Admin (ADMIN permission)

---

## Newsletters

### Subscribe
```
POST /api/newsletters/subscribe
```
**Auth:** None

**Request:**
```json
{ "email": "subscriber@example.com" }
```

**Response:** `201 Created`
```json
{ "detail": "Subscribed successfully" }
```

---

### Unsubscribe
```
DELETE /api/newsletters/unsubscribe?email={email}
```
**Auth:** None

---

### List Subscribers
```
GET /api/newsletters
```
**Auth:** Admin (ADMIN permission)

---

## Notifications

### List My Notifications
```
GET /api/notifications
```
**Auth:** Bearer token

**Query:** `unread_only` (bool), `skip`, `limit`

---

### Mark Notification as Read
```
PATCH /api/notifications/{notification_id}/read
```
**Auth:** Bearer token

---

### Delete Notification
```
DELETE /api/notifications/{notification_id}
```
**Auth:** Bearer token

---

### Mark All as Read
```
PATCH /api/notifications/read-all
```
**Auth:** Bearer token

---

## Collections

### List Active Collections
```
GET /api/collections
```
**Auth:** None

---

### Get Collection by Slug
```
GET /api/collections/{slug}
```
**Auth:** None

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Summer Essentials",
  "slug": "summer-essentials",
  "products": [{ "id": 1, "name": "Sunglasses", "price": 29.99 }]
}
```

---

### Create Collection
```
POST /api/collections
```
**Auth:** Admin (ADMIN permission)

---

### Update Collection
```
PUT /api/collections/{collection_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Collection
```
DELETE /api/collections/{collection_id}
```
**Auth:** Admin (ADMIN permission)

---

### Add Product to Collection
```
POST /api/collections/{collection_id}/products
```
**Auth:** Admin (ADMIN permission)

**Request:**
```json
{ "product_id": 1, "position": 0 }
```

---

### Remove Product from Collection
```
DELETE /api/collections/{collection_id}/products/{product_id}
```
**Auth:** Admin (ADMIN permission)

---

## Testimonials

### List Active Testimonials
```
GET /api/testimonials
```
**Auth:** None

**Query:** `skip`, `limit`

---

### Create Testimonial
```
POST /api/testimonials
```
**Auth:** Admin (ADMIN permission)

---

### Update Testimonial
```
PUT /api/testimonials/{testimonial_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Testimonial
```
DELETE /api/testimonials/{testimonial_id}
```
**Auth:** Admin (ADMIN permission)

---

## Hero Banners

### List Active Banners
```
GET /api/hero-banners
```
**Auth:** None

---

### Create Banner
```
POST /api/hero-banners
```
**Auth:** Admin (ADMIN permission)

---

### Update Banner
```
PUT /api/hero-banners/{banner_id}
```
**Auth:** Admin (ADMIN permission)

---

### Delete Banner
```
DELETE /api/hero-banners/{banner_id}
```
**Auth:** Admin (ADMIN permission)

---

## Audit Logs

### List Audit Logs
```
GET /api/audit
```
**Auth:** Admin (ADMIN permission)

**Query:** `user_id`, `action`, `entity_type`, `skip`, `limit`

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "user_id": 1,
    "action": "CREATE",
    "entity_type": "Product",
    "entity_id": 15,
    "details": "Created product: Laptop (SKU: LAPTOP-001)",
    "ip_address": "127.0.0.1",
    "created_at": "2026-01-15T10:30:00",
    "user": { "id": 1, "username": "admin", "email": "admin@primenest.com" }
  }
]
```

---

### List System Logs
```
GET /api/audit/system
```
**Auth:** Admin (ADMIN permission)

**Query:** `level`, `source`, `skip`, `limit`

---

## Content

### Get Homepage Data
```
GET /api/content/homepage
```
**Auth:** None

**Response:** `200 OK`
```json
{
  "banners": [{ "id": 1, "title": "Summer Sale", "position": 0 }],
  "featured_products": [{ "id": 1, "name": "Phone", "price": 599.99 }],
  "testimonials": [{ "id": 1, "customer_name": "Jane", "rating": 5 }]
}
```

---

### Get Public Settings
```
GET /api/content/settings
```
**Auth:** None

**Response:** `200 OK`
```json
[
  { "key": "site_name", "value": "ASAH'S PRIMENEST", "description": "Site name" }
]
```

---

## Health Check

```
GET /health
```
**Auth:** None

**Response:** `200 OK`
```json
{ "status": "ok" }
```

---

## Pagination

Most list endpoints support pagination via `skip` and `limit` query parameters:

```
GET /api/products?skip=20&limit=10
```

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 422 | Unprocessable Entity (request validation) |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |
