import os,sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1]/ ".env")
MODEL = os.getenv("MODEL")
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
MILVUS_URL = os.getenv("MILVUS_URL")
EMBED_MODEL = os.getenv("EMBED_MODEL")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL")



def assert_env():

    assert API_KEY,"缺少API_KEY"
    assert MILVUS_URL, "缺少MILVUS_URL"
    assert EMBED_MODEL, "缺少EMBED_MODEL"
    assert EMBED_BASE_URL, "缺少EMBED_BASE_URL"
    assert MODEL, "缺少 MODEL"
    assert BASE_URL, "缺少 BASE_URL"


if __name__ == '__main__':
    assert_env()
    print("配置就绪 ✅")