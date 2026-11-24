# Deck structure

The brand deck follows this order. The Dopamine Club deck ran to about 90 slides and the user was happy with that length. Adapt the application list to the client's sector.

| Section | Slides |
|---|---|
| Opening | Cover, contents, intro |
| 01 Concept | Divider, context, the idea, positioning, a diagram of the idea, values, audience, voice, manifesto, moodboard, inspiration |
| 02 Logo | Divider, brief, exploration, shortlist, reveal (the process slides: the user asked for these), construction, measurements, semiotics, the signature detail, wordmark, wordmark details, horizontal × 3 colourways, stacked × 3, badge × 3, colour variations, clear space, minimum size, on photo, misuse, app icon |
| 03 Typography | Divider, primary face, weights, character set, secondary face, hierarchy, type in use, type rules |
| 04 Identity | Divider, palette, proportions, pairings, pattern (bento), pattern (full bleed), supergraphic, wayfinding, photo direction, photo rules |
| 05 Visuals | Divider, then about 25 full-image application slides: for a gym that was athletes, cards, stationery, facade, shopfront, poster wall, metro, lightbox, posters, apparel, bags, bottles, cap, socks, shaker, plates, app screens, social, campaign |
| Routes | One section per alternative logo route (see logo-system.md) |
| End | Credits, closing |

## Credits slide

Title: "Brand identity by BAAK Studio." Use `assets/baak-studio-logo.png`, captioned "Architecture · Brand".

- [Name], Architect, [email]
- Ahmed Blaich, Architect, [email] (the studio address; no personal one is known)
- 18, Impasse Shéhérazade, El Menzah IV, Tunis 1004
- [phone]

Also credit photographers of any free stock used in the deck.

## Working in the Slides type

The type's own instructions are the authority on the format; read them when you open the deck. These are the things that have actually gone wrong:

- **Fixed pixel sizes on images.** Percent sizes on images in a grid were dropped on read and broke a moodboard ("FIX MOODBOARD LAYOUT"). Compute the tile size in px.
- **No text under 24 px**, and at most 200 elements per slide. A badge with one rotated element per letter uses a lot of them.
- **Logos inline.** Paste the mark as `<svg>` with its path rather than uploading a PNG, so it can be recoloured per slide.
- **Upload compressed JPEGs** (`scripts/compress-images.ps1`). Reuse the same `/_blob/` id across slides.
- **Page numbers are hard-coded text**, and so are the contents page numbers. Adding slides in the middle means updating the later ones.
- **Don't re-render the deck to check it** unless the user asks; the type's instructions say so. Check marks and images before they go in.
- **Others edit the deck.** A publish can be refused or warn about a newer version. Read again, merge your change onto theirs, and tell the user if something of theirs may have been affected.

## Boards

For a one-page overview, use the Design type with one artboard per theme. The set the user asked to include in the deck: Main, Symbol, Lockups, Colour, Type, Photography, Plates, Wall, Apparel, Poster 1, Poster 2, App, Social.
