# PitchVision design system

The interface is a ground scoreboard put to work: figures sit in labelled windows on a painted board, and the layout is held together by one-pixel rules instead of shadows or cards.

## Colour

| Role | Dark board | Whitewash |
|---|---|---|
| Background | #0D1310 | #F4F6F1 |
| Surface | #121A16 | #FFFFFF |
| Ink | #F4F6F1 | #0D1310 |
| Secondary ink | #AAB5AB | #47524A |
| Rule | rgba(244,246,241,.14) | rgba(13,19,16,.14) |
| Number plate | #050806 | #0D1310 |
| Accent (numeral yellow) | #F2C230 | #F2C230 |
| Positive | #4FAE78 | #1F6B45 |
| Negative | #EC6A5F | #B3261E |
| Pitch strip | #B9A877 | #D8C98F |
| Outfield | #1B4A33 | #2F7A52 |

Number plates are dark with light numerals in both themes. Violet is not used.

## Type

Text is set in the system face (San Francisco on Apple devices) with Barlow as the fallback. Labels and numerals use Barlow Condensed in capitals. Three sizes only: 12 px labels, 15 px text, 32 px figures. Rank comes from weight, case and rules. Numbers use tabular figures.

## Components

Number plate and window, ruled section heading, tab strip, data table with hover link to the pitch or ground drawing, over strip (six fixed cells, wides and no-balls in narrow side cells), pitch map, ground drawing, DRS side and front views. Buttons are 8 px radius with a 1 px lift on hover and a press on click. Linked names draw an underline on hover. Controls are 44 px tall on touch screens.

## Motion

A figure slides into its plate in 140 ms when it changes. Pages rise in over 180 ms. Calculators recompute as inputs change. Reduced-motion preferences switch all of it off.

## Source of truth

Tokens: `frontend/tailwind.config.js` and `frontend/src/index.css`. Components: `frontend/src/components/`. The direction contract is in `.impeccable/surfaces/frontend-src.md`.
