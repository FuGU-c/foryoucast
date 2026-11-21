# 📰→🎙️ Seranews — news in, podcast out

> A personal, **source-linked** news briefing, delivered as a podcast.
> Built in **2 days** for **an AI hackathon** 🏁 — it didn't make the finals, but the logic is solid and the bones are good. This is the version *after* the hackathon dust settled.

🎬 **[Watch the pitch video — plays right in the browser](https://github.com/FuGU-c/seranews/releases/download/v1.0/pitch_video.mp4)** (2.5 min)
> ⚠️ Heads-up: the video may look glitchy or have odd patches in places — the business name and the dataset topic it was about were censored out after recording.

---

## ✨ The idea

Pick what matters to you — interests, languages, voices, wake-up time — and a **daily podcast briefing** is prepared before you open your eyes. Every story stays **source-linked** 🔗: the summary is never more than one tap away from the original reporting.

The repo includes **6 ready-made ~5-minute sample podcasts, 57 spoken news summaries and 24 voice previews** — replayable with **no API key** 🎧 (running the full app still needs a news dataset prepared locally).

## 🧩 Three distinctive features

### 1. 🫂 A social-style "For you" page — for news
A feed that behaves like the social apps you know, but for journalism. You arrange the stats behind the scenes — they control **how much news you get from each category**. Thumbs-up/down feeds the algorithm, so a **feedback loop keeps re-personalising** your briefing, constantly.

### 2. ⚙️ An n8n workflow that runs the whole backend
Everything happens behind the curtain: news is **continuously processed, tagged, translated**, summaries are written, and **podcasts are pre-prepared for the exact time each listener requested**. The workflow runs in the cloud, but it's **swappable — point it at your own server** and keep the app.

### 3. 💰 A pricing model with real features
Three tiers — **Free / Flow / Horizon** — each with a meaningful feature line-up, not just "more of the same".

## 🧠 The stack (and why it's easy to replace)

- 🔊 **Microsoft TTS** for the free-tier summaries, **ElevenLabs** for premium natural voices — honestly, only because the hackathon sponsors gave free credits 🎁
- 🤖 **GPT-6.1 Sol** for the heavy lifting (review, the big decisions) and **GPT-6 Luna** for the light jobs — translations, tags, and similar chores
- 💡 **In theory** you can swap in cheaper models — e.g. **GLM 5.3** with a well-written skill plus Microsoft TTS — and still get qualified podcasts. Or plug in your **own models** entirely. The orchestration doesn't care.

## 🔮 Where it could go

- 🏡 **A self-hosted news app** — good UI, sensible logic, high potential to be polished, add more news sources, and run on your own box.
- 💼 **A sellable platform** — possible, but that route needs a *lot* more polish.

## 📄 License — AGPL-3.0

Fork it, build your own version, self-host it — **free for everyone**, forever 🍴 Under **AGPL-3.0**, anyone serving this app to users must keep their version open-source too. Want to run it **closed-source in a commercial product** instead? Then reach out for a **commercial license** 📬 — happy to make a reasonable deal. Full terms in [LICENSE](LICENSE).
