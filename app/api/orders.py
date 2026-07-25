"""Orders REST API."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.catalog import Order, OrderItem, Address, User, AuditLog, Payment, Product
from app.schemas import OrderOut, CheckoutIn, MessageOut, OrderStatusUpdate
from app.security import CurrentUser, RequireAdmin, RequireEditor, RequireViewer
from app.audit import log_audit

router = APIRouter(prefix='/orders', tags=['Orders'])


# ---- Public order tracking ----

class TrackOrderIn(BaseModel):
    order_number: str
    email: str


class TrackItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quantity: int
    price: float
    snapshot_name: Optional[str] = None
    snapshot_image: Optional[str] = None
    snapshot_brand: Optional[str] = None


class TrackOrderOut(BaseModel):
    id: int
    order_number: str
    status: str
    total_amount: float
    subtotal: float
    shipping_fee: float
    tax: float
    created_at: Optional[datetime] = None
    items: List[TrackItemOut] = []
    shipping_address: Optional[str] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None


@router.post('/track', response_model=TrackOrderOut)
async def track_order(payload: TrackOrderIn, db: AsyncSession = Depends(get_db)):
    """Public endpoint: look up an order by order number and customer email."""
    result = await db.execute(
        select(Order, User, Address)
        .join(User, Order.user_id == User.id, isouter=True)
        .join(Address, Order.shipping_address_id == Address.id, isouter=True)
        .where(Order.order_number == payload.order_number)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail='Order not found. Please check your order number.')
    if not row.User or row.User.email.lower() != payload.email.lower():
        raise HTTPException(status_code=404, detail='No order found with that order number and email combination.')
    order = row.Order
    items = [TrackItemOut.model_validate(i) for i in (order.items or [])]
    payment_result = await db.execute(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc()).limit(1)
    )
    payment = payment_result.scalar_one_or_none()
    shipping_addr = None
    if row.Address:
        parts = [row.Address.street, row.Address.city, row.Address.state, row.Address.country]
        shipping_addr = ', '.join(p for p in parts if p)
    return TrackOrderOut(
        id=order.id, order_number=order.order_number, status=order.status,
        total_amount=order.total_amount, subtotal=order.subtotal,
        shipping_fee=order.shipping_fee, tax=order.tax,
        created_at=order.created_at, items=items,
        shipping_address=shipping_addr,
        payment_status=payment.status if payment else None,
        payment_method=payment.payment_method if payment else None,
    )


def _gen_order_number() -> str:
    return f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


@router.get('', response_model=List[OrderOut])
async def list_orders(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Order).where(Order.user_id == current_user.id)
    if status:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/admin')
async def admin_list_orders(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
    status: str = Query(None),
    user_id: int = Query(None),
    search: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items),
            selectinload(Order.payment),
            selectinload(Order.shipping_address),
        )
    )
    if status:
        stmt = stmt.where(Order.status == status)
    if user_id:
        stmt = stmt.where(Order.user_id == user_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.join(User, Order.user_id == User.id, isouter=True).where(
            or_(
                Order.order_number.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.phone.ilike(like),
            )
        )
    stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    orders = result.scalars().unique().all()

    out = []
    for o in orders:
        cust = None
        if o.customer:
            cust = {
                'id': o.customer.id,
                'first_name': o.customer.first_name,
                'last_name': o.customer.last_name,
                'email': o.customer.email,
                'phone': o.customer.phone,
            }
        items_out = []
        for it in (o.items or []):
            items_out.append({
                'id': it.id,
                'quantity': it.quantity,
                'price': it.price,
                'product_id': it.product_id,
                'snapshot_name': it.snapshot_name,
                'snapshot_image': it.snapshot_image,
            })
        pay_method = None
        pay_brief = None
        if o.payment:
            pay_method = o.payment.payment_method or o.payment.channel or 'Paystack'
            pay_brief = {
                'id': o.payment.id,
                'status': o.payment.status,
                'payment_method': o.payment.payment_method,
                'transaction_reference': o.payment.transaction_reference,
                'channel': o.payment.channel,
                'provider': o.payment.provider,
            }
        addr = None
        if o.shipping_address:
            addr = {
                'id': o.shipping_address.id,
                'street': getattr(o.shipping_address, 'street', None),
                'city': getattr(o.shipping_address, 'city', None),
                'state': getattr(o.shipping_address, 'state', None),
                'country': getattr(o.shipping_address, 'country', None),
                'zip_code': getattr(o.shipping_address, 'zip_code', None),
            }
        out.append({
            'id': o.id,
            'order_number': o.order_number,
            'status': o.status,
            'payment_status': o.payment_status,
            'currency': o.currency,
            'discount': o.discount,
            'subtotal': o.subtotal,
            'shipping_fee': o.shipping_fee,
            'tax': o.tax,
            'total_amount': o.total_amount,
            'notes': o.notes,
            'created_at': o.created_at.isoformat() if o.created_at else None,
            'updated_at': o.updated_at.isoformat() if o.updated_at else None,
            'user_id': o.user_id,
            'customer': cust,
            'items': items_out,
            'payment': pay_brief,
            'payment_method': pay_method,
            'shipping_address': addr,
        })

    return out


@router.get('/{order_id}')
async def get_order(order_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items),
            selectinload(Order.payment),
            selectinload(Order.shipping_address),
        )
        .where(Order.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalars().unique().first()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    if not current_user.is_admin and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')

    cust = None
    if order.customer:
        cust = {
            'id': order.customer.id,
            'first_name': order.customer.first_name,
            'last_name': order.customer.last_name,
            'email': order.customer.email,
            'phone': order.customer.phone,
        }
    items_out = []
    for it in (order.items or []):
        items_out.append({
            'id': it.id,
            'quantity': it.quantity,
            'price': it.price,
            'product_id': it.product_id,
            'snapshot_name': it.snapshot_name,
            'snapshot_image': it.snapshot_image,
        })
    pay_method = None
    pay_brief = None
    if order.payment:
        pay_method = order.payment.payment_method or order.payment.channel or 'Paystack'
        pay_brief = {
            'id': order.payment.id,
            'status': order.payment.status,
            'payment_method': order.payment.payment_method,
            'transaction_reference': order.payment.transaction_reference,
            'channel': order.payment.channel,
            'provider': order.payment.provider,
            'amount': order.payment.amount,
            'currency': order.payment.currency,
            'paid_at': order.payment.paid_at.isoformat() if order.payment.paid_at else None,
            'customer_email': order.payment.customer_email,
            'gateway_response': order.payment.gateway_response,
        }
    addr = None
    if order.shipping_address:
        addr = {
            'id': order.shipping_address.id,
            'street': getattr(order.shipping_address, 'street', None),
            'city': getattr(order.shipping_address, 'city', None),
            'state': getattr(order.shipping_address, 'state', None),
            'country': getattr(order.shipping_address, 'country', None),
            'zip_code': getattr(order.shipping_address, 'zip_code', None),
            'full_name': getattr(order.shipping_address, 'full_name', None),
            'phone': getattr(order.shipping_address, 'phone', None),
        }

    return {
        'id': order.id,
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment_status,
        'currency': order.currency,
        'discount': order.discount,
        'subtotal': order.subtotal,
        'shipping_fee': order.shipping_fee,
        'tax': order.tax,
        'total_amount': order.total_amount,
        'notes': order.notes,
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        'user_id': order.user_id,
        'customer': cust,
        'items': items_out,
        'payment': pay_brief,
        'payment_method': pay_method,
        'shipping_address': addr,
    }


@router.post('/checkout', response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    payload: CheckoutIn, cart_id: str = 'default',
    current_user: CurrentUser = None, db: AsyncSession = Depends(get_db),
):
    from app.api.cart import _get_cart, _cart_coupons, CART_SHIPPING_FEE, CART_TAX_RATE
    from app.models.catalog import Product, Coupon

    if current_user is None:
        raise HTTPException(status_code=401, detail='Authentication required')

    # Resolve address
    address = None
    if payload.address_id:
        result = await db.execute(select(Address).where(Address.id == payload.address_id))
        address = result.scalar_one_or_none()
        if not address or address.user_id != current_user.id:
            raise HTTPException(status_code=400, detail='Invalid address')
    elif payload.street and payload.city:
        address = Address(
            street=payload.street, city=payload.city, state=payload.state,
            country=payload.country, zip_code=payload.zip_code, user_id=current_user.id,
        )
        db.add(address)
        await db.flush()
    else:
        raise HTTPException(status_code=400, detail='Address required')

    # Get cart
    cart = _get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=400, detail='Cart is empty')

    # Validate all products exist and have stock
    order_items = []
    subtotal = 0.0
    for product_id, qty in list(cart.items()):
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=400, detail=f'Product {product_id} not found')
        if product.stock < qty:
            raise HTTPException(status_code=400, detail=f'Insufficient stock for {product.name}')
        unit_price = product.effective_price
        line_total = unit_price * qty
        subtotal += line_total

        # Capture product image URL
        snapshot_image = None
        if product.images:
            primary = next((i for i in product.images if i.is_primary), None)
            if primary:
                snapshot_image = primary.image_url
            elif product.images:
                snapshot_image = product.images[0].image_url

        # Capture brand name
        snapshot_brand = product.brand.name if product.brand else None

        order_items.append({
            'product_id': product.id,
            'quantity': qty,
            'price': unit_price,
            'snapshot_name': product.name,
            'snapshot_image': snapshot_image,
            'snapshot_slug': product.slug,
            'snapshot_sku': product.sku,
            'snapshot_brand': snapshot_brand,
            'snapshot_variant': None,
        })

    # Apply coupon
    discount = 0.0
    coupon_code = payload.coupon_code or _cart_coupons.get(cart_id)
    if coupon_code:
        coupon_result = await db.execute(
            select(Coupon).where(Coupon.code == coupon_code, Coupon.is_active == True)
        )
        coupon = coupon_result.scalar_one_or_none()
        if coupon:
            from datetime import datetime as dt
            now = dt.utcnow()
            valid = True
            if coupon.start_date and now < coupon.start_date:
                valid = False
            if coupon.end_date and now > coupon.end_date:
                valid = False
            if coupon.max_uses and coupon.used_count >= coupon.max_uses:
                valid = False
            if subtotal < coupon.min_order_amount:
                valid = False
            if valid:
                if coupon.discount_type == 'percentage':
                    discount = subtotal * (coupon.discount_value / 100)
                else:
                    discount = min(coupon.discount_value, subtotal)
                coupon.used_count += 1
                await db.flush()
            else:
                coupon_code = None
        else:
            coupon_code = None

    discount = round(discount, 2)
    shipping_fee = payload.shipping_fee if payload.shipping_fee else CART_SHIPPING_FEE
    taxable = max(subtotal - discount, 0.0)
    tax = round(taxable * CART_TAX_RATE, 2)
    total_amount = round(taxable + shipping_fee + tax, 2)

    # Create order
    is_paystack = payload.payment_method in ('Paystack', 'Credit Card', 'Mobile Money', 'Bank Transfer')
    order = Order(
        order_number=_gen_order_number(),
        user_id=current_user.id,
        shipping_address_id=address.id,
        status='Pending Payment' if is_paystack else 'Pending',
        payment_status='Pending' if is_paystack else 'Pending',
        currency='GHS',
        subtotal=round(subtotal, 2),
        discount=discount,
        shipping_fee=shipping_fee,
        tax=tax,
        total_amount=total_amount,
        notes=payload.notes,
    )
    db.add(order)
    await db.flush()

    # Create order items (don't decrement stock yet for online payments - wait for payment verification)
    for item_data in order_items:
        oi = OrderItem(
            order_id=order.id,
            product_id=item_data['product_id'],
            quantity=item_data['quantity'],
            price=item_data['price'],
            snapshot_name=item_data.get('snapshot_name'),
            snapshot_image=item_data.get('snapshot_image'),
            snapshot_slug=item_data.get('snapshot_slug'),
            snapshot_sku=item_data.get('snapshot_sku'),
            snapshot_brand=item_data.get('snapshot_brand'),
            snapshot_variant=item_data.get('snapshot_variant'),
        )
        db.add(oi)

    # For COD: decrement stock immediately. For Paystack: wait for payment verification.
    if not is_paystack:
        for item_data in order_items:
            product = (await db.execute(select(Product).where(Product.id == item_data['product_id']))).scalar_one_or_none()
            if product:
                product.stock -= item_data['quantity']

    # Create payment record
    from datetime import datetime as _dt
    payment = Payment(
        order_id=order.id,
        provider='paystack' if is_paystack else 'cod',
        amount=total_amount,
        currency='GHS',
        status='Pending',
        payment_method=payload.payment_method,
    )
    db.add(payment)

    await db.commit()
    await db.refresh(order)
    await db.refresh(payment)

    # For COD: clear cart immediately. For Paystack: clear after payment verified.
    if not is_paystack:
        _cart_store = __import__('app.api.cart', fromlist=['_cart_store'])._cart_store
        _cart_store.pop(cart_id, None)
        _cart_coupons.pop(cart_id, None)

    # Audit log
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Order",
        entity_id=order.id,
        user_id=current_user.id,
        details=f"Created order: {order.order_number} total={total_amount} items={len(order_items)} payment={payload.payment_method}"
    )

    return order


@router.patch('/{order_id}/status', response_model=OrderOut)
async def update_order_status(
    order_id: int, payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db), admin: User = Depends(RequireEditor),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    old_status = order.status
    order.status = payload.status

    # Auto-update payment_status when order status changes
    status_to_payment = {
        'Paid': 'Paid',
        'Processing': 'Paid',
        'Shipped': 'Paid',
        'Delivered': 'Paid',
        'Payment Failed': 'Failed',
        'Payment Processing': 'Processing',
    }
    if payload.status in status_to_payment:
        order.payment_status = status_to_payment[payload.status]

    await db.commit()
    await db.refresh(order)

    await log_audit(
        db=db,
        action="UPDATE",
        entity_type="Order",
        entity_id=order.id,
        user_id=admin.id,
        details=f"Updated order {order.order_number} status: {old_status} -> {order.status}"
    )

    return order


@router.post('/{order_id}/cancel', response_model=OrderOut)
async def cancel_order(
    order_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Forbidden')
    if order.status not in ('Pending Payment', 'Pending', 'Processing'):
        raise HTTPException(status_code=400, detail='Order cannot be cancelled at this stage')

    # Restore stock only if stock was decremented (non-Paystack orders)
    if order.payment_status != 'Pending':
        for item in order.items:
            product = (await db.execute(select(Product).where(Product.id == item.product_id))).scalar_one_or_none()
            if product:
                product.stock += item.quantity

    order.status = 'Cancelled'
    await db.commit()
    await db.refresh(order)
    return order
