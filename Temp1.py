from bs4 import BeautifulSoup
import json

def parse_cdl_html_and_update_json(file_path, json_file_path):
    # Open and read the HTML file
    with open(file_path, 'r') as file:
        html_data = file.read()

    # Parse the HTML data with BeautifulSoup
    soup = BeautifulSoup(html_data, 'html.parser')

    # Extract match details
    matches = soup.find_all('div', class_='mantine-Card-root')

    # Initialize a dictionary to count wins for each team
    team_wins = {}

    # Initialize a list to store the match results
    results = []

    # Team name mapping to match the keys in the JSON file
    team_name_mapping = {
        "TX-OpTic-color-darkmode.png": "OpTic Texas",
        "ATL-FaZe-color-darkmode.png": "Atlanta FaZe",
        "BOS-Breach-color-darkmode.png": "Boston Breach",
        "CAR_ROYAL_RAVENS_ALLMODE.webp": "Carolina Royal Ravens",
        "Cloud9_New_York_darkmodee.webp": "Cloud9 New York",
        "Los_Angeles_Guerrillas_M8logo_square.webp": "LA Guerrillas M8",
        "LA-Thieves-color-allmode.png": "Los Angeles Thieves",
        "MIA_HERETICS_ALLMODE.webp": "Miami Heretics",
        "Minnesota_ROKKR_RED.webp": "Minnesota ROKKR",
        "TO-Ultra-color-darkmode.png": "Toronto Ultra",
        "SEA-Surge-color-allmode.png": "Vancouver Surge",
        "Las_Vegas_Falconslogo_square.webp": "Vegas Falcons"
    }

    # List of match modes in order
    match_modes = ["Hardpoint", "Search", "Control", "Hardpoint", "Search"]

    # Iterate over each match to extract team names and scores
    for match_idx, match in enumerate(matches):
        # Get all <p> elements for scores
        score_elements = match.find_all('p')
        
        if len(score_elements) < 3:  # Ensure we have at least 3 elements (team1 score, separator, team2 score)
            print(f"⚠️ Skipping match {match_idx}: Not enough <p> elements found.")
            continue

        # Extract scores
        team_1_score = int(score_elements[0].get_text(strip=True))
        team_2_score = int(score_elements[2].get_text(strip=True))

        # Get team image filenames safely
        img_elements = match.find_all('img')
        if len(img_elements) < 2:
            print(f"⚠️ Skipping match {match_idx}: Not enough <img> elements found.")
            continue

        team_1_filename = img_elements[0]['src'].split('/')[-1].split('?')[0]
        team_2_filename = img_elements[1]['src'].split('/')[-1].split('?')[0]

        # Team name mapping
        team_1_name = team_name_mapping.get(team_1_filename, "Unknown")
        team_2_name = team_name_mapping.get(team_2_filename, "Unknown")

        print(f"Extracted Team 1 Name: {team_1_name}")
        print(f"Extracted Team 2 Name: {team_2_name}")

        # Ensure we don't exceed the number of predefined match modes
        if match_idx >= len(match_modes):
            print(f"⚠️ Skipping match {match_idx}: More matches than expected.")
            continue

        match_mode = match_modes[match_idx]

        # Store result
        results.append({
            'team_1': team_1_name,
            'team_1_score': team_1_score,
            'team_2': team_2_name,
            'team_2_score': team_2_score,
            'mode': match_mode
        })


        # Determine the winner of the match
        if team_1_score > team_2_score:
            winner = team_1_name
            loser = team_2_name
        elif team_2_score > team_1_score:
            winner = team_2_name
            loser = team_1_name
        else:
            continue  # If there is a tie (not expected in this case)

        # Count the win for the winning team
        if winner not in team_wins:
            team_wins[winner] = 0
        team_wins[winner] += 1

        # Count the loss for the losing team
        if loser not in team_wins:
            team_wins[loser] = 0
        team_wins[loser] += 0

    # Now, open the existing DataAid.json file
    with open(json_file_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    # For each match result, update the corresponding mode
    for result in results:
        team_1 = result['team_1']
        team_2 = result['team_2']
        mode = result['mode']

        if mode == "Hardpoint":
            data[team_1]["Hardpoint"].append("W" if result['team_1_score'] > result['team_2_score'] else "L")
            data[team_2]["Hardpoint"].append("L" if result['team_1_score'] > result['team_2_score'] else "W")
        elif mode == "Search":
            data[team_1]["Search"].append("W" if result['team_1_score'] > result['team_2_score'] else "L")
            data[team_2]["Search"].append("L" if result['team_1_score'] > result['team_2_score'] else "W")
        elif mode == "Control":
            data[team_1]["Control"].append("W" if result['team_1_score'] > result['team_2_score'] else "L")
            data[team_2]["Control"].append("L" if result['team_1_score'] > result['team_2_score'] else "W")

    # Update the 'Win/Loss' section for the teams
    if team_wins.get(team_1, 0) > team_wins.get(team_2, 0):
        data[team_1]["Win/Loss"].append("W")
        data[team_2]["Win/Loss"].append("L")
    else:
        data[team_1]["Win/Loss"].append("L")
        data[team_2]["Win/Loss"].append("W")

    # Save the updated data back to the DataAid.json file
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4)

    print("DataAid.json has been updated.")

# Example usage
file_path = "cdl_stats.html"  # Replace with your actual file path for the HTML
json_file_path = "DataAid.json"  # Path to the existing DataAid.json file
parse_cdl_html_and_update_json(file_path, json_file_path)
