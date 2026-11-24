# ForYouCast: theme proposals, round two

Supersedes the previous four proposals. Product styles are untouched pending user selection.

1. **Signal (recommended):** charcoal, clean white and electric lime. High-contrast dark briefing card; lime is reserved for the primary listening action. The rest of the interface stays calm.
2. **Cobalt:** saturated blue and optical white. A brighter, familiar consumer-app direction with a clear action hierarchy.
3. **Edition:** warm paper, ink and vermilion. An editorial news identity; soft apricot inside the dark player card avoids competing red accents.
4. **Afterhours:** deep ink and luminous orchid, designed in dark mode. Restrained silver supports long listening sessions.

All show the same representative screen and components. index.html includes designed, light and dark appearance choices, editable search fields, selected/disabled controls, hover/active/focus states, and status colors. The pictured stories, dates and playback are mock content; preview buttons don't generate audio.

palettes.json defines semantic roles for primary/hover/active/disabled, secondary, accent, background/surfaces, text, borders, selected, focus, hero and status treatments in both modes. contrast-checks.json verifies 112 configured text/background pairs against 4.5:1. Disabled controls are exempt; decorative accents and borders are not presented as normal text. This is a palette/component check, not a claim that the whole app has passed WCAG AA.

The earlier audit still applies: repeated CSS overrides and hardcoded greens, coral, blue and purple compete across pages. Muted labels are too low contrast in several components. After selection, replace those with a single semantic token layer, preserving layout and behavior, then check actual page and component states.
