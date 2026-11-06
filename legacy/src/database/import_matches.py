"""
Import existing match JSON files into the database
"""
import json
import logging
from pathlib import Path
from typing import List

from src.database.db_manager import DatabaseManager
from src.utils.logger import setup_logger
from config.settings import LOGS_DIR


def import_json_matches(json_dir: Path, db_manager: DatabaseManager) -> int:
    """Import all JSON match files from a directory
    
    Args:
        json_dir: Directory containing match JSON files
        db_manager: Database manager instance
    
    Returns:
        Number of matches imported
    """
    logger = logging.getLogger("ImportMatches")
    
    # Find all JSON files
    json_files = list(json_dir.glob("match_*.json"))
    
    if not json_files:
        logger.warning(f"No match JSON files found in {json_dir}")
        return 0
    
    logger.info(f"Found {len(json_files)} match files to import")
    
    imported = 0
    errors = 0
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                match_data = json.load(f)
            
            db_manager.insert_match(match_data)
            imported += 1
            logger.info(f"Imported {json_file.name}")
            
        except Exception as e:
            errors += 1
            logger.error(f"Failed to import {json_file.name}: {e}")
    
    logger.info(f"Import complete: {imported} succeeded, {errors} failed")
    return imported


def main():
    """Main import script"""
    logger = setup_logger("ImportMatches", LOGS_DIR)
    
    # Initialize database
    db_manager = DatabaseManager()
    
    # Import from data/matches directory
    matches_dir = Path("data/matches")
    
    if not matches_dir.exists():
        logger.error(f"Matches directory not found: {matches_dir}")
        return
    
    # Import all matches
    imported = import_json_matches(matches_dir, db_manager)
    
    if imported > 0:
        logger.info("Updating statistics...")
        db_manager.update_all_stats()
        logger.info("Database import and stats update complete!")
    else:
        logger.warning("No matches imported")


if __name__ == "__main__":
    main()
