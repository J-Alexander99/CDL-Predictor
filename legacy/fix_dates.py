"""
Fix date format in database from YYYY-DD-MM to YYYY-MM-DD
"""
from src.database.db_manager import DatabaseManager
import re

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

# Get all matches with their current dates
cursor.execute("SELECT id, match_date FROM matches")
matches = cursor.fetchall()

print(f"Fixing dates for {len(matches)} matches...")
fixed_count = 0

for match_id, date_str in matches:
    # Parse YYYY-DD-MM format
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        year, dd, mm = match.groups()
        
        # Check if this needs fixing (day > 12 means it's in wrong position)
        if int(dd) > 12:
            # Swap day and month to get correct YYYY-MM-DD
            correct_date = f"{year}-{mm}-{dd}"
            
            cursor.execute("UPDATE matches SET match_date = ? WHERE id = ?", 
                          (correct_date, match_id))
            print(f"  Fixed: {date_str} -> {correct_date}")
            fixed_count += 1
        elif int(mm) > 12:
            # Already in wrong format, but month is > 12, so we know what to fix
            print(f"  Warning: Ambiguous date {date_str} - skipping")

conn.commit()
conn.close()

print(f"\nFixed {fixed_count} dates!")
print("\nRun 'python main.py update-stats' to recalculate statistics with correct dates.")
