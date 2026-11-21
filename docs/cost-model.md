# Cost model: measured usage and projections

**As of:** 21 November 2026. All USD values below are calculations at public standard model rates, not account invoices. The cost scope is model tokens only unless stated otherwise.

## Model pricing

| Model | Input / 1M | Cached input / 1M | Cache-write input / 1M | Output / 1M |
|---|---:|---:|---:|---:|
| GPT-6 Luna | $0.10 | $0.01 | $0.125 | $0.50 |
| GPT-6.1 Sol | $2.00 | $0.10 | $2.50 | $10.00 |

The cache-write rate is 1.25 times the ordinary input rate. The current News Desk sample reports cache-write tokens and no cached-token hits. Rates are from the [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) model pages.

## Observed smoke usage

The successful one-report News Desk smoke used GPT-6 Luna for preparation and GPT-6.1 Sol for review. It returned three claims attached to one source, titles and summaries in English, Dutch, and German, four tags, and a `new` relation. Its recorded usage was:

- Luna: 4,055 input tokens (4,052 cache-write, 3 ordinary, 0 cached) and 1,099 output tokens; estimated **$0.0010563**.
- Sol: 4,827 input tokens (4,824 cache-write, 3 ordinary, 0 cached) and 895 output tokens; estimated **$0.021016**.
- Combined one-report model estimate: **$0.0220723**.

The successful Podcast Studio smoke used GPT-6.1 Sol for writing and review of one three-turn chapter: 466 input / 126 output for writing and 555 input / 406 output for review, with no cache reads or writes. Its estimated model cost is **$0.007362 per sample chapter**.

The ElevenLabs v3 smoke produced 20.64 seconds of audio. Its usage response reported 119 provider character-cost units; this is not necessarily the literal number of text characters, and the USD charge or credit consumption is unknown. The separate Medium request configured for approximately five minutes produced 265.04 seconds (4:25) of audio, with four source-reviewed chapters. Its exact workflow and audio charges remain unknown.

## Full and 10x estimates

The shared preparation arithmetic applies the measured one-report News Desk usage once for every original input article. The personalized addition assumes two paid profiles each receive one edition requested at approximately five minutes. At that configured duration the app selects four chapters; each is modeled at one observed Studio chapter's token usage. The measured Medium edition lasted 265.04 seconds (4:25). The personalized script estimate is therefore 8 × $0.007362 = **$0.058896** for both profiles.

| Scenario | Shared News Desk model estimate | Two requested ~5-minute Studio script estimates | Estimated OpenAI model total | Full operating total |
|---|---:|---:|---:|---|
| 1,740 input articles | $38.405802 | $0.058896 | **$38.464698** (about $38.46) | Unknown |
| 17,400 input articles | $384.058020 | $0.058896 | **$384.116916** (about $384.12) | Unknown |

This estimate assumes one News Desk call per original article, identical token usage to the one-report sample, and two paid listener edition requests configured at approximately five minutes. It makes no allowance for shared prompt-cache savings. Article lengths, source context, retries, failure rates, listener count, and episode sizes can change real use. The full-dataset and 10x values are projections; no cloud run of 1,740 or 17,400 distinct article records was performed.

The numbers exclude ElevenLabs USD charges, n8n executions, hosting, storage, worker operations, and any retry or failure cost. Therefore the table is a concrete **model-token estimate**, not an all-in production price or vendor invoice. The 20.64-second narration smoke and its 119 provider character-cost units are not a valid cost estimate for the 4:25 Medium audio output.

## Separate local measurements

Local offline timings and traced memory are recorded in [`performance-measurements.json`](performance-measurements.json). They measure catalog load, ZIP parsing, deterministic tagging, profile ranking, and a synthetic 10x tag pass. That 10x pass repeats the same 1,740 parsed rows ten times; it is not a distinct 17,400-article corpus and says nothing about cloud latency or provider spend.

The machine-readable token records and formulas are in [`cost-model.json`](cost-model.json). The local smoke artifacts remain under ignored `data/` and should not be copied into a public repository.
