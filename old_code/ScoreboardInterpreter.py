from bs4 import BeautifulSoup
import json

def parse_cdl_html(file_path):
    # Hardcoded file path
    file_path = 'output.html'

    # Open and read the HTML file
    with open(file_path, 'r') as file:
        html_data = file.read()

    # Parse the HTML data with BeautifulSoup
    soup = BeautifulSoup(html_data, 'html.parser')


    # Find all player rows (excluding team headers)
    player_data = []
    rows = soup.find_all("tr", class_="css-e5a2k5")

    for row in rows:
        cols = row.find_all("td")

        if len(cols) >= 7:  # Ensure the row has enough columns
            player_name = cols[0].text.strip()
            kd_ratio = cols[3].text.strip()
            bp_rating = cols[6].text.strip()

            player_data.append({
                "player": player_name,
                "KD": kd_ratio,
                "BP_Rating": bp_rating
            })

    # Save to JSON
    with open("cdl_stats.json", "w", encoding="utf-8") as json_file:
        json.dump(player_data, json_file, indent=4)

    return player_data

# Example usage
file_path = "cdl_stats.html"  # Replace with your actual file path
data = parse_cdl_html(file_path)
print(json.dumps(data, indent=4))
