<div align="right">
  <a href="README.md">English</a>
</div>

# 🔗 Link Checker & AI Content Verifier
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://link-checker-app-ebwus)

## 📌 1. 這是什麼應用程式？
這是一個專為自動化簡報內容審核而設計的網頁應用程式與程式庫。

**主要功能：**
*   **上傳 PPT：** 匯入您的 PowerPoint 檔案 (.pptx)。
*   **萃取連結：** 自動掃描並提取投影片中嵌入的所有超連結及其前後文。
*   **AI 驗證：** 利用 AI (DeepSeek / LLM) 將簡報中的上下文與抓取到的網頁實際內容進行語意比對。它能自動檢查網頁內容是否與 PPT 上下文吻合，或判斷連結是否已失效。

---

## 🚀 2. 如何使用

要執行此應用程式，您需要準備兩組 API 金鑰：一組用於 **Apify**（負責網頁爬蟲），另一組用於 **LLM 供應商**（負責 AI 語意比對）。

### 步驟 1：萃取 PPT 連結 (Extract PPT Links)
*   **上傳檔案：** 上傳您的 PowerPoint 檔案（最高支援 200 MB）。系統會自動提取所有內部超連結及相關文字上下文。
*   **檢查與編輯：** 萃取完成後，您可以在畫面上預覽結果表格。如有需要，您可以下載 Excel 檔案進行手動編輯，再用於後續步驟。

### 步驟 2：API 與模型設定 (API & Model Configuration)
您必須設定爬蟲與 AI 模型的 API 金鑰才能繼續。

**第一部分：取得 Apify API Token (用於網頁爬蟲)**
1.  **註冊/登入：** 前往 [Apify 官方網站](https://apify.com/) 註冊一個新帳號並完成登入。
2.  **設定頁面：** 登入後，點擊左側選單底部的 **Settings（設定）**。
3.  **整合標籤：** 在設定頁面中，找到並點擊 **Integrations（整合）** 選項。
4.  **複製 Token：** 找到您的 **Personal API Token**（即 API Key）。點擊右側的 "Copy" 按鈕進行複製。
5.  **輸入系統：** 將複製的 Token 貼到應用程式的 `APIFY_API_TOKEN` 欄位中。
    *   *註：每個 Apify 免費帳號每個月皆享有 $5 美元的免費額度。*

![Apify 介面](Apify.png)

**第二部分：取得 LLM API 金鑰 (兩種推薦方式)**

**方式 1：使用 DeepSeek (依用量計費，極度平價)**
1.  **前往平台：** 打開瀏覽器，前往 [DeepSeek 開發者平台](https://platform.deepseek.com/)。
2.  **註冊/登入：** 使用電子信箱或 Google 帳號快速註冊並登入。
3.  **金鑰管理：** 進入開發者控制台後，點擊左側或右側選單的 **API Keys**。
4.  **建立金鑰：** 點擊 **Create new API key**，為金鑰命名（例如 `MyTestKey`）後確認。
5.  **妥善保存：** 畫面會跳出一串以 `sk-` 開頭的金鑰。*請立刻點擊複製並安全保存，因為它只會完整顯示這一次。*
6.  **帳戶儲值：** DeepSeek 採預付費制，新帳號請至 "Top Up"（儲值）頁面充值最低 $2 美元。*(預估成本：檢查 120 筆連結約只需 $0.1 美元)*。
7.  **在系統中設定：**
    *   **供應商：** 選擇 `DeepSeek`
    *   **API Key：** 貼上您剛複製的金鑰。
    *   **模型名稱 (Model Name)：** 輸入 `deepseek-v4-flash` (推薦)。
    *   **Base URL：** 輸入 `https://api.deepseek.com`

![DeepSeek 介面](Deepseek.png)

**方式 2：使用 OpenRouter (提供免費方案)**
1.  **前往平台：** 打開瀏覽器，前往 [OpenRouter 官方網站](https://openrouter.ai/)。
2.  **註冊/登入：** 點擊右上角的 **Sign In** 或 **Get Started**，可使用 Google、GitHub 帳號快速登入。
3.  **金鑰管理：** 進入控制台的 **API Keys** 頁面。
4.  **建立金鑰：** 點擊 **Create Key**，命名後確認。
5.  **妥善保存：** 複製以 `sk-or-v1-` 開頭的金鑰。*請立即妥善保存。*
6.  **速率限制：** 
    *   *免費帳戶：* 每天最多只能檢查 **50 筆連結**。
    *   *付費解鎖：* 若您一次性儲值 $10 美元，該帳號的免費模型額度將永久提升至 **每天 1000 筆請求**。(參考資料：[OpenRouter 常見問答](https://openrouter.ai/docs/faq#how-are-rate-limits-calculated))。
7.  **在系統中設定：**
    *   **供應商：** 選擇 `OpenRouter`
    *   **API Key：** 貼上您剛複製的金鑰。
    *   **模型名稱 (Model Name)：** 輸入 `openrouter/free` (免費模型推薦)。
    *   **Base URL：** 輸入 `https://openrouter.ai/api/v1`

![OpenRouter 介面](OpenRouter.png)

### 步驟 3：爬取網頁內容 (Scrape Web Content)
*   **輸入資料：** 系統預設會直接使用 **步驟 1** 萃取出來的 Excel 檔案進行爬蟲。
*   **自訂上傳：** 您也可以取消勾選預設值，上傳您手動編輯過的 Excel 檔案。*(注意：上傳的 Excel 檔案必須包含精確命名為 `Link_URL` 的欄位)*。
*   **執行：** 點擊 **Start Web Scraper**，爬蟲程式即會開始抓取目標網址的真實內容。
    *   *(注意：爬取過程可能需要一些時間。若您看到畫面右上角出現「正在奔跑的小人」圖示，代表系統正在背景正常載入與執行中，並非當機卡住，請耐心等候。)*

### 步驟 4：AI 語意檢核 (AI Semantic Check)
*   **輸入資料：** 系統預設會使用 **步驟 3** 產生的爬蟲結果檔案。
*   **提示詞設定 (Prompt)：** 您可以在文字框中編輯 AI Prompt，明確定義「相符 (match)」與「不符 (mismatch)」的標準。
    *   **極度重要：** 您的 Prompt **必須** 包含 `{context}`（用於插入 PPT 擷取的前後文）與 `{content}`（用於插入爬蟲抓取的網頁內容）這兩個變數標籤。系統會在每一筆迴圈中自動將內容填入這兩個變數供 AI 判讀。
*   **執行：** 點擊 **Start AI Verification**，稍候片刻，即可下載最終檢核完畢的 Excel 報告！

---

## ⚠️ 3. 限制與平台支援狀態
*   **通用限制：** 無法檢查圖片內的超連結，也無法驗證動態數據（如粉絲數、即時日期等）。
*   **支援平台 (截至 2026 年 8 月 25 日)：** Instagram, Threads, 小紅書 (Xiaohongshu), WeChat, HK01。
*   **不支援平台：** Facebook, 抖音 (Douyin)。
*   **極度不穩定：** 香港討論區 (Discuss.com), 微博 (Weibo)。