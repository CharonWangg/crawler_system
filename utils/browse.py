import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

class WebBrowser:
    def __init__(self, headless=True, sleep_time=0.5):
        self.headless = headless
        self.sleep_time = sleep_time

    def google_search(self, query):
        search_url = f"https://www.google.com/search?q={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        return response

    def scroll_to_bottom(self, url):
        # Set up Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Initialize WebDriver
        service = Service('/opt/homebrew/bin/chromedriver')  # Replace with your actual chromedriver path
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # URL of the main faculty profiles page
        driver.get(url)

        # Scroll down to load all dynamic content
        scroll_pause_time = self.sleep_time # Pause time between scrolls
        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down to the bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait for new content to load
            time.sleep(scroll_pause_time)
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Extract the page source once all content is loaded
        page_source = driver.page_source

        # Close WebDriver
        driver.quit()

        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        return soup