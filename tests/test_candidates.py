from app.douban_parser import (
    parse_douban_json,
    parse_imdb_json,
    parse_json,
    summarize_candidate,
)
from app.doubaninfo import DoubanInfoClient
from unittest.mock import Mock, patch


DOUBAN_SINGLE = {
    "chinese_title": "看上去很美",
    "title": "看上去很美",
    "year": "2006",
    "region": "中国大陆 / 意大利",
    "genre": ["剧情", "喜剧"],
    "language": "汉语普通话",
    "release_date": "2006-03-18(中国大陆) / 2006-02-15(柏林电影节)",
    "runtime": "92分钟",
    "douban_rating_average": "7.9",
    "douban_votes": "94200",
    "imdb_id": "tt0492473",
    "imdb_rating": "6.7",
    "imdb_votes": "1606",
    "site": "douban",
    "sid": "1469441",
    "director": ["张元 Yuan Zhang"],
    "writer": ["宁 岱 Dai Ning"],
    "cast": ["董博文 Bowen Dong", "傅绍杰 Shaojie Fu (饰 小付阿姨)"],
    "summary": "测试简介",
    "poster": "https://example.com/poster.jpg",
    "success": True,
}

IMDB_SINGLE = {
    "aka": [
        {"country": "(original title)", "note": None, "title": "The Matrix"},
        {"country": "China", "note": "(Mandarin)", "title": "黑客帝国"},
    ],
    "year": 1999,
    "runtime": "2h 16m",
    "site": "imdb",
    "cast": [
        {"character": "Neo", "name": "Keanu Reeves", "link": ""},
        {"character": "Morpheus", "name": "Laurence Fishburne", "link": ""},
    ],
    "directors": [{"name": "Lana Wachowski", "link": ""}],
    "writers": [{"name": "Lilly Wachowski", "link": ""}],
    "original_title": "The Matrix",
    "title": None,
    "type": "movie",
    "link": "https://www.imdb.com/title/tt0133093/",
    "image": "https://example.com/matrix.jpg",
    "rating": 8.7,
    "vote_count": 2281537,
    "origin_country": ["United States"],
    "languages": ["English"],
    "genres": ["Action", "Sci-Fi"],
    "plot": "A computer hacker...",
    "keywords": ["dystopia"],
    "release": [
        {"country": "United States", "date": "March 31, 1999", "event": None},
    ],
    "certificates": [
        {"country": "United States", "ratings": [{"rating": "R"}]},
    ],
}


def test_parse_douban_json_splits_slash_fields():
    movie = parse_douban_json(DOUBAN_SINGLE)
    assert movie.title == "看上去很美"
    assert movie.year == 2006
    assert movie.countries == ["中国大陆", "意大利"]
    assert movie.languages == ["汉语普通话"]
    assert len(movie.release_dates) == 2
    assert movie.runtime == 92
    assert movie.douban_id == "1469441"
    assert movie.imdb_id == "tt0492473"
    assert movie.douban_url == "https://movie.douban.com/subject/1469441/"
    assert movie.actors[1].role == "小付阿姨"
    assert movie.actors[1].name == "傅绍杰"


def test_parse_imdb_json():
    movie = parse_imdb_json(IMDB_SINGLE)
    assert movie.title == "黑客帝国"
    assert movie.original_title == "The Matrix"
    assert movie.year == 1999
    assert movie.runtime == 136  # 2h16m
    assert movie.imdb_id == "tt0133093"
    assert movie.imdb_rating == 8.7
    assert movie.imdb_votes == 2281537
    assert movie.directors[0].name == "Lana Wachowski"
    assert movie.actors[0].role == "Neo"
    assert movie.countries == ["United States"]
    assert movie.certification == "R"
    assert "The Matrix" not in movie.aka


def test_parse_json_auto_detects_source():
    assert parse_json(DOUBAN_SINGLE).source == "douban"
    assert parse_json(IMDB_SINGLE).source == "imdb"


def test_summarize_candidate_douban():
    cand = summarize_candidate(DOUBAN_SINGLE)
    assert cand["title"] == "看上去很美"
    assert cand["year"] == 2006
    assert cand["site"] == "douban"
    assert cand["douban_id"] == "1469441"


def test_summarize_candidate_imdb():
    cand = summarize_candidate(IMDB_SINGLE)
    assert cand["title"] == "The Matrix"
    assert cand["site"] == "imdb"
    assert cand["imdb_id"] == "tt0133093"


@patch("app.doubaninfo.requests.Session.get")
def test_search_candidates_multiple(mock_get):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "status": "multiple",
        "success": True,
        "results": [DOUBAN_SINGLE, IMDB_SINGLE],
    }
    mock_get.return_value = response

    client = DoubanInfoClient(api_key="k", base_url="https://example.com/api")
    results = client.search_candidates("无间道")
    assert len(results) == 2


@patch("app.doubaninfo.requests.Session.get")
def test_search_candidates_single(mock_get):
    response = Mock()
    response.status_code = 200
    response.json.return_value = DOUBAN_SINGLE
    mock_get.return_value = response

    client = DoubanInfoClient(api_key="k", base_url="https://example.com/api")
    results = client.search_candidates("看上去很美")
    assert len(results) == 1
    assert results[0]["chinese_title"] == "看上去很美"
