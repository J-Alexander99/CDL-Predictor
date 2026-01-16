import json

def load_data(filename):
    with open(filename, "r") as file:
        return json.load(file)

def save_match_data(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

def calculate_last_10_performance(matches):
    """Takes the last 10 matches and calculates wins, losses, and win rate."""
    last_10 = matches[-10:]  # Take only the last 10 matches
    wins = last_10.count("W")
    losses = last_10.count("L")
    total_games = len(last_10)
    win_rate = round((wins / total_games) * 100, 2) if total_games else 0

    return {"wins": wins, "losses": losses, "win_rate": win_rate}

def get_team_data(data, team_name):
    team_info = data[team_name]

    # Calculate last 10 mode performance
    last_10_modes = {
        mode: calculate_last_10_performance(team_info[mode]) 
        for mode in ["Hardpoint", "Search", "Control"]
    }

    # Calculate last 10 series performance
    series_performance = calculate_last_10_performance(team_info["Win/Loss"])

    # Extract players and their stats
    players = {}
    for player, kd_list in team_info["KDs"].items():
        avg_kd = float(kd_list[-1]) if kd_list else 0
        avg_bp = float(team_info["BP"].get(player, [0])[-1]) if team_info["BP"].get(player) else 0
        players[player] = {"avg_kd": avg_kd, "avg_bp_rating": avg_bp}

    return {
        "name": team_name,
        "roster_similarity": 0,  # You can manually modify this later if needed
        "last_10_mode_performance": last_10_modes,
        "last_10_series_performance": series_performance,
        "players": players,
        "head_to_head": team_info["Head 2 Head"]
    }

def main():
    filename = "DataAid.json"
    data = load_data(filename)

    teams = list(data.keys())

    # Display teams and let user pick
    print("Available Teams:")
    for i, team in enumerate(teams, 1):
        print(f"{i}. {team}")

    team_a_index = int(input("Select Team A (number): ")) - 1
    team_b_index = int(input("Select Team B (number): ")) - 1

    if team_a_index not in range(len(teams)) or team_b_index not in range(len(teams)) or team_a_index == team_b_index:
        print("Invalid selection. Please select different valid teams.")
        return

    team_a = teams[team_a_index]
    team_b = teams[team_b_index]

    match_id = input("Enter Match ID: ")
    match_date = input("Enter Match Date (YYYY/MM/DD): ")
    match_type = input("Enter Match Type (Online/LAN): ")
    final_score = input("Enter Final Score (e.g., 3-2): ")

    match_data = {
        "match_id": match_id,
        "date": match_date,
        "match_type": match_type,
        "team_A": get_team_data(data, team_a),
        "team_B": get_team_data(data, team_b),
        "final_score": final_score,
        "head_to_head": {
            team_a: data[team_a]["Head 2 Head"].get(team_b, 0),
            team_b: data[team_b]["Head 2 Head"].get(team_a, 0)
        }
    }

    output_filename = f"{match_id}.json"
    save_match_data(output_filename, match_data)
    print(f"Match data saved to {output_filename}")

if __name__ == "__main__":
    main()
