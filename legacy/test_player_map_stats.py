from src.database.db_manager import DatabaseManager

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

# Check per-map stats
cursor.execute('SELECT player_name, mode, map_name, kills FROM player_map_stats WHERE player_name="Insight" ORDER BY map_number')
print('\nInsight per-map stats:')
for row in cursor.fetchall():
    print(f'{row[1]:<20} {row[2]:<12} {row[3]}K')

# Check aggregated mode stats
cursor.execute('SELECT * FROM player_mode_stats WHERE player_name="Insight"')
rows = cursor.fetchall()
print('\nInsight by mode:')
for row in rows:
    print(f'{row[1]:<20} Avg: {row[3]:.1f}K over {row[2]} maps')

# Check map-mode combo stats  
cursor.execute('SELECT * FROM player_map_mode_stats WHERE player_name="Insight"')
rows = cursor.fetchall()
print('\nInsight by map-mode combo:')
for row in rows:
    print(f'{row[2]:<20} {row[1]:<12} Avg: {row[4]:.1f}K over {row[3]} maps')

conn.close()
