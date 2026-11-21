# Claude handoff: capture and assemble the Seranews demo

Create a polished **exactly 2:30** product video using actual Seranews browser footage. Use STORYBOARD.md as the creative plan and timeline.json as the timing source. The voiceover folder contains the exact presenter text per scene. This is a capture/editing task; do not redesign the application or change its feature behavior.

## Files and app

- App folder: <local-outputs-folder>/liquid-briefing
- Demo URL: http://127.0.0.1:8000
- Start if needed: ./start-demo.ps1 -SkipInstall -NoBrowser from the app folder.
- Current product behavior: ALL_FEATURES.md and CONTINUE_HERE.md.
- Storyboard, narration and timeline: docs/presentation-video/.
- Use the existing recorded English Medium/Flow natural episode or another verified natural sample for scene 10. Do not initiate new paid generation merely to capture a spinner.

## Continuity and preparation

1. Record from an isolated browser profile and a disposable copy of the demo data where actions will change saved preferences, votes, history, schedules or stored audio. Preserve the master blank New listener and the main prepared episodes.
2. Use one main configured English listener (Medium user) for Discover, sources, playback and the library. The four archetypes and blank onboarding are brief labelled inserts, not a claim that their saved audio was produced by the immediately preceding click.
3. Preselect a real story with a readable source, relevant language editions and an AI-translated summary label. Preselect a natural-audio excerpt with source attribution and preferably a speaker change. Check all media before recording.
4. A Since your last visit section can legitimately be caught up. Show that real state if no verified follow-up exists; do not invent a news development, rewrite a source or forge history to make a more dramatic shot.
5. Record any genuine generation progression separately. Edit it with “Generation condensed”; do not imply a complete natural podcast is generated in three seconds. Scheduled preparation needs the demo worker running and is not a phone alarm or push service.
6. For Keep summary only, use an expendable copy of an edition, not the audio needed for the rest of the recording.

## Visual treatment

- Final canvas: 1920×1080, 30 fps, exactly 4,500 frames.
- Keep a fixed phone crop, ideally captured at high pixel density. Frame the app without tabs/address bars, desktop clutter or unrelated personal content.
- Begin with Signal Light for clarity. Keep the main footage in that theme until the Appearance montage, then choose one consistent final look.
- Use a neutral background and generous space. Place a short caption beside the phone, not over article text. Use occasional tight crops for a source link, topic adjustment or player seek; return to the same phone position.
- Captions are the storyboard’s short phrases, normally one line and no more than two. Do not layer a second transcript of the entire narrator over the UI. Optional subtitles can occupy a separate safe area.
- One action at a time: deliberate cursor, a brief pause before activation, and enough settling time to read the result. Avoid rapid scrolling, cursor circling and exaggerated click rings.
- Use matched cuts or brief restrained dissolves. All transitions are contained inside the 150-second timeline, not appended between scenes. Do not add a separate opening bumper or credit sequence.
- In scene 8, capture only the n8n node canvas. Do not show keys, credential forms, secret URLs or execution payloads.
- Scene 13 must show Signal, Cobalt, Edition and Afterhours, plus one Light/Dark change. Do not cycle through all eight modes at high speed.
- Scene 14 shows all three plans together: $0, $ A BIT, $ A LOT. Paid amounts remain placeholders; show no live checkout or claimed finalized price.

## Useful browser targets

- Profile picker: [aria-label="Change listener profile"]
- Navigation: [aria-label="Main navigation"] buttons Today / Discover / Podcasts
- Preferences: [aria-label="Open settings"]
- Appearance: [aria-label="Open appearance"]; [role="radio"] for the four theme cards
- Subscription: [aria-label="Open subscription"]
- Search/filter drawer: [aria-label="Search and filter stories"]
- Feedback: [aria-label="More like this"], [aria-label="Less like this"]
- Bookmark: [aria-label="Save story"] (becomes Remove from saved stories)
- Story: [aria-label="Read story and sources"]
- Reader: [aria-label="Source article"]; Summary / Full article mode buttons; .reader-actions
- History: [aria-label="Reading history"]; Recently viewed / Saved tabs
- Recorded edition: [aria-label="Play this edition"] or [aria-label="Play edition"]
- Player: [aria-label="Expand player"], [aria-label="Playback speed"], [aria-label="Sleep timer"]
- Library: Today / This week / This month / All editions; Edition options → Keep summary only

Resolve current accessible names from the actual DOM before acting. Use the live layout, not stale coordinates. The source reader has stacked primary/secondary actions; the Script & sources dialog no longer has redundant download buttons.

## Voice and audio assembly

**Update: the narration is already generated. Read GENERATED-AUDIO.md first and use the existing 150-second master or scene pack from the repository’s presentation-audio/ folder (also available in the creator’s local export folder). Do not spend credits generating the following scripts again. The original generation instructions below are a reference only.**

1. Generate the 15 narrator segments from voiceover/*.txt using one ElevenLabs voice. Do not synthesize timestamps or production notes. Scene 10 has no narrator file by design.
2. Fit each segment inside its assigned interval. Preserve pronunciation and natural pacing. If a clip exceeds its slot, regenerate or shorten the line without changing its factual meaning; record any wording revision in the delivery notes rather than cutting the last word. Avoid a hard word boundary exactly at a scene cut.
3. At 01:27, silence the presenter and background music. Insert the actual seven-second app podcast excerpt, with a small “Actual demo audio · AI voices” label. Product playback time and displayed chapter should match the excerpt.
4. At 01:34, return to the presenter and mute the app audio. Keep later click/voice-preview sounds muted. Music, if used, stays quiet beneath the presenter and must not mask source names or language names.
5. Use one consistent delivery level and gentle fades. Preserve the quiet final logo hold from 02:28 to 02:30. End the file at exactly 150.000 seconds, with no black tail.

## Final checks

- The argument is understandable without seeing the cursor: personal fit, sources, useful memory, a listenable result, then product viability.
- All 16 scene intervals are contiguous and total 150 seconds.
- Actual podcast audio is audible without the presenter talking over it.
- UI text remains readable; no hover/pressed state, loading placeholder or modal transition is frozen accidentally in the final edit.
- Natural podcast output is shown as a single recorded episode, with chapter seeking rather than disconnected audio cards.
- No claim of independent fact verification, guaranteed duplicate-grouping accuracy, finalized paid prices, measured cost savings, production billing/ad serving, or fully cloud-hosted operation.
- Use this recording for the authorized hackathon presentation. The supplied dataset is event-restricted; do not publish an article-text-heavy public version without checking the organizer’s reuse permission.

Deliver: the final video, separate presenter audio clips, timeline/project data, and a short note of any storyboard feature that could not be recorded honestly from the running app.
