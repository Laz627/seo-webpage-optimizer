import streamlit as st
from bs4 import BeautifulSoup
from openai import OpenAI
from docx import Document
from io import BytesIO
import difflib

# Set page config
st.set_page_config(page_title="Content Optimizer", layout="wide")
st.title("Content Optimizer")

# Instructions
st.markdown("""
## How to Use This Tool:
1. **Enter your OpenAI API key** in the field below.
2. **Upload the HTML file** of your web page.
3. **Input your target keyword.**
4. **Upload competitor HTML files** for comparison.
5. Click **'Optimize Content'** to analyze competitor pages and receive content recommendations.
6. **Download the updated content** as a Word document with changes highlighted.

This tool helps you enhance your existing content by comparing it with competitor pages for your target keyword.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

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
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        return headings, paragraphs
    except Exception as e:
        st.warning(f"Error extracting content: {str(e)}")
        return [], []

def analyze_competitor_content(html_files):
    all_headings = []
    for file in html_files:
        try:
            html_content = file.read().decode('utf-8')
            soup = BeautifulSoup(html_content, "html.parser")
            # Remove scripts and styles
            for element in soup(['script', 'style', 'noscript']):
                element.decompose()
            # Extract headings
            headings = {
                "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
                "h3": [h.get_text(strip=True) for h in soup.find_all("h3")],
                "h4": [h.get_text(strip=True) for h in soup.find_all("h4")]
            }
            all_headings.append(headings)
        except Exception as e:
            st.warning(f"Error processing {file.name}: {e}")
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

Pay special attention to the 'examples' in each heading level, as these are actual headings from competitor pages.

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

def highlight_differences(original_html, recommendations):
    # Parse the original HTML
    soup_original = BeautifulSoup(original_html, 'html.parser')

    # Ensure the soup has a body
    if not soup_original.body:
        # Create a new body tag and wrap the entire content
        new_body = soup_original.new_tag('body')
        new_body.append(soup_original)
        soup_original.insert(0, new_body)

    # Extract text from original HTML
    original_text = soup_original.get_text(separator='\n')

    # Use AI recommendations as new content
    new_content = recommendations

    # Split texts into lines
    original_lines = [line.strip() for line in original_text.split('\n') if line.strip()]
    new_lines = [line.strip() for line in new_content.split('\n') if line.strip()]

    # Compute diff
    diff = list(difflib.ndiff(original_lines, new_lines))

    # Apply changes to the original soup
    for line in diff:
        if line.startswith('- '):
            # Find the text in the original HTML and apply strikethrough
            text_to_find = line[2:].strip()
            tag = soup_original.find(string=lambda text: text and text.strip() == text_to_find)
            if tag:
                del_tag = soup_original.new_tag('del', style="color:red;")
                del_tag.string = tag
                tag.replace_with(del_tag)
        elif line.startswith('+ '):
            # Insert additions at the end of the body
            text_to_add = line[2:].strip()
            new_tag = soup_original.new_tag('span', style="color:red;")
            new_tag.string = text_to_add
            soup_original.body.append(new_tag)
            soup_original.body.append(soup_original.new_tag('br'))

    # Return modified HTML
    return str(soup_original)

def convert_html_to_docx(html_content):
    from html2docx import html2docx
    doc = Document()
    html2docx(html_content, doc)
    return doc

# Streamlit UI
st.write("Enter your API key and target keyword below:")

openai_api_key = st.text_input("OpenAI API key:", value=st.session_state.openai_api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.openai_api_key = openai_api_key
st.session_state.keyword = keyword

# File uploader for user's HTML file
uploaded_file = st.file_uploader("Upload your HTML file:", type=['html', 'htm'])

# File uploader for competitor HTML files
uploaded_competitor_files = st.file_uploader(
    "Upload competitor HTML files (you can select multiple files):",
    type=['html', 'htm'],
    accept_multiple_files=True
)

if st.button("Optimize Content"):
    if openai_api_key and keyword and uploaded_file and uploaded_competitor_files:
        with st.spinner("Processing..."):
            try:
                # Read user's HTML content
                html_content = uploaded_file.read().decode('utf-8')
                if not html_content:
                    st.error("Uploaded HTML content is empty.")
                else:
                    # Extract headings and paragraphs from user's content
                    user_headings, user_paragraphs = extract_headings_and_text(html_content)

                    # Analyze competitor content
                    competitor_headings_list = analyze_competitor_content(uploaded_competitor_files)
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

                        # Incorporate recommendations into original HTML
                        modified_html = highlight_differences(html_content, optimized_structure)

                        # Convert modified HTML to Word document
                        doc = convert_html_to_docx(modified_html)

                        # Create a BytesIO buffer and save the docx content
                        bio = BytesIO()
                        doc.save(bio)
                        bio.seek(0)

                        st.download_button(
                            label="Download Updated Content",
                            data=bio,
                            file_name=f"updated_content_{keyword.replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        st.error("Failed to generate optimized structure. Please try again.")
            except Exception as e:
                st.error(f"Error processing files: {str(e)}")
    else:
        st.error("Please enter your API key, target keyword, and upload your HTML files to proceed.")
