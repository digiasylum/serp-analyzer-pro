# SERP V7 - SEO Intelligence Toolkit

SERP V7 is an all-in-one SEO and marketing intelligence tool built with Streamlit. It helps marketers, SEO teams, content writers, and business owners analyze live Google SERP data, understand competitor content, plan topical authority, inspect URLs, and track keyword rankings from one simple dashboard.

Built by DigiAsylum, the tool uses SerpAPI and on-page scraping to turn search results into actionable SEO insights.

## What It Does

SERP V7 helps you understand what is ranking, why it is ranking, and how to improve your own pages. It combines SERP analysis, competitor benchmarking, content grading, local SEO checks, URL inspection, and position tracking into one workflow.

## Main Features

### SERP Analyzer

Analyze live Google search results for any keyword. The SERP Analyzer detects search intent, SERP features, AI Overview signals, related keywords, People Also Ask questions, top ranking URLs, headings, semantic terms, and content patterns from ranking pages.

### Topical Authority Planner

Build a practical topical map from SERP data. This module suggests pillar pages, supporting pages, FAQ topics, long-tail opportunities, content clusters, and internal linking ideas to strengthen topical coverage.

### Local Pack Analyzer

Review local search visibility and Google Business Profile signals. The Local Pack module detects local pack presence, extracts top local competitors, reviews business listing details, and suggests local optimization improvements.

### Competitor Score

Benchmark top-ranking pages against content quality signals. It reviews competitor word count, readability, heading structure, keyword usage, tone, writing style, and content depth so you can understand what your page needs to compete.

### Content Grader

Grade your own content with a 0-100 score. The grader checks readability, word count, keyword inclusion, content quality, and publish readiness. When SERP data is available, it also compares your draft against live competitors.

### URL Inspector

Inspect any webpage for SEO and technical content signals. The URL Inspector extracts title tags, meta descriptions, canonical tags, robots meta, Open Graph data, schema markup, headings, internal links, external links, and full page text.

### Position Tracking

Track where your website ranks for one or multiple keywords in a single run. The tracker checks exact URL and domain-level matches across the selected SERP depth, captures SERP signals, checks AI Overview presence, logs history, and supports backlink gap discovery.

### Backlink Scout

Scan competitor pages for external domains that may represent link-building opportunities. Backlink Scout highlights domains linking to competitors but not to your target site, helping prioritize outreach.

## Why Use SERP V7

- Understand live SERP behavior before creating or updating content
- Find what top-ranking pages have in common
- Discover content gaps and keyword opportunities
- Build topical authority plans from real search data
- Improve local SEO visibility
- Inspect technical and content signals from any URL
- Track multiple keyword positions in one workflow
- Export useful SEO data for reporting and planning

## Best For

- SEO professionals
- Content marketers
- Digital marketing agencies
- Local businesses
- Bloggers and publishers
- Founders and growth teams
- Anyone planning search-focused content

## Installation

Follow these steps to run SERP V7 locally in VS Code.

### 1. Download or Clone the Project

Download this repository to your computer, or clone it from GitHub. Open the project folder in VS Code.

### 2. Open the VS Code Terminal

In VS Code, open the terminal from:

Terminal > New Terminal

Make sure the terminal is opened inside the SERP V7 project folder.

### 3. Create a Virtual Environment

For Windows:

```bash
python -m venv venv
```

For macOS or Linux:

```bash
python3 -m venv venv
```

### 4. Activate the Virtual Environment

For Windows PowerShell:

```bash
venv\Scripts\Activate.ps1
```

For Windows Command Prompt:

```bash
venv\Scripts\activate.bat
```

For macOS or Linux:

```bash
source venv/bin/activate
```

### 5. Install Required Packages

```bash
pip install -r requirements.txt
```

### 6. Run the App Locally

```bash
streamlit run app.py
```

After running the command, Streamlit will open the app in your browser. If it does not open automatically, visit:

```text
http://localhost:8501
```

## SerpAPI Key

SERP V7 requires a SerpAPI key to fetch live Google SERP results.

Create a free SerpAPI account here:

https://serpapi.com/users/sign_up

After signing up, copy your private API key from your SerpAPI dashboard/account area and paste it into the app sidebar under `SerpAPI Key`, then click `Authenticate`.

You can also learn more about SerpAPI here:

https://serpapi.com/


## Data Source

SERP V7 uses SerpAPI for live Google SERP data and combines it with webpage scraping and content analysis to generate insights. A SerpAPI key is required to fetch live search results.

## Project Status

This project is ready for GitHub use as a Streamlit-based SEO intelligence dashboard.
