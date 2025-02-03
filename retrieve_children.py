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
import ast
from retrieve_parent import name_in_column, configure_logging


def df_to_mentee_list(df):
    df = df.astype(str)
    df_dict = df.to_dict(orient='records')
    new_df_dict = []
    for entry in df_dict:
        new_df_dict.append({k: ast.literal_eval(v) if '{' in v and '}' in v else v for k, v in entry.items()})

    mentees = []
    for entry in new_df_dict:
        if entry['grad students']:
            mentees.extend([{'name': name, 'website': link, 'university': entry['university'],
                             'mentor': {
                                 entry['name']: entry['website'] if entry['website'] else entry['profile_address']}}
                            for name, link in entry['grad students'].items()])

        if entry['postdocs']:
            mentees.extend([{'name': name, 'website': link, 'university': entry['university'],
                             'mentor': {
                                 entry['name']: entry['website'] if entry['website'] else entry['profile_address']}}
                            for name, link in entry['postdocs'].items()])
    return mentees


def fetch_mentee_info(entry, crawler_cfg, df, proxy, logger):
    web_browser = WebBrowser(headless=True, sleep_time=crawler_cfg['sleep_time'], proxy=proxy)
    html_finder = HTMLFinder(model=crawler_cfg[crawler_cfg['model']],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'], logger=logger)

    logger.info(f"Fetching mentee information for {entry['name']}")

    search_query = f"{entry['university']} {entry['name']}"

    google_prompt = (f"Here is the previous gathered information: {entry}, "
                     f"include the previous 'website' in the return if you find it align with "
                     f"your search result analysis.")
    personal_soup = html_finder.find_relevant_content_from_google(web_browser, search_query,
                                                                  previous_info=google_prompt)
    entry = html_finder.find_mentee_info_in_html(personal_soup, previous_info=entry)

    logger.info(f"Info after gathering from personal profile: {entry}")

    # Save the official and personal profile to files
    profile_path = os.path.join(profile_dir, entry["name"])
    os.makedirs(profile_path, exist_ok=True)
    with open(os.path.join(profile_path, 'personal_profile.html'), 'w', encoding='utf-8') as file:
        file.write(str(personal_soup))

    web_browser.quit()

    logger.info(f"Finished fetching profile for {entry['name']}")
    logger.debug(entry)

    # Update the DataFrame and save it
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.drop_duplicates(subset=['name'], keep='last', inplace=True)
    df.to_csv(os.path.join(data_dir, 'mentee_profiles.csv'), index=False)
    logger.info(
        f"Saved profile for {entry['name']} to {os.path.join(data_dir, 'mentee_profiles.csv')}, {len(df)} entries in total")

    return entry, df


def build_mentee_df(mentee_entries, crawler_cfg, proxy, logger):
    # Create an empty DataFrame or load existing data
    csv_path = os.path.join(data_dir, 'mentee_profiles.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame()

    for entry in tqdm(mentee_entries, desc='Fetching mentee profiles'):
        entry['name'] = entry['name'].replace('Dr. ', '')
        if name_in_column(df.copy(), entry['name']):
            logger.info(f"Profile for {entry['name']} already exists, skipping")
            continue
        new_entry, df = fetch_mentee_info(entry, crawler_cfg, df, proxy, logger)
    return df


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='jacob')
    parser.add_argument('--num_processes', type=int, default=4)
    parser.add_argument('--proxy', type=bool, default=False)
    args = parser.parse_args()

    if os.environ.get('API_KEY') is None:
        raise ValueError("API_KEY is not set")

    cfg = yaml.safe_load(open(args.config, 'r'))['faculty']
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))

    # Initialization
    if args.department != 'all':
        cfg = {args.department: cfg[args.department]}
    logger = configure_logging(args.department, type='mentee')

    for department in cfg.keys():
        try:
            data_dir = cfg[department]['data_dir']
            profile_dir = os.path.join(data_dir, 'profiles')
            os.makedirs(data_dir, exist_ok=True)
            os.makedirs(profile_dir, exist_ok=True)

            logger.info(
                f"Fetching Graduate students/Postdocs' contacts from the gathered faculties in the {args.department} department.")
            if os.path.exists(os.path.join(data_dir, 'faculty_profiles.csv')):
                df = pd.read_csv(os.path.join(data_dir, 'faculty_profiles.csv'))
                mentee_entries = df_to_mentee_list(df)
            else:
                logger.error('No faculty profiles found. Please run retrieve_faculty.py first.')
                exit(1)

            mentee_df = build_mentee_df(mentee_entries, crawler_cfg, args.proxy, logger)
            logger.info(f"Finished processing all mentee profiles for the {args.department} department.")
        except Exception as e:
            logger.error(f"An error occurred while fetching mentee profiles: {e}")