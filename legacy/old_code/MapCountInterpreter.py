from bs4 import BeautifulSoup

def determine_winner_and_score():
    # Hardcoded file path
    file_path = 'output.html'

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

    # Iterate over each match to extract team names and scores
    for match in matches:
        # Extract the team scores
        team_1_score = int(match.find_all('p')[0].get_text(strip=True))
        team_2_score = int(match.find_all('p')[2].get_text(strip=True))

        # Get team names (from image src URL)
        team_1_name = match.find_all('img')[0]['src'].split('/')[-1].split('-')[1]
        team_2_name = match.find_all('img')[1]['src'].split('/')[-1].split('-')[1]

        # Store the match result
        results.append({
            'team_1': team_1_name,
            'team_1_score': team_1_score,
            'team_2': team_2_name,
            'team_2_score': team_2_score
        })

        # Determine the winner of the match
        if team_1_score > team_2_score:
            winner = team_1_name
        elif team_2_score > team_1_score:
            winner = team_2_name
        else:
            continue  # If there is a tie (not expected in this case)

        # Count the win for the winning team
        if winner not in team_wins:
            team_wins[winner] = 0
        team_wins[winner] += 1

    # Determine the series score (final score in the format "3-2", "3-1", etc.)
    team_1 = results[0]['team_1']
    team_2 = results[0]['team_2']

    team_1_wins = team_wins.get(team_1, 0)
    team_2_wins = team_wins.get(team_2, 0)

    # Print the final result
    print(f"Final Score: {team_1_wins}-{team_2_wins}")

# Call the function without arguments
determine_winner_and_score()
