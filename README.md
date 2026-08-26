<div align="right">
  <a href="README.zh.md">繁體中文</a>
</div>

# 🔗 Link Checker & AI Content Verifier
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://link-checker-app-ebwus)

## 📌 1. What is this app?
This web application and repository are designed to automate presentation content auditing. 

**Main Purpose:**
*   **Upload PPT:** Input your PowerPoint file (.pptx).
*   **Extract Links:** Automatically scan and extract all hyperlinks embedded in the slides, along with their surrounding text context.
*   **AI Verification:** Use AI (DeepSeek / LLM) to compare the presentation context with the live scraped content from each link. It automatically checks whether the website content matches the PPT context, or if the link is expired/invalid.

---

## 🚀 2. How to Use

To run this application, you will need two API keys: one for **Apify** (to scrape web content) and one for an **LLM Provider** (to perform the semantic check). 

### Step 1: Extract PPT Links
*   **Upload:** Upload your PowerPoint file (supports up to 200 MB). The app will automatically extract all internal hyperlinks and the surrounding text context.
*   **Review:** Once the extraction is complete, you can review the results table on the screen. If necessary, download the Excel file, edit it manually, and use it for the next steps.

### Step 2: API & Model Configuration
You must configure your API keys for the scraper and the AI model to proceed. 

**Part A: Get the Apify API Token (For Web Scraping)**
1.  **Register/Login:** Go to the [Apify Website](https://apify.com/) and create a new account or log in.
2.  **Settings:** Navigate to the **Settings** menu at the bottom of the left sidebar.
3.  **Integrations:** Click on the **Integrations** tab.
4.  **Copy Token:** Locate your **Personal API Token**. Click the "Copy" button.
5.  **Configure:** Paste this token into the `APIFY_API_TOKEN` field in the app. 
    *   *Note: Each Apify free account receives $5 USD in free usage credits every month.*

![Apify Interface](images/Apify.png)

**Part B: Get the LLM API Key (Two Recommended Methods)**

**Method 1: Using DeepSeek (Paid per usage, highly affordable)**
1.  **Platform:** Go to the [DeepSeek Developer Platform](https://platform.deepseek.com/).
2.  **Login/Register:** Sign in with your email or Google account.
3.  **API Keys:** Navigate to the **API Keys** management page from the dashboard menu.
4.  **Create Key:** Click **Create new API key**, give it a recognizable name (e.g., `MyTestKey`), and confirm.
5.  **Save Key:** Copy the generated key (starting with `sk-`). *Save it immediately, as it will only be shown once.*
6.  **Top Up:** DeepSeek is a prepaid service. Go to the "Top Up" page and add a minimum of $2 USD. *(Estimated cost: ~ $0.10 USD per 120 links).*
7.  **Configure in App:**
    *   **Provider:** Select `DeepSeek`
    *   **API Key:** Paste your copied key.
    *   **Model Name:** Type `deepseek-v4-flash` (recommended).
    *   **Base URL:** Type `https://api.deepseek.com`

![DeepSeek Interface](images/Deepseek.png)

**Method 2: Using OpenRouter (Free tier available)**
1.  **Platform:** Go to the [OpenRouter Website](https://openrouter.ai/).
2.  **Login/Register:** Click **Sign In** or **Get Started** using Google, GitHub, or Email.
3.  **API Keys:** Navigate to the **API Keys** management page.
4.  **Create Key:** Click **Create Key**, name it, and confirm.
5.  **Save Key:** Copy the generated key (starting with `sk-or-v1-`). *Save it immediately in a secure place.*
6.  **Rate Limits:** 
    *   *Free Users:* Limited to checking **50 links per day**.
    *   *Paid Users:* If you top up $10 USD once, your free model rate limit is permanently increased to **1000 requests per day**. (Reference: [OpenRouter FAQ](https://openrouter.ai/docs/faq#how-are-rate-limits-calculated)).
7.  **Configure in App:**
    *   **Provider:** Select `OpenRouter`
    *   **API Key:** Paste your copied key.
    *   **Model Name:** Type `openrouter/free` (recommended for free usage).
    *   **Base URL:** Type `https://openrouter.ai/api/v1`

![OpenRouter Interface](images/Openrouter.png)

### Step 3: Scrape Web Content
*   **Input Data:** By default, the app will use the extracted links Excel file generated in **Step 1**. 
*   **Custom Upload:** Alternatively, you can uncheck the default option and upload a custom, edited Excel file. *(Note: The uploaded Excel file MUST contain a column named exactly `Link_URL`)*.
*   **Execute:** Click **Start Web Scraper** to begin fetching the live content from the target URLs. 
    *   *(Note: This process may take some time. If you see a "running person" icon in the top right corner of the screen, it indicates that the system is loading and processing normally in the background. It is not stuck or frozen, so please wait patiently.)*

### Step 4: AI Semantic Check
*   **Input Data:** By default, the app uses the scraped checkpoint Excel file generated in **Step 3**.
*   **Prompt Engineering:** You can edit the AI Prompt in the provided text area to define exactly what constitutes a "match" or "mismatch" for your specific use case.
    *   **CRITICAL:** Your prompt **must** include the variables `{context}` (to insert the PPT preceding context) and `{content}` (to insert the scraped web post content). The system will automatically inject the corresponding text for each link into these placeholders.
*   **Execute:** Click **Start AI Verification**. Wait for the process to finish, and download your final audited report!

---

## ⚠️ 3. Limitations & Platform Support
*   **General:** Cannot check links inside images or verify dynamic metrics (follower counts, dates).
*   **Supported (as of Aug 25, 2026):** Instagram, Threads, Xiaohongshu (XHS), WeChat, HK01.
*   **Not Supported:** Facebook, Douyin.
*   **Unstable:** Discuss.com, Weibo.