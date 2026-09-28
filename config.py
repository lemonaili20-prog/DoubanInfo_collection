import os

DOUBANINFO_API_BASE_URL = "https://doubaninfo.com/api/v1_douban.php"
DOUBANINFO_API_KEY = os.getenv("DOUBANINFO_API_KEY", "你的API")

REQUEST_TIMEOUT = 20
MAX_RETRIES = 2
