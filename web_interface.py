"""
Web interface for CDL Predictor
Simple Flask app for database queries and predictions
"""
from flask import Flask, render_template, request, jsonify, send_file
from src.database.db_manager import DatabaseManager
from src.predictor import MatchPredictor
from src.utils.graphics_generator import generate_prediction_graphic
from pathlib import Path
import json

app = Flask(__name__)
db = DatabaseManager()


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/api/teams')
def get_teams():
    """Get all teams"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT team_a FROM matches 
        UNION SELECT DISTINCT team_b FROM matches 
        ORDER BY 1
    """)
    teams = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(teams)


@app.route('/api/team-stats/<team>')
def get_team_stats(team):
    """Get team statistics"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as matches,
            SUM(CASE WHEN matches.winner = ? THEN 1 ELSE 0 END) as wins
        FROM matches 
        WHERE team_a = ? OR team_b = ?
    """, (team, team, team))
    
    overall = cursor.fetchone()
    
    # Mode stats
    cursor.execute("""
        SELECT 
            mr.mode,
            COUNT(*) as maps,
            SUM(CASE WHEN mr.winner = ? THEN 1 ELSE 0 END) as wins
        FROM matches m
        JOIN map_results mr ON m.match_id = mr.match_id
        WHERE m.team_a = ? OR m.team_b = ?
        GROUP BY mr.mode
    """, (team, team, team))
    
    modes = [{'mode': row[0], 'maps': row[1], 'wins': row[2], 
              'win_rate': round(row[2]/row[1]*100, 1) if row[1] > 0 else 0} 
             for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'team': team,
        'matches': overall[0],
        'wins': overall[1],
        'win_rate': round(overall[1]/overall[0]*100, 1) if overall[0] > 0 else 0,
        'modes': modes
    })


@app.route('/api/matches')
def get_matches():
    """Get recent matches"""
    limit = request.args.get('limit', 20, type=int)
    team = request.args.get('team', None)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    if team:
        cursor.execute("""
            SELECT match_id, match_date, team_a, team_b, 
                   team_a_score, team_b_score, winner
            FROM matches
            WHERE team_a = ? OR team_b = ?
            ORDER BY match_date DESC
            LIMIT ?
        """, (team, team, limit))
    else:
        cursor.execute("""
            SELECT match_id, match_date, team_a, team_b, 
                   team_a_score, team_b_score, winner
            FROM matches
            ORDER BY match_date DESC
            LIMIT ?
        """, (limit,))
    
    matches = [{'match_id': row[0], 'date': row[1], 'team_a': row[2], 
                'team_b': row[3], 'score_a': row[4], 'score_b': row[5], 
                'winner': row[6]} for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(matches)


@app.route('/api/predict', methods=['POST'])
def predict():
    """Generate prediction"""
    data = request.json
    team_a = data.get('team_a')
    team_b = data.get('team_b')
    generate_graphic = data.get('generate_graphic', False)
    
    try:
        predictor = MatchPredictor()
        result = predictor.predict(team_a, team_b)
        
        # Simplify result for JSON
        simplified = {
            'team_a': result['team_a'],
            'team_b': result['team_b'],
            'team_a_probability': result['team_a_win_probability'],
            'team_b_probability': result['team_b_win_probability'],
            'predicted_winner': result['predicted_winner'],
            'predicted_score': result['predicted_score'],
            'confidence': result['confidence'],
            'team_a_stats': {
                'win_rate': result['team_a_stats']['win_rate'],
                'map_win_rate': result['team_a_stats']['map_win_rate'],
                'avg_kd': result['team_a_stats']['roster_quality']['avg_kd'],
            },
            'team_b_stats': {
                'win_rate': result['team_b_stats']['win_rate'],
                'map_win_rate': result['team_b_stats']['map_win_rate'],
                'avg_kd': result['team_b_stats']['roster_quality']['avg_kd'],
            }
        }
        
        if generate_graphic:
            graphic_path = generate_prediction_graphic(result)
            simplified['graphic'] = graphic_path
        
        return jsonify(simplified)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/query', methods=['POST'])
def custom_query():
    """Execute custom SQL query"""
    data = request.json
    query = data.get('query', '')
    
    # Basic SQL injection protection
    if any(keyword in query.upper() for keyword in ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER']):
        return jsonify({'error': 'Only SELECT queries allowed'}), 400
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({'columns': columns, 'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)
