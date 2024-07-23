# OrinNet-Crawler-Utils Documentation

## Overview
OrinNet-Crawler-Utils is a sophisticated Python library designed for scraping and processing faculty profiles from academic websites. It aims to automate the collection of comprehensive information about faculty members, including their academic positions, departments, research interests, and contact details. This utility is invaluable for academic research, networking, and data analysis purposes.

## Key Components

### `browse.WebBrowser`
Handles automated web browsing tasks using Selenium, providing methods for page navigation, content scrolling, and dynamic content loading.

### `find.HTMLFinder`
Employs BeautifulSoup to parse HTML content and extract required information based on customizable selectors. It's designed to adapt to different webpage structures by using the LLMs.

### `fetch_profile`
The core function orchestrating the scraping process. It retrieves faculty profiles from both official (website embedded in the school official website) and personal web pages (lab/personal website retrieved with google), extracts the necessary information, and compiles it into a structured format.

### `Data Management`
Raw scraped personal and official information are stored in the `data/<university>/<school>/profiles/<name>`. Structured data (JSON, CSV) are stored in the `data/<university>/<school>` directory.

## Installation

1. Install the python libraries:
   ```
   pip install -r requirements.txt
   ```
   
2. Install the Chrome WebDriver:
    ```
    # For Mac
    brew install chromedriver
    ```

## Usage

1. Fetch faculty profiles from a department website:
   ```
   python retrieve_faculty.py --department jacob --num_processes 1
   ```
   
2. Fetch faculty-corresponding mentees (graduate students and postdoc) from a department website:
   ```
   python retrieve_mentee.py --department jacob --num_processes 1
   ```
   
3. Fetch top N (50) research keywords from the local stored official and personal profiles for a specific researcher:
   ```
   python retrieve_keyword.py --department hdsi
   ```