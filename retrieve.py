import requests
import json
import time
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import yaml
from argparse import ArgumentParser
from utils.browse import WebBrowser
from utils.find import HTMLFinder

import os

def update_with_skip_NA(old_dict, new_dict):
    # skip the new dict's value if it is "N/A"
    for key in old_dict:
        if key not in new_dict: continue
        if new_dict[key] != "N/A":
            old_dict[key] = new_dict[key]
    return old_dict


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='jacob')
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    cfg = yaml.safe_load(open(args.config, 'r'))[args.department]
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))
    api_key = os.environ.get('API_KEY')

    # initialization
    data_dir = cfg['data_dir']
    os.makedirs(data_dir, exist_ok=True)
    base_url = cfg['base_url']
    profile_base_url = cfg['profile_base_url']
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'])
    html_finder = HTMLFinder(api_key=api_key, model=crawler_cfg['model'], token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    if os.path.exists(os.path.join(data_dir, 'faculty_profiles.html')):
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'r') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
    else:
        soup = web_browser.scroll_to_bottom(base_url)
        # save the soup to a file
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'w') as f:
            f.write(str(soup))

    # Chunk the HTML content to avoid rate limits
    if os.path.exists(os.path.join(data_dir, 'faculty_entries.json')):
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'r') as f:
            faculty_entries = json.load(f)
    else:
        faculty_entries = html_finder.find_profile_from_faculty_list(soup)
        # save the faculty entries to a file
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'w') as f:
            json.dump(faculty_entries, f)
    print("Finish fetching faculty entries")


    for entry in tqdm(faculty_entries, desc="Fetching faculty profiles"):
        time.sleep(crawler_cfg['sleep_time'])  # Sleep to avoid rate limits
        try:
            if not entry["profile_address"].startswith('/'):
                entry["profile_address"] = f'/{entry["profile_address"]}'
            response = requests.get(f'{profile_base_url}{entry["profile_address"]}')
            response.raise_for_status()  # Check for request errors

            # faculty page in the department page
            soup = BeautifulSoup(response.content, 'html.parser')
            entry.update(html_finder.find_faculty_info_in_html(soup))
        except Exception as e:
            print(f"An error occurred: {e}")
            continue

        # browse personal page gathered from faculty page
        try:
            response = requests.get(entry['website'])
            response.raise_for_status()  # Check for request errors

            # faculty page in the department page
            soup = BeautifulSoup(response.content, 'html.parser')
            entry = update_with_skip_NA(entry, html_finder.find_faculty_info_in_html(soup))
            print(f"Name: {entry['name']}, Email: {entry['email']}")
        except Exception as e:
            print(f"An error occurred: {e}")
            continue

    # Create a DataFrame from the extracted data
    df = pd.DataFrame(faculty_entries)
    df.to_csv(f'{data_dir}/faculty_profiles.csv', index=False)
    print('Data has been saved to faculty_profiles.csv')

