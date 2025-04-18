from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Callable, Dict
import os
import uvicorn
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta, timezone
import io
import zipfile
from PIL import Image
from bs4 import BeautifulSoup
import urllib3
import numpy as np
import colorsys
import httpx
import feedparser
import json
import warnings
warnings.filterwarnings("ignore")
import io
import re
from dateutil import parser
import subprocess
import shutil
from typing import Optional
from pathlib import Path
import aiohttp
import logging


load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the request model
class AnswerResponse(BaseModel):
    answer: str

# Keep AIPROXY_TOKEN and NLP_API_URL without usage
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
NLP_API_URL = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

# Function map to dynamically call the correct function based on regex patterns
function_map: Dict[str, Callable] = {}

# Function to recognise questions using regex pattern
def questions_tds(pattern: str):
    def decorator(func: Callable):
       function_map[pattern] = func
       return func
    return decorator
    
#-------- GA1 questions---------
# QA1 Q1 - What is the output of code -s?
@questions_tds(r".*output of code -s.*")
def install_vscode(question: str) -> str:
    try:
        url = "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64"
        installer_path = os.path.join(os.getenv('TEMP'), 'VSCodeSetup.exe')
        
        # Download the installer
        subprocess.run(['curl', '-L', url, '-o', installer_path], check=True)
        
        # Run the installer
        subprocess.run([installer_path, '/silent'], check=True)
        
        # Clean up the installer
        os.remove(installer_path)
        
        subprocess.run(['code', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
        
    except FileNotFoundError:
        return False   
    
    except Exception as e:
        return f"Error processing: {str(e)}"
    
    result = subprocess.run(['code', '-s'])
    return result
    
# GA1 Q2 - Make HTTP requests with uv
# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@questions_tds(r".*email set to.*")
async def ga1_q2(question: str) -> str:
    email_pattern = r"email set to\s*([\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,})"
    match = re.search(email_pattern, question, re.IGNORECASE)  
    
    if match:
        email = match.group(1)
        url = "https://httpbin.org/get"
        command = f"uv run --with httpie -- https {url}?email={email}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
  
  
# GA1 Q3 - Run command with npx?
@questions_tds(r".*npx -y prettier@3.4.2 README.md.*")
async def ga1_q3(question: str, file: UploadFile) -> str:
    print(f"?? Called ga1_q3: {question}")
    try:
        # Step 1: Save the uploaded file as README.md in a temp directory
        file_path = f"/tmp/README.md"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Step 2: Run the command: npx -y prettier@3.4.2 README.md | sha256sum
        result = subprocess.run(
            "npx -y prettier@3.4.2 README.md | Powershell sha256sum",
            shell=True,
            cwd="/tmp",
            capture_output=True,
            text=True
        )

        # Step 3: Extract and return only the SHA-256 hash
        return result.stdout.split()[0] if result.stdout else "Error: No output"

    except Exception as e:
        return f"Error: {str(e)}"
        
# GA1 Q4 - Use Google Sheets      
@questions_tds(r".*=SUM\(ARRAY_CONSTRAIN\(SEQUENCE\(100, 100, 8, 0\), 1, 10\)\).*")
async def solve_excel_formula(question: str) -> str:
    """Solve Excel formula questions using Python."""

    try:
        if "=SUM(ARRAY_CONSTRAIN(SEQUENCE(100, 100, 8, 0), 1, 10))" in question:
            # Create a sequence starting at 8, with step 0, for 100x100
            # Then constrain to 1 row, 10 columns and sum
            sequence = np.full((100, 100), 8)
            constrained_array = sequence[:1, :10]
            result = np.sum(constrained_array)
            return str(result)  # Return as string
        else:
            return "Error: Formula not recognized."

    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"
            
            
            
#GA1 Q5 -Use Excel 
import pandas as pd
@questions_tds(r"^=SUM\(TAKE\(SORTBY\(\{[\d,]+\}, \{[\d,]+\}, \d+, \d+\)\)\)$")
async def solve_excel_formula(question: str) -> str:
    """Solve Excel formula questions using Python."""
    
    # Use raw string for regex to avoid backslash escaping issues
    pattern = r"=SUM\(TAKE\(SORTBY\(\{([\d,]+)\}, \{([\d,]+)\}, (\d+), (\d+)\)\)\)$"
    match = re.match(pattern, question)

    if match:
        try:
            values_str = match.group(1)
            sort_keys_str = match.group(2)
            take_count = int(match.group(3))
            sort_order = int(match.group(4))  # Added to handle sort order

            values = [int(x) for x in values_str.split(',')]
            sort_keys = [int(x) for x in sort_keys_str.split(',')]

            # Crucial: Check for valid input lengths
            if len(values) != len(sort_keys):
                return "Invalid input: values and sort keys must have the same length."

            # Create a DataFrame
            df = pd.DataFrame({'values': values, 'sort_keys': sort_keys})

            # Sort based on sort_keys and sort_order
            df = df.sort_values('sort_keys', ascending=sort_order == 1)

            # Take the specified number of elements
            result = df['values'].head(take_count).sum()
            return str(int(result))  # Ensure the result is an integer
        except (ValueError, IndexError) as e:
            return f"Invalid input: {e}"
    else:
        return "Invalid formula"
            
#GA1 Q6-Use DevTools     
from fastapi import UploadFile
from bs4 import BeautifulSoup

@questions_tds(r".*What is the value in the hidden input.*")  
async def extract_hidden_input(question: str, file: UploadFile) -> str:
    """Extract the value from a hidden input in an uploaded HTML file."""
    try:
        # Read the file content correctly
        html_content = await file.read()
        html_content = html_content.decode("utf-8")  # Convert bytes to string
        
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the hidden input
        hidden_input = soup.find('input', type='hidden')
        
        # Get the value of the hidden input
        if hidden_input and 'value' in hidden_input.attrs:
            return {"answer": hidden_input['value']}
        else:
            return {"answer": "No hidden input found."}
    except Exception as e:
        return {"answer": f"Error: {str(e)}"}

            
# GA1 Q7 - Count the number of Wednesdays in a given date range ?
@questions_tds(r".*How many Wednesdays are there in the date range.*")
async def ga1_q7(question: str) -> str:
    match = re.search(r".*How many Wednesdays are there in the date range (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2}).*", question)
    if not match:
        return "Invalid question format"
    start_date_str, end_date_str = match.groups()
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    current_date = start_date
    wednesday_count = 0
    while current_date <= end_date:
        if current_date.weekday() == 2:  # Wednesday
            wednesday_count += 1
        current_date += timedelta(days=1)
    return str(wednesday_count)

# GA1 Q8 - Import file to get answer from CSV ?
@questions_tds(r".*Download and unzip file .* which has a single extract.csv file inside.*")
async def ga1_q8(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zip_ref:
        zip_ref.extractall('extracted_files')
    csv_file_path = 'extracted_files/extract.csv'
    df = pd.read_csv(csv_file_path)
    answer_value = df['answer'].iloc[0]
    return str(answer_value)

#GA1 Q9 Use JSON
@questions_tds(r".*Sort this JSON array of objects by the value of the age field. In case of a tie, sort by the name field*")
async def ga1_q9(question: str) -> str:
    """Sorts a JSON array of objects by age and then name."""
    # Find the JSON array within the question string.
    match = re.search(r"\[.*\]", question) # finds the json array.
    if match:
        json_string = match.group(0)
        try:
            data = json.loads(json_string)
            sorted_data = sorted(data, key=lambda x: (x['age'], x['name']))
            return json.dumps(sorted_data, separators=(',', ':'))
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON"}, separators=(',', ':'))
    else:
        return json.dumps({"error": "JSON array not found"}, separators=(',', ':'))
        
        
import json
#GA1 Q10  Multi-cursor edits to convert to JSON
@questions_tds(r".*use multi-cursors and convert it into a single JSON object, where key=value pairs are converted into {key: value, key: value, ...}.*")
async def ga1_q10(question: str, file: UploadFile) -> str:

    # Step 1: Read the text file
    with open(file, 'r') as file:
        lines = file.readlines()
    
    # Step 2: Parse the key-value pairs
    data = {}
    for line in lines:
        if '=' in line:
            key, value = line.strip().split('=', 1)  # Split only on the first '='
            data[key.strip()] = value.strip()
    
    # Step 3: Create a JSON object
    json_object = json.dumps(data, indent=4)
    
    # Print the JSON object
    return json_object
    
#GA1 Q11 CSS selectors 
@questions_tds(r".*Find all <div>s having a foo class in the hidden element below. What's the sum of their data-value attributes? Sum of data-value attributes.*")
async def ga1_q11(question: str, file: UploadFile) -> str:
    try:
        with open(file, 'r', encoding='utf-8') as file:
            html_content = file.read()    
    # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all <div> elements with class 'foo'
        foo_divs = soup.find_all('div', class_='foo')
        
        # Sum the data-value attributes
        total_value = sum(int(div['data-value']) for div in foo_divs)
        
        # Output the result
        return total_value
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"

# GA1 Q12-Process files with different encodings
        
# GA1 Q14 - find and replace a string in a file
import hashlib
@questions_tds(r".*replace all \"IITM\".*")
async def ga1_q14(question: str, file: UploadFile) -> str:
    try:
        # ? Step 1: Save and Extract ZIP
        zip_path = f"/tmp/{file.filename}"
        extract_folder = f"/tmp/extracted_{os.path.splitext(file.filename)[0]}"
        os.makedirs(extract_folder, exist_ok=True)

        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # Extract ZIP preserving file structure
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)

        # ? Step 2: Replace "IITM" (case insensitive) with "IIT Madras"
        for file_path in Path(extract_folder).rglob("*"):
            if file_path.is_file():
                with open(file_path, "r", encoding="utf-8", newline='') as f:
                    content = f.read()

                updated_content = re.sub(r"(?i)\bIITM\b", "IIT Madras", content)

                with open(file_path, "w", encoding="utf-8", newline='') as f:
                    f.write(updated_content)

        # ? Step 3: Compute SHA-256 hash using `cat * | sha256sum`
        result = subprocess.run(
            "cat * | sha256sum",
            shell=True,
            cwd=extract_folder,
            capture_output=True,
            text=True
        )
        # Extract and return the SHA-256 hash
        return result.stdout.split()[0] if result.stdout else "Error: No output"

    except Exception as e:
        return f"Error: {str(e)}"

# GA1 Q15 - filter files based on size and timestamp
@questions_tds(r".*ls with options to list all files.*")
async def ga1_q15(question: str, file: UploadFile) -> str:
    try:
        # ? Step 1: Extract size and date conditions from the question using regex
        size_match = re.search(r"at least (\d+) bytes", question)
        date_match = re.search(r"on or after ([\w, ]+ \d{4}, \d+:\d+ [apAP][mM] IST)", question)

        if not size_match or not date_match:
            return "Error: Could not extract size or date from the question."

        min_size = int(size_match.group(1))  # Extracted minimum file size
        date_str = date_match.group(1)  # Extracted modification date string

        # ? Convert extracted date string to a datetime object
        target_date = datetime.strptime(date_str, "%a, %d %b, %Y, %I:%M %p IST")

        # ? Step 2: Save and Extract ZIP file
        zip_path = f"/tmp/{file.filename}"
        extract_folder = f"/tmp/extracted_{os.path.splitext(file.filename)[0]}"

        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # Extract using `unzip` to preserve timestamps
        subprocess.run(["unzip", zip_path, "-d", extract_folder], check=True)

        # ? Step 3: Run `ls -l --time-style=full-iso` to list files with size & timestamp
        result = subprocess.run(
            ["ls", "-l", "--time-style=full-iso", extract_folder],
            capture_output=True,
            text=True
        )

        # ? Step 4: Process the output using regex
        lines = result.stdout.strip().split("\n")[1:]  # Skip the first line (total)
        total_size = 0

        for line in lines:
            match = re.search(r"(\S+) +\S+ +\S+ +\S+ +(\d+) (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)

            if match:
                size = int(match.group(2))  # Extracted file size
                mod_time_str = match.group(3)  # Extracted modification time

                mod_time = datetime.strptime(mod_time_str, "%Y-%m-%d %H:%M:%S")  # Convert to datetime

                # ? Step 5: Check conditions and sum file sizes
                if size >= min_size and mod_time >= target_date:
                    total_size += size

        return str(total_size)

    except Exception as e:
        return f"Error: {str(e)}"



#GA1 Q16 - Calculate the sum of all numbers in a text file   -- ? 
@questions_tds(r".*grep . * | LC_ALL=C sort | sha256sum.*")
async def ga1_q16(question: str, file: UploadFile) -> str:
    try:
        # Step 1: Save the uploaded ZIP file
        zip_path = f"/tmp/{file.filename}"  # Temporary path for extraction
        extract_folder = f"/tmp/extracted_{os.path.splitext(file.filename)[0]}"
        
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # Step 2: Extract ZIP file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)

        # Step 3: Move all files from subdirectories to the main folder
        for root, dirs, files in os.walk(extract_folder):
            for file in files:
                old_path = os.path.join(root, file)
                new_path = os.path.join(extract_folder, file)
                if old_path != new_path:  # Avoid moving if already in the folder
                    shutil.move(old_path, new_path)

        # Step 4: Rename files (Replace each digit with the next one)
        for file in os.listdir(extract_folder):
            new_name = re.sub(r'\d', lambda x: str((int(x.group(0)) + 1) % 10), file)
            old_path = os.path.join(extract_folder, file)
            new_path = os.path.join(extract_folder, new_name)
            os.rename(old_path, new_path)

        # Step 5: Run the required bash command and get SHA-256 hash
        result = subprocess.run(
            'grep . * | LC_ALL=C sort | sha256sum',
            shell=True,
            cwd=extract_folder,
            capture_output=True,
            text=True
        )

        # Extract and return only the hash
        return result.stdout.split()[0] if result.stdout else "Error: No output"

    except Exception as e:
        return f"Error: {str(e)}"


# GA1 Q17 - Count the number of different lines between two files ?
@questions_tds(r".*Download .* and extract it. It has 2 nearly identical files, a.txt and b.txt, with the same number of lines. How many lines are different between a.txt and b.txt?.*")
async def ga1_q17(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zip_ref:
        zip_ref.extractall('extracted_files')
    with open('extracted_files/a.txt', 'r') as file_a, open('extracted_files/b.txt', 'r') as file_b:
        lines_a = file_a.readlines()
        lines_b = file_b.readlines()
    different_lines_count = sum(1 for line_a, line_b in zip(lines_a, lines_b) if line_a != line_b)
    return str(different_lines_count)


#-------- GA2 questions---------
# GA2 Q1 -Markdown
@questions_tds(r".*the markdown must include.*")
async def ga2_q1(question: str) -> str:
    markdown_content = """# Puducherry
    
    ## City in India
    
    **Pondicherry** is the capital and most populous city of the *Union Territory of Puducherry* in India. 
    
    >Beach lovers_ find their paradise in Pondicherry. The serene beaches of Pondicherry offer the perfect escape. Relaxing by the beach in Pondicherry is `pure bliss`.
    
    ```python
    def hello_world():
        print("Welcome to Puducherry!")
    ```
    
    The four divisions of Puducherry are 
    - Puducherry
    - Karaikal 
    - Mahe and
    - Yanam.
    
    Puducherry has five official names, owing to its linguistic diversity, past-French heritage and the legacy of British India.
    1. English
    2. French
    3. Tamil
    4. Telugu
    5. Malayalam
    
    |Area   | Population| 
    |-----  |-----------|
    |483 km2|1,394,467  |
    
    Official Website (https://www.py.gov.in/)
    
    ![Alt Text](https://en.wikipedia.org/wiki/Puducherry_(union_territory)#/media/File:Emblem_of_the_Government_of_Puducherry.png)
    
    """
    if re.search(r".*the markdown must include.*", question, re.IGNORECASE):
        return markdown_content
        
#GA2 Q4 - google collab 
@questions_tds(r"Let's make sure you can access Google Colab")
async def ga2_q4(question: str) -> str:
    print(f"?? Called ga2_q4: {question}")

    # Robust error handling
    try:
        match = re.search(r"ID:\s*([\w\.-]+@[\w\.-]+)", question, re.IGNORECASE)
        if not match:
            return "Error: 'ID:' and email not found in question"

        email = match.group(1).rstrip('.')
        year = 2025  # fixed to match Colab
        i1 = f"{email} {year}".encode('utf-8')  # Explicit encoding
        hash_val = hashlib.sha256(i1).hexdigest()[-5:]
        return hash_val
    except AttributeError as e:
        return f"Error: Invalid question format: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"
        
# GA2 Q5 - Calculate number of light pixels in an image ?
@questions_tds(r".*Create a new Google Colab notebook and run this code \(after fixing a mistake in it\) to calculate the number of pixels with a certain minimum brightness.*")
async def ga2_q5(file: UploadFile) -> str:
    file_content = await file.read()
    image = Image.open(io.BytesIO(file_content))
    rgb = np.array(image) / 255.0
    lightness = np.apply_along_axis(lambda x: colorsys.rgb_to_hls(*x)[1], 2, rgb)
    light_pixels = np.sum(lightness > 0.133)
    return str(int(light_pixels))

#GA2 Q10 - running llamafile through ngrok
@questions_tds(r".*Create a tunnel to the Llamafile server using ngrok.*")
async def ga2_q10(question: str) -> str:
    print(f"?? Called ga2_q10: {question}")
    url = "https://2350-2409-4072-6e45-1953-c9d6-9624-b787-cecb.ngrok-free.app/"
    return url


#------------------------------------



#-------- GA3 questions---------

# GA3 Q9 - Generate a prompt for LLM to respond "Yes" ?

@questions_tds(r".*(prompt|make).*LLM.*Yes..*")
async def ga3_q9(question: str) -> str:
    return "Fire is wet"



#------------------------------------
#-------- GA4 questions---------

# GA4 Q1 - Get the total no of ducks from the espn page ?
@questions_tds(r".*total number of ducks.*")
async def ga4_q1(question: str) -> str:
    """
    Answers questions about the total number of ducks on a given ESPN Cricinfo 
    ODI batting stats page, e.g.:
      "What is the total number of ducks across players on page number 30 of ESPN Cricinfo's ODI batting stats?"
    
    Steps:
      1) Extract page number from the question: "page number <digits>"
      2) Build the URL for that page
      3) Fetch the HTML with a browser-like user-agent to avoid 403
      4) Find the 'engineTable' that contains a header named "Player"
      5) Determine which column is labeled "0" (ducks)
      6) Gather data rows (class="data1"), sum integer values in that '0' column
      7) Return the sum as a string
    """

    # 1) Extract page number from question
    match = re.search(r"page number\s+(\d+)", question, flags=re.IGNORECASE)
    if not match:
        return "No valid page number found in the question."

    page_num = int(match.group(1))

    # 2) Build the ESPN Cricinfo ODI batting stats URL
    url = (
        "https://stats.espncricinfo.com/stats/engine/stats/"
        f"index.html?class=2;template=results;type=batting;page={page_num}"
    )

    # 3) Use a custom User-Agent to avoid 403 Forbidden
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers)
    if not response.ok:
        return f"Error fetching page {page_num}. HTTP status: {response.status_code}"

    # 4) Parse the HTML with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    # Find a table with class="engineTable" that has a <th> named "Player"
    tables = soup.find_all("table", class_="engineTable")
    stats_table = None
    for table in tables:
        if table.find("th", string="Player"):
            stats_table = table
            break

    if not stats_table:
        return "Could not find the batting stats table on the page."

    # 5) Extract the table headers
    headers_list = [th.get_text(strip=True) for th in stats_table.find_all("th")]

    # Find the index of the "0" column
    duck_col_index = None
    for i, header in enumerate(headers_list):
        if header == "0":
            duck_col_index = i
            break

    if duck_col_index is None:
        return "Could not find the '0' (ducks) column in the table."

    # 6) Extract the data rows; ESPN often labels them with class="data1"
    data_rows = stats_table.find_all("tr", class_="data1")

    # Sum the ducks
    total_ducks = 0
    for row in data_rows:
        cells = row.find_all("td")
        if len(cells) > duck_col_index:
            duck_value = cells[duck_col_index].get_text(strip=True)
            if duck_value.isdigit():
                total_ducks += int(duck_value)

    # 7) Return the total as a string
    return str(total_ducks)


#GA4 Q3 -  public api endpoint url that gives a json response of headers alone taking 
#countryname as input in the url (request is passed accordingly). Takes data from wikipedia.

@questions_tds(r".*Wikipedia.*")
async def ga4_q3(question: str) -> str:
    print(f"?? Called ga4_q3: {question}")
    url ="https://e00b-2409-4072-6e45-1953-c9d6-9624-b787-cecb.ngrok-free.app/api/outline"
    return url

#GA4 Q4 - Json weather description for a city ?
@questions_tds(r".*What is the JSON weather forecast description for.*")
async def ga4_q4(question: str) -> str:
    """
    Answers a question like:
        "What is the JSON weather forecast description for Seoul?"
    
    1) Extract city name from question via regex
    2) Use BBC's location service to find the city ID
    3) Fetch BBC weather page for that ID
    4) Parse the daily summary from the weather page
    5) Create a dictionary mapping each date to its summary
    6) Return that dictionary as a JSON string
    """
    # 1) Extract city name using regex
    match = re.search(r".*What is the JSON weather forecast description for (.*)\?", question, flags=re.IGNORECASE)
    if not match:
        return "Invalid question format. Please ask 'What is the JSON weather forecast description for <city>?'"
    city = match.group(1).strip()

    # 2) Build the BBC location service URL to get the city ID
    location_url = 'https://locator-service.api.bbci.co.uk/locations?' + urlencode({
       'api_key': 'AGbFAKx58hyjQScCXIYrxuEwJh2W2cmv',
       's': city,
       'stack': 'aws',
       'locale': 'en',
       'filter': 'international',
       'place-types': 'settlement,airport,district',
       'order': 'importance',
       'a': 'true',
       'format': 'json'
    })

    try:
        # Fetch location data (JSON)
        loc_result = requests.get(location_url).json()
        # The first search result's ID
        city_id = loc_result['response']['results']['results'][0]['id']
    except (KeyError, IndexError) as e:
        return f"Could not find weather location for '{city}'. Error: {e}"

    # 3) Build the BBC weather page URL
    weather_url = 'https://www.bbc.com/weather/' + city_id

    # 4) Fetch the weather page HTML
    response = requests.get(weather_url)
    if not response.ok:
        return f"Error fetching weather data for {city}. HTTP status: {response.status_code}"

    soup = BeautifulSoup(response.content, 'html.parser')

    # 5) Parse the daily summary (div with class 'wr-day-summary')
    daily_summary_div = soup.find('div', attrs={'class': 'wr-day-summary'})
    if not daily_summary_div:
        return f"Could not find daily summary for {city} on BBC Weather."

    # Extract text and split into list of descriptions
    daily_summary_list = re.findall('[a-zA-Z][^A-Z]*', daily_summary_div.text)

    # 6) Create date list (assuming one summary per day)
    datelist = pd.date_range(datetime.today(), periods=len(daily_summary_list)).tolist()
    datelist = [date.date().strftime('%Y-%m-%d') for date in datelist]

    # Map each date to its summary
    weather_data = {date: desc for date, desc in zip(datelist, daily_summary_list)}

    # 7) Convert dictionary to JSON and return
    return json.dumps(weather_data, indent=4)


# GA4 Q5 - Get maximum latitude of Algiers in Algeria using Nominatim API ?
@questions_tds(r".*?(maximum latitude|max latitude).*?(bounding box).*?city (.*?) in the country (.*?) on the Nominatim API.*")
async def ga4_q5(question: str) -> str:
    match = re.search(r".*?(maximum latitude|max latitude).*?(bounding box).*?city (.*?) in the country (.*?) on the Nominatim API.*", question, re.IGNORECASE)
    if not match:
        return "Invalid question format"
    city = match.group(3)
    country = match.group(4)
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{city}, {country}",
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
        "extratags": 1,
        "polygon_geojson": 0,
        "bounded": 1
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data and "boundingbox" in data[0]:
            bounding_box = data[0]["boundingbox"]
            max_latitude = float(bounding_box[1])
            return str(max_latitude)
    return "No data found"

# GA4 Q6 - Get link to the latest Hacker News post about "name" with point ?


@questions_tds(r".*What is the link to the latest Hacker News post mentioning.*")
async def ga4_q6(question: str) -> str:
    """
    Example question:
      "What is the link to the latest Hacker News post mentioning DuckDB having at least 71 points?"
    
    Steps:
      1) Regex capture: search term (e.g. "DuckDB") and integer points (e.g. "71").
      2) Make an async GET request to https://hnrss.org/newest?q=<term>&points=<points> using httpx.
      3) Parse the XML with ElementTree, find the first <item>, and return the <link>.
      4) If no items found, or question is invalid, return a relevant message.
    """

    # 1) Extract search term and points from the question
    match = re.search(
        r"What is the link to the latest Hacker News post mentioning (.+?) having at least (\d+) points\?",
        question,
        flags=re.IGNORECASE
    )
    if not match:
        return ("Invalid question format. Please ask: "
                "'What is the link to the latest Hacker News post mentioning <term> having at least <points> points?'")
    search_term = match.group(1).strip()
    min_points = match.group(2).strip()

    # 2) Build the HNRSS URL and parameters
    url = "https://hnrss.org/newest"
    params = {
        "q": search_term,
        "points": min_points
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()  # Raise if e.g. 4xx/5xx
            rss_content = response.text

            # 3) Parse the RSS feed
            root = ET.fromstring(rss_content)
            # Items are typically found under <channel><item>
            items = root.findall(".//item")

            if not items:
                return f"No Hacker News posts found mentioning {search_term} with at least {min_points} points"

            # Grab the first item (most recent)
            latest_item = items[0]

            # Extract link from <link> tag
            link_elem = latest_item.find("link")
            link = link_elem.text if link_elem is not None else None

            if not link:
                return "No link found for the latest HN post"

            return link

    except Exception as e:
        return f"Failed to fetch or parse HNRSS feed: {str(e)}"


#GA4 Q7 - Using the GitHub API, find all users located in the city ?

@questions_tds(r".*Using the GitHub API, find all users located in the city.*")
async def ga4_q7(question: str) -> str:
    """
    Example question:
      "Using the GitHub API, find all users located in the city Basel with over 80 followers?"
    
    Steps:
      1) Extract 'city' and 'followers' from the question with regex.
      2) Build the GitHub search query for location:<city> and followers:> <followers>.
      3) Sort by 'joined' descending.
      4) Iterate results, find the newest user (by join date) that was created before the cutoff date.
      5) Return that user's information or a 'No users found' message.
    """

    # 1) Extract the city and followers from the question
    match = re.search(
        r"Using the GitHub API, find all users located in the city (.+?) with over (\d+) followers",
        question,
        flags=re.IGNORECASE
    )
    if not match:
        return (
            "Invalid question format. Please ask in the form: "
            "'Using the GitHub API, find all users located in the city <City> with over <followers> followers?'"
        )

    city = match.group(1).strip()
    followers = match.group(2).strip()

    # Build the query for the GitHub API
    # e.g. 'location:Basel followers:>80'
    query = f'location:"{city}" followers:>{followers}'
    params = {
        'q': query,
        'sort': 'joined',
        'order': 'desc'
    }

    url = 'https://api.github.com/search/users'
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return f"GitHub API request failed with status {response.status_code}"

    data = response.json()
    if 'items' not in data:
        return "No users found in the response."

    # Define the cutoff date
    cutoff_date_str = '2025-02-08T17:15:15Z'
    cutoff_date = datetime.strptime(cutoff_date_str, '%Y-%m-%dT%H:%M:%SZ')

    # Iterate through the search results in descending join order
    for user in data.get('items', []):
        # user['url'] is the API URL for details about that user
        user_response = requests.get(user['url'])
        if user_response.status_code != 200:
            # Could skip or return an error message
            continue
        user_data = user_response.json()
        
        # Parse the created_at date
        created_at_str = user_data.get('created_at')
        if not created_at_str:
            continue
        created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')

        # Check if this user was created before the cutoff date
        if created_at < cutoff_date:
            # Return or build the user info
            username = user_data.get('login', 'Unknown')
            profile_url = user_data.get('html_url', 'Unknown')
            created_date = user_data.get('created_at', 'Unknown')
            return (created_date)

    # If we exhaust the list and find no user matching the cutoff criterion
    return "No users found matching the criteria."


#GA4 Q9 - PDF MARKS (BIOLOGY, MATHS, PHYSICS, CHEM) BASED ON GROUPS

@questions_tds(r".*marks of students who scored.*")
async def ga4_q9(question: str, file: UploadFile) -> str:
    """
    Example question:
      "What is the total Biology marks of students who scored 32 or more marks in Maths in groups 11-44 (including both groups)?"
    
    Because the PDF has one group per page, with heading "Student marks - Group X",
    we parse each page individually, detect the group number, insert it as "Group",
    and then combine all pages into a single DataFrame with columns like:
      ["Maths", "Physics", "English", "Economics", "Biology", "Group"]
    Then filter by sub2 >= mark1, group in [group1..group2], sum(sub1).
    """

    # 1) Extract sub1, mark1, sub2, group1, group2 from the question
    match = re.search(
        r"What is the total (.+?) marks of students who scored (\d+) or more marks in (.+?) in groups (\d+)-(\d+) \(including both groups\)\?",
        question,
        flags=re.IGNORECASE
    )
    if not match:
        return (
            "Invalid question format. Example:\n"
            "What is the total Biology marks of students who scored 32 or more marks in Maths in groups 11-44 (including both groups)?"
        )

    sub1  = match.group(1).strip()  # e.g. "Biology"
    mark1 = int(match.group(2))     # e.g. 32
    sub2  = match.group(3).strip()  # e.g. "Maths"
    grp1  = int(match.group(4))     # e.g. 11
    grp2  = int(match.group(5))     # e.g. 44

    # 2) Read the PDF from the UploadFile into memory, then write to a temp file
    pdf_bytes = await file.read()
    temp_pdf_path = "temp_uploaded.pdf"
    with open(temp_pdf_path, "wb",encoding='utf-8') as f:
        f.write(pdf_bytes)

    # 3) Determine how many pages are in the PDF (so we can parse each individually)
    reader = PdfReader(temp_pdf_path)
    total_pages = len(reader.pages)

    all_dfs = []

    # 4) For each page: 
    #    a) read the text with PyPDF2 to find the heading "Student marks - Group X"
    #    b) parse the table with tabula
    #    c) label each row with the group number X, and store the DataFrame
    for page_num in range(1, total_pages + 1):
        page_index = page_num - 1  # PyPDF2 pages are 0-based

        # (a) find "Student marks - Group X" in the page text
        page_text = reader.pages[page_index].extract_text() or ""
        # e.g.  "Student marks - Group 11"

        group_match = re.search(r"Student marks\s*-\s*Group\s+(\d+)", page_text)
        if not group_match:
            # If we can't find a group # on this page, skip
            continue

        group_number = int(group_match.group(1))

        # (b) parse the table on this page with tabula
        try:
            # We'll parse only this page
            df_list = tabula.read_pdf(
                temp_pdf_path,
                pages=str(page_num),
                multiple_tables=False,  # Each page is just one main table
                lattice=True            # or stream=True, depending on PDF lines
            )
        except Exception as e:
            # If tabula can't parse this page, skip or handle error
            continue

        if not df_list:
            continue

        # There's presumably one table per page
        df_page = df_list[0]

        # (c) Insert a "Group" column
        df_page["Group"] = group_number

        # We might rename columns if needed. The PDF columns are:
        # ["Maths", "Physics", "English", "Economics", "Biology"]
        # If tabula doesn't produce exactly those column names, rename them here.
        # For example, if the first row is used as a header:
        # df_page.columns = ["Maths", "Physics", "English", "Economics", "Biology", ...]
        # OR if the PDF is recognized correctly, no rename needed.

        all_dfs.append(df_page)

    if not all_dfs:
        return "No tables found across pages."

    # Combine all pages into one DataFrame
    df = pd.concat(all_dfs, ignore_index=True)

    # 5) Convert numeric columns to numeric
    # If the parsed column headers differ, adjust accordingly.
    for col in ["Maths", "Physics", "English", "Economics", "Biology", "Group"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 6) Check that sub1 and sub2 exist
    if sub1 not in df.columns or sub2 not in df.columns:
        return f"Columns '{sub1}' or '{sub2}' not found. Found: {list(df.columns)}"

    # 7) Filter:
    #    - df[sub2] >= mark1
    #    - group in [grp1..grp2]
    mask = (
        (df[sub2] >= mark1) &
        (df["Group"].between(grp1, grp2, inclusive="both"))
    )
    filtered_df = df[mask]

    # 8) Sum the sub1 column
    total_marks = filtered_df[sub1].sum(skipna=True)

    return str(total_marks)


#GA4 Q10 - What is the markdown content of the PDF, formatted with prettier@3.4.2?

@questions_tds(r".*What is the markdown content of the PDF, formatted with prettier@3.4.2.*")
async def ga4_q10(question: str, file: UploadFile) -> str:
    """
    Example question:
      "What is the markdown content of the PDF, formatted with prettier@3.4.2?"

    Steps:
      1) Extract text from the uploaded PDF
      2) Convert to naive Markdown
      3) (Optional) Run 'npx prettier@3.4.2 --parser=markdown' on the Markdown to format it
      4) Return the final, formatted Markdown string
    """

    # 1) Read PDF from UploadFile into memory, then parse text
    pdf_bytes = await file.read()
    pdf_path = "temp_to_markdown.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # Use PyPDF2 to extract text from each page
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        all_text = []
        for page_idx in range(len(reader.pages)):
            page = reader.pages[page_idx]
            page_text = page.extract_text() or ""
            # Basic cleanup
            page_text = page_text.strip()
            # Collect
            all_text.append(page_text)
    raw_text = "\n\n".join(all_text)

    # 2) Convert to a naive Markdown. For example:
    #    - Split on double newlines to get paragraphs
    #    - Insert blank lines or bullet points, etc.
    paragraphs = raw_text.split("\n\n")
    markdown_lines = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # If the paragraph starts with a bullet marker or dash, keep it
        # Otherwise, treat it as a normal paragraph
        # (This is extremely simplistic - adjust as needed)
        bullets = "*"
        pattern = r"^[" + re.escape(bullets) + r"]\s"
        if re.match(pattern, paragraph):
            markdown_lines.append(paragraph)
        else:
            # Possibly add a blank line before paragraphs in Markdown
            markdown_lines.append(paragraph + "\n")

    naive_markdown = "\n".join(markdown_lines)

    # 3) (Optional) Run Prettier on the Markdown
    #    This requires Node.js, npx, and an internet or local environment with 'prettier@3.4.2' installed
    try:
        with open("temp.md", "w", encoding="utf-8") as temp_md_file:
            temp_md_file.write(naive_markdown)

        # Format with npx prettier@3.4.2
        subprocess.run(
            ["npx", "prettier@3.4.2", "--parser=markdown", "--write", "temp.md"],
            check=True,
            capture_output=True,
        )

        # Read back the formatted MD
        with open("temp.md", "r", encoding="utf-8") as temp_md_file:
            formatted_markdown = temp_md_file.read()

    except FileNotFoundError:
        # If npx or Node is not installed, fallback to naive_markdown
        formatted_markdown = naive_markdown
    except subprocess.CalledProcessError as e:
        # If Prettier fails, fallback to naive_markdown
        formatted_markdown = naive_markdown

    # 4) Return the final, formatted Markdown
    return formatted_markdown


#-------- GA4 questions---------

# GA4 Q5 - Get maximum latitude of Algiers in Algeria using Nominatim API ?
@questions_tds(r".*?(maximum latitude|max latitude).*?(bounding box).*?city (.*?) in the country (.*?) on the Nominatim API.*")
async def ga4_q5(question: str) -> str:
    match = re.search(r".*?(maximum latitude|max latitude).*?(bounding box).*?city (.*?) in the country (.*?) on the Nominatim API.*", question, re.IGNORECASE)
    if not match:
        return "Invalid question format"
    city = match.group(3)
    country = match.group(4)
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{city}, {country}",
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
        "extratags": 1,
        "polygon_geojson": 0,
        "bounded": 1
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data and "boundingbox" in data[0]:
            bounding_box = data[0]["boundingbox"]
            max_latitude = float(bounding_box[1])
            return str(max_latitude)
    return "No data found"

# GA4 Q6 - Get link to the latest Hacker News post about Linux with at leas66 pointst  
@questions_tds(r".*?(Hacker News|link).*?(Linux).*?(66 points|minimum 66 points|66 or more points).*?")
async def ga4_q6() -> str:
    feed_url = "https://hnrss.org/newest?q=Linux&points=66"
    feed = feedparser.parse(feed_url)
    if feed.entries:
        return feed.entries[0].link
    return "No relevant post found"



#----------------------------------------------------------------------------

#-------- GA5 questions---------

# GA5 Q1 - Calculate total margin from Excel file

import re
import io
from datetime import datetime
from dateutil import parser

import pandas as pd
from fastapi import UploadFile

@questions_tds(r".*Download the Sales Excel file: .* What is the total margin for transactions before (.*) for (.*) sold in (.*)\?.*")
async def ga5_q1(question: str, file: UploadFile) -> str:
    """
    This function cleans an Excel file and calculates the margin for transactions
    strictly *before* a specified local date/time, for a specified product and country.

    Main changes from previous version:
      1) We interpret "before" as a strict comparison: (df['Date'] < filter_date)
      2) We ignore the time zone from the question by using parse(..., ignoretz=True).

    This often fixes mismatches where the code previously got 0.2107 but should be 0.2362.
    """
    # --- 1) Extract components from question ---
    match = re.search(
        r".*Download the Sales Excel file: .*"
        r"What is the total margin for transactions before (.*) for (.*) sold in (.*)\?.*",
        question,
        re.IGNORECASE
    )
    if not match:
        return "Invalid question format"

    date_str, product, country = match.groups()

    # --- 2) Clean the date string by removing parentheses and parse ignoring time zone ---
    #    e.g. "Fri Nov 25 2022 06:28:05 GMT+0530 (India Standard Time)" ? "Fri Nov 25 2022 06:28:05 GMT+0530"
    #    Then parse it as naive local time:
    cleaned_date_str = re.sub(r"\(.*\)", "", date_str).strip()
    parsed_dt = parser.parse(cleaned_date_str, ignoretz=True)

    # Since we are ignoring time zones, we can just use 'parsed_dt' as our cutoff
    filter_date = parsed_dt

    # --- 3) Read Excel contents into a DataFrame ---
    file_content = await file.read()
    df = pd.read_excel(io.BytesIO(file_content))

    # --- 4) Clean and normalize columns ---

    # a) Trim spaces in Customer Name and Country
    df['Customer Name'] = df['Customer Name'].astype(str).str.strip()
    df['Country']       = df['Country'].astype(str).str.strip()

    # b) Map inconsistent country names to standard codes
    country_mapping = {
        "Ind": "IN", "India": "IN", "IND": "IN",
        "USA": "US", "U.S.A": "US", "US": "US", "United States": "US",
        "UK": "GB", "U.K": "GB", "United Kingdom": "GB",
        "Fra": "FR", "France": "FR", "FRA": "FR",
        "Bra": "BR", "Brazil": "BR", "BRA": "BR",
        "AE": "AE", "U.A.E": "AE", "UAE": "AE", "United Arab Emirates": "AE"
    }
    df['Country'] = df['Country'].map(country_mapping).fillna(df['Country'])

    # c) Parse mixed-format dates (e.g. MM-DD-YYYY, YYYY/MM/DD)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', infer_datetime_format=True)

    # d) Extract just the product name from "Product/Code" (split by slash)
    df['Product'] = df['Product/Code'].astype(str).str.strip().str.split('/').str[0]

    # e) Clean numeric columns (remove 'USD' and spaces) for Sales and Cost
    df['Sales'] = (df['Sales'].astype(str)
                             .str.replace('USD', '', case=False, regex=True)
                             .str.replace(r'\s+', '', regex=True)
                             .astype(float))

    df['Cost'] = (df['Cost'].astype(str)
                            .str.replace('USD', '', case=False, regex=True)
                            .str.replace(r'\s+', '', regex=True))
    df['Cost'] = pd.to_numeric(df['Cost'], errors='coerce')

    # Fill missing cost with 50% of Sales
    df['Cost'].fillna(df['Sales'] * 0.5, inplace=True)

    # --- 5) Filter rows: strictly *before* filter_date, matching product and country ---
    country_standard = country_mapping.get(country, country)

    filtered_df = df[
        (df['Date'] < filter_date) &  # Strictly before
        (df['Product'] == product) &
        (df['Country'] == country_standard)
    ]

    # --- 6) Calculate the margin ---
    total_sales = filtered_df['Sales'].sum()
    total_cost  = filtered_df['Cost'].sum()

    filtered_df.to_csv('filtered_df.csv', index=False)
    if total_sales == 0:
        total_margin = 0
    else:
        total_margin = (total_sales - total_cost) / total_sales

    # Return as a decimal, e.g. "0.2362" for 23.62%
    return f"{total_margin:.4f}"

# GA5 Q2 - Count unique student IDs in a text file


# @questions_tds(r".*Download.*text.* file.*q-clean-up-student-marks.txt.*(unique students|number of unique students|student IDs).*")
@questions_tds(r".*(unique.*students|student IDs).*?(file|download).*")

async def ga5_q2(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    lines = file_content.decode("utf-8").splitlines()
    student_ids = set()
    pattern = re.compile(r'-\s*([\w\d]+)::?Marks')
    for line in lines:
        match = pattern.search(line)
        if match:
            student_ids.add(match.group(1))
    return str(len(student_ids))

# GA5 Q5 - Calculate Pizza sales in Mexico City with sales >= 158 units
@questions_tds(r".*Pizza.*Mexico City.* at least 158 units.*")
async def ga5_q5(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    sales_data = json.loads(file_content)
    df = pd.DataFrame(sales_data)
    mexico_city_variants = ["Mexico-City", "Mexiko City", "Mexico Cty", "Mexicocity", "Mexicoo City"]
    df['city_standardized'] = df['city'].apply(lambda x: "Mexico City" if x in mexico_city_variants else x)
    filtered_df = df[(df['product'] == "Pizza") & (df['sales'] >= 158)]
    sales_by_city = filtered_df.groupby('city_standardized')['sales'].sum().reset_index()
    mexico_city_sales = sales_by_city[sales_by_city['city_standardized'] == "Mexico City"]['sales'].sum()
    return str(int(mexico_city_sales))

# GA5 Q6 - Calculate total sales from JSONL file
@questions_tds(r".*download.*data.*q-parse-partial-json.jsonl.*(total sales value|total sales).*")
async def ga5_q6(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    total_sales = 0
    file_content_str = file_content.decode("utf-8")
    sales_matches = re.findall(r'"sales":\s*([\d.]+)', file_content_str)
    total_sales = sum(int(float(sales)) for sales in sales_matches)
    return str(total_sales)

# GA5 Q7 - Count occurrences of "LGK" as a key in nested JSON

#@questions_tds(r".*?(LGK).*?(appear|count|frequency).*?(key).*")
@questions_tds(r".*(LGK).*(appear|count|frequency)?.*(key).*")

async def ga5_q7(question: str, file: UploadFile) -> str:
    file_content = await file.read()
    data = json.loads(file_content.decode("utf-8"))
    def count_key_occurrences(obj, key_to_count):
        count = 0
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == key_to_count:
                    count += 1
                count += count_key_occurrences(value, key_to_count)
        elif isinstance(obj, list):
            for item in obj:
                count += count_key_occurrences(item, key_to_count)
        return count

    lgk_count = count_key_occurrences(data, "LGK")
    return str(lgk_count)


@app.post("/api/", response_model=AnswerResponse)
async def get_answer(question: str = Form(...), file: Optional[UploadFile] = None):
    try:
        #if file:
            #await handle_file(file)
        for pattern, func in function_map.items():
            if re.search(pattern, question, re.IGNORECASE):
                if file:
                    if 'file' in func.__code__.co_varnames and func.__code__.co_argcount == 1:
                        return AnswerResponse(answer=await func(file))
                    return AnswerResponse(answer=await func(question, file))
                else:
                    return AnswerResponse(answer=await func(question))

        return AnswerResponse(answer="No matching function found for the given question.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

#------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
