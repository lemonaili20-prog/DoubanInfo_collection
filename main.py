"""命令行入口：识别本地影片并导出元数据。

使用示例：

    python main.py                            # 交互式主菜单
    python main.py "D:/Movies/无间道"          # 传入文件夹
    python main.py a.mkv b.mkv                # 传入多个文件
    python main.py "D:/Movies" --yes          # 自动选择最佳候选，不逐条确认

自定义刮削：

    # 交互式：主菜单选 2，然后输入片名/编号/链接与目标文件夹
    python main.py

    # 命令行直接指定查询内容与目标文件夹
    python main.py --query "看上去很美 2006" --out "D:/Media/看上去很美 (2006)"
    python main.py --query tt0492473 --out "D:/Media/无间道"
    python main.py -q "https://movie.douban.com/subject/1307914/" -o "D:/Media/无间道"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.douban_parser import parse_json, summarize_candidate
from app.doubaninfo import DoubanInfoClient, DoubanInfoError
from app.exporter import export
from app.models import MovieMetadata
from app.scanner import MediaItem, resolve_inputs
from config import DOUBANINFO_API_KEY


def _setup_console() -> None:
    """让控制台输出更宽容。

    Windows 中文环境默认使用 GBK，无法编码 ``✓`` 等符号会直接抛
    ``UnicodeEncodeError`` 导致程序中断，这里统一降级为替换字符。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def _print_candidates(candidates: list[dict]) -> None:
    print("\n找到多个匹配版本：")
    for idx, cand in enumerate(candidates, start=1):
        title = cand.get("title") or "(无标题)"
        year = cand.get("year") or "未知年份"
        site = cand.get("site") or "?"
        rating = cand.get("rating")
        ctype = "剧集" if cand.get("type") == "tv" else ""
        id_text = cand.get("imdb_id") or cand.get("douban_id") or ""
        rating_text = f"{rating}分" if rating is not None else ""
        print(f"  [{idx}] {title} ({year}) [{site}] {rating_text} {ctype} {id_text}".rstrip())


def _choose_candidate(candidates: list[dict], auto: bool) -> dict | None:
    """让用户选择版本，返回选中的原始数据；返回 None 表示跳过。

    唯一匹配时直接使用，不做确认；多个候选时才让用户选择。
    """
    if not candidates:
        return None

    if len(candidates) == 1:
        cand = candidates[0]
        print(f"\n唯一匹配：{cand.get('title')}（{cand.get('year') or '未知年份'}），直接使用。")
        return cand["raw"]

    _print_candidates(candidates)

    if auto:
        print(f"  -> 自动选择第 1 个：{candidates[0].get('title')}")
        return candidates[0]["raw"]

    while True:
        answer = input(
            "\n请输入要使用的版本序号（可多选如 1,3；回车默认第 1 个；s 跳过）："
        ).strip().lower()
        if answer in {"s", "skip"}:
            return None
        if not answer:
            return candidates[0]["raw"]

        first = answer.split(",")[0].strip()
        if first.isdigit() and 1 <= int(first) <= len(candidates):
            return candidates[int(first) - 1]["raw"]
        print("  输入无效，请重新输入。")



def _display_metadata(movie: MovieMetadata) -> None:
    print("\n识别结果：")
    print(f"  标题    : {movie.display_title}")
    if movie.original_title and movie.original_title != movie.display_title:
        print(f"  原名    : {movie.original_title}")
    print(f"  年份    : {movie.year or '未知'}")
    print(f"  类型    : {'剧集' if movie.media_type == 'tv' else '电影'}")
    if movie.runtime:
        print(f"  片长    : {movie.runtime} 分钟")
    if movie.directors:
        print(f"  导演    : {', '.join(p.name for p in movie.directors)}")
    if movie.genres:
        print(f"  分类    : {' / '.join(movie.genres)}")
    if movie.countries:
        print(f"  制片    : {' / '.join(movie.countries)}")
    if movie.douban_rating is not None:
        print(f"  豆瓣评分: {movie.douban_rating}（{movie.douban_votes or 0} 人评价）")
    if movie.imdb_rating is not None:
        print(f"  IMDb评分: {movie.imdb_rating}（{movie.imdb_votes or 0} 人评价）")
    if movie.plot:
        print(f"  简介    : {movie.plot[:80]}...")


def _search_and_select(
    query: str,
    client: DoubanInfoClient,
    *,
    auto: bool,
) -> tuple[MovieMetadata, dict] | None:
    """搜索并选择版本，返回 (解析结果, 原始数据)；失败或跳过返回 None。"""
    try:
        raw_candidates = client.search_candidates(query)
    except DoubanInfoError as exc:
        print(f"  [X] API 请求失败：{exc}")
        return None

    candidates = [
        summarize_candidate(c) for c in raw_candidates if isinstance(c, dict)
    ]

    if not candidates:
        print("  [X] 未找到匹配结果。")
        return None

    raw = _choose_candidate(candidates, auto=auto)
    if raw is None:
        print("  -> 已跳过。")
        return None

    try:
        movie = parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"  [X] 解析失败：{exc}")
        return None

    return movie, raw


def _export_movie(
    movie: MovieMetadata,
    raw: dict,
    output_dir: Path,
    client: DoubanInfoClient,
    *,
    write_nfo: bool,
    write_json: bool,
    download_poster: bool,
) -> bool:
    """把识别结果导出到指定目录。"""
    try:
        written = export(
            movie,
            output_dir,
            write_nfo=write_nfo,
            write_json=write_json,
            download_poster=download_poster,
            raw=raw,
            session=client.session,
        )
    except OSError as exc:
        print(f"  [X] 写入文件失败：{exc}")
        return False

    if written:
        print("  [OK] 已导出到：")
        for key, path in written.items():
            print(f"      {key:7s}: {path}")
    else:
        print("  [!] 未生成任何文件（请检查导出选项）。")
    return True


def process_item(
    item: MediaItem,
    client: DoubanInfoClient,
    *,
    auto: bool,
    write_nfo: bool,
    write_json: bool,
    download_poster: bool,
) -> bool:
    """处理单条待识别影片，成功导出返回 True。"""
    print("\n" + "=" * 64)
    print(f"待识别：{item.name}")
    print(f"  路径  ：{item.path}")
    print(f"  查询词：{item.query or '(空)'}")

    if not item.query:
        print("  [X] 无法从名称中解析出有效的查询关键字，已跳过。")
        return False

    result = _search_and_select(item.query, client, auto=auto)
    if result is None:
        return False

    movie, raw = result
    _display_metadata(movie)
    return _export_movie(
        movie,
        raw,
        item.output_dir,
        client,
        write_nfo=write_nfo,
        write_json=write_json,
        download_poster=download_poster,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="识别本地影片并从 DoubanInfo 导出元数据到原文件目录。",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="文件夹或视频文件路径，可多个；留空则进入交互式菜单。",
    )
    parser.add_argument(
        "--query",
        "-q",
        metavar="TEXT",
        help="自定义刮削的查询内容（片名/豆瓣编号/IMDb编号/链接）。",
    )
    parser.add_argument(
        "--out",
        "-o",
        metavar="DIR",
        help="自定义刮削的导出目标文件夹（配合 --query 使用）。",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="导入文件夹时只扫描顶层，不递归子目录。",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="自动选择最佳候选，不逐条确认。",
    )
    parser.add_argument("--no-nfo", action="store_true", help="不生成 movie.nfo。")
    parser.add_argument("--no-json", action="store_true", help="不生成 metadata.json。")
    parser.add_argument("--no-poster", action="store_true", help="不下载 poster.jpg。")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只识别并预览，不写入任何文件。",
    )
    return parser


def _prompt_paths() -> list[str] | None:
    """读取用户输入的路径。

    返回 ``None`` 表示用户选择返回主菜单，返回空列表表示直接回车跳过。
    """
    print("请导入文件/输入要识别的文件夹或文件路径（可直接把文件夹拖进来）。")
    print("多个路径用 ; 分隔，直接回车返回主菜单。")
    raw = input("路径：").strip().strip('"')
    if raw.lower() in {"b", "back", "q", "quit", "exit"}:
        return None
    if not raw:
        return []
    return [p.strip().strip('"') for p in raw.split(";") if p.strip()]


def _prompt_output_dir(default: Path | None = None) -> Path | None:
    """让用户输入导出目标文件夹；返回 ``None`` 表示取消。"""
    target: Path | None = None
    while True:
        print("\n请输入导出目标文件夹（不存在会自动创建）。")
        if default is not None:
            print(f"  直接回车使用默认：{default}")
        print("  输入 b 取消本次操作。")
        raw = input("目标文件夹：").strip().strip('"')

        if raw.lower() in {"b", "back", "q", "quit", "exit"}:
            return None
        if not raw:
            if default is not None:
                target = default
                break
            print("  未输入内容，请重新输入。")
            continue

        target = Path(raw)
        break

    if target is None:
        return None

    if target.exists() and not target.is_dir():
        print(f"  [X] 该路径已存在且不是文件夹：{target}")
        return None

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"  [X] 无法创建文件夹：{exc}")
        return None

    return target.resolve()


def custom_scrape(
    client: DoubanInfoClient,
    args: argparse.Namespace,
    *,
    query: str | None = None,
    output_dir: str | None = None,
) -> bool:
    """自定义刮削：手动输入查询内容并导出到指定文件夹。

    支持影片名称、豆瓣编号、IMDb 编号、豆瓣/IMDb 链接。
    返回 True 表示完成了一次导出。
    """
    print("\n" + "=" * 64)
    print("自定义刮削")
    print("=" * 64)

    if query is None:
        print("可输入以下任意一种查询内容：")
        print("  · 影片名称，如：看上去很美 或 看上去很美 2006")
        print("  · 豆瓣编号，如：1469441")
        print("  · IMDb 编号，如：tt0492473")
        print("  · 豆瓣链接，如：https://movie.douban.com/subject/1469441/")
        print("  · IMDb 链接，如：https://www.imdb.com/title/tt0492473/")
        print("  输入 b 返回主菜单。")
        query = input("\n请输入查询内容：").strip().strip('"')
        if not query:
            print("  未输入内容，已取消。")
            return False
        if query.lower() in {"b", "back", "q", "quit", "exit"}:
            return False
    else:
        print(f"查询内容：{query}")

    result = _search_and_select(query, client, auto=args.yes)
    if result is None:
        return False

    movie, raw = result
    _display_metadata(movie)

    # 目标目录：命令行已指定则直接用，否则交互询问。
    if output_dir is not None:
        target: Path | None = Path(output_dir).expanduser()
        if target.exists() and not target.is_dir():
            print(f"  [X] 该路径已存在且不是文件夹：{target}")
            return False
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"  [X] 无法创建文件夹：{exc}")
            return False
        target = target.resolve()
        print(f"\n导出目标文件夹：{target}")
    else:
        # 默认目标目录：以“片名 (年份)”命名，方便直接用于媒体库整理。
        default_dir = None
        if movie.display_title:
            year_text = f" ({movie.year})" if movie.year else ""
            default_dir = Path.cwd() / f"{movie.display_title}{year_text}"
        target = _prompt_output_dir(default_dir)

    if target is None:
        print("  -> 已取消导出。")
        return False

    if args.dry_run:
        print(f"  [预览] 未写入文件。目标目录：{target}")
        return True

    return _export_movie(
        movie,
        raw,
        target,
        client,
        write_nfo=not args.no_nfo,
        write_json=not args.no_json,
        download_poster=not args.no_poster,
    )


def _process_batch(
    inputs: list[str],
    client: DoubanInfoClient,
    args: argparse.Namespace,
) -> tuple[int, int]:
    """处理一批输入，返回 (成功数, 总数)。"""
    items = resolve_inputs(inputs, recursive=not args.no_recursive)
    if not items:
        print("未找到任何可识别的内容（请检查路径，或目录内是否包含视频文件）。")
        return 0, 0

    print(f"\n共找到 {len(items)} 个待识别条目。")

    success = 0
    for item in items:
        ok = process_item(
            item,
            client,
            auto=args.yes,
            write_nfo=not args.no_nfo and not args.dry_run,
            write_json=not args.no_json and not args.dry_run,
            download_poster=not args.no_poster and not args.dry_run,
        )
        success += 1 if ok else 0

    print("\n" + "=" * 64)
    print(f"本批处理完成：成功 {success} / 共 {len(items)}。")
    return success, len(items)


def _prompt_main_action() -> str:
    """主菜单：返回 ``scan`` / ``custom`` / ``quit``。"""
    print("\n请选择操作：")
    print("  [1] 导入文件/扫描本地文件夹（自动识别影片并导出到原目录）")
    print("  [2] 自定义刮削（手动输入片名/编号/链接 + 指定目标文件夹）")
    print("  [3] 退出程序")
    while True:
        answer = input("请选择 [1/2/3，回车默认 1，输入 q 退出]：").strip().lower()
        if answer in {"", "1", "s", "scan"}:
            return "scan"
        if answer in {"2", "c", "custom"}:
            return "custom"
        if answer in {"3", "q", "quit", "exit"}:
            return "quit"
        print("  输入无效，请输入 1、2 或 3。")


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    args = build_parser().parse_args(argv)

    if not DOUBANINFO_API_KEY:
        print("请先设置环境变量 DOUBANINFO_API_KEY")
        print("Windows PowerShell: $env:DOUBANINFO_API_KEY='你的API Key'")
        return 1

    client = DoubanInfoClient(api_key=DOUBANINFO_API_KEY)

    # 自定义刮削（命令行直接指定查询内容）。
    if args.query:
        custom_scrape(client, args, query=args.query, output_dir=args.out)
        return 0

    # 命令行直接传入路径时视为“单次批处理模式”，处理完不再询问。
    if args.paths:
        _process_batch(list(args.paths), client, args)
        return 0

    # 交互模式：主菜单循环，直到用户选择退出。
    print("=" * 64)
    print("电影元数据识别工具")
    print("=" * 64)

    while True:
        action = _prompt_main_action()

        if action == "quit":
            print("已退出，感谢使用。")
            return 0

        if action == "scan":
            inputs = _prompt_paths()
            if inputs is None:
                continue
            if not inputs:
                print("未提供任何路径。")
                continue
            _process_batch(inputs, client, args)
        else:  # custom
            custom_scrape(client, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n已中断，退出程序。")
        sys.exit(0)


