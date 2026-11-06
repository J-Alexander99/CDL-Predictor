"""
Fix ALL dates in database - swap month and day for ALL entries
since website uses DD/MM/YYYY format
"""
from src.database.db_manager import DatabaseManager
import re
from datetime import datetime

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

# Get all matches with their current dates
cursor.execute("SELECT id, match_date FROM matches")
matches = cursor.fetchall()

print(f"Checking dates for {len(matches)} matches...")
fixed_count = 0

# Today's date for reference
today = datetime(2026, 2, 27)

for match_id, date_str in matches:
    # Parse YYYY-MM-DD format (what's currently stored)
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        year, mm, dd = match.groups()
        
        # Create date object from current format
        try:
            current_date = datetime(int(year), int(mm), int(dd))
        except:
            print(f"  Invalid date: {date_str}")
            continue
        
        # If date is in the future (beyond today), it's definitely wrong
        # OR if month > 12 (obviously wrong)
        # Swap mm and dd
        if current_date > today or int(mm) > 12:
            swapped_date = f"{year}-{dd}-{mm}"
            try:
                # Validate the swapped date
                test = datetime(int(year), int(dd), int(mm))
                cursor.execute("UPDATE matches SET match_date = ? WHERE id = ?", 
                              (swapped_date, match_id))
                print(f"  Fixed: {date_str} -> {swapped_date}")
                fixed_count += 1
            except:
                print(f"  Cannot fix: {date_str} (invalid when swapped)")

conn.commit()
conn.close()

print(f"\nFixed {fixed_count} dates!")
print("Dates should now be in correct YYYY-MM-DD format.")
