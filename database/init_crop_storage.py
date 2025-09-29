import sqlite3
from datetime import datetime

DATABASE_PATH = '../data/fs25_farming.db'

def initialize_crop_storage():
    """Initialize crop storage with all FS25 crops"""
    
    # All crops available in FS25
    fs25_crops = [
        # Grains
        ('Wheat', 'Grains', 0, 2000, 220, 'Grain Elevator'),
        ('Barley', 'Grains', 0, 1800, 190, 'Grain Elevator'),
        ('Oat', 'Grains', 0, 1500, 180, 'Grain Elevator'),
        ('Canola', 'Grains', 0, 1200, 380, 'Grain Elevator'),
        ('Sunflower', 'Grains', 0, 1000, 350, 'Oil Mill'),
        ('Soybean', 'Grains', 0, 1500, 385, 'Export Terminal'),
        ('Corn', 'Grains', 0, 2500, 185, 'Grain Elevator'),
        ('Sorghum', 'Grains', 0, 1800, 175, 'Grain Elevator'),
        
        # Rice (FS25 new crop)
        ('Rice', 'Grains', 0, 1200, 425, 'Rice Mill'),
        
        # Root Crops
        ('Potato', 'Root Crops', 0, 800, 320, 'Food Processing Plant'),
        ('Sugar Beet', 'Root Crops', 0, 1200, 45, 'Sugar Factory'),
        
        # New FS25 Vegetables
        ('Spinach', 'Vegetables', 0, 200, 850, 'Fresh Market'),
        ('Green Beans', 'Vegetables', 0, 150, 1200, 'Fresh Market'),
        ('Peas', 'Vegetables', 0, 180, 950, 'Fresh Market'),
        
        # Forage/Silage
        ('Grass', 'Forage', 0, 500, 1800, 'Livestock Farm'),
        ('Hay', 'Forage', 0, 400, 1500, 'Livestock Farm'),
        ('Silage', 'Forage', 0, 800, 1200, 'Livestock Farm'),
        ('Straw', 'Forage', 0, 300, 800, 'Livestock Farm'),
        
        # Tree Products
        ('Wood Chips', 'Forestry', 0, 600, 120, 'Biomass Plant'),
        ('Logs', 'Forestry', 0, 200, 400, 'Sawmill'),
        
        # Animal Products
        ('Milk', 'Animal Products', 0, 50, 650, 'Dairy'),
        ('Wool', 'Animal Products', 0, 20, 1800, 'Textile Mill'),
        ('Eggs', 'Animal Products', 0, 30, 980, 'Food Market'),
        
        # Processed Goods
        ('Flour', 'Processed', 0, 100, 450, 'Bakery'),
        ('Bread', 'Processed', 0, 50, 1200, 'Supermarket'),
        ('Cake', 'Processed', 0, 25, 2200, 'Bakery'),
        ('Butter', 'Processed', 0, 20, 4500, 'Supermarket'),
        ('Cheese', 'Processed', 0, 30, 3200, 'Supermarket'),
        ('Fabric', 'Processed', 0, 40, 2800, 'Clothing Store'),
        ('Clothes', 'Processed', 0, 20, 4200, 'Clothing Store'),
    ]
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crop_storage (
            storage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_name TEXT NOT NULL UNIQUE,
            crop_category TEXT,
            quantity_stored REAL DEFAULT 0,
            storage_capacity REAL DEFAULT 1000,
            current_market_price REAL DEFAULT 0,
            sale_location TEXT DEFAULT 'Local Elevator',
            price_per_unit TEXT DEFAULT 'per tonne',
            last_price_update DATE,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_locations (
            location_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT NOT NULL,
            location_type TEXT,
            distance_km REAL,
            contact_info TEXT,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_name TEXT NOT NULL,
            price REAL NOT NULL,
            sale_location TEXT,
            price_date DATE NOT NULL,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert crops
    for crop_data in fs25_crops:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO crop_storage 
                (crop_name, crop_category, quantity_stored, storage_capacity, 
                 current_market_price, sale_location, last_price_update)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (*crop_data, datetime.now().date()))
        except sqlite3.IntegrityError:
            pass  # Crop already exists
    
    # Insert default sale locations
    sale_locations = [
        ('Grain Elevator', 'Elevator', 15.5, 'Main St Grain Co.'),
        ('Export Terminal', 'Terminal', 45.2, 'Harbor Export LLC'),
        ('Rice Mill', 'Mill', 32.1, 'Valley Rice Processing'),
        ('Food Processing Plant', 'Processing', 28.7, 'AgriFood Industries'),
        ('Sugar Factory', 'Factory', 18.3, 'Sweet Valley Sugar'),
        ('Fresh Market', 'Market', 8.2, 'Farmers Market Co-op'),
        ('Livestock Farm', 'Farm', 12.1, 'Valley Livestock'),
        ('Biomass Plant', 'Plant', 22.5, 'Green Energy Solutions'),
        ('Sawmill', 'Mill', 35.8, 'Timber Works Inc'),
        ('Dairy', 'Processing', 19.4, 'Valley Dairy Co-op'),
        ('Textile Mill', 'Mill', 41.2, 'Heritage Textiles'),
        ('Bakery', 'Retail', 6.8, 'Village Bakery'),
        ('Supermarket', 'Retail', 5.2, 'FreshMart Supermarket'),
    ]
    
    for location in sale_locations:
        cursor.execute('''
            INSERT OR IGNORE INTO sale_locations 
            (location_name, location_type, distance_km, contact_info)
            VALUES (?, ?, ?, ?)
        ''', location)
    
    conn.commit()
    conn.close()
    
    print("✅ Crop storage initialized with all FS25 crops!")
    print(f"📦 Added {len(fs25_crops)} crop types")
    print(f"🏪 Added {len(sale_locations)} sale locations")

if __name__ == "__main__":
    initialize_crop_storage()