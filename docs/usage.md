# 使用方法

这个项目的用途是：准备 7–9 幕手绘彩色图片，自动提取对应线稿，再用 HyperFrames 做成“线稿从左到右出现、颜色从左到右填充”的竖屏故事视频。

## 1. 安装环境

Windows PowerShell：

```powershell
git clone https://github.com/xiejunjie524/handdraw-story-video.git
cd handdraw-story-video
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install gsap
```

还需要安装 Node.js 18+、FFmpeg 和 HyperFrames。若 PowerShell 禁止激活虚拟环境，可以直接使用：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. 准备项目目录

建议在仓库内创建一个独立的工作目录：

```powershell
New-Item -ItemType Directory -Force hyperframes\assets\images | Out-Null
New-Item -ItemType Directory -Force hyperframes\assets\audio | Out-Null
New-Item -ItemType Directory -Force hyperframes\assets\vendor | Out-Null
Copy-Item node_modules\gsap\dist\gsap.min.js hyperframes\assets\vendor\gsap.min.js
```

不要把 API 密钥、浏览器数据、下载的版权音乐或以前的 MP4 成片放进 Git 仓库。

## 3. 创建故事配置

复制模板：

```powershell
Copy-Item templates\story-template.json story.json
```

编辑 `story.json`：

- `duration` 设置为 35–45 秒，默认 40 秒
- `scenes` 保持 7–9 幕，通常每幕 5 秒
- 每幕使用不同的 `line_image` 和 `color_image`
- 字幕最多 3 行，每行不超过约 18 个中文字符
- `bgm` 写相对于 `hyperframes` 目录的路径，例如 `assets/audio/bgm.mp3`

参考配置：[examples/soy-milk-at-4am/story.json](../examples/soy-milk-at-4am/story.json)。

## 4. 准备图片并提取线稿

每幕先准备一张 1K 彩色母图。把彩色图放在 `hyperframes\assets\images`，再从同一张图本地提取线稿：

```powershell
python scripts\make_lineart.py `
  hyperframes\assets\images\scene-01-color.png `
  hyperframes\assets\images\scene-01-line.png
```

对 8 幕分别执行一次。不要为同一幕重新生一张“线稿图”，否则线稿和颜色会错位。

## 5. 放入 BGM 并生成页面

把已经获得授权的音乐复制为 `hyperframes\assets\audio\bgm.mp3`，然后运行：

```powershell
python scripts\build_story.py story.json hyperframes\index.html --check-assets
```

如果提示缺少素材，检查图片、BGM 和 `story.json` 中的路径是否一致。

## 6. 检查和渲染

```powershell
npx hyperframes check hyperframes\index.html --json
New-Item -ItemType Directory -Force renders | Out-Null
npx hyperframes render hyperframes\index.html `
  --output renders\story-v1.mp4 `
  --workers 1
```

每次渲染使用新的文件名，例如 `story-v2.mp4`，不要覆盖旧成片。发布前检查视频是否为 720×960、约 40 秒、有音频、没有黑帧，且每幕都是左到右显现和填色。

## 7. 更新到 GitHub

修改代码或文档后：

```powershell
git add .
git commit -m "描述本次修改"
git push
```

只提交源代码、模板和必要示例；生成的图片、音频、渲染视频默认已被 `.gitignore` 排除。
