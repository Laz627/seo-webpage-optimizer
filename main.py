import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from docx import Document
from io import BytesIO
import time
import random
from serpapi import GoogleSearch
import re
from fp.fp import FreeProxy  # Import FreeProxy

# Set page config
st.set_page_config(page_title="Content Optimizer", layout="wide")
st.title("Content Optimizer")

# Instructions
st.markdown("""
## How to Use This Tool:
1. **Enter your OpenAI and SerpApi API keys** in the fields below.
2. **Upload the HTML file** of your web page.
3. **Input your target keyword.**
4. Click **'Optimize Content'** to analyze top-ranking competitor pages and receive content recommendations.
5. **Download the updated content** as a Word document with changes highlighted.

This tool helps you enhance your existing content by comparing it with top-ranking pages for your target keyword.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'serpapi_api_key' not in st.session_state:
    st.session_state.serpapi_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

# List of user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    ' AppleWebKit/537.36 (KHTML, like Gecko)'
    ' Chrome/93.0.4577.63 Safari/537.36',
    # Add more user agents as needed
]

def get_random_headers():
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,'
                  'application/xml;q=0.9,image/webp,'
                  'image/apng,*/*;q=0.8',
        'Connection': 'keep-alive',
    }
    return headers

# Function to get a free proxy using FreeProxy
def get_free_proxy():
    try:
        proxy = FreeProxy(timeout=1, rand=True, anonym=True).get()
        return proxy
    except Exception as e:
        st.warning(f"Error fetching proxy: {str(e)}")
        return None

def get_top_urls(keyword, serpapi_key, num_results=15):
    params = {
        "api_key": serpapi_key,
        "engine": "google",
        "q": keyword,
        "num": num_results,
        "gl": "us",
        "hl": "en"
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        urls = []
        for result in results.get("organic_results", [])[:num_results]:
            urls.append(result["link"])
        return urls
    except Exception as e:
        st.error(f"Error fetching search results: {str(e)}")
        return []

def analyze_competitor_content(urls):
    all_headings = []
    for url in urls:
        success = False
        attempts = 0
        max_attempts = 5
        while not success and attempts < max_attempts:
            try:
                time.sleep(random.uniform(2, 5))  # Random delay
                headers = get_random_headers()
                proxy = get_free_proxy()
                if not proxy:
                    st.warning("Could not obtain a free proxy. Proceeding without proxy.")
                    proxies = None
                else:
                    proxies = {
                        'http': f'http://{proxy}',
                        'https': f'http://{proxy}',
                    }
                session = requests.Session()
                retries = requests.adapters.Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[403, 500, 502, 503, 504],
                    raise_on_status=False,
                )
                adapter = requests.adapters.HTTPAdapter(max_retries=retries)
                session.mount('http://', adapter)
                session.mount('https://', adapter)
                response = session.get(
                    url, headers=headers, proxies=proxies, timeout=10
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                # Remove scripts and styles
                for element in soup(['script', 'style', 'noscript']):
                    element.decompose()
                # Extract headings
                headings = {
                    "h2": [h.get_text(strip=True)
                           for h in soup.find_all("h2")],
                    "h3": [h.get_text(strip=True)
                           for h in soup.find_all("h3")],
                    "h4": [h.get_text(strip=True)
                           for h in soup.find_all("h4")]
                }
                all_headings.append(headings)
                success = True
            except requests.exceptions.RequestException as e:
                attempts += 1
                st.warning(
                    f"Attempt {attempts} for {url} failed with proxy "
                    f"{proxy if proxy else 'No Proxy'}: {e}"
                )
        if not success:
            st.warning(f"Failed to process {url} after {max_attempts} attempts.")
    return all_headings

def analyze_headings(all_headings):
    analysis = {}
    for level in ["h2", "h3", "h4"]:
        headings = [h for page in all_headings for h in page[level]]
        analysis[level] = {
            "count": len(headings),
            "avg_length": (sum(len(h) for h in headings) /
                           len(headings)) if headings else 0,
            "examples": headings[:10]  # Up to 10 examples
        }
    return analysis

def generate_optimized_structure(keyword, heading_analysis, api_key):
    client = OpenAI(api_key=api_key)

    prompt = f"""
Generate an optimized heading structure for a content brief on the
keyword: "{keyword}"

Use the following heading analysis as a guide:
{heading_analysis}

Pay special attention to the 'examples' in each heading level, as these
are actual headings from top-ranking pages.

[Include your requirements here]

IMPORTANT: Do not use any markdown syntax (such as ##, ###, or *) in
your output. Use only the following format:

H2: [Heading based on examples and best practices]
- [Brief direction on content]
  H3: [Subheading based on examples and best practices]
  - [Brief direction on content]
    H4: [Sub-subheading based on examples and best practices]
    - [Brief direction on content]

Repeat this structure as needed, ensuring a logical flow of information
that best serves the user's needs based on the given keyword.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an SEO expert "
                 "creating optimized, user-focused content outlines for "
                 "any given topic. Do not use markdown syntax in your "
                 "output."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        output = response.choices[0].message.content
        output = output.replace('#', '').replace('*', '').replace('_', '')
        return output
    except Exception as e:
        st.error(f"Error generating optimized structure: {str(e)}")
        return None

def extract_headings_and_text(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts and styles
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        # Extract headings and text
        headings = []
        for tag in ['h2', 'h3', 'h4']:
            for element in soup.find_all(tag):
                headings.append((tag, element.get_text(strip=True)))
        paragraphs = [p.get_text(strip=True)
                      for p in soup.find_all('p')]
        return headings, paragraphs
    except Exception as e:
        st.warning(f"Error extracting content: {str(e)}")
        return [], []

def highlight_differences(original_html, recommendations):
    soup_original = BeautifulSoup(original_html, 'html.parser')

    # Ensure that the body exists
    if not soup_original.body:
        soup_original.body = soup_original.new_tag('body')
        if soup_original.html:
            soup_original.html.append(soup_original.body)
        else:
            soup_original.append(soup_original.body)

    # Extract existing headings
    existing_headings = {
        (tag.name, tag.get_text(strip=True))
        for tag in soup_original.find_all(['h2', 'h3', 'h4'])
    }

    # Parse recommendations into a list of headings
    recommended_headings = []
    lines = recommendations.strip().split('\n')
    for line in lines:
        if line.startswith('H2:'):
            tag = 'h2'
            text = line[3:].strip()
            recommended_headings.append((tag, text))
        elif line.startswith('H3:'):
            tag = 'h3'
            text = line[3:].strip()
            recommended_headings.append((tag, text))
        elif line.startswith('H4:'):
            tag = 'h4'
            text = line[3:].strip()
            recommended_headings.append((tag, text))

    # Identify new headings to add
    new_headings = [
        (tag, text) for tag, text in recommended_headings
        if (tag, text) not in existing_headings
    ]

    # Insert new headings at the end of the body
    for tag_name, text in new_headings:
        new_tag = soup_original.new_tag(tag_name)
        new_tag.string = text
        new_tag['style'] = 'color:red;'  # Highlight new headings
        soup_original.body.append(new_tag)

    return str(soup_original)

# Streamlit UI
st.write("Enter your API keys and target keyword below:")

openai_api_key = st.text_input(
    "OpenAI API key:", value=st.session_state.openai_api_key, type="password"
)
serpapi_api_key = st.text_input(
    "SerpApi API key:", value=st.session_state.serpapi_api_key, type="password"
)
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.openai_api_key = openai_api_key
st.session_state.serpapi_api_key = serpapi_api_key
st.session_state.keyword = keyword

# File uploader for HTML
uploaded_file = st.file_uploader(
    "Upload your HTML file:", type=['html', 'htm']
)

if st.button("Optimize Content"):
    if openai_api_key and serpapi_api_key and keyword and uploaded_file:
        with st.spinner("Processing..."):
            try:
                # Read user's HTML content
                html_content = uploaded_file.read().decode('utf-8')
                if not html_content:
                    st.error("Uploaded HTML content is empty.")
                else:
                    # Extract headings and paragraphs
                    user_headings, user_paragraphs = extract_headings_and_text(
                        html_content
                    )

                    # Get competitor data
                    urls = get_top_urls(
                        keyword, serpapi_api_key, num_results=15
                    )
                    if not urls:
                        st.error(
                            "No competitor URLs were extracted. Please check "
                            "your SerpApi key and try again."
                        )
                    else:
                        competitor_headings_list = analyze_competitor_content(
                            urls
                        )
                        heading_analysis = analyze_headings(
                            competitor_headings_list
                        )

                        # Generate optimized structure
                        optimized_structure = generate_optimized_structure(
                            keyword=keyword,
                            heading_analysis=heading_analysis,
                            api_key=openai_api_key
                        )

                        if optimized_structure:
                            st.subheader("Optimized Content Structure:")
                            st.text(optimized_structure)

                            # Incorporate recommendations into original HTML
                            modified_html = highlight_differences(
                                html_content, optimized_structure
                            )

                            # Convert modified HTML to Word document
                            from html2docx import html2docx
                            doc = Document()
                            html2docx(modified_html, doc)

                            # Create a BytesIO buffer and save the docx content
                            bio = BytesIO()
                            doc.save(bio)
                            bio.seek(0)

                            st.download_button(
                                label="Download Updated Content",
                                data=bio,
                                file_name=(
                                    f"updated_content_{keyword.replace(' ', '_')}.docx"
                                ),
                                mime=(
                                    "application/vnd.openxmlformats-officedocument."
                                    "wordprocessingml.document"
                                )
                            )
                        else:
                            st.error(
                                "Failed to generate optimized structure. "
                                "Please try again."
                            )
            except Exception as e:
                st.error(f"Error processing the uploaded file: {str(e)}")
    else:
        st.error(
            "Please enter your API keys, target keyword, and upload your HTML "
            "file to proceed."
        )
