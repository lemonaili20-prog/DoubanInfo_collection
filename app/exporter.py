"""把识别出的 :class:`MovieMetadata` 导出到影片所在目录。

支持导出：

* ``movie.nfo``   —— Kodi/Emby/Jellyfin 通用元数据；
* ``metadata.json`` —— 规范化后的元数据与原始 API 数据；
* ``poster.jpg``  —— 海报图片。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from .models import MovieMetadata, Person
from config import REQUEST_TIMEOUT

# Windows 文件名非法字符。
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, fallback: str = "movie") -> str:
    """把标题转成安全的文件名。"""
    cleaned = _INVALID_FILENAME_CHARS.sub("", str(name or "")).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def _xml_escape(text: Any) -> str:
    s = str(text if text is not None else "")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _person_tag(tag: str, person: Person) -> str:
    lines = [f"    <{tag}>"]
    if person.name:
        lines.append(f"      <name>{_xml_escape(person.name)}</name>")
    if person.original_name:
        lines.append(f"      <altname>{_xml_escape(person.original_name)}</altname>")
    if person.role:
        lines.append(f"      <role>{_xml_escape(person.role)}</role>")
    lines.append(f"    </{tag}>")
    return "\n".join(lines)


def build_nfo(movie: MovieMetadata) -> str:
    """生成 Kodi 兼容的 movie.nfo 内容。"""
    lines: list[str] = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<movie>"]

    def add(tag: str, value: Any) -> None:
        if value is None or value == "":
            return
        lines.append(f"  <{tag}>{_xml_escape(value)}</{tag}>")

    add("title", movie.display_title)
    add("originaltitle", movie.original_title)
    add("sorttitle", movie.sort_title)
    if movie.year:
        add("year", movie.year)
    if movie.douban_rating is not None:
        add("rating", movie.douban_rating)
        add("votes", movie.douban_votes or "")
    if movie.imdb_rating is not None:
        add("imdb_rating", movie.imdb_rating)
        add("imdb_votes", movie.imdb_votes or "")
    if movie.runtime:
        add("runtime", movie.runtime)
    add("plot", movie.plot)
    add("tagline", movie.tagline)
    add("outline", movie.plot[:300] if movie.plot else "")

    for genre in movie.genres:
        add("genre", genre)
    for country in movie.countries:
        add("country", country)
    for language in movie.languages:
        add("language", language)
    for date in movie.release_dates:
        add("premiered", date)
    for aka in movie.aka:
        add("tag", aka)
    add("certification", movie.certification)
    add("awards", movie.awards)

    for director in movie.directors:
        lines.append(_person_tag("director", director))
    for writer in movie.writers:
        lines.append(_person_tag("credits", writer))
    for actor in movie.actors:
        lines.append(_person_tag("actor", actor))

    for source, value in movie.uniqueids.items():
        lines.append(f'  <uniqueid type="{_xml_escape(source)}" default="true">{_xml_escape(value)}</uniqueid>')

    if movie.douban_url:
        add("doubanurl", movie.douban_url)
    if movie.imdb_url:
        add("imdburl", movie.imdb_url)

    lines.append("</movie>")
    return "\n".join(lines) + "\n"


def build_metadata_json(movie: MovieMetadata, raw: Any = None) -> str:
    """生成 metadata.json 内容。"""
    payload: dict[str, Any] = {"metadata": asdict(movie)}
    if raw is not None:
        payload["raw"] = raw
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _download_image(url: str, target: Path, session: requests.Session | None = None) -> bool:
    if not url:
        return False
    sess = session or requests.Session()
    sess.headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) movie-scraper/2.0",
    )
    try:
        response = sess.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        return False

    target.write_bytes(response.content)
    return True


def export(
    movie: MovieMetadata,
    output_dir: str | Path,
    *,
    write_nfo: bool = True,
    write_json: bool = True,
    download_poster: bool = True,
    raw: Any = None,
    session: requests.Session | None = None,
) -> dict[str, Path]:
    """把元数据导出到 ``output_dir``。

    返回实际写出的文件路径字典，键为 ``nfo`` / ``json`` / ``poster`` / ``fanart``。
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}

    if write_nfo:
        nfo_path = out_dir / "movie.nfo"
        nfo_path.write_text(build_nfo(movie), encoding="utf-8")
        written["nfo"] = nfo_path

    if write_json:
        json_path = out_dir / "metadata.json"
        json_path.write_text(build_metadata_json(movie, raw=raw), encoding="utf-8")
        written["json"] = json_path

    if download_poster:
        poster_sources = [
            movie.poster_url,
            movie.cover_url,
            movie.poster_backup_url,
        ]
        poster_path = out_dir / "poster.jpg"
        for url in poster_sources:
            if url and _download_image(url, poster_path, session=session):
                written["poster"] = poster_path
                break

        # 背景图（可选）：单独一张 fanart.jpg。
        if movie.cover_url and movie.cover_url != movie.poster_url:
            fanart_path = out_dir / "fanart.jpg"
            if _download_image(movie.cover_url, fanart_path, session=session):
                written["fanart"] = fanart_path

    return written
