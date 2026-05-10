"""File I/O: vs-chart.json loading and .vsm reading/writing."""

import json
import os
import re

from model import (
    Chart, ChartInfo, Difficulty, DifficultyMeta, Note, TimingPoint, Gimmick
)


def strip_json_comments(text: str) -> str:
    """Remove // comments and trailing commas from JSON-like text."""
    # Remove single-line comments (// ...)
    result = []
    for line in text.split("\n"):
        # Remove // comments, but be careful with URLs
        # Simple approach: find // not inside a string
        in_string = False
        string_char = None
        i = 0
        while i < len(line):
            c = line[i]
            if in_string:
                if c == "\\":
                    i += 2
                    continue
                if c == string_char:
                    in_string = False
                i += 1
            else:
                if c in ('"', "'"):
                    in_string = True
                    string_char = c
                    i += 1
                elif c == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    line = line[:i]
                    break
                else:
                    i += 1
        result.append(line)

    text = "\n".join(result)
    # Remove trailing commas before ] or }
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def load_chart(folder_path: str) -> Chart:
    """Load vs-chart.json and find the song file in the given folder.

    Returns a Chart object. Raises ValueError on problems.
    """
    chart_path = os.path.join(folder_path, "vs-chart.json")
    if not os.path.isfile(chart_path):
        raise ValueError(f"找不到 vs-chart.json: {chart_path}")

    with open(chart_path, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = strip_json_comments(raw)
    data = json.loads(cleaned)

    # Parse song info
    song_data = data.get("song", {})
    info = ChartInfo(
        name=song_data.get("name", ""),
        composer=song_data.get("composer", ""),
        display_bpm=song_data.get("bpm", "120"),
    )

    # Find song file (ogg or mp3)
    song_file = ""
    songs_found = []
    for fname in os.listdir(folder_path):
        lower = fname.lower()
        if lower.endswith(".ogg") or lower.endswith(".mp3"):
            songs_found.append(os.path.join(folder_path, fname))
    if len(songs_found) > 1:
        raise ValueError(
            f"文件夹内存在多个歌曲文件，请只保留一个:\n"
            + "\n".join(songs_found)
        )
    if songs_found:
        song_file = songs_found[0]

    # Parse difficulties
    difficulties = []
    for diff_data in data.get("diffs", []):
        meta_data = diff_data.get("meta", {})
        meta = DifficultyMeta(
            diff_name=meta_data.get("diff_name", ""),
            diff1=meta_data.get("diff1", ""),
            diff2=meta_data.get("diff2", ""),
            charter=meta_data.get("charter", ""),
        )

        # Parse timing points
        timing_points = []
        for tp_data in diff_data.get("timing", []):
            timing_points.append(TimingPoint(
                time_ms=float(tp_data.get("time", 0)),
                bpm=float(tp_data.get("bpm", 120)),
                num=int(tp_data.get("num", 4)),
                den=int(tp_data.get("den", 4)),
            ))

        # Parse notes
        notes = []
        for n_data in diff_data.get("notes", []):
            snm = int(n_data.get("snm", 0))
            if snm == 2:
                snm = 0  # treat as normal
            notes.append(Note(
                lane=int(n_data.get("lane", 0)),
                time_ms=float(n_data.get("time", 0)),
                width=int(n_data.get("width", 1)),
                snm=snm,
                length_ms=float(n_data.get("len", 0)),
            ))

        difficulties.append(Difficulty(
            meta=meta,
            notes=notes,
            timing_points=timing_points,
        ))

    return Chart(info=info, difficulties=difficulties, song_file=song_file)


def _extract_beat(raw: str) -> float:
    """Extract numeric beat from a field like '19.9' or '19.9(:35.9:8)'."""
    m = re.match(r"([-+]?\d+\.?\d*)", raw.strip())
    if m:
        return float(m.group(1))
    raise ValueError(f"无法解析拍数: {raw}")


def load_vsm(filepath: str) -> list[Gimmick]:
    """Load gimmicks from a .vsm file.

    Lines not matching the standard 7-field format are silently skipped.
    """
    if not os.path.isfile(filepath):
        return []

    gimmicks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("!"):
                continue

            parts = line.split(",")
            if len(parts) != 7:
                continue

            try:
                beat = _extract_beat(parts[0])
                duration = float(parts[1].strip())
                easing = parts[2].strip()
                value1 = parts[3].strip()
                value2 = parts[4].strip()
                modname = parts[5].strip()
                proxy = parts[6].strip()

                gimmicks.append(Gimmick(
                    beat=beat, duration=duration, easing=easing,
                    value1=value1, value2=value2,
                    modname=modname, proxy=proxy,
                ))
            except (ValueError, IndexError):
                continue

    return gimmicks


def save_vsm(filepath: str, gimmicks: list[Gimmick]):
    """Write gimmicks to a .vsm file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("!proxies:0\n")
        f.write("!obj:obj_custom_gimmick\n")
        for g in gimmicks:
            f.write(
                f"{g.beat},{g.duration},{g.easing},"
                f"{g.value1},{g.value2},{g.modname},{g.proxy}\n"
            )
