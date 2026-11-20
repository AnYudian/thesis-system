"""智能体的公共契约。

这一层刻意保持很薄：只定义"输入是什么、输出必须长什么样、失败怎么表达"。
换模型（DeepSeek / 通义 / 学校内网模型）时只换 provider，不改业务代码；
以后需要多步编排（抽取 → 自检 → 评分 → 复核）时再引入 LangGraph，
把 provider 当成图里的一个节点即可，不用推倒重来。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ReviewRequest:
    """一次预审要用的全部输入。只带正文，不带学生姓名/学号。"""

    text: str
    stage: str
    title: str
    material_version: int
    truncated: bool = False


@dataclass(frozen=True)
class ProviderReply:
    """模型的原始回复 + 用量，原始文本一律落库，方便回溯。"""

    payload: dict
    raw: str
    tokens_input: int | None = None
    tokens_output: int | None = None


class AiError(RuntimeError):
    """预审失败。message 会写进 ai_runs.error，前端直接展示给老师看。

    retryable 区分"再试一次可能就好了"（超时、限流、输出被截断）
    和"重试也没用"（key 无效、余额不足、材料格式不支持）：
    前者由 ai_service 自动重试，后者直接落失败，省一次请求也省一次等待。
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class AiSkipped(RuntimeError):
    """不构成失败、但没必要/不能审的情况（扫描件没文字、格式不支持、额度用完）。"""


class ReviewProvider(Protocol):
    name: str
    model: str

    async def review(self, request: ReviewRequest) -> ProviderReply:
        ...
