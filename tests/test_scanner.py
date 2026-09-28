from pathlib import Path

from app.scanner import media_item_from_path, resolve_inputs, scan_folder


def _make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "Movies"
    (root / "看上去很美 (2006)").mkdir(parents=True)
    (root / "看上去很美 (2006)" / "看上去很美.2006.1080p.BluRay.mkv").write_text("x")
    (root / "The Matrix (1999)").mkdir(parents=True)
    (root / "The Matrix (1999)" / "The.Matrix.1999.1080p.mkv").write_text("x")
    (root / "The Matrix (1999)" / "The.Matrix.1999.1080p.srt").write_text("x")
    # 忽略目录中的视频不应被扫描到。
    (root / "sample").mkdir()
    (root / "sample" / "sample.2010.mkv").write_text("x")
    return root


def test_scan_folder_recursive(tmp_path):
    root = _make_tree(tmp_path)
    items = scan_folder(root, recursive=True)
    names = sorted(i.name for i in items)
    assert len(items) == 2
    assert "看上去很美.2006.1080p.BluRay.mkv" in names
    assert "The.Matrix.1999.1080p.mkv" in names


def test_scan_folder_skips_ignored_dirs(tmp_path):
    root = _make_tree(tmp_path)
    items = scan_folder(root)
    assert all("sample" not in i.path.parts for i in items)


def test_media_item_output_dir_is_parent(tmp_path):
    root = _make_tree(tmp_path)
    items = scan_folder(root)
    item = next(i for i in items if i.name.startswith("看上去很美"))
    assert item.output_dir == item.path.parent
    assert item.parsed.title == "看上去很美"


def test_media_item_from_folder(tmp_path):
    folder = tmp_path / "霸王别姬 (1993)"
    folder.mkdir()
    item = media_item_from_path(folder)
    assert item.kind == "folder"
    assert item.parsed.title == "霸王别姬"
    assert item.parsed.year == 1993
    assert item.output_dir == folder


def test_resolve_inputs_mixed(tmp_path):
    root = _make_tree(tmp_path)
    single = tmp_path / "独行.mkv"
    single.write_text("x")
    items = resolve_inputs([str(root), str(single)])
    # root 下 2 个视频 + 1 个单独文件
    assert len(items) == 3


def test_resolve_inputs_missing_path_is_ignored(tmp_path):
    items = resolve_inputs([str(tmp_path / "不存在.mkv")])
    assert items == []
