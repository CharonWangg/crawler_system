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


def configure_logging(department, type='faculty'):
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'{current_time}_{department}_{type}_retrieval.log')

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


def fetch_profile(entry, crawler_cfg, profile_dir, logger, df, data_dir, proxy=False, parent_type='faculty'):
    if name_in_column(df.copy(), entry['name']):
        logger.info(f"Profile for {entry['name']} already exists, skipping")
        return entry, df
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'], proxy=proxy)
    html_finder = HTMLFinder(logger=logger, model=crawler_cfg[crawler_cfg['model']],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    logger.info(f"Fetching profile for {entry['name']}")
    official_soup = web_browser.browse(entry["profile_address"], human_browse=True)
    if parent_type == 'mentee':
        entry.update(html_finder.find_mentee_info_in_html(official_soup, previous_info=entry))
    elif parent_type == 'faculty':
        entry.update(html_finder.find_faculty_info_in_html(official_soup, previous_info=entry))
    else:
        raise ValueError(f"Invalid mentor type: {parent_type}")
    
    logger.info(f"Info after gathering from official profile: {entry}")

    # Browse personal page gathered from faculty page and google to find more information
    if parent_type == 'mentee':
        search_query = f"{entry['university']} {entry['name']} personal website"
    elif parent_type == 'faculty':
        search_query = f"{entry['university']} {entry['name']} lab"

    google_prompt = (f"Here is the previous gathered information: {entry}, "
                     f"include the previous 'website' in the return if you find it align with "
                     f"your search result analysis. Do not include the previous 'profile address' "
                     f"in the return.")
    personal_soup = html_finder.find_relevant_content_from_google(web_browser, search_query,
                                                                  previous_info=google_prompt)

    if parent_type == 'mentee':
        entry.update(html_finder.find_mentee_info_in_html(personal_soup, previous_info=entry))
    elif parent_type == 'faculty':
        personal_soup = html_finder.find_relevant_content_from_lab(web_browser, personal_soup, previous_info=entry)
        entry.update(html_finder.find_faculty_info_in_html(personal_soup, previous_info=entry))
    else:
        raise ValueError(f"Invalid mentor type: {parent_type}")

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
    df.to_csv(os.path.join(data_dir, f'{parent_type}_profiles.csv'), index=False)
    logger.info(f"Saved profile for {entry['name']} to CSV")

    return entry, df

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='jacob')
    parser.add_argument('--parent_type', type=str, default='faculty')
    parser.add_argument('--num_processes', type=int, default=4)
    parser.add_argument('--proxy', type=bool, default=False)
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    parent_type = args.parent_type
    cfg = yaml.safe_load(open(args.config, 'r'))[parent_type][args.department]
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))

    # Initialization
    logger = configure_logging(args.department, type=parent_type)
    data_dir = cfg['data_dir']
    profile_dir = os.path.join(data_dir, 'profiles')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)
    base_url = cfg['base_url']
    profile_base_url = cfg['profile_base_url']
    base_university, base_department = args.config.split('/')[-1].replace('.yaml', ''), args.department

    logger.info(f"Starting to fetch {parent_type} profiles")
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'], proxy=args.proxy)
    if os.path.exists(os.path.join(data_dir, f'{parent_type}_profiles.html')):
        with open(os.path.join(data_dir, f'{parent_type}_profiles.html'), 'r', encoding='utf-8') as f:
            soup = f.read()
    else:
        soup = web_browser.scroll_to_bottom(base_url)
        with open(os.path.join(data_dir, f'{parent_type}_profiles.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup))

    if os.path.exists(os.path.join(data_dir, f'{parent_type}_entries.json')):
        with open(os.path.join(data_dir, f'{parent_type}_entries.json'), 'r') as f:
            faculty_entries = json.load(f)
    else:
        html_finder = HTMLFinder(logger=logger, model=crawler_cfg[crawler_cfg['model']],
                                 token_limit_per_minute=crawler_cfg['token_limit_per_minute'])
        if parent_type == 'faculty':
            faculty_entries = html_finder.find_profile_from_faculty_list(soup, profile_base_url)
        elif parent_type == 'mentee':
            faculty_entries = html_finder.find_profile_from_student_list(soup, profile_base_url)
        else:
            raise ValueError(f"Invalid mentor type: {parent_type}")
        # fill the department and university information if not provided to mitigate hallucination
        for entry in faculty_entries:
            entry['department'] = base_department
            entry['university'] = base_university

        with open(os.path.join(data_dir, f'{parent_type}_entries.json'), 'w') as f:
            json.dump(faculty_entries, f)

    logger.info(f"Finished fetching {parent_type} entries, in total {len(faculty_entries)} entries.")
    logger.info(str(faculty_entries))

    # Create an empty DataFrame or load existing data
    csv_path = os.path.join(data_dir, f'{parent_type}_profiles.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame()

    # Process the faculty entries
    for entry in tqdm(faculty_entries, desc=f'Processing {parent_type} profiles'):
        new_entry, df = fetch_profile(entry, crawler_cfg, profile_dir, logger, df, data_dir, args.proxy, parent_type)

    logger.info('All profiles have been processed and saved.')
