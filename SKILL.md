---
name: handdraw-good-deed-story
description: Batch-produce 35–45 second vertical hand-drawn good-deed story videos with black line art revealed left to right and aligned low-saturation color filling in the same direction. Use for Chinese warm-story shorts, gradual line-art coloring videos, reusable eight-beat story templates, or HyperFrames delivery of this visual format.
---

# Hand-drawn good-deed story

Create a compact cause-and-effect story, then build it with the bundled scripts and HyperFrames.

## Defaults

- Deliver 40 seconds, 720×960, 30 fps, H.264 MP4.
- Use 8 distinct beats of about 5 seconds; accept 7–9 beats and 35–45 seconds.
- Use no narration by default. Select licensed BGM for each story instead of fixing one track.
- Generate one 1K low-saturation color mother image per beat. Never retry image generation automatically.
- Derive line art locally from the exact color image with `scripts/make_lineart.py`; never generate line and color images separately.
- Reveal line art left to right, then fill color left to right from the same origin.
- Render with one worker and never overwrite a prior render.

## Workflow

1. Read `docs/story-spec.md` and write an eight-row beat sheet: event, characters, setting, key prop, action/reaction, two visual details, and framing.
2. Keep every beat visually distinct. Reject repeated mother images, crops, mirrors, recolors, or zooms used to pad runtime.
3. Copy `templates/story-template.json` to a project `story.json` and fill it in. Manually wrap captions; do not use HTML line breaks.
4. Generate one complete color mother image for each beat, sequentially, at 1K. Keep broad paper-white negative space and clean separated contours.
5. Run `python scripts/make_lineart.py COLOR OUTPUT_LINE` for every approved mother image.
6. Run `python scripts/build_story.py story.json hyperframes/index.html --check-assets`.
7. Install GSAP through npm and copy `node_modules/gsap/dist/gsap.min.js` to `hyperframes/assets/vendor/gsap.min.js`.
8. Run HyperFrames checks, inspect the line and color midpoint of every scene, then render with `--workers 1`.
9. Verify duration, dimensions, audio stream, black frames, text fit, consistent reveal direction, and final color before delivery.

## Visual constraints

- Keep the illustrated action mainly in the lower 45%–55% when captions are present.
- Use at most 2–3 people and two key background anchors per frame.
- Avoid dense architecture, crowds, heavy rain hatching, and line-art extraction that becomes a black mass.
- Vary framing: establish place, show a prop/detail interaction, show action/reaction, and end on a changed communal image.
- Keep captions optional, at 1–3 lines and no more than about 18 Chinese characters per line.
- Add in-scene text only when a physical note, sign, phone, label, or receipt exists in the story.

Use the builder rather than rewriting mask and timeline boilerplate.
