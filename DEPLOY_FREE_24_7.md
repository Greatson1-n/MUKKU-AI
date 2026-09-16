# 🚀 Deploy MUKKU.AI 100% Free & 24/7 (No Credit Card Required)

This guide walks you through deploying **MUKKU.AI** as a live, public website with **24/7 uptime** without paying anything or entering any credit card.

---

## 🏛️ Architecture Overview

| Part | Service | Purpose | Cost & Card |
| :--- | :--- | :--- | :--- |
| **Frontend** | [Vercel](https://vercel.com) | Ultra-fast global CDN for the React UI | **$0 / No card** |
| **Backend** | [Render](https://render.com) | Runs FastAPI, SQLite, RAG search & memories | **$0 / No card** |
| **AI Brain** | [Groq Cloud](https://console.groq.com) | Ultra-fast LPU inference (Qwen 2.5 32B / LLaMA 3.1) | **$0 / No card** |
| **Keep-Alive** | [cron-job.org](https://cron-job.org) | Pings backend every 10 min so it never sleeps | **$0 / No card** |

> [!NOTE]
> **Your local setup is preserved**: Running `start.bat` or `start.ps1` at home will still use your local Ollama `qwen2.5:3b` engine. The cloud configuration only activates when deployed to Render.

---

## Step 1: Get your Free Groq API Key (60 Seconds)

1. Go to **[console.groq.com](https://console.groq.com/)**.
2. Sign in with your Google or GitHub account (no credit card requested).
3. In the left sidebar, click **API Keys**.
4. Click **Create API Key**, name it `mukku-cloud`, and click **Create**.
5. **Copy the key** (it looks like `gsk_...`) and save it somewhere temporary.

---

## Step 2: Push your Project to GitHub

If your code is not already on GitHub:

1. Create a new repository on [github.com](https://github.com) (can be **Public** or **Private**).
2. In your terminal inside `MUKKU.AI`:
   ```bash
   git init
   git add .
   git commit -m "MUKKU.AI cloud deployment ready"
   git branch -M main
   git remote add origin https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git
   git push -u origin main
   ```

---

## Step 3: Deploy Backend on Render (Free)

1. Go to **[render.com](https://render.com/)** and sign up/log in with GitHub (no card needed).
2. Click the blue **New +** button in the top right and select **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your `MUKKU.AI` repository.
4. Fill in the settings:
   - **Name:** `mukku-backend` (or any name you like)
   - **Region:** Choose whatever is closest to you (e.g. *Singapore*, *Oregon*, or *Frankfurt*)
   - **Branch:** `main`
   - **Root Directory:** *(leave blank)*
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install -r backend/requirements.txt
     ```
   - **Start Command:**
     ```bash
     python backend/run.py
     ```
   - **Instance Type:** Select **Free** (0.5 CPU, 512 MB RAM).
5. Scroll down to **Environment Variables** and add the following:
   - `LLM_PROVIDER` = `groq`
   - `GROQ_API_KEY` = *(paste your `gsk_...` key from Step 1)*
   - `GROQ_MODEL` = `qwen-2.5-32b`
   - `PYTHON_VERSION` = `3.11.9`
6. Click **Create Web Service**.
7. Wait 2–3 minutes for the build to finish. Once it says **Live**, copy your Render backend URL (e.g. `https://mukku-backend.onrender.com`).

> [!TIP]
> Test it in your browser by visiting `https://your-backend.onrender.com/api/health`. You should see `{"status":"healthy","provider":"groq","ollama_host":"Groq Cloud"}`.

---

## Step 4: Deploy Frontend on Vercel (Free)

1. Go to **[vercel.com](https://vercel.com/)** and sign up/log in with GitHub (no card needed).
2. Click **Add New...** ➔ **Project**.
3. Select your `MUKKU.AI` GitHub repository and click **Import**.
4. In the configuration screen:
   - **Framework Preset:** `Vite` (detected automatically).
   - **Root Directory:** Click **Edit** and select **`frontend`**.
5. Expand **Environment Variables** and add:
   - **Name:** `VITE_API_BASE`
   - **Value:** `https://your-backend.onrender.com/api` *(replace with your actual Render URL from Step 3, with `/api` at the end)*
6. Click **Deploy**.
7. In ~40 seconds, your site will be live! Vercel will give you a public link like `https://mukku-ai.vercel.app`.

---

## Step 5: Keep it Awake 24/7 with cron-job.org (Free)

Because Render puts free services to sleep after 15 minutes of inactivity, we use a free ping service to keep it awake 24/7:

1. Go to **[cron-job.org](https://cron-job.org/)** and register a free account.
2. In the dashboard, click **Create Cronjob**.
3. Fill in:
   - **Title:** `Keep MUKKU Alive`
   - **URL:** `https://your-backend.onrender.com/api/health`
   - **Schedule:** Select **Every 10 minutes**.
4. Click **Create**.

**That’s it!** `cron-job.org` will send a tiny ping every 10 minutes, keeping your Render backend warm 24/7 so visitors never experience startup delays.

---

## 🎉 Done!
Your MUKKU.AI assistant is now:
- Hosted 24/7 in the cloud.
- 100% free with zero recurring costs.
- Powered by Qwen 2.5 via Groq LPUs for instant responses.
- Capable of web search, memory, safe math, voice recognition, and document chat.
