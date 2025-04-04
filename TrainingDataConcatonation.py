import os
import json

def load_match_files(matches_directory):
    """Load all match data from the specified directory."""
    match_data = []
    
    for filename in os.listdir(matches_directory):
        if filename.endswith('.json'):
            file_path = os.path.join(matches_directory, filename)
            with open(file_path, 'r') as file:
                match = json.load(file)
                match_data.append(match)
    
    return match_data

def save_training_data(training_data, output_file):
    """Save the aggregated match data into a single JSON file."""
    with open(output_file, 'w') as file:
        json.dump(training_data, file, indent=4)
    print(f"Training data saved to {output_file}")

def main():
    # Define the directory where match data is stored
    matches_directory = 'matches'  # Directory containing individual match JSON files
    output_file = 'training_data.json'  # The output file for the aggregated data

    # Load all the match files and aggregate them into a list
    match_data = load_match_files(matches_directory)

    # Save the aggregated match data as a single JSON file
    save_training_data(match_data, output_file)

if __name__ == '__main__':
    main()
