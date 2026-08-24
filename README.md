<div align="right">
  <a href="README.zh.md">繁體中文</a>
</div>

# 🔗 Link Checker & AI Content Verifier

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://link-checker-app-3nryd555fp2369ia8dqmca.streamlit.app/)

## 📌 1. What is this app?
This web application and repository are designed to automate presentation content auditing. 

**Main Purpose:**
* **Upload PPT:** Input your PowerPoint file (.pptx).
* **Extract Links:** Automatically scan and extract all hyperlinks embedded in the slides.
* **AI Verification:** Use AI (DeepSeek / LLM) to compare the presentation context with the live scraped content from each link. It checks whether the website content matches the PPT context, or if the link is expired/invalid.

## 🚀 2. How to Use
1. **Step 1:** Upload your PowerPoint file (up to 200 MB) to extract all links.
2. **Step 2:** Review and edit the extracted results table if needed.
3. **Step 3:** Setup your AI prompt. **Important:** Your prompt MUST contain the exact `{context}` and `{content}` placeholder tags.
4. **Step 4:** Run the verification, wait a moment, and download your final report!

## ⚠️ 3. Limitations & Platform Support
* **General:** Cannot check links inside images or verify dynamic metrics (follower counts, dates).
* **Supported (as of Aug 25, 2026):** Instagram, Threads, Xiaohongshu (XHS), WeChat, HK01.
* **Not Supported:** Facebook, Douyin.
* **Unstable:** Discuss.com, Weibo.