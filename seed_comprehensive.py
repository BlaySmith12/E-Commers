"""Comprehensive seed script for ASAH'S PRIMENEST.

Run:  python seed_comprehensive.py

Drops all tables, recreates them, and populates the database with realistic
demo data for development / demo purposes.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker, init_db, engine, Base
from app.models.catalog import (
    Role,
    User,
    Address,
    Category,
    Brand,
    Product,
    ProductVariant,
    ProductAttribute,
    ProductImage,
    ProductReview,
    Order,
    OrderItem,
    Payment,
    SiteSetting,
    AuditLog,
    Collection,
    CollectionProduct,
    Coupon,
    Promotion,
    NewsletterSubscriber,
    Testimonial,
    HeroBanner,
    BlogPost,
    Warehouse,
    Inventory,
)
from app.security import hash_password


# ─── helpers ────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("&", "and").replace("/", "-").replace("'", "")


def rand_dt(months_back: int = 6) -> datetime:
    now = datetime.utcnow()
    delta = timedelta(days=random.randint(1, months_back * 30))
    return now - delta


def pick(lst, n=1):
    items = random.sample(lst, min(n, len(lst)))
    return items[0] if n == 1 else items


# ─── seed data constants ────────────────────────────────────────────────────────

ROLES_DATA = [
    {"name": "Customer", "default": True, "permissions": 1},
    {"name": "Admin", "default": False, "permissions": 255},
    {"name": "Editor", "default": False, "permissions": 7},
    {"name": "Viewer", "default": False, "permissions": 1},
]

ADMINS = [
    {"email": "admin@primenest.com", "username": "admin", "first_name": "Asah", "last_name": "Admin", "phone": "+233240001001", "role_name": "Admin"},
    {"email": "manager@primenest.com", "username": "manager", "first_name": "Kwame", "last_name": "Mensah", "phone": "+233240001002", "role_name": "Admin"},
    {"email": "editor@primenest.com", "username": "editor", "first_name": "Ama", "last_name": "Osei", "phone": "+233240001003", "role_name": "Editor"},
]

CUSTOMERS = [
    {"email": "kwadwo.asante@gmail.com", "first_name": "Kwadwo", "last_name": "Asante", "phone": "+233201234567"},
    {"email": "efua.mensah@gmail.com", "first_name": "Efua", "last_name": "Mensah", "phone": "+233202345678"},
    {"email": "kofi.boateng@yahoo.com", "first_name": "Kofi", "last_name": "Boateng", "phone": "+233203456789"},
    {"email": "adwoa.franklin@gmail.com", "first_name": "Adwoa", "last_name": "Franklin", "phone": "+233204567890"},
    {"email": "kwesi.ankrah@gmail.com", "first_name": "Kwesi", "last_name": "Ankrah", "phone": "+233205678901"},
    {"email": "ama.darko@gmail.com", "first_name": "Ama", "last_name": "Darko", "phone": "+233206789012"},
    {"email": "yaw.agyeman@yahoo.com", "first_name": "Yaw", "last_name": "Agyeman", "phone": "+233207890123"},
    {"email": "abena.osei@gmail.com", "first_name": "Abena", "last_name": "Osei", "phone": "+233208901234"},
    {"email": "nana.adjei@gmail.com", "first_name": "Nana", "last_name": "Adjei", "phone": "+233209012345"},
    {"email": "efi.cudjoe@gmail.com", "first_name": "Efi", "last_name": "Cudjoe", "phone": "+233210123456"},
]

CATEGORIES_DATA = [
    ("Bathroom Fixtures", "Premium bathroom fixtures for modern homes"),
    ("Kitchen Appliances", "Top-quality kitchen appliances and gadgets"),
    ("Plumbing Tools", "Professional-grade plumbing tools"),
    ("Water Heaters", "Reliable water heating solutions"),
    ("Pipes and Fittings", "Durable pipes and fittings for all needs"),
    ("Kitchen Sinks", "Stylish and functional kitchen sinks"),
    ("Faucets and Taps", "Elegant faucets and taps for every room"),
    ("Showers and Accessories", "Complete shower systems and accessories"),
    ("Water Purifiers", "Clean water purification systems"),
    ("Power Tools", "High-performance power tools"),
    ("Hand Tools", "Essential hand tools for every toolkit"),
    ("Electrical Supplies", "Quality electrical components"),
    ("Home Appliances", "Everyday home and kitchen appliances"),
    ("Bathroom Accessories", "Bathroom accessories and organizers"),
    ("Kitchen Storage", "Smart kitchen storage solutions"),
]

BRANDS_DATA = [
    ("Grohe", "grohe"),
    ("Kohler", "kohler"),
    ("Moen", "moen"),
    ("Delta", "delta"),
    ("Rheem", "rheem"),
    ("A.O. Smith", "ao-smith"),
    ("Bosch", "bosch"),
    ("Makita", "makita"),
    ("DeWalt", "dewalt"),
    ("Milwaukee", "milwaukee"),
    ("SharkBite", "sharkbite"),
    ("Geberit", "geberit"),
    ("Toto", "toto"),
    ("American Standard", "american-standard"),
    ("Blanco", "blanco"),
    ("Franke", "franke"),
    ("Rohl", "rohl"),
    ("Brizo", "brizo"),
    ("Pfister", "pfister"),
    ("AquaPure", "aquapure"),
]

# (category_index, brand_index, name, description, price, stock, is_featured, is_trending, sku_prefix)
PRODUCTS_DATA = [
    # ── Bathroom Fixtures (cat 0) ──────────────────────────────────────────
    (0, 0, "Grohe Euroeco Shower Head", "Single-function shower head with EcoJoy technology for water savings.", 450, 30, True, True, "BF-001"),
    (0, 1, "Kohler Highline Classic Toilet", "Two-piece elongated toilet with powerful flushing system.", 1800, 12, True, False, "BF-002"),
    (0, 2, "Moen Adler 4-Inch centreset Faucet", "Chrome bathroom faucet with 2-handle design.", 320, 45, False, True, "BF-003"),
    (0, 3, "Delta Foundations Single Handle Faucet", "Budget-friendly single-handle lavatory faucet.", 280, 60, False, False, "BF-004"),
    (0, 12, "Toto Drake Two-Piece Toilet", "High-efficiency toilet with tornado flush.", 2200, 8, True, False, "BF-005"),
    (0, 13, "American Standard Champion 4 Toilet", "MaximFlush toilet with EverClean surface.", 1650, 15, False, True, "BF-006"),
    (0, 1, "Kohler Archer Rectangle Bathtub", "5-foot drop-in bathtub with lumbar support.", 3500, 5, True, False, "BF-007"),
    (0, 11, "Geberit AquaClean Mera Shower Toilet", "Smart shower toilet with integrated washlet.", 5000, 3, True, True, "BF-008"),
    (0, 0, "Grohe Costa S Mono Basin Mixer", "Single-lever basin mixer in chrome finish.", 520, 25, False, False, "BF-009"),
    (0, 14, "Blanco Subline 500 Undermount Basin", "Silgranit undermount kitchen basin in white.", 1200, 10, False, False, "BF-010"),
    # ── Kitchen Appliances (cat 1) ──────────────────────────────────────────
    (1, 6, "Bosch Series 4 Dishwasher", "Fully integrated dishwasher with 12 place settings.", 3200, 10, True, True, "KA-001"),
    (1, 6, "Bosch Maxx3 Washing Machine", "Front-loading washer with 7 kg capacity.", 2800, 8, False, False, "KA-002"),
    (1, 6, "Bosch Microwave Oven 900W", "Built-in microwave with grill function.", 950, 20, False, True, "KA-003"),
    (1, 6, "Bosch Food Processor", "Multi-functional food processor with 2.3L bowl.", 780, 15, False, False, "KA-004"),
    (1, 6, "Bosch Electric Kettle 1.7L", "Double-wall insulated kettle with auto shut-off.", 250, 40, False, True, "KA-005"),
    (1, 6, "Bosch 2-Slice Toaster", "Pop-up toaster with variable browning control.", 200, 50, False, False, "KA-006"),
    (1, 6, "Bosch Stand Mixer 500W", "Heavy-duty stand mixer with 4.5L stainless bowl.", 1400, 12, True, False, "KA-007"),
    (1, 6, "Bosch Hand Blender Set", "Immersion blender with whisk and chopper attachments.", 350, 25, False, False, "KA-008"),
    (1, 2, "Moen Pot Filler Faucet", "Wall-mount pot filler with dual-joint swing spout.", 1100, 8, True, False, "KA-009"),
    (1, 1, "Kohler Induction Cooktop", "30-inch induction cooktop with 4 zones.", 4200, 5, True, True, "KA-010"),
    # ── Plumbing Tools (cat 2) ──────────────────────────────────────────────
    (2, 10, "SharkBite Push-to-Connect Fitting Set", "Set of 10 push-fit connectors for copper/CPVC.", 380, 35, True, False, "PT-001"),
    (2, 7, "Makita Cordless Pipe Threader", "18V lithium-ion cordless pipe threader for up to 1 inch.", 1600, 10, False, True, "PT-002"),
    (2, 8, "DeWalt Pipe Cutter Kit", "Heavy-duty tube cutter for copper and PVC pipes.", 280, 40, False, False, "PT-003"),
    (2, 9, "Milwaukee M12 ProPEX Expander", "Cordless expansion tool for PEX-A piping systems.", 2400, 7, True, True, "PT-004"),
    (2, 10, "SharkBite Max Fitting Coupler", "3/4 inch push-fit coupler for quick connections.", 85, 60, False, False, "PT-005"),
    (2, 7, "Makita Cordless Impact Wrench", "18V LXT impact wrench for pipe fitting work.", 950, 15, False, True, "PT-006"),
    (2, 8, "DeWalt Adjustable Wrench Set", "3-piece chrome vanadium adjustable wrench set.", 320, 30, False, False, "PT-007"),
    (2, 9, "Milwaukee Tubing Cutter", "Enclosed-feed tubing cutter for tight spaces.", 180, 45, False, False, "PT-008"),
    (2, 10, "SharkBite DZR Brass Ball Valve", "Quarter-turn ball valve, 1 inch push-to-connect.", 220, 25, False, False, "PT-009"),
    (2, 7, "Makita Pipe Wrench 14-Inch", "Heavy-duty cast iron pipe wrench.", 150, 50, False, False, "PT-010"),
    # ── Water Heaters (cat 3) ──────────────────────────────────────────────
    (3, 4, "Rheem Performance Plus 50 Gal", "Gas water heater with 50-gallon capacity.", 2800, 8, True, True, "WH-001"),
    (3, 5, "A.O. Smith Signature 40 Gal", "Electric water heater with 6-year warranty.", 2200, 10, True, False, "WH-002"),
    (3, 4, "Rheem Prestige Hybrid Heat Pump", "Hybrid electric water heater, 65-gallon.", 3800, 4, True, True, "WH-003"),
    (3, 5, "A.O. Smith PowerShot 75 Gal", "High-output commercial-grade gas water heater.", 4500, 3, False, False, "WH-004"),
    (3, 4, "Rheem Professional Classic 30 Gal", "Compact gas water heater for small spaces.", 1500, 12, False, False, "WH-005"),
    (3, 5, "A.O. Smith XE-80 Heat Pump", "Ultra-efficient 80-gallon heat pump water heater.", 4800, 2, False, True, "WH-006"),
    # ── Pipes and Fittings (cat 4) ─────────────────────────────────────────
    (4, 10, "SharkBite 1/2 inch PEX Pipe 100ft", "Flexible PEX-B tubing for potable water.", 350, 40, True, False, "PF-001"),
    (4, 10, "SharkBite 3/4 inch Copper Coupling", "Push-fit copper coupling, bag of 10.", 280, 50, False, False, "PF-002"),
    (4, 10, "SharkBite 90-degree Elbow 1/2 in", "Push-fit brass elbow fitting.", 95, 80, False, False, "PF-003"),
    (4, 10, "SharkBite Tee Fitting 3/4 inch", "Push-fit tee connector for branching lines.", 120, 45, False, False, "PF-004"),
    (4, 10, "SharkBite Male Adapter 1 inch", "Push-fit male threaded adapter.", 110, 35, False, False, "PF-005"),
    (4, 10, "SharkBite CPVC Cement Kit", "Complete CPVC cement and primer set.", 150, 30, False, False, "PF-006"),
    (4, 10, "SharkBite Stainless Steel Clamp 25pk", "Stainless steel PEX crimp clamps, pack of 25.", 200, 55, False, False, "PF-007"),
    (4, 10, "SharkBite Thermostatic Mixing Valve", "Anti-scald mixing valve for water heaters.", 450, 15, True, False, "PF-008"),
    (4, 10, "SharkBite Water Hammer Arrestor", "Screw-on arrestor to prevent pipe banging.", 180, 25, False, False, "PF-009"),
    (4, 10, "SharkBite Expansion PEX-A Tool Set", "Manual expansion tool with 3 heads.", 1200, 8, True, True, "PF-010"),
    # ── Kitchen Sinks (cat 5) ──────────────────────────────────────────────
    (5, 14, "Blanco Silgranit Diamond Sink", "Single-bowl granite composite sink in anthracite.", 1800, 10, True, True, "KS-001"),
    (5, 15, "Franke Kubus KBX 110-50", "Ceramic undermount kitchen sink, white.", 2200, 7, True, False, "KS-002"),
    (5, 14, "Blanco Metro Nano Undermount", "Stainless steel single-bowl undermount sink.", 900, 15, False, True, "KS-003"),
    (5, 15, "Franke Mythos MYX 610-78", "Tectonite double-bowl sink with drainer.", 1500, 9, False, False, "KS-004"),
    (5, 14, "Blanco Precis Medium Bowl", "Workstation-style kitchen sink with ledge.", 2000, 6, True, False, "KS-005"),
    (5, 15, "Franke Onda ONB 610-50", "Classic stainless steel topmount sink.", 750, 20, False, False, "KS-006"),
    # ── Faucets and Taps (cat 6) ───────────────────────────────────────────
    (6, 17, "Brizo Litze Pull-Down Kitchen Faucet", "SmartTouch kitchen faucet in luxe gold.", 1800, 8, True, True, "FT-001"),
    (6, 18, "Pfister Contempra Single-Handle Faucet", "Centerset bathroom faucet in brushed nickel.", 350, 30, False, False, "FT-002"),
    (6, 0, "Grohe Minta Single-Lever Kitchen Tap", "Pull-out spout kitchen mixer in chrome.", 900, 20, True, False, "FT-003"),
    (6, 2, "Moen Align Motionsense Wave Faucet", "Touchless kitchen faucet with MotionSense.", 1400, 10, True, True, "FT-004"),
    (6, 3, "Delta Trinsic Pull-Down Kitchen Faucet", "Touch-Clean spray kitchen faucet in chrome.", 800, 25, False, True, "FT-005"),
    (6, 16, "Rohl Perrin and Rowe Bridge Faucet", "Traditional bridge kitchen faucet in polished chrome.", 2400, 5, True, False, "FT-006"),
    (6, 0, "Grohe Euroeco Cosmopolitan E InfraRed", "Infra-red electronic basin mixer for commercial use.", 1600, 6, False, False, "FT-007"),
    (6, 1, "Kohler Simplice Pull-Down Faucet", "Three-function spray kitchen faucet.", 950, 18, False, True, "FT-008"),
    # ── Showers and Accessories (cat 7) ────────────────────────────────────
    (7, 0, "Grohe Rainshower SmartActive 250", "250mm head shower with ActiveRain spray.", 1200, 15, True, True, "SA-001"),
    (7, 1, "Kohler Hydro-Drome Hand Shower Set", "Multi-function hand shower with hose and bracket.", 450, 25, False, True, "SA-002"),
    (7, 2, "Moen Magnetix Attract 6-Setting Shower", "Magnetic dock hand shower with 6 spray settings.", 380, 30, False, False, "SA-003"),
    (7, 3, "Delta HydroRain Two-In-One Shower", "Dual showerhead system with hand shower.", 600, 12, True, False, "SA-004"),
    (7, 0, "Grohe Rainshower F-Series Shower System", "Complete shower column with thermostat.", 2800, 5, True, True, "SA-005"),
    (7, 17, "Brizo H2Okinetic Tempassent Showerhead", "H2Okinetic 3-spray showerhead, chrome.", 420, 20, False, False, "SA-006"),
    # ── Water Purifiers (cat 8) ────────────────────────────────────────────
    (8, 19, "AquaPure RO+UV Purifier 7L", "7-stage RO+UV water purifier with TDS control.", 1200, 20, True, True, "WP-001"),
    (8, 19, "AquaPure Gravity Water Filter", "Non-electric gravity-based water purifier.", 350, 40, False, False, "WP-002"),
    (8, 19, "AquaPure Ultra UF Water Purifier", "UF membrane purifier with mineral cartridge.", 650, 25, False, True, "WP-003"),
    (8, 19, "AquaPure Hot and Cold Dispenser", "Instant hot and cold water purifier with UV.", 1800, 10, True, False, "WP-004"),
    (8, 19, "AquaPure Under-Sink RO System", "Compact under-sink reverse osmosis system.", 900, 15, False, False, "WP-005"),
    # ── Power Tools (cat 9) ────────────────────────────────────────────────
    (9, 8, "DeWalt 20V MAX Cordless Drill/Driver Kit", "Compact drill with 2 batteries and charger.", 850, 20, True, True, "PW-001"),
    (9, 7, "Makita 18V LXT Circular Saw", "6-1/2 inch cordless circular saw.", 780, 15, True, False, "PW-002"),
    (9, 8, "DeWalt 20V MAX Reciprocating Saw", "Compact reciprocating saw for demolition.", 650, 18, False, True, "PW-003"),
    (9, 7, "Makita 4-1/2 inch Angle Grinder", "9.5 Amp paddle-switch angle grinder.", 420, 25, False, False, "PW-004"),
    (9, 8, "DeWalt 20V MAX Impact Driver Kit", "3-speed impact driver with 2 batteries.", 900, 15, True, False, "PW-005"),
    (9, 9, "Milwaukee M18 FUEL Hammer Drill", "Brushless hammer drill/driver with 2 batteries.", 1100, 12, True, True, "PW-006"),
    (9, 9, "Milwaukee M18 FUEL Oscillating Multi-Tool", "Variable-speed multi-tool with 10 accessories.", 680, 20, False, True, "PW-007"),
    (9, 7, "Makita 7-1/4 inch Miter Saw", "10 Amp compound miter saw with laser guide.", 1200, 8, False, False, "PW-008"),
    (9, 8, "DeWalt 12-inch Miter Saw", "Sliding compound miter saw with XPS shadow line.", 2200, 6, True, False, "PW-009"),
    (9, 9, "Milwaukee M12 FUEL Jigsaw", "Compact cordless jigsaw with tool-free blade change.", 580, 18, False, False, "PW-010"),
    # ── Hand Tools (cat 10) ────────────────────────────────────────────────
    (10, 8, "DeWalt 20-piece Screwdriver Set", "Precision and standard screwdrivers in carry case.", 180, 40, False, False, "HT-001"),
    (10, 7, "Makita 8-inch Locking Pliers Set", "Set of 3 locking pliers (6/8/10 inch).", 220, 30, False, False, "HT-002"),
    (10, 8, "DeWalt 25-foot Tape Measure", "Extra-wide tape with magnetic tip.", 120, 60, False, False, "HT-003"),
    (10, 7, "Makita 16 oz Ball Peen Hammer", "Carbon steel head with fiberglass handle.", 90, 70, False, False, "HT-004"),
    (10, 8, "DeWalt Torpedo Level 9-inch", "Magnetic base torpedo level with vial.", 85, 50, False, False, "HT-005"),
    (10, 9, "Milwaukee 6-in-1 Multi-Bit Driver", "Ratcheting multi-bit driver with 6 bits.", 150, 35, False, True, "HT-006"),
    (10, 8, "DeWalt 3-piece Adjustable Wrench Set", "Chrome-plated adjustable wrenches.", 280, 25, False, False, "HT-007"),
    (10, 7, "Makita 50mm Utility Knife", "Retractable blade utility knife with spare blades.", 65, 55, False, False, "HT-008"),
    (10, 9, "Milwaukee 25-foot Fiber Tape Measure", "High-visibility tape measure with nylon blade.", 130, 40, False, False, "HT-009"),
    (10, 8, "DeWalt Hex Key Allen Wrench Set", "Metric and SAE hex key set with holder.", 110, 45, False, False, "HT-010"),
    # ── Electrical Supplies (cat 11) ────────────────────────────────────────
    (11, 8, "DeWalt 12-Gauge Extension Cord 50ft", "Heavy-duty outdoor extension cord.", 250, 30, False, False, "ES-001"),
    (11, 8, "DeWalt 6-outlet Power Strip with USB", "Surge protector with 6 outlets and 2 USB ports.", 180, 35, False, True, "ES-002"),
    (11, 8, "DeWalt Circuit Breaker 20A", "Single-pole 20 Amp circuit breaker.", 95, 50, False, False, "ES-003"),
    (11, 8, "DeWalt GFCI Outlet 20A", "Self-testing GFCI receptacle, 20 Amp.", 120, 40, False, False, "ES-004"),
    (11, 8, "DeWalt Wire Nuts Assortment Kit", "200-piece wire connector assortment.", 75, 60, False, False, "ES-005"),
    (11, 8, "DeWalt Toggle Switch 15A", "Single-pole toggle switch, 15 Amp.", 45, 80, False, False, "ES-006"),
    (11, 8, "DeWalt Dimmer Switch 600W", "LED/CFL compatible dimmer switch.", 130, 30, False, True, "ES-007"),
    (11, 8, "DeWalt Electrical Tape 5-pack", "Professional grade electrical tape, assorted.", 55, 70, False, False, "ES-008"),
    # ── Home Appliances (cat 12) ───────────────────────────────────────────
    (12, 6, "Bosch Series 6 Refrigerator", "No-frost double-door refrigerator, 351L.", 4200, 5, True, True, "HA-001"),
    (12, 6, "Bosch Expressive Blender 1200W", "High-speed countertop blender with glass jar.", 450, 20, False, True, "HA-002"),
    (12, 6, "Bosch Steam Iron 2400W", "Powerful steam iron with ceramic soleplate.", 280, 30, False, False, "HA-003"),
    (12, 6, "Bosch Air Conditioner 12000 BTU", "Split-type inverter air conditioner.", 3500, 8, True, False, "HA-004"),
    (12, 6, "Bosch Air Purifier HEPA H13", "HEPA H13 air purifier for rooms up to 40m2.", 800, 12, False, True, "HA-005"),
    (12, 6, "Bosch Stand Fan 16 inch", "3-speed pedestal fan with oscillation.", 220, 25, False, False, "HA-006"),
    # ── Bathroom Accessories (cat 13) ──────────────────────────────────────
    (13, 1, "Kohler Verdera Medicine Cabinet", "Mirrored medicine cabinet with soft-close door.", 900, 12, True, False, "BA-001"),
    (13, 1, "Kohler Memoirs Towel Ring", "Polished chrome towel ring, wall-mount.", 180, 30, False, False, "BA-002"),
    (13, 1, "Kohler Memoirs Toilet Paper Holder", "Classic toilet paper holder in chrome.", 120, 40, False, False, "BA-003"),
    (13, 0, "Grohe Essentials Bath Robe Hook", "Single robe hook in chrome finish.", 90, 45, False, False, "BA-004"),
    (13, 0, "Grohe Essentials Towel Bar 24 inch", "Wall-mount towel bar in polished chrome.", 200, 25, False, False, "BA-005"),
    (13, 1, "Kohler Reflekt LED Mirror", "24-inch round LED backlit bathroom mirror.", 650, 10, True, True, "BA-006"),
    (13, 13, "American Standard Tissue Cover", "Freestanding toilet tissue cover.", 85, 50, False, False, "BA-007"),
    (13, 0, "Grohe Shower Caddy Basket", "Chrome wire shower caddy with 2 shelves.", 150, 20, False, False, "BA-008"),
    # ── Kitchen Storage (cat 14) ───────────────────────────────────────────
    (14, 6, "Bosch Bamboo Spice Rack", "Wall-mount bamboo spice rack, 3-tier.", 250, 25, False, False, "KV-001"),
    (14, 6, "Bosch Stainless Steel Canister Set", "Set of 4 airtight stainless steel canisters.", 180, 30, False, False, "KV-002"),
    (14, 6, "Bosch Pull-Out Cabinet Organizer", "Slide-out pantry organizer for base cabinets.", 320, 15, True, False, "KV-003"),
    (14, 6, "Bosch Lazy Susan Turntable", "3-tier rotating lazy susan for corner cabinets.", 200, 20, False, True, "KV-004"),
    (14, 6, "Bosch Drawer Organizer Set", "Bamboo drawer divider and organizer set.", 150, 35, False, False, "KV-005"),
    (14, 6, "Bosch Wall-Mount Pot Rack", "Heavy-duty wall-mount pot rack with hooks.", 280, 10, True, False, "KV-006"),
    # ── Additional Bathroom Fixtures (cat 0) ────────────────────────────────
    (0, 1, "Kohler Cimarron Round-Front Toilet", "Comfort-height two-piece round toilet.", 1400, 14, False, False, "BF-011"),
    (0, 0, "Grohe Eurodisc Joystick Basin Mixer", "Joystick single-lever basin mixer in chrome.", 680, 22, False, False, "BF-012"),
    (0, 1, "Kohler Bellera Undermount Bathroom Sink", "Rectangular ceramic undermount basin, white.", 550, 18, False, True, "BF-013"),
    (0, 13, "American Standard Studio Arc Bathtub", "Freestanding acrylic bathtub with chrome overflow.", 4200, 4, True, False, "BF-014"),
    (0, 12, "Toto Washlet C200 Bidet Seat", "Electronic bidet seat with heated seat and dryer.", 2800, 7, True, True, "BF-015"),
    # ── Additional Kitchen Appliances (cat 1) ────────────────────────────────
    (1, 6, "Bosch Built-In Electric Oven", "60cm single oven with 8 cooking functions.", 3500, 6, True, False, "KA-011"),
    (1, 6, "Bosch 4-Burner Gas Hob", "Tempered glass gas cooktop with auto ignition.", 1200, 14, False, True, "KA-012"),
    (1, 6, "Bosch Range Hood 90cm", "Telescopic pull-out hood with LED lighting.", 1500, 9, False, False, "KA-013"),
    (1, 6, "Bosch Wine Cooler 18 Bottle", "Freestanding dual-zone wine refrigerator.", 1800, 5, False, False, "KA-014"),
    # ── Additional Water Heaters (cat 3) ─────────────────────────────────────
    (3, 4, "Rheem Tankless Water Heater RTEX-13", "On-demand tankless electric water heater, 13kW.", 1800, 10, False, True, "WH-007"),
    (3, 5, "A.O. Smith NEXA 50 Gallon Smart", "WiFi-enabled smart water heater with leak detection.", 3200, 4, True, True, "WH-008"),
    (3, 4, "Rheem Solar Water Heater 200L", "Compact solar water heating system for homes.", 4000, 3, True, False, "WH-009"),
    # ── Additional Kitchen Sinks (cat 5) ─────────────────────────────────────
    (5, 14, "Blanco Quatrus R15 Single Bowl", "R15 zero-radius single bowl stainless sink.", 1100, 12, False, False, "KS-007"),
    (5, 15, "Franke Single Bowl Fragranite Sink", "Fragranite granite composite undermount sink.", 1600, 8, False, True, "KS-008"),
    # ── Additional Faucets and Taps (cat 6) ──────────────────────────────────
    (6, 1, "Kohler Purist Kitchen Sink Faucet", "Single-hole pull-down kitchen faucet, vibrant stainless.", 1200, 14, False, False, "FT-009"),
    (6, 3, "Delta Windemere Centerset Bathroom Faucet", "Two-handle centerset lavatory faucet, chrome.", 280, 35, False, False, "FT-010"),
    (6, 0, "Grohe Concetto Single-Lever Sink Mixer", "Tall single-lever kitchen mixer in supersteel.", 750, 18, False, True, "FT-011"),
    # ── Additional Showers and Accessories (cat 7) ───────────────────────────
    (7, 0, "Grohe Euphoria Thermostatic Shower System", "Complete exposed thermostat with hand shower.", 1800, 8, True, False, "SA-007"),
    (7, 1, "Kohler Response Pressure-balancing Valve", "Single-handle shower valve with anti-scald.", 380, 20, False, False, "SA-008"),
    (7, 2, "Moen Engage Magnetix Hand Shower", "Handheld showerhead with magnetic dock, chrome.", 250, 30, False, True, "SA-009"),
    # ── Additional Power Tools (cat 9) ───────────────────────────────────────
    (9, 7, "Makita 18V LXT Rotary Hammer Drill", "SDS-Plus rotary hammer with 3 modes.", 1300, 9, True, False, "PW-011"),
    (9, 8, "DeWalt 20V MAX Random Orbit Sander", "5-inch cordless random orbit sander.", 550, 18, False, False, "PW-012"),
    (9, 9, "Milwaukee M18 FUEL Table Saw", "10-inch cordless table saw with stand.", 3200, 4, True, True, "PW-013"),
    # ── Additional Hand Tools (cat 10) ───────────────────────────────────────
    (10, 8, "DeWalt 450mm Hacksaw Frame", "Heavy-duty hacksaw with spare blade.", 95, 40, False, False, "HT-011"),
    (10, 7, "Makita Digital Caliper 150mm", "Electronic digital caliper with LCD display.", 180, 25, False, False, "HT-012"),
    (10, 9, "Milwaukee 23-piece Socket Set", "SAE and metric socket set with ratchet.", 350, 15, False, True, "HT-013"),
    # ── Additional Electrical Supplies (cat 11) ──────────────────────────────
    (11, 8, "DeWalt Wire Stripper/Crimper Tool", "Multi-purpose wire stripper for 10-24 AWG.", 160, 30, False, False, "ES-009"),
    (11, 8, "DeWalt Voltage Tester Pen", "Non-contact voltage detector with LED indicator.", 75, 45, False, False, "ES-010"),
    (11, 8, "DeWalt 14/2 NM-B Electrical Wire 250ft", "Romex non-metallic building wire, 14 AWG.", 200, 20, False, False, "ES-011"),
    # ── Additional Home Appliances (cat 12) ──────────────────────────────────
    (12, 6, "Bosch Cordless Vacuum Cleaner", "2-in-1 cordless stick vacuum, 28V lithium.", 650, 15, False, True, "HA-007"),
    (12, 6, "Bosch Electric Pressure Washer 1600W", "High-pressure washer for car and garden cleaning.", 1100, 10, False, False, "HA-008"),
    (12, 6, "Bosch Dehumidifier 20L/day", "Compressor dehumidifier for damp rooms.", 850, 8, False, False, "HA-009"),
]

ADDR_STREETS = [
    "14 Independence Avenue", "23 Liberation Road", "5 Ring Road Central",
    "31 Oxford Street, Osu", "8 Cantonments Road", "42 Labone Junction",
    "17 East Legon Hills", "3 Spintex Road", "29 Tema Community 25",
    "11 Adabraka Market Street", "6 Ashaiman New Town", "36 Airport Residential Area",
    "22 Dzorwulu Avenue", "9 Madina Zongo Junction", "15 Kumasi Adum",
    "48 Takoradi Market Circle", "7 Cape Coast Pedu", "33 Tamale Central",
    "19 Ho Municipal", "25 Koforidua Krobo Road",
]

CITIES = [
    "Accra", "Accra", "Accra", "Accra", "Accra", "Accra",
    "Tema", "Tema", "Kumasi", "Kumasi",
    "Takoradi", "Cape Coast", "Tamale", "Ho", "Koforidua",
    "Accra", "Accra", "Kumasi", "Tema", "Accra",
]

COUPONS_DATA = [
    ("WELCOME10", "percentage", 10.0, "Welcome discount for new customers", 0, 100, 0),
    ("SAVE20", "percentage", 20.0, "20% off your order", 200, 50, 5),
    ("FREESHIP", "fixed", 15.0, "Free standard shipping on any order", 0, 200, 30),
    ("FLAT50", "fixed", 50.0, "Flat GHS 50 off orders above GHS 500", 500, 30, 10),
    ("PREMIUM15", "percentage", 15.0, "Premium collection exclusive discount", 300, 40, 8),
    ("TOOLTIME", "percentage", 12.0, "Power and hand tools special", 0, 60, 0),
    ("SUMMER25", "percentage", 25.0, "Summer clearance sale", 400, 25, 3),
    ("NEWUSER", "fixed", 25.0, "New user signup bonus", 100, 150, 0),
    ("BULK10", "percentage", 10.0, "Bulk order discount for 5+ items", 1000, 20, 0),
    ("FESTIVE30", "percentage", 30.0, "Festive season mega deal", 600, 10, 0),
]

HERO_BANNERS_DATA = [
    ("Premium Plumbing Sale", "Up to 30% off on bathroom fixtures", "/static/images/banners/banner1.png", "/collections/best-sellers", "Shop Now", 1),
    ("Featured Kitchen Appliances", "Upgrade your kitchen with top brands", "/static/images/banners/banner2.png", "/categories/kitchen-appliances", "Explore", 2),
    ("Seasonal Deals", "Save big on water heaters and purifiers", "/static/images/banners/banner3.png", "/categories/water-heaters", "View Deals", 3),
    ("Brand Spotlight: Grohe", "Discover Grohe's premium bathroom range", "/static/images/banners/banner4.png", "/brands/grohe", "Learn More", 4),
    ("New Arrivals", "Check out the latest tools and accessories", "/static/images/banners/banner5.png", "/collections/new-arrivals", "See What's New", 5),
]

TESTIMONIALS_DATA = [
    ("Kwadwo Asante", "Homeowner", "PrimPenest has the best selection of plumbing materials in Accra. I renovated my entire bathroom using their products and the quality is outstanding.", 5, True),
    ("Efua Mensah", "Interior Designer", "As a designer, I need reliable suppliers. PrimPenest never disappoints with their range of premium bathroom fixtures and kitchen appliances.", 5, True),
    ("Kofi Boateng", "Contractor", "I've been sourcing tools and plumbing supplies from PrimPenest for over a year. Their prices are competitive and delivery is always on time.", 5, True),
    ("Adwoa Franklin", "Real Estate Developer", "The Grohe and Kohler products we purchased from PrimPenest for our new apartment complex were top-notch. Highly recommended for bulk orders.", 4, False),
    ("Kwesi Ankrah", "DIY Enthusiast", "Great online shopping experience. I ordered a complete set of DeWalt power tools and they arrived well-packaged and on schedule.", 5, True),
    ("Ama Darko", "Restaurant Owner", "PrimPenest helped us equip our restaurant kitchen with Bosch appliances. Excellent customer service from start to finish.", 5, False),
    ("Yaw Agyeman", "Plumber", "As a professional plumber, I trust PrimPenest for all my fittings and pipe supplies. SharkBite products are always in stock.", 4, True),
    ("Abena Osei", "Home Maker", "I love the water purifier I bought! The AquaPure system gives my family clean and safe drinking water. Thank you PrimPenest!", 5, False),
]

BLOG_POSTS_DATA = [
    ("10 Essential Plumbing Tips Every Homeowner Should Know", "plumbing-tips-homeowner", "Proper plumbing maintenance can save you thousands of cedis in repairs. Here are 10 expert tips from our team at PrimPenest to keep your pipes flowing smoothly and prevent costly emergencies...", "Learn how to maintain your plumbing system, prevent leaks, and save money on repairs with these practical tips from professional plumbers.", True),
    ("How to Choose the Right Water Heater for Your Home", "choose-right-water-heater", "Selecting the perfect water heater depends on your household size, energy preferences, and budget. In this comprehensive guide, we compare tankless vs. tank water heaters, gas vs. electric options, and help you find the best fit for your home in Ghana's climate...", "A comprehensive guide to selecting the perfect water heater for your Ghanaian home, comparing types, capacities, and energy efficiency.", True),
    ("Complete Guide to Kitchen Renovation in Ghana", "kitchen-renovation-guide", "Planning a kitchen renovation? From choosing the right sink and faucet to selecting appliances that match your cooking needs, our step-by-step guide covers everything you need to know about transforming your kitchen into a modern culinary space...", "Everything you need to know about planning and executing a kitchen renovation in Ghana, from budgeting to product selection.", True),
    ("Power Tools Buying Guide: What Every DIYer Needs", "power-tools-buying-guide", "Whether you're a weekend warrior or a seasoned contractor, choosing the right power tools is crucial for project success. We compare top brands like DeWalt, Makita, and Milwaukee to help you make informed decisions...", "Compare top power tool brands and learn what to look for when building your workshop toolkit.", False),
    ("Bathroom Design Trends to Watch in 2026", "bathroom-design-trends-2026", "The bathroom is no longer just a functional space — it's becoming a personal sanctuary. Discover the latest trends in bathroom design, from smart toilets and rainfall showers to minimalist fixtures and spa-inspired aesthetics...", "Explore the latest bathroom design trends and how to incorporate them into your home renovation project.", True),
]

NEWSLETTER_EMAILS = [
    "kwame.tech@gmail.com", "ama.fashion@yahoo.com", "kofi.business@gmail.com",
    "efua.design@hotmail.com", "yaw.info@gmail.com", "abena.style@yahoo.com",
    "nana.build@gmail.com", "adwoa.smart@yahoo.com", "kwesi.pro@gmail.com",
    "efi.creative@hotmail.com", "asah.trades@gmail.com", "kofi.plumbing@yahoo.com",
    "ama.cooks@gmail.com", "yaw.repairs@hotmail.com", "abena.home@gmail.com",
    "nana.electrical@yahoo.com", "kwadwo.tools@gmail.com", "efua.cares@hotmail.com",
    "kofi.fitness@gmail.com", "adwoa.writes@yahoo.com",
]

SITE_SETTINGS_DATA = [
    ("site_name", "ASAH'S PRIMENEST", "The name of the store"),
    ("site_description", "Premium plumbing materials, household appliances, tools, and home improvement products in Ghana", "Store description"),
    ("contact_email", "info@primenest.com", "Primary contact email"),
    ("contact_phone", "+233302123456", "Primary contact phone number"),
    ("currency", "GHS", "Currency code"),
    ("currency_symbol", "GH\u20b5", "Currency symbol"),
    ("shipping_fee", "15.00", "Default shipping fee in GHS"),
    ("tax_rate", "0.15", "Tax rate (15% VAT)"),
    ("free_shipping_threshold", "500.00", "Minimum order for free shipping"),
    ("store_address", "14 Independence Avenue, Accra, Ghana", "Physical store address"),
]

WAREHOUSES_DATA = [
    ("Accra Main Warehouse", "Spintex Road, Accra"),
    ("Kumasi Branch", "Adum, Kumasi"),
    ("Tema Warehouse", "Tema Community 25, Tema"),
]

COLLECTIONS_DATA = [
    ("Best Sellers", "best-sellers", "Our most popular products loved by customers", True),
    ("New Arrivals", "new-arrivals", "Fresh additions to our product catalog", True),
    ("On Sale", "on-sale", "Great deals on quality products", True),
    ("Premium Selection", "premium-selection", "Handpicked premium products for discerning customers", True),
    ("Essentials", "essentials", "Must-have products for every home", True),
]

REVIEW_COMMENTS = [
    "Excellent product! Works exactly as described.",
    "Great quality for the price. Would recommend.",
    "Very satisfied with this purchase. Fast delivery too.",
    "Good product but shipping could be faster.",
    "Top-notch quality. PrimPenest never disappoints.",
    "Installed easily and works perfectly. Happy customer!",
    "Decent product. Does what it's supposed to do.",
    "Amazing build quality. Feels premium.",
    "This exceeded my expectations. Highly recommend!",
    "Solid product with great warranty support.",
    "Perfect fit for my bathroom renovation project.",
    "Professional grade tool. Worth every cedi.",
    "Good value for money. Would buy again.",
    "The finish is beautiful. Very pleased with my choice.",
    "Customer service was helpful in choosing the right product.",
]


# ─── main seeding logic ─────────────────────────────────────────────────────────

async def drop_and_create_tables() -> None:
    print("[1/15] Dropping all tables...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    print("       Tables dropped.")
    print("[1/15] Creating all tables...")
    await init_db()
    print("       Tables created.")


async def seed_roles(session: AsyncSession) -> dict:
    print("[2/15] Seeding roles...")
    roles = {}
    for rd in ROLES_DATA:
        role = Role(name=rd["name"], default=rd["default"], permissions=rd["permissions"])
        session.add(role)
        await session.flush()
        roles[rd["name"]] = role
    print(f"       Created {len(ROLES_DATA)} roles.")
    return roles


async def seed_users(session: AsyncSession, roles: dict) -> list:
    print("[3/15] Seeding users...")
    users = []
    pwd = hash_password("password123")
    # Admins
    for ad in ADMINS:
        user = User(
            email=ad["email"],
            username=ad["username"],
            password_hash=pwd,
            first_name=ad["first_name"],
            last_name=ad["last_name"],
            phone=ad["phone"],
            is_active=True,
            role_id=roles[ad["role_name"]].id,
        )
        session.add(user)
        await session.flush()
        users.append(user)
    # Customers
    for idx, c in enumerate(CUSTOMERS):
        user = User(
            email=c["email"],
            username=f"customer{idx+1}",
            password_hash=pwd,
            first_name=c["first_name"],
            last_name=c["last_name"],
            phone=c["phone"],
            is_active=True,
            role_id=roles["Customer"].id,
        )
        session.add(user)
        await session.flush()
        users.append(user)
    print(f"       Created {len(ADMINS)} admins + {len(CUSTOMERS)} customers = {len(users)} users.")
    return users


async def seed_addresses(session: AsyncSession, users: list) -> list:
    print("[4/15] Seeding addresses...")
    addresses = []
    for i, user in enumerate(users):
        idx = i % len(ADDR_STREETS)
        addr = Address(
            street=ADDR_STREETS[idx],
            city=CITIES[idx],
            state=CITIES[idx],
            country="Ghana",
            zip_code=f"00233",
            is_default=True,
            user_id=user.id,
        )
        session.add(addr)
        await session.flush()
        addresses.append(addr)
    print(f"       Created {len(addresses)} addresses.")
    return addresses


async def seed_categories(session: AsyncSession) -> list:
    print("[5/15] Seeding categories...")
    categories = []
    for name, desc in CATEGORIES_DATA:
        cat = Category(name=name, slug=slugify(name), description=desc)
        session.add(cat)
        await session.flush()
        categories.append(cat)
    print(f"       Created {len(categories)} categories.")
    return categories


async def seed_brands(session: AsyncSession) -> list:
    print("[6/15] Seeding brands...")
    brands = []
    for name, s in BRANDS_DATA:
        brand = Brand(name=name, slug=s, image_url=f"/static/images/brands/{s}.jpg")
        session.add(brand)
        await session.flush()
        brands.append(brand)
    print(f"       Created {len(brands)} brands.")
    return brands


async def seed_products(session: AsyncSession, categories: list, brands: list) -> list:
    print("[7/15] Seeding products (150+)...")
    products = []
    materials = ["Stainless Steel", "Chrome", "Brass", "Ceramic", "ABS Plastic", "Copper", "PVC", "Porcelain", "Bamboo", "Carbon Steel"]
    warranty_options = ["1 Year", "2 Years", "3 Years", "5 Years", "10 Years", "Lifetime"]
    weight_units = ["kg", "lbs"]

    for idx, (cat_idx, brand_idx, name, desc, price, stock, feat, trend, sku_prefix) in enumerate(PRODUCTS_DATA):
        discount = round(price * random.uniform(0.80, 0.95), 2) if random.random() < 0.4 else None
        prod = Product(
            sku=f"PN-{sku_prefix}",
            name=name,
            slug=slugify(name),
            description=desc,
            price=price,
            discount_price=discount,
            stock=stock,
            is_featured=feat,
            is_trending=trend,
            status="active",
            category_id=categories[cat_idx].id,
            brand_id=brands[brand_idx].id,
            created_at=rand_dt(6),
        )
        session.add(prod)
        await session.flush()
        products.append(prod)

        # Product image — map to one of the 8 available static images by category
        category_images = {
            0: "shower-system.jpg",       # Bathroom Fixtures
            1: "kitchen-faucet.jpg",      # Kitchen Appliances
            2: "pipe-fittings.jpg",       # Plumbing Tools
            3: "water-heater.jpg",        # Water Heaters
            4: "pipe-fittings.jpg",       # Pipes and Fittings
            5: "stainless-sink.jpg",      # Kitchen Sinks
            6: "kitchen-faucet.jpg",      # Faucets and Taps
            7: "shower-system.jpg",       # Showers and Accessories
            8: "water-heater.jpg",        # Water Purifiers
            9: "drill-machine.jpg",       # Power Tools
            10: "drill-machine.jpg",      # Hand Tools
            11: "led-light.jpg",          # Electrical Supplies
            12: "water-heater.jpg",       # Home Appliances
            13: "shower-system.jpg",      # Bathroom Accessories
            14: "stainless-sink.jpg",     # Kitchen Storage
        }
        img_file = category_images.get(cat_idx, "pipe-fittings.jpg")
        img = ProductImage(
            image_url=f"/static/images/products/{img_file}",
            is_primary=True,
            alt_text=f"{name} product image",
            product_id=prod.id,
        )
        session.add(img)

        # Product attributes
        mat = random.choice(materials)
        war = random.choice(warranty_options)
        wt = round(random.uniform(0.2, 25.0), 1)
        unit = random.choice(weight_units)
        for attr_name, attr_val in [("Material", mat), ("Warranty", war), ("Weight", f"{wt} {unit}")]:
            session.add(ProductAttribute(product_id=prod.id, name=attr_name, value=attr_val))

        # Variants for some products (colors / sizes)
        if random.random() < 0.35:
            colors = random.sample(["Chrome", "Brushed Nickel", "Matte Black", "Polished Gold", "White", "Gunmetal"], k=random.randint(2, 4))
            for color in colors:
                session.add(ProductVariant(
                    product_id=prod.id,
                    name=f"Color: {color}",
                    sku=f"PN-{sku_prefix}-{color[:3].upper()}",
                    price_modifier=round(random.uniform(-50, 150), 2),
                    stock=random.randint(1, max(1, stock)),
                ))

    print(f"       Created {len(products)} products with images, attributes, and variants.")
    return products


async def seed_warehouses(session: AsyncSession) -> list:
    print("[8/15] Seeding warehouses...")
    warehouses = []
    for name, location in WAREHOUSES_DATA:
        wh = Warehouse(name=name, location=location)
        session.add(wh)
        await session.flush()
        warehouses.append(wh)
    print(f"       Created {len(warehouses)} warehouses.")
    return warehouses


async def seed_inventory(session: AsyncSession, products: list, warehouses: list) -> None:
    print("[8b/15] Seeding inventory...")
    count = 0
    for prod in products:
        assigned_wh = random.sample(warehouses, k=random.randint(1, 3))
        for wh in assigned_wh:
            qty = random.randint(5, 100)
            session.add(Inventory(
                product_id=prod.id,
                warehouse_id=wh.id,
                quantity=qty,
                reserved=random.randint(0, min(5, qty)),
                reorder_level=random.randint(5, 15),
            ))
            count += 1
    print(f"       Created {count} inventory records.")


async def seed_orders(session: AsyncSession, users: list, addresses: list, products: list) -> list:
    print("[9/15] Seeding 50 orders...")
    orders = []
    statuses = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]
    status_weights = [15, 20, 25, 35, 5]
    payment_methods = ["Cash on Delivery", "Mobile Money", "Bank Transfer", "Credit Card"]
    customers = [u for u in users if u.role and u.role.name == "Customer"]

    for i in range(50):
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        customer = pick(customers)
        addr = pick([a for a in addresses if a.user_id == customer.id]) or pick(addresses)
        order_date = rand_dt(3)
        num_items = random.randint(1, 5)
        order_products = random.sample(products, k=min(num_items, len(products)))

        subtotal = 0.0
        order = Order(
            order_number=f"ORD-{order_date.strftime('%Y%m%d')}{i+1:04d}",
            status=status,
            total_amount=0,
            shipping_fee=0.0,
            tax=0.0,
            subtotal=0.0,
            notes=pick(["", "Leave at reception", "Call before delivery", "Weekend delivery preferred", ""]) if random.random() < 0.4 else None,
            user_id=customer.id,
            shipping_address_id=addr.id,
            created_at=order_date,
            updated_at=order_date + timedelta(days=random.randint(0, 14)),
        )
        session.add(order)
        await session.flush()

        for p in order_products:
            qty = random.randint(1, 3)
            item_price = p.effective_price
            subtotal += item_price * qty
            session.add(OrderItem(
                order_id=order.id,
                product_id=p.id,
                quantity=qty,
                price=item_price,
            ))

        shipping = 0.0 if subtotal >= 500 else 15.0
        tax = round(subtotal * 0.15, 2)
        total = round(subtotal + shipping + tax, 2)
        order.subtotal = round(subtotal, 2)
        order.shipping_fee = shipping
        order.tax = tax
        order.total_amount = total

        # Payment for non-cancelled orders
        if status != "Cancelled":
            pay_status = "Completed" if status in ("Delivered", "Shipped", "Processing") else "Pending"
            session.add(Payment(
                transaction_id=f"TXN-{order_date.strftime('%Y%m%d')}{random.randint(10000,99999)}",
                amount=total,
                status=pay_status,
                payment_method=random.choice(payment_methods),
                created_at=order_date,
                order_id=order.id,
            ))

        orders.append(order)
    print(f"       Created {len(orders)} orders with items and payments.")
    return orders


async def seed_reviews(session: AsyncSession, users: list, products: list) -> None:
    print("[10/15] Seeding 30 reviews...")
    customers = [u for u in users if u.role and u.role.name == "Customer"]
    reviewed_products = random.sample(products, k=min(30, len(products)))
    count = 0
    for p in reviewed_products:
        reviewer = pick(customers)
        session.add(ProductReview(
            rating=random.choices([3, 4, 5], weights=[10, 40, 50], k=1)[0],
            comment=pick(REVIEW_COMMENTS),
            created_at=rand_dt(4),
            product_id=p.id,
            user_id=reviewer.id,
        ))
        count += 1
    print(f"       Created {count} reviews.")


async def seed_coupons(session: AsyncSession) -> None:
    print("[11/15] Seeding 10 coupons...")
    now = datetime.utcnow()
    for code, dtype, dval, desc, min_amt, max_uses, used in COUPONS_DATA:
        session.add(Coupon(
            code=code,
            description=desc,
            discount_type=dtype,
            discount_value=dval,
            min_order_amount=min_amt,
            max_uses=max_uses,
            used_count=used,
            is_active=True,
            start_date=now - timedelta(days=random.randint(1, 30)),
            end_date=now + timedelta(days=random.randint(30, 180)),
        ))
    print("       Created 10 coupons.")


async def seed_hero_banners(session: AsyncSession) -> None:
    print("[12/15] Seeding 5 hero banners...")
    for title, sub, img, link, btn, pos in HERO_BANNERS_DATA:
        session.add(HeroBanner(
            title=title,
            subtitle=sub,
            image_url=img,
            link_url=link,
            button_text=btn,
            position=pos,
            is_active=True,
        ))
    print("       Created 5 hero banners.")


async def seed_testimonials(session: AsyncSession) -> None:
    print("[13/15] Seeding 8 testimonials...")
    for name, title, content, rating, featured in TESTIMONIALS_DATA:
        session.add(Testimonial(
            customer_name=name,
            customer_title=title,
            content=content,
            rating=rating,
            is_featured=featured,
            is_active=True,
        ))
    print("       Created 8 testimonials.")


async def seed_blog_posts(session: AsyncSession, users: list) -> None:
    print("[14/15] Seeding 5 blog posts...")
    admin = users[0]
    for title, slug, content, excerpt, published in BLOG_POSTS_DATA:
        session.add(BlogPost(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            image_url=f"/static/images/blog/{slug}.jpg",
            author_id=admin.id,
            is_published=published,
            created_at=rand_dt(6),
        ))
    print("       Created 5 blog posts.")


async def seed_newsletter(session: AsyncSession) -> None:
    print("[15/15] Seeding newsletter subscribers...")
    for email in NEWSLETTER_EMAILS:
        session.add(NewsletterSubscriber(email=email, is_active=True))
    print(f"       Created {len(NEWSLETTER_EMAILS)} subscribers.")


async def seed_site_settings(session: AsyncSession) -> None:
    print("[*]  Seeding site settings...")
    for key, val, desc in SITE_SETTINGS_DATA:
        session.add(SiteSetting(key=key, value=val, description=desc))
    print(f"       Created {len(SITE_SETTINGS_DATA)} site settings.")


async def seed_collections(session: AsyncSession, products: list) -> None:
    print("[*]  Seeding collections...")
    collections = []
    for name, slug, desc, active in COLLECTIONS_DATA:
        col = Collection(name=name, slug=slug, description=desc, is_active=active)
        session.add(col)
        await session.flush()
        collections.append(col)

    # Assign products to collections
    featured = [p for p in products if p.is_featured]
    trending = [p for p in products if p.is_trending]
    discounted = [p for p in products if p.discount_price]
    cheapest = sorted(products, key=lambda p: p.price)[:20]

    assignments = {
        0: featured,         # Best Sellers
        1: trending,         # New Arrivals (trending)
        2: discounted,       # On Sale
        3: featured[:10],    # Premium Selection
        4: cheapest,         # Essentials
    }
    count = 0
    for col_idx, prods in assignments.items():
        if col_idx < len(collections):
            for pos, prod in enumerate(prods[:15]):
                session.add(CollectionProduct(
                    collection_id=collections[col_idx].id,
                    product_id=prod.id,
                    position=pos,
                ))
                count += 1
    print(f"       Created {len(collections)} collections with {count} product links.")


async def seed_notifications(session: AsyncSession, users: list) -> None:
    from app.models.catalog import Notification
    print("[*]  Seeding notifications...")
    notif_templates = [
        ("Welcome!", "Welcome to PrimPenest. Browse our premium collection.", "info"),
        ("Order Confirmed", "Your order has been confirmed and is being processed.", "success"),
        ("Shipment Update", "Your order has been shipped and is on its way.", "info"),
        ("Payment Received", "We have received your payment. Thank you!", "success"),
    ]
    count = 0
    for user in users[:5]:
        title, msg, ntype = pick(notif_templates)
        session.add(Notification(
            user_id=user.id,
            title=title,
            message=msg,
            type=ntype,
            is_read=random.choice([True, False]),
        ))
        count += 1
    print(f"       Created {count} notifications.")


# ─── entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 60)
    print("  ASAH'S PRIMENEST — Comprehensive Database Seed")
    print("=" * 60)
    print()

    try:
        await drop_and_create_tables()
    except Exception as e:
        print(f"ERROR during table setup: {e}")
        sys.exit(1)

    async with async_session_maker() as session:
        try:
            roles = await seed_roles(session)
            users = await seed_users(session, roles)
            addresses = await seed_addresses(session, users)
            categories = await seed_categories(session)
            brands = await seed_brands(session)
            products = await seed_products(session, categories, brands)
            warehouses = await seed_warehouses(session)
            await seed_inventory(session, products, warehouses)
            await seed_orders(session, users, addresses, products)
            await seed_reviews(session, users, products)
            await seed_coupons(session)
            await seed_hero_banners(session)
            await seed_testimonials(session)
            await seed_blog_posts(session, users)
            await seed_newsletter(session)
            await seed_site_settings(session)
            await seed_collections(session, products)
            await seed_notifications(session, users)

            await session.commit()
            print()
            print("=" * 60)
            print("  Seeding completed successfully!")
            print("=" * 60)
            print()
            print("  Login credentials:")
            print("  Admin  : admin@primenest.com  / password123")
            print("  Manager: manager@primenest.com / password123")
            print("  Editor : editor@primenest.com  / password123")
            print("  Customer: kwadwo.asante@gmail.com / password123")
            print()
        except Exception as e:
            await session.rollback()
            print(f"\nERROR during seeding: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
