import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from base64 import b64decode
import json

from bs4 import BeautifulSoup
import random

class WebBrowser:
    def __init__(self, headless=True, proxy=False, sleep_time=0.5):
        self.headless = headless
        self.proxy = proxy
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

    def wait_for_page_load(self, timeout=30):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.driver.execute_script("return document.readyState") == "complete":
                return True
            time.sleep(0.5)
        return False

    def quit(self):
        try:
            self.driver.close()
            self.driver.quit()
        except Exception as e:
            print(f"An error occurred inside quit_browser: {e}")

    def browse(self, url, human_browse=False):
        # browse a website. First request, if blocked use selenium
        try:
            if human_browse:
                self.driver.get(url)
                if self.wait_for_page_load():
                    return BeautifulSoup(self.driver.page_source, 'html.parser')
                else:
                    print(f"An error occurred inside human_browse: {url} is not valid")
            else:
                response = requests.get(url)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            try:
                self.driver.get(url)
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                print(f"An error occurred inside selenium browse: url {url} is not valid")
                return None

    def multi_request(self, urls):
        responses = []
        for url in urls:
            if url:
                if url == "{}": continue
                response = self.browse(url)
                responses.append(response)
        return responses

    def google_search(self, query, human_browse=True):
        if self.proxy:
            # Use Zyte API to get rotated proxies
            search_url = f"https://www.google.com/search?q={query}"
            api_response = requests.post(
                "https://api.zyte.com/v1/extract",
                auth=("d6e2548834c34ac68a369f4b4ec02aae", ""),
                json={
                    "url": search_url,
                    "httpResponseBody": True,
                },
            )
            response = b64decode(
                api_response.json()["httpResponseBody"])
        else:
            if not human_browse:
                response = requests.get(url)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            else:
                self.driver.get("https://www.google.com")
                q = self.driver.find_element(By.NAME, 'q')
                q.send_keys(query)
                q.submit()
                response = self.driver.page_source
        return response

    def select_option(self):
        wait = WebDriverWait(self.driver, 10)
        mat_select = wait.until(EC.element_to_be_clickable((By.ID, "mat-select-2")))

        # Click the mat-select element to open the dropdown
        mat_select.click()

        # Wait for the dropdown options to be visible
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "mat-option")))

        # Select the desired option (e.g., 50 items per page)
        options = self.driver.find_elements(By.CSS_SELECTOR, "mat-option")
        for option in options:
            if option.text.strip() == "100":
                option.click()
                break

    def scroll_to_bottom(self, url):
        # URL of the main faculty profiles page
        self.driver.get(url)

        # Hard-coding this part is too limited, use a LLM to analyze what should be done next to get the full page
        # For example, when there is a 'table-responsive, LLM should use corresponding wait functions in selenium
        if self.wait_for_page_load():
            try:
                wait = WebDriverWait(self.driver, 5)
                wait.until(EC.presence_of_all_elements_located((By.XPATH, '//*[@id="faculty"]')))
            except TimeoutException:
                # Handle the case where the faculty elements are not found
                print("Faculty elements not found within the given time frame or there is no hidden table.")
        else:
            print("Page did not load properly")

        # Select the maximum option if existed
        try:
            # so far only biology has this option
            self.select_option()
        except Exception as e:
            # ugly pass that should be replaced with proper error handling
            pass

        # Scroll down to load all dynamic content
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        count = 0
        while True:
            # Scroll down to the bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait for new content to load
            time.sleep(self.sleep_time)
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                count += 1
            if count > 5:
                break
            last_height = new_height

        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        return soup