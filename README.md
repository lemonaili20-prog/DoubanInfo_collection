# Movie Scraper V2

一个用于整理本地电影文件、查询 DoubanInfo、生成标准化电影元数据的 Python 项目。

## 当前版本

- 使用 DoubanInfo JSON API，而不是直接抓取豆瓣网页
- API Key 使用 `X-API-KEY` 请求头
- JSON → `MovieMetadata` 标准数据模型（同时支持豆瓣 / IMDb 两种返回结构）
- 从 **文件名 / 文件夹名** 自动解析片名与年份（含分辨率、编码、字幕组等噪音过滤）
- 导入 **文件夹递归扫描** 视频文件，或直接传入单个文件
- **自定义刮削**：手动输入片名 / 豆瓣编号 / IMDb 编号 / 豆瓣链接 / IMDb 链接，
  再指定目标文件夹导出，适合单个影片的手动整理
- **多候选版本选择**：搜索到多个结果时列出版本列表由用户选择
- **识别结果导出到原文件所在目录**：`movie.nfo` + `metadata.json` + `poster.jpg`
- 交互式主菜单：可选择「扫描文件夹」或「自定义刮削」，处理完可选择继续或退出
- 保留 BBCode 解析器作为兼容备用
- 增加 API、解析器、扫描器、导出器的单元测试

## 目录

```text
movie_scraper/
├── main.py               # CLI 入口（主菜单 / 扫描 / 自定义刮削 / 导出）
├── config.py
├── requirements.txt
├── .env.example
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── models.py         # MovieMetadata / Person 数据模型
│   ├── doubaninfo.py     # DoubanInfo API 客户端
│   ├── douban_parser.py  # 豆瓣 / IMDb JSON → MovieMetadata
│   ├── filename_parser.py# 文件名 / 文件夹名解析
│   ├── scanner.py        # 目录递归扫描待识别条目
│   └── exporter.py       # NFO / JSON / 海报导出
│
└── tests/
    ├── test_candidates.py
    ├── test_douban_parser.py
    ├── test_doubaninfo.py
    ├── test_exporter.py
    ├── test_filename_parser.py
    └── test_scanner.py
```

## 安装

```bash
python -m venv .venv
```

Windows：

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

## 设置 API Key

PowerShell：

```powershell
$env:DOUBANINFO_API_KEY="你的API Key"
```

CMD：

```cmd
set DOUBANINFO_API_KEY=你的API Key
```

也可以参考 `.env.example`。

## 运行

交互模式（推荐）：启动后进入主菜单，输入 `q` 可随时退出。

```powershell
python main.py
```

主菜单：

```text
请选择操作：
  [1] 扫描本地文件夹（自动识别影片并导出到原目录）
  [2] 自定义刮削（手动输入片名/编号/链接 + 指定目标文件夹）
  [3] 退出程序
```

### 方式一：扫描本地文件夹

```powershell
# 递归扫描文件夹内所有视频文件
python main.py "D:\Movies"

# 一次传入多个路径
python main.py "D:\Movies\无间道" "D:\Movies\看上去很美.mkv"

# 自动选择最佳候选，不逐条确认（适合批量）
python main.py "D:\Movies" --yes

# 只识别预览，不写入任何文件
python main.py "D:\Movies" --dry-run
```

### 方式二：自定义刮削

适用于手动整理单个影片：自己提供准确的查询内容，并指定导出到哪个文件夹。

**交互式**：运行 `python main.py`，主菜单选 `2`，然后按提示输入：

```text
请输入查询内容：看上去很美 2006

请输入导出目标文件夹（不存在会自动创建）。
  直接回车使用默认：E:\python\movie_scraper\看上去很美 (2006)
目标文件夹：D:\Media\看上去很美 (2006)
```

**命令行直接指定**：

```powershell
# 按片名
python main.py --query "看上去很美 2006" --out "D:\Media\看上去很美 (2006)"

# 按豆瓣编号
python main.py --query 1469441 --out "D:\Media\看上去很美 (2006)"

# 按 IMDb 编号
python main.py --query tt0492473 --out "D:\Media\看上去很美 (2006)"

# 按豆瓣链接 / IMDb 链接
python main.py -q "https://movie.douban.com/subject/1307914/" -o "D:\Media\无间道 (2002)"
python main.py -q "https://www.imdb.com/title/tt0338564/" -o "D:\Media\无间道 (2002)"
```

支持的查询内容：

| 类型 | 示例 |
| --- | --- |
| 影片名称 | `看上去很美`、`看上去很美 2006` |
| 豆瓣编号 | `1469441` |
| IMDb 编号 | `tt0492473` |
| 豆瓣链接 | `https://movie.douban.com/subject/1469441/` |
| IMDb 链接 | `https://www.imdb.com/title/tt0492473/` |

目标文件夹若不存在会自动创建；直接回车则使用默认的「片名 (年份)」目录。

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--query` / `-q` | 自定义刮削的查询内容（片名/编号/链接） |
| `--out` / `-o` | 自定义刮削的导出目标文件夹 |
| `--no-recursive` | 导入文件夹时只扫描顶层，不递归子目录 |
| `--yes` / `-y` | 自动选择第 1 个候选，不逐条确认 |
| `--no-nfo` | 不生成 `movie.nfo` |
| `--no-json` | 不生成 `metadata.json` |
| `--no-poster` | 不下载 `poster.jpg` |
| `--dry-run` | 只识别预览，不写入文件 |

## 识别流程

```text
方式一：导入文件夹 / 文件路径
方式二：自定义输入片名 / 编号 / 链接 + 目标文件夹
      ↓
filename_parser 解析片名 + 年份（方式一）
      ↓
DoubanInfo API 搜索
      ↓
多个候选？ → 列出版本让用户选择（唯一匹配直接使用）
      ↓
MovieMetadata
      ↓
导出到原文件所在目录 / 用户指定的目标文件夹
    Movie Name (Year)/
    ├── Movie Name (Year).mkv   ← 原视频文件保持不变（方式一）
    ├── movie.nfo               ← Kodi/Emby/Jellyfin 元数据
    ├── metadata.json           ← 规范化 + 原始 API 数据
    └── poster.jpg              ← 海报
```


## 测试

```bash
pytest -q
```

