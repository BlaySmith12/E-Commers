import os
from app import create_app, db
from app.models.user import User, Role
from app.models.product import Category, Brand, Product

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

def seed_data():
    with app.app_context():
        print("Starting seeding process...")
        
        # Create Roles
        if not Role.query.first():
            admin_role = Role(name='Administrator', permissions=0xff)
            customer_role = Role(name='Customer', default=True, permissions=0x01)
            db.session.add_all([admin_role, customer_role])
            db.session.commit()
            print("Created roles.")
            
            # Create Admin User
            admin_user = User(username='admin', email='admin@primenest.com', password='password123', role=admin_role)
            db.session.add(admin_user)
            db.session.commit()
            print("Created admin user (admin@primenest.com / password123)")

        # Create Categories
        if not Category.query.first():
            c1 = Category(name='Bathroom', slug='bathroom', description='Premium bathroom fixtures')
            c2 = Category(name='Kitchen', slug='kitchen', description='Luxury kitchen appliances')
            db.session.add_all([c1, c2])
            db.session.commit()
            print("Created categories.")
            
            # Create Brands
            b1 = Brand(name='Grohe', slug='grohe')
            b2 = Brand(name='Kohler', slug='kohler')
            db.session.add_all([b1, b2])
            db.session.commit()
            print("Created brands.")
            
            # Create Products
            p1 = Product(sku='GH-001', name='Premium Thermostatic Shower', slug='premium-thermostatic-shower', 
                         description='Experience luxury.', price=1200.0, discount_price=1020.0, stock=15, 
                         category=c1, brand=b1, is_featured=True)
            db.session.add(p1)
            db.session.commit()
            print("Created products.")
            
        print("Seeding complete!")

if __name__ == '__main__':
    seed_data()
