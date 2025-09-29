# Database creation
import sqlite3
import os
from datetime import datetime

def create_database():
    """Create the FS25 farming database with all tables"""
    
    # Ensure data directory exists
    os.makedirs('../data', exist_ok=True)
    
    # Connect to database (creates file if doesn't exist)
    conn = sqlite3.connect('../data/fs25_farming.db')
    cursor = conn.cursor()
    
    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")
    
    print("🌾 Creating FS25 Farming Database...")
    
    # Fields table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fields (
            field_id TEXT PRIMARY KEY,
            field_name TEXT NOT NULL,
            size_hectares REAL NOT NULL,
            soil_type TEXT,
            soil_ph REAL,
            organic_matter_percent REAL,
            drainage_rating TEXT,
            slope_percent REAL,
            gps_latitude REAL,
            gps_longitude REAL,
            purchase_price REAL,
            purchase_date DATE,
            current_value REAL,
            stone_percent REAL,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Fields table created")
    
    # Equipment table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            brand TEXT,
            model TEXT,
            category TEXT,
            purchase_price REAL,
            purchase_date DATE,
            current_value REAL,
            fuel_consumption_per_hour REAL,
            maintenance_cost_per_hour REAL,
            total_hours REAL DEFAULT 0,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Equipment table created")
    
    # Crop seasons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crop_seasons (
            season_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id TEXT NOT NULL,
            crop_year INTEGER NOT NULL,
            season_name TEXT,
            crop_type TEXT NOT NULL,
            variety_name TEXT,
            planting_date DATE,
            harvest_date DATE,
            growth_days INTEGER,
            yield_tonnes_per_ha REAL,
            quality_percent REAL,
            weather_impact TEXT,
            disease_pest_notes TEXT,
            rotation_benefit_percent REAL,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (field_id) REFERENCES fields (field_id)
        )
    ''')
    print("✅ Crop seasons table created")
    
    # Field operations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS field_operations (
            operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id TEXT NOT NULL,
            season_id INTEGER,
            operation_date DATE NOT NULL,
            operation_type TEXT NOT NULL,
            equipment_id INTEGER,
            operator_name TEXT,
            hours_worked REAL,
            fuel_used_liters REAL,
            average_speed_kmh REAL,
            weather_conditions TEXT,
            soil_moisture_percent REAL,
            compaction_risk TEXT,
            quality_rating INTEGER CHECK (quality_rating BETWEEN 1 AND 10),
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (field_id) REFERENCES fields (field_id),
            FOREIGN KEY (season_id) REFERENCES crop_seasons (season_id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment_id)
        )
    ''')
    print("✅ Field operations table created")
    
    # Weather events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id TEXT NOT NULL,
            season_id INTEGER,
            event_date DATE NOT NULL,
            weather_type TEXT NOT NULL,
            severity TEXT,
            crop_stage TEXT,
            damage_percent REAL,
            yield_impact_percent REAL,
            quality_impact_percent REAL,
            recovery_time_days INTEGER,
            insurance_claim BOOLEAN DEFAULT 0,
            insurance_amount REAL,
            mitigation_used TEXT,
            lessons_learned TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (field_id) REFERENCES fields (field_id),
            FOREIGN KEY (season_id) REFERENCES crop_seasons (season_id)
        )
    ''')
    print("✅ Weather events table created")
    
    # Insert sample data
    sample_fields = [
        ('F001', 'North Valley', 15.5, 'Clay Loam', 6.8, 3.2, 'Good', 2.1, 
         45.123, -93.456, 185000, '2024-03-15', 185000, 0.5, 'Near water source'),
        ('F002', 'Hill Top', 22.3, 'Sandy Loam', 6.2, 2.8, 'Excellent', 8.5, 
         45.134, -93.467, 267000, '2024-04-22', 267000, 1.2, 'Windy location'),
        ('F003', 'River Bottom', 18.7, 'Silt Loam', 7.1, 4.1, 'Poor', 0.8, 
         45.145, -93.478, 224000, '2024-05-10', 224000, 0.2, 'Flood risk area')
    ]
    
    cursor.executemany('''
        INSERT INTO fields (field_id, field_name, size_hectares, soil_type, soil_ph, 
                           organic_matter_percent, drainage_rating, slope_percent, 
                           gps_latitude, gps_longitude, purchase_price, purchase_date, 
                           current_value, stone_percent, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_fields)
    print("✅ Sample fields added")
    
    conn.commit()
    conn.close()
    
    print("\n🎉 Database setup complete!")
    print("📂 Database location: data/fs25_farming.db")
    print("🚀 Ready to run your Flask app!")

if __name__ == "__main__":
    create_database()