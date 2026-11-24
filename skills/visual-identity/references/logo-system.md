# Logo system

## Finding the mark

Start from what the name means and write the idea as one sentence before drawing. Dopamine Club: a D and a C cut out of a disc (a weight plate), with a red dot, the dose, in the mouth of the C.

Draw on a grid so the mark can be explained and rebuilt. Dopamine Club uses an 8-unit grid: disc 24u, letter radius 5u, stem, bridge and dot radius 2u, in a 192 viewBox:

```svg
<svg viewBox="0 0 192 192" xmlns="http://www.w3.org/2000/svg">
  <path fill="#0B0D10" fill-rule="evenodd" d="M183.27 56A96 96 0 1 0 183.27 136H144A40 40 0 0 1 144 56ZM32 56H48A40 40 0 0 1 48 136H32Z"/>
  <circle cx="144" cy="96" r="16" fill="#FF3D24"/>
</svg>
```

Keep marks as SVG with exact numbers, so they stay sharp at every size and can sit inline in slides.

Test legibility before going further. Put the mark at 16, 32, 64 and 256 px in one small HTML page, render it with `scripts/shot.ps1`, and look at the result. (Given an `.svg` directly, the script scales it to fill the window, which is how to export large PNGs.) Geometry can work against the letters: a circle made "DC" read as "CD" until the D became a solid knock-out and the C's mouth ran out to the edge. If a letter misreads, fix the drawing, not the caption.

## The version set

Every primary logo needs all of these. They are also the deck's logo section.

| Version | Notes |
|---|---|
| Symbol | Ink, colour and reversed SVGs |
| Horizontal lockup | Symbol and wordmark, three colourways |
| Stacked lockup | Three colourways |
| Wordmark | With its own details slide |
| Badge or seal | Name around the symbol, three colourways |
| Colourways | Ink on chalk (primary), accent on ink, ink on accent, chalk on a mid-tone |
| On photo | Which version to use on light and dark images |
| Clear space | Expressed in a unit of the mark (for example the dot) |
| Minimum size | Print and screen, in mm and px |
| Misuse | Six or so things not to do, shown |
| App icon | Must read at 16 px |

Also export PNGs for image generation: `logo-symbol.png` (1024) and `logo-lockup.png` (2048), on white.

## Variants mean routes

When the user asks for other logo variants, add alternative directions alongside any missing colourways. Read the deck first to see which routes exist, and don't repeat them.

A route must differ in idea and register, not only colour. Each gets its own palette and a place in a final comparison, so the client can choose between positions.

Route families to draw from, choosing what fits the brief:

| Family | Idea | Register |
|---|---|---|
| Symbol-led | A geometric mark holding the concept | Energetic, digital |
| Stencil or stamped wordmark | Lettering cut like a plate or crate | Premium club, calm |
| Mechanism lettering | Custom letters that act out the concept (for example compressing and releasing) | Performance, physical |
| Literal idea | Something true about the name drawn exactly (the dopamine molecule, a local plan, a trade tool) | Clever, ownable |
| Monoline custom lowercase | Built from a few shapes shared with the concept | Boutique, friendly |
| Heritage crest | Shield, varsity or club seal | Tradition, belonging |

Slides per route, labelled "Simulation · Variant X":

- **Short set (4):** divider with the hero mark, logic with a construction drawing, versions as a 4-up, in use.
- **Full set (8):** divider, intent, primary lockup, reversed, versions, palette, applications, compare.

Finish with one overview slide comparing all routes side by side. Say what each route positions the client as, so the choice is a business decision and not a matter of taste. Application sketches for routes can be vector until a route is retained; existing photos carry the primary logo, so photo mock-ups follow once the client picks.

## Drawing

- **Prefer hand-built paths for custom lettering.** They need no font, and they make the mark genuinely the client's. Generate them with a small PowerShell script if the letters are parametric, using invariant-culture number formatting.
- **Fonts are fine for a simulation.** Use a Google Font in SVG `<text>`. `textLength` with `lengthAdjust="spacing"` justifies lines to one width. Say in the notes that a final mark would be redrawn by hand. A Slides deck allows at most 4 faces in total, so count them first.
- **Always look at it.** Render each new mark with `scripts/shot.ps1`, read the PNG, and iterate. A logo that has only been reasoned about is usually wrong in some small, visible way.
