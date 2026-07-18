#!/usr/bin/env python3
"""Validate a 35–45 second story JSON and generate HyperFrames index.html."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"story validation failed: {message}")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def validate(data: dict) -> None:
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 7 <= len(scenes) <= 9:
        fail("scenes must contain 7–9 beats")

    duration = float(data.get("duration", 0))
    scene_total = sum(float(scene.get("duration", 0)) for scene in scenes)
    if not 35 <= duration <= 45:
        fail("duration must be 35–45 seconds")
    if abs(scene_total - duration) > 0.01:
        fail(f"scene durations total {scene_total}, expected {duration}")

    width = int(data.get("width", 720))
    height = int(data.get("height", 960))
    fps = int(data.get("fps", 30))
    if width <= 0 or height <= 0 or fps <= 0:
        fail("width, height, and fps must be positive")

    font_size = float(data.get("caption_font_size", 30))
    if not 24 <= font_size <= 34:
        fail("caption_font_size must be 24–34")

    seen_ids: set[str] = set()
    seen_line_images: set[str] = set()
    seen_color_images: set[str] = set()
    for index, scene in enumerate(scenes, 1):
        scene_id = str(scene.get("id", ""))
        if not scene_id or scene_id in seen_ids:
            fail(f"scene {index} needs a unique id")
        seen_ids.add(scene_id)

        scene_duration = float(scene.get("duration", 0))
        if scene_duration <= 0:
            fail(f"{scene_id} duration must be positive")

        for key in ("line_image", "color_image"):
            if not scene.get(key):
                fail(f"{scene_id} is missing {key}")
        line_image = str(scene["line_image"])
        color_image = str(scene["color_image"])
        if line_image in seen_line_images:
            fail(f"{scene_id} reuses line_image {line_image}")
        if color_image in seen_color_images:
            fail(f"{scene_id} reuses color_image {color_image}")
        seen_line_images.add(line_image)
        seen_color_images.add(color_image)

        lines = scene.get("caption_lines", [])
        if not isinstance(lines, list) or len(lines) > 3:
            fail(f"{scene_id} caption_lines must contain 0–3 lines")
        for line in lines:
            if len(str(line)) > 18:
                fail(f"{scene_id} caption line is over 18 characters: {line}")

        prop = scene.get("prop_text")
        if prop:
            prop_lines = prop.get("lines", [])
            if not isinstance(prop_lines, list) or not 1 <= len(prop_lines) <= 3:
                fail(f"{scene_id} prop_text.lines must contain 1–3 lines")
            prop_size = float(prop.get("font_size", 8))
            if not 5 <= prop_size <= 13:
                fail(f"{scene_id} prop font_size must be 5–13")


def check_assets(data: dict, output_dir: Path) -> None:
    media_paths = [str(data.get("bgm", ""))]
    for scene in data["scenes"]:
        media_paths.extend((str(scene["line_image"]), str(scene["color_image"])))
    missing = [path for path in media_paths if path and not (output_dir / path).is_file()]
    if missing:
        fail("missing assets relative to output HTML: " + ", ".join(missing))


def render_caption(scene: dict, global_enabled: bool) -> str:
    enabled = bool(scene.get("captions_enabled", global_enabled))
    lines = scene.get("caption_lines", [])
    if not enabled or not lines:
        return ""
    spans = "".join(f"<span>{esc(line)}</span>" for line in lines)
    return f'<div class="story-text" data-layout-allow-overlap>{spans}</div>'


def render_prop(scene: dict) -> str:
    prop = scene.get("prop_text")
    if not prop:
        return ""
    x = float(prop.get("x", 360))
    y = float(prop.get("y", 600))
    rotation = float(prop.get("rotation", 0))
    size = float(prop.get("font_size", 8))
    gap = float(prop.get("line_gap", size + 1))
    texts = []
    for index, line in enumerate(prop["lines"]):
        yy = y + index * gap
        texts.append(
            f'<text x="{x:g}" y="{yy:g}" text-anchor="middle" '
            f'font-size="{size:g}">{esc(line)}</text>'
        )
    return (
        f'<g class="prop-copy" data-show-at="{float(prop.get("show_at", 1.5)):g}" '
        f'transform="rotate({rotation:g} {x:g} {y:g})" aria-label="画面内文字">'
        + "".join(texts)
        + "</g>"
    )


def render_scene(scene: dict, start: float, track_index: int, global_enabled: bool) -> str:
    scene_id = esc(scene["id"])
    duration = float(scene["duration"])
    crop = scene.get("crop", {})
    scale = float(crop.get("scale", 1))
    x = float(crop.get("x", 0))
    y = float(crop.get("y", 0))
    return f'''      <section id="{scene_id}" class="scene clip" data-start="{start:g}" data-duration="{duration:g}" data-track-index="{track_index}">
        {render_caption(scene, global_enabled)}
        <svg class="illustration" viewBox="0 0 720 960" aria-label="{esc(scene.get('aria_label', scene_id))}">
          <defs>
            <mask id="{scene_id}-line-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="720" height="960"><rect width="720" height="960" fill="#000"/><rect class="mask-surface line-wipe" width="720" height="960" fill="#fff"/></mask>
            <mask id="{scene_id}-color-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="720" height="960"><rect width="720" height="960" fill="#000"/><rect class="mask-surface color-wipe" width="720" height="960" fill="#fff"/></mask>
          </defs>
          <g class="art-group" data-layout-allow-overflow transform="translate({x:g} {y:g}) scale({scale:g})">
            <image href="{esc(scene['line_image'])}" width="720" height="960" preserveAspectRatio="xMidYMid slice" mask="url(#{scene_id}-line-mask)"/>
            <image href="{esc(scene['color_image'])}" width="720" height="960" preserveAspectRatio="xMidYMid slice" mask="url(#{scene_id}-color-mask)"/>
            {render_prop(scene)}
          </g>
        </svg>
      </section>'''


def build(data: dict) -> str:
    width = int(data.get("width", 720))
    height = int(data.get("height", 960))
    duration = float(data["duration"])
    font_size = float(data.get("caption_font_size", 30))
    global_enabled = bool(data.get("captions_enabled", True))
    scenes_html: list[str] = []
    starts: list[float] = []
    cursor = 0.0
    for index, scene in enumerate(data["scenes"]):
        starts.append(cursor)
        scenes_html.append(render_scene(scene, cursor, index + 1, global_enabled))
        cursor += float(scene["duration"])

    scene_ids = json.dumps([f"#{scene['id']}" for scene in data["scenes"]], ensure_ascii=False)
    scene_starts = json.dumps(starts)
    scene_durations = json.dumps([float(scene["duration"]) for scene in data["scenes"]])
    composition_id = esc(data.get("composition_id", "good-deed-story"))
    bgm = esc(data.get("bgm", "assets/audio/bgm.mp3"))
    bgm_volume = float(data.get("bgm_volume", 0.38))

    return f'''<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{esc(data.get('title', '暖心小故事'))}</title>
    <style>
      @font-face {{ font-family: "StoryKai"; src: local("KaiTi"), local("STKaiti"); }}
      * {{ box-sizing: border-box; }}
      html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; background: #f9f7f1; }}
      #root {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; background: transparent; }}
      .paper-bg {{ position: absolute; inset: 0; background: #fbfaf6; }}
      .scene {{ position: absolute; inset: 0; width: {width}px; height: {height}px; opacity: 0; overflow: hidden; }}
      .illustration {{ position: absolute; left: 1px; top: 1px; width: {width - 2}px; height: {height - 2}px; }}
      .story-text {{ position: absolute; z-index: 5; left: 48px; top: 48px; width: 620px; color: #24211d; font-family: "StoryKai", serif; font-size: {font_size:g}px; font-weight: 700; line-height: 1.45; letter-spacing: .4px; text-shadow: 0 .5px 0 rgba(35,28,20,.15); }}
      .story-text span {{ display: block; opacity: 0; transform-origin: left center; }}
      .mask-surface {{ transform-box: fill-box; }}
      .line-wipe, .color-wipe {{ transform-origin: 0% 50%; }}
      .prop-copy {{ opacity: 0; fill: #24211d; font-family: "StoryKai", serif; font-weight: 700; }}
      .paper-flash {{ position: absolute; inset: 0; background: #fff; opacity: 0; z-index: 20; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="{composition_id}" data-start="0" data-duration="{duration:g}" data-width="{width}" data-height="{height}">
      <div class="paper-bg"></div>
{chr(10).join(scenes_html)}
      <div id="paper-flash" class="paper-flash"></div>
      <audio id="bgm" src="{bgm}" data-start="0" data-duration="{duration:g}" data-track-index="20" data-volume="{bgm_volume:g}"></audio>
    </div>
    <script src="assets/vendor/gsap.min.js"></script>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      const scenes = {scene_ids};
      const starts = {scene_starts};
      const durations = {scene_durations};
      scenes.forEach((id, index) => {{
        const start = starts[index];
        const sceneDuration = durations[index];
        const sceneEl = document.getElementById(id.slice(1));
        const textLines = Array.from(sceneEl.querySelectorAll(".story-text span"));
        const lineWipe = sceneEl.querySelector(".line-wipe");
        const colorWipe = sceneEl.querySelector(".color-wipe");
        const propCopy = sceneEl.querySelector(".prop-copy");
        const illustration = sceneEl.querySelector(".illustration");
        tl.fromTo(sceneEl, {{ opacity: 0 }}, {{ opacity: 1, duration: .16, ease: "power1.out" }}, start + .04);
        tl.fromTo(illustration, {{ x: -.4 }}, {{ x: .4, duration: sceneDuration - .18, ease: "none" }}, start + .08);
        if (textLines.length) tl.fromTo(textLines, {{ opacity: 0, x: -8, rotation: -1 }}, {{ opacity: 1, x: 0, rotation: 0, duration: .28, stagger: .20, ease: "power2.out" }}, start + .16);
        tl.fromTo(lineWipe, {{ scaleX: 0 }}, {{ scaleX: 1, duration: 1.25, ease: "power1.inOut" }}, start + .55);
        tl.fromTo(colorWipe, {{ scaleX: 0 }}, {{ scaleX: 1, duration: 2.15, ease: "none" }}, start + 2.15);
        if (propCopy) tl.fromTo(propCopy, {{ opacity: 0 }}, {{ opacity: 1, duration: .22, ease: "power1.out" }}, start + Number(propCopy.dataset.showAt || 1.5));
        tl.to(sceneEl, {{ opacity: 0, duration: .20, ease: "power1.in" }}, start + sceneDuration - .22);
        if (index < scenes.length - 1) tl.fromTo("#paper-flash", {{ opacity: 0 }}, {{ opacity: .42, duration: .09, yoyo: true, repeat: 1, ease: "none" }}, start + sceneDuration - .16);
      }});
      tl.fromTo("#bgm", {{ volume: 0 }}, {{ volume: {bgm_volume:g}, duration: .8, ease: "power1.out" }}, 0);
      tl.to("#bgm", {{ volume: 0, duration: 1.2, ease: "power1.in" }}, {max(0, duration - 1.2):g});
      window.__timelines["{composition_id}"] = tl;
    </script>
  </body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story_json", type=Path)
    parser.add_argument("output_html", type=Path)
    parser.add_argument(
        "--check-assets",
        action="store_true",
        help="verify image and BGM paths relative to the output HTML directory",
    )
    args = parser.parse_args()
    data = json.loads(args.story_json.read_text(encoding="utf-8"))
    validate(data)
    if args.check_assets:
        check_assets(data, args.output_html.parent)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(build(data), encoding="utf-8")
    print(f"generated {args.output_html} ({len(data['scenes'])} scenes, {data['duration']}s)")


if __name__ == "__main__":
    main()
