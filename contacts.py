import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

import os
from openai import OpenAI

api_key = "sk-proj-lPvjprJp4QKX73lqPXFST3BlbkFJy6fvhoMHKyqEiM8tGu7E"
# Define your OpenAI API key
client = OpenAI(
    # This is the default and can be omitted
    api_key=api_key,

)


def find_profile_in_html(html_content):
    # Prompt to instruct GPT-4 to extract email from the HTML content
    prompt = (
        f"Extract the faculty profile address, faculty position, department, and domain "
        f"from the following HTML content. Only return the information in the format of a JSON object with keys "
        f"'profile_address', 'position', 'department', and 'domain'. Do not include any other text. "
        f"Here is the HTML content:\n\n{html_content}\n\n"
        f"Return the result as a JSON object:"
    )

    try:
        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4o-mini",
        )

        # Extract the email address from the response
        profile = response.choices[0].message.content
        profile = json.loads(profile)

        return profile
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def find_email_in_html(html_content):
    # Prompt to instruct GPT-4 to extract email from the HTML content
    prompt = (f"Extract the email address from the following HTML content, only return the "
              f"email and do not return other things:\n\n{html_content}")

    try:
        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4o-mini",
        )

        # Extract the email address from the response
        email = response.choices[0].message.content
        return email
    except Exception as e:
        print(f"An error occurred: {e}")
        return None



# Define the base URL
base_url = 'https://jacobsschool.ucsd.edu'

# URL of the main faculty profiles page
url = f'{base_url}/faculty/profiles'

# Send a GET request to the website
response = requests.get(url)
response.raise_for_status()  # Check for request errors

# Parse the HTML content
soup = BeautifulSoup(response.content, 'html.parser')

# Define lists to store the extracted data
names = []
titles = []
departments = []
positions = []
emails = []

# Find all the faculty profile entries
faculty_entries = soup.find_all('div', class_='col-4 py-2')

for entry in faculty_entries:
    # Hard-coded extract the link to the individual profile
    link_element = entry.find('span', class_='font-weight-bold').find('a')
    href = link_element['href']

    profile_url = f'{base_url}{href}'

    # Extract the name
    name = link_element.get_text(strip=True)

    # Extract the department and position
    title_element = entry.find('div', class_='faculty_list_associations').get_text(strip=True)

    # Send a GET request to the individual profile page
    profile_response = requests.get(profile_url)
    profile_response.raise_for_status()

    # Parse the individual profile page
    profile_soup = BeautifulSoup(profile_response.content, 'html.parser')

    # Extract the email using LLM
    try:
        email = find_email_in_html(str(profile_soup))
    except Exception as e:
        print(f"Failed to extract email for {name}: {e}")
        email = 'N/A'

    # Append data to the lists
    names.append(name)
    titles.append(title_element)
    emails.append(email)

    print(f"Name: {name}, Title: {title_element}, Email: {email}")

# Create a DataFrame from the extracted data
df = pd.DataFrame({
    'Name': names,
    'Title': titles,
    'Email': emails
})

# Save the DataFrame to a CSV file
df.to_csv(f'{data_dir}/faculty_profiles.csv', index=False)

print(f'Data has been saved to {data_dir}/faculty_profiles.csv')
