import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
from openai import OpenAI
from docx import Document
from docx.shared import RGBColor
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE
from io import BytesIO
import time
import random
from serpapi import GoogleSearch
import re

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

def get_top_urls(keyword, serpapi_key, num_results=5):
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

def extract_headings_and_text(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts and styles
        for element in soup(['script', 'style']):
            element.decompose()
        # Extract headings and text
        headings = []
        for tag in ['h2', 'h3', 'h4']:
            for element in soup.find_all(tag):
                headings.append((tag, element.get_text(strip=True)))
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        return headings, paragraphs
    except Exception as e:
        st.warning(f"Error extracting content: {str(e)}")
        return [], []

def analyze_competitor_content(urls):
    all_headings = []
    for url in urls:
        try:
            time.sleep(random.uniform(1, 3))  # Random delay
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                              " AppleWebKit/537.36 (KHTML, like Gecko)"
                              " Chrome/92.0.4515.159 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove scripts and styles
            for element in soup(['script', 'style']):
                element.decompose()
            # Extract headings
            headings = {
                "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
                "h3": [h.get_text(strip=True) for h in soup.find_all("h3")],
                "h4": [h.get_text(strip=True) for h in soup.find_all("h4")]
            }
            all_headings.append(headings)
        except requests.exceptions.RequestException as e:
            st.warning(f"Error processing {url}: {str(e)}")
            continue
    return all_headings

def analyze_headings(all_headings):
    analysis = {}
    for level in ["h2", "h3", "h4"]:
        headings = [h for page in all_headings for h in page[level]]
        analysis[level] = {
            "count": len(headings),
            "avg_length": sum(len(h) for h in headings) / len(headings) if headings else 0,
            "examples": headings[:10]  # Include up to 10 example headings
        }
    return analysis

def generate_optimized_structure(keyword, heading_analysis, api_key):
    client = OpenAI(api_key=api_key)

    prompt = f"""
Generate an optimized heading structure for a content brief on the keyword: "{keyword}"

Use the following heading analysis as a guide:
{heading_analysis}

Pay special attention to the 'examples' in each heading level, as these are actual headings from top-ranking pages.

Requirements:
1. Create a logical, user-focused structure with H2s, H3s, and H4s that guides the reader through understanding the topic comprehensively.
2. Ensure the structure flows cohesively, focusing on what users should know about the topic.
3. Avoid using branded subheads unless absolutely necessary for the topic.
4. Include brief directions on what content should be included under each heading.
5. Maintain a similar style and tone to the example headings while improving clarity and user focus.
6. Organize the content in a way that naturally progresses from basic concepts to more advanced ideas.
7. Include sections that address common questions or concerns related to the topic.
8. Where applicable, include comparisons with alternatives or related concepts.
9. Consider including a section on practical application or next steps for the reader.
10. Ensure the outline covers the topic thoroughly while remaining focused and relevant to the main keyword.

IMPORTANT: Do not use any markdown syntax (such as ##, ###, or *) in your output. Use only the following format:

H2: [Heading based on examples and best practices]
- [Brief direction on content]
  H3: [Subheading based on examples and best practices]
  - [Brief direction on content]
    H4: [Sub-subheading based on examples and best practices]
    - [Brief direction on content]

Repeat this structure as needed, ensuring a logical flow of information that best serves the user's needs based on the given keyword.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an SEO expert creating optimized, user-focused content outlines for any given topic. Do not use markdown syntax in your output."},
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

def create_word_document(keyword, optimized_structure, original_headings):
    if not optimized_structure:
        st.error("No content to create document. Please try again.")
        return None

    doc = Document()

    # Add styles
    styles = doc.styles
    h1_style = styles.add_style('H1', WD_STYLE_TYPE.PARAGRAPH)
    h1_style.font.size = Pt(18)
    h1_style.font.bold = True

    h2_style = styles.add_style('H2', WD_STYLE_TYPE.PARAGRAPH)
    h2_style.font.size = Pt(16)
    h2_style.font.bold = True

    h3_style = styles.add_style('H3', WD_STYLE_TYPE.PARAGRAPH)
    h3_style.font.size = Pt(14)
    h3_style.font.bold = True

    h4_style = styles.add_style('H4', WD_STYLE_TYPE.PARAGRAPH)
    h4_style.font.size = Pt(12)
    h4_style.font.bold = True

    # Add title
    doc.add_paragraph(f'Content Brief: {keyword}', style='H1')

    # Existing headings for comparison
    existing_headings = set([text for _, text in original_headings])

    # Process the optimized structure
    lines = optimized_structure.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('H2:'):
            heading_text = line[3:].strip()
            p = doc.add_paragraph(heading_text, style='H2')
            if heading_text not in existing_headings:
                p.runs[0].font.color.rgb = RGBColor(255, 0, 0)
            i += 1
            # Add content for H2
            while i < len(lines) and lines[i].strip().startswith('-'):
                content = lines[i].strip()
                p = doc.add_paragraph(content, style='List Bullet')
                p.paragraph_format.left_indent = Pt(12)
                i += 1
        elif line.startswith('H3:'):
            heading_text = line[3:].strip()
            p = doc.add_paragraph(heading_text, style='H3')
            if heading_text not in existing_headings:
                p.runs[0].font.color.rgb = RGBColor(255, 0, 0)
            i += 1
            # Add content for H3
            while i < len(lines) and lines[i].strip().startswith('-'):
                content = lines[i].strip()
                p = doc.add_paragraph(content, style='List Bullet')
                p.paragraph_format.left_indent = Pt(24)
                i += 1
        elif line.startswith('H4:'):
            heading_text = line[3:].strip()
            p = doc.add_paragraph(heading_text, style='H4')
            if heading_text not in existing_headings:
                p.runs[0].font.color.rgb = RGBColor(255, 0, 0)
            i += 1
            # Add content for H4
            while i < len(lines) and lines[i].strip().startswith('-'):
                content = lines[i].strip()
                p = doc.add_paragraph(content, style='List Bullet')
                p.paragraph_format.left_indent = Pt(36)
                i += 1
        else:
            i += 1

    return doc

# Streamlit UI
st.write("Enter your API keys and target keyword below:")

openai_api_key = st.text_input("OpenAI API key:", value=st.session_state.openai_api_key, type="password")
serpapi_api_key = st.text_input("SerpApi API key:", value=st.session_state.serpapi_api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.openai_api_key = openai_api_key
st.session_state.serpapi_api_key = serpapi_api_key
st.session_state.keyword = keyword

# File uploader for HTML
uploaded_file = st.file_uploader("Upload your HTML file:", type=['html', 'htm'])

if st.button("Optimize Content"):
    if openai_api_key and serpapi_api_key and keyword and uploaded_file:
        with st.spinner("Processing..."):
            # Read user's HTML content
            html_content = uploaded_file.read().decode('utf-8')
            user_headings, user_paragraphs = extract_headings_and_text(html_content)

            # Get competitor data
            urls = get_top_urls(keyword, serpapi_api_key, num_results=10)
            if not urls:
                st.error("No competitor URLs were extracted. Please check your SerpApi key and try again.")
            else:
                competitor_headings_list = analyze_competitor_content(urls)
                heading_analysis = analyze_headings(competitor_headings_list)

                # Generate optimized structure
                optimized_structure = generate_optimized_structure(
                    keyword=keyword,
                    heading_analysis=heading_analysis,
                    api_key=openai_api_key
                )

                if optimized_structure:
                    st.subheader("Optimized Content Structure:")
                    st.text(optimized_structure)

                    # Create Word document
                    doc = create_word_document(keyword, optimized_structure, user_headings)
                    if doc:
                        bio = BytesIO()
                        doc.save(bio)
                        st.download_button(
                            label="Download Updated Content",
                            data=bio.getvalue(),
                            file_name=f"content_brief_{keyword.replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                else:
                    st.error("Failed to generate optimized structure. Please try again.")
    else:
        st.error("Please enter your API keys, target keyword, and upload your HTML file to proceed.")
