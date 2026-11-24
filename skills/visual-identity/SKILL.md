---
name: visual-identity
description: Build or extend a complete brand and visual identity (identité visuelle, charte graphique) for any client - concept, logo, logo variants and alternative routes, typography, palette, patterns, mock-ups and campaign visuals, a brand book deck, brand boards and short brand videos or reels. Use this whenever the user asks for a logo, a logo variant, branding, an identity, a brand book or brand deck, brand mock-ups or campaign images, or a strobe or reel for a brand, and whenever they paste a Behance, Instagram or Pinterest link or an image as a reference for brand work, even with no other words.
---

# Visual identity

The user (BAAK STUDIO, architecture and brand, Tunis) builds identities for clients and judges them against Behance-level work. They write short all-caps messages, often only a link or an image. Read a bare link as "study this and apply it to what we are doing": look at it, act, show the result. Ask only when a decision truly blocks the work, because a question costs them more than a draft they can redirect.

## What they have corrected before

Each of these came from a real correction, so treat them as the bar for a first pass.

- **Match the reference's visual language, not only its layout.** "NO THIS STYLE OF VISUALS" came after images that had the right subjects but the wrong light, colour and mood. Write the language down (light, backdrop, palette, wardrobe, grain, negative space) and hold every image to it.
- **The sector must be obvious at a glance.** "GYM BRO GO ON THE GYM" came after a first pass that felt like a generic brand. Show the client's real world: the equipment, the people, the place.
- **Use real-looking imagery.** Grey placeholders and flat vector scenes read as unfinished. Use free photography and generated images (see [image-generation](references/image-generation.md)).
- **The logo must be right in every image.** "FIX THIS LOGO" came from a generated mock-up that bent a letter. Inspect each logo after generating it, before it reaches a slide.
- **More is welcome.** "WE DONT HAVE A LIMIT" and "25 VISUALS SLIDES": a rich application section is what makes the deck feel real. Don't trim for brevity.
- **"Variantes de logo" means new directions**, not only colourways. Check what the deck already has first.

## The order of work

The deck reads in this order and the user asked for it explicitly: **Concept → Logo → Typography → Identity → Visuals**, then alternative routes, credits, closing. Work in the same order so each stage inherits the idea from the last.

1. **Study the references.** Read [reference-study](references/reference-study.md) when any link or image comes in.
2. **Concept.** One idea in one sentence, plus a short line the client can own. Dopamine Club: the red dot is the dose, "Earned, not scrolled." Every later choice should trace back to this sentence; that is what stops the identity feeling like a template.
3. **Logo.** Grid-built mark, full version set, then routes. Read [logo-system](references/logo-system.md).
4. **Typography and colour.** One or two families (one display, one mono or text). One dark, one light, one mid-tone, one accent. Give each colour a name and a job. Keep one signature detail running through everything, such as the red full stop that ends headlines.
5. **Graphic system.** A pattern, a supergraphic and wayfinding, all derived from the mark's geometry.
6. **Visuals.** Generated and sourced images, in the reference's language. Read [image-generation](references/image-generation.md).
7. **Deck and boards.** Read [deck-structure](references/deck-structure.md).
8. **Motion, when asked.** Read [video-edits](references/video-edits.md). Three working templates are in `assets/video-templates/`.

The user may jump to any stage. Start there and reuse what exists rather than rebuilding it.

## Facts

Don't invent details about the client. Use bracketed placeholders such as `[@handle]`, `[Address]`, `[date]`, `Coach [Name]`, and list them in your reply so they get filled in. Don't invent statistics or quotes. Project-specific claims stay out of the deck until the user supplies them.

## Originality

References teach structure, register and logic. Never trace or reproduce another studio's mark, lettering or layout. When a route leans on a reference, say so on the slide, in this form: "Reference: the heat-as-colour logic of [project]. Own lettering; no element of their mark is reproduced."

## Output

- Publish finished work as artifacts so the user gets a link, using the Artifact tool's quickstart for the right type (Slides for the deck, Design for boards, a plain page for video). Artifacts start private; tell the user that others need the Share menu.
- The user and other sessions edit the same deck. Read `project/deck.json` again right before publishing, and merge onto what is there.
- When the logo or palette changes, say what else is now out of date (generated images keep the old mark).
- End with what still needs the user: placeholders, routes to choose, anything not checked.

## This machine

- `ffmpeg` and ImageMagick are not installed. Use the scripts below, plus the browser for video.
- Numbers from PowerShell can come out as `5,243` under the French locale, which breaks SVG paths. Format with `[Globalization.CultureInfo]::InvariantCulture`.
- PowerShell variables are case-insensitive: `$r` and `$R` are the same variable.
- Windows PowerShell and Chrome can't reach paths over about 260 characters, and report them as "not found" or simply produce nothing. Session scratchpad folders can be that long, so keep working images in a shorter folder.

Scripts in `C:\Users\sbs\.claude\skills\visual-identity\scripts\`, all run with `powershell -ExecutionPolicy Bypass -File`:

| Script | Use |
|---|---|
| `shot.ps1 -Html page.html -Size 1080,1350 -Out page.png [-Hash t3.2]` | Render a local HTML or SVG page to PNG with headless Chrome. Use it to look at marks and video frames, and to export logo PNGs. |
| `compress-images.ps1 -In folder -Out folder [-MaxSide 1600] [-Quality 82]` | Resize and convert images to JPEG before uploading them to a deck or page. |
| `luminance.ps1 -In folder` | List images from darkest to lightest, to order fast edits. |

`assets/baak-studio-logo.png` is the studio's logo for the credits slide.
