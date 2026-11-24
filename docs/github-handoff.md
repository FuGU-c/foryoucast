# GitHub handoff

Repository: https://github.com/FuGU-c/foryoucast-project-news, branch `main`. The owner made it public on 21 November 2026. The source was uploaded through the GitHub plugin; local command-line authentication is separate. Provider credentials, original licensed reporting and personal state remain local. The approved fixed demo media and presentation narration are versioned. See [the security audit](../SECURITY.md).

Binary image assets are stored losslessly in `assets/embedded-images.json`; `npm run build`, `npm run dev` and `npm run preview` restore the exact image bytes with SHA-256 validation. The materialized files are ignored. The included source can be built normally; article data and podcast recordings still require the authorized local dataset/media setup.

Collaborator invitations for kepcheto and KordianKlimas require repository Settings → Collaborators because the connected plugin exposes listing but no invitation action. No browser automation is authorized after the user asked to stop controlling the PC.

## Include

- Frontend source, backend code and tests.
- Dependency manifests, build configuration and launch scripts.
- README.md, ALL_FEATURES.md and CONTINUE_HERE.md.
- Synthetic news intake example and operational/testing documentation.
- Workflow graph exports, after reviewing credential names, instance URLs and public verification keys. Credential references contain no provider keys, but a new installation needs its own credentials and signing-key configuration.

## Keep local

- `.env` and `.secrets/` — credentials and private signing material.
- `data/` — private article/catalog databases, user preferences, usage responses, backup copies and connection configuration.
- New recordings and `work/` — generated episodes and intermediate files. The fixed, explicitly shared samples are already tracked exceptions.
- Source ZIP archives and original challenge files.
- `.venv/`, `node_modules/` and `dist/` — regenerate from manifests/build instructions.

These paths are covered by `.gitignore`. Before pushing, inspect the actual staged paths and diff: ignored files can still be force-added. Public source availability does not grant rights to redistribute the organizer dataset or reuse publisher reporting and partner branding.

## Portable audio update

The user approved sharing the demo recordings. The repository includes six fixed podcast MP3s in `media/demo-samples/`, 57 spoken summaries in `media/story-summaries/`, and 24 voice preview MP3s in `public/voice-previews/`. Source-linked sample scripts and timing manifests are in `assets/demo/`; the backend seeds only missing sample editions and leaves New listener blank. Existing episodes, history, personalized settings, and summary-only choices are retained. No paid regeneration or provider credentials are needed for playback. Verify native binary sizes and checksums against `assets/demo/media-verification.json`.

After pulling, run `npm run build`, then restart the backend and worker. The authorized organizer dataset must still be prepared locally. Its original README prohibits sharing dataset files outside the team and republishing full article text, permits short quotes and source links, and requires deletion after the event. Those terms remain applicable regardless of repository visibility.

## Reproduction limits

The repository does not contain the licensed source dataset, article database, personal database, or cloud credentials. Another machine must prepare the catalog from its authorized source ZIP. The fixed sample podcasts and summaries are included; n8n/provider setup is needed only for new cloud generation.

The local worker must remain running for scheduled production. Public deployment additionally needs production authentication, managed hosting/storage, appropriate Windows speech infrastructure or a licensed server TTS replacement, monitoring and delivery services. The password-free demo selector is not production login.

## Verification evidence

- `docs/runtime-proof.json`: one actual n8n/OpenAI/ElevenLabs episode, four reviewed chapters, measured duration and HTTP byte-range support.
- `docs/intake-publication-proof.json`: isolated file import through publication and three real Microsoft recordings, reusing an already completed cloud review without new paid model calls.
- `docs/performance-measurements.json`: measured local timings and explicit synthetic 10× assumptions.
- `docs/cost-model.json`: model-token projections with rates and exclusions; not an all-in invoice.
- Source review, checklist and remaining judging limits are in `docs/evidence-review.md` and `docs/challenge-readiness.md`.
