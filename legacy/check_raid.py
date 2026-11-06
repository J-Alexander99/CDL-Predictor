from src.database.db_manager import DatabaseManager

db = DatabaseManager()
conn = db.get_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT m.match_date, m.team_a, m.team_b, mr.mode, mr.map_name, 
           mr.winner, mr.team_a_score, mr.team_b_score
    FROM map_results mr
    JOIN matches m ON mr.match_id = m.match_id
    WHERE mr.map_name = 'Raid'
    ORDER BY m.match_date, mr.map_number
""")

results = cursor.fetchall()

print('\n=== RAID MAP HISTORY ===\n')
print(f'Total times played: {len(results)}\n')

for date, team_a, team_b, mode, map_name, winner, score_a, score_b in results:
    print(f'{date} | {mode:20} | {team_a:30} vs {team_b:30}')
    print(f'         Winner: {winner:30} | Score: {score_a}-{score_b}\n')

conn.close()
