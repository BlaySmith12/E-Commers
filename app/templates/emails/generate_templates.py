"""Generate all email templates for the notification system."""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))

def w(name, html):
    # Fix double-braces: f-string escaping produced {{{{ instead of {{
    html = html.replace('{{{{', '{{').replace('}}}}', '}}')
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(html)

def header(title):
    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{title}</title></head>
<body style="margin:0;padding:0;background-color:#F6F9F9;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F6F9F9;">
<tr><td align="center" style="padding:30px 15px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="background-color:#121010;padding:25px 40px;text-align:center;border-radius:8px 8px 0 0;">
<h1 style="color:#ffffff;margin:0;font-size:22px;letter-spacing:1px;">{{{{ store_name }}}}</h1>
</td></tr>
'''

FOOTER = '''
<tr><td style="background-color:#F6F9F9;padding:30px 40px;text-align:center;border-top:1px solid #DBD2CB;border-radius:0 0 8px 8px;">
<p style="color:#999;font-size:12px;margin:0 0 5px;">&copy; {{{{ year }}}} {{{{ store_name }}}}. All rights reserved.</p>
<p style="color:#999;font-size:12px;margin:0;">This is a transactional email regarding your account.</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''

FOOTER_MARKETING = '''
<tr><td style="background-color:#F6F9F9;padding:30px 40px;text-align:center;border-top:1px solid #DBD2CB;border-radius:0 0 8px 8px;">
<p style="color:#999;font-size:12px;margin:0 0 5px;">&copy; {{{{ year }}}} {{{{ store_name }}}}. All rights reserved.</p>
<p style="color:#999;font-size:12px;margin:0 0 5px;"><a href="{{{{ unsubscribe_url }}}}" style="color:#999;">Unsubscribe</a></p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''

def cta_button(url, text):
    return f'<table cellpadding="0" cellspacing="0" style="margin:20px 0;"><tr><td style="background-color:#F2660F;border-radius:6px;"><a href="{url}" style="display:inline-block;padding:14px 40px;color:#ffffff;text-decoration:none;font-weight:bold;font-size:16px;">{text}</a></td></tr></table>'

def info_box(text):
    return f'<p style="color:#121010;font-size:13px;line-height:1.6;margin:20px 0 0;background-color:#F6F9F9;padding:15px;border-radius:6px;border-left:4px solid #F2660F;">{text}</p>'

# 1. password_changed
w("password_changed.html", header("Password Changed") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Password Changed Successfully</h2>
<p style="color:#555;line-height:1.7;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;line-height:1.7;font-size:15px;margin:0 0 20px;">Your password has been successfully changed. You can now log in with your new password.</p>
''' + info_box("If you did NOT make this change, please contact our support team immediately at <a href=\"mailto:{{{{ support_email }}}}\" style=\"color:#F2660F;\">{{{{ support_email }}}}</a> and secure your account.") + '''
</td></tr>
''' + FOOTER)

# 2. order_confirmation
w("order_confirmation.html", header("Order Confirmed") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">Thank You for Your Order!</h2>
<p style="color:#555;font-size:15px;margin:0 0 25px;">Hi {{{{ customer_name }}}}, we've received your order and it's being processed.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 20px;border:1px solid #DBD2CB;border-radius:6px;">
<tr style="background-color:#F6F9F9;">
<td style="font-size:13px;color:#555;font-weight:bold;">Order Number</td>
<td style="font-size:13px;color:#121010;font-weight:bold;">#{{{{ order_number }}}}</td>
</tr>
<tr><td style="font-size:13px;color:#555;">Order Date</td><td style="font-size:13px;color:#121010;">{{{{ order_date }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Status</td><td style="font-size:13px;color:#F2660F;font-weight:bold;">{{{{ order_status }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Payment</td><td style="font-size:13px;color:#121010;">{{{{ payment_status }}}}</td></tr>
</table>
<h3 style="color:#121010;font-size:16px;margin:25px 0 10px;">Order Items</h3>
<table width="100%" cellpadding="8" cellspacing="0" style="border:1px solid #DBD2CB;border-radius:6px;">
<tr style="background-color:#F6F9F9;">
<td style="font-size:12px;color:#555;font-weight:bold;width:50%;">Product</td>
<td style="font-size:12px;color:#555;font-weight:bold;text-align:center;">Qty</td>
<td style="font-size:12px;color:#555;font-weight:bold;text-align:right;">Price</td>
<td style="font-size:12px;color:#555;font-weight:bold;text-align:right;">Total</td>
</tr>
{% for item in items %}
<tr style="border-top:1px solid #eee;">
<td style="font-size:13px;color:#121010;">
{% if item.image %}<img src="{{{{ item.image }}}}" width="50" height="50" style="border-radius:4px;vertical-align:middle;margin-right:8px;">{% endif %}
{{{{ item.name }}}}
{% if item.brand %}<br><small style="color:#999;">{{{{ item.brand }}}}</small>{% endif %}
</td>
<td style="font-size:13px;color:#121010;text-align:center;">{{{{ item.quantity }}}}</td>
<td style="font-size:13px;color:#555;text-align:right;">{{{{ currency }}}} {{{{ item.price }}}}</td>
<td style="font-size:13px;color:#121010;font-weight:bold;text-align:right;">{{{{ currency }}}} {{{{ item.total }}}}</td>
</tr>
{% endfor %}
</table>
<h3 style="color:#121010;font-size:16px;margin:25px 0 10px;">Order Summary</h3>
<table width="100%" cellpadding="6" cellspacing="0">
<tr><td style="font-size:14px;color:#555;">Subtotal</td><td style="font-size:14px;color:#121010;text-align:right;">{{{{ currency }}}} {{{{ subtotal }}}}</td></tr>
{% if discount and discount != "0.00" %}
<tr><td style="font-size:14px;color:#555;">Coupon Discount</td><td style="font-size:14px;color:#198754;text-align:right;">-{{{{ currency }}}} {{{{ discount }}}}</td></tr>
{% endif %}
{% if points_discount %}
<tr><td style="font-size:14px;color:#555;">Loyalty Points Discount</td><td style="font-size:14px;color:#198754;text-align:right;">-{{{{ currency }}}} {{{{ points_discount }}}}</td></tr>
{% endif %}
<tr><td style="font-size:14px;color:#555;">Shipping</td><td style="font-size:14px;color:#121010;text-align:right;">{{{{ currency }}}} {{{{ shipping_fee }}}}</td></tr>
<tr><td style="font-size:14px;color:#555;">Tax</td><td style="font-size:14px;color:#121010;text-align:right;">{{{{ currency }}}} {{{{ tax }}}}</td></tr>
<tr style="border-top:2px solid #121010;">
<td style="font-size:16px;color:#121010;font-weight:bold;padding-top:10px;">Total</td>
<td style="font-size:18px;color:#F2660F;font-weight:bold;text-align:right;padding-top:10px;">{{{{ currency }}}} {{{{ total }}}}</td></tr>
</table>
<h3 style="color:#121010;font-size:16px;margin:25px 0 10px;">Shipping Address</h3>
<p style="color:#555;font-size:14px;line-height:1.6;margin:0;background-color:#F6F9F9;padding:12px;border-radius:4px;">{{{{ shipping_address }}}}</p>
<p style="color:#555;font-size:14px;margin:15px 0;"><strong>Payment Method:</strong> {{{{ payment_method }}}</p>
''' + cta_button("{{{{ order_url }}}}", "View My Order") + '''
</td></tr>
''' + FOOTER)

# 3. payment_success
w("payment_success.html", header("Payment Successful") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<div style="text-align:center;margin:0 0 25px;">
<div style="width:60px;height:60px;border-radius:50%;background-color:#198754;margin:0 auto 15px;line-height:60px;font-size:30px;color:#ffffff;">&#10003;</div>
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">Payment Successful!</h2>
</div>
<p style="color:#555;font-size:15px;margin:0 0 20px;text-align:center;">Hi {{{{ customer_name }}}}, your payment has been confirmed.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr style="background-color:#F6F9F9;"><td style="font-size:13px;color:#555;">Order Number</td><td style="font-size:13px;color:#121010;font-weight:bold;">#{{{{ order_number }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Amount Paid</td><td style="font-size:16px;color:#198754;font-weight:bold;">{{{{ currency }}}} {{{{ amount }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Payment Method</td><td style="font-size:13px;color:#121010;">{{{{ payment_method }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Reference</td><td style="font-size:13px;color:#121010;font-family:monospace;">{{{{ payment_reference }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Date</td><td style="font-size:13px;color:#121010;">{{{{ paid_at }}}}</td></tr>
</table>
''' + cta_button("{{{{ order_url }}}}", "View My Order") + '''
</td></tr>
''' + FOOTER)

# 4. payment_failed
w("payment_failed.html", header("Payment Failed") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<div style="text-align:center;margin:0 0 25px;">
<div style="width:60px;height:60px;border-radius:50%;background-color:#dc3545;margin:0 auto 15px;line-height:60px;font-size:30px;color:#ffffff;">&#10007;</div>
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">Payment Failed</h2>
</div>
<p style="color:#555;font-size:15px;margin:0 0 20px;text-align:center;">Hi {{{{ customer_name }}}}, we were unable to process your payment for order <strong>#{{{{ order_number }}}}</strong>.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Amount</td><td style="font-size:13px;color:#121010;">{{{{ currency }}}} {{{{ amount }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Reason</td><td style="font-size:13px;color:#dc3545;">{{{{ reason }}}}</td></tr>
</table>
<p style="color:#555;font-size:14px;margin:0 0 20px;">Don't worry — your order is still saved. You can try paying again using the button below.</p>
''' + cta_button("{{{{ retry_url }}}}", "Retry Payment") + '''
</td></tr>
''' + FOOTER)

# 5-12: order status emails
for tpl, title, emoji, msg in [
    ("order_processing.html", "Order Processing", "&#9881;", "Your order <strong>#{{{{ order_number }}}}</strong> is now being processed. We'll prepare it for shipment soon."),
    ("order_shipped.html", "Order Shipped", "&#128666;", "Great news! Your order <strong>#{{{{ order_number }}}}</strong> has been shipped.{% if courier %}<br><strong>Carrier:</strong> {{{{ courier }}}}{% endif %}{% if tracking_number %}<br><strong>Tracking:</strong> {{{{ tracking_number }}}}{% endif %}"),
    ("order_out_for_delivery.html", "Out for Delivery", "&#128665;", "Your order <strong>#{{{{ order_number }}}}</strong> is out for delivery! You should receive it today."),
    ("order_delivered.html", "Order Delivered", "&#10003;", "Your order <strong>#{{{{ order_number }}}}</strong> has been delivered! We hope you love your purchase."),
    ("order_on_hold.html", "Order On Hold", "&#9888;", "Your order <strong>#{{{{ order_number }}}}</strong> is temporarily on hold. We'll update you shortly."),
    ("order_refunded.html", "Order Refunded", "&#128176;", "Your order <strong>#{{{{ order_number }}}}</strong> has been refunded. The refund will be processed to your original payment method."),
    ("order_status_update.html", "Order Status Update", "&#128221;", "Your order <strong>#{{{{ order_number }}}}</strong> status has been updated from <strong>{{{{ old_status }}}}</strong> to <strong>{{{{ new_status }}}}</strong>."),
]:
    btn = ""
    if "shipped" in tpl or "delivery" in tpl:
        btn = cta_button("{{{{ order_url }}}}", "Track My Order")
    else:
        btn = cta_button("{{{{ order_url }}}}", "View My Order")
    w(tpl, header(title) + f'''
<tr><td style="background-color:#ffffff;padding:40px;">
<div style="text-align:center;margin:0 0 25px;">
<div style="width:60px;height:60px;border-radius:50%;background-color:#F2660F;margin:0 auto 15px;line-height:60px;font-size:30px;color:#ffffff;">{emoji}</div>
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">{title}</h2>
</div>
<p style="color:#555;font-size:15px;margin:0 0 20px;text-align:center;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;text-align:center;">{msg}</p>
{btn}
</td></tr>
''' + FOOTER)

# 13. order_cancelled
w("order_cancelled.html", header("Order Cancelled") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Order Cancelled</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}}, your order <strong>#{{{{ order_number }}}}</strong> has been cancelled.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Cancelled By</td><td style="font-size:13px;color:#121010;">{{{{ cancelled_by }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Date</td><td style="font-size:13px;color:#121010;">{{{{ cancellation_date }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Order Total</td><td style="font-size:13px;color:#121010;">{{{{ currency }}}} {{{{ total }}}}</td></tr>
</table>
<p style="color:#555;font-size:14px;margin:0;">If a payment was made, a refund will be processed to your original payment method within 5-10 business days.</p>
''' + cta_button("{{{{ order_url }}}}", "View Order Details") + '''
</td></tr>
''' + FOOTER)

# 14. refund
w("refund.html", header("Refund Notification") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Refund {{{{ refund_status }}}}</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 20px;">A refund for order <strong>#{{{{ order_number }}}}</strong> has been processed.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Refund Amount</td><td style="font-size:16px;color:#198754;font-weight:bold;">{{{{ currency }}}} {{{{ refund_amount }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Status</td><td style="font-size:13px;color:#121010;">{{{{ refund_status }}}}</td></tr>
{% if refund_reason %}<tr><td style="font-size:13px;color:#555;">Reason</td><td style="font-size:13px;color:#121010;">{{{{ refund_reason }}}}</td></tr>{% endif %}
{% if refund_reference %}<tr><td style="font-size:13px;color:#555;">Reference</td><td style="font-size:13px;color:#121010;font-family:monospace;">{{{{ refund_reference }}}}</td></tr>{% endif %}
</table>
<p style="color:#555;font-size:14px;margin:0;">The refund will be credited to your original payment method within 5-10 business days.</p>
''' + cta_button("{{{{ order_url }}}}", "View Order") + '''
</td></tr>
''' + FOOTER)

# 15. loyalty_points_earned
w("loyalty_points_earned.html", header("Loyalty Points Earned") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<div style="text-align:center;margin:0 0 25px;">
<div style="width:60px;height:60px;border-radius:50%;background-color:#F2660F;margin:0 auto 15px;line-height:60px;font-size:28px;color:#ffffff;">&#9733;</div>
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">You Earned {{{{ points }}}} Points!</h2>
</div>
<p style="color:#555;font-size:15px;margin:0 0 20px;text-align:center;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;text-align:center;">You've earned <strong>{{{{ points }}}} loyalty points</strong>! {% if description %}{{{{ description }}}}{% endif %}</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Points Earned</td><td style="font-size:16px;color:#F2660F;font-weight:bold;">+{{{{ points }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">New Balance</td><td style="font-size:14px;color:#121010;font-weight:bold;">{{{{ balance_after }}}} points</td></tr>
{% if order_number %}<tr><td style="font-size:13px;color:#555;">Order</td><td style="font-size:13px;color:#121010;">#{{{{ order_number }}}}</td></tr>{% endif %}
</table>
''' + cta_button("{{{{ loyalty_url }}}}", "View My Loyalty Points") + '''
</td></tr>
''' + FOOTER)

# 16. loyalty_points_redeemed
w("loyalty_points_redeemed.html", header("Points Redeemed") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Points Redeemed</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;"><strong>{{{{ points }}}} loyalty points</strong> have been redeemed.{% if description %} {{{{ description }}}}{% endif %}</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Points Redeemed</td><td style="font-size:16px;color:#dc3545;font-weight:bold;">-{{{{ points }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">New Balance</td><td style="font-size:14px;color:#121010;font-weight:bold;">{{{{ balance_after }}}} points</td></tr>
</table>
''' + cta_button("{{{{ loyalty_url }}}}", "View My Loyalty Points") + '''
</td></tr>
''' + FOOTER)

# 17. coupon_used
w("coupon_used.html", header("Coupon Applied") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<div style="text-align:center;margin:0 0 25px;">
<div style="width:60px;height:60px;border-radius:50%;background-color:#198754;margin:0 auto 15px;line-height:60px;font-size:28px;color:#ffffff;">&#10003;</div>
<h2 style="color:#121010;margin:0 0 10px;font-size:24px;">Coupon Applied!</h2>
</div>
<p style="color:#555;font-size:15px;margin:0 0 20px;text-align:center;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;text-align:center;">Coupon <strong>{{{{ coupon_code }}}}</strong> has been applied to your order.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Coupon Code</td><td style="font-size:14px;color:#F2660F;font-weight:bold;">{{{{ coupon_code }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Discount</td><td style="font-size:16px;color:#198754;font-weight:bold;">-{{{{ currency }}}} {{{{ discount_amount }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Order</td><td style="font-size:13px;color:#121010;">#{{{{ order_number }}}}</td></tr>
</table>
''' + cta_button("{{{{ shop_url }}}}", "Continue Shopping") + '''
</td></tr>
''' + FOOTER)

# 18. review_request
w("review_request.html", header("How Was Your Purchase?") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">How Was Your Purchase?</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;">We hope you're enjoying your recent order <strong>#{{{{ order_number }}}}</strong>. Your feedback helps other customers make great choices!</p>
{% for item in items %}
<table width="100%" cellpadding="12" cellspacing="0" style="margin:0 0 15px;border:1px solid #DBD2CB;border-radius:6px;">
<tr>
<td style="width:60px;">
{% if item.image %}<img src="{{{{ item.image }}}}" width="50" height="50" style="border-radius:4px;">{% endif %}
</td>
<td style="font-size:14px;color:#121010;">{{{{ item.name }}}}</td>
<td style="text-align:right;white-space:nowrap;">
<a href="{{{{ base_url }}}}/product/{{{{ item.slug }}}}" style="display:inline-block;padding:8px 16px;background-color:#F2660F;color:#ffffff;text-decoration:none;border-radius:4px;font-size:13px;font-weight:bold;">Leave a Review</a>
</td>
</tr>
</table>
{% endfor %}
</td></tr>
''' + FOOTER)

# 19. newsletter_welcome
w("newsletter_welcome.html", header("You're Subscribed!") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Welcome to Our Newsletter!</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 25px;">You've been subscribed to the <strong>{{ store_name }}</strong> newsletter. Here's what you can expect:</p>
<ul style="color:#555;font-size:15px;line-height:2;margin:0 0 25px;padding-left:20px;">
<li>Exclusive deals and promotions</li>
<li>New product announcements</li>
<li>Seasonal sales and offers</li>
<li>Home living tips and inspiration</li>
</ul>
''' + cta_button("{{{{ store_url }}}}/shop", "Start Shopping") + '''
<p style="color:#999;font-size:12px;margin:20px 0 0;">Don't want these emails? <a href="{{{{ unsubscribe_url }}}}" style="color:#F2660F;">Unsubscribe</a></p>
</td></tr>
''' + FOOTER)

# 20. test_email
w("test_email.html", header("Test Email") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">Test Email</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<p style="color:#555;font-size:15px;margin:0 0 20px;">This is a test email sent from the admin dashboard.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="margin:0 0 25px;border:1px solid #DBD2CB;border-radius:6px;">
<tr><td style="font-size:13px;color:#555;">Email Type</td><td style="font-size:13px;color:#121010;">{{{{ email_type }}}}</td></tr>
<tr><td style="font-size:13px;color:#555;">Sent At</td><td style="font-size:13px;color:#121010;">{{{{ sent_at }}}}</td></tr>
</table>
<p style="color:#198754;font-size:15px;font-weight:bold;text-align:center;margin:20px 0 0;">Email delivery is working correctly!</p>
</td></tr>
''' + FOOTER)

# 21. promotional
w("promotional.html", header("Special Offer") + '''
<tr><td style="background-color:#ffffff;padding:40px;">
<h2 style="color:#121010;margin:0 0 15px;font-size:24px;">{{{{ headline }}}}</h2>
<p style="color:#555;font-size:15px;margin:0 0 20px;">Hi {{{{ customer_name }}}},</p>
<div style="color:#555;font-size:15px;line-height:1.7;margin:0 0 25px;">{{{{ content_html }}}}</div>
{% if cta_url %}
''' + cta_button("{{{{ cta_url }}}}", "{{{{ cta_text | default('Shop Now') }}}}") + '''
{% endif %}
</td></tr>
''' + FOOTER_MARKETING)

print(f"Generated {len(os.listdir(OUT))} email templates in {OUT}")
