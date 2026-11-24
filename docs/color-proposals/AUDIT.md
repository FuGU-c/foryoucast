# ForYouCast color audit and proposals

Scope: existing frontend styles, including Today, Discover, player, Preferences, voice selection, History, saved news, reading/transcript sheets, subscription comparison and generation states. **Proposal only; no application styles changed.**

## Findings

- Thirteen CSS files contain 1,305 hexadecimal color occurrences and 1,071 distinct literal spellings, including alpha/shorthand variants. These are not 1,071 meaningful brand colors; many are near-duplicates.
- `styles.css` contributes 475 occurrences; `professional-theme.css` contributes 379. The latter contains two root token declarations layered over the root in the former.
- Original paper/sage/coral values coexist with blue overrides and later indigo/lavender/champagne styling. `--orange` is also used for blue, so a token name no longer describes its purpose.
- Components independently define off-white cards, green/blue secondary text, form borders, chips, timers, reader panels and selected states. Specificity and import order determine which theme wins.
- Source-review, generation, voice controls, subscription and waveform styles add local colors instead of using shared role-based values.
- Illustrative contrast failures: `#82847B` on `#F8F7F3` = 3.54:1; `#6B7789` on `#FAFBFD` = 4.39:1; `#7C8796` on white = 3.64:1. These fail the 4.5:1 normal-text target. Large text has different requirements.
- White overlay controls on publisher photographs need a predictable dark scrim or sufficient local protection; a text shadow alone does not guarantee contrast over every photo.
- Status, selected and disabled states need consistent non-color cues. Retain icons, labels, filled thumbs and aria states; don't distinguish states by hue alone.
- There is no complete current dark theme. The proposals include dark token variants, but adding an application appearance control requires the user's selection and the implementation phase.

## Four directions

1. **Atlantic — recommended:** trustworthy blue, deep teal secondary and restrained terracotta accent. Strong fit with sourced news and ForYouCast's existing blue mark. Calm surfaces, clear primary actions.
2. **Evergreen:** editorial forest green, warm brown secondary and ochre accent on paper. A quieter, reading-oriented experience with a warmer character.
3. **Aubergine:** plum, slate-blue secondary and copper accent. More distinctive and premium; works well for an audio product without making every component colorful.
4. **Midnight Studio:** deep teal, violet secondary/accent and cool slate. A modern listening-first direction, especially effective in dark mode.

`index.html` shows all four on the same briefing, story, preference and player layout. Switch Light/Dark at the top. Each proposal exposes its complete role/state values. `four-palettes.png` provides a static light comparison. `palettes.json` is the complete specification, not an installed theme.

## Roles and checks

- Primary actions use `primary`, `primary-hover`, `primary-active` and `on-primary`.
- Secondary and accent are separate; accents are reserved for playback or sparse editorial highlights.
- Page, panel and quiet fills use `background`, `surface` and `surface-subtle`.
- Typography uses `text`, `text-secondary` and `text-muted`.
- Dividers use `border`; input outlines use stronger `border-control`.
- Selected content uses `selected` and `on-selected`; keyboard focus uses `focus`.
- Disabled controls use `disabled` and `on-disabled`, with actual disabled semantics. Disabled controls are contrast exemptions, not examples of active text.
- Success, warning and error each have a foreground and background pair.
- All eight palette/mode variants passed the 104 configured checks in `contrast-checks.json`: normal text and action/status labels at 4.5:1; focus/control outlines at 3:1 against the specified surface. Ratios are evaluated before rounding.
- These are token-pair checks, not an assertion of whole-app WCAG compliance. Actual typography, photographs, gradients, focus adjacency, forms and every final component state must be tested after implementation.

## Implementation after selection

1. Install one semantic light/dark token map, keeping brand source assets intact.
2. Replace the stacked theme overrides, including the misleading `--orange` mapping.
3. Migrate common controls and every page's isolated colors to the same roles.
4. Keep Free neutral, Flow primary and Horizon premium through controlled surface/typography emphasis, without introducing unrelated palettes.
5. Preserve the existing layout, native audio controls, reaction animation, bookmarks, feedback logic and responsiveness.
6. Check normal/hover/pressed/selected/disabled/focus/error states and both appearances; then run the existing playback, generation and saved-story regression checks.

Waiting for palette approval. No implementation begins until a palette is selected.
