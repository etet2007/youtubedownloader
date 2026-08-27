#!/usr/bin/env python3
"""
YouTubeDownloader — 下载音视频 + 字幕并合成一个视频文件。

依赖:
    yt-dlp (pip install yt-dlp)
    ffmpeg (硬字幕烧录需要带 libass 支持的 ffmpeg-full)

用法:
    python3 ytdl.py <URL> [options]

示例:
    python3 ytdl.py "https://www.youtube.com/watch?v=xxxx"          # 默认软字幕
    python3 ytdl.py "https://youtu.be/xxxx" --burn                   # 硬字幕烧录
    python3 ytdl.py "https://youtu.be/xxxx" -o ./output --burn --sub-langs zh,en
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


FFMPEG_BIN = "ffmpeg"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """执行命令，失败时打印完整命令并退出。"""
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f"[ERROR] 命令失败 (exit {r.returncode}): {' '.join(cmd)}")
    return r


def find_ffmpeg(prefer_libass: bool = False) -> str:
    """
    查找 ffmpeg 可执行文件。
    prefer_libass=True 时，优先查找带 subtitles 滤镜的 ffmpeg（含 ffmpeg-full keg-only 路径）。
    """
    candidates = []
    # homebrew ffmpeg-full keg-only 路径 (macOS)
    for p in (
        "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",  # Apple Silicon
        "/usr/local/opt/ffmpeg-full/bin/ffmpeg",     # Intel
    ):
        if Path(p).exists():
            candidates.append(p)
    # PATH 中的 ffmpeg
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)

    if not candidates:
        return "ffmpeg"  # 让后续调用报错

    if not prefer_libass:
        return candidates[0] if candidates else "ffmpeg"

    # 检查哪些 ffmpeg 有 subtitles 滤镜
    for ffmpeg in candidates:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True, text=True,
        )
        if re.search(r"\bsubtitles\b", r.stdout):
            return ffmpeg
    return candidates[0]  # 都没有就返回第一个，后续报错指引


def has_subtitles_filter(ffmpeg_bin: str = "ffmpeg") -> bool:
    """检查 ffmpeg 是否有 subtitles 滤镜（需要 libass 支持）。"""
    r = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-filters"],
        capture_output=True, text=True,
    )
    return bool(re.search(r"\bsubtitles\b", r.stdout))


def escape_filter_path(path: Path) -> str:
    """
    转义 ffmpeg subtitles 滤镜中的文件路径。
    需要转义的字符: \\ : ' , 以及过滤图中的特殊字符。
    """
    s = str(path)
    # 转义反斜杠和冒号（libass 滤镜分隔符）
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s


def check_deps(burn: bool = False) -> None:
    """检查必要的外部依赖，并设置全局 FFMPEG_BIN。"""
    global FFMPEG_BIN
    if shutil.which("yt-dlp") is None:
        sys.exit("[ERROR] 缺少依赖: yt-dlp。请先安装 (pip install yt-dlp)。")
    FFMPEG_BIN = find_ffmpeg(prefer_libass=burn)
    if not Path(FFMPEG_BIN).exists() and shutil.which(FFMPEG_BIN) is None:
        sys.exit("[ERROR] 缺少依赖: ffmpeg。请先安装。")


def download_media(url: str, out_dir: Path, sub_langs: str) -> dict:
    """
    用 yt-dlp 下载最佳视频+音频和字幕。

    分两阶段：先下载视频，再单独尝试下载字幕。
    字幕下载失败（如 429）不会中断流程，仅输出警告。

    返回 dict:
        video_path  — 合并后的视频文件路径
        subtitle    — srt 字幕路径（若无可用字幕则为 None）
        title       — 视频标题
    """
    import yt_dlp

    sub_lang_list = [l.strip() for l in sub_langs.split(",") if l.strip()]
    outtmpl = str(out_dir / "%(title)s - %(uploader)s.%(ext)s")

    # ---- 阶段 1: 下载视频+音频（不含字幕）----
    print(f"[1/3] 下载视频: {url}")
    video_opts = {
        "outtmpl": outtmpl,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mkv",
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mkv"},
        ],
    }

    info: dict = {}
    with yt_dlp.YoutubeDL(video_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", "video")
    uploader = info.get("uploader", info.get("channel", "unknown"))
    safe_title = yt_dlp.utils.sanitize_filename(f"{title} - {uploader}", restricted=False)
    video_path = out_dir / f"{safe_title}.mkv"

    # 如果预期文件不存在，搜索目录中最近生成的 mkv
    if not video_path.exists():
        mkvs = sorted(
            out_dir.glob("*.mkv"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if mkvs:
            video_path = mkvs[0]
        else:
            sys.exit(f"[ERROR] 未找到下载的视频文件: {video_path}")

    print(f"      视频文件: {video_path.name}")

    # ---- 阶段 2: 逐个语言尝试下载字幕（容错）----
    # yt-dlp 在任一语言字幕下载失败时会报错退出，
    # 因此逐个语言单独尝试，避免一种语言 429 阻断其他语言。
    print(f"[2/3] 下载字幕 (语言优先级: {', '.join(sub_lang_list)})")
    for lang in sub_lang_list:
        sub_opts = {
            "outtmpl": str(video_path.with_suffix("")),
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "srt/best",
            "quiet": True,
        }
        try:
            with yt_dlp.YoutubeDL(sub_opts) as ydl:
                ydl.extract_info(url, download=True)
            # 检查文件是否实际生成（yt-dlp 在无该语言字幕时会静默跳过）
            stem = video_path.stem
            candidates = list(out_dir.glob(f"{stem}.{lang}.*"))
            candidates += list(out_dir.glob(f"{stem}.{lang}"))
            if candidates:
                print(f"      字幕 '{lang}' 下载成功: {candidates[0].name}")
                break
            else:
                print(f"      字幕 '{lang}' 不存在（视频无该语言字幕）")
                continue
        except Exception as e:
            print(f"      字幕 '{lang}' 下载失败: {e}")
            continue

    # 查找字幕文件 — 按语言优先级
    subtitle: Path | None = None
    stem = video_path.stem
    for lang in sub_lang_list:
        candidates = list(out_dir.glob(f"{stem}.{lang}.*"))
        candidates += list(out_dir.glob(f"{stem}.{lang}"))
        if candidates:
            subtitle = candidates[0]
            break

    # fallback: 任意 srt/vtt
    if subtitle is None:
        for ext in ("srt", "vtt", "ass"):
            candidates = list(out_dir.glob(f"{stem}.*.{ext}"))
            if candidates:
                subtitle = candidates[0]
                break

    if subtitle:
        print(f"      字幕文件: {subtitle.name}")
    else:
        print("      未找到字幕（视频可能无字幕或字幕下载失败），将仅输出无字幕视频。")
    return {"video_path": video_path, "subtitle": subtitle, "title": title, "uploader": uploader}


def convert_to_srt(subtitle: Path, out_dir: Path) -> Path:
    """将字幕统一转换为 srt 格式（ffmpeg）。"""
    if subtitle.suffix.lower() == ".srt":
        return subtitle

    srt_path = out_dir / (subtitle.stem + ".srt")
    print(f"      转换字幕为 SRT: {subtitle.name} -> {srt_path.name}")
    run(
        [FFMPEG_BIN, "-y", "-i", str(subtitle), "-c:s", "srt", str(srt_path)],
        capture_output=True,
    )
    return srt_path


def merge_subtitles(
    video_path: Path,
    subtitle: Path | None,
    out_dir: Path,
    burn: bool,
) -> Path:
    """
    合成最终视频:
        - 软字幕 (默认): 将字幕嵌入为可选轨道 (mp4 用 mov_text)。
        - 硬字幕 (--burn): 将字幕烧录进画面 (需要 libass)。
        - 无字幕: 直接复制。
    """
    output_path = out_dir / f"{video_path.stem}_final.mp4"

    # 无字幕 → 直接复制
    if subtitle is None:
        print(f"[3/3] 无字幕，直接输出: {output_path.name}")
        run(
            [FFMPEG_BIN, "-y", "-i", str(video_path),
             "-c", "copy", str(output_path)],
            capture_output=True,
        )
        return output_path

    if burn:
        if not has_subtitles_filter(FFMPEG_BIN):
            sys.exit(
                "[ERROR] 当前 ffmpeg 不支持 subtitles 滤镜（缺少 libass）。\n"
                "  硬字幕烧录需要带 libass 的 ffmpeg，请安装:\n"
                "    brew install ffmpeg-full\n"
                "  或者使用软字幕模式（去掉 --burn 参数）。"
            )

        print(f"[3/3] 烧录硬字幕: {output_path.name}")
        sub_path = escape_filter_path(subtitle)
        run(
            [FFMPEG_BIN, "-y",
             "-i", str(video_path),
             "-vf", f"subtitles={sub_path}",
             "-c:v", "libx264",
             "-crf", "20",
             "-preset", "medium",
             "-c:a", "copy",
             str(output_path)],
            capture_output=True,
        )
    else:
        print(f"[3/3] 嵌入软字幕: {output_path.name}")
        run(
            [FFMPEG_BIN, "-y",
             "-i", str(video_path),
             "-i", str(subtitle),
             "-c", "copy",
             "-c:s", "mov_text",
             "-metadata:s:s:0", "language=chi",
             str(output_path)],
            capture_output=True,
        )

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube 下载器：下载音视频 + 字幕并合成一个视频文件。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="视频 URL（YouTube 等 yt-dlp 支持的站点）")
    parser.add_argument(
        "-o", "--output", default="./downloads",
        help="输出目录（默认 ./downloads）",
    )
    parser.add_argument(
        "--burn", action="store_true",
        help="烧录硬字幕（不可关闭），默认为软字幕嵌入",
    )
    parser.add_argument(
        "--sub-langs", default="zh-Hans,zh,en",
        help="字幕语言，逗号分隔（默认 zh-Hans,zh,en）",
    )
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="保留中间文件（原始 mkv、原始字幕）",
    )
    args = parser.parse_args()

    check_deps(burn=args.burn)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = download_media(args.url, out_dir, args.sub_langs)
    video_path: Path = result["video_path"]
    subtitle: Path | None = result["subtitle"]

    if subtitle and subtitle.suffix.lower() != ".srt":
        subtitle = convert_to_srt(subtitle, out_dir)

    final = merge_subtitles(video_path, subtitle, out_dir, args.burn)

    print(f"\n✓ 完成！最终视频: {final}")

    if not args.keep_temp:
        for f in out_dir.glob("*"):
            if f == final:
                continue
            if f.suffix.lower() in (".mkv", ".srt", ".vtt", ".ass"):
                f.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
