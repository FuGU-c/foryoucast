# 📰→🎙️ ForYouCast — news in, podcast out

> A personal, **source-linked** news briefing, delivered as a podcast.
> Built in **a day** for **an AI hackathon** 🏁 — it didn't make the finals, but the logic is solid and the bones are good. This is the version *after* the hackathon dust settled.

https://github.com/user-attachments/assets/f6e76536-7cc4-4b8e-88c9-544758387995

> ⚠️ Heads-up: the video may look glitchy or have odd patches in places — the business name and the dataset topic it was about were censored out after recording.

---

## ✨ The idea

Pick what matters to you — interests, languages, voices, wake-up time — and a **daily podcast briefing** is prepared before you open your eyes. Every story stays **source-linked** 🔗: the summary is never more than one tap away from the original reporting.

The demo replays a **1,740-article corpus in three languages** (English, Dutch, German) and includes **6 ready-made ~5-minute sample podcasts, 57 spoken summaries and 24 voice previews** — replayable with **no API key** 🎧.

## 🧩 Three distinctive features

### 1. 🫂 A social-style "For you" page — for news *and* podcasts
A feed that behaves like the social apps you know, but for journalism. You arrange the stats behind the scenes — they control **how much news you get from each category**. Thumbs-up/down feeds the algorithm, so a feedback loop keeps re-personalising everything — your feed **and your podcast episodes themselves**: length, depth, topics, voices — constantly.

### 2. ⚙️ Four live n8n workflows run the whole backend
News desk · Podcast studio · Natural narration · Personal radar. News is **continuously processed, tagged, translated and reviewed** behind the curtain, and **podcasts are pre-prepared for the exact time each listener requested**. The workflows run in the cloud but are **swappable — point them at your own server** and keep the app.

### 3. 💰 A pricing model with real feature lines
**Free / Flow / Horizon** — daily podcast allowances, length caps, natural-vs-basic voices, AI translations and ad placement actually differ per tier, not just "more of the same".

## ⚙️ Under the hood — what it actually does

- 📥 **Intake:** drop licensed article JSONL into `data/incoming/` → auto-imported, deduplicated, tagged, translation-linked
- 🧪 **Two-model editorial line:** GPT-6 Luna prepares, GPT-6.1 Sol reviews evidence & translation fidelity — then the backend re-validates **exact quotes, source IDs and numbers** before anything publishes
- 🎙️ **Podcast studio:** a two-host dialogue (Maya & Leo) with logical chapter ordering — sources named aloud, no invented quotes; one MP3 with **measured chapter markers**
- 🔊 **Voices:** 24 natural-voice samples (8 per language), pick two per language with previews — Microsoft TTS as the free layer, ElevenLabs premium
- ⏰ **Scheduler:** timezone-aware, starts preparation ≤30 min before your listening time — durable SQLite jobs, retries and generation allowances survive restarts
- 🕰️ **Catch-up without AI:** "Since your last visit" detects follow-ups on stories you already read/heard — purely local, zero tokens
- 🛡️ **Security:** Ed25519-signed webhook intake with expiry checks; no API keys anywhere in the public code; your private database never gets a public tunnel
- 🧠 **Easy to re-price:** because the hackathon sponsors gave free credits, the stack leans on ElevenLabs + GPT-6 models — swap in cheaper models (e.g. **GLM 5.3** with a well-written skill + Microsoft TTS) or your **own models**; the orchestration doesn't care

## 🧱 The stack

**React + TypeScript + Vite** frontend · **FastAPI + SQLite** backend · **Python worker + ffmpeg** for audio assembly · **n8n** orchestration · **OpenAI** writing & review · **ElevenLabs** narration.

## 🔮 Where it could go

- 🏡 **A self-hosted news app** — good UI, sensible logic, high potential to be polished, add more news sources, and run on your own box.
- 🤖 **Make it *yours* with AI** — the codebase is compact and readable: point an AI assistant at it and reshape the feed, sources, voices and pipeline into your own homelab news-to-podcast service.
- 💼 **A sellable platform** — possible, but that route needs a *lot* more polish.

## 📄 License — AGPL-3.0

🍴 Fork it, build your own version, self-host it! Under **AGPL-3.0**, anyone serving this app to users must keep their version open-source too ✨ Want to run it **closed-source in a commercial product** instead? Then reach out to me 📬 Full terms in [LICENSE](LICENSE).
