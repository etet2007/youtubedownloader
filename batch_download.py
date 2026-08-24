#!/usr/bin/env python3
"""
批量下载仙剑奇侠传（Dos版）攻略系列视频。
逐个调用 ytdl.py 下载，自动跳过已完成的。
"""

import subprocess
import sys
from pathlib import Path

# 仙剑奇侠传（Dos版）攻略 全22集
VIDEOS = [
    ("jjcukAKGTtQ", "01"),
    ("rIYbX77Pj2U", "02"),
    ("D3hHSceIRAI", "03"),
    ("N9aF4S8iTnE", "04"),
    ("6Ev4uu8CGKY", "05"),
    ("xDwJOxlC6EM", "06"),
    ("eldjzKjYdh0", "07"),
    ("jup98JItPQ4", "08"),  # 已下载
    ("J9hMU_7IQrI", "09"),
    ("3-CMS7RN7fM", "10"),
    ("yFjFltuSSxY", "11"),
    ("bkBmcQST5jM", "12"),
    ("rIrUXZyanx8", "13"),
    ("xc3lLM1mMkc", "14"),
    ("bednqL7ES0c", "15"),
    ("-yyFtErim0Y", "16"),
    ("KlKN3o2E3o8", "17"),
    ("kX5bKhB7jGM", "18"),
    ("7_HNKO2NRT0", "19"),
    ("64Qf-_Jl0as", "20"),
    ("AwjF8N-ugzk", "21"),
    ("D7Oc3Cp97nI", "22"),
]

OUTPUT_DIR = Path(__file__).parent / "downloads"
YTDLP = str(Path(__file__).parent / ".venv" / "bin" / "python")
SCRIPT = str(Path(__file__).parent / "ytdl.py")


def main():
    total = len(VIDEOS)
    success = 0
    failed = []

    for i, (vid, ep) in enumerate(VIDEOS, 1):
        url = f"https://www.youtube.com/watch?v={vid}"
        print(f"\n{'='*60}")
        print(f"[{i}/{total}] 第{ep}集 (ID: {vid})")
        print(f"{'='*60}")

        r = subprocess.run(
            [YTDLP, SCRIPT, url, "-o", str(OUTPUT_DIR)],
            timeout=600,
        )

        if r.returncode == 0:
            success += 1
            print(f"  ✓ 第{ep}集下载成功")
        else:
            failed.append((ep, vid))
            print(f"  ✗ 第{ep}集下载失败 (exit {r.returncode})")

    print(f"\n{'='*60}")
    print(f"批量下载完成: 成功 {success}/{total}")
    if failed:
        print("失败列表:")
        for ep, vid in failed:
            print(f"  第{ep}集: https://www.youtube.com/watch?v={vid}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
