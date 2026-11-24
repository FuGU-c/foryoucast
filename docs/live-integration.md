# Live n8n integration

**Status checked:** 21 November 2026. Four n8n Cloud workflows are published. The app calls them from its outbound-only local backend; the browser does not hold provider credentials.

## Published workflows

| Workflow | Role | Published workflow |
|---|---|---|
| Radar | Advisory discovery/candidate selection | [Open Radar](https://<your-n8n-host>/workflow/3ayexitw5VgzfSOc) |
| Podcast Studio | Write and review a personalized, source-linked chapter | [Open Podcast Studio](https://<your-n8n-host>/workflow/alCqbDEhLlWczybC) |
| Natural Narration | Generate natural speech with ElevenLabs v3 | [Open Natural Narration](https://<your-n8n-host>/workflow/ALBVDM55ue2ErBm9) |
| News Desk | Prepare and review one imported report | [Open News Desk](https://<your-n8n-host>/workflow/qdVgSd8RoLPWMhps) |

## Request and data boundary

- `backend.cloud_client` sends requests over HTTPS to the approved n8n Cloud host. Requests are Ed25519-signed with a local private key under `.secrets/`; that key is not in the app source or public repository.
- `data/cloud-connection.json` contains local workflow routing and readiness configuration and is ignored by Git. It is not an API-key store.
- OpenAI native credentials and ElevenLabs Header Auth credentials remain in n8n. The app has no provider API keys.
- The network flow is outbound from the app. There is no inbound public tunnel to this computer, and the article database is not exposed publicly. Selected article paragraphs and metadata are sent outbound to the workflow that needs them.
- Cloud jobs are saved locally. The app reports stage/progress, resumes saved work, and exposes safe retry state. The local worker must remain running to dispatch jobs and check scheduled preparations during the 30-minute window. There is no push notification or automatic alarm.
- Natural audio uses the n8n-held ElevenLabs credential. The Basic path records local Microsoft SAPI audio to a file. Billing and advertising are not connected; plan prices are demo placeholders.

## Successful smoke and end-to-end checks

| Check | Observed outcome | What it proves |
|---|---|---|
| Podcast Studio, one chapter | Passed; GPT-6.1 Sol wrote and reviewed one three-turn chapter. Its review accepted the source evidence. Usage: 466/126 writing input/output tokens and 555/406 review input/output tokens. | Confirms one live writing/review request and returned token usage. It does not prove a full edition or independent fact verification. |
| News Desk, one report | Passed; GPT-6 Luna prepared and GPT-6.1 Sol reviewed. The result had three source-linked claims, four tags, one source ID, and English, Dutch, and German titles/summaries; relation classified as `new`. The recorded n8n execution interval was 19.731 seconds. | Confirms the one-report prepare/review path and saved response validation. It does not validate cross-outlet clustering over the dataset. |
| Natural Narration smoke | Passed; ElevenLabs `eleven_v3` returned 20.64 seconds of audio and 119 provider-reported character-cost units. | Confirms a short natural-audio response. The provider's character-cost units are not necessarily literal text characters; the USD charge is unknown. This smoke is separate from the 4:25 Medium result below. |
| Voice-preview availability | HTTP `HEAD` returned 200 for all 24 voice-sample URLs, eight each for English, Dutch, and German. | Confirms the sample assets are reachable from the demo. It does not measure listener preference or voice quality. |
| Medium Natural edition requested at approximately five minutes | Passed end to end. Read-only `GET /api/profiles/medium-demo/briefings/cloud-2ac92ab03b214408` returned `ready`, progress 100, and edition `edition-aedb1b5222fe48c8`. Four natural chapters passed source review. The measured single-file MP3 duration was 265.04 seconds (4:25); an HTTP Range request returned 206 and playback was verified. Resume reused completed chapter audio for the same edition, with no duplicate paid completed chapters. | Confirms one asynchronous job reached a saved ready state, produced four source-reviewed natural chapters, and supports partial-file playback. This run's 4:25 duration does not guarantee future duration, production availability, or an all-in unit cost. |

The first complete attempt exposed an unsupported ElevenLabs resume parameter and fell back before the retry. That was corrected so the retry resumed the same edition and reused its completed natural-audio chapter. A separate numeric normalizer change handles Dutch clock notation (`11.20 uur`) against English (`11:20`) while checking numeric claims; the later News Desk smoke passed. Keep both details in mind when describing what has been exercised.

Local smoke response files live in ignored `data/`. They include generated content and, for narration, a large base64 audio payload. This document records only safe usage and status fields; do not copy those payloads into a public repository. The sanitized runtime summary is in [`runtime-proof.json`](runtime-proof.json); it records status, measured duration, chapter boundaries and source-review flags without audio bytes or article text.

## Remaining limits

- One successful full Medium job does not establish reliability across providers, all listener profiles, every language, or long-running schedules.
- The News Desk is one-report-at-a-time. It proposes candidate relations and preserves different developments; no full-dataset cross-outlet answer-key evaluation has been run.
- Exact quote and numeric checks prove that supplied reporting is traceable to a source passage; they do not independently prove that the publisher's reporting is correct.
- The local 30-minute scheduler requires the worker to run continuously. There is no push notification, alarm, public feed ingestion, billing, or ad serving.
- ElevenLabs USD, n8n execution costs, hosting, and full-episode audio cost remain unknown. Model-only projections are documented in [`cost-model.md`](cost-model.md).
