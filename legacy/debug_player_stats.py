"""Debug script to check player stats structure"""
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import time

options = Options()
options.add_argument('--headless')
driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

try:
    driver.get('https://www.breakingpoint.gg/match/214811/Toronto-KOI-vs-FaZe-Vegas-at-CDL-Major-1-Qualifier-2026')
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    rows = soup.find_all('tr', class_=lambda x: x and 'GameOverview_tr' in x)
    
    print(f'Total rows found: {len(rows)}\n')
    
    # Check if there are sections/tabs
    sections = soup.find_all(['button', 'div'], class_=lambda x: x and ('tab' in x.lower() or 'section' in x.lower()))
    print(f'Found {len(sections)} potential tab/section elements\n')
    
    insight_kills = []
    for i, row in enumerate(rows):
        cells = row.find_all('td')
        if cells and len(cells) >= 7:  # Changed from 8 to 7 to catch all formats
            player = cells[0].get_text(strip=True)
            kills = cells[1].get_text(strip=True) if len(cells) > 1 else '?'
            deaths = cells[2].get_text(strip=True) if len(cells) > 2 else '?'
            print(f'Row {i}: [{len(cells)} cells] {player} - K:{kills} D:{deaths}')
            if player == 'Insight' and kills != '?':
                try:
                    insight_kills.append(int(kills))
                except:
                    pass
        elif len(cells) == 0:
            print(f'Row {i}: [HEADER]')
    
    print(f'\n\nInsight kill counts found: {insight_kills}')
    print(f'Total: {sum(insight_kills)}')
    
    # Check for "Series" or "Total" labels
    print('\n\nSearching for "Series", "Total", or "Overall" text:')
    text = soup.get_text()
    if 'Series' in text:
        print('Found "Series" in page text')
    if 'Total' in text:
        print('Found "Total" in page text')
    if 'Overall' in text:
        print('Found "Overall" in page text')
    
finally:
    driver.quit()
