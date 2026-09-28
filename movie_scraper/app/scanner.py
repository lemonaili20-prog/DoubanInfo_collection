"""扫描本地目录，找出待识别的影片条目。

支持两种输入方式：

1. 目录路径 —— 递归扫描其中的视频文件；
2. 单个视频文件路径 —— 直接作为一条待识别条目。

每条 :class:`MediaItem` 都记录了原始路径与解析出的查询关键字，
后续识别结果会导出到该条目所在目录。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .filename_parser import ParsedName, is_video_file, parse_name

# 扫描时忽略的目录名。
_IGNORED_DIRS = {
    "@eadir", ".ds_store", "system volume information", "$recycle.bin",
    "extras", "featurettes", "sample", "samples", "subs", "subtitles",
    "bdmv", "certificate", "trickplay", "metadata",
}


@dataclass
class MediaItem:
    """一条待识别的影片。"""

    path: Path
    kind: str  # "file" 或 "folder"
    parsed: ParsedName
    # 导出目标目录：默认取文件所在目录。
    output_dir: Path = field(default=None)  # type: ignore[assignment]
    # 直接输入片名（无真实路径）时为 True，此时不导出文件。
    virtual: bool = False

    def __post_init__(self) -> None:
        if self.output_dir is None:
            self.output_dir = self.path.parent if self.kind == "file" else self.path

    @property
    def name(self) -> str:
        """真实的文件/文件夹名，用于展示。"""
        return self.parsed.raw if self.virtual else self.path.name

    @property
    def query(self) -> str:
        return self.parsed.query


def _is_ignored(path: Path) -> bool:
    return path.name.lower() in _IGNORED_DIRS


def scan_folder(root: str | Path, recursive: bool = True) -> list[MediaItem]:
    """递归扫描目录下的视频文件。"""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"不是有效目录：{root_path}")

    items: list[MediaItem] = []
    iterator = root_path.rglob("*") if recursive else root_path.glob("*")

    for path in sorted(iterator):
        if not path.is_file() or not is_video_file(path):
            continue
        # 跳过位于忽略目录中的文件。
        if any(_is_ignored(parent) for parent in path.relative_to(root_path).parents):
            continue
        if _is_ignored(path):
            continue

        parsed = parse_name(path.name)
        if not parsed.title:
            continue
        items.append(MediaItem(path=path, kind="file", parsed=parsed))

    return items


def media_item_from_path(path: str | Path) -> MediaItem:
    """从单个文件/文件夹路径构造待识别条目。"""
    p = Path(path).expanduser().resolve()
    if p.is_dir():
        parsed = parse_name(p.name)
        return MediaItem(path=p, kind="folder", parsed=parsed)
    parsed = parse_name(p.name)
    return MediaItem(path=p, kind="file", parsed=parsed)


def resolve_inputs(raw_inputs: list[str], recursive: bool = True) -> list[MediaItem]:
    """把用户输入的路径列表展开成待识别条目。

    目录会递归扫描视频文件；单个视频文件直接加入；
    单个非视频文件按文件夹名解析处理。
    """
    items: list[MediaItem] = []
    seen: set[Path] = set()

    for raw in raw_inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            # 允许直接输入影片名（无路径）作为查询关键字。
            if not path.drive and not path.suffix:
                parsed = parse_name(raw)
                items.append(
                    MediaItem(
                        path=Path.cwd(),
                        kind="folder",
                        parsed=parsed,
                        virtual=True,
                    )
                )
            continue

        if path.is_dir():
            for item in scan_folder(path, recursive=recursive):
                if item.path not in seen:
                    seen.add(item.path)
                    items.append(item)
            # 目录内没有视频文件时，把目录名本身当作一部影片。
            if not any(i.path == path or path in i.path.parents for i in items):
                parsed = parse_name(path.name)
                items.append(MediaItem(path=path, kind="folder", parsed=parsed))
        else:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            items.append(media_item_from_path(resolved))

    return items
