import requests
from bs4 import BeautifulSoup
import json
import re
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
    model_context_limit = {
        "gpt-4o-mini": 16000,
        "gpt-3.5-turbo": 40000
    }
    model_token_limit = {
        "gpt-4o-mini": 60000,
        "gpt-3.5-turbo": 200000
    }
    def __init__(self, api_key, model="gpt-4o-mini", token_limit_per_minute=None):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key
        )
        self.model = model
        self.context_length_limit = 240000
        if token_limit_per_minute is None:
            self.token_limit_per_minute = self.model_limit[model]
        else:
            self.token_limit_per_minute = token_limit_per_minute
        self.sleep_time = 60

    def chunk_text(self, text, max_length):
        return [text[i:i + max_length] for i in range(0, len(text), max_length)]

    def chunk_html(self, html_content):
        html_str = str(html_content)
        return [html_str[i:i + self.token_limit_per_minute] for i in range(0, len(html_str), self.token_limit_per_minute)]

    def ask_llm(self, prompt, html=None):
        try:
            if html is not None and len(html) > self.context_length_limit:
                html_chunks = self.chunk_text(html, self.context_length_limit)
                prev_response = ""
                for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
                    response = self.client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": open('prompts/system_prompt.txt', 'r').read()},
                            {"role": "user", "content": f"This is the {i} chunk of a long text, previous response is {prev_response},"
                                                        f"if you don't find better answer for a specific content, use the "
                                                        f"answer of that content from the previous response.\n"
                                                        + prompt.replace('[html_content]', chunk)}
                        ],
                        model=self.model,
                    )
                    prev_response = json.loads(response.choices[0].message.content.replace('```json\n', '').replace('```', ''))
            else:
                if html is not None:
                    prompt = prompt.replace('[html_content]', html)
                response = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": open('prompts/system_prompt.txt', 'r').read()},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.model,
                )
            return response.choices[0].message.content.replace('```json\n', '').replace('```', '')
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    # def find_profile_with_bs4(self, html_content):
    #     # Find all the faculty profile entries
    #     profiles = html_content.find_all('div', class_='col-4 py-2')
    #
    #     hrefs = []
    #     for entry in profiles:
    #         link_element = entry.find('span', class_='font-weight-bold').find('a')
    #         href = link_element['href']
    #         hrefs.append(href)
    #     return
    #     return hrefs

    def find_profile_from_faculty_list(self, html_content):
        def retrieve_profile(prompt):
            prompt = open('prompts/find_faculty_profile_link_from_faculty_list.txt', 'r').read()

            profile = self.ask_llm(prompt, str(html_content))
            profile = json.loads(profile)
            return profile

        if len(str(html_content)) > self.token_limit_per_minute:
            html_chunks = self.chunk_html(html_content)
            profiles = []
            for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
                profiles.extend(retrieve_profile(chunk))
                # uncomment when rate_limit_exceeded
                # if i != len(html_chunks) - 1:
                #     time.sleep(self.sleep_time)  # Sleep to avoid rate limits
        else:
            profiles = retrieve_profile(html_content)

        return profiles

    def find_faculty_info_in_html(self, html_content, extra_prompt=""):
        # Prompt to instruct GPT-4 to extract email from the HTML content
        prompt = open('prompts/find_faculty_info_from_html.txt', 'r').read()
        prompt += extra_prompt
        info = self.ask_llm(prompt, str(html_content))
        info = json.loads(info)
        return info

    def find_relevant_links_in_google_html(self, html_content, query):
        prompt = open('prompts/google_search.txt', 'r').read()
        prompt = prompt.replace('[query]', str(query))
        info = self.ask_llm(prompt, str(html_content))
        info = json.loads(info)
        return info

    def find_relevant_links_in_lab_html(self, html_content):
        prompt = open('prompts/lab_page_search.txt', 'r').read()
        info = self.ask_llm(prompt, str(html_content))
        info = json.loads(info)
        return info

    def find_relevant_content_from_google(self, web_browser, query):
        search_html = BeautifulSoup(web_browser.google_search(query).content, 'html.parser')
        google_links = self.find_relevant_links_in_google_html(search_html, query)
        if google_links:
            personal_soup = web_browser.multi_request(list(google_links.values()))
            personal_soup = [BeautifulSoup(response.content, 'html.parser') for response in personal_soup]
            personal_soup = "\n".join(
                [f'This website link: {link}\n' + str(soup) for link, soup in zip(google_links, personal_soup)])
        return personal_soup

    def find_relevant_content_from_lab(self, web_browser, lab_pages):
        lab_section_links = self.find_relevant_links_in_lab_html(lab_pages)
        if lab_section_links:
            lab_soup = web_browser.multi_request(list(lab_section_links.values()))
            lab_soup = [BeautifulSoup(response.content, 'html.parser') for response in lab_soup]
            lab_pages = lab_pages + "\n" + "\n".join([str(soup) for soup in lab_soup])
        return lab_pages

    def minify_html(self, html):
        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Remove unnecessary whitespace
        html = re.sub(r'>\s+<', '><', html)
        html = re.sub(r'\s+', ' ', html)

        # Parse the HTML using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Simplify attribute names (example of shortening class names)
        class_map = {}
        class_counter = 1

        for tag in soup.find_all(True):
            if tag.has_attr('class'):
                new_classes = []
                for cls in tag['class']:
                    if cls not in class_map:
                        short_name = 'c{}'.format(class_counter)
                        class_map[cls] = short_name
                        class_counter += 1
                    new_classes.append(class_map[cls])
                tag['class'] = new_classes

        # Remove redundant attributes
        for tag in soup.find_all(True):
            if tag.name == 'script' and tag.get('type') == 'text/javascript':
                del tag['type']
            if tag.name == 'link' and tag.get('type') == 'text/css':
                del tag['type']

        # Combine inline styles (example for demonstration purposes)
        style_map = {}
        style_counter = 1

        for tag in soup.find_all(True):
            if tag.has_attr('style'):
                style = tag['style']
                if style not in style_map:
                    short_name = 's{}'.format(style_counter)
                    style_map[style] = short_name
                    style_counter += 1
                tag['class'] = tag.get('class', []) + [style_map[style]]
                del tag['style']

        # Convert the modified soup object back to a string
        minified_html = str(soup)

        # Further remove any extra whitespace created during parsing
        minified_html = re.sub(r'\s+', ' ', minified_html).strip()

        return minified_html