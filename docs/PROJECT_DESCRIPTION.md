# Submission description

**Seranews — The Liquid Briefing**

Seranews turns a busy news feed into a personal audio briefing. Listeners choose their interests, article languages, narration language, explanation depth and listening time. They can then explore a swipeable news feed, give thumbs-up/down feedback, and listen to a continuous, source-linked podcast tailored to their preferences.

The prototype serves four contrasting listener types: a Dutch investor, a German investor, an FX trader and a general-news listener. A blank New listener account demonstrates onboarding. Separate Free and Medium accounts show the proposed product tiers.

News preparation happens once for the shared catalog. Personalized editions are composed when requested or during the scheduled preparation window. n8n coordinates news preparation, drafting, source review and natural narration; the local backend owns preferences, history, quotas, jobs and reusable audio. OpenAI supports writing and evidence review, while ElevenLabs supplies natural speech.

The demo includes multilingual sample podcasts, spoken summaries, searchable reading history, saved stories, history-aware catch-up, chapter navigation, playback speed, sleep timers and four light/dark themes. Every episode retains its readable brief and source links, even when its audio is removed.

This is a working local hackathon prototype using a November 2026 dataset replay. Demo account switching, subscription pricing and advertising are presentation features; production authentication, billing, ad delivery and push notifications are not implemented. New cloud generation requires a configured n8n connection. The organizer's licensed source dataset is not distributed in this repository.

## Short repository description

Personalized, source-linked news podcasts with multilingual discovery, adaptive interests and natural voices. React + FastAPI + n8n + ElevenLabs.
