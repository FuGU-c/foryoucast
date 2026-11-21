# Seranews · The Liquid Briefing

A mobile-first browser demo for **The Liquid Briefing**, built from the supplied Newstex dataset. Prepare the shared news catalog once; compose an edition when a listener asks for it.

## What works in this demo

- Four coordinated themes—Signal, Cobalt, Edition and Afterhours—with Light/Dark modes, illustrated previews and instant device-local persistence. Open Appearance below Subscription in the profile menu.
- History-aware catch-up uses stored reading/listening versions, source links and conservative content similarity. It suppresses unchanged repeats and highlights likely developments without additional AI tokens.
- Seven password-free demo accounts at the top right: Mila (Dutch investor), Jonas (German investor), Alex (FX trader), Sam (general news), Free user, Medium user, and an unidentified New listener. The first four match the supplied listener types; their names and detailed preferences are demo choices. New listener starts without interests or a sample, ready for presentation onboarding.
- Interests and Listening screens with multiple goals, editable topic priorities, original news languages, a separate narration language and custom episode limits. Changes update the profile and feed immediately and sync automatically. The Stock watchlist accepts individual symbols or imported CSV, TSV or TXT lists. Only stock symbols are saved.
- Personalized source-linked editorial stories, immediate upvote/downvote feedback, optional reasons, a compact preference memory, persistent listening history, and “Since you last listened.” Votes update the visible topic mix in Settings and the For You ranking. Each multi-tag story shares a bounded learning change across its tags, with the main tag receiving the strongest influence. Manual interests stay separate from learned adjustments; undoing or reversing a vote restores the corresponding balance, and manual changes override older feedback. Vote buttons switch straight to their final color, while the active card and image stay in place. Rapid actions are reconciled in order; repetition/depth feedback does not reject an entire topic.
- Reading history from the clock-arrow icon to the left of Search. Opened stories, original reports and Discover cards viewed for 1.2 seconds are recorded for the selected profile. Search by headline, source or topic, or filter by recent dates and feedback. Merely viewing a story does not count as liking it.
- Discover has a higher thumb-positioned action rail and an instant Save control below the arrows. History separates Recently viewed and Saved; bookmarks persist per listener and can be searched or removed without changing topic preferences.
- The expanded player has an animated waveform-style seek bar. Its position follows real playback, the motion pauses with audio, and reduced-motion settings are respected. Today prefers the newest recorded edition matching the current preferences, and new editions skip unchanged stories already completed.
- Dated podcast editions with separate creation dates and news coverage dates. New briefings are saved under the actual day of creation, including when an older date filter is selected. Today, This week, This month, All editions and the calendar all group by creation date in Brussels, with Monday-based weeks. Legacy editions are normalized from their original creation timestamps without changing their content; the sample's November 19 news date is retained separately. The calendar marks saved editions with a dot. The API can also compose earlier sample coverage without including later reports. Each edition keeps its own summary and sources. “Keep summary only” removes its audio while retaining the readable brief and report export. Shared audio remains until the final referencing edition releases it. Device-voice previews have no stored audio file, so removing one does not claim disk savings.
- Today, Discover, Podcasts and Preferences inside a phone-shaped browser preview. Discover shows one story and its publisher thumbnail at a time. Swipe up or down, use two-finger trackpad gestures, or use arrow controls to turn a page. Momentum stays on one story; a reverse gesture goes back immediately. Search and filters open from the top-right button. Story and transcript sources open in an in-app reader, with Summary / Full article controls and original language editions.
- Six pre-rendered, approximately five-minute samples: personalized Dutch, German and English two-host conversations for the four task personas, plus Medium user in English, use ElevenLabs natural voices. Free user has a separate recorded Microsoft TTS conversation. Each episode is one MP3 with measured chapter boundaries; selecting a story seeks inside that file. Connected on-demand editions use an asynchronous n8n job for source-reviewed writing and, when Natural voice is selected, ElevenLabs v3 audio. A Medium Natural edition requested at approximately five minutes completed end to end with four ready audio chapters; this run measured 4:25 (265.04 seconds) and verified byte-range playback. The Basic voice path records local Microsoft SAPI audio to a file. Jobs show progress, retain resumable work, and expose retry when safe.
- Flow and Horizon have a **Listen to summary** button below a story summary. The 19 reviewed stories have 57 prerecorded Microsoft TTS summaries in English, German and Dutch, including spoken outlet attribution. Missing clips use an explicitly labeled device preview. Starting a summary pauses the podcast and vice versa. Free users see the paid-plan entry point. These are accessibility foundations, not a claim of complete screen-reader accessibility.
- Listening controls in Podcasts and the expanded player: 0.75×, 1×, 1.25×, 1.5×, 1.75× and 2× speed, remembered on this device. A sleep timer supports preset or custom minutes and stopping at the end of the whole podcast. Timers use real minutes while the app remains open. Briefing choices and preview lengths use approximate `~5 min` labels at 1× speed.
- Voice samples in Listening: 24 ElevenLabs library samples, eight each in English, German and Dutch, plus the browser's actual Basic voices. Choose up to two Natural voices per language or leave the choice random. Basic voice pairs stay consistent through an episode. Sample playback does not generate new paid audio.
- Subscription comparison fits Free ($0), Flow ($ A BIT), and Horizon ($ A LOT) on one screen. Free: 1 Basic-voice edition/day, up to ~7 min, summaries, no AI translations, with ads. Flow: 1 Natural-voice edition/day plus unlimited Basic-voice editions, up to ~15 min, translation, with ads. Horizon: unlimited Natural/Basic editions, up to ~40 min, translation, ad-free. Prices are placeholders. Demo switching creates no payment; billing and ad serving are not connected. Daily limits count new editions, never replays; removing audio does not reset them.
- Personal provider/model controls have been removed. Personal-key creation endpoints return 410; legacy encrypted keys can still be removed. Provider credentials remain in n8n. The Podcast Studio uses GPT-6 Luna for Free draft writing and GPT-6.1 Sol for paid draft writing and source review; the News Desk uses Luna for preparation and Sol for review. No model above GPT-6.1 Sol is used.
- Flow and Horizon can include reviewed translated summaries; translated summaries display “Translated by AI.” Free receives original-language summaries and publisher headlines. The live News Desk prepares English, German and Dutch summaries from an imported report, preserves original source IDs and languages, checks claim quotes against the supplied article, and proposes semantic candidate relationships for the listener's reviewable catalog. It does not independently verify publisher reporting against official releases or the jury answer key.
- An offline catalog with tags for all 1,740 articles. Language editions remain linked, not discarded. Source-language availability is preserved; a source not available in the listener’s language must remain clearly identified.
- A durable local worker that dispatches signed cloud generation and news jobs, handles saved retries, records Basic audio, and checks schedules during a 30-minute preparation window in the listener's timezone. The worker must stay running for scheduled jobs; it does not send push notifications or set an alarm.

**This is a local prototype. Demo account switching is not production authentication, and plan prices are placeholders.** Four n8n Cloud workflows are published and connected. The app sends signed HTTPS requests outward; there is no public tunnel into the app or public access to its private article database. Selected article paragraphs are sent to the cloud workflows for processing. OpenAI and ElevenLabs credentials stay in n8n, not in the app. Billing and ad serving are not connected. Basic device speech is labelled as a preview.

## Run locally

The **private team repository now includes six five-minute sample podcasts, 57 English/German/Dutch spoken summaries, and 24 locally served Natural voice previews**. Pull the latest `main`, rebuild the frontend, and restart the backend. The backend installs missing sample editions automatically after the licensed catalog is prepared; it preserves existing editions, personal preferences, history, and summary-only choices. No provider key or n8n connection is required to replay these recordings. Basic device voice previews still depend on voices installed on the listener's computer. Live generation requires a separately configured cloud connection.

Image assets are stored losslessly in `assets/embedded-images.json`. `npm run build`, `npm run dev`, and `npm run preview` restore their original binary files automatically with SHA-256 verification. These generated copies are ignored by Git.

For a complete feature inventory see [ALL_FEATURES.md](ALL_FEATURES.md). To add licensed reporting see [the news intake guide](docs/news-intake.md) and its synthetic JSONL example. For repository scope and setup limits see [GitHub handoff](docs/github-handoff.md). The [2:30 video storyboard](docs/presentation-video/STORYBOARD.md), [Claude capture handoff](docs/presentation-video/CLAUDE-HANDOFF.md) and [podcast-writing guidance](skills/seranews-podcast-writer/SKILL.md) are included.

On this Windows workspace, double-click **Launch-Seranews.cmd** to open the prepared demo. Keep its terminal window open while using Seranews. If the demo is already serving port 8000, the launcher opens that session. On another machine, run the setup below first.

Prerequisites: **Python 3.11+**, **Node.js 22+**, npm, and the licensed dataset ZIP supplied by the organizers. Run commands from this folder.

On Windows:

```powershell
.\start-demo.ps1 -DatasetZip 'C:\path\to\liquid-briefing-data.zip'
```

The script creates a project-local Python environment, installs dependencies, builds the frontend, starts the worker in a hidden process, and serves the app at `http://127.0.0.1:8000`. Stop the foreground server with Ctrl+C to stop its worker. `-SkipInstall` reuses an existing environment and build; `-NoBrowser` suppresses opening a browser tab.

Manual setup:

```text
python -m venv .venv
# Activate .venv with the command appropriate to your shell.
python -m pip install -r requirements.txt
npm install
python -m backend.prepare /path/to/liquid-briefing-data.zip
npm run build
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

In a second terminal with the same virtual environment active:

```text
python -m backend.worker
```

For UI development, `npm run dev` serves Vite at port 5173 and proxies API/media requests to port 8000. The built demo needs only the API server and worker. Use a single local worker instance.

SQLite state is saved in `data/liquid.db`; the prepared catalog is `data/catalog.json`. Full source text from the supplied ZIP stays separately in the private local `data/articles.db`, with each original language edition retained. New generated media is stored in `media/`. Personal state, new recordings and source databases remain excluded from Git. The explicitly approved fixed sample recordings and their source-linked scripts are shared only in this private team repository for the hackathon. An app restart preserves account preferences, votes, listening history and editions.

For local news updates, place a completed, licensed Newstex-style `.jsonl` file in `data/incoming/` while the worker runs. It checks the folder every 30 seconds, adds new articles and tags, and skips previously imported IDs. The open app checks for a changed catalog every 45 seconds and refreshes when returning to the tab. New coverage can change the topic prompts in Discover and Settings. Imported headlines are available for browsing. Podcast generation uses the reviewed catalog summaries.

## Data and editorial behavior

The news is a **November 19, 2026 dataset replay**, not a live news service. Edition creation dates and reading-history dates use the real clock. Most feeds cover November 13–19; the Zacks sample also contains older material. Current-briefing selection filters historical research by date. “Since you last listened” uses the replay clock and per-listener history.

The original replay catalog is prepared locally using deterministic topic rules and author/time-based links for translated Invezz coverage. The connected News Desk can prepare one imported story at a time with an English, Dutch and German title and summary, checked source quotes, tags and candidate relationships. Candidate links are suggestions; full-dataset cross-outlet grouping has not been validated against the organizer's answer key. Playable sample summaries are human-authored paraphrases in English, Dutch and German. The shared catalog contains metadata and links; the local reader retrieves original article bodies separately from the private article database. Missing source text offers the publisher link.

Source references establish **provenance**. They are not a claim of independent verification against official releases or the jury’s answer key. Related coverage is distinguished from the report supporting a summary. Unconfirmed reports and allegations retain attribution. The demo reports news without adopting a publisher’s investment recommendation.

Votes adjust relevance gradually. Explicit language and depth settings remain under the user’s control. “Already heard it,” “Too technical,” and “Too basic” are distinct from disliking the topic. Publisher sentiment labels such as `POSITIVE`/`NEGATIVE` are not used as listener preferences.

## Connected n8n workflows

Four n8n Cloud workflows are published and connected. The app makes outbound signed HTTPS requests; n8n does not open a tunnel into the local app or its private article database. The OpenAI and ElevenLabs credentials are stored as n8n credentials and are not present in the app. The local connection file and signing key are ignored by Git.

| Workflow | Purpose | Published workflow |
|---|---|---|
| Radar | Advisory discovery and candidate selection | [Open Radar](https://<your-n8n-host>.app.n8n.cloud/workflow/3ayexitw5VgzfSOc) |
| Podcast Studio | Personalized, source-linked script writing and review | [Open Podcast Studio](https://<your-n8n-host>.app.n8n.cloud/workflow/alCqbDEhLlWczybC) |
| Natural Narration | ElevenLabs v3 audio generation | [Open Natural Narration](https://<your-n8n-host>.app.n8n.cloud/workflow/ALBVDM55ue2ErBm9) |
| News Desk | Single-story preparation, multilingual summaries, tags and review | [Open News Desk](https://<your-n8n-host>.app.n8n.cloud/workflow/qdVgSd8RoLPWMhps) |

The app persists jobs locally and displays asynchronous progress, safe retry state and resumable work. The Podcast Studio freezes selected stories and evidence before generation, checks each spoken turn's source quote, and validates source IDs before publishing. The News Desk retains the original report and source IDs, produces English, Dutch and German summaries, reviews extracted claims, and proposes `new`, `same-event` or `translation` candidate relationships. Its exact-quote and numeric checks establish traceability to the submitted report; they do not establish that the publisher's claim is independently true.

The local worker dispatches queued work and checks scheduled tasks during a 30-minute preparation window. It must remain running for the schedule to be checked. The demo has no push notification or automatic alarm. Billing and ad serving remain unconnected, and plan prices are placeholders. Basic voice uses the local Microsoft speech engine and is labeled as a preview. For the full data path, request/signing details and verified run records, see [`docs/live-integration.md`](docs/live-integration.md).

## Cost and judging readiness

Observed token usage from a successful one-chapter, three-turn Podcast Studio run and a successful one-article News Desk run produces a sample-based OpenAI estimate. It is not an invoice or an all-in production quote. At standard published rates, the News Desk sample estimates to **$0.0220723 per article** (Luna preparation plus Sol review, including the reported prompt-cache writes). Linear projections are **$38.41 for 1,740 articles** and **$384.06 for 17,400 articles** under one News Desk run per article and identical token usage. A four-chapter model for one listener edition requested at approximately five minutes, based on the observed Podcast Studio chapter, adds about **$0.029448 per paid listener edition**. ElevenLabs USD, n8n execution charges, hosting, retries and any cache-hit savings are unknown; the model estimates are therefore not total operating costs. See [`docs/cost-model.md`](docs/cost-model.md) and [`docs/cost-model.json`](docs/cost-model.json).

The required working prototype is strongest when comparing at least two listener profiles while following a spoken claim to its source. Prepared episodes, Studio/News Desk/narration smoke tests, and a completed Medium Natural edition request configured for approximately five minutes show the connected path; this run measured 4:25 (265.04 seconds). The one-article News Desk smoke test does not validate cross-outlet grouping across the 1,740-record set. No answer-key or official-release comparison is recorded. The presentation still needs a clear payer and a cost explanation that separates measured data from assumptions; this is an event replay, not live news.

See [`docs/challenge-readiness.md`](docs/challenge-readiness.md) for the rubric-by-rubric audit, required items versus optional data tips, remaining checks and a concise judging runbook.

## Dataset licence and brand

The dataset README limits use to the hackathon, prohibits republishing article text, limits sharing to the team and requires deletion of all dataset copies after the event. The connected workflows process selected source paragraphs for the demo; that does not grant public redistribution rights. Keep the ZIP, article database, catalog, event-derived scripts and audio, backups and secrets out of a later public GitHub upload. `.gitignore` excludes `data/`, `.secrets/`, `*.zip` and generated media, but inspect the final Git staging list anyway. Do not deploy the licensed catalog or article reader publicly. Ask the organizer about reuse of event-derived summaries/audio after the event, and remove them from any public repository unless permission is explicit. The challenge brief itself does not state a separate public reuse licence for the Seranews mark; ask Seranews or remove the mark before public distribution.

Seranews is the track partner and Newstex is the data partner.

References: [ElevenLabs timed TTS](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps), [n8n import/export](https://docs.n8n.io/workflows/export-import/), [n8n webhooks](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/), [n8n chapter loop](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.splitinbatches/).

See `../seranews-cloud-workflow-plan.md` for the proposed dedicated feedback/For You subworkflow and model routing. That document is a design plan for feedback-driven cloud ranking; the four published operational workflows are listed above. The backend remains canonical for feedback, preferences and feed revisions. The app applies feedback optimistically and does not wait for n8n to acknowledge a tap. Tag learning uses normalized multi-tag weights and is reversible from the latest-state ledger, with learned influence bounded to ±2 on the manual 0–5 scale.
