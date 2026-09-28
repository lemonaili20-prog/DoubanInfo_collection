from __future__ import annotations

import re
from typing import Any

from .models import MovieMetadata, Person


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _split_slash(value: Any) -> list[str]:
    """处理“中国大陆 / 意大利”这类用斜杠分隔的字段。"""
    items: list[str] = []
    for chunk in _as_list(value):
        parts = re.split(r"\s*/\s*", chunk)
        items.extend(p.strip() for p in parts if p.strip())
    return items


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def _parse_runtime(value: Any) -> int | None:
    """把 ``92分钟`` / ``2h 16m`` / ``136 min`` 统一成分钟数。"""
    if value is None or value == "":
        return None

    text = str(value)
    hours = re.search(r"(\d+)\s*(?:h|小时)", text, re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*(?:m(?:in)?|分钟)", text, re.IGNORECASE)

    if hours or minutes:
        total = 0
        if hours:
            total += int(hours.group(1)) * 60
        if minutes:
            total += int(minutes.group(1))
        return total or None

    return _to_int(text)


def _split_person_name(text: str) -> tuple[str, str]:
    """把 ``张元 Yuan Zhang`` / ``宁 岱 Dai Ning`` 拆成中文名 + 原名。"""
    text = text.strip()
    if not text:
        return "", ""

    # 前导的中文（可能夹杂空格）作为本地名。
    match = re.match(r"^([\u4e00-\u9fff\u3000-\u303f\s]+?)(?=\s*[A-Za-z]|$)", text)
    if match:
        cjk_part = match.group(1)
        rest = text[match.end():].strip()
        name = re.sub(r"\s+", "", cjk_part)
        if name:
            return name, rest

    parts = re.split(r"\s+", text, maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _parse_person_douban(value: Any, parse_role: bool = False) -> list[Person]:
    result = []
    for item in _as_list(value):
        role = ""
        text = item

        if parse_role:
            match = re.search(r"\s*\(饰\s*(.*?)\)\s*$", text)
            if match:
                role = match.group(1).strip()
                text = text[:match.start()].strip()

        name, original_name = _split_person_name(text)
        result.append(Person(name=name, original_name=original_name, role=role))
    return result


def _parse_person_imdb(value: Any) -> list[Person]:
    """IMDb 来源的演职员是 ``[{"name": ..., "character": ...}, ...]``。"""
    result = []
    for item in value or []:
        if isinstance(item, dict):
            result.append(
                Person(
                    name=str(item.get("name") or "").strip(),
                    original_name="",
                    role=str(item.get("character") or "").strip(),
                )
            )
        elif item:
            name, original_name = _split_person_name(str(item))
            result.append(Person(name=name, original_name=original_name))
    return result


def _extract_id(url: str, pattern: str) -> str:
    if not url:
        return ""
    match = re.search(pattern, url)
    return match.group(1) if match else ""


def _format_awards(awards_data: Any) -> str:
    if not isinstance(awards_data, list):
        return str(awards_data or "").strip()

    chunks = []
    for award in awards_data:
        if isinstance(award, dict):
            festival = str(award.get("festival") or "").strip()
            details = award.get("awards")
            if isinstance(details, list):
                detail_text = "; ".join(str(x) for x in details)
            else:
                detail_text = str(details or "").strip()
            chunks.append(" - ".join(x for x in (festival, detail_text) if x))
        elif award:
            chunks.append(str(award))
    return "\n".join(chunks)


def _format_imdb_release(release: Any) -> list[str]:
    dates = []
    for item in release or []:
        if isinstance(item, dict):
            country = str(item.get("country") or "").strip()
            date = str(item.get("date") or "").strip()
            event = str(item.get("event") or "").strip()
            suffix = f"({event})" if event else (f"({country})" if country else "")
            text = " ".join(x for x in (date, suffix) if x)
            if text:
                dates.append(text)
    return dates


def _pick_certification(certificates: Any) -> str:
    if not isinstance(certificates, list):
        return ""
    fallback = ""
    for item in certificates:
        if not isinstance(item, dict):
            continue
        ratings = item.get("ratings") or []
        if not isinstance(ratings, list) or not ratings:
            continue
        rating = str((ratings[0] or {}).get("rating") or "").strip()
        if not rating:
            continue
        if str(item.get("country") or "").lower() in {"united states", "usa", "us"}:
            return rating
        fallback = fallback or rating
    return fallback


def _detect_source(data: dict[str, Any]) -> str:
    site = str(data.get("site") or "").lower()
    if site in {"imdb", "tmdb", "douban"}:
        return site
    if "original_title" in data and "chinese_title" not in data:
        return "imdb"
    return "douban"


def parse_douban_json(data: dict[str, Any]) -> MovieMetadata:
    """解析豆影（豆瓣来源）返回的 JSON。"""

    chinese_title = str(data.get("chinese_title") or "").strip()
    title = str(data.get("title") or "").strip()

    # API 某些结果的 title 可能同时包含中英文标题；
    # chinese_title 存在时优先作为本地标题。
    local_title = chinese_title or title

    if title and chinese_title and title != chinese_title:
        original_title = title
    else:
        original_title = str(data.get("original_title") or "").strip()

    release_dates = _split_slash(data.get("release_date"))
    if not release_dates:
        release_dates = _split_slash(data.get("premiere_date"))

    douban_id = str(data.get("douban_id") or data.get("sid") or "").strip()
    douban_url = str(data.get("douban_url") or data.get("douban") or "").strip()
    if not douban_id:
        douban_id = _extract_id(douban_url, r"/subject/(\d+)")
    if not douban_url and douban_id:
        douban_url = f"https://movie.douban.com/subject/{douban_id}/"

    imdb_url = str(data.get("imdb_url") or "").strip()
    imdb_id = str(data.get("imdb_id") or "").strip()
    if not imdb_id and imdb_url:
        imdb_id = _extract_id(imdb_url, r"/title/(tt\d+)")
    if not imdb_url and imdb_id:
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"

    is_tv = bool(data.get("episodes") or data.get("season_count"))

    return MovieMetadata(
        title=local_title,
        original_title=original_title,
        year=_to_int(data.get("year")),
        media_type="tv" if is_tv else "movie",
        countries=_split_slash(data.get("region")),
        genres=_as_list(data.get("genre")),
        languages=_split_slash(data.get("language")),
        release_dates=release_dates,
        aka=_as_list(data.get("aka")),
        runtime=_parse_runtime(data.get("runtime") or data.get("duration")),
        douban_rating=_to_float(
            data.get("douban_rating_average") or data.get("douban_rating")
        ),
        douban_votes=_to_int(data.get("douban_votes")),
        imdb_rating=_to_float(data.get("imdb_rating")),
        imdb_votes=_to_int(data.get("imdb_votes")),
        directors=_parse_person_douban(data.get("director")),
        writers=_parse_person_douban(data.get("writer")),
        actors=_parse_person_douban(data.get("cast"), parse_role=True),
        plot=str(data.get("summary") or "").strip(),
        awards=_format_awards(data.get("awards")),
        douban_id=douban_id,
        douban_url=douban_url,
        imdb_id=imdb_id,
        imdb_url=imdb_url,
        poster_url=str(data.get("poster") or data.get("dbposter") or "").strip(),
        cover_url=str(data.get("cover") or "").strip(),
        poster_backup_url=str(data.get("posterbak") or "").strip(),
        source="douban",
    )


def parse_imdb_json(data: dict[str, Any]) -> MovieMetadata:
    """解析豆影（IMDb 来源）返回的 JSON。"""

    original_title = str(data.get("original_title") or data.get("title") or "").strip()

    # aka 可能是 [{"country":..,"note":..,"title":..}] 或 [str]。
    aka_titles: list[str] = []
    for item in data.get("aka") or []:
        if isinstance(item, dict):
            t = str(item.get("title") or "").strip()
            if t:
                aka_titles.append(t)
        elif item:
            aka_titles.append(str(item).strip())

    # 若有中文本地化标题，可作为展示标题。
    title = ""
    for t in aka_titles:
        if re.search(r"[\u4e00-\u9fff]", t):
            title = t
            break
    title = title or original_title

    imdb_id = str(data.get("imdb_id") or "").strip()
    link = str(data.get("link") or "").strip()
    if not imdb_id and link:
        imdb_id = _extract_id(link, r"/title/(tt\d+)")
    imdb_url = link or (f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "")

    # aka 中已提升为 title/original_title 的条目不再重复记录。
    extra_aka = [
        t for t in aka_titles if t and t not in {title, original_title}
    ]

    return MovieMetadata(
        title=title,
        original_title=original_title,
        year=_to_int(data.get("year")),
        media_type=str(data.get("type") or "movie").strip() or "movie",
        countries=_as_list(data.get("origin_country")),
        genres=_as_list(data.get("genres")),
        languages=_as_list(data.get("languages")),
        release_dates=_format_imdb_release(data.get("release")),
        aka=extra_aka,
        keywords=_as_list(data.get("keywords")),
        certification=_pick_certification(data.get("certificates")),
        runtime=_parse_runtime(data.get("runtime")),
        imdb_rating=_to_float(data.get("rating")),
        imdb_votes=_to_int(data.get("vote_count")),
        directors=_parse_person_imdb(data.get("directors")),
        writers=_parse_person_imdb(data.get("writers")),
        actors=_parse_person_imdb(data.get("cast")),
        plot=str(data.get("plot") or "").strip(),
        imdb_id=imdb_id,
        imdb_url=imdb_url,
        poster_url=str(data.get("image") or "").strip(),
        source="imdb",
    )


def parse_json(data: dict[str, Any]) -> MovieMetadata:
    """把 DoubanInfo JSON 规范化为 MovieMetadata。

    自动识别 ``douban`` / ``imdb`` 两种返回结构。
    """
    if _detect_source(data) == "imdb":
        return parse_imdb_json(data)
    return parse_douban_json(data)


def summarize_candidate(data: dict[str, Any]) -> dict[str, Any]:
    """从候选条目里提取用于列表展示的简要信息。"""
    if _detect_source(data) == "imdb":
        link = str(data.get("link") or "").strip()
        return {
            "title": str(data.get("original_title") or data.get("title") or "").strip(),
            "year": _to_int(data.get("year")),
            "site": "imdb",
            "rating": _to_float(data.get("rating")),
            "type": str(data.get("type") or "").strip(),
            "imdb_id": str(data.get("imdb_id") or "").strip()
            or _extract_id(link, r"/title/(tt\d+)"),
            "douban_id": "",
            "raw": data,
        }

    return {
        "title": str(data.get("chinese_title") or data.get("title") or "").strip(),
        "year": _to_int(data.get("year")),
        "site": "douban",
        "rating": _to_float(
            data.get("douban_rating_average") or data.get("douban_rating")
        ),
        "type": "tv" if data.get("episodes") or data.get("season_count") else "movie",
        "imdb_id": str(data.get("imdb_id") or "").strip(),
        "douban_id": str(data.get("sid") or data.get("douban_id") or "").strip(),
        "raw": data,
    }


def parse_bbcode(text: str) -> MovieMetadata:
    """兼容旧版 DoubanInfo BBCode 返回格式。"""

    def field(name: str) -> str:
        pattern = rf"◎\s*{re.escape(name)}\s*(.*)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    title = field("片　　名") or field("片名")
    original_title = field("译　　名")
    year = _to_int(field("年　　代"))

    runtime_match = re.search(r"(\d+)\s*分钟", field("片　　长"))
    runtime = int(runtime_match.group(1)) if runtime_match else None

    return MovieMetadata(
        title=title,
        original_title=original_title,
        year=year,
        countries=[x.strip() for x in field("产　　地").split("/") if x.strip()],
        genres=[x.strip() for x in field("类　　别").split("/") if x.strip()],
        languages=[x.strip() for x in field("语　　言").split("/") if x.strip()],
        release_dates=[x.strip() for x in field("上映日期").split("/") if x.strip()],
        runtime=runtime,
        douban_rating=_to_float(field("豆瓣评分")),
        imdb_rating=_to_float(field("IMDb评分")),
        douban_url=re.search(r"◎豆瓣链接\s*(\S+)", text).group(1)
        if re.search(r"◎豆瓣链接\s*(\S+)", text) else "",
        imdb_url=re.search(r"◎IMDb链接\s*(\S+)", text).group(1)
        if re.search(r"◎IMDb链接\s*(\S+)", text) else "",
        poster_url=(re.search(r"\[img\](.*?)\[/img\]", text).group(1)
                    if re.search(r"\[img\](.*?)\[/img\]", text) else ""),
    )
