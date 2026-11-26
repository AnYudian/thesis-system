"""全局配置。

约定：所有可变配置只从这里读，业务代码不直接碰 os.environ。
这样将来换部署环境（本机 → 服务器 / 容器）只改 .env，不动代码。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py 位于 backend/app/core/ 下，上溯三级即 backend 目录，
# 用来定位 data/ 上传目录，避免依赖当前工作目录。
BASE_DIR = Path(__file__).resolve().parents[2]
# 仓库根目录：.env 约定放在这里（README 和 .env.example 都按这个位置写），
# backend/.env 作为本机覆盖，后者优先。两个位置都读，避免"照文档放了却没生效"。
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BASE_DIR / ".env"),
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

    # ---- 智能体（AI 预审）----
    # 总开关：关掉后上传/审核等主流程完全不受影响，界面上也不出现 AI 相关内容。
    ai_enabled: bool = False
    # mock = 不调真实模型（离线可演示）；deepseek = 调用 OpenAI 兼容接口
    ai_provider: str = "mock"
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-flash"
    ai_api_key: str = ""
    ai_timeout_seconds: int = 90
    # 失败自动重试次数：只对"可能自己好"的错误重试（超时 / 限流 / 输出截断）
    ai_retry_times: int = 1
    # 单次输出上限。开题报告 7 个维度 + 问题清单约 2500-3000 tokens，
    # 留在 4000 是为了不被截断；真被截断会判定为可重试错误
    ai_max_tokens: int = 6000
    # 每天最多自动跑多少次，防止误点或反复重跑烧 key；0 表示不限制
    ai_daily_limit: int = 30
    # 送入模型的正文字数上限：开题报告一般不够这个数，超出只截断并提示
    ai_max_chars: int = 24000

    # ---- 智能审阅服务（外部 HTTP 接口，按「学生+环节」打包送审）----
    # 地址与令牌只放配置，不写进代码：迁移到公司服务器时只改环境变量
    agent_enabled: bool = False
    agent_base_url: str = "https://10.96.20.67:9443/api/v1"
    agent_token: str = ""
    # 对方用的是 Caddy 自签证书且 12 小时一换，只能跳过校验；
    # 正式环境应换成可信证书后把这个开关关掉
    agent_verify_tls: bool = False
    agent_timeout_seconds: int = 60
    # 对方串行处理，实测单份约 3 分 45 秒；轮询间隔和最长等待都按这个量级设
    agent_poll_interval: int = 10
    agent_max_wait_minutes: int = 60
    # 对方当前只收这些格式；PDF 待其修复后再加进来
    agent_supported_ext: str = "docx,png,jpg,jpeg,zip"
    agent_max_files: int = 10
    agent_max_file_mb: int = 2

    @property
    def agent_supported_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.agent_supported_ext.split(",") if e.strip()}

    @property
    def upload_path(self) -> Path:
        """上传目录的绝对路径。相对路径一律相对于项目根目录，而不是启动目录。"""
        return self.upload_dir if self.upload_dir.is_absolute() else (BASE_DIR / self.upload_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    """缓存单例，避免每次请求都重新读 .env。"""
    return Settings()
