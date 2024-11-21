import streamlit as st
from bs4 import BeautifulSoup
from openai import OpenAI
from docx import Document
from io import BytesIO

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
6. **Download the recommendations** as a Word document.

This tool provides specific recommendations on how to enhance your content based on competitor analysis.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def extract_headings_and_content(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts and styles
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        # Extract headings and their content
        content = []
        for header in soup.find_all(['h2', 'h3', 'h4']):
            header_text = header.get_text(strip=True)
            sibling_text = ''
            for sibling in header.next_siblings:
                if sibling.name and sibling.name.startswith('h'):
                    break
                if sibling.name == 'p':
                    sibling_text += sibling.get_text(strip=True) + '\n'
            content.append({'header': header_text, 'content': sibling_text})
        return content
    except Exception as e:
        st.warning(f"Error extracting content: {str(e)}")
        return []

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
            headings = []
            for tag in ['h2', 'h3', 'h4']:
                for h in soup.find_all(tag):
                    headings.append(h.get_text(strip=True))
            all_headings.extend(headings)
        except Exception as e:
            st.warning(f"Error processing {file.name}: {e}")
            continue
    return all_headings

def generate_specific_recommendations(keyword, user_content, competitor_headings, api_key):
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an SEO content expert.

Your task is to analyze the provided original content and competitor headings to generate specific recommendations for improvement.

- **Keyword**: "{keyword}"
- **Original Content Headings and Content**:
{user_content}

- **Competitor Headings**:
{competitor_headings}

Instructions:

1. Identify any important topics or subtopics in the competitor headings that are missing or underdeveloped in the original content.
2. For each identified area, provide a specific recommendation on what to add or modify in the original content.
3. If the original content already covers the topic comprehensively, acknowledge that no significant changes are needed.
4. Avoid using branded terms unless they are necessary.
5. Present the recommendations clearly, specifying where changes should be made.

Format:

- **Recommendation #1**:
  - **Section**: [Specify the heading or section in the original content]
  - **Suggestion**: [Detailed suggestion]

Repeat this format for each recommendation.

If no significant changes are needed, provide a summary stating that the original content is comprehensive and well-optimized.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Provide specific, actionable SEO content recommendations based on the analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        output = response.choices[0].message.content
        return output
    except Exception as e:
        st.error(f"Error generating recommendations:\n\n{str(e)}")
        return None

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
                    # Extract headings and content from user's content
                    user_content = extract_headings_and_content(html_content)

                    # Analyze competitor content
                    competitor_headings = analyze_competitor_content(uploaded_competitor_files)

                    # Generate specific recommendations
                    recommendations = generate_specific_recommendations(
                        keyword=keyword,
                        user_content=user_content,
                        competitor_headings=competitor_headings,
                        api_key=openai_api_key
                    )

                    if recommendations:
                        st.subheader("Specific Recommendations:")
                        st.text(recommendations)

                        # Create a Word document with the recommendations
                        doc = Document()
                        doc.add_heading("Content Optimization Recommendations", level=1)
                        doc.add_paragraph(f"Keyword: {keyword}")

                        for line in recommendations.split('\n'):
                            if line.strip() == '':
                                continue  # Skip empty lines
                            if line.startswith('- **Recommendation'):
                                doc.add_heading(line[2:].strip(), level=2)
                            elif line.startswith('  - **Section'):
                                doc.add_heading(line[4:].strip(), level=3)
                            elif line.startswith('  - **Suggestion'):
                                doc.add_paragraph(line[4:].strip(), style='List Bullet')
                            else:
                                doc.add_paragraph(line)

                        # Create a BytesIO buffer and save the docx content
                        bio = BytesIO()
                        doc.save(bio)
                        bio.seek(0)

                        st.download_button(
                            label="Download Recommendations",
                            data=bio,
                            file_name=f"recommendations_{keyword.replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        st.error("Failed to generate recommendations. Please try again.")
            except Exception as e:
                st.error(f"Error processing files: {str(e)}")
    else:
        st.error("Please enter your API key, target keyword, and upload your HTML files to proceed.")
