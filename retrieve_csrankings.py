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
from multiprocessing import Manager
import threading


def configure_logging():
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'{current_time}_csrankings_retrieval.log')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def aggregate_csvs(data_dir):
    df = pd.read_csv(os.path.join(data_dir, 'CSrankings', 'csrankings.csv'))
    df = df.drop(columns='scholarid')
    df.columns = ['name', 'university', 'website']
    df['profile_address'] = df['website']
    return df


def name_in_column(df, name, ignore_middle_name=True):
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
            df['first_last_variants'] = df['normalized_name'].apply(lambda x: name_variants(normalize_name(x)))
            input_variants = name_variants(normalize_name(name))
            return any(variant in df['first_last_variants'].explode().values for variant in input_variants)
        else:
            return name in df['normalized_name'].values
    except KeyError as e:
        return False


def fetch_profile(entry, crawler_cfg, profile_dir, logger, proxy=False):
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'], proxy=proxy)
    html_finder = HTMLFinder(logger=logger, model=crawler_cfg[crawler_cfg['model']],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    logger.info(f"Fetching profile for {entry['name']}")

    try:
        try:
            personal_soup = web_browser.browse(entry["website"], human_browse=True).text
        except AttributeError as e:
            search_query = f"{entry['university']} {entry['name']} lab"
            google_prompt = (f"Here is the previous gathered information: {entry}, "
                             f"include the previous 'website' in the return if you find it align with "
                             f"your search result analysis. Do not include the previous 'profile address' "
                             f"in the return.")
            personal_soup = html_finder.find_relevant_content_from_google(web_browser, search_query,
                                                                          previous_info=google_prompt, only_text=True)
        entry.update(html_finder.find_faculty_info_in_html(personal_soup, previous_info=entry))

        logger.info(f"Info after gathering from personal profile: {entry}")

        profile_path = os.path.join(profile_dir, entry["name"])
        os.makedirs(profile_path, exist_ok=True)
        with open(os.path.join(profile_path, 'personal_profile.html'), 'w', encoding='utf-8') as file:
            file.write(str(personal_soup))
    except Exception as e:
        logger.error(f"Error fetching profile for {entry['name']}: {e}")

    web_browser.quit()

    logger.info(f"Finished fetching profile for {entry['name']}")
    logger.debug(entry)

    return entry


def process_entry(entry, crawler_cfg, profile_dir, logger, shared_dict, proxy):
    new_entry = fetch_profile(entry, crawler_cfg, profile_dir, logger, proxy)
    if new_entry:
        shared_dict[entry['name']] = new_entry
    return new_entry


def periodic_saver(shared_dict, csv_path, interval=300):
    while True:
        time.sleep(interval)
        new_entries = list(shared_dict.values())
        if new_entries:
            new_df = pd.DataFrame(new_entries)
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df = pd.concat([df, new_df], ignore_index=True)
                df.drop_duplicates(subset=['name'], keep='last', inplace=True)
            else:
                df = new_df
            df.to_csv(csv_path, index=False)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/external.yaml')
    parser.add_argument('--num_processes', type=int, default=16)
    parser.add_argument('--proxy', type=bool, default=False)
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    cfg = yaml.safe_load(open(args.config, 'r'))['csrankings']
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))

    logger = configure_logging()
    data_dir = cfg['data_dir']
    profile_dir = os.path.join(data_dir, 'profiles')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)
    base_url = cfg['base_url']

    logger.info(f"Starting to fetch csrankings profiles")
    faculty_entries = aggregate_csvs(data_dir)

    csv_path = os.path.join(data_dir, f'faculty_profiles.csv')

    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path)
    else:
        existing_df = pd.DataFrame()

    manager = Manager()
    shared_dict = manager.dict()

    saver_thread = threading.Thread(target=periodic_saver, args=(shared_dict, csv_path))
    saver_thread.start()

    with ProcessPoolExecutor(max_workers=args.num_processes) as executor:
        futures = []
        for i, entry in faculty_entries.iterrows():
            if not name_in_column(existing_df, entry['name']):
                futures.append(executor.submit(process_entry, entry.to_dict(), crawler_cfg, profile_dir, logger, shared_dict, args.proxy))

        for future in tqdm(as_completed(futures), total=len(futures), desc='Processing faculty profiles'):
            future.result()

    saver_thread.join()

    # Final save after all processes are done
    new_entries = list(shared_dict.values())
    if new_entries:
        new_df = pd.DataFrame(new_entries)
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df = pd.concat([df, new_df], ignore_index=True)
            df.drop_duplicates(subset=['name'], keep='last', inplace=True)
        else:
            df = new_df
        df.to_csv(csv_path, index=False)

    logger.info('All profiles have been processed and saved.')
