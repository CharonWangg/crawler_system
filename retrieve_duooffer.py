import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
import os
from argparse import ArgumentParser
import yaml


def configure_logging():
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'{current_time}_duooffer.log')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def fetch_html_content(url, logger):
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Successfully fetched content from {url}")
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch webpage content from {url}: {e}")
        raise


def find_latest_date(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'id': 'people-table'})

    # Find all date cells in the table
    dates = []
    for row in table.find('tbody').find_all('tr'):
        date_cell = row.find('td')
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            dates.append(date_text)

    if dates:
        latest_date = sorted(dates, reverse=True)[0]
        return latest_date
    else:
        return None

def parse_html(html_content, logger):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'people-table'})
        events = []

        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            event = {
                'Date': cells[0].get_text(strip=True),
                'Name': cells[1].get_text(strip=True),
                'Institution': cells[2].get_text(strip=True),
                'Country': cells[3].get_text(strip=True),
                'Homepage': cells[4].find('a')['href'] if cells[4].find('a') else '',
                'Research_Direction': cells[5].find('div', class_='scrollable-content').get_text(strip=True) if cells[
                    5].find('div', class_='scrollable-content') else '',
                'Source': cells[6].get_text(strip=True),
                'Source_Link': cells[6].find('a')['href'] if cells[6].find('a') else '',
                # 'Invisible_1': cells[7].get_text(strip=True),
                'Continent': cells[8].get_text(strip=True),
                'Field': cells[9].get_text(strip=True)
            }
            events.append(event)

        logger.info("Successfully parsed HTML content")
        return events
    except Exception as e:
        logger.error(f"Failed to parse HTML content: {e}")
        raise


def save_to_csv(data, filename, logger):
    try:
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Data successfully saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save data to {filename}: {e}")
        raise


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/external.yaml')
    args = parser.parse_args()
    logger = configure_logging()
    cfg = yaml.safe_load(open(args.config, 'r'))['duooffer']
    os.makedirs(cfg['data_dir'], exist_ok=True)

    data_dir = cfg['data_dir']
    if 'latest_date' not in cfg:
        cfg['latest_date'] = ''
    try:
        html_content = fetch_html_content(cfg['base_url'], logger)
        latest_date = find_latest_date(html_content)
        if latest_date == cfg['latest_date']:
            logger.info("No new events found")
            exit()
        cfg['latest_date'] = latest_date
        # Load the entire config file
        full_config = yaml.safe_load(open(args.config, 'r'))
        # Update the duooffer section
        full_config['duooffer'] = cfg
        # Dump the entire updated config back to the file
        yaml.dump(full_config, open(args.config, 'w'))
        events = parse_html(html_content, logger)
        save_to_csv(events, os.path.join(data_dir, 'faculty_profiles.csv'), logger)
    except Exception as e:
        logger.error(f"Script failed: {e}")
