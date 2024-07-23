import json
import time
import logging
import pandas as pd
from tqdm import tqdm
import yaml
from argparse import ArgumentParser
from utils.browse import WebBrowser
from utils.find import HTMLFinder
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime


def configure_logging(department):
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'{current_time}_{department}_faculty_retrieval.log')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def name_in_column(df, name, ignore_middle_name=True):
    # Normalize the names in the DataFrame and the input name
    try:
        df['normalized_name'] = df['name'].str.lower()
        name = name.lower()

        def normalize_name(n):
            n = n.replace(',', '').strip()
            parts = n.split()
            return ' '.join([parts[0], parts[-1]])

        def name_variants(n):
            parts = n.split()
            if len(parts) < 2:
                return [n]
            first_last = ' '.join([parts[0], parts[-1]])
            last_first = ' '.join([parts[-1], parts[0]])
            return [first_last, last_first]

        if ignore_middle_name:
            # Normalize names and create variants
            df['first_last_variants'] = df['normalized_name'].apply(lambda x: name_variants(normalize_name(x)))
            input_variants = name_variants(normalize_name(name))

            # Check if any variant matches
            return any(variant in df['first_last_variants'].explode().values for variant in input_variants)
        else:
            return name in df['normalized_name'].values
    except KeyError as e:
        return False


def fetch_profile(entry, api_key, crawler_cfg, profile_dir, logger, df, data_dir):
    if name_in_column(df.copy(), entry['name']):
        logger.info(f"Profile for {entry['name']} already exists, skipping")
        return entry, df
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'])
    html_finder = HTMLFinder(api_key=api_key, logger=logger, model=crawler_cfg['model'],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    logger.info(f"Fetching profile for {entry['name']}")
    official_soup = web_browser.browse(entry["profile_address"])
    entry.update(html_finder.find_faculty_info_in_html(official_soup, previous_info=entry))
    logger.info(f"Info after gathering from official profile: {entry}")

    # Browse personal page gathered from faculty page and google to find more information
    search_query = f"{entry['university']} {entry['name']} lab website"

    google_prompt = (f"Here is the previous gathered information: {entry}, "
                     f"include the previous 'website' in the return if you find it align with "
                     f"your search result analysis. Do not include the previous 'profile address' "
                     f"in the return.")
    personal_soup = html_finder.find_relevant_content_from_google(web_browser, search_query,
                                                                  previous_info=google_prompt)
    personal_soup = html_finder.find_relevant_content_from_lab(web_browser, personal_soup, previous_info=entry)

    entry.update(html_finder.find_faculty_info_in_html(personal_soup, previous_info=entry))

    logger.info(f"Info after gathering from personal profile: {entry}")

    # Save the official and personal profile to files
    profile_path = os.path.join(profile_dir, entry["name"])
    os.makedirs(profile_path, exist_ok=True)
    with open(os.path.join(profile_path, 'official_profile.html'), 'w', encoding='utf-8') as file:
        file.write(str(official_soup))
    if entry.get('website'):
        with open(os.path.join(profile_path, 'personal_profile.html'), 'w', encoding='utf-8') as file:
            file.write(str(personal_soup))

    web_browser.quit()

    logger.info(f"Finished fetching profile for {entry['name']}")
    logger.debug(entry)

    # Update the DataFrame and save it
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.drop_duplicates(subset=['name'], keep='last', inplace=True)
    df.to_csv(os.path.join(data_dir, 'faculty_profiles.csv'), index=False)
    logger.info(f"Saved profile for {entry['name']} to CSV")

    return entry, df

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='jacob')
    parser.add_argument('--num_processes', type=int, default=4)
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    cfg = yaml.safe_load(open(args.config, 'r'))[args.department]
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))
    api_key = os.environ.get('API_KEY')

    # Initialization
    logger = configure_logging(args.department)
    data_dir = cfg['data_dir']
    profile_dir = os.path.join(data_dir, 'profiles')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)
    base_url = cfg['base_url']
    profile_base_url = cfg['profile_base_url']

    logger.info("Starting to fetch faculty profiles")
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'])
    if os.path.exists(os.path.join(data_dir, 'faculty_profiles.html')):
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'r', encoding='utf-8') as f:
            soup = f.read()
    else:
        soup = web_browser.scroll_to_bottom(base_url)
        with open(os.path.join(data_dir, 'faculty_profiles.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup))

    if os.path.exists(os.path.join(data_dir, 'faculty_entries.json')):
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'r') as f:
            faculty_entries = json.load(f)
    else:
        html_finder = HTMLFinder(api_key=api_key, logger=logger, model=crawler_cfg['model'],
                                 token_limit_per_minute=crawler_cfg['token_limit_per_minute'])
        faculty_entries = html_finder.find_profile_from_faculty_list(soup, profile_base_url)
        with open(os.path.join(data_dir, 'faculty_entries.json'), 'w') as f:
            json.dump(faculty_entries, f)

    logger.info(f"Finished fetching faculty entries, in total {len(faculty_entries)} entries.")
    logger.info(str(faculty_entries))

    # Create an empty DataFrame or load existing data
    csv_path = os.path.join(data_dir, 'faculty_profiles.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame()

    # Process the faculty entries
    for entry in tqdm(faculty_entries, desc='Processing faculty profiles'):
        new_entry, df = fetch_profile(entry, api_key, crawler_cfg, profile_dir, logger, df, data_dir)

    logger.info('All profiles have been processed and saved.')
