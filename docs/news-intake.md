# Add a news report

The connected pipeline accepts licensed Newstex-style JSONL files in `data/incoming/`. Each nonempty line is one JSON article. The file must be UTF-8. The backend and worker must both be running.

1. Prepare a file outside `data/incoming/` and finish writing it before copying it into that directory.
2. Include the fields listed below. Use a new stable article ID for a new report.
3. Copy the completed `.jsonl` into `data/incoming/`.
4. The worker imports original source data, then sends the report through the connected News desk workflow.
5. On approval, the app receives summaries, translations and tags. Microsoft speech recordings are prepared in English, Dutch and German. Paid accounts receive the spoken-summary controls.
6. The open app checks for a changed catalog about every 45 seconds and on returning to the tab. Refreshing the page also loads the new version.

The example file beside this guide is **fictional** and is not automatically imported. Replace its content with a report you have permission to use. Importing it deliberately will run the model workflow and can consume API credits.

| Field | Requirement |
|---|---|
| `article_id` or `$id` | Stable unique identifier; an existing ID is not a new report |
| `headline` | Original publisher headline |
| `text_content` | Original article text; needed for source checks |
| `language` | `en`, `nl` or `de` |
| `date` | ISO date/time with timezone, for example `2026-11-21T08:00:00+01:00` |
| `permalink` | Original HTTP(S) article URL |
| `publication.name` | Publisher name used in source attribution |
| `thumb_url` | Optional licensed HTTPS image URL; no image gives fallback artwork |
| `translation_group_id` | Optional shared ID for genuine publisher-language editions of the same report |
| `event_id` | Optional shared ID for the exact same development, not a broad topic/company |
| `company_tickers` | Optional array of stock symbols |
| `provider_categories` | Optional array of category strings |

Keep original English/German/Dutch reporting as separate records with separate article IDs. Give translations the same translation group only when they really are editions of the same report. A newer development needs its own article identity and event identity when the underlying event changed.

## What happens on failure

- A report lacking original text cannot pass editorial preparation; the worker retains its source rather than inventing a summary.
- Invalid claims, evidence quotations or introduced numbers prevent reviewed publication.
- An approved report can remain readable while its local speech recordings retry.
- Preparation state and useful errors are retained in SQLite's `news_preparations` table. Worker diagnostics are in `data/worker.log` and `data/worker-error.log`.
- Source URLs alone are insufficient: automatic website scraping and a live RSS/API feed connector are not connected. A future feed adapter must produce the same input records.

## Demonstration and privacy

The pipeline sends original reporting paragraphs to the configured cloud models for processing. Use only content permitted by the event's licence. Do not upload the source files, local databases or generated event-derived recordings into a public repository. The example contains no licensed article text or credentials.
