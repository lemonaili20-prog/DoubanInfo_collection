from app.douban_parser import parse_json, parse_bbcode


def test_parse_json():
    data = {
        "success": True,
        "title": "看上去很美",
        "chinese_title": "看上去很美",
        "year": 2006,
        "region": ["中国大陆", "意大利"],
        "genre": ["剧情", "喜剧"],
        "language": ["汉语普通话"],
        "release_date": ["2006-03-18(中国大陆)"],
        "runtime": "92分钟",
        "douban_rating": "7.9/10",
        "douban_votes": "94138",
        "imdb_rating": "6.7/10",
        "imdb_id": "tt0492473",
        "director": ["张元 Yuan Zhang"],
        "writer": ["宁岱 Dai Ning", "张元 Yuan Zhang"],
        "cast": ["董博文 Bowen Dong", "傅绍杰 Shaojie Fu (饰 小付阿姨)"],
        "summary": "测试简介",
        "poster": "https://example.com/poster.jpg",
        "douban_url": "https://movie.douban.com/subject/1469441/",
    }

    movie = parse_json(data)

    assert movie.title == "看上去很美"
    assert movie.year == 2006
    assert movie.runtime == 92
    assert movie.douban_rating == 7.9
    assert movie.douban_votes == 94138
    assert movie.imdb_id == "tt0492473"
    assert movie.douban_id == "1469441"
    assert movie.actors[1].role == "小付阿姨"


def test_parse_bbcode():
    text = """[img]https://example.com/poster.jpg[/img]
◎片　　名　看上去很美
◎译　　名　小红花 / Little Red Flowers
◎年　　代　2006
◎产　　地　中国大陆 / 意大利
◎类　　别　剧情 / 喜剧
◎语　　言　汉语普通话
◎豆瓣评分　7.9/10 (94138 人评价)
◎IMDb评分  6.7/10 (1603 人评价)
◎IMDb链接  https://www.imdb.com/title/tt0492473/
◎豆瓣链接　https://movie.douban.com/subject/1469441/
◎片　　长　92分钟
"""

    movie = parse_bbcode(text)

    assert movie.title == "看上去很美"
    assert movie.year == 2006
    assert movie.runtime == 92
    assert movie.poster_url.endswith("poster.jpg")
    assert movie.imdb_id == ""
