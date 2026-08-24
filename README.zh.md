<div align="right">
  <a href="README.md">English</a>
</div>

# 🔗 連結檢查與 AI 內容核對工具

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://link-checker-app-3nryd555fp2369ia8dqmca.streamlit.app/)

## 📌 1. 這個應用程式的用途是什麼？
這個網頁應用程式與專案資料庫旨在自動化簡報內容審查工作：

**主要功能：**
* **上傳簡報：** 匯入 PowerPoint 檔案 (.pptx)。
* **萃取連結：** 自動掃描並提取投影片中的超連結。
* **AI 智慧比對：** 透過 AI (DeepSeek / LLM) 交叉比對簡報內文與網頁抓取內容，檢查是否相符或失效。

## 🚀 2. 如何使用
1. **步驟一：** 上傳簡報（上限 200 MB）以萃取連結。
2. **步驟二：** 檢查並編輯萃取出來的表格。
3. **步驟三：** 設定 AI 提示詞。**重要：** 提示詞中必須包含 `{context}` 與 `{content}` 佔位標籤。
4. **步驟四：** 執行比對並下載最終報告！

## ⚠️ 3. 限制與平台支援狀況
* **一般限制：** 無法檢查圖片中的超連結，無法驗證動態數據。
* **支援平台（截至 2026年8月25日）：** Instagram、Threads、小紅書 (XHS)、微信、HK01。
* **不支援：** Facebook、抖音。
* **不穩定：** Discuss.com、微博。