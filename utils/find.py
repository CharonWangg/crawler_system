import json
import re
from bs4 import BeautifulSoup
from tqdm import tqdm

import os
from openai import OpenAI


class HTMLFinder:
    model_context_limit = {
        # 1:4 token/char ratio, use 1/4 of 128000 to have a large number of generated tokens
        "gpt-4o-mini": 128000,
        "gpt-3.5-turbo": 40000
    }
    model_token_limit = {
        "gpt-4o-mini": 2000000,
        "gpt-3.5-turbo": 2000000
    }
    def __init__(self, api_key, logger, model="gpt-4o-mini", token_limit_per_minute=None):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key
        )
        self.model = model
        self.context_length_limit = self.model_context_limit[model]
        if token_limit_per_minute is None:
            self.token_limit_per_minute = self.model_token_limit[model]
        else:
            self.token_limit_per_minute = token_limit_per_minute
        self.sleep_time = 60
        self.logger = logger

    def chunk_text(self, text, max_length):
        return [text[i:i + max_length] for i in range(0, len(text), max_length)]

    def chunk_html(self, html_content):
        html_str = str(html_content)
        return [html_str[i:i + self.token_limit_per_minute] for i in range(0, len(html_str), self.token_limit_per_minute)]

    def ask_llm(self, prompt, html, substitute=True):
        if html is not None and len(html) > self.context_length_limit:
            html_chunks = self.chunk_text(html, self.context_length_limit)
            prev_response = "" if substitute else []
            if substitute:
                # for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
                for i, chunk in enumerate(html_chunks):
                # for long text chunks, update the result with the previous response
                    if i == 0:
                        content = prompt.replace('[html_content]', chunk)
                    else:
                        content = (f"This is the {i} chunk of a long text, previous response is {prev_response}, "
                                   f"if you don't find better information for a specific content, use the "
                                   f"information that content from the previous response.\n") + prompt.replace('[html_content]', chunk)
                    response = self.client.chat.completions.create(
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": open('prompts/system_prompt.txt', 'r').read()},
                            {"role": "user", "content": content}
                        ],
                        model=self.model,
                    )
                    prev_response = json.loads(response.choices[0].message.content)["result"]
                response = prev_response
            else:
                # for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
                for i, chunk in enumerate(html_chunks):
                    # for long text chunks, append the new response to the previous response
                    content = prompt.replace('[html_content]', chunk)
                    response = self.client.chat.completions.create(
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": open('prompts/system_prompt.txt', 'r').read()},
                            {"role": "user", "content": content}
                        ],
                        model=self.model,
                    )
                    prev_response.extend(json.loads(response.choices[0].message.content)["result"])
                response = prev_response
            return response
        elif html is not None and len(html) < self.context_length_limit:
            prompt = prompt.replace('[html_content]', html)
            response = self.client.chat.completions.create(
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": open('prompts/system_prompt.txt', 'r').read()},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
            )
            return json.loads(response.choices[0].message.content)["result"]
        else:
            # currently don't have cases that only need prompt
            raise ValueError("html content is required")

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

    def find_profile_from_faculty_list(self, html_content, profile_base_url):
        def retrieve_profile(prompt):
            prompt = open('prompts/find_faculty_profile_link_from_faculty_list.txt', 'r').read()
            prompt = prompt.replace('[profile_base_url]', profile_base_url)
            profile = self.ask_llm(prompt, str(html_content), substitute=False)
            return profile

        profiles = retrieve_profile(html_content)

        # if len(str(html_content)) > self.token_limit_per_minute:
        #     html_chunks = self.chunk_html(html_content)
        #     profiles = []
        #     for i, chunk in enumerate(tqdm(html_chunks, desc="Processing chunks")):
        #     # for i, chunk in enumerate(html_chunks):
        #         profiles.extend(retrieve_profile(chunk))
        #         # uncomment when rate_limit_exceeded
        #         # if i != len(html_chunks) - 1:
        #         #     time.sleep(self.sleep_time)  # Sleep to avoid rate limits
        # else:
        #     profiles = retrieve_profile(html_content)

        return profiles

    def find_faculty_info_in_html(self, html_content, previous_info=""):
        # Prompt to instruct GPT-4 to extract email from the HTML content
        prompt = open('prompts/find_faculty_info_from_html.txt', 'r').read()
        prompt = prompt.replace('[previous_info]', str(previous_info))
        info = self.ask_llm(prompt, str(html_content))
        return info

    def find_mentee_info_in_html(self, html_content, previous_info=""):
        # Prompt to instruct GPT-4 to extract email from the HTML content
        prompt = open('prompts/find_mentee_info_from_html.txt', 'r').read()
        prompt = prompt.replace('[previous_info]', str(previous_info))
        info = self.ask_llm(prompt, str(html_content))
        return info

    def find_relevant_links_in_google_html(self, html_content, query, previous_info=""):
        prompt = open('prompts/google_search.txt', 'r').read()
        prompt = prompt.replace('[query]', str(query))
        prompt = prompt.replace('[previous_info]', str(previous_info))
        info = self.ask_llm(prompt, str(html_content))
        self.logger.info(f"Relevant links found in google: {info}")

        return info

    def find_relevant_links_in_lab_html(self, html_content, previous_info=""):
        prompt = open('prompts/lab_page_search.txt', 'r').read()
        prompt = prompt.replace('[previous_info]', str(previous_info))
        info = self.ask_llm(prompt, str(html_content))
        self.logger.info(f"Relevant links found in lab website: {info}")
        return info

    def find_relevant_content_from_google(self, web_browser, query, previous_info=""):
        search_html = BeautifulSoup(web_browser.google_search(query), 'html.parser')
        google_links = self.find_relevant_links_in_google_html(search_html, query, previous_info)
        if google_links:
            personal_soup = web_browser.multi_request(list(google_links.values()))
            # only use the text part to exact content
            personal_soup = "\n".join(
                ['='*10 + f'\nThis {name} website link: {link}\n' + str(soup) for (name, link), soup in zip(google_links.items(), personal_soup)])
            return personal_soup
        return ""

    def find_relevant_content_from_lab(self, web_browser, lab_pages, previous_info=""):
        lab_section_links = self.find_relevant_links_in_lab_html(lab_pages, previous_info)
        if lab_section_links:
            lab_soup = web_browser.multi_request(list(lab_section_links.values()))
            lab_pages = lab_pages + "\n" + "\n".join([str(soup) for soup in lab_soup])
        return lab_pages

    def find_keywords_in_html(self, html_content, previous_info=""):
        prompt = open('prompts/find_research_keywords_in_html.txt', 'r').read()
        prompt = prompt.replace('[previous_info]', str(previous_info))
        info = self.ask_llm(prompt, str(html_content))
        self.logger.info(f"Representative keywords for {previous_info['name']} found in lab website: {info}")
        return info

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