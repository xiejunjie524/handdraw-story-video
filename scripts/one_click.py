#!/usr/bin/env python3
"""Generate an eight-beat hand-drawn story project from a topic."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


BEATS = [
    ("建立问题", "在日常地点建立一个具体的小困难，主角和受影响者同时出现。"),
    ("展示反应", "展示受影响者的反应，让障碍通过环境和道具变得清楚。"),
    ("出现线索", "用一个道具特写或小动作出现有用线索。"),
    ("决定帮助", "主角看见问题并做出帮助的决定，动作和表情要可见。"),
    ("帮助发生", "展示帮助正在被使用，环境或物体状态随之发生变化。"),
    ("善意延续", "主角回来、继续行动或把得到的帮助传给别人。"),
    ("善意扩散", "至少加入一位回应者，让善意扩散成为画面中的行动。"),
    ("具体结果", "用宽景展示事情已经变好，结尾留下一个克制的情绪结果。"),
]


def fail(message: str) -> None:
    raise SystemExit(f"one-click failed: {message}")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"config not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    raise AssertionError


def endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def api_key(config: dict) -> str:
    env_name = str(config.get("api_key_env", "IMAGE_API_KEY"))
    value = os.environ.get(env_name, "")
    if not value:
        fail(f"environment variable {env_name} is not set")
    return value


def strip_json_fence(text: str) -> str:
    fence = chr(96) * 3
    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith(fence):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith(fence):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def fallback_scenes(topic: str) -> list[dict]:
    subject = topic.strip() or "一个普通的善意瞬间"
    captions = [
        f"关于{subject}，一件小事开始了。",
        "有人遇到了一个没人注意的困难。",
        "一个不起眼的细节给出了线索。",
        "主角决定伸手帮一把。",
        "帮助终于真正发生了。",
        "温暖没有停在一个人身上。",
        "旁边的人也加入了进来。",
        "一件小事，让这里变得不一样。",
    ]
    return [
        {
            "id": f"scene-{index:02d}",
            "duration": 5,
            "caption_lines": [caption],
            "visual_prompt": f"{beat} 故事主题是“{subject}”。{action}",
        }
        for index, ((beat, action), caption) in enumerate(zip(BEATS, captions), 1)
    ]


def generate_story(topic: str, story_config: dict, style_prompt: str) -> list[dict]:
    base_url = str(story_config.get("base_url", "")).strip()
    model = str(story_config.get("model", "")).strip()
    if not base_url or not model:
        return fallback_scenes(topic)

    key = api_key(story_config)
    prompt = (
        "请为一个竖屏手绘暖心短视频生成严格 JSON，不要 Markdown。"
        f"主题：{topic}。需要 8 幕，每幕包含 id、duration、caption_lines、visual_prompt。"
        "duration 必须都是 5；caption_lines 是 0-3 条、每条不超过 18 个中文字符；"
        "visual_prompt 要写清人物、地点、动作、道具、景别和两个以内背景锚点。"
        "剧情必须有具体因果，至少三幕出现多人或环境变化，结尾要展示可见结果。"
        "每幕都必须是不同构图。只输出 {\"scenes\":[...]}。"
        f"固定画风要求：{style_prompt}"
    )
    response = requests.post(
        endpoint(base_url, "/chat/completions"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    parsed = json.loads(strip_json_fence(str(content)))
    scenes = parsed.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 8:
        fail("story model must return exactly 8 scenes")
    return scenes


def image_request(image_config: dict, prompt: str, output_path: Path) -> None:
    base_url = str(image_config.get("base_url", "")).strip()
    if not base_url:
        fail("image.base_url is empty")
    key = api_key(image_config)
    model = str(image_config.get("model", "")).strip()
    size = str(image_config.get("size", "1024x1024"))
    references = [Path(item) for item in image_config.get("reference_images", [])]
    headers = {"Authorization": f"Bearer {key}"}

    if references:
        files = []
        for path in references:
            if not path.is_file():
                fail(f"reference image not found: {path}")
            files.append(("image", (path.name, path.open("rb"), "image/png")))
        try:
            response = requests.post(
                endpoint(base_url, "/images/edits"),
                headers=headers,
                data={"model": model, "prompt": prompt, "size": size},
                files=files,
                timeout=300,
            )
        finally:
            for _, (_, handle, _) in files:
                handle.close()
    else:
        response = requests.post(
            endpoint(base_url, "/images/generations"),
            headers={**headers, "Content-Type": "application/json"},
            json={"model": model, "prompt": prompt, "size": size, "n": 1},
            timeout=300,
        )
    response.raise_for_status()
    data = response.json().get("data", [])
    if not data:
        fail("image provider returned no image data")
    item = data[0]
    if item.get("b64_json"):
        output_path.write_bytes(base64.b64decode(item["b64_json"]))
        return
    if item.get("url"):
        image_response = requests.get(item["url"], timeout=300)
        image_response.raise_for_status()
        output_path.write_bytes(image_response.content)
        return
    fail("image response has neither b64_json nor url")


def normalize_scene(scene: dict, index: int, topic: str) -> dict:
    caption_lines = scene.get("caption_lines", [])
    if not isinstance(caption_lines, list):
        caption_lines = [str(caption_lines)]
    caption_lines = [str(line)[:18] for line in caption_lines[:3]]
    visual_prompt = str(scene.get("visual_prompt", f"围绕{topic}展开第{index}幕善意故事。"))
    return {
        "id": f"scene-{index:02d}",
        "duration": 5,
        "caption_lines": caption_lines,
        "line_image": f"assets/images/scene-{index:02d}-line.png",
        "color_image": f"assets/images/scene-{index:02d}-color.png",
        "visual_prompt": visual_prompt,
        "crop": {"scale": 1, "x": 0, "y": 0},
    }


def write_story(path: Path, scenes: list[dict], bgm: str) -> None:
    path.write_text(
        json.dumps(
            {
                "composition_id": "good-deed-story",
                "title": "手绘暖心故事",
                "width": 720,
                "height": 960,
                "fps": 30,
                "duration": 40,
                "captions_enabled": True,
                "caption_font_size": 30,
                "bgm": bgm,
                "bgm_volume": 0.38,
                "scenes": scenes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, help="故事主题")
    parser.add_argument("--config", type=Path, required=True, help="本地模型配置 JSON")
    parser.add_argument("--output", type=Path, default=Path("runs/story"), help="输出目录")
    parser.add_argument("--dry-run", action="store_true", help="只生成故事配置和提示词，不调用模型")
    parser.add_argument("--render", action="store_true", help="完成后调用 HyperFrames 渲染 MP4")
    args = parser.parse_args()

    config = load_json(args.config)
    output = args.output.resolve()
    image_config = config.get("image", {})
    story_config = config.get("story", {})
    style_path = Path(config.get("style_prompt_file", "templates/style-prompt.txt"))
    style_prompt = style_path.read_text(encoding="utf-8")
    raw_scenes = generate_story(args.topic, story_config, style_prompt)
    scenes = [normalize_scene(scene, index, args.topic) for index, scene in enumerate(raw_scenes, 1)]
    hyperframes = output / "hyperframes"
    hyperframes.mkdir(parents=True, exist_ok=True)
    write_story(output / "story.json", scenes, str(config.get("bgm", "")))

    for scene in scenes:
        prompt = style_prompt + "\n\n" + scene["visual_prompt"]
        prompt_path = output / f"{scene['id']}-prompt.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        color_path = hyperframes / scene["color_image"]
        line_path = hyperframes / scene["line_image"]
        color_path.parent.mkdir(parents=True, exist_ok=True)
        if not args.dry_run:
            image_request(image_config, prompt, color_path)
            subprocess.run(
                [sys.executable, str(Path(__file__).with_name("make_lineart.py")), str(color_path), str(line_path)],
                check=True,
            )

    builder = Path(__file__).with_name("build_story.py")
    subprocess.run([sys.executable, str(builder), str(output / "story.json"), str(hyperframes / "index.html")], check=True)
    print(f"created {output}")
    if args.render:
        subprocess.run(
            [
                "npx",
                "hyperframes",
                "render",
                str(hyperframes / "index.html"),
                "--output",
                str(output / "story.mp4"),
                "--workers",
                "1",
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
