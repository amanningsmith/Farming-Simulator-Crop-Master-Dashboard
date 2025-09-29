#!/usr/bin/env python3
"""
FS25 Farming Database Web Application
Complete Flask application for managing field performance data
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date
import sqlite3
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
app.secret_key = 'fs25-farming-secret-key-change-this'  # Change this in production!

app.jinja_env.globals.update(min=min, max=max)

DATABASE_PATH = 'data/fs25_farming.db'

def get_db_connection():
    """Get database connection with row factory for easier data access"""
    if not os.path.exists(DATABASE_PATH):
        flash('Database not found! Please run database setup first.', 'error')
        return None
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name: row['field_name']
    return conn

def init_db_check():
    """Check if database exists and has data"""
    if not os.path.exists(DATABASE_PATH):
        return False
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fields'")
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except:
        return False

# =====================================================
# HOME DASHBOARD ROUTE
# =====================================================

@app.route('/')
def index():
    """Home dashboard with key statistics and recent activity"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('setup_required'))
    
    try:
        # Get dashboard statistics
        stats = {}
        
        # Total fields and area
        result = conn.execute('SELECT COUNT(*) as count, SUM(size_hectares) as total_area FROM fields').fetchone()
        stats['total_fields'] = result['count']
        stats['total_area'] = round(result['total_area'] or 0, 1)
        
        # Active crop seasons this year
        current_year = datetime.now().year
        result = conn.execute(
            'SELECT COUNT(*) as count FROM crop_seasons WHERE crop_year = ?', 
            (current_year,)
        ).fetchone()
        stats['active_seasons'] = result['count']
        
        # Total harvested yield this year
        result = conn.execute('''
            SELECT SUM(cs.yield_tonnes_per_ha * f.size_hectares) as total_yield
            FROM crop_seasons cs
            JOIN fields f ON cs.field_id = f.field_id
            WHERE cs.crop_year = ? AND cs.yield_tonnes_per_ha IS NOT NULL
        ''', (current_year,)).fetchone()
        stats['total_yield'] = round(result['total_yield'] or 0, 1)
        
        # Recent operations (last 7 days)
        recent_operations = conn.execute('''
            SELECT fo.operation_date, fo.field_id, f.field_name, fo.operation_type, fo.hours_worked
            FROM field_operations fo
            JOIN fields f ON fo.field_id = f.field_id
            WHERE fo.operation_date >= date('now', '-7 days')
            ORDER BY fo.operation_date DESC, fo.created_date DESC
            LIMIT 10
        ''').fetchall()
        
        # Weather events this year
        result = conn.execute('''
            SELECT COUNT(*) as count FROM weather_events 
            WHERE strftime('%Y', event_date) = ?
        ''', (str(current_year),)).fetchone()
        stats['weather_events'] = result['count']
        
        # Top performing fields (by average yield)
        top_fields = conn.execute('''
            SELECT f.field_name, ROUND(AVG(cs.yield_tonnes_per_ha), 2) as avg_yield, COUNT(cs.season_id) as seasons
            FROM fields f
            JOIN crop_seasons cs ON f.field_id = cs.field_id
            WHERE cs.yield_tonnes_per_ha IS NOT NULL
            GROUP BY f.field_id, f.field_name
            HAVING seasons >= 1
            ORDER BY avg_yield DESC
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return render_template('index.html', 
                             stats=stats, 
                             recent_operations=recent_operations,
                             top_fields=top_fields)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        conn.close()
        return render_template('index.html', stats={}, recent_operations=[], top_fields=[])

# =====================================================
# FIELD MANAGEMENT ROUTES
# =====================================================

@app.route('/fields')
def fields_list():
    """List all fields with summary information"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        fields = conn.execute('''
            SELECT f.field_id, f.field_name, f.size_hectares, f.soil_type, 
                   f.drainage_rating, f.current_value,
                   COUNT(cs.season_id) as total_seasons,
                   ROUND(AVG(cs.yield_tonnes_per_ha), 2) as avg_yield
            FROM fields f
            LEFT JOIN crop_seasons cs ON f.field_id = cs.field_id
            GROUP BY f.field_id, f.field_name, f.size_hectares, f.soil_type, f.drainage_rating, f.current_value
            ORDER BY f.field_id
        ''').fetchall()
        
        conn.close()
        return render_template('fields/list.html', fields=fields)
    
    except Exception as e:
        flash(f'Error loading fields: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('index'))

@app.route('/fields/add', methods=['GET', 'POST'])
def add_field():
    """Add new field"""
    print(f"Add field route called with method: {request.method}")  # Debug
    
    if request.method == 'POST':
        print("Form submitted!")  # Debug
        print(f"Form data: {request.form}")  # Debug
        
        try:
            # Get form data with better error handling
            field_id = request.form.get('field_id', '').strip().upper()
            field_name = request.form.get('field_name', '').strip()
            size_hectares = request.form.get('size_hectares', '')
            
            print(f"Field ID: {field_id}")  # Debug
            print(f"Field Name: {field_name}")  # Debug
            print(f"Size: {size_hectares}")  # Debug
            
            # Validate required fields
            if not field_id:
                flash('Field ID is required!', 'error')
                return render_template('fields/add.html')
            
            if not field_name:
                flash('Field name is required!', 'error')
                return render_template('fields/add.html')
                
            if not size_hectares:
                flash('Field size is required!', 'error')
                return render_template('fields/add.html')
            
            # Convert numeric fields
            try:
                size_hectares = float(size_hectares)
            except ValueError:
                flash('Invalid size value!', 'error')
                return render_template('fields/add.html')
            
            # Get optional fields with defaults
            soil_type = request.form.get('soil_type', '') or None
            soil_ph = float(request.form.get('soil_ph') or 7.0)
            organic_matter = float(request.form.get('organic_matter_percent') or 3.0)
            drainage = request.form.get('drainage_rating', '') or None
            slope = float(request.form.get('slope_percent') or 0)
            
            # GPS coordinates (allow empty)
            gps_lat = request.form.get('gps_latitude', '')
            gps_lon = request.form.get('gps_longitude', '')
            gps_lat = float(gps_lat) if gps_lat else None
            gps_lon = float(gps_lon) if gps_lon else None
            
            # Financial data
            purchase_price = float(request.form.get('purchase_price') or 0)
            purchase_date = request.form.get('purchase_date') or None
            current_value = float(request.form.get('current_value') or purchase_price)
            stone_percent = float(request.form.get('stone_percent') or 0)
            notes = request.form.get('notes', '').strip()
            
            print("About to insert into database...")  # Debug
            
            conn = get_db_connection()
            if not conn:
                flash('Database connection failed!', 'error')
                return render_template('fields/add.html')
            
            conn.execute('''
                INSERT INTO fields (field_id, field_name, size_hectares, soil_type, 
                                   soil_ph, organic_matter_percent, drainage_rating, 
                                   slope_percent, gps_latitude, gps_longitude, 
                                   purchase_price, purchase_date, current_value, 
                                   stone_percent, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                field_id, field_name, size_hectares, soil_type, soil_ph, 
                organic_matter, drainage, slope, gps_lat, gps_lon, 
                purchase_price, purchase_date, current_value, stone_percent, notes
            ))
            
            conn.commit()
            conn.close()
            
            print("Field added successfully!")  # Debug
            flash(f'Field "{field_name}" added successfully!', 'success')
            return redirect(url_for('fields_list'))
            
        except sqlite3.IntegrityError as e:
            print(f"Integrity error: {e}")  # Debug
            flash(f'Field ID "{field_id}" already exists!', 'error')
        except ValueError as e:
            print(f"Value error: {e}")  # Debug
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            print(f"General error: {e}")  # Debug
            flash(f'Error adding field: {str(e)}', 'error')
    
    return render_template('fields/add.html')

@app.route('/fields/<field_id>')
def field_detail(field_id):
    """Show detailed field information with history"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        # Get field info
        field = conn.execute('SELECT * FROM fields WHERE field_id = ?', (field_id,)).fetchone()
        if not field:
            flash('Field not found!', 'error')
            return redirect(url_for('fields_list'))
        
        # Get crop seasons for this field
        seasons = conn.execute('''
            SELECT season_id, crop_year, season_name, crop_type, variety_name,
                   planting_date, harvest_date, yield_tonnes_per_ha, quality_percent, growth_days
            FROM crop_seasons 
            WHERE field_id = ? 
            ORDER BY crop_year DESC, planting_date DESC
        ''', (field_id,)).fetchall()
        
        # Get recent operations
        operations = conn.execute('''
            SELECT operation_date, operation_type, hours_worked, 
                   fuel_used_liters, quality_rating, weather_conditions
            FROM field_operations 
            WHERE field_id = ? 
            ORDER BY operation_date DESC 
            LIMIT 15
        ''', (field_id,)).fetchall()
        
        # Get weather events
        weather_events = conn.execute('''
            SELECT event_date, weather_type, severity, damage_percent, yield_impact_percent
            FROM weather_events 
            WHERE field_id = ? 
            ORDER BY event_date DESC
            LIMIT 10
        ''', (field_id,)).fetchall()
        
        conn.close()
        
        return render_template('fields/detail.html', 
                             field=field, seasons=seasons, 
                             operations=operations, weather_events=weather_events)
    
    except Exception as e:
        flash(f'Error loading field details: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('fields_list'))
    
@app.route('/fields/<field_id>/delete', methods=['POST'])
def delete_field(field_id):
    """Delete a field and all associated data"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        # Check if field exists
        field = conn.execute('SELECT * FROM fields WHERE field_id = ?', (field_id,)).fetchone()
        if not field:
            flash('Field not found!', 'error')
            return redirect(url_for('fields_list'))
        
        # Delete only from tables that exist in your current database
        # Delete crop seasons first (foreign key dependency)
        conn.execute('DELETE FROM crop_seasons WHERE field_id = ?', (field_id,))
        
        # Delete field operations 
        conn.execute('DELETE FROM field_operations WHERE field_id = ?', (field_id,))
        
        # Delete weather events
        conn.execute('DELETE FROM weather_events WHERE field_id = ?', (field_id,))
        
        # Finally delete the field itself
        conn.execute('DELETE FROM fields WHERE field_id = ?', (field_id,))
        
        conn.commit()
        conn.close()
        
        flash(f'Field "{field["field_name"]}" deleted successfully!', 'success')
        return redirect(url_for('fields_list'))
        
    except Exception as e:
        flash(f'Error deleting field: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('fields_list'))

@app.route('/fields/delete-all-sample-data', methods=['POST'])
def delete_all_sample_data():
    """Delete all sample data from the database"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        # Delete all data from existing tables only
        conn.execute('DELETE FROM weather_events')
        conn.execute('DELETE FROM field_operations')
        conn.execute('DELETE FROM crop_seasons')
        conn.execute('DELETE FROM equipment')
        conn.execute('DELETE FROM crop_varieties')
        conn.execute('DELETE FROM fields')
        
        conn.commit()
        conn.close()
        
        flash('All sample data deleted successfully! You can now start fresh.', 'success')
        return redirect(url_for('fields_list'))
        
    except Exception as e:
        flash(f'Error deleting sample data: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('fields_list'))

# =====================================================
# CROP MANAGEMENT ROUTES
# =====================================================

@app.route('/crops')
def crops_list():
    """List all crop seasons"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        seasons = conn.execute('''
            SELECT cs.season_id, cs.field_id, f.field_name, cs.crop_year, cs.season_name,
                   cs.crop_type, cs.variety_name, cs.planting_date, cs.harvest_date,
                   cs.yield_tonnes_per_ha, cs.quality_percent, cs.growth_days
            FROM crop_seasons cs
            JOIN fields f ON cs.field_id = f.field_id
            ORDER BY cs.crop_year DESC, cs.planting_date DESC
        ''').fetchall()
        
        conn.close()
        return render_template('crops/list.html', seasons=seasons)
    
    except Exception as e:
        flash(f'Error loading crop seasons: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('index'))

@app.route('/crops/add', methods=['GET', 'POST'])
def add_crop_season():
    """Add new crop season"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    # Get available fields for dropdown
    fields = conn.execute('SELECT field_id, field_name FROM fields ORDER BY field_name').fetchall()
    
    if request.method == 'POST':
        try:
            crop_data = {
                'field_id': request.form['field_id'],
                'crop_year': int(request.form['crop_year']),
                'season_name': request.form['season_name'],
                'crop_type': request.form['crop_type'],
                'variety_name': request.form['variety_name'].strip(),
                'planting_date': request.form['planting_date']
            }
            
            conn.execute('''
                INSERT INTO crop_seasons (field_id, crop_year, season_name, 
                                         crop_type, variety_name, planting_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                crop_data['field_id'], crop_data['crop_year'], crop_data['season_name'],
                crop_data['crop_type'], crop_data['variety_name'], crop_data['planting_date']
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'{crop_data["crop_type"]} season added successfully!', 'success')
            return redirect(url_for('crops_list'))
            
        except Exception as e:
            flash(f'Error adding crop season: {str(e)}', 'error')
    
    conn.close()
    return render_template('crops/add.html', fields=fields)

@app.route('/crops/<int:season_id>/harvest', methods=['GET', 'POST'])
def record_harvest(season_id):
    """Record harvest results for a crop season"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    # Get season info
    season = conn.execute('''
        SELECT cs.*, f.field_name 
        FROM crop_seasons cs
        JOIN fields f ON cs.field_id = f.field_id
        WHERE cs.season_id = ?
    ''', (season_id,)).fetchone()
    
    if not season:
        flash('Crop season not found!', 'error')
        conn.close()
        return redirect(url_for('crops_list'))
    
    if request.method == 'POST':
        try:
            harvest_data = {
                'harvest_date': request.form['harvest_date'],
                'yield_tonnes_per_ha': float(request.form['yield_tonnes_per_ha']),
                'quality_percent': float(request.form['quality_percent']),
                'weather_impact': request.form.get('weather_impact', '').strip(),
                'disease_pest_notes': request.form.get('disease_pest_notes', '').strip(),
                'notes': request.form.get('notes', '').strip()
            }
            
            # Calculate growth days
            growth_days = None
            if season['planting_date'] and harvest_data['harvest_date']:
                planting = datetime.strptime(season['planting_date'], '%Y-%m-%d').date()
                harvest = datetime.strptime(harvest_data['harvest_date'], '%Y-%m-%d').date()
                growth_days = (harvest - planting).days
            
            conn.execute('''
                UPDATE crop_seasons 
                SET harvest_date = ?, yield_tonnes_per_ha = ?, quality_percent = ?,
                    weather_impact = ?, disease_pest_notes = ?, growth_days = ?, notes = ?
                WHERE season_id = ?
            ''', (
                harvest_data['harvest_date'], harvest_data['yield_tonnes_per_ha'],
                harvest_data['quality_percent'], harvest_data['weather_impact'],
                harvest_data['disease_pest_notes'], growth_days, harvest_data['notes'], season_id
            ))
            
            conn.commit()
            conn.close()
            
            flash('Harvest recorded successfully!', 'success')
            return redirect(url_for('crops_list'))
            
        except Exception as e:
            flash(f'Error recording harvest: {str(e)}', 'error')
    
    conn.close()
    return render_template('crops/harvest.html', season=season)

# =====================================================
# WEATHER EVENTS ROUTES
# =====================================================

@app.route('/weather/add', methods=['GET', 'POST'])
def add_weather_event():
    """Add weather event"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    fields = conn.execute('SELECT field_id, field_name FROM fields ORDER BY field_name').fetchall()
    
    if request.method == 'POST':
        try:
            weather_data = {
                'field_id': request.form['field_id'],
                'event_date': request.form['event_date'],
                'weather_type': request.form['weather_type'],
                'severity': request.form['severity'],
                'crop_stage': request.form.get('crop_stage', '').strip(),
                'damage_percent': float(request.form.get('damage_percent', 0)),
                'yield_impact_percent': float(request.form.get('yield_impact_percent', 0)),
                'insurance_claim': 1 if request.form.get('insurance_claim') == 'on' else 0,
                'lessons_learned': request.form.get('lessons_learned', '').strip()
            }
            
            conn.execute('''
                INSERT INTO weather_events (field_id, event_date, weather_type, severity,
                                           crop_stage, damage_percent, yield_impact_percent,
                                           insurance_claim, lessons_learned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                weather_data['field_id'], weather_data['event_date'], weather_data['weather_type'],
                weather_data['severity'], weather_data['crop_stage'], weather_data['damage_percent'],
                weather_data['yield_impact_percent'], weather_data['insurance_claim'],
                weather_data['lessons_learned']
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'{weather_data["weather_type"]} event logged successfully!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error logging weather event: {str(e)}', 'error')
    
    conn.close()
    return render_template('weather/add.html', fields=fields)

# =====================================================
# CROP STORAGE ROUTES
# =====================================================

@app.route('/storage')
def storage_dashboard():
    """Improved storage dashboard with search/filters using your working base"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        print("🔍 Starting storage dashboard query...")
        
        # First, let's check what data exists (your debug code)
        raw_data = conn.execute('SELECT * FROM crop_storage LIMIT 5').fetchall()
        print(f"📊 Sample raw data: {[dict(row) for row in raw_data]}")
        
        # Check for NULL values (your debug code)
        null_check = conn.execute('''
            SELECT 
                COUNT(*) as total_rows,
                COUNT(quantity_stored) as non_null_quantity,
                COUNT(storage_capacity) as non_null_capacity,
                COUNT(current_market_price) as non_null_price
            FROM crop_storage
        ''').fetchone()
        print(f"🔍 NULL check: {dict(null_check)}")
        
        # Get all crops with storage data - your working query
        print("🔍 Executing main query...")
        crops = conn.execute('''
            SELECT 
                crop_name, 
                COALESCE(crop_category, 'Other') as crop_category,
                COALESCE(quantity_stored, 0.0) as quantity_stored,
                COALESCE(storage_capacity, 1000.0) as storage_capacity,
                COALESCE(current_market_price, 0.0) as current_market_price,
                COALESCE(sale_location, 'Local Elevator') as sale_location
            FROM crop_storage 
            ORDER BY crop_name  -- Changed to name order for better searching
        ''').fetchall()
        
        print(f"📊 Found {len(crops)} crops")
        
        # Process crops and calculate values - your working logic
        processed_crops = []
        for crop in crops:
            try:
                quantity = float(crop['quantity_stored']) if crop['quantity_stored'] is not None else 0.0
                capacity = float(crop['storage_capacity']) if crop['storage_capacity'] is not None else 1000.0
                price = float(crop['current_market_price']) if crop['current_market_price'] is not None else 0.0
                
                # Ensure capacity is never zero to avoid division by zero
                if capacity <= 0:
                    capacity = 1000.0
                
                total_value = quantity * price
                capacity_used = round((quantity / capacity) * 100, 1) if capacity > 0 else 0.0
                
                processed_crop = {
                    'crop_name': crop['crop_name'],
                    'crop_category': crop['crop_category'] or 'Other',
                    'quantity_stored': quantity,
                    'storage_capacity': capacity,
                    'current_market_price': price,
                    'sale_location': crop['sale_location'] or 'Local Elevator',
                    'total_value': total_value,
                    'capacity_used': capacity_used
                }
                processed_crops.append(processed_crop)
                
            except Exception as e:
                print(f"❌ Error processing crop {crop['crop_name']}: {e}")
                print(f"   Crop data: {dict(crop)}")
                continue
        
        print(f"✅ Processed {len(processed_crops)} crops successfully")
        
        # Calculate summary statistics - your working logic
        total_value = sum(crop['total_value'] for crop in processed_crops)
        total_capacity = sum(crop['storage_capacity'] for crop in processed_crops)
        total_stored = sum(crop['quantity_stored'] for crop in processed_crops)
        
        print(f"📊 Summary: Value=${total_value:.2f}, Stored={total_stored:.1f}t, Capacity={total_capacity:.1f}t")
        
        # Get unique categories for filter dropdown (NEW)
        categories = sorted(set(crop['crop_category'] for crop in processed_crops))
        print(f"📂 Categories for filter: {categories}")
        
        conn.close()
        
        # Return data for the new template format
        return render_template('storage/dashboard.html', 
                             crops=processed_crops,  # Changed from crops_by_category to crops
                             categories=categories,   # NEW: for filter dropdown
                             total_value=total_value,
                             total_capacity=total_capacity,
                             total_stored=total_stored)
    
    except Exception as e:
        print(f"❌ Storage dashboard error: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        
        flash(f'Error loading storage dashboard: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('index'))
    
# Also add this route to check your data directly
@app.route('/storage/debug')
def storage_debug():
    """Debug route to check storage data"""
    conn = get_db_connection()
    if not conn:
        return "No database connection"
    
    try:
        # Check table structure
        schema = conn.execute("PRAGMA table_info(crop_storage)").fetchall()
        
        # Check all data
        all_data = conn.execute("SELECT * FROM crop_storage").fetchall()
        
        # Check for problematic records
        problematic = conn.execute('''
            SELECT crop_name, quantity_stored, storage_capacity, current_market_price 
            FROM crop_storage 
            WHERE quantity_stored IS NULL 
               OR storage_capacity IS NULL 
               OR current_market_price IS NULL
        ''').fetchall()
        
        conn.close()
        
        debug_info = {
            'table_schema': [dict(row) for row in schema],
            'total_records': len(all_data),
            'sample_data': [dict(row) for row in all_data[:3]],
            'problematic_records': [dict(row) for row in problematic]
        }
        
        return f"<pre>{str(debug_info)}</pre>"
        
    except Exception as e:
        return f"Debug error: {e}"

@app.route('/storage/edit/<crop_name>', methods=['GET', 'POST'])
def edit_crop_storage(crop_name):
    """Edit crop storage details"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('storage_dashboard'))
    
    # Get sale locations for dropdown
    locations = conn.execute('SELECT location_name FROM sale_locations ORDER BY location_name').fetchall()
    
    if request.method == 'POST':
        try:
            quantity = float(request.form.get('quantity_stored', 0))
            capacity = float(request.form.get('storage_capacity', 1000))
            price = float(request.form.get('current_market_price', 0))
            location = request.form.get('sale_location', '')
            notes = request.form.get('notes', '')
            
            # Record price change in history
            old_price = conn.execute('SELECT current_market_price FROM crop_storage WHERE crop_name = ?', (crop_name,)).fetchone()
            if old_price and old_price['current_market_price'] != price:
                conn.execute('''
                    INSERT INTO price_history (crop_name, price, sale_location, price_date)
                    VALUES (?, ?, ?, ?)
                ''', (crop_name, price, location, datetime.now().date()))
            
            # Update crop storage
            conn.execute('''
                UPDATE crop_storage 
                SET quantity_stored = ?, storage_capacity = ?, current_market_price = ?,
                    sale_location = ?, notes = ?, last_price_update = ?, updated_date = ?
                WHERE crop_name = ?
            ''', (quantity, capacity, price, location, notes, 
                  datetime.now().date(), datetime.now(), crop_name))
            
            conn.commit()
            conn.close()
            
            flash(f'{crop_name} storage updated successfully!', 'success')
            return redirect(url_for('storage_dashboard'))
            
        except Exception as e:
            flash(f'Error updating {crop_name}: {str(e)}', 'error')
    
    # Get crop data
    crop = conn.execute('SELECT * FROM crop_storage WHERE crop_name = ?', (crop_name,)).fetchone()
    if not crop:
        flash('Crop not found!', 'error')
        conn.close()
        return redirect(url_for('storage_dashboard'))
    
    conn.close()
    return render_template('storage/edit.html', crop=crop, locations=locations)

@app.route('/storage/update-quantity', methods=['POST'])
def update_quantity():
    """Quick update quantity via AJAX"""
    try:
        crop_name = request.json.get('crop_name')
        quantity = float(request.json.get('quantity', 0))
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'})
        
        conn.execute('''
            UPDATE crop_storage 
            SET quantity_stored = ?, updated_date = ?
            WHERE crop_name = ?
        ''', (quantity, datetime.now(), crop_name))
        
        # Get updated total value
        crop = conn.execute('''
            SELECT quantity_stored * current_market_price as total_value
            FROM crop_storage WHERE crop_name = ?
        ''', (crop_name,)).fetchone()
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'total_value': crop['total_value'] if crop else 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/storage/price-history/<crop_name>')
def price_history(crop_name):
    """View price history for a crop"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('storage_dashboard'))
    
    try:
        history = conn.execute('''
            SELECT price, sale_location, price_date, notes
            FROM price_history 
            WHERE crop_name = ?
            ORDER BY price_date DESC
            LIMIT 50
        ''', (crop_name,)).fetchall()
        
        crop = conn.execute('SELECT * FROM crop_storage WHERE crop_name = ?', (crop_name,)).fetchone()
        
        conn.close()
        
        return render_template('storage/price_history.html', 
                             crop=crop, history=history)
    
    except Exception as e:
        flash(f'Error loading price history: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('storage_dashboard'))

@app.route('/storage/update-field', methods=['POST'])
def update_storage_field():
    """Update any field in crop storage via AJAX"""
    try:
        crop_name = request.json.get('crop_name')
        field_name = request.json.get('field_name')
        new_value = request.json.get('value')
        
        # Validate field name for security
        allowed_fields = [
            'quantity_stored', 'storage_capacity', 'current_market_price', 
            'sale_location', 'notes'
        ]
        
        if field_name not in allowed_fields:
            return jsonify({'success': False, 'error': 'Invalid field'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'})
        
        # Convert numeric fields
        if field_name in ['quantity_stored', 'storage_capacity', 'current_market_price']:
            try:
                new_value = float(new_value)
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid numeric value'})
        
        # Record price change in history if it's a price update
        if field_name == 'current_market_price':
            old_price = conn.execute(
                'SELECT current_market_price FROM crop_storage WHERE crop_name = ?', 
                (crop_name,)
            ).fetchone()
            
            if old_price and old_price['current_market_price'] != new_value:
                conn.execute('''
                    INSERT INTO price_history (crop_name, price, price_date)
                    VALUES (?, ?, ?)
                ''', (crop_name, new_value, datetime.now().date()))
        
        # Update the field
        conn.execute(f'''
            UPDATE crop_storage 
            SET {field_name} = ?, updated_date = ?
            WHERE crop_name = ?
        ''', (new_value, datetime.now(), crop_name))
        
        # Get updated crop data for response
        crop = conn.execute('''
            SELECT quantity_stored, storage_capacity, current_market_price,
                   (quantity_stored * current_market_price) as total_value,
                   ROUND((quantity_stored / storage_capacity * 100), 1) as capacity_used
            FROM crop_storage WHERE crop_name = ?
        ''', (crop_name,)).fetchone()
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_value': crop['total_value'] if crop else 0,
            'capacity_used': crop['capacity_used'] if crop else 0,
            'formatted_value': f"${crop['total_value']:,.0f}" if crop else "$0"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/storage/get-locations', methods=['GET'])
def get_sale_locations():
    """Get list of sale locations for dropdown"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'})
        
        locations = conn.execute('''
            SELECT DISTINCT sale_location FROM crop_storage 
            WHERE sale_location IS NOT NULL AND sale_location != ''
            ORDER BY sale_location
        ''').fetchall()
        
        # Add some default locations if none exist
        default_locations = [
            'Grain Elevator', 'Export Terminal', 'Rice Mill', 'Food Processing Plant',
            'Sugar Factory', 'Fresh Market', 'Livestock Farm', 'Biomass Plant',
            'Sawmill', 'Dairy', 'Textile Mill', 'Bakery', 'Supermarket'
        ]
        
        location_names = [loc['sale_location'] for loc in locations]
        for default in default_locations:
            if default not in location_names:
                location_names.append(default)
        
        conn.close()
        return jsonify({'success': True, 'locations': sorted(location_names)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    

# =====================================================
# SALE LOCATIONS MANAGEMENT ROUTES
# =====================================================

@app.route('/storage/locations')
def manage_locations():
    """Manage sale locations"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('storage_dashboard'))
    
    try:
        # Get all existing locations from both tables
        locations_from_crops = conn.execute('''
            SELECT DISTINCT sale_location as location_name, 'Used in crops' as source
            FROM crop_storage 
            WHERE sale_location IS NOT NULL AND sale_location != ''
            ORDER BY sale_location
        ''').fetchall()
        
        # Check if sale_locations table exists
        table_exists = conn.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='sale_locations'
        ''').fetchone()
        
        if table_exists:
            # Get locations from dedicated table
            saved_locations = conn.execute('''
                SELECT location_id, location_name, location_type, distance_km, contact_info, notes
                FROM sale_locations 
                ORDER BY location_name
            ''').fetchall()
        else:
            saved_locations = []
        
        # Combine and deduplicate
        all_locations = {}
        
        # Add saved locations first
        for loc in saved_locations:
            all_locations[loc['location_name']] = {
                'location_id': loc['location_id'],
                'location_name': loc['location_name'],
                'location_type': loc['location_type'],
                'distance_km': loc['distance_km'],
                'contact_info': loc['contact_info'],
                'notes': loc['notes'],
                'in_use': False,
                'source': 'Saved'
            }
        
        # Mark which ones are actually used
        for loc in locations_from_crops:
            if loc['location_name'] in all_locations:
                all_locations[loc['location_name']]['in_use'] = True
            else:
                # Add locations that are used but not formally saved
                all_locations[loc['location_name']] = {
                    'location_id': None,
                    'location_name': loc['location_name'],
                    'location_type': 'Unknown',
                    'distance_km': None,
                    'contact_info': None,
                    'notes': None,
                    'in_use': True,
                    'source': 'Used in crops'
                }
        
        final_locations = list(all_locations.values())
        
        conn.close()
        
        return render_template('storage/manage_locations.html', 
                             locations=final_locations)
    
    except Exception as e:
        flash(f'Error loading locations: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('storage_dashboard'))

@app.route('/storage/locations/add', methods=['POST'])
def add_location():
    """Add new sale location"""
    try:
        location_name = request.form.get('location_name', '').strip()
        location_type = request.form.get('location_type', '').strip()
        distance_km = request.form.get('distance_km', '')
        contact_info = request.form.get('contact_info', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not location_name:
            flash('Location name is required!', 'error')
            return redirect(url_for('manage_locations'))
        
        # Convert distance to float
        try:
            distance_km = float(distance_km) if distance_km else None
        except ValueError:
            distance_km = None
        
        conn = get_db_connection()
        if not conn:
            return redirect(url_for('manage_locations'))
        
        # Create table if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sale_locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT NOT NULL UNIQUE,
                location_type TEXT,
                distance_km REAL,
                contact_info TEXT,
                notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert new location
        conn.execute('''
            INSERT INTO sale_locations (location_name, location_type, distance_km, contact_info, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (location_name, location_type, distance_km, contact_info, notes))
        
        conn.commit()
        conn.close()
        
        flash(f'Location "{location_name}" added successfully!', 'success')
        return redirect(url_for('manage_locations'))
        
    except sqlite3.IntegrityError:
        flash(f'Location "{location_name}" already exists!', 'error')
        return redirect(url_for('manage_locations'))
    except Exception as e:
        flash(f'Error adding location: {str(e)}', 'error')
        return redirect(url_for('manage_locations'))

@app.route('/storage/locations/<int:location_id>/edit', methods=['POST'])
def edit_location(location_id):
    """Edit existing sale location"""
    try:
        location_name = request.form.get('location_name', '').strip()
        location_type = request.form.get('location_type', '').strip()
        distance_km = request.form.get('distance_km', '')
        contact_info = request.form.get('contact_info', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not location_name:
            flash('Location name is required!', 'error')
            return redirect(url_for('manage_locations'))
        
        # Convert distance to float
        try:
            distance_km = float(distance_km) if distance_km else None
        except ValueError:
            distance_km = None
        
        conn = get_db_connection()
        if not conn:
            return redirect(url_for('manage_locations'))
        
        # Get old location name for updating crops
        old_location = conn.execute(
            'SELECT location_name FROM sale_locations WHERE location_id = ?', 
            (location_id,)
        ).fetchone()
        
        if not old_location:
            flash('Location not found!', 'error')
            conn.close()
            return redirect(url_for('manage_locations'))
        
        # Update location
        conn.execute('''
            UPDATE sale_locations 
            SET location_name = ?, location_type = ?, distance_km = ?, 
                contact_info = ?, notes = ?
            WHERE location_id = ?
        ''', (location_name, location_type, distance_km, contact_info, notes, location_id))
        
        # Update crops that use this location if name changed
        if old_location['location_name'] != location_name:
            conn.execute('''
                UPDATE crop_storage 
                SET sale_location = ? 
                WHERE sale_location = ?
            ''', (location_name, old_location['location_name']))
        
        conn.commit()
        conn.close()
        
        flash(f'Location "{location_name}" updated successfully!', 'success')
        return redirect(url_for('manage_locations'))
        
    except sqlite3.IntegrityError:
        flash(f'Location name "{location_name}" already exists!', 'error')
        return redirect(url_for('manage_locations'))
    except Exception as e:
        flash(f'Error updating location: {str(e)}', 'error')
        return redirect(url_for('manage_locations'))

@app.route('/storage/locations/<int:location_id>/delete', methods=['POST'])
def delete_location(location_id):
    """Delete sale location"""
    try:
        conn = get_db_connection()
        if not conn:
            return redirect(url_for('manage_locations'))
        
        # Get location name and check if it's in use
        location = conn.execute(
            'SELECT location_name FROM sale_locations WHERE location_id = ?', 
            (location_id,)
        ).fetchone()
        
        if not location:
            flash('Location not found!', 'error')
            conn.close()
            return redirect(url_for('manage_locations'))
        
        # Check if location is being used
        usage_count = conn.execute(
            'SELECT COUNT(*) as count FROM crop_storage WHERE sale_location = ?', 
            (location['location_name'],)
        ).fetchone()
        
        if usage_count['count'] > 0:
            flash(f'Cannot delete "{location["location_name"]}" - it is being used by {usage_count["count"]} crops!', 'error')
            conn.close()
            return redirect(url_for('manage_locations'))
        
        # Delete location
        conn.execute('DELETE FROM sale_locations WHERE location_id = ?', (location_id,))
        conn.commit()
        conn.close()
        
        flash(f'Location "{location["location_name"]}" deleted successfully!', 'success')
        return redirect(url_for('manage_locations'))
        
    except Exception as e:
        flash(f'Error deleting location: {str(e)}', 'error')
        return redirect(url_for('manage_locations'))

@app.route('/storage/locations/bulk-add', methods=['POST'])
def bulk_add_locations():
    """Add multiple default locations"""
    try:
        default_locations = [
            ('Grain Elevator', 'Elevator', 15.5, 'Main Street Grain Co.'),
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
        
        conn = get_db_connection()
        if not conn:
            return redirect(url_for('manage_locations'))
        
        # Create table if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sale_locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT NOT NULL UNIQUE,
                location_type TEXT,
                distance_km REAL,
                contact_info TEXT,
                notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        added_count = 0
        for location in default_locations:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO sale_locations 
                    (location_name, location_type, distance_km, contact_info)
                    VALUES (?, ?, ?, ?)
                ''', location)
                if conn.lastrowid:  # If a row was actually inserted
                    added_count += 1
            except:
                continue
        
        conn.commit()
        conn.close()
        
        flash(f'Added {added_count} default locations!', 'success')
        return redirect(url_for('manage_locations'))
        
    except Exception as e:
        flash(f'Error adding default locations: {str(e)}', 'error')
        return redirect(url_for('manage_locations'))
    


# =====================================================
# REPORTS AND ANALYTICS ROUTES
# =====================================================

@app.route('/reports')
def reports_dashboard():
    """Reports dashboard with performance summaries"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        # Field performance summary
        field_performance = conn.execute('''
            SELECT f.field_id, f.field_name, f.size_hectares,
                   COUNT(cs.season_id) as total_seasons,
                   ROUND(AVG(cs.yield_tonnes_per_ha), 2) as avg_yield,
                   ROUND(AVG(cs.quality_percent), 1) as avg_quality,
                   ROUND(SUM(cs.yield_tonnes_per_ha * f.size_hectares), 1) as total_production
            FROM fields f
            LEFT JOIN crop_seasons cs ON f.field_id = cs.field_id
            WHERE cs.yield_tonnes_per_ha IS NOT NULL
            GROUP BY f.field_id, f.field_name, f.size_hectares
            ORDER BY avg_yield DESC
        ''').fetchall()
        
        # Crop performance by type
        crop_performance = conn.execute('''
            SELECT crop_type, COUNT(*) as total_seasons,
                   ROUND(AVG(yield_tonnes_per_ha), 2) as avg_yield,
                   ROUND(AVG(quality_percent), 1) as avg_quality,
                   ROUND(AVG(growth_days), 0) as avg_growth_days,
                   ROUND(MIN(yield_tonnes_per_ha), 2) as min_yield,
                   ROUND(MAX(yield_tonnes_per_ha), 2) as max_yield
            FROM crop_seasons
            WHERE yield_tonnes_per_ha IS NOT NULL
            GROUP BY crop_type
            ORDER BY avg_yield DESC
        ''').fetchall()
        
        # Weather impact summary
        weather_summary = conn.execute('''
            SELECT weather_type, COUNT(*) as total_events,
                   ROUND(AVG(damage_percent), 1) as avg_damage,
                   ROUND(AVG(yield_impact_percent), 1) as avg_yield_impact,
                   SUM(CASE WHEN insurance_claim = 1 THEN 1 ELSE 0 END) as insurance_claims
            FROM weather_events
            GROUP BY weather_type
            ORDER BY avg_yield_impact DESC
        ''').fetchall()
        
        conn.close()
        
        return render_template('reports/dashboard.html', 
                             field_performance=field_performance,
                             crop_performance=crop_performance,
                             weather_summary=weather_summary)
    
    except Exception as e:
        flash(f'Error generating reports: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('index'))

# =====================================================
# PLANTING TRACKING ROUTES
# =====================================================

@app.route('/planting')
def planting_dashboard():
    """Planting operations dashboard"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        # Get all planting records with field info
        plantings = conn.execute('''
            SELECT 
                p.*,
                f.field_name,
                f.size_hectares as field_size,
                (SELECT COUNT(*) FROM field_maintenance WHERE planting_id = p.planting_id) as maintenance_count,
                (SELECT COUNT(*) FROM harvest_records WHERE planting_id = p.planting_id) as harvest_count
            FROM planting_records p
            JOIN fields f ON p.field_id = f.field_id
            ORDER BY p.planting_date DESC
        ''').fetchall()
        
        # Get summary stats
        active_plantings = conn.execute('''
            SELECT COUNT(*) as count FROM planting_records WHERE status = 'Active'
        ''').fetchone()['count']
        
        total_planted_area = conn.execute('''
            SELECT SUM(planted_area_ha) as total FROM planting_records WHERE status = 'Active'
        ''').fetchone()['total'] or 0
        
        total_costs = conn.execute('''
            SELECT SUM(total_planting_cost) as total FROM planting_records
        ''').fetchone()['total'] or 0
        
        conn.close()
        
        return render_template('planting/dashboard.html',
                             plantings=plantings,
                             active_plantings=active_plantings,
                             total_planted_area=total_planted_area,
                             total_costs=total_costs)
    
    except Exception as e:
        flash(f'Error loading planting dashboard: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('index'))

@app.route('/planting/add', methods=['GET', 'POST'])
def add_planting():
    """Add new planting record"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('planting_dashboard'))
    
    # Get fields for dropdown
    fields = conn.execute('SELECT field_id, field_name, size_hectares FROM fields ORDER BY field_name').fetchall()
    
    if request.method == 'POST':
        try:
            # Get form data
            field_id = request.form.get('field_id')
            crop_type = request.form.get('crop_type')
            variety = request.form.get('variety', '')
            planting_date = request.form.get('planting_date')
            planting_season = request.form.get('planting_season')
            expected_harvest_date = request.form.get('expected_harvest_date') or None
            planted_area_ha = float(request.form.get('planted_area_ha', 0))
            
            # Costs
            seed_cost = float(request.form.get('seed_cost', 0))
            seed_rate = request.form.get('seed_rate', '')
            fertilizer_cost = float(request.form.get('fertilizer_cost', 0))
            lime_cost = float(request.form.get('lime_cost', 0))
            labor_cost = float(request.form.get('labor_cost', 0))
            equipment_cost = float(request.form.get('equipment_cost', 0))
            fuel_cost = float(request.form.get('fuel_cost', 0))
            other_costs = float(request.form.get('other_costs', 0))
            
            # Calculate totals
            total_planting_cost = seed_cost + fertilizer_cost + lime_cost + labor_cost + equipment_cost + fuel_cost + other_costs
            cost_per_hectare = total_planting_cost / planted_area_ha if planted_area_ha > 0 else 0
            
            # Details
            planting_method = request.form.get('planting_method', '')
            soil_temp = request.form.get('soil_temp_c') or None
            soil_moisture = request.form.get('soil_moisture', '')
            weather_conditions = request.form.get('weather_conditions', '')
            operator_name = request.form.get('operator_name', '')
            notes = request.form.get('notes', '')
            
            # Insert planting record
            conn.execute('''
                INSERT INTO planting_records (
                    field_id, crop_type, variety, planting_date, planting_season,
                    expected_harvest_date, planted_area_ha,
                    seed_cost, seed_rate, fertilizer_cost, lime_cost, labor_cost,
                    equipment_cost, fuel_cost, other_costs, total_planting_cost, cost_per_hectare,
                    planting_method, soil_temp_c, soil_moisture, weather_conditions,
                    operator_name, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                field_id, crop_type, variety, planting_date, planting_season,
                expected_harvest_date, planted_area_ha,
                seed_cost, seed_rate, fertilizer_cost, lime_cost, labor_cost,
                equipment_cost, fuel_cost, other_costs, total_planting_cost, cost_per_hectare,
                planting_method, soil_temp, soil_moisture, weather_conditions,
                operator_name, notes, 'Active'
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'Planting record for {crop_type} added successfully!', 'success')
            return redirect(url_for('planting_dashboard'))
            
        except Exception as e:
            flash(f'Error adding planting record: {str(e)}', 'error')
    
    conn.close()
    return render_template('planting/add.html', fields=fields)

@app.route('/planting/<int:planting_id>')
def planting_detail(planting_id):
    """View detailed planting record with maintenance and harvest"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('planting_dashboard'))
    
    try:
        # Get planting record
        planting = conn.execute('''
            SELECT p.*, f.field_name, f.size_hectares as field_size
            FROM planting_records p
            JOIN fields f ON p.field_id = f.field_id
            WHERE p.planting_id = ?
        ''', (planting_id,)).fetchone()
        
        if not planting:
            flash('Planting record not found!', 'error')
            conn.close()
            return redirect(url_for('planting_dashboard'))
        
        # Get maintenance records
        maintenance = conn.execute('''
            SELECT * FROM field_maintenance
            WHERE planting_id = ?
            ORDER BY maintenance_date DESC
        ''', (planting_id,)).fetchall()
        
        # Get harvest records
        harvests = conn.execute('''
            SELECT * FROM harvest_records
            WHERE planting_id = ?
            ORDER BY harvest_date DESC
        ''', (planting_id,)).fetchall()
        
        # Calculate total maintenance costs
        total_maintenance_cost = conn.execute('''
            SELECT SUM(total_cost) as total
            FROM field_maintenance
            WHERE planting_id = ?
        ''', (planting_id,)).fetchone()['total'] or 0
        
        conn.close()
        
        return render_template('planting/detail.html',
                             planting=planting,
                             maintenance=maintenance,
                             harvests=harvests,
                             total_maintenance_cost=total_maintenance_cost)
    
    except Exception as e:
        flash(f'Error loading planting details: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('planting_dashboard'))

# =====================================================
# FIELD MAINTENANCE ROUTES
# Add this NEW route to your app.py
# =====================================================

@app.route('/fields/<field_id>/maintenance/add', methods=['GET', 'POST'])
def field_maintenance_add(field_id):
    """Add maintenance record directly from field (not tied to specific planting)"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('fields_list'))
    
    # Get field info
    field = conn.execute('''
        SELECT * FROM fields WHERE field_id = ?
    ''', (field_id,)).fetchone()
    
    if not field:
        flash('Field not found!', 'error')
        conn.close()
        return redirect(url_for('fields_list'))
    
    # Get active plantings for this field (optional - user can select one or none)
    active_plantings = conn.execute('''
        SELECT planting_id, crop_type, variety, planting_date, status
        FROM planting_records
        WHERE field_id = ? AND status = 'Active'
        ORDER BY planting_date DESC
    ''', (field_id,)).fetchall()
    
    if request.method == 'POST':
        try:
            maintenance_date = request.form.get('maintenance_date')
            maintenance_type = request.form.get('maintenance_type')
            operation_details = request.form.get('operation_details', '')
            equipment_used = request.form.get('equipment_used', '')
            operator_name = request.form.get('operator_name', '')
            hours_worked = float(request.form.get('hours_worked', 0))
            
            # Optional planting association
            planting_id = request.form.get('planting_id')
            planting_id = int(planting_id) if planting_id and planting_id != '' else None
            
            # Costs
            labor_cost = float(request.form.get('labor_cost', 0))
            equipment_cost = float(request.form.get('equipment_cost', 0))
            material_cost = float(request.form.get('material_cost', 0))
            fuel_cost = float(request.form.get('fuel_cost', 0))
            total_cost = labor_cost + equipment_cost + material_cost + fuel_cost
            
            # Details
            area_covered = float(request.form.get('area_covered_ha', 0)) if request.form.get('area_covered_ha') else None
            product_used = request.form.get('product_used', '')
            application_rate = request.form.get('application_rate', '')
            weather_conditions = request.form.get('weather_conditions', '')
            soil_conditions = request.form.get('soil_conditions', '')
            notes = request.form.get('notes', '')
            
            conn.execute('''
                INSERT INTO field_maintenance (
                    field_id, planting_id, maintenance_date, maintenance_type,
                    operation_details, equipment_used, operator_name, hours_worked,
                    labor_cost, equipment_cost, material_cost, fuel_cost, total_cost,
                    area_covered_ha, product_used, application_rate,
                    weather_conditions, soil_conditions, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                field_id, planting_id, maintenance_date, maintenance_type,
                operation_details, equipment_used, operator_name, hours_worked,
                labor_cost, equipment_cost, material_cost, fuel_cost, total_cost,
                area_covered, product_used, application_rate,
                weather_conditions, soil_conditions, notes
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'{maintenance_type} maintenance recorded successfully for {field["field_name"]}!', 'success')
            return redirect(url_for('field_detail', field_id=field_id))
            
        except Exception as e:
            flash(f'Error adding maintenance record: {str(e)}', 'error')
            if conn:
                conn.close()
            return redirect(url_for('field_maintenance_add', field_id=field_id))
    
    conn.close()
    return render_template('maintenance/field_add.html', 
                         field=field, 
                         active_plantings=active_plantings)


# =====================================================
# HARVEST TRACKING ROUTES
# =====================================================

@app.route('/harvest/add/<int:planting_id>', methods=['GET', 'POST'])
def add_harvest(planting_id):
    """Add harvest record"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('planting_dashboard'))
    
    # Get planting info with all costs
    planting = conn.execute('''
        SELECT p.*, f.field_name,
               (SELECT SUM(total_cost) FROM field_maintenance WHERE planting_id = p.planting_id) as maintenance_costs
        FROM planting_records p
        JOIN fields f ON p.field_id = f.field_id
        WHERE p.planting_id = ?
    ''', (planting_id,)).fetchone()
    
    if not planting:
        flash('Planting record not found!', 'error')
        conn.close()
        return redirect(url_for('planting_dashboard'))
    
    if request.method == 'POST':
        try:
            harvest_date = request.form.get('harvest_date')
            harvest_season = request.form.get('harvest_season', '')
            
            # Yield information
            total_yield_tonnes = float(request.form.get('total_yield_tonnes'))
            harvested_area_ha = float(request.form.get('harvested_area_ha', planting['planted_area_ha']))
            yield_per_hectare = total_yield_tonnes / harvested_area_ha if harvested_area_ha > 0 else 0
            
            # Quality
            moisture_percent = float(request.form.get('moisture_percent')) if request.form.get('moisture_percent') else None
            quality_grade = request.form.get('quality_grade', '')
            test_weight = float(request.form.get('test_weight')) if request.form.get('test_weight') else None
            protein_percent = float(request.form.get('protein_percent')) if request.form.get('protein_percent') else None
            damage_percent = float(request.form.get('damage_percent', 0))
            
            # Market
            market_price = float(request.form.get('market_price_per_tonne', 0))
            price_premium = float(request.form.get('price_premium', 0))
            buyer_name = request.form.get('buyer_name', '')
            sale_location = request.form.get('sale_location', '')
            
            # Harvest costs
            harvest_labor_cost = float(request.form.get('harvest_labor_cost', 0))
            harvest_equipment_cost = float(request.form.get('harvest_equipment_cost', 0))
            harvest_fuel_cost = float(request.form.get('harvest_fuel_cost', 0))
            transport_cost = float(request.form.get('transport_cost', 0))
            drying_cost = float(request.form.get('drying_cost', 0))
            storage_cost = float(request.form.get('storage_cost', 0))
            other_harvest_costs = float(request.form.get('other_harvest_costs', 0))
            total_harvest_cost = (harvest_labor_cost + harvest_equipment_cost + harvest_fuel_cost +
                                transport_cost + drying_cost + storage_cost + other_harvest_costs)
            
            # Financial calculations
            gross_revenue = total_yield_tonnes * (market_price + price_premium)
            maintenance_costs = planting['maintenance_costs'] or 0
            total_costs = planting['total_planting_cost'] + maintenance_costs + total_harvest_cost
            net_profit = gross_revenue - total_costs
            profit_per_hectare = net_profit / harvested_area_ha if harvested_area_ha > 0 else 0
            roi_percent = (net_profit / total_costs * 100) if total_costs > 0 else 0
            break_even_price = total_costs / total_yield_tonnes if total_yield_tonnes > 0 else 0
            
            # Details
            harvest_method = request.form.get('harvest_method', '')
            equipment_used = request.form.get('equipment_used', '')
            operator_name = request.form.get('operator_name', '')
            weather_conditions = request.form.get('weather_conditions', '')
            notes = request.form.get('notes', '')
            
            conn.execute('''
                INSERT INTO harvest_records (
                    planting_id, field_id, harvest_date, harvest_season,
                    total_yield_tonnes, yield_per_hectare, harvested_area_ha,
                    moisture_percent, quality_grade, test_weight, protein_percent, damage_percent,
                    market_price_per_tonne, price_premium, buyer_name, sale_location,
                    harvest_method, equipment_used, operator_name, weather_conditions,
                    harvest_labor_cost, harvest_equipment_cost, harvest_fuel_cost,
                    transport_cost, drying_cost, storage_cost, other_harvest_costs, total_harvest_cost,
                    gross_revenue, total_costs, net_profit, profit_per_hectare, roi_percent, break_even_price,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                planting_id, planting['field_id'], harvest_date, harvest_season,
                total_yield_tonnes, yield_per_hectare, harvested_area_ha,
                moisture_percent, quality_grade, test_weight, protein_percent, damage_percent,
                market_price, price_premium, buyer_name, sale_location,
                harvest_method, equipment_used, operator_name, weather_conditions,
                harvest_labor_cost, harvest_equipment_cost, harvest_fuel_cost,
                transport_cost, drying_cost, storage_cost, other_harvest_costs, total_harvest_cost,
                gross_revenue, total_costs, net_profit, profit_per_hectare, roi_percent, break_even_price,
                notes
            ))
            
            # Update planting status
            conn.execute('UPDATE planting_records SET status = ? WHERE planting_id = ?',
                        ('Harvested', planting_id))
            
            # Update storage dashboard if crop exists there
            storage_exists = conn.execute(
                'SELECT 1 FROM crop_storage WHERE crop_name = ?',
                (planting['crop_type'],)
            ).fetchone()
            
            if storage_exists:
                conn.execute('''
                    UPDATE crop_storage
                    SET quantity_stored = quantity_stored + ?,
                        current_market_price = ?,
                        last_price_update = ?
                    WHERE crop_name = ?
                ''', (total_yield_tonnes, market_price, harvest_date, planting['crop_type']))
            
            conn.commit()
            conn.close()
            
            flash(f'Harvest recorded successfully! Net profit: ${net_profit:,.2f} (ROI: {roi_percent:.1f}%)', 'success')
            return redirect(url_for('planting_detail', planting_id=planting_id))
            
        except Exception as e:
            flash(f'Error recording harvest: {str(e)}', 'error')
    
    conn.close()
    return render_template('harvest/add.html', planting=planting)

# =====================================================
# FIELD MAINTENANCE ROUTES
# =====================================================

@app.route('/maintenance/add/<int:planting_id>', methods=['GET', 'POST'])
def add_maintenance(planting_id):
    """Add field maintenance record"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('planting_dashboard'))
    
    # Get planting info
    planting = conn.execute('''
        SELECT p.*, f.field_name
        FROM planting_records p
        JOIN fields f ON p.field_id = f.field_id
        WHERE p.planting_id = ?
    ''', (planting_id,)).fetchone()
    
    if not planting:
        flash('Planting record not found!', 'error')
        conn.close()
        return redirect(url_for('planting_dashboard'))
    
    if request.method == 'POST':
        try:
            maintenance_date = request.form.get('maintenance_date')
            maintenance_type = request.form.get('maintenance_type')
            operation_details = request.form.get('operation_details', '')
            equipment_used = request.form.get('equipment_used', '')
            operator_name = request.form.get('operator_name', '')
            hours_worked = float(request.form.get('hours_worked', 0))
            
            # Costs
            labor_cost = float(request.form.get('labor_cost', 0))
            equipment_cost = float(request.form.get('equipment_cost', 0))
            material_cost = float(request.form.get('material_cost', 0))
            fuel_cost = float(request.form.get('fuel_cost', 0))
            total_cost = labor_cost + equipment_cost + material_cost + fuel_cost
            
            # Details
            area_covered = float(request.form.get('area_covered_ha', 0)) if request.form.get('area_covered_ha') else None
            product_used = request.form.get('product_used', '')
            application_rate = request.form.get('application_rate', '')
            weather_conditions = request.form.get('weather_conditions', '')
            soil_conditions = request.form.get('soil_conditions', '')
            notes = request.form.get('notes', '')
            
            conn.execute('''
                INSERT INTO field_maintenance (
                    field_id, planting_id, maintenance_date, maintenance_type,
                    operation_details, equipment_used, operator_name, hours_worked,
                    labor_cost, equipment_cost, material_cost, fuel_cost, total_cost,
                    area_covered_ha, product_used, application_rate,
                    weather_conditions, soil_conditions, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                planting['field_id'], planting_id, maintenance_date, maintenance_type,
                operation_details, equipment_used, operator_name, hours_worked,
                labor_cost, equipment_cost, material_cost, fuel_cost, total_cost,
                area_covered, product_used, application_rate,
                weather_conditions, soil_conditions, notes
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'{maintenance_type} maintenance recorded successfully!', 'success')
            return redirect(url_for('planting_detail', planting_id=planting_id))
            
        except Exception as e:
            flash(f'Error adding maintenance record: {str(e)}', 'error')
    
    conn.close()
    return render_template('maintenance/add.html', planting=planting)


# =====================================================
# OPTIONAL: Additional maintenance management routes
# =====================================================

@app.route('/maintenance/list')
def maintenance_list():
    """List all maintenance records"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        maintenance = conn.execute('''
            SELECT m.*, f.field_name, p.crop_type
            FROM field_maintenance m
            JOIN fields f ON m.field_id = f.field_id
            LEFT JOIN planting_records p ON m.planting_id = p.planting_id
            ORDER BY m.maintenance_date DESC
            LIMIT 100
        ''').fetchall()
        
        conn.close()
        return render_template('maintenance/list.html', maintenance=maintenance)
    
    except Exception as e:
        flash(f'Error loading maintenance records: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('index'))


@app.route('/maintenance/<int:maintenance_id>/edit', methods=['GET', 'POST'])
def edit_maintenance(maintenance_id):
    """Edit maintenance record"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('maintenance_list'))
    
# =====================================================
# OPERATIONS MANAGEMENT ROUTES
# Replace your existing operations section with this
# =====================================================

@app.route('/operations')
def operations_list():
    """List all field operations"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    try:
        operations = conn.execute('''
            SELECT fo.operation_id, fo.operation_date, fo.field_id, f.field_name, 
                   fo.operation_type, fo.hours_worked, fo.fuel_used_liters, 
                   fo.quality_rating, fo.weather_conditions, fo.operator_name
            FROM field_operations fo
            JOIN fields f ON fo.field_id = f.field_id
            ORDER BY fo.operation_date DESC
            LIMIT 100
        ''').fetchall()
        
        # Get summary statistics
        total_operations = conn.execute('SELECT COUNT(*) as count FROM field_operations').fetchone()['count']
        
        total_hours = conn.execute('''
            SELECT SUM(hours_worked) as total FROM field_operations 
            WHERE hours_worked IS NOT NULL
        ''').fetchone()['total'] or 0
        
        total_fuel = conn.execute('''
            SELECT SUM(fuel_used_liters) as total FROM field_operations 
            WHERE fuel_used_liters IS NOT NULL
        ''').fetchone()['total'] or 0
        
        conn.close()
        return render_template('operations/list.html', 
                             operations=operations,
                             total_operations=total_operations,
                             total_hours=round(total_hours, 1),
                             total_fuel=round(total_fuel, 1))
    
    except Exception as e:
        flash(f'Error loading operations: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('index'))


@app.route('/operations/add', methods=['GET', 'POST'])
def add_operation():
    """Add field operation"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('index'))
    
    # Get available fields
    fields = conn.execute('SELECT field_id, field_name FROM fields ORDER BY field_name').fetchall()
    
    # Get available crop seasons (optional link)
    seasons = conn.execute('''
        SELECT season_id, field_id, crop_type, crop_year, season_name
        FROM crop_seasons
        ORDER BY crop_year DESC, planting_date DESC
        LIMIT 50
    ''').fetchall()
    
    if request.method == 'POST':
        try:
            operation_data = {
                'field_id': request.form['field_id'],
                'operation_date': request.form['operation_date'],
                'operation_type': request.form['operation_type'],
                'hours_worked': float(request.form.get('hours_worked', 0)) if request.form.get('hours_worked') else None,
                'fuel_used_liters': float(request.form.get('fuel_used_liters', 0)) if request.form.get('fuel_used_liters') else None,
                'weather_conditions': request.form.get('weather_conditions', '').strip(),
                'quality_rating': int(request.form.get('quality_rating', 8)) if request.form.get('quality_rating') else None,
                'operator_name': request.form.get('operator_name', '').strip(),
                'average_speed_kmh': float(request.form.get('average_speed_kmh', 0)) if request.form.get('average_speed_kmh') else None,
                'soil_moisture_percent': float(request.form.get('soil_moisture_percent', 0)) if request.form.get('soil_moisture_percent') else None,
                'notes': request.form.get('notes', '').strip()
            }
            
            # Optional season link
            season_id = request.form.get('season_id')
            operation_data['season_id'] = int(season_id) if season_id and season_id != '' else None
            
            conn.execute('''
                INSERT INTO field_operations (
                    field_id, season_id, operation_date, operation_type,
                    hours_worked, fuel_used_liters, weather_conditions, 
                    quality_rating, operator_name, average_speed_kmh,
                    soil_moisture_percent, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_data['field_id'], operation_data['season_id'],
                operation_data['operation_date'], operation_data['operation_type'],
                operation_data['hours_worked'], operation_data['fuel_used_liters'],
                operation_data['weather_conditions'], operation_data['quality_rating'],
                operation_data['operator_name'], operation_data['average_speed_kmh'],
                operation_data['soil_moisture_percent'], operation_data['notes']
            ))
            
            conn.commit()
            conn.close()
            
            flash(f'{operation_data["operation_type"]} operation logged successfully!', 'success')
            return redirect(url_for('operations_list'))
            
        except Exception as e:
            flash(f'Error logging operation: {str(e)}', 'error')
            if conn:
                conn.close()
            return redirect(url_for('add_operation'))
    
    conn.close()
    return render_template('operations/add.html', fields=fields, seasons=seasons)


@app.route('/operations/<int:operation_id>/edit', methods=['GET', 'POST'])
def edit_operation(operation_id):
    """Edit existing operation"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('operations_list'))
    
    # Get operation
    operation = conn.execute('''
        SELECT fo.*, f.field_name
        FROM field_operations fo
        JOIN fields f ON fo.field_id = f.field_id
        WHERE fo.operation_id = ?
    ''', (operation_id,)).fetchone()
    
    if not operation:
        flash('Operation not found!', 'error')
        conn.close()
        return redirect(url_for('operations_list'))
    
    # Get available fields
    fields = conn.execute('SELECT field_id, field_name FROM fields ORDER BY field_name').fetchall()
    
    if request.method == 'POST':
        try:
            operation_data = {
                'field_id': request.form['field_id'],
                'operation_date': request.form['operation_date'],
                'operation_type': request.form['operation_type'],
                'hours_worked': float(request.form.get('hours_worked', 0)) if request.form.get('hours_worked') else None,
                'fuel_used_liters': float(request.form.get('fuel_used_liters', 0)) if request.form.get('fuel_used_liters') else None,
                'weather_conditions': request.form.get('weather_conditions', '').strip(),
                'quality_rating': int(request.form.get('quality_rating', 8)) if request.form.get('quality_rating') else None,
                'operator_name': request.form.get('operator_name', '').strip(),
                'notes': request.form.get('notes', '').strip()
            }
            
            conn.execute('''
                UPDATE field_operations 
                SET field_id = ?, operation_date = ?, operation_type = ?,
                    hours_worked = ?, fuel_used_liters = ?, weather_conditions = ?,
                    quality_rating = ?, operator_name = ?, notes = ?
                WHERE operation_id = ?
            ''', (
                operation_data['field_id'], operation_data['operation_date'],
                operation_data['operation_type'], operation_data['hours_worked'],
                operation_data['fuel_used_liters'], operation_data['weather_conditions'],
                operation_data['quality_rating'], operation_data['operator_name'],
                operation_data['notes'], operation_id
            ))
            
            conn.commit()
            conn.close()
            
            flash('Operation updated successfully!', 'success')
            return redirect(url_for('operations_list'))
            
        except Exception as e:
            flash(f'Error updating operation: {str(e)}', 'error')
    
    conn.close()
    return render_template('operations/edit.html', operation=operation, fields=fields)


@app.route('/operations/<int:operation_id>/delete', methods=['POST'])
def delete_operation(operation_id):
    """Delete operation"""
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('operations_list'))
    
    try:
        conn.execute('DELETE FROM field_operations WHERE operation_id = ?', (operation_id,))
        conn.commit()
        conn.close()
        
        flash('Operation deleted successfully!', 'success')
        return redirect(url_for('operations_list'))
        
    except Exception as e:
        flash(f'Error deleting operation: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('operations_list'))

# =====================================================
# ERROR HANDLERS AND UTILITY ROUTES
# =====================================================

@app.route('/setup-required')
def setup_required():
    """Show setup required page"""
    return render_template('setup_required.html')

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500

# =====================================================
# APPLICATION STARTUP
# =====================================================

if __name__ == '__main__':
    # Check if database exists
    if not init_db_check():
        print("❌ Database not found or not properly initialized!")
        print("Please run: python database/setup.py")
        print("Then restart the application.")
        exit(1)
    
    print("🌾 FS25 Farming Web Application Starting...")
    print("=" * 50)
    print("📱 Open your browser to: http://localhost:5000")
    print("🔧 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run the Flask application
    app.run(debug=True, host='0.0.0.0', port=5000)