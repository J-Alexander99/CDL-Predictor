from src.database.db_manager import DatabaseManager

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

print("\n=== MAP NAMES IN DATABASE ===\n")

# Get all distinct map-mode combinations
cursor.execute("""
    SELECT DISTINCT mode, map_name 
    FROM map_results 
    ORDER BY mode, map_name
""")
maps = cursor.fetchall()

current_mode = None
for mode, map_name in maps:
    if mode != current_mode:
        print(f"\n{mode}:")
        current_mode = mode
    print(f"  - {map_name}")

print("\n\n=== OPTIC TEXAS MAP HISTORY ===\n")

# Get OpTic's map history
cursor.execute("""
    SELECT mr.mode, mr.map_name, mr.winner, 
           CASE WHEN m.team_a = 'OpTic Texas' THEN m.team_b ELSE m.team_a END as opponent
    FROM map_results mr
    JOIN matches m ON mr.match_id = m.match_id
    WHERE m.team_a = 'OpTic Texas' OR m.team_b = 'OpTic Texas'
    ORDER BY m.match_date, mr.map_number
""")

for mode, map_name, winner, opponent in cursor.fetchall():
    result = "WIN " if winner == "OpTic Texas" else "LOSS"
    print(f"{mode:20} {map_name:15} -> {result} vs {opponent}")

conn.close()
