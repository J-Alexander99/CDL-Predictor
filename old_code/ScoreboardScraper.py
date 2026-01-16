from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.firefox import GeckoDriverManager
import time

# Set up Selenium WebDriver for Firefox
options = Options()
options.add_argument("--headless")  # Run in headless mode (no GUI)
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Initialize WebDriver for Firefox
service = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=options)

# Open the webpage
url = "https://www.breakingpoint.gg/match/93816/OpTic-Texas-vs-Boston-Breach-at-CDL-Major-1-Qualifier-2025"
driver.get(url)

# Wait for dynamically loaded tables (adjust timeout if needed)
time.sleep(5)

# Get page source after JavaScript execution
page_source = driver.page_source
driver.quit()

# Parse with BeautifulSoup
soup = BeautifulSoup(page_source, "html.parser")

# Find all tables with the specified class
tables = soup.find_all("div", class_="m_b0c91715 mantine-Tabs-panel")

if tables:
    final_div = tables[-1]  # Get the last div
    with open("output.html", "w", encoding="utf-8") as f:
        f.write(final_div.prettify())
        f.write("\n" + "=" * 80 + "\n")
    print("Output saved to output.html")
else:
    print("No dynamically loaded divs found.")
