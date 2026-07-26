"""Orders REST API."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.catalog import Order, OrderItem, Address, User, AuditLog, Payment, Product, Coupon, CouponUsage, LoyaltyAccount, LoyaltyTransaction, LoyaltySettings
from app.schemas import OrderOut, CheckoutIn, MessageOut, OrderStatusUpdate
from app.security import CurrentUser, RequireAdmin, RequireEditor, RequireViewer
from app.audit import log_audit
from app.activity import log_activity

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
                'snapshot_name': it.snapshot_name or it.product_name,
                'snapshot_image': it.snapshot_image or it.product_image,
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
            'snapshot_name': it.snapshot_name or it.product_name,
            'snapshot_image': it.snapshot_image or it.product_image,
            'product_name': it.product_name,
            'product_image': it.product_image,
            'product_slug': it.product_slug,
            'product_brand': it.product_brand,
            'product_sku': it.product_sku,
            'product_variant': it.product_variant,
            'line_total': it.price * it.quantity,
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

    # Apply coupon (secure server-side validation)
    discount = 0.0
    coupon_code = payload.coupon_code or _cart_coupons.get(cart_id)
    coupon_obj = None
    if coupon_code:
        coupon_result = await db.execute(
            select(Coupon).where(Coupon.code == coupon_code.strip().upper(), Coupon.is_active == True)  # noqa: E712
        )
        coupon_obj = coupon_result.scalar_one_or_none()
        if coupon_obj:
            from datetime import datetime as dt
            now = dt.utcnow()
            valid = True
            if coupon_obj.start_date and now < coupon_obj.start_date:
                valid = False
            if coupon_obj.end_date and now > coupon_obj.end_date:
                valid = False
            if coupon_obj.max_uses and coupon_obj.used_count >= coupon_obj.max_uses:
                valid = False
            if subtotal < coupon_obj.min_order_amount:
                valid = False
            if valid and coupon_obj.max_uses_per_customer and coupon_obj.max_uses_per_customer > 0:
                usage_check = await db.execute(
                    select(func.count(CouponUsage.id)).where(
                        CouponUsage.coupon_id == coupon_obj.id,
                        CouponUsage.user_id == current_user.id,
                    )
                )
                if (usage_check.scalar() or 0) >= coupon_obj.max_uses_per_customer:
                    valid = False
            if valid and coupon_obj.first_order_only:
                prev_orders = await db.execute(
                    select(func.count(Order.id)).where(
                        Order.user_id == current_user.id,
                        Order.status.in_(['Paid', 'Processing', 'Shipped', 'Delivered']),
                    )
                )
                if (prev_orders.scalar() or 0) > 0:
                    valid = False
            if valid:
                if coupon_obj.discount_type == 'percentage':
                    discount = subtotal * (coupon_obj.discount_value / 100)
                else:
                    discount = min(coupon_obj.discount_value, subtotal)
                if coupon_obj.max_discount_amount and coupon_obj.max_discount_amount > 0:
                    discount = min(discount, coupon_obj.max_discount_amount)
                coupon_obj.used_count += 1
                await db.flush()
            else:
                coupon_code = None
                coupon_obj = None
        else:
            coupon_code = None

    # Apply loyalty points redemption
    points_discount = 0.0
    points_used = payload.points_used if payload.points_used else 0
    if points_used and points_used > 0:
        loyalty_result = await db.execute(select(LoyaltyAccount).where(LoyaltyAccount.user_id == current_user.id))
        loyalty_account = loyalty_result.scalar_one_or_none()
        if loyalty_account and loyalty_account.points_balance >= points_used:
            redemption_rate = 100
            try:
                settings_result = await db.execute(
                    select(LoyaltySettings).where(LoyaltySettings.key == 'redemption_rate')
                )
                setting_row = settings_result.scalar_one_or_none()
                if setting_row:
                    redemption_rate = int(setting_row.value)
            except Exception:
                pass
            points_discount = round(points_used / redemption_rate, 2)
            points_discount = min(points_discount, subtotal - discount)
            loyalty_account.points_balance -= points_used
            loyalty_account.total_redeemed += points_used
            await db.add(LoyaltyTransaction(
                user_id=current_user.id, type='redeem', points=-points_used,
                balance_after=loyalty_account.points_balance,
                description=f'Points redeemed for order',
            ))
            await db.flush()
            # Activity log for loyalty points redemption
            await log_activity(
                db=db,
                activity_type="loyalty_points_redeemed",
                description=f"{current_user.full_name or current_user.email} redeemed {points_used} loyalty points",
                entity_type="User",
                entity_id=current_user.id,
                actor_name=current_user.full_name or current_user.email,
                actor_id=current_user.id,
                extra_data={"points": points_used, "discount": points_discount},
            )

    discount = round(discount, 2)
    points_discount = round(points_discount, 2)
    shipping_fee = payload.shipping_fee if payload.shipping_fee else CART_SHIPPING_FEE
    taxable = max(subtotal - discount - points_discount, 0.0)
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
        coupon_code=coupon_code if coupon_code else None,
        coupon_id=coupon_obj.id if coupon_obj else None,
        points_used=points_used,
        points_discount=points_discount,
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

        # Record coupon usage for COD
        if coupon_obj:
            try:
                coupon_usage = CouponUsage(
                    coupon_id=coupon_obj.id,
                    user_id=current_user.id,
                    order_id=order.id,
                    discount_amount=discount,
                )
                db.add(coupon_usage)
                await db.flush()
                # Activity log for coupon usage
                await log_activity(
                    db=db,
                    activity_type="coupon_used",
                    description=f"Coupon {coupon_obj.code} was used on order #{order.order_number}",
                    entity_type="Coupon",
                    entity_id=coupon_obj.id,
                    entity_number=coupon_obj.code,
                    actor_name=current_user.full_name or current_user.email,
                    actor_id=current_user.id,
                    extra_data={"discount": discount, "order_number": order.order_number},
                )
            except Exception:
                pass

        # Award loyalty points for COD (immediate since no payment verification)
        try:
            from app.api.payments import _award_loyalty_points
            await _award_loyalty_points(order, db)
            await db.commit()
        except Exception:
            await db.commit()

    # Audit log
    await log_audit(
        db=db,
        action="CREATE",
        entity_type="Order",
        entity_id=order.id,
        user_id=current_user.id,
        details=f"Created order: {order.order_number} total={total_amount} items={len(order_items)} payment={payload.payment_method}"
    )

    # Activity log
    customer_name = current_user.full_name or current_user.email or "Customer"
    await log_activity(
        db=db,
        activity_type="order_created",
        description=f"New order #{order.order_number} was placed by {customer_name}",
        entity_type="Order",
        entity_id=order.id,
        entity_number=order.order_number,
        actor_name=customer_name,
        actor_id=current_user.id,
        extra_data={"total": total_amount, "items": len(order_items), "payment_method": payload.payment_method},
    )
    await db.commit()

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

    # Activity log
    status_label = order.status.lower().replace("_", " ").title()
    await log_activity(
        db=db,
        activity_type="order_status_changed",
        description=f"Order #{order.order_number} was marked as {status_label}",
        entity_type="Order",
        entity_id=order.id,
        entity_number=order.order_number,
        actor_name=admin.full_name or admin.email or "Admin",
        actor_id=admin.id,
        extra_data={"old_status": old_status, "new_status": order.status},
    )
    await db.commit()

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

    # Activity log
    customer_name = current_user.full_name or current_user.email or "Customer"
    await log_activity(
        db=db,
        activity_type="order_cancelled",
        description=f"Order #{order.order_number} was cancelled by {customer_name}",
        entity_type="Order",
        entity_id=order.id,
        entity_number=order.order_number,
        actor_name=customer_name,
        actor_id=current_user.id,
    )
    await db.commit()

    return order
