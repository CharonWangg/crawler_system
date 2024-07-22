import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import random

class WebBrowser:
    def __init__(self, headless=True, sleep_time=0.5):
        self.headless = headless
        self.sleep_time = sleep_time
        self.init_browser()

    def init_browser(self):
        # Set up Chrome options
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")  # Run in headless mode

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Random user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0'
        ]
        user_agent = random.choice(user_agents)
        chrome_options.add_argument(f'user-agent={user_agent}')

        # Random window size
        window_sizes = [(1024, 768), (1280, 800), (1366, 768), (1920, 1080)]
        window_size = random.choice(window_sizes)
        chrome_options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')

        # Initialize WebDriver
        service = Service('/opt/homebrew/bin/chromedriver')  # Replace with your actual chromedriver path
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def quit(self):
        try:
            self.driver.close()
            self.driver.quit()
        except Exception as e:
            print(f"An error occurred inside quit_browser: {e}")

    def browse(self, url):
        # browse a website. First request, if blocked use selenium
        try:
            response = requests.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            try:
                self.driver.get(url)
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                print(f"An error occurred inside selenium browse: {e}")
                return None

    def multi_request(self, urls):
        responses = []
        for url in urls:
            if url:
                if url == "{}": continue
                response = self.browse(url)
                responses.append(response)
        return responses

    def google_search(self, query):
        search_url = f"https://www.google.com/search?q={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        return response

    def scroll_to_bottom(self, url):
        # URL of the main faculty profiles page
        self.driver.get(url)

        # Scroll down to load all dynamic content
        scroll_pause_time = self.sleep_time # Pause time between scrolls
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down to the bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait for new content to load
            time.sleep(scroll_pause_time)
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        return soup