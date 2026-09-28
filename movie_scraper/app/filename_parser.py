"""从文件名 / 文件夹名中提取影片名称与年份。

本地影片命名千奇百怪，例如：

    看上去很美.2006.1080p.BluRay.x264.mkv
    Little.Red.Flowers.2006.1080p.BluRay.DD5.1.x264-CMCT/
    [圣城家园字幕组]这个杀手不太冷.1994.BluRay.1080p.国法双语.mkv
    The.Matrix.1999.BluRay.1080p.x264.mkv

本模块的目标不是做到 100% 精确，而是从这些噪音里提取出足够
可靠的 ``title`` + ``year`` 作为 API 查询关键字。核心思路：

1. 去掉发布组方括号、字幕组等前后缀；
2. 定位“年份 / 分辨率 / 编码 / 音轨”等技术标记出现的位置；
3. 把这些标记之前的内容作为片名。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 视频文件扩展名。
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".m2ts",
    ".mpg", ".mpeg", ".rmvb", ".rm", ".vob", ".iso", ".webm", ".3gp",
}

# 需要剔除的常见技术标记（来源 / 编码 / 音频 / 语言等）。
_TECH_TAGS = {
    "bluray", "blu", "ray", "bdrip", "brrip", "dvdrip", "dvd", "webrip", "web",
    "webdl", "web-dl", "hdtv", "hdrip", "remux", "uhd", "hddvd", "vhsrip",
    "tvrip", "bd", "rip",
    "x264", "x265", "h264", "h265", "hevc", "avc", "xvid", "divx", "av1",
    "10bit", "8bit", "hi10p",
    "aac", "ac3", "dts", "dtshd", "truehd", "ddp", "dd", "flac", "mp3",
    "atmos", "dolby", "eac3", "lpcm", "pcm", "dtsx",
    "hdr", "hdr10", "dovi", "sdr", "imax", "proper", "repack", "internal",
    "complete", "limited", "extended", "uncut", "remastered", "criterion",
    "cn", "chs", "cht", "eng", "gb", "big5", "双语", "国语", "粤语", "中字",
    "简繁", "简体", "繁体", "字幕",
}

# 需要去掉的常见中文发布组标记。
_CN_GROUP_RE = re.compile(
    r"[\[\(【（][^\]\)】）]{0,40}(字幕组|压制组|发布组|制作组|影视|出品|字幕社)"
    r"[^\]\)】）]{0,40}[\]\)】）]"
)
# [xx] / 【xx】 这类方括号内容（多为发布组或语言标记）。
_BRACKET_RE = re.compile(r"[\[【][^\]】]{0,40}[\]】]")
# 年份：1900-2099。
_YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
# 分辨率：1080p / 720p / 2160p / 4K。
_RES_RE = re.compile(r"(?i)^\d{3,4}p$|^4k$|^8k$")
# 发布组标记：xxx-yyy。
_GROUP_TOKEN_RE = re.compile(r"^[A-Za-z0-9]{2,}[-@][A-Za-z0-9]{2,}$")


@dataclass
class ParsedName:
    """从文件名/文件夹名解析出的查询线索。"""

    raw: str = ""
    title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    media_type: str = "movie"  # movie / tv
    tokens: list[str] = field(default_factory=list)

    @property
    def query(self) -> str:
        """组合成发送给 API 的查询字符串。"""
        parts = [p for p in (self.title, str(self.year) if self.year else "") if p]
        return " ".join(parts)


def _detect_season_episode(text: str) -> tuple[int | None, int | None, str]:
    season = episode = None
    media_type = "movie"

    m = re.search(r"(?i)\bS(\d{1,2})(?:E(\d{1,3}))?\b", text)
    if m:
        season = int(m.group(1))
        if m.group(2):
            episode = int(m.group(2))
        media_type = "tv"

    if season is None:
        m = re.search(r"第\s*(\d{1,3})\s*季", text)
        if m:
            season = int(m.group(1))
            media_type = "tv"

    if episode is None:
        m = re.search(r"第\s*(\d{1,3})\s*[集话話]", text)
        if m:
            episode = int(m.group(1))
            media_type = "tv"

    return season, episode, media_type


def _tokenize(text: str) -> list[str]:
    """按常见分隔符切分，同时保留中文连续片段。"""
    return [t for t in re.split(r"[._\-\u2013\u2014+\s]+", text) if t]


def _is_tech_token(token: str) -> bool:
    low = token.lower().strip("()[]{}")
    if not low:
        return True
    if low in _TECH_TAGS:
        return True
    if _RES_RE.match(low):
        return True
    if _YEAR_RE.fullmatch(low):
        return True
    if re.fullmatch(r"(?i)(x|h)26[45]", low):
        return True
    return False


def _extract_title_and_year(stem: str) -> tuple[str, int | None]:
    # 1. 去掉方括号内容与字幕组标记。
    work = _CN_GROUP_RE.sub(" ", stem)
    work = _BRACKET_RE.sub(" ", work)
    work = work.strip(" ._-")

    tokens = _tokenize(work)
    if not tokens:
        return stem.strip(), None

    # 2. 找到第一个技术标记 / 年份的位置，之前的内容视为片名。
    cut = len(tokens)
    year: int | None = None
    for i, tok in enumerate(tokens):
        ym = _YEAR_RE.fullmatch(tok.strip("()[]{}"))
        if ym:
            if year is None:
                year = int(ym.group(1))
            cut = i
            break
        if _is_tech_token(tok):
            cut = i
            break

    title_tokens = tokens[:cut] if cut > 0 else tokens[:1]

    # 3. 片名里若混入发布组尾巴（如 CMCT），尽量去掉。
    if title_tokens and cut == len(tokens) and len(title_tokens) > 1:
        if _GROUP_TOKEN_RE.match(title_tokens[-1]):
            title_tokens = title_tokens[:-1]

    title = " ".join(title_tokens).strip(" ._-")

    # 4. 若年份没在切分过程中找到，再从整串里兜底查找。
    if year is None:
        ym = _YEAR_RE.search(work)
        if ym:
            year = int(ym.group(1))

    return title or stem.strip(), year


def parse_name(name: str) -> ParsedName:
    """解析文件名或文件夹名为 :class:`ParsedName`。

    ``name`` 既可以是完整路径，也可以是纯文件名 / 文件夹名。
    """
    p = Path(str(name))
    stem = p.stem if p.suffix.lower() in VIDEO_EXTENSIONS else p.name

    season, episode, media_type = _detect_season_episode(stem)
    title, year = _extract_title_and_year(stem)

    # 去掉标题中残留的季集标记（S01E02 / 第二季）。
    title = re.sub(r"(?i)\bS\d{1,2}(E\d{1,3})?\b", " ", title)
    title = re.sub(r"第\s*\d{1,3}\s*[集话話季部]", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" ._-")

    return ParsedName(
        raw=stem,
        title=title,
        year=year,
        season=season,
        episode=episode,
        media_type=media_type,
        tokens=title.split(),
    )


def is_video_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS
