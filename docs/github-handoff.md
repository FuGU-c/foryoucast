# GitHub handoff

Uploaded repository: https://github.com/FuGU-c/seranews-project-news (private), branch `main`. The upload used the GitHub plugin. Local Git has been initialized with this origin, but command-line authentication is separate from the plugin connection. Provider credentials, licensed reporting and generated media remain local.

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
- `media/` and `work/` — recorded episodes, source-derived audio and intermediate files.
- Source ZIP archives and original challenge files.
- `.venv/`, `node_modules/` and `dist/` — regenerate from manifests/build instructions.

These paths are covered by `.gitignore`. Before pushing, inspect the actual staged paths and diff: ignored files can still be force-added. Keep any repository private until event reuse rights for the partner mark and dataset-derived presentation materials have been confirmed.

## Reproduction limits

The code repository alone does not contain the licensed dataset or finished podcast media. Another machine must prepare the catalog from its authorized source ZIP and configure n8n/provider access. The existing local demonstration retains its private media, profiles and credentials and keeps working separately from GitHub.

The local worker must remain running for scheduled production. Public deployment additionally needs production authentication, managed hosting/storage, appropriate Windows speech infrastructure or a licensed server TTS replacement, monitoring and delivery services. The password-free demo selector is not production login.

## Verification evidence

- `docs/runtime-proof.json`: one actual n8n/OpenAI/ElevenLabs episode, four reviewed chapters, measured duration and HTTP byte-range support.
- `docs/intake-publication-proof.json`: isolated file import through publication and three real Microsoft recordings, reusing an already completed cloud review without new paid model calls.
- `docs/performance-measurements.json`: measured local timings and explicit synthetic 10× assumptions.
- `docs/cost-model.json`: model-token projections with rates and exclusions; not an all-in invoice.
- Source review, checklist and remaining judging limits are in `docs/evidence-review.md` and `docs/challenge-readiness.md`.
