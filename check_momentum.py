"""Quick script to check momentum calculation details"""
from src.database.db_manager import DatabaseManager

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

# FaZe Vegas recent matches
print("="*60)
print("FAZE VEGAS - Last 5 matches (most recent first):")
print("="*60)
cursor.execute("""
    SELECT match_id, team_a, team_b, winner, match_date 
    FROM matches 
    WHERE team_a = 'FaZe Vegas' OR team_b = 'FaZe Vegas' 
    ORDER BY match_date DESC, id DESC 
    LIMIT 5
""")
faze_matches = cursor.fetchall()
for i, (match_id, team_a, team_b, winner, date) in enumerate(faze_matches, 1):
    result = "WIN" if winner == "FaZe Vegas" else "LOSS"
    opponent = team_a if team_a != "FaZe Vegas" else team_b
    print(f"{i}. {date}: vs {opponent} - {result}")

print("\n" + "="*60)
print("OPTIC TEXAS - Last 5 matches (most recent first):")
print("="*60)
cursor.execute("""
    SELECT match_id, team_a, team_b, winner, match_date 
    FROM matches 
    WHERE team_a = 'OpTic Texas' OR team_b = 'OpTic Texas' 
    ORDER BY match_date DESC, id DESC 
    LIMIT 5
""")
optic_matches = cursor.fetchall()
for i, (match_id, team_a, team_b, winner, date) in enumerate(optic_matches, 1):
    result = "WIN" if winner == "OpTic Texas" else "LOSS"
    opponent = team_a if team_a != "OpTic Texas" else team_b
    print(f"{i}. {date}: vs {opponent} - {result}")

conn.close()
