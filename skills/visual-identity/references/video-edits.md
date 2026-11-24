# Brand videos

There is no ffmpeg here, so videos are built as a canvas animation in an HTML page. The page plays the edit and records itself with `MediaRecorder`, then offers the file through the `downloads` capability. All three templates in `assets/video-templates/` work this way.

| Template | Format | Edit | Use when |
|---|---|---|---|
| `strobe.html` | 16:9, 20 s | Full-frame photo cuts, big word cards, symbol hits | The user asks for a strobe or a fast identity film |
| `chrome.html` | 4:5, 20 s | A chrome 3D version of the symbol (three.js) on a card, cut with split-portrait stills and tech captions | A hero object or "first slide video" for Instagram |
| `archive.html` | 4:5, 15 s | Stop-motion stack of printed cards: 56 cards, slow at the ends, up to about 7 a second in the middle | A reference with a card-flip or archive rhythm, or "50 images in 15 seconds" |

## Making a new one

Copy the closest template into the project and change the top of its script:

- `W`, `H`, `DUR`: size and length.
- `C`: the palette. `SYM` (`PATH` in chrome): the logo's SVG path. `DISPLAY`, `MONO`: fonts, plus the stylesheet link.
- The timeline. `strobe` and `chrome` use `add(duration, {type, ...})`. `archive` uses the `deck` array and works out the timing itself, so you only list cards.
- The page's `<title>`, heading, meta line and `aria-label`.
- Put images in `img/` next to the page, named as the keys the timeline uses, and compress them first.
- Replace `EARNED`, `NOT SCROLLED` and any other captions with the client's words.

For a chrome object, the symbol is extruded from the SVG path. The realism comes from the custom studio environment and metalness 1 with low roughness; a plain light rig looks like white plastic. Oscillate the rotation rather than spinning fully, because a flat logo seen edge-on disappears.

## Rhythm from a reference

Open the reference and count roughly: how long a shot stays, whether the frame is full-bleed or framed, what stays constant between cuts. Rhythm is the point of these requests ("THIS RYTHME THIS TYPE OF EDIT"), so slow the start and end and let the middle run fast.

## Flashing

Keep it safe for people with photosensitivity, even when the reference is harsher, and tell the user what you did.

- At most about 3 full-frame, high-contrast changes per second. `strobe` and `chrome` stay at or under 2.5 cuts a second.
- Going faster is fine when each change is small and low in contrast. `archive` keeps the background and paper constant, changes only the photo window, and orders images dark to light (`scripts/luminance.ps1`).
- Saturated red full frames are the riskiest: use them rarely and in slower moments.

## Checking and publishing

A hash like `#t7.2` makes the page draw that moment on load, so single frames can be checked:

```powershell
powershell -ExecutionPolicy Bypass -File shot.ps1 -Html archive.html -Size 790,1100 -Out frame.png -Hash t7.2
```

Look at the start, the fast middle, a word card and the end. Publish as a plain artifact with `capabilities: {downloads: true}`, `icon: "video"`, `root` set to the folder, and every image listed in `files`.

Recording plays in real time, so the tab must stay visible. Chrome usually saves WebM. Instagram needs MP4, so tell the user to convert it (HandBrake, CapCut) and add music there. A real recording can't be checked headlessly: say so rather than implying it was tested.
