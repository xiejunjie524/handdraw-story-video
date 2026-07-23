#!/usr/bin/env python3
"""Generate an eight-beat hand-drawn story project from a topic."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests


ATLASCLOUD_MEDIA_BASE_URL = "https://api.atlascloud.ai/api/v1"
ATLASCLOUD_LLM_BASE_URL = "https://api.atlascloud.ai/v1"
ATLASCLOUD_IMAGE_MODEL = "bytedance/seedream-v5.0-lite"
ATLASCLOUD_STORY_MODEL = "qwen/qwen3.5-flash"
ATLASCLOUD_API_KEY_ENVS = ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY")

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


def provider_name(config: dict) -> str:
    return str(config.get("provider", "")).strip().lower().replace("_", "-")


def is_atlascloud(config: dict) -> bool:
    return provider_name(config) in {"atlas", "atlascloud", "atlas-cloud"}


def env_names(config: dict, default_names: tuple[str, ...]) -> list[str]:
    raw = config.get("api_key_env")
    if isinstance(raw, list):
        names = [str(name).strip() for name in raw if str(name).strip()]
    elif raw:
        names = [str(raw).strip()]
    else:
        names = list(default_names)

    aliases = config.get("api_key_env_aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    names.extend(str(name).strip() for name in aliases if str(name).strip())
    return list(dict.fromkeys(names))


def api_key(config: dict, default_names: tuple[str, ...] = ("IMAGE_API_KEY",)) -> str:
    names = env_names(config, default_names)
    for env_name in names:
        value = os.environ.get(env_name, "")
        if value:
            return value
    fail("none of these environment variables are set: " + ", ".join(names))


def resolved_image_config(config: dict) -> dict:
    resolved = dict(config)
    if is_atlascloud(resolved):
        resolved.setdefault("base_url", ATLASCLOUD_MEDIA_BASE_URL)
        resolved.setdefault("api_key_env", ATLASCLOUD_API_KEY_ENVS[0])
        resolved.setdefault("api_key_env_aliases", [ATLASCLOUD_API_KEY_ENVS[1]])
        resolved.setdefault("model", ATLASCLOUD_IMAGE_MODEL)
        resolved.setdefault("size", "1024x1024")
        resolved.setdefault("poll_interval", 3)
        resolved.setdefault("poll_timeout", 300)
    return resolved


def resolved_story_config(config: dict) -> dict:
    resolved = dict(config)
    if is_atlascloud(resolved):
        resolved.setdefault("base_url", ATLASCLOUD_LLM_BASE_URL)
        resolved.setdefault("api_key_env", ATLASCLOUD_API_KEY_ENVS[0])
        resolved.setdefault("api_key_env_aliases", [ATLASCLOUD_API_KEY_ENVS[1]])
        resolved.setdefault("model", ATLASCLOUD_STORY_MODEL)
    return resolved


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
    story_config = resolved_story_config(story_config)
    base_url = str(story_config.get("base_url", "")).strip()
    model = str(story_config.get("model", "")).strip()
    if not base_url or not model:
        return fallback_scenes(topic)

    key = api_key(story_config, ATLASCLOUD_API_KEY_ENVS if is_atlascloud(story_config) else ("TEXT_API_KEY",))
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


def successful_payload(payload: dict, context: str) -> dict:
    code = payload.get("code")
    if code not in (None, 0, 200, "0", "200"):
        fail(f"{context} failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload.get("data", payload)


def write_image_item(item: object, output_path: Path) -> None:
    if isinstance(item, str):
        item = {"url": item}
    if not isinstance(item, dict):
        fail("image response item must be an object or URL string")
    if item.get("b64_json"):
        output_path.write_bytes(base64.b64decode(str(item["b64_json"])))
        return
    url = item.get("url") or item.get("download_url")
    if url:
        image_response = requests.get(str(url), timeout=300)
        image_response.raise_for_status()
        output_path.write_bytes(image_response.content)
        return
    fail("image response has neither b64_json nor url")


def atlas_output_items(data: dict) -> list:
    outputs = (
        data.get("outputs")
        or data.get("output")
        or data.get("images")
        or data.get("urls")
        or data.get("result")
    )
    if isinstance(outputs, list):
        return outputs
    if outputs:
        return [outputs]
    return []


def atlas_upload_reference(base_url: str, key: str, path: Path) -> str:
    if not path.is_file():
        fail(f"reference image not found: {path}")
    with path.open("rb") as handle:
        response = requests.post(
            endpoint(base_url, "/model/uploadMedia"),
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (path.name, handle, "image/png")},
            timeout=120,
        )
    response.raise_for_status()
    data = successful_payload(response.json(), "Atlas Cloud media upload")
    url = data.get("download_url") or data.get("url")
    if not url:
        fail("Atlas Cloud media upload returned no URL")
    return str(url)


def atlas_image_request(image_config: dict, prompt: str, output_path: Path) -> None:
    base_url = str(image_config.get("base_url", ATLASCLOUD_MEDIA_BASE_URL)).strip()
    key = api_key(image_config, ATLASCLOUD_API_KEY_ENVS)
    model = str(image_config.get("model", ATLASCLOUD_IMAGE_MODEL)).strip()
    size = str(image_config.get("image_size") or image_config.get("size") or "1024x1024")
    references = [Path(item) for item in image_config.get("reference_images", [])]

    payload = {"model": model, "prompt": prompt, "image_size": size}
    params = image_config.get("params", {})
    if isinstance(params, dict):
        payload.update(params)
    if references and "image_url" not in payload and "image_urls" not in payload:
        urls = [atlas_upload_reference(base_url, key, path) for path in references]
        if len(urls) == 1:
            payload["image_url"] = urls[0]
        else:
            payload["image_urls"] = urls
    response = requests.post(
        endpoint(base_url, "/model/generateImage"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = successful_payload(response.json(), "Atlas Cloud image generation")
    prediction_id = data.get("id") or data.get("prediction_id") or data.get("task_id")
    if not prediction_id:
        items = atlas_output_items(data)
        if items:
            write_image_item(items[0], output_path)
            return
        fail("Atlas Cloud image generation returned no prediction id")

    deadline = time.monotonic() + float(image_config.get("poll_timeout", 300))
    poll_interval = float(image_config.get("poll_interval", 3))
    while time.monotonic() < deadline:
        poll_response = requests.get(
            endpoint(base_url, f"/model/prediction/{prediction_id}"),
            headers={"Authorization": f"Bearer {key}"},
            timeout=60,
        )
        poll_response.raise_for_status()
        result = successful_payload(poll_response.json(), "Atlas Cloud prediction polling")
        status = str(result.get("status", "")).lower()
        if status in {"completed", "succeeded", "success"}:
            items = atlas_output_items(result)
            if not items:
                fail("Atlas Cloud prediction completed without output URLs")
            write_image_item(items[0], output_path)
            return
        if status in {"failed", "error", "canceled", "cancelled"}:
            fail(f"Atlas Cloud prediction {prediction_id} ended with status {status}")
        time.sleep(poll_interval)
    fail(f"Atlas Cloud prediction {prediction_id} timed out")


def openai_image_request(image_config: dict, prompt: str, output_path: Path) -> None:
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
    write_image_item(data[0], output_path)


def image_request(image_config: dict, prompt: str, output_path: Path) -> None:
    image_config = resolved_image_config(image_config)
    if is_atlascloud(image_config):
        atlas_image_request(image_config, prompt, output_path)
        return
    openai_image_request(image_config, prompt, output_path)


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
