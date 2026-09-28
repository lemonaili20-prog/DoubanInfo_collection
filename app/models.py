from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Person:
    name: str
    original_name: str = ""
    role: str = ""


@dataclass
class MovieMetadata:
    title: str = ""
    original_title: str = ""
    year: Optional[int] = None
    media_type: str = "movie"  # movie / tv

    countries: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    release_dates: list[str] = field(default_factory=list)
    aka: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    certification: str = ""
    tagline: str = ""

    runtime: Optional[int] = None

    douban_rating: Optional[float] = None
    douban_votes: Optional[int] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None

    directors: list[Person] = field(default_factory=list)
    writers: list[Person] = field(default_factory=list)
    actors: list[Person] = field(default_factory=list)

    plot: str = ""
    awards: str = ""

    douban_id: str = ""
    douban_url: str = ""
    imdb_id: str = ""
    imdb_url: str = ""
    tmdb_id: str = ""
    tmdb_url: str = ""

    poster_url: str = ""
    cover_url: str = ""
    poster_backup_url: str = ""

    # 记录该条目来自哪个数据源（douban / imdb / tmdb），便于展示与排错。
    source: str = ""

    @property
    def display_title(self) -> str:
        """用于文件名/NFO 的标题，优先中文名。"""
        return self.title or self.original_title

    @property
    def sort_title(self) -> str:
        return self.display_title

    @property
    def uniqueids(self) -> dict[str, str]:
        ids: dict[str, str] = {}
        if self.imdb_id:
            ids["imdb"] = self.imdb_id
        if self.tmdb_id:
            ids["tmdb"] = self.tmdb_id
        if self.douban_id:
            ids["douban"] = self.douban_id
        return ids

