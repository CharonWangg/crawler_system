import requests
from bs4 import BeautifulSoup
import json
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

"sk-proj-lPvjprJp4QKX73lqPXFST3BlbkFJy6fvhoMHKyqEiM8tGu7E"

class HTMLFinder:
    model_limit = {
        "gpt-4o-mini": 60000,
        "gpt-3.5-turbo": 200000
    }
    def __init__(self, api_key, model="gpt-4o-mini", token_limit_per_minute=None):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key
        )
        self.model = model
        if token_limit_per_minute is None:
            self.token_limit_per_minute = self.model_limit[model]
        else:
            self.token_limit_per_minute = token_limit_per_minute
        self.sleep_time = 60

    def ask_llm(self, prompt):
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
            )

            return response.choices[0].message.content
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def chunk_html(self, html_content):
        html_str = str(html_content)
        return [html_str[i:i + self.token_limit_per_minute] for i in range(0, len(html_str), self.token_limit_per_minute)]

    def find_profile_with_bs4(self, html_content):
        # Find all the faculty profile entries
        profiles = html_content.find_all('div', class_='col-4 py-2')

        hrefs = []
        for entry in profiles:
            link_element = entry.find('span', class_='font-weight-bold').find('a')
            href = link_element['href']
            hrefs.append(href)
        return
        return hrefs

    def find_profile_from_faculty_list(self, html_content):
        def retrieve_profile(prompt):
            prompt = open('prompts/find_faculty_profile_link_from_faculty_list.txt', 'r').read()
            prompt = prompt.replace('[html_content]', str(html_content))

            profile = self.ask_llm(prompt).replace('```json\n', '').replace('```', '')
            profile = json.loads(profile)
            return profile

        if len(str(html_content)) > self.token_limit_per_minute:
            html_chunks = self.chunk_html(html_content)
            profiles = []
            for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
                profiles.extend(retrieve_profile(chunk))
                if i != len(html_chunks) - 1:
                    time.sleep(self.sleep_time)  # Sleep to avoid rate limits
        else:
            profiles = retrieve_profile(html_content)

        return profiles

    def find_faculty_info_in_html(self, html_content):
        # Prompt to instruct GPT-4 to extract email from the HTML content
        prompt = open('prompts/find_faculty_info_from_html.txt', 'r').read()
        info = self.ask_llm(prompt.replace('[html_content]', str(html_content))).replace('```json\n', '').replace('```', '')
        info = json.loads(info)
        return info