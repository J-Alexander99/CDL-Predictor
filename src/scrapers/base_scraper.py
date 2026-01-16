"""
Base scraper class with common functionality
"""
from abc import ABC, abstractmethod
from typing import Optional
import time

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup

from config.settings import HEADLESS_BROWSER, PAGE_LOAD_TIMEOUT, REQUEST_DELAY
from src.utils import setup_logger


class BaseScraper(ABC):
    """Base class for all web scrapers"""
    
    def __init__(self, headless: bool = HEADLESS_BROWSER):
        """
        Initialize the scraper
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.driver: Optional[webdriver.Firefox] = None
        self.logger = setup_logger(self.__class__.__name__)
    
    def _init_driver(self) -> None:
        """Initialize Selenium WebDriver"""
        if self.driver:
            return
        
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = Service(GeckoDriverManager().install())
        self.driver = webdriver.Firefox(service=service, options=options)
        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        self.logger.info("WebDriver initialized")
    
    def _close_driver(self) -> None:
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("WebDriver closed")
    
    def fetch_page(self, url: str, wait_time: float = REQUEST_DELAY) -> BeautifulSoup:
        """
        Fetch and parse a webpage
        
        Args:
            url: URL to fetch
            wait_time: Time to wait for dynamic content to load
        
        Returns:
            BeautifulSoup object of the page
        
        Raises:
            Exception: If page fails to load
        """
        try:
            self._init_driver()
            self.logger.info(f"Fetching: {url}")
            
            self.driver.get(url)
            time.sleep(wait_time)
            
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            
            self.logger.info("Page fetched successfully")
            return soup
            
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            raise
    
    @abstractmethod
    def scrape(self, *args, **kwargs):
        """
        Main scraping method - must be implemented by subclasses
        """
        pass
    
    def __enter__(self):
        """Context manager entry"""
        self._init_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._close_driver()
