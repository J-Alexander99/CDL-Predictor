from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
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
url = input("Enter the webpage URL: ")
driver.get(url)

# Wait for dynamically loaded content (adjust timeout if needed)
time.sleep(5)

# Get page source after JavaScript execution
page_source = driver.page_source
driver.quit()

# Parse with BeautifulSoup
soup = BeautifulSoup(page_source, "html.parser")

# Find all relevant divs
tables1 = soup.find_all("div", class_="css-11t6rk7 m_e615b15f mantine-Card-root m_1b7284a3 mantine-Paper-root")
tables2 = soup.find_all("div", class_="m_b0c91715 mantine-Tabs-panel")

# Save to file for easier viewing
with open("cdl_stats.html", "w", encoding="utf-8") as f:
    if tables1:
        f.write("=== First Set of Divs ===\n")
        for idx, div in enumerate(tables1, 1):
            f.write(f"\nTable {idx}:\n")
            f.write(div.prettify())
            f.write("\n" + "=" * 80 + "\n")
    
    if tables2:
        f.write("\n=== Second Set of Divs ===\n")
        final_div = tables2[-1]  # Get the last div
        f.write(final_div.prettify())
        f.write("\n" + "=" * 80 + "\n")

print("Output saved to cdl_stats.html")
