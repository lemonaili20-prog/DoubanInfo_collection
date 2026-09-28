import xml.etree.ElementTree as ET

from app.exporter import build_metadata_json, build_nfo, safe_filename
from app.models import MovieMetadata, Person


def _sample_movie() -> MovieMetadata:
    return MovieMetadata(
        title="看上去很美",
        original_title="Little Red Flowers",
        year=2006,
        runtime=92,
        countries=["中国大陆", "意大利"],
        genres=["剧情", "喜剧"],
        languages=["汉语普通话"],
        release_dates=["2006-03-18 (中国大陆)"],
        aka=["小红花"],
        douban_rating=7.9,
        douban_votes=94200,
        imdb_rating=6.7,
        imdb_votes=1606,
        directors=[Person(name="张元", original_name="Yuan Zhang")],
        writers=[Person(name="宁岱", original_name="Dai Ning")],
        actors=[Person(name="董博文", original_name="Bowen Dong", role="方枪枪")],
        plot="测试简介",
        awards="第43届金马影展 - 最佳改编剧本",
        douban_id="1469441",
        douban_url="https://movie.douban.com/subject/1469441/",
        imdb_id="tt0492473",
        imdb_url="https://www.imdb.com/title/tt0492473/",
    )


def test_build_nfo_is_valid_xml():
    nfo = build_nfo(_sample_movie())
    root = ET.fromstring(nfo)
    assert root.tag == "movie"
    assert root.findtext("title") == "看上去很美"
    assert root.findtext("year") == "2006"
    assert root.findtext("runtime") == "92"
    assert root.findtext("doubanurl").endswith("/1469441/")
    uniqueids = {u.get("type"): u.text for u in root.findall("uniqueid")}
    assert uniqueids["imdb"] == "tt0492473"
    assert uniqueids["douban"] == "1469441"
    actor = root.find("actor")
    assert actor.findtext("name") == "董博文"
    assert actor.findtext("role") == "方枪枪"


def test_build_nfo_escapes_special_chars():
    movie = MovieMetadata(title='A & B <test>', plot='引号 "x" 与 & 符号')
    nfo = build_nfo(movie)
    root = ET.fromstring(nfo)
    assert root.findtext("title") == 'A & B <test>'
    assert root.findtext("plot") == '引号 "x" 与 & 符号'


def test_build_metadata_json():
    text = build_metadata_json(_sample_movie(), raw={"site": "douban"})
    assert '"title": "看上去很美"' in text
    assert '"raw"' in text


def test_safe_filename_strips_illegal_chars():
    assert safe_filename('问号?/星号*冒号:') == "问号星号冒号"
    assert safe_filename("") == "movie"
