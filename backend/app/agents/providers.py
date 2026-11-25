"""模型提供方。

provider 只关心"给一段文字，拿回一个 JSON"，不碰数据库、不碰权限。
换模型就是新增一个类 + 改一行配置，业务代码不用动。
"""

import asyncio
import hashlib
import json

import httpx

from app.agents.base import AiError, ProviderReply, ReviewRequest
from app.agents.proposal import parse_json, system_prompt, user_message
from app.core.config import Settings


class MockProvider:
    """离线演示用：不联网、不花钱，结果由正文哈希决定（同一份报告分数稳定）。

    存在的意义：没有 key 也能把"上传 → 排队 → 结果 → 三个角色看到"这条链路跑通，
    验收环境和老师演示环境都不依赖外网。
    """

    name = "mock"
    model = "mock-reviewer-v1"

    async def review(self, request: ReviewRequest) -> ProviderReply:
        await asyncio.sleep(1.2)  # 留一点"在审"的时间，前端轮询状态才看得出变化
        digest = hashlib.sha256(request.text.encode("utf-8")).digest()
        base = 68 + digest[0] % 20  # 68-87 分，看起来像正常评分
        # 分数与评语要一致：演示时若出现"4.5 分 + 文献偏少"，老师一眼就看出是假的
        dimensions = [
            ("background", "选题背景与意义", "背景与意义写得清楚，能再具体到行业痛点会更好。", "选题背景偏笼统，缺少要解决的具体问题。"),
            ("literature", "国内外研究现状", "文献综述有归纳也有对比，建议再补两篇近三年文献。", "文献偏少且只做罗列，缺少观点对比与归纳。"),
            ("content", "研究内容与目标", "研究内容边界清楚，目标可以再量化一层。", "研究内容偏宽泛，目标缺少可验收的指标。"),
            ("method", "研究方法与技术路线", "技术路线可行，建议补一张流程图说明步骤衔接。", "方法与问题匹配度不足，缺少技术难点与对策。"),
            ("schedule", "进度安排", "进度安排合理，建议留出联调与写作缓冲。", "进度安排偏紧，没有给测试与论文写作留时间。"),
            ("reference", "参考文献", "参考文献数量与格式基本达标，可再补外文文献。", "参考文献数量不足，格式也不统一，需按 GB/T 7714 整理。"),
            ("feasibility", "可行性与工作量", "工作量与本科毕设匹配，按期完成问题不大。", "工作量偏大，按当前进度存在做不完的风险。"),
        ]
        payload = {
            "score": base,
            "completion": min(100, base + 3),
            "summary": "整体结构完整，可以进入下一阶段；主要短板是文献综述深度与目标量化。（演示模式，非真实模型输出）",
            "dimensions": [
                {
                    "key": key,
                    "label": label,
                    "score": (score := round(3 + (digest[index] % 5) / 2, 1)),
                    "max_score": 5,
                    "comment": positive if score >= 4 else negative,
                }
                for index, (key, label, positive, negative) in enumerate(dimensions)
            ],
            "issues": [
                {
                    "level": "MAJOR",
                    "title": "研究现状缺少对比归纳",
                    "quote": request.text[:60],
                    "suggestion": "按「方法—结论—不足」三段式重写综述，至少补 5 篇近三年文献。",
                },
                {
                    "level": "MINOR",
                    "title": "研究目标不够量化",
                    "quote": "",
                    "suggestion": "把「提升效率」改成可验证的指标，例如准确率达到多少、响应时间降到多少。",
                },
            ],
            "suggestions": [
                "补充近三年文献并做对比表",
                "把研究目标改写成可验收的指标",
                "技术路线补一张流程图",
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False)
        return ProviderReply(payload=payload, raw=raw, tokens_input=len(request.text) // 2, tokens_output=600)


class DeepSeekProvider:
    """OpenAI 兼容接口。base_url / model / key 全部来自配置，方便换供应商。

    这一层的职责只有两个：把请求发出去、把"哪些错误值得再试一次"标出来。
    重试循环放在 ai_service，因为那里还要落库（记录本次是第几次尝试）。
    """

    name = "deepseek"

    def __init__(self, settings: Settings) -> None:
        if not settings.ai_api_key:
            raise AiError("未配置 AI_API_KEY，无法调用真实模型（可在 .env 里填写或改用 AI_PROVIDER=mock）")
        self._settings = settings
        self.model = settings.ai_model

    async def review(self, request: ReviewRequest) -> ProviderReply:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_message(request)},
            ],
            # 评分要稳定，不要发挥：温度调到接近 0
            "temperature": 0.2,
            "max_tokens": self._settings.ai_max_tokens,
            "response_format": {"type": "json_object"},
        }
        data = await self._post(payload)

        choices = data.get("choices") or []
        if not choices:
            raise AiError("模型返回结构异常，缺少 choices", retryable=True)
        choice = choices[0]
        content = (choice.get("message") or {}).get("content") or ""

        # 达到输出上限时 JSON 一定是半截的，直接判"可重试"，
        # 让 ai_service 再要一次，而不是把 500 字半截 JSON 当结果存下来
        if choice.get("finish_reason") == "length":
            raise AiError("模型输出被截断（达到单次输出上限），请重试", retryable=True)
        if not content.strip():
            raise AiError("模型返回了空内容，请重试", retryable=True)

        try:
            parsed = parse_json(content)
        except AiError as exc:
            raise AiError(exc.message, retryable=True) from None

        usage = data.get("usage") or {}
        return ProviderReply(
            payload=parsed,
            raw=content,
            tokens_input=usage.get("prompt_tokens"),
            tokens_output=usage.get("completion_tokens"),
        )

    async def _post(self, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._settings.ai_api_key}"}
        url = f"{self._settings.ai_base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(self._settings.ai_timeout_seconds, connect=10)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                # 个别兼容实现不认 response_format，降级重试一次，别让整次预审白跑
                if response.status_code == 400 and "response_format" in response.text:
                    payload = {k: v for k, v in payload.items() if k != "response_format"}
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise AiError(
                f"模型接口超过 {self._settings.ai_timeout_seconds} 秒没有返回，稍后自动重试",
                retryable=True,
            ) from None
        except httpx.HTTPError as exc:
            # 断网 / DNS / TLS 这类问题重试一次通常能过，不值得直接判失败
            raise AiError(f"连不上模型接口（{exc.__class__.__name__}），稍后自动重试", retryable=True) from None

        if response.status_code != 200:
            raise AiError(
                self._explain(response),
                retryable=response.status_code == 429 or response.status_code >= 500,
            )

        try:
            return response.json()
        except ValueError:
            raise AiError("模型接口返回的不是 JSON，稍后自动重试", retryable=True) from None

    @staticmethod
    def _explain(response: httpx.Response) -> str:
        status = response.status_code
        detail = response.text[:200].replace("\n", " ")
        if status == 401:
            return "API Key 无效或已过期，请检查 AI_API_KEY"
        if status == 402:
            return "模型账户余额不足，请充值后再试"
        if status == 429:
            return "模型接口限流，稍后自动重试"
        if status >= 500:
            return f"模型服务暂时不可用（{status}），稍后自动重试"
        return f"模型接口返回 {status}：{detail}"


def get_provider(settings: Settings):
    provider = (settings.ai_provider or "mock").lower()
    if provider == "mock":
        return MockProvider()
    if provider == "deepseek":
        return DeepSeekProvider(settings)
    raise AiError(f"未知的 AI_PROVIDER：{settings.ai_provider}")
