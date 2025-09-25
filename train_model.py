# train_model.py

import os
import json
from utils.drafting_ai import train_and_save_prediction_model
from utils.data_processing import HERO_PROFILES, HERO_DAMAGE_TYPE

# This is a standalone script to train your model.
# Run this from your terminal: python train_model.py

def main():
    """
    Loads all match data from the 'data' directory and uses it to train
    and save the prediction model.
    """
    print("Starting model training process...")
    
    data_dir = "data"
    if not os.path.exists(data_dir):
        print(f"Error: Data directory '{data_dir}' not found.")
        return

    all_matches = []
    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_matches.extend(data)
            except Exception as e:
                print(f"Could not read or parse {filename}: {e}")

    if not all_matches:
        print("No match data found to train the model.")
        return
        
    print(f"Loaded a total of {len(all_matches)} matches for training.")

    try:
        feedback = train_and_save_prediction_model(
            all_matches,
            HERO_PROFILES,
            HERO_DAMAGE_TYPE
        )
        print(feedback)
    except Exception as e:
        print(f"An error occurred during training: {e}")


if __name__ == "__main__":
    main()
