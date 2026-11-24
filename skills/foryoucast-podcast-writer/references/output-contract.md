# App and workflow handoff

Return these fields; IDs and evidence come from supplied catalog data, never fabricated placeholders in a real script.

- Edition: profile_id, language, depth, created_at, edition_date (creation day), news_as_of, requested_minutes, estimated_seconds, estimated_range_seconds, timing_basis (estimated_at_1x), duration_label (for example ~5 min), shorter_than_requested_reason, hosts.
- chapters[]: story_id, story_version, title, tags[], summary (written paraphrase), development_since_last_listen, estimated_seconds, turns[], claims[].
- turns[]: speaker (maya or leo), text (spoken words only), claim_ids[], source_ids[], estimated_seconds.
- claims[]: id, statement, source_ids[], evidence_locator (supplied paragraph index or short supporting excerpt), qualification.
- sources[]: article_id, outlet, headline, language, published_at, url, translation_group_id when supplied.
- review_claim_ids[]: three substantive claims when available; otherwise the available IDs plus a coverage note.

Include the introduction, bridges and ending in chapter turns or explicit interludes so the duration estimate counts them. Turn estimates should approximately sum to chapter estimates and chapter estimates to the edition total. Derive the range from actual uncertainty rather than always returning an identical range.

Every factual turn must cite a claim that exists. Each cited source must exist and actually support that statement. Preserve the claim-source relationship through translation and audio chunking. Greetings and purely editorial pivots can have empty arrays.

Keep metadata, voice IDs, URLs and evidence locators out of spoken text. Voice IDs are chosen by production, using voices actually available in the connected workspace. Written summaries and source links remain after audio removal. Measured waveform duration, ASR word timestamps and native provider alignment are separate production fields and retain their provenance.

Example timing metadata for an approximate five-minute request:

```json
{"requested_minutes":5,"estimated_seconds":300,"estimated_range_seconds":[270,330],"timing_basis":"estimated_at_1x","duration_label":"~5 min"}
```

The example is illustrative, not a fixed range or a requirement to pad to 300 seconds.
