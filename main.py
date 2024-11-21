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

This tool provides specific recommendations on how to enhance your content based on competitor analysis, including new sections to add, where to place them, and the appropriate heading levels.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def extract_content_structure(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts and styles
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        # Extract headings and their hierarchy
        content_structure = []
        for header in soup.find_all(['h2', 'h3', 'h4']):
            header_text = header.get_text(strip=True)
            header_level = header.name
            content_structure.append({'level': header_level, 'text': header_text})
        return content_structure
    except Exception as e:
        st.warning(f"Error extracting content structure: {str(e)}")
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
            for header in soup.find_all(['h2', 'h3', 'h4']):
                header_text = header.get_text(strip=True)
                header_level = header.name
                headings.append({'level': header_level, 'text': header_text})
            all_headings.extend(headings)
        except Exception as e:
            st.warning(f"Error processing {file.name}: {e}")
            continue
    return all_headings

def generate_detailed_recommendations(keyword, user_structure, competitor_headings, api_key):
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an SEO content strategist.

Your task is to analyze the provided original content structure and competitor headings to generate specific recommendations for improvement.

- **Keyword**: "{keyword}"
- **Original Content Structure**:
{user_structure}

- **Competitor Headings**:
{competitor_headings}

Instructions:

1. Identify important topics or subtopics in the competitor headings that are missing or underdeveloped in the original content.
2. For each identified area:
   - Recommend new sections to add.
   - Specify where to place them within the existing content structure.
   - Indicate the appropriate heading level (H2, H3, H4).
   - Provide a suggested heading title.
   - Briefly describe what content should be included under each new section.
3. If rearranging existing sections would improve content flow, provide specific suggestions.
4. If the original content is already comprehensive, acknowledge that but suggest any minor improvements if applicable.
5. Avoid using branded terms unless necessary.
6. Present the recommendations clearly and in a structured format.

Format:

For each recommendation:

- **Recommendation #X**:
  - **New Section Heading**: [Suggested heading title]
  - **Heading Level**: [H2/H3/H4]
  - **Placement**: [Where to insert in the existing structure]
  - **Content Description**: [Brief description of what to include]

If rearranging sections:

- **Rearrangement Suggestion**:
  - **Current Section**: [Existing heading]
  - **New Position**: [Where it should be moved]
  - **Reason**: [Why this improves the content flow]

Provide a final summary acknowledging if the content is comprehensive or noting any overall improvements.

IMPORTANT: Do not include any additional text outside of the specified format.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Provide detailed SEO content recommendations based on the analysis."},
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
                    # Extract content structure from user's content
                    user_structure = extract_content_structure(html_content)

                    # Analyze competitor content
                    competitor_headings = analyze_competitor_content(uploaded_competitor_files)

                    # Generate detailed recommendations
                    recommendations = generate_detailed_recommendations(
                        keyword=keyword,
                        user_structure=user_structure,
                        competitor_headings=competitor_headings,
                        api_key=openai_api_key
                    )

                    if recommendations:
                        st.subheader("Detailed Recommendations:")
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
                            elif line.startswith('  - **'):
                                if 'New Section Heading' in line:
                                    doc.add_heading(line[4:].strip(), level=3)
                                else:
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
