import json

def calculate_avg(values):
    """Calculates the average of a list of numbers, ignoring missing data."""
    if not values:
        return 0
    valid_values = [v for v in values if v is not None]  # Filter out missing data
    return round(sum(valid_values) / len(valid_values), 2) if valid_values else 0

def get_team_data(team_name, players_list):
    """Collects team data based on predefined teams and players."""
    print(f"\nEntering data for {team_name}...")

    roster_similarity = float(input("Roster similarity percentage (0-100): "))

    # Last 10 performances in modes
    last_10_mode_performance = {}
    for mode in ["Hardpoint", "Search&Destroy", "Control"]:
        # Ask for data for the last 10 matches
        wins = []
        losses = []
        print(f"\nEnter data for the last 10 matches in {mode}. Enter 1 for a win, 0 for a loss (or leave empty for missing data).")
        for i in range(1, 11):
            match_result = input(f"Match {i} result: ").strip()
            if match_result == '1':
                wins.append(1)
                losses.append(0)
            elif match_result == '0':
                wins.append(0)
                losses.append(1)
            else:
                wins.append(None)  # None for missing match
                losses.append(None)

        # Calculate the win rate based on the available data
        total_matches = len([w for w in wins if w is not None])  # Matches entered (non-missing)
        win_rate = calculate_avg([sum([1 for w in wins if w == 1]) / total_matches * 100 if total_matches else 0])

        last_10_mode_performance[mode] = {
            "wins": sum([1 for w in wins if w == 1]),
            "losses": sum([1 for w in losses if w == 1]),
            "win_rate": win_rate
        }

    # Last 10 series performance (one set for all modes)
    last_10_series_performance = []
    print("\nEnter data for the last 10 series. Enter 1 for a win, 0 for a loss (or leave empty for missing data).")
    for i in range(1, 11):
        series_result = input(f"Series {i} result: ").strip()
        if series_result == '1':
            last_10_series_performance.append(1)
        elif series_result == '0':
            last_10_series_performance.append(0)
        else:
            last_10_series_performance.append(None)  # None for missing series data

    # Calculate the series win rate
    series_win_rate = calculate_avg(last_10_series_performance)

    # Player stats input (automatic player name assignment)
    players = {}
    for player_name in players_list:
        print(f"\nEnter stats for {player_name}:")
        
        # Input KD ratios for the last 10 matches
        last_10_kds = []
        print(f"Enter KD ratios for the last 10 matches (leave empty for missing data):")
        for i in range(1, 11):
            kd_input = input(f"Match {i} KD ratio: ").strip()
            if kd_input:
                last_10_kds.append(float(kd_input))
            else:
                last_10_kds.append(None)  # None for missing data

        # Input BP ratings for the last 10 matches
        last_10_bp_ratings = []
        print(f"Enter BP ratings for the last 10 matches (leave empty for missing data):")
        for i in range(1, 11):
            bp_input = input(f"Match {i} BP rating: ").strip()
            if bp_input:
                last_10_bp_ratings.append(float(bp_input))
            else:
                last_10_bp_ratings.append(None)  # None for missing data

        players[player_name] = {
            "avg_kd": calculate_avg(last_10_kds),
            "avg_bp_rating": calculate_avg(last_10_bp_ratings)
        }

    return {
        "name": team_name,
        "roster_similarity": roster_similarity,
        "last_10_mode_performance": last_10_mode_performance,
        "last_10_series_performance": {
            "series_win_rate": series_win_rate,
            "wins": sum([1 for r in last_10_series_performance if r == 1]),
            "losses": sum([1 for r in last_10_series_performance if r == 0])
        },
        "players": players
    }

def generate_match_json():
    """Generates and saves a match JSON file based on user input."""
    # List of teams and their players
    teams = {
        "Atlanta FaZe": ["Cellium", "Drazah", "Simp", "aBeZy"],
        "Boston Breach": ["Cammy", "Owakening", "Purj", "Snoopy"],
        "Carolina Royal Ravens": ["Gwinn", "SlasheR", "TJHaLy", "Vivid"],
        "Cloud9 New York": ["Attach", "Kremp", "Mack", "Sib"],
        "LA Guerrillas M8": ["KiSMET", "Lunarz", "Lynz", "Priestahh"],
        "Los Angeles Theives": ["Envoy", "Ghosty", "HyDra", "Scrap"],
        "Miami Heretics": ["Lucky", "MettalZ", "ReeaL", "RenKoR"],
        "Minnesota ROKKR": ["Estreal", "Gio", "Nero", "PaulEhx"],
        "OpTic Texas": ["Dashy", "Kenny", "Pred", "Shotzzy"],
        "Toronto Ultra": ["Beans", "CleanX", "Insight", "JoeDeceives"],
        "Vancouver Surge": ["04", "Abuzah", "Nastie", "Neptune"],
        "Vegas Falcons": ["D7oomx", "Exnid", "KiinG", "WXSL"]
    }

    # Print team list and let the user choose
    print("Available teams:")
    for idx, team_name in enumerate(teams.keys(), start=1):
        print(f"{idx}. {team_name}")
    
    team_A_num = int(input("Enter the number for Team A: "))
    team_B_num = int(input("Enter the number for Team B: "))

    team_A_name = list(teams.keys())[team_A_num - 1]
    team_B_name = list(teams.keys())[team_B_num - 1]

    # Generate team data based on selected teams
    team_A = get_team_data(team_A_name, teams[team_A_name])
    team_B = get_team_data(team_B_name, teams[team_B_name])

    match_id = input("Enter match ID: ")
    date = input("Enter match date (YYYY-MM-DD): ")
    match_type = input("Match type (LAN/Online): ")

    final_score = input("Enter final score (e.g., 2-3): ")
    head_to_head = {
        team_A["name"]: int(input(f"Enter all-time wins for {team_A['name']}: ")),
        team_B["name"]: int(input(f"Enter all-time wins for {team_B['name']}: "))
    }

    match_data = {
        "match_id": match_id,
        "date": date,
        "match_type": match_type,
        "team_A": team_A,
        "team_B": team_B,
        "final_score": final_score,
        "head_to_head": head_to_head
    }

    filename = f"{match_id}.json"
    with open(filename, "w") as file:
        json.dump(match_data, file, indent=4)

    print(f"\nMatch data saved to {filename}")

# Run the script
generate_match_json()
