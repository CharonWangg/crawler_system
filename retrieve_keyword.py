from glob import glob
import os
import re
import requests
from bs4 import BeautifulSoup
from argparse import ArgumentParser
import yaml
import pandas as pd
from utils.find import HTMLFinder
from retrieve_parent import configure_logging
from tqdm import tqdm


def clean_scraped_text(text):
    text = re.sub(r'[^\S\r\n]+', ' ', text)
    text = re.sub(r'[^a-zA-Z0-9,.!?;:\s]', '', text)
    return text


def clean_df(df):
    # TODO: clean the dataframe, remove the noise (mailto in email, etc.), fill the missing values (department)
    pass


def retrieve_profile_text(html, online=False):
    if online:
        soup = BeautifulSoup(html.content, 'html.parser').text
    else:
        with open(html, 'r') as f:
            soup = f.read()
        soup = BeautifulSoup(soup, 'html.parser').text
    soup = clean_scraped_text(soup)
    return soup


def process_profiles(df, profile_dir, html_finder, department, logger, entity_type):
    if 'keyword' not in df.columns:
        df['keyword'] = "{}"
    df['department'] = df['department'].apply(lambda x: department if x == "{}" else x)

    for i, row in tqdm(list(df.iterrows()), desc=f'Finding keywords for {entity_type} in {department}'):
        if "[" in row['keyword'] and "]" in row['keyword']:
            logger.info(f"Skipping {row['name']} as it already has keywords")
            continue
        official_path = os.path.join(profile_dir, row['name'], 'official_profile.html')
        personal_path = os.path.join(profile_dir, row['name'], 'personal_profile.html')
        official_text = retrieve_profile_text(official_path)
        try:
            personal_text = retrieve_profile_text(personal_path)
        except Exception as e:
            logger.error(f"{row['name']} does not have a personal profile")
            personal_text = ""
        # merge the two texts
        prompt = open('prompts/find_research_keywords_in_html.txt', 'r').read()
        html_content = ("\nHere is the personal website of this researcher in the department/university website:\n"
                        "[official_html]\nHere is the lab/personal website of this researcher:\n[personal_html]\n")
        html_content = html_content.replace('[official_html]', official_text)
        html_content = html_content.replace('[personal_html]', personal_text)
        keyword = html_finder.find_keywords_in_html(html_content, previous_info=row.to_dict())
        df.at[i, 'keyword'] = keyword

    return df


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/ucsd.yaml')
    parser.add_argument('--department', type=str, default='all')
    args = parser.parse_args()

    # Load the configuration
    cfg = yaml.safe_load(open(args.config, 'r'))
    crawler_cfg = yaml.safe_load(open('configs/crawler.yaml', 'r'))
    api_key = os.environ.get('API_KEY')

    # Initialization
    if args.department != 'all':
        cfg = {args.department: cfg[args.department]}
    logger = configure_logging(args.department, type='keyword')
    html_finder = HTMLFinder(api_key=api_key, logger=logger, model=crawler_cfg['model'],
                             token_limit_per_minute=crawler_cfg['token_limit_per_minute'])

    for department in cfg.keys():
        try:
            data_dir = cfg[department]['data_dir']
            profile_dir = os.path.join(data_dir, 'profiles')
            faculty_df = pd.read_csv(os.path.join(data_dir, 'faculty_profiles.csv'))
            mentee_df = pd.read_csv(os.path.join(data_dir, 'mentee_profiles.csv'))

            faculty_df = process_profiles(faculty_df, profile_dir, html_finder, department, logger, 'faculty')
            mentee_df = process_profiles(mentee_df, profile_dir, html_finder, department, logger, 'mentee')

            faculty_df.to_csv(os.path.join(data_dir, 'faculty_profiles.csv'), index=False)
            mentee_df.to_csv(os.path.join(data_dir, 'mentee_profiles.csv'), index=False)
        except Exception as e:
            logger.error(f"{e}, {department} might not be collected")
            continue
