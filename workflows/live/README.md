# Connected ForYouCast workflows

These JSON files snapshot the four tested workflows on the connected n8n instance. Imports are deliberately inactive. The existing cloud copies are already published; importing again is unnecessary for this installation.

1. [News desk](https://<your-n8n-host>/workflow/qdVgSd8RoLPWMhps): grammar, tags, three-language summaries and source-quote review.
2. [Podcast studio](https://<your-n8n-host>/workflow/alCqbDEhLlWczybC): two-host writing and a separate evidence review.
3. [Natural narration](https://<your-n8n-host>/workflow/ALBVDM55ue2ErBm9): ElevenLabs v3 dialogue with timestamps and explicit failure handling.
4. [Personal radar](https://<your-n8n-host>/workflow/3ayexitw5VgzfSOc): deterministic feedback weights and personal feed ordering.

The backend initiates signed HTTPS requests, so the private app stays on localhost. Public verification keys are included in workflow code; the matching private signing key stays in the ignored `.secrets/` directory. Provider credentials are references only and contain no keys in these exports. When moving to a new installation, configure its signing key/connection and the corresponding workflow verification keys, and select credentials belonging to that n8n account.

`backend/workflow_exports.py` generates Workflow SDK sources. The JSON snapshots represent the tested cloud graphs, including their current credential references. Files in the parent folder marked `draft` or `inactive` are older scaffolds, not the connected pipeline.

The local worker handles durable jobs, the 30-minute preparation trigger, Basic Windows speech, audio assembly and publication. Keep the backend and worker running during the demonstration. No push alarm, live billing or real ad serving is implemented.
