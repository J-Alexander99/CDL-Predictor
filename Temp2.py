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

    for match in matches:
        # Debug: Print the structure of the match object
        print("Match HTML structure:", match)

        p_tags = match.find_all('p')

        # Check if there are at least 3 <p> tags to prevent index error
        if len(p_tags) < 3:
            print(f"⚠️ Not enough <p> tags found for match: {match}")
            continue  # Skip this match if the structure is incorrect

        team_1_score = int(p_tags[0].get_text(strip=True))
        team_2_score = int(p_tags[2].get_text(strip=True))

        team_1_filename = match.find_all('img')[0]['src'].split('/')[-1].split('?')[0]
        team_2_filename = match.find_all('img')[1]['src'].split('/')[-1].split('?')[0]

        team_1_name = team_name_mapping.get(team_1_filename, "Unknown")
        team_2_name = team_name_mapping.get(team_2_filename, "Unknown")

        if team_1_name == "Unknown":
            print(f"⚠️ Unmatched Team 1 Filename: {team_1_filename} (Add to mapping)")
        if team_2_name == "Unknown":
            print(f"⚠️ Unmatched Team 2 Filename: {team_2_filename} (Add to mapping)")

    with open(json_file_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    player_data = parse_final_player_stats(file_path)

    if len(player_data) == 8:
        team_1_players = player_data[:4]
        team_2_players = player_data[4:]

        def add_player_stats(team_name, players):
            data.setdefault(team_name, {}).setdefault("KDs", {})
            data.setdefault(team_name, {}).setdefault("BP", {})

            for player in players:
                player_name = player['player']
                kd_ratio = player['KD']
                bp_rating = player['BP_Rating']

                data[team_name]["KDs"].setdefault(player_name, []).append(kd_ratio)
                data[team_name]["BP"].setdefault(player_name, []).append(bp_rating)

        add_player_stats(team_1_name, team_1_players)
        add_player_stats(team_2_name, team_2_players)

    data.setdefault(team_1_name, {}).setdefault("Win/Loss", [])
    data.setdefault(team_2_name, {}).setdefault("Win/Loss", [])

    # if team_1_score > team_2_score:
    #     data[team_1_name]["Win/Loss"].append("W")
    #     data[team_2_name]["Win/Loss"].append("L")
    # else:
    #     data[team_1_name]["Win/Loss"].append("L")
    #     data[team_2_name]["Win/Loss"].append("W")

    map_results = soup.find_all("div", {"class": "css-2bd7qut"})
    map_results_data = [result.text.strip() for result in map_results]

    print(f"Map Results Data: {map_results_data}")

    data.setdefault(team_1_name, {}).setdefault("Hardpoint", [])
    data.setdefault(team_2_name, {}).setdefault("Hardpoint", [])
    data.setdefault(team_1_name, {}).setdefault("Search", [])
    data.setdefault(team_2_name, {}).setdefault("Search", [])
    data.setdefault(team_1_name, {}).setdefault("Control", [])
    data.setdefault(team_2_name, {}).setdefault("Control", [])

    for map_result in map_results_data:
        if map_result == "Hardpoint":
            data[team_1_name]["Hardpoint"].append("W" if team_1_score > team_2_score else "L")
            data[team_2_name]["Hardpoint"].append("L" if team_1_score > team_2_score else "W")

        elif map_result == "Search":
            data[team_1_name]["Search"].append("W" if team_1_score > team_2_score else "L")
            data[team_2_name]["Search"].append("L" if team_1_score > team_2_score else "W")

        elif map_result == "Control":
            data[team_1_name]["Control"].append("W" if team_1_score > team_2_score else "L")
            data[team_2_name]["Control"].append("L" if team_1_score > team_2_score else "W")

    if team_1_score > team_2_score:
        winner, loser = team_1_name, team_2_name
    else:
        winner, loser = team_2_name, team_1_name

    data.setdefault(winner, {}).setdefault("Head 2 Head", {}).setdefault(loser, 0)
    data[winner]["Head 2 Head"][loser] += 1

    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4)

    print("DataAid.json has been updated.")

def parse_final_player_stats(file_path):
    with open(file_path, 'r') as file:
        html_data = file.read()

    soup = BeautifulSoup(html_data, 'html.parser')
    tables = soup.find_all('table')

    if not tables:
        print("No tables found in the HTML.")
        return []

    final_table = tables[-1]
    player_data = []
    rows = final_table.find_all("tr", class_="css-e5a2k5")

    for row in rows:
        cols = row.find_all("td")

        if len(cols) >= 7:
            player_name = cols[0].text.strip()
            kd_ratio = cols[3].text.strip()
            bp_rating = cols[6].text.strip()

            player_data.append({
                "player": player_name,
                "KD": kd_ratio,
                "BP_Rating": bp_rating
            })

    return player_data

# Example usage
file_path = "cdl_stats.html"  
json_file_path = "DataAid.json"

parse_cdl_html_and_update_json(file_path, json_file_path)
