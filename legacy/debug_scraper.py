"""
Debug script to save page HTML for analysis
"""
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
import time

# Set up browser
options = Options()
options.add_argument("--headless")
service = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=options)

# Load page
url = "https://www.breakingpoint.gg/match/214811/Toronto-KOI-vs-FaZe-Vegas-at-CDL-Major-1-Qualifier-2026"
driver.get(url)
time.sleep(5)

# Save HTML
with open("data/debug_page.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)

driver.quit()
print("Page saved to data/debug_page.html")
