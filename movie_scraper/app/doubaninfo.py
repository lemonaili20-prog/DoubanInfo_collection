from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import DOUBANINFO_API_BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT


class DoubanInfoError(RuntimeError):
    """Raised when DoubanInfo returns an unusable response."""


class DoubanInfoClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DOUBANINFO_API_BASE_URL,
        timeout: int = REQUEST_TIMEOUT,
    ):
        if not api_key:
            raise ValueError("DoubanInfo API Key 不能为空")

        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

        retry = Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            status=MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "X-API-KEY": api_key,
            "Accept": "application/json",
            "User-Agent": "movie-scraper/2.0",
        })

    def search(self, query: str) -> Any:
        """按电影名称、年份、Douban/IMDb/TMDB 标识符查询。"""
        return self._request({"url": query})

    def search_candidates(self, query: str) -> list[dict[str, Any]]:
        """执行搜索并统一返回候选列表。

        API 有两种返回形式：

        * 唯一匹配：直接返回影片对象（含 ``title`` / ``chinese_title``）；
        * 多个匹配：返回 ``{"status": "multiple", "results": [...]}``。

        本方法把两种情况都规范化为“列表”，方便上层做版本选择。
        唯一匹配时列表中只有一个元素。
        """
        data = self.search(query)

        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list) and results:
                return [r for r in results if isinstance(r, dict)]
            if data.get("title") or data.get("chinese_title") or data.get("original_title"):
                return [data]

        return []

    def get(self, identifier: str, source: str | None = None) -> Any:
        """按标识符查询，可选强制指定 douban/imdb 来源。"""
        params = {"url": identifier}
        if source:
            params["source"] = source
        return self._request(params)

    def _request(self, params: dict[str, str]) -> Any:
        response = self.session.get(
            self.base_url,
            params=params,
            timeout=self.timeout,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise DoubanInfoError(
                f"HTTP {response.status_code}: {response.text[:500]}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DoubanInfoError("API 返回的内容不是有效 JSON") from exc

        if isinstance(data, dict) and data.get("success") is False:
            message = data.get("message") or data.get("error") or "API 请求失败"
            raise DoubanInfoError(str(message))

        return data
