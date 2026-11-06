import json

def load_rosters(current_rosters_file):
    with open(current_rosters_file, 'r') as file:
        return json.load(file)

def load_match_data(match_data_file):
    with open(match_data_file, 'r') as file:
        return json.load(file)

def save_updated_match_data(match_data_file, updated_data):
    with open(match_data_file, 'w') as file:
        json.dump(updated_data, file, indent=4)

def calculate_roster_similarity(current_roster, match_roster):
    common_players = set(current_roster) & set(match_roster)
    similarity_percentage = len(common_players) / len(current_roster)
    return similarity_percentage

def update_roster_similarity(current_rosters, match_data):
    updated_data = []
    
    for match in match_data:
        # Check roster similarity for team A
        team_A_roster = [player['player_name'] for player in match['team_A']['players']]
        team_A_similarity = calculate_roster_similarity(current_rosters[match['team_A']['team_name']], team_A_roster)
        match['team_A']['roster_similarity'] = team_A_similarity

        # Check roster similarity for team B
        team_B_roster = [player['player_name'] for player in match['team_B']['players']]
        team_B_similarity = calculate_roster_similarity(current_rosters[match['team_B']['team_name']], team_B_roster)
        match['team_B']['roster_similarity'] = team_B_similarity

        updated_data.append(match)

    return updated_data

def main():
    # Define file paths
    current_rosters_file = 'current_rosters.json'
    match_data_file = 'match_data.json'

    # Load current rosters and match data
    current_rosters = load_rosters(current_rosters_file)
    match_data = load_match_data(match_data_file)

    # Update the roster similarity in the match data
    updated_data = update_roster_similarity(current_rosters, match_data)

    # Save the updated match data
    save_updated_match_data(match_data_file, updated_data)
    print("Roster similarity updated successfully!")

if __name__ == '__main__':
    main()
