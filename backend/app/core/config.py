"""全局配置。

约定：所有可变配置只从这里读，业务代码不直接碰 os.environ。
这样将来换部署环境（本机 → 服务器 / 容器）只改 .env，不动代码。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py 位于 backend/app/core/ 下，上溯三级即项目根目录，
# 用来定位根目录的 .env 和 data/ 目录，避免依赖当前工作目录。
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多出的键不报错，方便团队各自加临时变量
    )

    app_name: str = "毕设论文审核系统"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://thesis:thesis_dev_pwd@127.0.0.1:5432/thesis"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    upload_dir: Path = Path("data/uploads")
    max_upload_mb: int = 20

    @property
    def upload_path(self) -> Path:
        """上传目录的绝对路径。相对路径一律相对于项目根目录，而不是启动目录。"""
        return self.upload_dir if self.upload_dir.is_absolute() else (BASE_DIR / self.upload_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    """缓存单例，避免每次请求都重新读 .env。"""
    return Settings()
