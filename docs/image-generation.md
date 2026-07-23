# 生图模型接入

本仓库负责故事配置、线稿提取和 HyperFrames 动画，不绑定任何生图服务，也不包含任何个人 API 地址、模型名或密钥。使用者可以接入自己的供应商，只要每一幕最终输出一张本地 PNG 彩色母图即可。

## 配置方式

建议在项目外部或本机环境中配置：

```text
IMAGE_PROVIDER=your-provider
IMAGE_API_BASE_URL=https://your-provider.example/v1
IMAGE_API_KEY=replace_me
IMAGE_MODEL=your-image-model
IMAGE_SIZE=1024x1024
```

这些变量只是约定名称，具体客户端可以使用自己的配置文件或命令行参数。真实密钥不要写入 Git 仓库、`story.json` 或截图。

## Atlas Cloud 配置

`scripts/one_click.py` 可以在 `provider` 设置为 `atlascloud`、`atlas-cloud` 或 `atlas` 时直接调用 Atlas Cloud。图像生成使用 Media API 的 `generateImage` + prediction 轮询流程；可选文本故事生成使用 OpenAI-compatible chat completions。

复制示例配置：

```powershell
Copy-Item config.atlascloud.example.json config.local.json
$env:ATLASCLOUD_API_KEY = "your-api-key"
python scripts\one_click.py --topic "楼下的流浪猫" --config config.local.json --output runs\cat-story
```

也可以使用环境变量别名：

```powershell
$env:ATLAS_CLOUD_API_KEY = "your-api-key"
```

默认图像模型是 `bytedance/seedream-v5.0-lite`，默认文本模型是 `qwen/qwen3.5-flash`。如需传入模型专属参数，可在 `image.params` 中添加，例如：

```json
{
  "image": {
    "provider": "atlascloud",
    "model": "bytedance/seedream-v5.0-lite",
    "size": "1024x1024",
    "params": {
      "image_size": "1024x1024"
    }
  }
}
```

如果 `reference_images` 中配置了本地参考图，脚本会先通过 Atlas Cloud `uploadMedia` 上传，再把返回 URL 传给图像生成请求。单张图使用 `image_url`，多张图使用 `image_urls`；若 `image.params` 已显式提供这些字段，则以 `image.params` 为准。

## 生图要求

每一幕先生成一张完整的低饱和彩铅彩色图，推荐 1K：

- 每幕必须使用不同的母图
- 主角、服装、发型和关键道具在同一故事中保持一致
- 保留大面积纸白留白，主体通常位于画面下方 45%–55%
- 单帧最多 2–3 人和两个关键背景锚点
- 不要先单独生成线稿，也不要用同一张图裁切或缩放凑时长

模型调用可以由你自己的脚本、工作流工具或供应商 SDK 完成。调用完成后，把结果保存为：

```text
hyperframes/assets/images/scene-01-color.png
hyperframes/assets/images/scene-02-color.png
...
```

## 参考图和角色一致性

需要固定画风或角色时，把上一幕确认过的彩色图作为参考图传给你的供应商，并在提示词中明确：保持人物外观、线条风格、留白比例和色彩限制，只改变动作、场景或道具。

不要把个人参考图、供应商返回的临时响应、浏览器缓存或 API 配置提交到公共仓库。可以将参考图放在被 `.gitignore` 排除的本地目录中。

## 从彩色图提取线稿

线稿必须从对应的彩色母图本地提取，确保两张图像素对齐：

```powershell
python scripts\make_lineart.py `
  hyperframes\assets\images\scene-01-color.png `
  hyperframes\assets\images\scene-01-line.png
```

对每一幕重复一次。不要为同一幕再调用一次模型生成“线稿版”，也不要自动重试覆盖已经确认的图片。

## 推荐批量顺序

1. 写好 7–9 幕 beat sheet。
2. 按顺序一次生成一张彩色母图。
3. 人工确认角色、鞋子、腿部、衣服和留白没有问题。
4. 从确认后的彩色图提取线稿。
5. 完成全部场景后，再运行 `build_story.py` 和 HyperFrames 检查。

模型服务的价格、速率限制、可商用范围和图片保留政策以各供应商当前条款为准。
