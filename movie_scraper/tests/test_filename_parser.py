from app.filename_parser import is_video_file, parse_name


def test_parse_chinese_movie_with_year():
    p = parse_name("看上去很美.2006.1080p.BluRay.x264.mkv")
    assert p.title == "看上去很美"
    assert p.year == 2006
    assert p.media_type == "movie"
    assert p.query == "看上去很美 2006"


def test_parse_english_dotted_name():
    p = parse_name("The.Matrix.1999.BluRay.1080p.x264.mkv")
    assert p.title == "The Matrix"
    assert p.year == 1999


def test_parse_with_release_group():
    p = parse_name(
        "Little.Red.Flowers.2006.1080p.BluRay.DD5.1.x264-CMCT"
    )
    assert p.title == "Little Red Flowers"
    assert p.year == 2006


def test_parse_with_subtitle_group_brackets():
    p = parse_name("[圣城家园字幕组]这个杀手不太冷.1994.BluRay.1080p.mkv")
    assert p.title == "这个杀手不太冷"
    assert p.year == 1994


def test_parse_tv_episode():
    p = parse_name("权力的游戏 S01E01 1080p.mkv")
    assert p.title == "权力的游戏"
    assert p.season == 1
    assert p.episode == 1
    assert p.media_type == "tv"


def test_parse_folder_name():
    p = parse_name("/movies/霸王别姬 (1993)")
    assert p.title == "霸王别姬"
    assert p.year == 1993


def test_parse_remux_noise():
    p = parse_name("Inception.2010.2160p.UHD.BluRay.REMUX.HEVC.DTS-HD.mkv")
    assert p.title == "Inception"
    assert p.year == 2010


def test_is_video_file():
    assert is_video_file("a.mkv")
    assert is_video_file("a.MP4")
    assert not is_video_file("a.srt")
    assert not is_video_file("a.jpg")
