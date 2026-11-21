# Seranews · The Liquid Briefing

**Your news. Your perspective. Your daily briefing.**

Seranews turns a busy news feed into a personal, source-linked podcast. Choose what matters to you, discover stories one card at a time, and listen to a briefing in your preferred language—with the original reporting always within reach.

Built for the **Seranews challenge at MAIN AI Hackathon 2026**. News data is provided by **Newstex**.

## The experience

- **Personalize once, refine as you go.** Combine interests, tune topic priorities, import a stock watchlist and choose your article languages, narration language, depth and approximate listening length.
- **Discover without losing your place.** A native, vertically snapping feed keeps each image, headline and controls together. Thumbs-up/down adjusts the future topic mix while the current deck stays in order.
- **Follow the reporting.** Open summaries, original language editions and source links. AI-translated summaries are labeled. Supporting reports are distinguished from related coverage.
- **Listen naturally.** Two-host sample conversations and connected natural narration produce one continuous recording with measured chapter boundaries. Selecting a chapter seeks to the corresponding story; skipping pauses until you press Play.
- **Remember what matters.** Search reading history and saved stories. Catch-up compares previously seen story versions and content to identify possible developments without another AI call.
- **Keep control.** Change playback speed, set a sleep timer, stop at the end of an episode, or delete audio while retaining its readable brief and sources.
- **Make it yours.** Four coordinated themes—Signal, Cobalt, Edition and Afterhours—each have light and dark modes, live previews and local persistence.

The repository includes **six approximately five-minute sample podcasts, 57 spoken news summaries and 24 voice previews**. Replaying these recordings requires no API key. The organizer's source dataset must still be prepared locally before running the full app.

## A quick judging walkthrough

1. Start with **Mila** and play her Dutch sample; switch to **Jonas** to compare a German investor's briefing.
2. Open **Discover**, give a story feedback, then check the updated interests in **Preferences & schedule**. Return to the source-linked story and inspect its reporting.
3. Save a story, find it in **History**, and explore the history-aware catch-up section on Today.
4. Choose **New listener** to demonstrate onboarding from a blank profile. Set interests, languages, voices, listening length and schedule.
5. Explore **Podcasts**: jump between chapters, change speed, set the sleep timer and keep a summary while removing its audio.
6. Finish with **Appearance** and the three-plan comparison.

| Demo listener | Starting perspective | Default plan |
|---|---|---|
| Mila | Dutch investor · Dutch narration | Horizon |
| Jonas | German investor · German narration | Horizon |
| Alex | FX trader · English narration | Horizon |
| Sam | General news · English narration | Horizon |
| Free user | Basic-voice sample · English | Free |
| Medium user | Technology and investing · English | Flow |
| New listener | Unidentified; no preloaded interests or episode | Free |

The four required listener types are starting points, not fixed classifications. Names and detailed presets are demo choices.

## How it works

Prepare the shared news catalog when reporting arrives. Compose an edition when a listener asks for it—or during the preparation window before their scheduled listening time.

| Layer | Responsibility | Implementation |
|---|---|---|
| News preparation | Import the six feeds, preserve language editions, assign tags and retain source evidence | Python; local catalog and article store; optional n8n News Desk |
| Personalization and application | Preferences, reversible multi-tag feedback, stable feed order, history, quotas and durable jobs | FastAPI, Pydantic, SQLite, React, TypeScript |
| Cloud orchestration | Advisory ranking, script drafting, evidence review and natural narration | Four n8n workflows; OpenAI; ElevenLabs |
| Listening | Combined recordings, reusable chapter audio, measured seeking, playback speed and sleep timer | Native browser audio; local media; Basic speech fallback |

If the writer is temporarily rate limited, the demo can use its reviewed summaries and labels that fallback. If a computer lacks a matching system voice, unchanged demo stories can reuse the included Basic recordings. Reuse checks the source IDs and summary text; it does not attach stale audio to changed reporting.

## Run locally

**Requirements:** Python **3.12+**, Node.js **22.12+** with npm, and an authorized copy of `liquid-briefing-data.zip` from the organizers. The licensed dataset and source article database are not included in Git.

On Windows, open PowerShell in the repository folder:

```powershell
.\start-demo.ps1 -DatasetZip 'C:\path\to\liquid-briefing-data.zip'
```

This creates the Python environment, installs dependencies, restores image assets, builds the frontend and starts the API and worker. Open **http://127.0.0.1:8000**. Keep the terminal open; Ctrl+C stops both processes.

After initial setup, use `Launch-Seranews.cmd` or:

```powershell
.\start-demo.ps1 -SkipInstall
```

For manual setup on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
python -m backend.prepare /path/to/liquid-briefing-data.zip
npm run build
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Run `python -m backend.worker` in a second terminal with the same environment activated. Development mode uses `npm run dev` and the API on port 8000. After pulling changes, rebuild the frontend and restart the backend and worker.

### Optional live generation

Sample playback works locally. New cloud-generated editions require your own configured n8n connection and provider credentials. Store OpenAI and ElevenLabs credentials **inside n8n**, never in frontend code. Each installation needs its own signing-key configuration; the original team's private connection is not distributed.

See the [live integration guide](docs/live-integration.md), [workflow exports](workflows/live/README.md) and [news intake guide](docs/news-intake.md).

## Prototype boundaries

- This is a **November 19, 2026 dataset replay**, not a live public news service. Creation dates use the real clock; news coverage dates remain separate.
- Demo profile switching is not production authentication. Free, Flow and Horizon demonstrate proposed allowances; prices are placeholders. Billing, ad serving and push notifications are not connected.
- Scheduled preparation requires the local worker to remain running. It is not a phone alarm or background mobile push service.
- Source review checks traceability to the supplied reporting. It does not independently establish that a publisher's claims are true. Full-dataset cross-outlet grouping has not been validated against the organizer's answer key.
- This is a mobile-shaped browser prototype, not a packaged iOS/Android release. Spoken summaries are an accessibility foundation, not a claim of complete accessibility compliance.

## Security and data

Provider credentials, `.env`, private signing keys, local cloud configuration, article databases and personal listening data are excluded from Git. Published workflow credential names, voice IDs, source article IDs and signature-verification **public keys** are identifiers, not API keys.

Read the [security audit and reporting guidance](SECURITY.md) for the checked commit, scope and limitations.

The organizer dataset is licensed for this hackathon only: do not redistribute its files or full article text, and delete local dataset copies after the event. Short source quotations and links are permitted by its README. Included demo summaries and recordings do not grant broader reuse rights to the underlying reporting, publisher imagery or partner branding.

## More detail

- [Complete feature inventory](ALL_FEATURES.md)
- [Submission description](docs/PROJECT_DESCRIPTION.md)
- [Challenge readiness and remaining limitations](docs/challenge-readiness.md)
- [Podcast-writing guidance](skills/seranews-podcast-writer/SKILL.md)
- [Cost model and measured evidence](docs/cost-model.md)
- [2:30 presentation storyboard](docs/presentation-video/STORYBOARD.md)
- [Presentation narration and editing pack](presentation-audio/README.md)
