# Images

## Codex

The user wants images generated with Codex. It is at `C:\Users\sbs\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe` and can see attached logos, which keeps the mark close to correct.

Set up one folder for the project holding `logo-symbol.png` and `logo-lockup.png`, then write a prompt file per batch and run it in the background so it doesn't block other work:

```bash
codex exec --skip-git-repo-check -C "<folder>" -s workspace-write -i logo-symbol.png -i logo-lockup.png -o last-message-a.txt - < prompt-a.txt
```

Send 3 to 7 images per batch, and run several batches at once for a big round. A background run reports when it exits; don't poll. Give each round a filename prefix (`v1-`, `v2-`, `c-`) so nothing is overwritten and earlier rounds stay available.

### Prompt skeleton

```text
You are producing campaign images for [what the client is, in one line].

The attached images are the exact logo:
- logo-symbol.png: [describe the mark's shapes in words, including what makes it easy to get wrong].
- logo-lockup.png: [the symbol and wordmark, exact spelling].
Only images [N, M] below show the logo; reproduce it faithfully from the attachment. All other images contain no logo and no text. The only words allowed anywhere are "[name]". Never invent another logo or brand, and show no other brands.

VISUAL LANGUAGE (match this closely in every image):
[Light. Backdrop. Palette with hex values. Wardrobe and materials. Grain. Negative space. What it is NOT.]

Create these [n] images with your image generation tool:
1. [prefix]-[subject].png (portrait 1024x1536): [the scene, framing, where headline space stays empty].
2. ...

After generating each image, save it as a PNG with exactly that filename in the current working directory (copy it from wherever the image tool stores its output). Do not modify or delete any existing file. When finished, reply with the list of saved files.
```

Two things in this skeleton prevent most failures: describing the mark in words as well as attaching it, and limiting the logo to named images, since every extra logo is one more chance of a wrong one.

### Visual languages that have worked

- **Airy studio** (boutique fitness): "calm and airy; seamless studio backdrops in soft powder-blue to steel-blue gradients (#C9D8E6 to #6F86A0); cool soft diffused light with gentle falloff; athletes in white or pale ice-blue; equipment matte black or brushed steel; the only warm colour is the logo's dot; lots of negative space; NOT a gritty gym, no neon, no heavy darkness."
- **Editorial black and white** (luxury jewellery book, but for a gym): "soft directional light, fine film grain, deep blacks and pearly greys, calm and intimate, lots of negative space; strictly monochrome; the only colour is the logo's dot."

Write a new paragraph from the current reference rather than reusing these unchanged.

### Check and fix

Read every generated PNG before using it. Generated logos go wrong in small ways: a letter turning into another letter, a wrong dot colour, invented small print.

Fix with an edit rather than regenerating, so the rest of the image survives. Attach the bad image and both logos with `-i`, and say exactly what is wrong:

```text
Three images are attached: x.png (a mock-up) and the exact logo files.
The logo printed on the [object] in x.png is wrong: [what it reads as instead]. Edit x.png so the print is replaced by the exact logo: [shapes in words, and how they appear on this material].
Keep everything else identical: same object, pose, lighting, background, framing and size. The print must look naturally printed, following the surface.
Save the result as x-fixed.png. Do not modify or delete any existing file.
```

## Free photography

The user also wants real photographs: Unsplash, Pexels and similar free sites. Search in the built-in browser, choose images that fit the visual language, and keep the photographer's name for the credits. Check the current licence if the use is unusual. Download only when the user has asked for photos in this request, or ask first with the source and file names.

## Getting images into a page

Run `scripts/compress-images.ps1` first (1600 px, quality 82 is a good default). A deck with dozens of 2 MB PNGs gets slow, and the page's size limits are real.
