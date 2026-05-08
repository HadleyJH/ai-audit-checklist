import json
import re
from io import BytesIO
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from openai import OpenAI


st.set_page_config(
    page_title="AI Optimisation Audit Checklist",
    page_icon="✅",
    layout="wide"
)


CHECKLIST = [
    {
        "category": "Technical",
        "item": "Server supports real-time AI fetch, with low TTFB and stable hosting",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Technical",
        "item": "No significant 499 HTTP errors detected in logs",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Technical",
        "item": "HTML is clean and semantically structured with proper heading hierarchy",
        "priority": "High",
        "weighting": 2,
    },
    {
        "category": "Technical",
        "item": "Important content is available in crawlable HTML, not hidden behind JavaScript",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Technical",
        "item": "Page has clear title tag and meta description",
        "priority": "High",
        "weighting": 2,
    },
    {
        "category": "Structured Data",
        "item": "Relevant schema markup is present, such as Product, FAQPage, BreadcrumbList, Organisation or Article",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Structured Data",
        "item": "Schema is detailed and machine-readable, including product, review, price, availability or entity data where relevant",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Content",
        "item": "Page directly answers customer questions in clear, natural language",
        "priority": "High",
        "weighting": 2,
    },
    {
        "category": "Content",
        "item": "Content demonstrates expertise, authority and trust signals",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "Content",
        "item": "Page includes useful supporting information such as FAQs, comparisons, benefits, use cases or buying guidance",
        "priority": "Medium",
        "weighting": 2,
    },
    {
        "category": "Entity Optimisation",
        "item": "Brand, product and category entities are clearly described",
        "priority": "Medium",
        "weighting": 2,
    },
    {
        "category": "Entity Optimisation",
        "item": "The page uses consistent terminology around products, categories, attributes and customer problems",
        "priority": "Medium",
        "weighting": 2,
    },
    {
        "category": "Internal Linking",
        "item": "Page includes useful internal links to related categories, guides, products or support content",
        "priority": "Medium",
        "weighting": 2,
    },
    {
        "category": "UX / Trust",
        "item": "Page includes visible trust signals, such as reviews, delivery information, returns, guarantees or customer support",
        "priority": "Medium",
        "weighting": 2,
    },
    {
        "category": "AI Readability",
        "item": "Content is easy for AI systems to summarise, with clear sections, headings and concise answers",
        "priority": "High",
        "weighting": 3,
    },
    {
        "category": "AI Readability",
        "item": "Page provides enough context for standalone citation in AI search results",
        "priority": "High",
        "weighting": 2,
    },
]


def normalise_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def fetch_page(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; SEO-AI-Audit-Bot/1.0; "
            "+https://example.com/audit)"
        )
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    return {
        "url": response.url,
        "status_code": response.status_code,
        "html": response.text,
        "ttfb_seconds": response.elapsed.total_seconds(),
    }


def extract_page_signals(html: str, url: str, status_code: int, ttfb_seconds: float):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta_description_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = (
        meta_description_tag.get("content", "").strip()
        if meta_description_tag
        else ""
    )

    canonical_tag = soup.find("link", rel=re.compile("canonical", re.I))
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""

    headings = {
        f"h{i}": [h.get_text(" ", strip=True) for h in soup.find_all(f"h{i}")]
        for i in range(1, 7)
    }

    json_ld_blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if text:
            json_ld_blocks.append(text.strip()[:5000])

    schema_types = []
    for block in json_ld_blocks:
        try:
            parsed = json.loads(block)
            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if isinstance(item, dict):
                    if "@graph" in item and isinstance(item["@graph"], list):
                        for graph_item in item["@graph"]:
                            if isinstance(graph_item, dict) and "@type" in graph_item:
                                schema_types.append(str(graph_item["@type"]))
                    elif "@type" in item:
                        schema_types.append(str(item["@type"]))
        except Exception:
            schema_types.append("Unparseable JSON-LD")

    body_text = soup.get_text(" ", strip=True)
    body_text = re.sub(r"\s+", " ", body_text)

    links = soup.find_all("a", href=True)
    parsed_domain = urlparse(url).netloc.replace("www.", "")

    internal_links = []
    external_links = []

    for link in links:
        href = link.get("href", "")
        text = link.get_text(" ", strip=True)

        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        if href.startswith("/") or parsed_domain in href:
            internal_links.append({"text": text, "href": href})
        else:
            external_links.append({"text": text, "href": href})

    images = soup.find_all("img")
    images_missing_alt = [
        img.get("src", "") for img in images if not img.get("alt")
    ]

    faq_like_questions = re.findall(
        r"([A-Z][^.!?]{10,120}\?)",
        body_text
    )[:20]

    trust_terms = [
        "review", "reviews", "trustpilot", "delivery", "returns", "guarantee",
        "warranty", "secure", "customer service", "contact us", "free shipping",
        "payment", "klarna"
    ]

    visible_trust_terms = [
        term for term in trust_terms if term.lower() in body_text.lower()
    ]

    return {
        "url": url,
        "status_code": status_code,
        "ttfb_seconds": round(ttfb_seconds, 3),
        "title": title,
        "title_length": len(title),
        "meta_description": meta_description,
        "meta_description_length": len(meta_description),
        "canonical": canonical,
        "headings": headings,
        "h1_count": len(headings["h1"]),
        "schema_types": list(set(schema_types)),
        "json_ld_count": len(json_ld_blocks),
        "word_count": len(body_text.split()),
        "body_text_sample": body_text[:8000],
        "internal_link_count": len(internal_links),
        "external_link_count": len(external_links),
        "sample_internal_links": internal_links[:30],
        "image_count": len(images),
        "images_missing_alt_count": len(images_missing_alt),
        "faq_like_questions": faq_like_questions,
        "visible_trust_terms": visible_trust_terms,
    }


def get_openai_client():
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OpenAI API key missing. Add OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()

    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def run_ai_audit(client, signals, checklist):
    prompt = f"""
You are an expert technical SEO and AI search optimisation auditor.

Audit the supplied ecommerce URL against the checklist.

Score each item from 0 to 5:
0 = not present / cannot verify
1 = very weak
2 = weak
3 = acceptable
4 = strong
5 = excellent

For each item, return:
- category
- item
- priority
- weighting
- score
- weighted_score
- evidence
- recommendation

Use only the supplied page signals. Do not invent evidence.

Also return:
- total_weighted_score
- max_possible_score
- readiness_percentage
- maturity_level
- executive_summary
- top_priorities

Checklist:
{json.dumps(checklist, indent=2)}

Page signals:
{json.dumps(signals, indent=2)}

Return valid JSON only, with this structure:
{{
  "total_weighted_score": 0,
  "max_possible_score": 0,
  "readiness_percentage": 0,
  "maturity_level": "",
  "executive_summary": "",
  "top_priorities": [],
  "audit": [
    {{
      "category": "",
      "item": "",
      "priority": "",
      "weighting": 0,
      "score": 0,
      "weighted_score": 0,
      "evidence": "",
      "recommendation": ""
    }}
  ]
}}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.2,
    )

    output_text = response.output_text.strip()

    try:
        return json.loads(output_text)
    except json.JSONDecodeError:
        st.error("The AI response was not valid JSON. Showing raw output below.")
        st.code(output_text)
        st.stop()


def create_excel_export(results, signals):
    output = BytesIO()

    summary_df = pd.DataFrame([
        {
            "URL": signals.get("url", ""),
            "Total Weighted Score": results.get("total_weighted_score", 0),
            "Max Possible Score": results.get("max_possible_score", 0),
            "AI Readiness %": results.get("readiness_percentage", 0),
            "Maturity Level": results.get("maturity_level", ""),
            "Executive Summary": results.get("executive_summary", ""),
            "Top Priorities": "\n".join(results.get("top_priorities", [])),
        }
    ])

    audit_df = pd.DataFrame(results.get("audit", []))

    signals_df = pd.DataFrame([
        {
            "URL": signals.get("url", ""),
            "Status Code": signals.get("status_code", ""),
            "TTFB Seconds": signals.get("ttfb_seconds", ""),
            "Title": signals.get("title", ""),
            "Title Length": signals.get("title_length", ""),
            "Meta Description": signals.get("meta_description", ""),
            "Meta Description Length": signals.get("meta_description_length", ""),
            "Canonical": signals.get("canonical", ""),
            "H1 Count": signals.get("h1_count", ""),
            "Schema Types": ", ".join(signals.get("schema_types", [])),
            "JSON-LD Count": signals.get("json_ld_count", ""),
            "Word Count": signals.get("word_count", ""),
            "Internal Link Count": signals.get("internal_link_count", ""),
            "External Link Count": signals.get("external_link_count", ""),
            "Image Count": signals.get("image_count", ""),
            "Images Missing Alt Count": signals.get("images_missing_alt_count", ""),
            "FAQ-like Questions": "\n".join(signals.get("faq_like_questions", [])),
            "Visible Trust Terms": ", ".join(signals.get("visible_trust_terms", [])),
        }
    ])

    headings_data = []
    for heading_level, headings in signals.get("headings", {}).items():
        for heading in headings:
            headings_data.append({
                "Heading Level": heading_level.upper(),
                "Heading Text": heading
            })

    headings_df = pd.DataFrame(headings_data)

    internal_links_df = pd.DataFrame(signals.get("sample_internal_links", []))

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        audit_df.to_excel(writer, index=False, sheet_name="Detailed Audit")
        signals_df.to_excel(writer, index=False, sheet_name="Page Signals")
        headings_df.to_excel(writer, index=False, sheet_name="Headings")
        internal_links_df.to_excel(writer, index=False, sheet_name="Internal Links")

        workbook = writer.book

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"

            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    try:
                        cell_value = str(cell.value) if cell.value is not None else ""
                        max_length = max(max_length, len(cell_value))
                    except Exception:
                        pass

                adjusted_width = min(max_length + 2, 60)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    return output.getvalue()


def display_results(results, signals):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Weighted Score", results.get("total_weighted_score", 0))

    with col2:
        st.metric("Max Score", results.get("max_possible_score", 0))

    with col3:
        st.metric("AI Readiness", f'{results.get("readiness_percentage", 0)}%')

    st.subheader("Executive Summary")
    st.write(results.get("executive_summary", ""))

    st.subheader("Maturity Level")
    st.info(results.get("maturity_level", ""))

    st.subheader("Top Priorities")
    for priority in results.get("top_priorities", []):
        st.write(f"- {priority}")

    st.subheader("Detailed Audit")

    audit_rows = results.get("audit", [])

    for row in audit_rows:
        with st.expander(
            f'{row.get("category", "")} — {row.get("item", "")} '
            f'({row.get("score", 0)}/5)'
        ):
            st.write(f'**Priority:** {row.get("priority", "")}')
            st.write(f'**Weighting:** {row.get("weighting", "")}')
            st.write(f'**Weighted score:** {row.get("weighted_score", "")}')
            st.write(f'**Evidence:** {row.get("evidence", "")}')
            st.write(f'**Recommendation:** {row.get("recommendation", "")}')

    st.subheader("Export Audit")

    excel_file = create_excel_export(results, signals)

    st.download_button(
        label="Download Excel Audit",
        data=excel_file,
        file_name="ai_optimisation_audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


st.title("AI Optimisation Audit Checklist")
st.write("Enter a website URL and the app will audit the page automatically.")

url_input = st.text_input(
    "Website URL",
    placeholder="https://www.example.com/product-page"
)

run_button = st.button("Run AI Audit")

if run_button:
    if not url_input:
        st.warning("Please enter a URL.")
        st.stop()

    url = normalise_url(url_input)

    with st.spinner("Fetching page and extracting SEO signals..."):
        try:
            page = fetch_page(url)
            signals = extract_page_signals(
                html=page["html"],
                url=page["url"],
                status_code=page["status_code"],
                ttfb_seconds=page["ttfb_seconds"],
            )
        except requests.exceptions.RequestException as error:
            st.error(f"Could not fetch the URL: {error}")
            st.stop()

    st.subheader("Extracted Page Signals")

    with st.expander("View extracted signals"):
        st.json(signals)

    with st.spinner("Running AI audit..."):
        client = get_openai_client()
        results = run_ai_audit(client, signals, CHECKLIST)

    display_results(results, signals)
