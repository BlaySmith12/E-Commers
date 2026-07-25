"""Seed database with real plumbing/home improvement products for Asah's Primenest."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import init_db, async_session_maker
from app.models.catalog import Category, Brand, Product, ProductImage, ProductAttribute
from sqlalchemy import select, text

CATEGORIES = [
    {"name": "Bathroom & Sanitary", "slug": "bathroom-sanitary", "description": "Premium showers, faucets & accessories", "image_url": "/static/images/cat_bathroom.png"},
    {"name": "Kitchen & Appliances", "slug": "kitchen-appliances", "description": "Modern sinks, faucets & appliances", "image_url": "/static/images/cat_kitchen.png"},
    {"name": "Plumbing & Fittings", "slug": "plumbing-fittings", "description": "Pipes, valves & connectors", "image_url": "/static/images/cat_plumbing.jpg"},
    {"name": "Tools & Equipment", "slug": "tools-equipment", "description": "Power tools & hand tools", "image_url": "/static/images/cat_tools.jpg"},
    {"name": "Home Appliances", "slug": "home-appliances", "description": "Fans, heaters & more", "image_url": "/static/images/cat_home_appliances.jpg"},
    {"name": "Electrical & Lighting", "slug": "electrical-lighting", "description": "Wiring, switches & fixtures", "image_url": "/static/images/cat_electrical.jpg"},
    {"name": "Hardware & Building Materials", "slug": "hardware-building-materials", "description": "Construction & renovation materials", "image_url": "/static/images/cat_hardware.jpg"},
    {"name": "Home Improvement", "slug": "home-improvement", "description": "Upgrade your living space", "image_url": "/static/images/cat_home_improvement.jpg"},
    {"name": "Water Solutions", "slug": "water-solutions", "description": "Water supply & management", "image_url": "/static/images/cat_water.jpg"},
    {"name": "Garden & Outdoor", "slug": "garden-outdoor", "description": "Outdoor living essentials", "image_url": "/static/images/cat_garden.jpg"},
]

BRANDS = [
    {"name": "Grohe", "slug": "grohe"},
    {"name": "Rinnai", "slug": "rinnai"},
    {"name": "Makita", "slug": "makita"},
    {"name": "Philips", "slug": "philips"},
    {"name": "Toto", "slug": "toto"},
    {"name": "Franke", "slug": "franke"},
    {"name": "Stanley", "slug": "stanley"},
    {"name": "Grundfos", "slug": "grundfos"},
]

PRODUCTS = [
    {
        "sku": "BS-1001", "name": "Grohe Rainshower SmartActive 310", "slug": "grohe-rainshower-smartactive-310",
        "description": "Experience luxurious rainfall showering with the Grohe Rainshower SmartActive 310. Features a 310mm head, GROHE DreamSpray technology, and a sleek chrome finish. Easy to install and built to last.",
        "price": 2850.00, "discount_price": 2450.00, "stock": 25, "is_featured": True, "category": "bathroom-sanitary", "brand": "Grohe",
        "image": "/static/images/products/shower-system.jpg",
        "attrs": [{"name": "Material", "value": "Chrome-plated metal"}, {"name": "Head Size", "value": "310mm"}, {"name": "Spray Type", "value": "Rain"}, {"name": "Installation", "value": "Wall Mounted"}],
    },
    {
        "sku": "BS-1002", "name": "Franke Kubus Kitchen Sink", "slug": "franke-kubus-kitchen-sink",
        "description": "Premium stainless steel undermount kitchen sink from Franke. Features a deep single bowl, SoundGuard undercoating for noise reduction, and a satin finish that resists scratches and stains.",
        "price": 3200.00, "discount_price": 2799.00, "stock": 15, "is_featured": True, "category": "kitchen-appliances", "brand": "Franke",
        "image": "/static/images/products/stainless-sink.jpg",
        "attrs": [{"name": "Material", "value": "Stainless Steel 304"}, {"name": "Bowl", "value": "Single Deep"}, {"name": "Mount Type", "value": "Undermount"}, {"name": "Finish", "value": "Satin"}],
    },
    {
        "sku": "TL-2001", "name": "Makita HR2470 Rotary Drill", "slug": "makita-hr2470-rotary-drill",
        "description": "Professional 780W rotary hammer drill from Makita. SDS-Plus chuck, 3-mode operation (rotation only, hammer only, rotation with hammer), and torque limiter for safety. Ideal for concrete, wood, and metal.",
        "price": 1850.00, "discount_price": None, "stock": 30, "is_featured": True, "category": "tools-equipment", "brand": "Makita",
        "image": "/static/images/products/drill-machine.jpg",
        "attrs": [{"name": "Power", "value": "780W"}, {"name": "Chuck", "value": "SDS-Plus"}, {"name": "Max Drill (Concrete)", "value": "24mm"}, {"name": "Modes", "value": "3-mode"}],
    },
    {
        "sku": "WH-3001", "name": "Rinnai RE160iN Water Heater", "slug": "rinnai-re160in-water-heater",
        "description": "Tankless natural gas water heater with 160,000 BTU. Provides endless hot water for 3-4 simultaneous fixtures. Energy-efficient with built-in digital controls and 15-year heat exchanger warranty.",
        "price": 5800.00, "discount_price": 4999.00, "stock": 10, "is_featured": True, "category": "water-solutions", "brand": "Rinnai",
        "image": "/static/images/products/water-heater.jpg",
        "attrs": [{"name": "Type", "value": "Tankless Gas"}, {"name": "BTU", "value": "160,000"}, {"name": "Capacity", "value": "3-4 Fixtures"}, {"name": "Warranty", "value": "15 Years"}],
    },
    {
        "sku": "EL-4001", "name": "Philips LED Panel Light 60x60", "slug": "philips-led-panel-60x60",
        "description": "Ultra-slim 40W LED panel light with edge-lit technology for uniform, flicker-free illumination. 4000K neutral white, 4000lm output. Perfect for offices, kitchens, and living spaces. 50,000-hour lifespan.",
        "price": 680.00, "discount_price": 549.00, "stock": 50, "is_featured": True, "category": "electrical-lighting", "brand": "Philips",
        "image": "/static/images/products/led-light.jpg",
        "attrs": [{"name": "Wattage", "value": "40W"}, {"name": "Lumens", "value": "4000lm"}, {"name": "Color Temp", "value": "4000K Neutral White"}, {"name": "Lifespan", "value": "50,000 hours"}],
    },
    {
        "sku": "PF-5001", "name": "Toto Ultramax II One-Piece Toilet", "slug": "toto-ultramax-ii-toilet",
        "description": "One-piece elongated toilet with Tornado Flush system for powerful, quiet flushing. CeFIONtect glaze resists waste buildup. Chair-height seating for comfort. WaterSense certified at 1.28 GPF.",
        "price": 4200.00, "discount_price": 3650.00, "stock": 8, "is_featured": True, "category": "bathroom-sanitary", "brand": "Toto",
        "image": "/static/images/cat_bathroom.png",
        "attrs": [{"name": "Flush", "value": "Tornado Flush"}, {"name": "GPF", "value": "1.28"}, {"name": "Bowl Shape", "value": "Elongated"}, {"name": "Glaze", "value": "CeFIONtect"}],
    },
    {
        "sku": "WS-6001", "name": "Grundfos SCALA2 Water Pump", "slug": "grundfos-scala2-water-pump",
        "description": "All-in-one variable speed water pressure pump with built-in electronics. Self-priming, dry-run protection, and Bluetooth connectivity for monitoring via app. Delivers consistent water pressure for homes and light commercial use.",
        "price": 3500.00, "discount_price": None, "stock": 12, "is_featured": True, "category": "water-solutions", "brand": "Grundfos",
        "image": "/static/images/products/pipe-fittings.jpg",
        "attrs": [{"name": "Type", "value": "Self-Priming Pressure Pump"}, {"name": "Max Flow", "value": "3.5 m3/h"}, {"name": "Max Head", "value": "45m"}, {"name": "Protection", "value": "Dry-run, Overheat"}],
    },
    {
        "sku": "TL-2002", "name": "Stanley 133-Piece Mechanics Tool Set", "slug": "stanley-133-piece-tool-set",
        "description": "Comprehensive 133-piece mechanics tool set in a durable blow-molded case. Includes ratchets, sockets, wrenches, screwdrivers, hex keys, and more. Chrome vanadium steel construction for durability.",
        "price": 1200.00, "discount_price": 999.00, "stock": 20, "is_featured": True, "category": "tools-equipment", "brand": "Stanley",
        "image": "/static/images/cat_tools.jpg",
        "attrs": [{"name": "Pieces", "value": "133"}, {"name": "Material", "value": "Chrome Vanadium Steel"}, {"name": "Case", "value": "Blow-molded"}, {"name": "Drive Size", "value": "1/4\" & 3/8\" & 1/2\""}],
    },
]

async def seed():
    await init_db()
    async with async_session_maker() as db:
        async with db.begin():
            # Clear old products
            await db.execute(text("DELETE FROM product_images"))
            await db.execute(text("DELETE FROM product_attributes"))
            await db.execute(text("DELETE FROM product_variants"))
            await db.execute(text("DELETE FROM products"))
            await db.execute(text("DELETE FROM categories"))
            await db.execute(text("DELETE FROM brands"))

            # Seed categories
            cat_map = {}
            for c in CATEGORIES:
                cat = Category(name=c["name"], slug=c["slug"], description=c["description"], image_url=c["image_url"])
                db.add(cat)
                await db.flush()
                cat_map[c["slug"]] = cat.id
                print(f"  + Category: {c['name']}")

            # Seed brands
            brand_map = {}
            for b in BRANDS:
                brand = Brand(name=b["name"], slug=b["slug"])
                db.add(brand)
                await db.flush()
                brand_map[b["name"]] = brand.id
                print(f"  + Brand: {b['name']}")

            # Seed products
            for p in PRODUCTS:
                product = Product(
                    sku=p["sku"], name=p["name"], slug=p["slug"],
                    description=p["description"],
                    price=p["price"], discount_price=p["discount_price"],
                    stock=p["stock"], is_featured=p["is_featured"],
                    status="active",
                    category_id=cat_map.get(p["category"]),
                    brand_id=brand_map.get(p["brand"]),
                )
                db.add(product)
                await db.flush()

                # Add image
                img = ProductImage(image_url=p["image"], is_primary=True, product_id=product.id)
                db.add(img)

                # Add attributes
                for a in p.get("attrs", []):
                    attr = ProductAttribute(name=a["name"], value=a["value"], product_id=product.id)
                    db.add(attr)

                print(f"  + Product: {p['name']}")

        await db.commit()
        print(f"\nSeeded {len(CATEGORIES)} categories, {len(BRANDS)} brands, {len(PRODUCTS)} products!")

if __name__ == "__main__":
    asyncio.run(seed())
