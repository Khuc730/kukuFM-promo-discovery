"""Deterministic parser for Kuku's timestamped screenplay text files."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Iterable

TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}\.\d{2}$")
SCENE_RE = re.compile(r"^SCENE\s+(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
EVENT_HEADER_RE = re.compile(r"^\*\*(.+?):\*\*\s*$", re.MULTILINE)


class ParseError(ValueError):
    """Raised when a screenplay does not match the supported format."""


def timestamp_to_seconds(value: str, *, source: str) -> float:
    value = value.strip()
    if not TIMESTAMP_RE.fullmatch(value):
        raise ParseError(f"{source}: invalid timestamp {value!r}; expected MM:SS.ss")
    minutes, seconds = value.split(":", 1)
    sec = float(seconds)
    if sec >= 60:
        raise ParseError(f"{source}: seconds component must be below 60: {value!r}")
    return int(minutes) * 60 + sec


@dataclass
class TimedElement:
    kind: str
    speaker_or_label: str
    start_ts: str
    end_ts: str
    start_sec: float
    end_sec: float
    text: str


@dataclass
class Scene:
    episode: int
    scene_number: int
    heading: str
    start_ts: str
    end_ts: str
    start_sec: float
    end_sec: float
    elements: list[TimedElement]
    warnings: list[str]


@dataclass
class Episode:
    episode: int
    source_file: str
    logline: str
    continuity_notes: str
    scenes: list[Scene]


def _required_header(text: str, label: str, filename: str) -> str:
    match = re.search(rf"^{re.escape(label)}\s*:\s*(.*?)\s*$", text, re.I | re.M)
    if not match or not match.group(1):
        raise ParseError(f"{filename}: missing or empty {label!r} header")
    return match.group(1).strip()


def parse_episode(path: str | Path) -> Episode:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"{path.name}: not valid UTF-8 text: {exc}") from exc

    episode_raw = _required_header(text, "EPISODE NUMBER", path.name)
    episode_match = re.search(r"(\d+)", episode_raw)
    if not episode_match:
        raise ParseError(f"{path.name}: cannot extract episode number from {episode_raw!r}")
    episode_no = int(episode_match.group(1))
    logline = _required_header(text, "EPISODE LOGLINE", path.name)
    continuity = _required_header(text, "CONTINUITY NOTES", path.name)

    script_match = re.search(r"---\s*SCRIPT START\s*---(.*?)---\s*SCRIPT END\s*---", text, re.I | re.S)
    if not script_match:
        raise ParseError(f"{path.name}: missing SCRIPT START / SCRIPT END markers")
    script = script_match.group(1)
    scene_matches = list(SCENE_RE.finditer(script))
    if not scene_matches:
        raise ParseError(f"{path.name}: no SCENE headings found inside script")

    scenes: list[Scene] = []
    for idx, sm in enumerate(scene_matches):
        block_start = sm.end()
        block_end = scene_matches[idx + 1].start() if idx + 1 < len(scene_matches) else len(script)
        block = script[block_start:block_end]
        scene_no = int(sm.group(1))

        heading = _required_header(block, "SCENE HEADING", f"{path.name} scene {scene_no}")
        start_ts = _required_header(block, "SCENE START", f"{path.name} scene {scene_no}")
        end_ts = _required_header(block, "SCENE END", f"{path.name} scene {scene_no}")
        start_sec = timestamp_to_seconds(start_ts, source=f"{path.name} scene {scene_no} start")
        end_sec = timestamp_to_seconds(end_ts, source=f"{path.name} scene {scene_no} end")
        if end_sec < start_sec:
            raise ParseError(f"{path.name} scene {scene_no}: scene end precedes scene start")

        elements: list[TimedElement] = []
        warnings: list[str] = []
        headers = list(EVENT_HEADER_RE.finditer(block))
        for hidx, hm in enumerate(headers):
            event_label = hm.group(1).strip()
            event_end = headers[hidx + 1].start() if hidx + 1 < len(headers) else len(block)
            event_block = block[hm.end():event_end]
            timing = re.search(
                r"^\s*Start:\s*\(([^)]+)\)\s*\|\s*End:\s*\(([^)]+)\)\s*$",
                event_block, re.I | re.M,
            )
            if not timing:
                raise ParseError(
                    f"{path.name} scene {scene_no}: event {event_label!r} has no valid Start/End timestamp line"
                )
            ev_start, ev_end = timing.group(1).strip(), timing.group(2).strip()
            ev_start_sec = timestamp_to_seconds(ev_start, source=f"{path.name} scene {scene_no} {event_label} start")
            ev_end_sec = timestamp_to_seconds(ev_end, source=f"{path.name} scene {scene_no} {event_label} end")
            if ev_end_sec < ev_start_sec:
                raise ParseError(f"{path.name} scene {scene_no}: event {event_label!r} ends before it starts")
            body = event_block[timing.end():].strip()
            if not body:
                raise ParseError(f"{path.name} scene {scene_no}: event {event_label!r} has empty content")
            if ev_start_sec < start_sec - 0.01 or ev_end_sec > end_sec + 0.01:
                # Valid event timestamps are preserved; the mismatch is surfaced for QA.
                warnings.append(
                    f"{event_label} ({ev_start}-{ev_end}) falls outside scene bounds "
                    f"({start_ts}-{end_ts})"
                )
            kind = "dialogue" if not event_label.upper() in {"CAMERA", "ACTION", "SOUND FX"} else event_label.lower()
            elements.append(TimedElement(kind, event_label, ev_start, ev_end,
                                         ev_start_sec, ev_end_sec, body))

        if not elements:
            raise ParseError(f"{path.name} scene {scene_no}: no timed elements found")
        scenes.append(Scene(episode_no, scene_no, heading, start_ts, end_ts,
                            start_sec, end_sec, elements, warnings))

    return Episode(episode_no, path.name, logline, continuity, scenes)


def parse_directory(input_dir: str | Path) -> list[Episode]:
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise ParseError(f"Input directory does not exist: {input_dir}")
    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise ParseError(f"No .txt screenplay files found in {input_dir}")
    episodes = [parse_episode(p) for p in files]
    numbers = [ep.episode for ep in episodes]
    if len(numbers) != len(set(numbers)):
        raise ParseError(f"Duplicate episode numbers found: {numbers}")
    return sorted(episodes, key=lambda ep: ep.episode)


def write_parsed_json(episodes: Iterable[Episode], output_path: str | Path) -> None:
    payload = [asdict(ep) for ep in episodes]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parse Kuku screenplay .txt files")
    parser.add_argument("--input", required=True, help="Directory containing episode .txt files")
    parser.add_argument("--out", required=True, help="Output parsed JSON path")
    args = parser.parse_args()
    parsed = parse_directory(args.input)
    write_parsed_json(parsed, args.out)
    scene_count = sum(len(ep.scenes) for ep in parsed)
    element_count = sum(len(scene.elements) for ep in parsed for scene in ep.scenes)
    warning_count = sum(len(scene.warnings) for ep in parsed for scene in ep.scenes)
    print(f"Parsed {len(parsed)} episodes, {scene_count} scenes, {element_count} timed elements.")
    print(f"Timestamp-boundary warnings: {warning_count}")
    print(f"Wrote {args.out}")
