# Studying references

The user finds references on Behance and Instagram and sends them with few or no words. Look properly before responding, using the built-in browser; a project's images say far more than its text.

## Behance

1. Open the gallery URL without the tracking parameters. It needs no sign-in, and if a modal appears, close it. Never sign in.
2. `get_page_text` gives the concept, the studio and the credits.
3. Find the images, then step through them:

```js
(() => { const imgs=[...document.querySelectorAll('main img')].filter(i=>(i.currentSrc||i.src).includes('project_modules')); return {h:document.documentElement.scrollHeight, n:imgs.length, tops:imgs.map(i=>Math.round(i.getBoundingClientRect().top+scrollY))}; })()
```

Then repeat `window.scrollTo(0, top)`, wait 2 s, and take a screenshot at scale 0.6. Six to ten stops usually show the whole system.

## Instagram

Add `?img_index=N` to the post URL to step through a carousel. A sign-up modal may appear: close it with the X. For videos, take screenshots at intervals and estimate the rhythm.

## What to extract

Write down, for yourself:

- **The idea:** the one thought behind the identity. Often more useful than the look. BYSEC, for example: fit is in the word fitness, heat as a colour language, a symbol from muscle contraction.
- **The structure:** the order of the presentation and which slide types recur. This is what "THIS SLIDES SHOULD BE RECREATED" asks for.
- **The register:** what kind of brand it positions the client as.
- **The visual language:** light, backdrop, palette, wardrobe, grain, crop, negative space.
- **The type logic:** width, weight, how headlines are set.
- **The rhythm,** for motion.

Then decide what to do with it:

- If the message says what to do, do it.
- If it is a bare link during brand work, apply what fits to the current stage and say in a line what you took from it.
- If it could change finished work a lot (a new app direction, say), name the two or three things you would change and ask with one question.

Use references for logic and structure, never for copying (see the Originality section of SKILL.md).
