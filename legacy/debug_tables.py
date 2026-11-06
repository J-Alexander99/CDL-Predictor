from bs4 import BeautifulSoup
import re

soup = BeautifulSoup(open('data/debug_page.html', encoding='utf-8').read(), 'html.parser')
rows = soup.find_all('tr', class_=re.compile(r'GameOverview_tr'))

print(f'Total rows: {len(rows)}\n')

for i, row in enumerate(rows[:15]):
    cells = row.find_all('td')
    text = row.get_text(' ', strip=True)
    print(f'Row {i}: {len(cells)} cells - {text[:120]}')
