import sqlite3
from datetime import datetime

DATABASE_PATH = '../data/fs25_farming.db'

def add_planting_harvest_tables():
    """Add planting and harvest tracking tables"""
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("🌱 Adding planting and harvest tracking tables...")
    
    # Planting records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS planting_records (
            planting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id TEXT NOT NULL,
            crop_type TEXT NOT NULL,
            variety TEXT,
            planting_date DATE NOT NULL,
            planting_season TEXT,
            expected_harvest_date DATE,
            planted_area_ha REAL,
            
            -- Costs
            seed_cost REAL DEFAULT 0,
            seed_rate TEXT,
            fertilizer_cost REAL DEFAULT 0,
            lime_cost REAL DEFAULT 0,
            labor_cost REAL DEFAULT 0,
            equipment_cost REAL DEFAULT 0,
            fuel_cost REAL DEFAULT 0,
            other_costs REAL DEFAULT 0,
            total_planting_cost REAL DEFAULT 0,
            cost_per_hectare REAL DEFAULT 0,
            
            -- Details
            planting_method TEXT,
            soil_temp_c REAL,
            soil_moisture TEXT,
            weather_conditions TEXT,
            operator_name TEXT,
            notes TEXT,
            
            -- Status
            status TEXT DEFAULT 'Active',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (field_id) REFERENCES fields (field_id)
        )
    ''')
    print("✅ Planting records table created")
    
    # Field maintenance records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS field_maintenance (
            maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id TEXT NOT NULL,
            planting_id INTEGER,
            maintenance_date DATE NOT NULL,
            maintenance_type TEXT NOT NULL,
            
            -- Details
            operation_details TEXT,
            equipment_used TEXT,
            operator_name TEXT,
            hours_worked REAL,
            
            -- Costs
            labor_cost REAL DEFAULT 0,
            equipment_cost REAL DEFAULT 0,
            material_cost REAL DEFAULT 0,
            fuel_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            
            -- Specifics based on type
            area_covered_ha REAL,
            product_used TEXT,
            application_rate TEXT,
            weather_conditions TEXT,
            soil_conditions TEXT,
            
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (field_id) REFERENCES fields (field_id),
            FOREIGN KEY (planting_id) REFERENCES planting_records (planting_id)
        )
    ''')
    print("✅ Field maintenance table created")
    
    # Harvest records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS harvest_records (
            harvest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            planting_id INTEGER NOT NULL,
            field_id TEXT NOT NULL,
            harvest_date DATE NOT NULL,
            harvest_season TEXT,
            
            -- Yield Information
            total_yield_tonnes REAL NOT NULL,
            yield_per_hectare REAL,
            harvested_area_ha REAL,
            
            -- Quality Metrics
            moisture_percent REAL,
            quality_grade TEXT,
            test_weight REAL,
            protein_percent REAL,
            damage_percent REAL,
            
            -- Market Information
            market_price_per_tonne REAL,
            price_premium REAL DEFAULT 0,
            buyer_name TEXT,
            sale_location TEXT,
            
            -- Harvest Details
            harvest_method TEXT,
            equipment_used TEXT,
            operator_name TEXT,
            weather_conditions TEXT,
            
            -- Costs
            harvest_labor_cost REAL DEFAULT 0,
            harvest_equipment_cost REAL DEFAULT 0,
            harvest_fuel_cost REAL DEFAULT 0,
            transport_cost REAL DEFAULT 0,
            drying_cost REAL DEFAULT 0,
            storage_cost REAL DEFAULT 0,
            other_harvest_costs REAL DEFAULT 0,
            total_harvest_cost REAL DEFAULT 0,
            
            -- Financial Summary (calculated)
            gross_revenue REAL,
            total_costs REAL,
            net_profit REAL,
            profit_per_hectare REAL,
            roi_percent REAL,
            break_even_price REAL,
            
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (planting_id) REFERENCES planting_records (planting_id),
            FOREIGN KEY (field_id) REFERENCES fields (field_id)
        )
    ''')
    print("✅ Harvest records table created")
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planting_field ON planting_records(field_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planting_date ON planting_records(planting_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maintenance_field ON field_maintenance(field_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maintenance_planting ON field_maintenance(planting_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_harvest_planting ON harvest_records(planting_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_harvest_field ON harvest_records(field_id)')
    
    print("✅ Indexes created")
    
    conn.commit()
    conn.close()
    
    print("\n🎉 Planting and harvest tracking system ready!")
    print("Tables created:")
    print("  - planting_records: Track all planting operations and costs")
    print("  - field_maintenance: Track plowing, weeding, liming, etc.")
    print("  - harvest_records: Track yields, quality, and ROI")

if __name__ == "__main__":
    add_planting_harvest_tables()