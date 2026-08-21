# YouTubeDownloader

下载 YouTube 视频的音视频 + 字幕，并合成一个视频文件。

## 功能

- 下载最佳画质视频 + 音频（yt-dlp）
- 自动下载字幕（中文优先，fallback 英文）
- 字幕合成两种模式：
  - **软字幕**（默认）：字幕作为可选轨道嵌入，可开关显示，速度快、画质无损
  - **硬字幕**（`--burn`）：字幕烧录进画面，任何播放器可见，需重新编码
- 统一输出 MP4 格式
- 自动清理中间文件

## 依赖

| 依赖 | 用途 | 安装 |
|------|------|------|
| Python 3.10+ | 运行环境 | — |
| yt-dlp | 视频/字幕下载 | `pip install yt-dlp` |
| ffmpeg | 音视频合并、字幕处理 | `brew install ffmpeg` |
| ffmpeg-full | 硬字幕烧录（`--burn`）所需 libass | `brew install ffmpeg-full` |

> 软字幕模式只需普通 `ffmpeg`；硬字幕烧录需要带 libass 的 `ffmpeg-full`，脚本会自动检测并优先使用。

## 安装

```bash
# 克隆项目
cd youtubedownloader

# 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# （可选）安装 ffmpeg-full 以支持硬字幕烧录
brew install ffmpeg-full
```

## 使用

```bash
# 基本用法（软字幕）
.venv/bin/python ytdl.py "https://www.youtube.com/watch?v=xxxx"

# 硬字幕烧录
.venv/bin/python ytdl.py "https://youtu.be/xxxx" --burn

# 指定输出目录和字幕语言
.venv/bin/python ytdl.py "https://youtu.be/xxxx" -o ./output --sub-langs zh,en

# 保留中间文件（原始 mkv、字幕）
.venv/bin/python ytdl.py "https://youtu.be/xxxx" --keep-temp
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 视频 URL（yt-dlp 支持的站点） | 必填 |
| `-o, --output` | 输出目录 | `./downloads` |
| `--burn` | 烧录硬字幕（不可关闭） | 软字幕 |
| `--sub-langs` | 字幕语言，逗号分隔 | `zh-Hans,zh,en` |
| `--keep-temp` | 保留中间文件 | 清理 |

## 工作流程

```
1. yt-dlp 下载最佳视频+音频 → 合并为 mkv
2. yt-dlp 下载字幕（srt/vtt）→ 转为 srt（如需）
3. ffmpeg 合成最终视频：
   - 软字幕: -c copy -c:s mov_text（无损、快）
   - 硬字幕: -vf subtitles=... -c:v libx264（烧录、慢）
4. 清理中间文件（除非 --keep-temp）
```
