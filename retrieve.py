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
from concurrent.futures import ProcessPoolExecutor, as_completed


def fetch_profile(entry, profile_base_url, api_key, crawler_cfg, profile_dir):
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'])
    html_finder = HTMLFinder(api_key=api_key, model=crawler_cfg['model'],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    try:
        if not entry["profile_address"].startswith('/'):
            entry["profile_address"] = f'/{entry["profile_address"]}'
        response = requests.get(f'{profile_base_url}{entry["profile_address"]}')
        response.raise_for_status()  # Check for request errors

        # faculty page in the department page
        official_soup = BeautifulSoup(response.content, 'html.parser')
        entry.update(html_finder.find_faculty_info_in_html(official_soup))

        # browse personal page gathered from faculty page
        # update prompt
        extra_prompt = open('prompts/substitute_previous_info.txt', 'r').read().replace('[previous_info]', str(entry))
        if entry['website']:
            response = requests.get(entry['website'])
            response.raise_for_status()  # Check for request errors

            # faculty page in the department page
            personal_soup = BeautifulSoup(response.content, 'html.parser')
            personal_soup = f"This website: {entry['website']}\n" + str(personal_soup)
        else:
            # try to gather personal information from google search
            search_query = f"{entry['name']} {entry['university']}"
            personal_soup = html_finder.find_relevant_content_from_google(web_browser, search_query)
        # dig deeper about the website to gather more information (team/research project)
        personal_soup = html_finder.find_relevant_content_from_lab(web_browser, personal_soup)

        # generate the final summary table of the faculty
        entry.update(html_finder.find_faculty_info_in_html(personal_soup, extra_prompt=extra_prompt))

        # save the official and personal profile to files
        if not os.path.exists(f'{profile_dir}/{entry["name"]}'):
            os.makedirs(f'{profile_dir}/{entry["name"]}', exist_ok=True)
        with open(f'{profile_dir}/{entry["name"]}/offcial_profile.html', 'w', encoding='utf-8') as file:
            file.write(str(official_soup))
        if entry['website']:
            with open(f'{profile_dir}/{entry["name"]}/personal_profile.html', 'w', encoding='utf-8') as file:
                file.write(str(personal_soup))

        print(f"Finish fetching {entry['name']}'s profile")
        print(entry)

        return entry
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='jacob')
    parser.add_argument('--num_processes', type=int, default=1)
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    cfg = yaml.safe_load(open(args.config, 'r'))[args.department]
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))
    api_key = os.environ.get('API_KEY')

    # initialization
    data_dir = cfg['data_dir']
    profile_dir = f'{data_dir}/profiles'
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)
    base_url = cfg['base_url']
    profile_base_url = cfg['profile_base_url']

    # Scroll down the faculty profiles page to load all the content
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'])
    if os.path.exists(os.path.join(data_dir, 'faculty_profiles.html')):
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
    else:
        soup = web_browser.scroll_to_bottom(base_url)
        # save the soup to a file
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup))

    # Find all the faculty profile entries
    if os.path.exists(os.path.join(data_dir, 'faculty_entries.json')):
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'r') as f:
            faculty_entries = json.load(f)
    else:
        html_finder = HTMLFinder(api_key=api_key, model=crawler_cfg['model'],
                                 token_limit_per_minute=crawler_cfg['token_limit_per_minute'])
        faculty_entries = html_finder.find_profile_from_faculty_list(soup)
        # save the faculty entries to a file
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'w') as f:
            json.dump(faculty_entries, f)
    print("Finish fetching faculty entries")

    # Fetch the individual faculty information
    with ProcessPoolExecutor(max_workers=args.num_processes) as executor:
        future_to_entry = {executor.submit(fetch_profile, entry, profile_base_url, api_key, crawler_cfg, profile_dir): entry for
                           entry in faculty_entries}
        results = []
        for future in tqdm(as_completed(future_to_entry), total=len(future_to_entry), desc="Fetching faculty profiles"):
            result = future.result()
            if result:
                results.append(result)
                time.sleep(crawler_cfg['sleep_time'])  # Sleep to avoid rate limits

    # Create a DataFrame from the extracted data
    df = pd.DataFrame(results)
    df.to_csv(f'{data_dir}/faculty_profiles.csv', index=False)
    print('Data has been saved to faculty_profiles.csv')
