-- Migration: Coupons + Loyalty/Points System
-- Adds missing coupon fields, CouponUsage, LoyaltyAccount, LoyaltyTransaction, LoyaltySettings

BEGIN;

-- 1. Enhance coupons table with new columns
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS max_uses_per_customer INTEGER DEFAULT 0;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS first_order_only BOOLEAN DEFAULT FALSE;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS applicable_product_ids JSON;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS applicable_category_ids JSON;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS applicable_brand_ids JSON;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS customer_eligibility VARCHAR(50) DEFAULT 'all';
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS max_discount_amount FLOAT DEFAULT 0.0;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- 2. Coupon Usage tracking
CREATE TABLE IF NOT EXISTS coupon_usage (
    id SERIAL PRIMARY KEY,
    coupon_id INTEGER NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    discount_amount FLOAT NOT NULL DEFAULT 0.0,
    used_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(coupon_id, order_id)
);
CREATE INDEX IF NOT EXISTS ix_coupon_usage_coupon_id ON coupon_usage(coupon_id);
CREATE INDEX IF NOT EXISTS ix_coupon_usage_user_id ON coupon_usage(user_id);

-- 3. Loyalty Accounts (one per customer)
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    points_balance INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0,
    total_redeemed INTEGER NOT NULL DEFAULT 0,
    total_expired INTEGER NOT NULL DEFAULT 0,
    tier VARCHAR(50) DEFAULT 'Bronze',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_loyalty_accounts_user_id ON loyalty_accounts(user_id);

-- 4. Loyalty Transactions (points ledger)
CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL,  -- earn, redeem, expire, adjust, bonus
    points INTEGER NOT NULL,
    balance_after INTEGER NOT NULL DEFAULT 0,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    description TEXT,
    admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_loyalty_transactions_user_id ON loyalty_transactions(user_id);
CREATE INDEX IF NOT EXISTS ix_loyalty_transactions_type ON loyalty_transactions(type);

-- 5. Loyalty Settings (key-value store for program config)
CREATE TABLE IF NOT EXISTS loyalty_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 6. Add coupon/loyalty columns to orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_id INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS points_used INTEGER DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS points_discount FLOAT DEFAULT 0.0;

-- Insert default loyalty settings
INSERT INTO loyalty_settings (key, value, description) VALUES
('points_per_currency', '10', 'Points earned per 1 GHS spent'),
('redemption_rate', '100', 'Points needed to redeem 1 GHS'),
('min_redemption_points', '500', 'Minimum points to redeem'),
('max_redemption_per_order', '5000', 'Max points redeemable per order'),
('min_order_for_redemption', '50', 'Minimum order amount to use points'),
('max_discount_percent', '50', 'Max percentage of order that points can cover'),
('points_expiry_days', '365', 'Days before points expire (0=never)'),
('signup_bonus_points', '100', 'Points awarded on signup'),
('first_order_bonus_points', '0', 'Bonus points on first order'),
('review_points', '50', 'Points for leaving a product review'),
('tier_bronze_min', '0', 'Minimum points for Bronze tier'),
('tier_silver_min', '1000', 'Minimum points for Silver tier'),
('tier_gold_min', '5000', 'Minimum points for Gold tier'),
('tier_platinum_min', '10000', 'Minimum points for Platinum tier'),
('tier_bronze_multiplier', '1.0', 'Points multiplier for Bronze'),
('tier_silver_multiplier', '1.2', 'Points multiplier for Silver'),
('tier_gold_multiplier', '1.5', 'Points multiplier for Gold'),
('tier_platinum_multiplier', '2.0', 'Points multiplier for Platinum'),
('allow_points_with_coupon', 'true', 'Allow using points with coupon together')
ON CONFLICT (key) DO NOTHING;

COMMIT;
