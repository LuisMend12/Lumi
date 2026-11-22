---
name: Lumi
description: Winter walking routes around BU, reported the way Boston TV covers a snowstorm.
colors:
  navy: "#0b2545"
  storm: "#1d4e89"
  sky: "#8ecae6"
  ice: "#eaf4fa"
  snow: "#f4f9fc"
  frost: "#cfe3ef"
  white: "#ffffff"
  amber: "#ffb703"
typography:
  wordmark:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.01em"
  poster-figure:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 800
    lineHeight: 0.86
    letterSpacing: "-0.02em"
    fontFeature: "\"tnum\", \"lnum\""
  chyron-title:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.05em"
  label:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    letterSpacing: "0.05em"
  tag:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    letterSpacing: "0.1em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.43
    fontFeature: "\"tnum\", \"lnum\""
  caption:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.375
rounded:
  tag: "2px"
  chip: "6px"
  card: "8px"
  control: "12px"
  sheet: "16px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  chyron:
    backgroundColor: "{colors.white}"
    textColor: "{colors.navy}"
    rounded: "{rounded.card}"
    padding: "10px 12px"
  chyron-selected-shortest:
    backgroundColor: "{colors.sky}"
    textColor: "{colors.navy}"
    rounded: "{rounded.card}"
    padding: "12px 16px"
  chyron-selected-safer:
    backgroundColor: "{colors.storm}"
    textColor: "{colors.white}"
    rounded: "{rounded.card}"
    padding: "12px 16px"
  chyron-selected-accessible:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.card}"
    padding: "12px 16px"
  button-report:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.card}"
    padding: "12px 20px"
  button-report-hover:
    backgroundColor: "{colors.storm}"
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  button-outline:
    backgroundColor: "{colors.white}"
    textColor: "{colors.navy}"
    rounded: "{rounded.pill}"
    padding: "6px 16px"
  button-outline-hover:
    backgroundColor: "{colors.ice}"
  button-pill:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  button-pill-hover:
    backgroundColor: "{colors.storm}"
  toggle-pill:
    backgroundColor: "{colors.white}"
    textColor: "{colors.navy}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  toggle-pill-active:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
  select:
    backgroundColor: "{colors.white}"
    textColor: "{colors.navy}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  live-chip:
    backgroundColor: "{colors.white}"
    textColor: "{colors.storm}"
    rounded: "{rounded.chip}"
    height: "32px"
  report-crawl:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    height: "40px"
  tag-simulated:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    typography: "{typography.tag}"
    rounded: "{rounded.tag}"
    padding: "2px 6px"
  hint:
    backgroundColor: "{colors.ice}"
    textColor: "{colors.navy}"
    rounded: "{rounded.card}"
    padding: "8px 12px"
---

# Design System: Lumi

## Overview

**Creative North Star: "Storm Center"**

Lumi reports the sidewalks the way Boston TV reports a snowstorm: live, bold, always labeled. The screen is a broadcast. A muted, ice-toned map is the studio backdrop; the colour belongs to what is happening on it, the routes and the reports. Over it sit the pieces of a weather desk: a LIVE chip top-left, a navy report crawl along the map's bottom edge, and the three route modes as lower-third chyrons, the chosen one flooded with its mode's colour and its walking minutes at poster scale.

The world is light blue, white and navy, and nothing else carries meaning except the report states. Barlow Condensed in bold caps speaks for names, chyrons and numbers; Barlow does the reading. Every figure is tabular, because the numbers are the broadcast. Density is phone-first: map on top, sheet below; on desktop the sheet becomes a 384px left column.

Honesty is visual, not just verbal. A report's certainty is drawn as a mark in a fixed cell (filled, hollow, dotted) and named in words beside it; simulated data wears the same navy SIMULATED tag wherever it appears.

**Key Characteristics:**
- Muted ice basemap; routes and report marks carry the colour.
- Broadcast furniture: LIVE chip, navy crawl, lower-third chyrons.
- Condensed bold caps for names and numbers, tabular figures everywhere.
- Mode colour floods the selected chyron; idle chyrons are white with a frost hairline.
- Verification as shape in a fixed cell, always paired with a text label.

## Colors

A cold, three-blue broadcast palette on white and snow, with amber held back for report state.

### Primary
- **Broadcast Navy** (navy): ink, wordmark, the crawl, the Report button, primary buttons, the SIMULATED tag, the Accessible route and its chyron flood, the A pin. The anchor of every screen.
- **Storm Blue** (storm): secondary text (never grey), hover state of navy buttons, the Safer route and its chyron flood, hint links.

### Secondary
- **Studio Sky** (sky): the Shortest route and its flood (with navy ink), the crawl's LIVE block, report times in the crawl, the confirmed mark on navy, text selection, and the focus ring on the navy Report button (drawn inside it).

### Tertiary
- **Report Amber** (amber): report state only. The hollow unverified mark, the "near you" dot, and the nearby-sidewalk highlight on the map. Never decoration, never a button.

### Neutral
- **White** (white): sheet, idle chyrons, panels, chips, the B pin.
- **Snow** (snow): page background, the collapsed legend, quiet hover fill.
- **Ice** (ice): hint and status panels, the map container behind tiles, the loading skeleton.
- **Frost** (frost): hairlines and idle borders on chyrons, selects, toggles, panels; scrollbar thumb.

### Named Rules
**The Navy Ring Rule.** The focus ring is navy everywhere (3px, 2px offset). Only the navy Report button takes a sky ring, drawn inside it.

**The Storm-Not-Grey Rule.** Secondary text is storm blue. There is no grey in the palette; `--muted` is an alias of storm.

**The Report-State Rule.** Amber marks report state only (unverified, nearby). It never fills a control or a surface.

**The Backdrop Rule.** The OSM tiles are filtered into the palette (`grayscale(1) brightness(1.06) contrast(0.82) sepia(0.25) hue-rotate(170deg) saturate(1.4)`), and only the tile pane. Routes, markers and overlays are never filtered.

## Typography

**Display Font:** Barlow Condensed (weights 600/700/800, with system-ui)
**Body Font:** Barlow (weights 400–700, with system-ui)

**Character:** A sports-and-weather broadcast pairing: the condensed face shouts names and numbers in caps, the regular face reads calmly underneath. Tabular, lining figures are set on `body` so every count, time and distance lines up.

### Hierarchy
- **Wordmark** (800, 40px, line-height 1, -0.01em): "Lumi" at the head of the sheet only.
- **Poster figure** (800, 64px, line-height 0.86, -0.02em): walking minutes inside the selected chyron, with a 20px caps "MIN" at 80% opacity.
- **Chyron title** (700, 19px, 0.05em, uppercase): mode names on chyrons.
- **Label** (700, 15px, 0.04–0.05em, uppercase): From/To labels, legend summary, demo pills, crawl text (600), the Report button (18px).
- **Chip** (700, 13px, 0.06em, uppercase; LIVE block 0.12em): the LIVE chip on the map.
- **Tag** (700, 11–12px, 0.1–0.12em, uppercase): SIMULATED and SELECTED tags.
- **Body** (400, 14px): sheet copy, hints, selects, toggles.
- **Caption** (400, 13px, snug): mode summaries under chyron titles; 12px for footnotes.

### Named Rules
**The Caps-Speak Rule.** Names, labels and numbers are Barlow Condensed in caps with positive tracking; sentences are Barlow in sentence case. Never set a sentence in condensed caps.

**The Tabular Rule.** All figures are tabular lining numerals; nothing in the UI uses proportional digits.

## Layout

Phone: a full-height flex column. The map fills the top (`order-1`), the sheet sits below capped at 58dvh, scrolling internally; the tagline under the wordmark is desktop-only, so on phones its space goes to the chyrons. Desktop (md, 768px): a row, the sheet becomes a fixed 384px left column at full height, padding 24px instead of 16px.

Sheet order: wordmark, mock banner (when mocked), the route (From/To pickers, or once a route exists a one-line A → B summary), then the chyrons immediately after, so they stay in view on a phone. The three chyrons stand by with their definitions before any route exists. The map fits each new route (24px inset, 64px top to clear the LIVE chip, 120px bottom to clear the Report button and crawl).

Map furniture is pinned: LIVE chip top-left (16px inset), zoom top-right (40px buttons), the 40px crawl full-width along the map's bottom edge, the Report button bottom-right just above the crawl (56px from bottom). Leaflet's attribution is lifted 40px to clear the crawl.

Spacing runs on a 4px base. Sheet sections are separated by 16px; lists of chyrons by 8px; inline groups by 8–12px. Chyron grids are `1fr auto`: name and summary left, distance and minutes right.

## Elevation & Depth

Mostly flat: surfaces sit on white and snow with frost hairlines. Shadow is reserved for things floating over the map, always tinted navy, never black.

### Shadow Vocabulary
- **Sheet edge** (`0 -8px 24px rgba(16,42,67,0.12)`; desktop `8px 0 24px rgba(16,42,67,0.08)`): separates the sheet from the map.
- **Map chip** (`0 4px 14px rgba(11,37,69,0.12)`): the LIVE chip.
- **Floating control** (`0 6px 18px rgba(11,37,69,0.35)`): the Report button; the nearby pill uses `0 6px 18px rgba(16,42,67,0.22)`.
- **Overlay sheet** (`0 -12px 32px rgba(16,42,67,0.25)`): the report sheet and nearby prompt (`0 8px 24px rgba(16,42,67,0.2)`).
- **Pin** (`0 2px 6px rgba(16,42,67,0.35)`): A/B pins.

### Named Rules
**The Over-The-Map Rule.** Only elements floating over the map cast a shadow. Cards inside the sheet are flat with a frost border.

## Shapes

Gently rounded, never sharp, never bubbly. 2px tags, 6px chip, 8px chyrons/panels/Report button, 12px selects and primary buttons, 16px sheets and prompts, full pills for toggles, sign-in, the nearby pill and demo buttons. Borders are 1px frost hairlines on panels and chyrons, 2px frost on interactive outlines (selects, toggles, outline buttons), turning navy on hover or focus. Pins are 28px circles with a 3px contrasting ring.

Map lines are round-capped. Modes differ by more than colour: Shortest solid sky over a navy casing (32% opacity), Safer dotted storm (`1 10`) over white, Accessible dashed navy (`12 8`) over white. Selected line weight 7, idle 4 at 75% opacity; casing is weight + 5, at 70% of its opacity when idle. Legend swatches carry the same casings.

## Components

### Mode Chyrons (signature)
Lower-third broadcast bars, one per mode.
- **Idle:** white, 1px frost border, 8px radius, 10px 12px padding; a 28×10 line swatch, condensed caps name, minutes and metres right-aligned, storm caption below. Hover turns the border storm.
- **Selected:** floods with the mode's colour (sky with navy ink; storm or navy with white ink), 12px 16px padding, a bordered SELECTED tag at half-opacity currentColor, minutes at poster scale, summary at max 11rem.

### Buttons
- **Report button:** navy, 8px radius, 12px 20px, condensed caps 18px, an inline 18px stroke alert glyph (circle with a bar and dot); hover storm; focus ring sky drawn inside the button (`outline-offset: -5px`), the one exception to the global navy ring.
- **Primary:** navy, 12px radius, full width, semibold, white; disabled at 40% opacity.
- **Outline:** 2px navy border, pill or 12px radius, navy text, hover ice fill (Sign in, vote "No").
- **Demo pill:** navy pill, condensed caps 15px, hover storm; disabled goes transparent with storm text and a frost ring, so it stays readable.

### Toggles
Pills with a 2px frost border and navy text; hover border navy; pressed state fills navy with white text (`aria-pressed`).

### Inputs / Fields
From/To labels are condensed caps (label role) with their lettered pins, set in a column beside the selects. Native selects, white, 2px frost border, 12px radius, 8px 12px. Focus swaps the border to navy (no outline). The photo field is a dashed 2px frost drop area on snow, navy border on hover.

### Live Chip
White 32px chip, 6px radius, the navy LIVE block flush-left in white caps, then storm "SIDEWALK REPORTS · n" and a navy "UPDATED <time>" once reports have loaded. Non-interactive.

### Report Crawl
Navy 40px strip, a sky LIVE block flush-left, items in condensed 15px semibold: verification mark, SIMULATED tag (white/15% on navy), state text, sky time; a 40%-opacity middle dot sits between items, never after the last. It loops (a duplicated track, `translateX(-50%)` over 40s linear) only when the reports overflow the strip; when they fit it sits still as one copy. Hover pauses it. Under reduced motion it holds still and becomes hand-scrollable. With no reports it reads "No sidewalk reports right now."

### Verification Marks
A 14px fixed cell. Confirmed: filled (navy on the map with a white ring; sky in the crawl). Unverified: hollow white with an amber ring. Under review: hollow with a dotted (`1 4` on map, `1 3` in crawl) navy or white ring. Always followed by its text label.

### SIMULATED Tag
Navy, 2px radius, condensed 12px caps, 0.1em tracking, white. Used everywhere simulated data appears; inverted to white/15% inside the navy crawl.

### Panels
Hints and statuses: ice fill, 8px radius, 8px 12px, navy text, no border. Info panels, the mock banner and the demo panel: white with a 1px frost hairline, 8px radius, led by the navy SIMULATED tag where the content is simulated. Legend: a snow `details` with a condensed caps summary.

### Route Summary
Once a route exists, From/To fold into one line: the A pin and start name, a storm arrow, the B pin and end name, each name kept unbroken (`nowrap`) so the line wraps only between them; a storm underlined "Edit route" link sits right. Editing reopens the pickers with a "Done editing" link.

## Do's and Don'ts

### Do:
- **Do** let the mode's own colour flood the chosen chyron, and set its minutes at 64px poster scale.
- **Do** set every name, label and number in Barlow Condensed caps with positive tracking, and keep figures tabular.
- **Do** draw verification as filled / hollow / dotted in a fixed cell and name the state in words beside it.
- **Do** wear the navy SIMULATED tag on every piece of simulated data.
- **Do** use storm blue for secondary text and frost for hairlines.
- **Do** filter only the tile pane into the palette, so routes and marks keep their colour.
- **Do** tint every shadow navy and keep shadows to elements floating over the map.
- **Do** distinguish route modes by dash pattern and casing as well as colour.

### Don't:
- **Don't** introduce grey text or grey surfaces; the neutrals are snow, ice and frost.
- **Don't** use amber outside report state.
- **Don't** shadow cards inside the sheet.
- **Don't** animate the crawl when its content fits, or under reduced motion.
- **Don't** show a report's state by colour alone, or present an unverified report as fact.
