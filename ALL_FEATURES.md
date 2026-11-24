# ForYouCast — complete feature inventory

Updated 21 November 2026. This describes the implemented local demonstration and distinguishes it from proposed production features. See README.md, docs/live-integration.md, docs/challenge-readiness.md and docs/runtime-proof.json for operational details and evidence.

## Product and presentation

- Personalized written and spoken news briefings branded ForYouCast / The Liquid Briefing.
- Mobile-shaped browser application with a phone frame, responsive content and persistent navigation.
- Four coordinated themes: Signal, Cobalt, Edition and Afterhours, each with Light and Dark modes. Appearance opens below Subscription in the profile menu; four illustrated choices fit on one sheet. Selection applies immediately and saves on this device across reloads and profile switches.
- Pricing uses a neutral comparison table with a soft Flow highlight and restrained button shadows. Display prices are $0, $ A BIT and $ A LOT; paid values remain demonstration placeholders.
- Transparent company mark and matching browser icon. Semantic color tokens are centralized in src/theme-palettes.json and src/theme.css; photographs use separate, high-contrast media labels.
- Today, Discover, Podcasts, Preferences, reading history and saved stories.
- Profile selector in the header; Preferences & schedule, Subscription and Appearance are grouped in that order below the demo accounts.
- Persistent player while moving between application screens.
- Loading, empty, failure and retry states rather than silently claiming success.
- Reduced-motion support and keyboard-accessible controls in key interactions.

## Accounts and demonstration content

- Seven password-free demo profiles; this selector is not production authentication.
- Mila: Dutch investor, Dutch narration and investment interests.
- Six original illustrated profile pictures identify the demo listeners in the profile menu and header. New listener keeps the unidentified plus icon.
- Previous/next controls and chapter selection always pause at the selected chapter, including when audio was playing. Playback resumes only after pressing Play. This applies to both expanded and mini players, combined recordings and separate clips/device previews.
- Discover uses one native vertical scroll track with snapping. Each page's image, headline, source labels and controls exist together before navigation and move as one card. There are no separately animated headlines, 3D flips, duplicate departing layers or independent image fades. Touch uses native scrolling, while wheel gestures and arrow controls advance one story at a time in either direction. Images remain mounted and load lazily near the viewport. The phone's bottom home indicator is black in every theme.
- Today cards, story details and Discover share the same story-image loader. It prioritizes the supporting report and its linked language editions, preserves image framing, and resets failed-image state when changing stories. Missing publisher photos use a labeled editorial illustration rather than oversized initials; unrelated coverage is not used as a substitute photo.
- Mila, Jonas, Alex and Sam default to Horizon. The one-time update preserves their existing interests and history; Free user and Medium user retain their demonstration tiers.
- Today and the main podcast Play control open the newest completed briefing even after preferences change. Library date filters affect the list, while its main Play control still plays the latest saved edition. Failed, pending, and summary-only editions are excluded.
- Create briefing always prepares a fresh edition. Temporary writing throttling falls back to the existing reviewed source summaries and displays a notice.
- Missing Microsoft/system speech voices can fall back to the included Basic recordings for the 19 fixed demo stories in English, Dutch and German. Exact source IDs and summary text must match; one combined MP3 receives measured chapter boundaries. No installed Dutch voice is needed for these unchanged demo stories.
- Jonas: German investor, German narration and deeper financial explanations.
- Alex: English-speaking FX trader with currencies and macroeconomic interests.
- Sam: English-speaking general-news listener with simpler explanations.
- Free user: a separate Free-plan account and Microsoft speech sample.
- Medium user: a separate Flow-plan technology/investment account and natural-voice sample.
- New listener: unidentified, not onboarded, no prepared podcast or initial interests.
- Four listener archetypes come from the challenge materials; names and detailed presets are demonstration choices.
- Six approximately five-minute prerecorded sample podcasts, excluding New listener.
- Five samples use natural voices; Free user's sample uses recorded Microsoft speech.
- A genuinely generated Medium episode is also saved: four reviewed natural-voice chapters, measured at 265.04 seconds (4:25) for a ~5-minute request.

## Onboarding and preferences

- Multiple listening goals can be selected together.
- Goal selections suggest a combined set of relevant tags.
- Individual topics can be added, removed and adjusted separately.
- Settings, preference memory and feed previews update without a Save button.
- Preference writes sync automatically, with pending/error/retry handling.
- Multiple original reporting languages can be selected simultaneously.
- Narration language is separate from original reporting-language preferences.
- English, Dutch and German are supported in the prepared demonstration.
- Explanation depth: simple, balanced or detailed.
- Preset and custom estimated podcast durations, bounded by the selected plan.
- Requested durations use approximate ~ labels; recorded playback uses measured timing.
- Listening time, timezone and scheduled preparation preferences.
- Custom-interest text and stock-symbol watchlists.
- CSV, TSV and TXT watchlist import; symbols are retained, not a general analysis of an uploaded investment portfolio.
- Onboarding/personalization can be revisited from preferences.
- New relevant topic suggestions derive from the current catalog.

## Feedback and recommendation behavior

- Instant upvote/downvote controls with stable final colors.
- Voting does not replace the current news card or reload its image.
- Selecting a thumb triggers a short hand tilt/pop with a small sparkle burst. Clearing a vote does not repeat the celebration; reduced-motion preferences disable the effect. Selected colors still update instantly.
- Votes can be cleared or reversed.
- Feedback can distinguish interest, repetition, overly technical and overly basic explanations.
- Viewing an article is not automatically a like.
- Saving an article does not automatically change topic preferences.
- Multi-tag stories distribute learning across their tags.
- Primary tag receives 0.6 of a multi-tag vote; the remaining 0.4 is divided among other tags. A single tag receives the full contribution.
- Manual topic amounts remain separate from learned changes.
- Learned influence is bounded to ±2 points; displayed effective amounts are bounded to the 0–5 scale.
- Manual edits override older feedback for the edited topics.
- Ordered feedback reconciliation protects newer actions from stale responses.
- Compact preference memory describes explicit preferences and liked/disliked topics.
- Backend ranking considers interests, feedback, language access, freshness, watchlists and variety.
- n8n recomputes topic weights and personal ordering from saved state.
- Cloud results are accepted only for matching profile/feedback/catalog revisions.
- Current-card stability is retained while future recommendations change.

## Discover

- Discover preserves the current browsing sequence after likes/dislikes and background recommendation refreshes, including backward swipes. New incoming stories append once; changing filters, explicit preferences or profile starts a fresh deck. Thumbs continue updating learned topic weights for future recommendations and briefing selection.

- One prominent picture-led story at a time.
- Rounded card, readable headline, publisher, language and topic tags.
- Publisher thumbnail when available, with fallback artwork otherwise.
- Touch, wheel/trackpad and arrow navigation.
- Page-turn-style transitions and one-story momentum handling.
- Reverse gestures return to the previous story.
- Search and filters are revealed on demand to keep the main feed uncluttered.
- Search by news text and filter by topics/original reporting languages.
- Upvote/downvote controls and article/source access.
- Save control sits below the thumb feedback buttons; separate footer arrows navigate stories. Saved state changes immediately.
- Bookmarks persist per profile and across reloads.
- More/Less recommendation controls use thumbs to distinguish voting from swiping. Thumbs, Save and Read float without button backgrounds, with wider spacing and a lower thumb-friendly position.

## Stories, sources and trust

- Written paraphrased story summaries.
- Supporting source IDs remain attached to summaries and spoken chapters.
- Source references open the original report in the local reader when available.
- Summary / Full article reading controls.
- Article actions are stacked and aligned with matching 44px touch targets: Read full article as the primary action, and a separate outlined publisher link with an external-link icon. Large button shadows were removed; long publisher names wrap safely.
- The Script & sources view keeps its transcript, chapter attribution and supporting source links without the redundant News report / Podcast script download-button row.
- Original reporting languages, headlines and links are retained.
- Related coverage is distinguished from evidence supporting a claim.
- Alternative original-language editions can be opened.
- Paid translated summaries are labelled Translated by AI.
- Free responses exclude AI-translated summary variants.
- Translation does not invent an original English article or discard the source language.
- Spoken summaries for paid plans, placed below the written summary.
- Fifty-seven prepared Microsoft speech summaries cover 19 reviewed stories in three languages.
- Spoken summary and podcast playback pause one another.
- Missing recordings can use an explicitly labelled browser device-voice preview.
- New cloud-written chapters have a separate source review.
- Exact evidence quotations and source IDs are checked against supplied original paragraphs.
- Transcript Source review disclosures show supporting passages and links when available.
- Review means checked against supplied reporting, not independent confirmation that a publisher's report is true.
- Source allegations, uncertainty and numeric qualifications are retained by writing/review rules.

## Reading history, saved news and catch-up

- Since your last visit checks both reading and listening history against prepared story content. Profile-scoped snapshots retain known versions. Existing story/source links and conservative entity plus headline/summary similarity detect follow-ups; unchanged coverage is suppressed. Tags alone do not link events. New standalone reports use their publication date against the catch-up frontier. It runs locally without AI tokens; matching is heuristic and content changes before snapshot tracking cannot be reconstructed exactly.
- Newly prepared podcast chapters preserve the story snapshot they were based on; replaying old audio does not overwrite a newer reading snapshot. Current browsing order stays stable while this history updates.

- History icon in the header.
- Recently viewed stories and opened original reports are recorded per profile.
- Discover cards viewed for approximately 1.2 seconds count as viewed.
- Search history by headline, source or topic.
- Recent-date and feedback filters for reading history.
- Separate Saved tab with search and date filtering.
- Open a saved story through the existing story/source reader.
- Remove a saved story without deleting reading history.
- Saved state is isolated between demo accounts.
- Timestamp ordering prevents an older bookmark request from overriding a newer action.

## Podcast composition and editorial rules

- Select news from a shared prepared catalog using the listener's preferences.
- Natural two-host dialogue using Maya and Leo roles.
- Logical chapter ordering and transitions between related topics.
- Supporting outlet named aloud when introducing each story.
- Factual turns retain their supporting article IDs.
- Original reports provide private evidence for the separate source-review stage.
- Requested language, explanation depth and word budget guide writing.
- Historical dataset reporting must not be presented as live breaking news.
- No invented quotes, unsupported filler or investment predictions to meet a duration.
- Completed unchanged story versions are excluded from new podcast selection.
- Partially heard stories remain eligible; an updated story version becomes eligible again.
- Existing episodes can be replayed without consuming another generation allowance.
- Dedicated reusable writing guidance is in skills/foryoucast-podcast-writer/SKILL.md.

## Audio and player

- One combined MP3 per recorded episode.
- Measured chapter start/end positions.
- Selecting a chapter seeks within the same audio element/file.
- Immediate play/pause intent and protection against stale asynchronous play promises.
- Previous/next chapter controls and source/transcript access.
- Continuous timeline and native seeking.
- Playback rates: 0.75×, 1×, 1.25×, 1.5×, 1.75× and 2×.
- Playback speed remembered on the device.
- Sleep presets: 5, 10, 15, 30, 45 and 60 minutes.
- Custom sleep timer from 1 to 180 minutes.
- Stop at the end of the whole podcast option.
- Sleep countdown uses real minutes while the app remains open.
- Animated waveform-style progress bar; decorative texture follows actual seek position.
- The denser, finer waveform uses a theme-matched played section, subdued unplayed bars and a slim playhead. Staggered breathing stays subtle during playback, pauses in place with audio and respects reduced motion.
- Native range input retains keyboard support and drag-to-seek behavior.
- Persistent mini-player and expanded player.
- HTTP byte-range playback supports seeking through recorded files.
- Browser device speech remains available as a labelled legacy preview/fallback.
- Recorded Basic speech uses installed Windows System.Speech voices.
- English/German can use distinct installed voices; this machine currently has only one installed Dutch Basic voice.
- Natural narration uses ElevenLabs v3 timed dialogue.

## Voice personalization

- Twenty-four real natural-voice catalog samples: eight each for English, Dutch and German.
- Searchable voice cards, descriptions and accent labels.
- Preview audio before choosing.
- Up to two selected natural voices per narration language.
- Surprise me leaves production to choose a suitable language-matched pair.
- Chosen production voices stay consistent within an episode.
- Natural voice IDs are checked against the frozen generation selection.
- Basic browser voices can also be previewed; availability depends on the browser/device.
- All 24 natural preview URLs were checked successfully.

## Podcast library and storage

- Saved editions retain scripts, summaries, sources and source-coverage date.
- Creation date is distinct from the historical news date.
- Today, This week, This month, All editions and calendar filtering.
- Calendar marks dates containing editions.
- New editions use their actual creation date rather than the dataset's fixed date.
- Script/news-report export endpoints remain available internally; their redundant download buttons were removed from the Script & sources dialog. Readable scripts, summaries and sources remain in the app.
- Keep summary only removes recorded episode audio while retaining readable material.
- Shared media is retained while another edition still references it.
- Audio deletion cancels pending natural retries and prevents later audio restoration.
- Measured reclaimed/shared/unreclaimed storage reporting.
- Newest ready recorded edition matching current preferences is preferred on Today.
- Stale samples do not silently replace a newly generated matching episode.
- Completed generation does not autoplay if preferences changed during production.

## Plans

- Free: $0 price label; one Basic podcast/day, up to ~7 minutes, personalization, summaries, sources, history and playback controls; includes ads in the product offering; no AI-translated variants or paid spoken-summary access.
- Flow: $ A BIT price placeholder; up to ~15 minutes; one natural podcast/day, then unlimited Basic podcasts; AI translations and spoken summaries; includes ads in the offering.
- Horizon: $ A LOT price placeholder; up to ~40 minutes; unlimited natural/Basic podcasts; translations and spoken summaries; ad-free offering.
- Three plans are compared together on one compact page without sheet scrolling, including a 480px-height check.
- Free uses a quiet neutral column, Flow receives a soft recommended highlight, and Horizon has a deep theme-tinted column with bright text, accent checkmarks, a subtle header sheen and a matching dark button, including its Current state. Prices remain demonstration placeholders for the paid plans.
- Demo plan switching creates no payment.
- Prepared samples and replays do not consume daily generation allowances.
- Pending generation reserves allowances; failures and ambiguous provider outcomes are handled separately.
- Personal bring-your-own-model/API-key controls have been retired.
- Billing, subscription charging and actual ad delivery are not implemented.

## Connected cloud workflows

- News desk: https://<your-n8n-host>/workflow/qdVgSd8RoLPWMhps
- Podcast studio: https://<your-n8n-host>/workflow/alCqbDEhLlWczybC
- Natural narration: https://<your-n8n-host>/workflow/ALBVDM55ue2ErBm9
- Personal radar: https://<your-n8n-host>/workflow/3ayexitw5VgzfSOc
- All four cloud workflows are published.
- Actual graph snapshots are under workflows/live/ as inactive importable JSON copies.
- The app initiates signed HTTPS requests outward; no public tunnel exposes its private database.
- Ed25519 request signatures, operation checks and expiry checks protect the workflow intake.
- OpenAI and ElevenLabs provider credentials remain in n8n.
- Cheap GPT-6 Luna prepares news/translations and writes Free dialogue.
- GPT-6.1 Sol handles paid dialogue and evidence review.
- Ordinary code handles per-vote arithmetic without an LLM request for every tap.

## New-news intake and preparation

- Put licensed Newstex-style JSONL files in data/incoming/; one article per line.
- Required article data includes a stable ID, headline, original text, source URL, supported language and publication date; image URL is optional.
- Worker detects completed/changed files and skips already imported IDs.
- Original article text is stored separately in the private article database.
- Initial tags and explicit event/translation links are prepared during import.
- News desk corrects presentation grammar, creates tags and three-language summaries, and extracts evidence-linked claims.
- A separate model reviews source accuracy and translation fidelity.
- Backend validates exact quotations, source IDs, numeric values and taxonomy before publication.
- Localized clock punctuation such as Dutch 11.20 uur is handled as a time, not an invented number.
- Original source metadata remains unchanged.
- Explicit duplicate/translation keys can group identical reporting while retaining its editions.
- Semantic candidates can be linked as related coverage; uncertain/new developments remain separate instead of overwriting earlier checked claims.
- Approved news receives Basic spoken summaries in the supported languages.
- Topic/catalog revisions update the app and invalidate stale personal-feed results.
- A live RSS/API publisher adapter or paste-a-URL intake screen is not connected. These would feed the same preparation path.

## Jobs, scheduling and reliability

- Durable SQLite job state survives restarts.
- Jobs freeze profile, catalog, selected reporting and voices.
- Writing, checking, recording, waiting, ready and failed progress states.
- Profile-specific polling, dismissal without cancellation, and appropriate retries.
- Duplicate active generation requests for a listener reuse the existing job.
- Local worker starts preparation within 30 minutes before the selected listening time.
- Timezone-aware due checks include just-after-midnight listening times.
- Daily reservations help prevent duplicate scheduled editions.
- Only complete recorded editions are published as ready.
- Basic audio is prepared first after a confirmed natural-voice queue limit.
- Natural retries use bounded backoff and reuse completed chapters.
- Ambiguous potentially billed audio requests are not automatically repeated.
- Shared script/audio caches include relevant source, language, depth, model and voice information.
- Listener-specific ranking scores do not prevent reuse of otherwise identical reviewed chapter content.
- The local backend and worker must stay running; no phone alarm, push notification or unattended cloud-only hosting is promised.

## Data, architecture and privacy

- React, TypeScript and Vite frontend.
- FastAPI/Pydantic backend, SQLite persistence and a Python worker.
- Native browser audio, local MP3 media and ffmpeg-based episode assembly.
- Supplied catalog: 1,740 articles from six feeds; 1,500 English, 120 Dutch and 120 German originals.
- Prepared corpus includes 238 translation links and 19 reviewed editorial stories; grouping counts are not a ground-truth accuracy score.
- Reporting is a November 2026 dataset replay, not a continuously connected live news service.
- Profiles, preferences, feedback, reading/listening history, bookmarks, editions and jobs persist locally.
- Private source data, databases, media, .env and .secrets are excluded by .gitignore.
- No provider API key is included in public frontend code or workflow exports.
- Local demo account switching is not secure multi-user authentication.
- Dataset rights restrict use and redistribution; original article bodies and event-derived media must not be uploaded with public code.

## Verification and judging materials

- Successful live Podcast Studio writing/source-review smoke.
- Successful live two-voice natural narration smoke: 20.64 seconds.
- Successful real Medium episode: four natural chapters, 4:25 measured, one file and HTTP 206 range playback.
- Successful one-report news preparation: three languages, tags and source-quoted claims; cloud execution about 19.731 seconds.
- Saved-news API transport and profile isolation checked.
- Player, source-review, generation lifecycle, bookmark, stale-sample and preference-change behavior covered by focused UI checks.
- Backend tests cover plans, languages, feedback, jobs, audio validation, source checks, history, saved stories and scheduling.
- Local dataset and synthetic 10× timing measurements: docs/performance-measurements.json.
- Concrete token-cost assumptions/projections: docs/cost-model.md and .json.
- Projected model-token costs are not all-in hosting, n8n or audio invoices.
- Three sourced example checks: docs/evidence-review.md.
- Challenge requirement audit and remaining judging risks: docs/challenge-readiness.md.
- Organizer answer-key/official-release validation and full-corpus grouping accuracy remain unverified; the supplied local files did not contain the answer key.
- No claim or guarantee of winning the hackathon.

## Appearance, interaction and readability

- Appearance opens below Subscription in the profile menu.
- Signal: charcoal and electric lime; Cobalt: blue and white; Edition: paper and vermilion; Afterhours: deep ink and orchid.
- Every theme has Light and Dark modes. Default startup is Signal Light; selecting Afterhours initially uses its designed Dark mode.
- Four illustrated theme choices fit on one sheet. Preview images show the briefing treatment; the active choice has a check indicator.
- Theme and mode apply instantly without a Save button. The browser remembers the selection across reloads and demo-profile switches; changes sync between tabs on the same device.
- Theme selection supports arrow-key navigation, one selected radio choice, trapped dialog focus, Escape to close and return focus.
- Shared semantic tokens replace legacy hardcoded page colors. Text, backgrounds, buttons, cards, borders, selected states, forms and status treatments follow the current palette.
- Publisher, original-language and topic chips over Discover artwork use white text on solid dark backgrounds across all themes. AI-translation badges have their own readable selected treatment.
- Bottom-navigation buttons and labels remain fixed when pressed. Only the icon has a subtle press response; reduced motion disables that response.
- Each tab's selection marker is anchored to that tab. Pressing the active Discover tab preserves the visible card; pressing active Today avoids an unnecessary reload.
- Main navigation exposes its current page to assistive technology.
- Readability checks cover 136 visible screen states across eight theme/mode combinations: 3,128 visible text/background checks with no detected failures in that run. The subsequent pricing revision passed a separate 360 checks across eight states. This is not a complete automated WCAG audit of arbitrary photograph pixels.
- Chooser fit was checked at desktop size and 640px/480px mobile heights; selection/persistence, keyboard behavior and runtime exceptions were also checked.
- Evidence: docs/appearance-checks.json, docs/readability-checks.json, docs/pricing-checks.json and docs/bottom-nav-checks.json.

## Presentation-video production materials

- A complete 150-second / 2:30 storyboard is in docs/presentation-video/STORYBOARD.md.
- Sixteen contiguous timed scenes follow the product journey from listener fit and personalization through discovery, sources, catch-up, preparation, audio, library, themes, plans and efficient architecture.
- Exact presenter narration is in docs/presentation-video/VOICEOVER.md and 15 separate ready-to-synthesize text files in docs/presentation-video/voiceover/.
- Seven seconds at 01:27–01:34 are reserved for actual recorded podcast audio, with no presenter speaking over it.
- Machine-readable scene timing, actions, narration and captions are in docs/presentation-video/timeline.json.
- Browser-capture and editing directions for Claude are in docs/presentation-video/CLAUDE-HANDOFF.md, including continuity, real/demo-state handling and short-screen readability.
- Target output: 1920×1080 at 30 fps, exactly 4,500 frames; transitions and end card are inside the 150-second runtime.
- The presenter voiceover is now generated with Marty — Warm, Confident Narrator on ElevenLabs v4, in a warm, gently encouraging business style. Fifteen selected scene clips and an exact 150-second master are saved locally in ../presentation-audio/, alongside original alternate takes and an editing ZIP. The 01:27–01:34 product-audio window is intentionally silent. This original marketing narration is now uploaded in the private repository’s presentation-audio/ folder at the user’s request; licensed news-derived podcasts remain excluded. The final edited video has not been created.

## Account/key changes and continuation


- Changing an API credential does not delete these local source files, the local database or recorded media.
- n8n credential changes are separate from the account used to chat with Codex.
- New generation requires valid provider credentials and available allowance/billing access.
- A different ChatGPT/Codex account may show different conversation history; do not rely on cross-account chat visibility.
- CONTINUE_HERE.md records paths and continuation state without storing secret values.
- Code, workflow exports, writing guidance and video planning files have been uploaded to the private FuGU-c/foryoucast-project-news repository. Licensed reporting, databases, credentials and generated audio remain local. Image assets are losslessly bundled and materialized automatically by npm build/dev with integrity checks.
- A ready-to-copy JSONL example and article-field guide are in docs/news-intake.example.jsonl and docs/news-intake.md.
- The file-import/publication/three-language recording path has also passed an isolated check using a previously completed cloud review; docs/intake-publication-proof.json records the result without source text or audio bytes.
- Nested model token accounting is retained without saving arbitrary credentials or prompt fields.
- GitHub handoff scope and excluded private assets are documented in docs/github-handoff.md; temporary work recordings are ignored too.
