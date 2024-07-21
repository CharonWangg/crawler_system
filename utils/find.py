import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

import os
from openai import OpenAI


class HTMLFinder:
    model_limit = {
        "gpt-4o-mini": 60000,
        "gpt-3.5-turbo": 200000
    }
    def __init__(self, api_key, model="gpt-4o-mini", token_limit_per_minute=60000, sleep_time=60):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key
        )
        self.model = model
        self.token_limit_per_minute = token_limit_per_minute
        self.sleep_time = sleep_time

    def





TOKEN_LIMIT_PER_MINUTE = 60000  # extreme large number for chatgpt3.5 200000 tokens, 60000 for chatgpt4
SLEEP_TIME = 60

api_key = "sk-proj-lPvjprJp4QKX73lqPXFST3BlbkFJy6fvhoMHKyqEiM8tGu7E"
# Define your OpenAI API key
client = OpenAI(
    # This is the default and can be omitted
    api_key=api_key,

)

def scroll_down_page(url='https://jacobsschool.ucsd.edu/faculty/profiles', speed=0.5):
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
    scroll_pause_time = 0.5  # Pause time between scrolls
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

def find_profile_with_bs4(html_content):
    # Find all the faculty profile entries
    profiles = html_content.find_all('div', class_='col-4 py-2')

    hrefs = []
    for entry in profiles:
        link_element = entry.find('span', class_='font-weight-bold').find('a')
        href = link_element['href']
        hrefs.append(href)
    return

def find_profile_in_html(html_content):
    # Prompt to instruct GPT-4 to extract email from the HTML content
    prompt = (
        f"Extract the faculty profile address, faculty position, department, and domain "
        f"from the following HTML content. Only return the information in the format of a list of dicts that they"
        f"have keys 'name', profile_address', 'position', 'department', and 'domain'. Do not include any other text. "
        f"Here is the HTML content:\n\n{html_content}\n\n"
        f"Return the result as a JSON object:"
    )

    try:
        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4o-mini",
        )

        # Extract the email address from the response
        profile = response.choices[0].message.content.replace('```json\n', '').replace('```', '')
        profile = json.loads(profile)

        return profile
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def find_email_in_html(html_content, ):
    # Prompt to instruct GPT-4 to extract email from the HTML content
    prompt = (f"Extract the email address from the following HTML content, only return the "
              f"email and do not return other things:\n\n{html_content}")

    try:
        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-3.5-turbo",
        )

        # Extract the email address from the response
        email = response.choices[0].message.content
        return email
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def chunk_html(html_content, chunk_size):
    html_str = str(html_content)
    return [html_str[i:i+chunk_size] for i in range(0, len(html_str), chunk_size)]


data_dir = 'data/engineering'
os.makedirs(data_dir, exist_ok=True)


# Define the base URL
base_url = 'https://jacobsschool.ucsd.edu/faculty/profiles'
base_profile_url = 'https://jacobsschool.ucsd.edu'

# # URL of the main faculty profiles page
# url = f'{base_url}/faculty/profiles'
#
# # Send a GET request to the website
# response = requests.get(url)
# response.raise_for_status()  # Check for request errors
#
# # Parse the HTML content
# soup = BeautifulSoup(response.content, 'html.parser')
if os.path.exists(os.path.join(data_dir, 'faculty_profiles.html')):
    with open(os.path.join(data_dir, 'faculty_profiles.html'), 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
else:
    soup = scroll_down_page(base_url, speed=0.5)
    # save the soup to a file
    with open(os.path.join(data_dir, 'faculty_profiles.html'), 'w') as f:
        f.write(str(soup))

# Chunk the HTML content to avoid rate limits
html_chunks = chunk_html(soup, chunk_size=TOKEN_LIMIT_PER_MINUTE)

faculty_entries = []

# Process each chunk
for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
    chunk_faculty_entries = find_profile_in_html(chunk)
    if chunk_faculty_entries:
        faculty_entries.extend(chunk_faculty_entries)
    print(f"Processed chunk {i + 1}/{len(html_chunks)}")
    print(f"Found {len(faculty_entries)} faculty entries")
    if i != len(html_chunks) - 1:
        time.sleep(SLEEP_TIME)  # Sleep to avoid rate limits
print("Finish fetching faculty entries")
print(faculty_entries)
# save the faculty entries to a file
with open(os.path.join(data_dir, 'faculty_entries.json'), 'w') as f:
    json.dump(faculty_entries, f)

for entry in faculty_entries:
    time.sleep(1)  # Sleep to avoid rate limits
    response = requests.get(f'{base_profile_url}{entry["profile_address"]}')
    response.raise_for_status()  # Check for request errors

    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    entry["email"] = find_email_in_html(soup)

    print(f"Name: {entry['name']}, Email: {entry['email']}")

# Create a DataFrame from the extracted data
df = pd.DataFrame(faculty_entries)
df.to_csv(f'{data_dir}/faculty_profiles.csv', index=False)
print('Data has been saved to faculty_profiles.csv')

