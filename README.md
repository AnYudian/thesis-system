# 毕设论文审核系统

面向学院毕业设计（论文）**全过程**的进度跟踪与审阅系统。当前版本先完成「账号与权限 → 学生与课题建档 → 材料提交 → 阶段审核 → 统计看板」这条主干，智能体审阅能力后续按节点逐个接入。

> 智能体不参与流程决策：它只产出建议（分数、意见、问题清单），**是否放行进入下一阶段由教师本人决定**。

## 技术栈

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端 | Python 3.12 · FastAPI · SQLAlchemy 2.0（async）· Alembic · Pydantic v2 | 全 Python 栈，后续 LangChain / LangGraph 可直接同进程调用 |
| 数据库 | PostgreSQL 16 | 本机原生安装，开发期 `127.0.0.1:5432` |
| 认证 | JWT（python-jose）+ bcrypt（passlib） | 三角色：ADMIN / TEACHER / STUDENT |
| 前端 | Vue 3 · Vite · TypeScript · Element Plus · Pinia · Vue Router · Axios | 学术风视觉：深墨蓝 + 暖纸色 + 衬线标题 |

## 目录结构

```
thesis-system/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由层：只做参数校验与鉴权，业务写在 services
│   │   ├── core/         # 配置、安全、统一响应体、全局异常
│   │   ├── db/           # 会话、初始账号与演示数据脚本
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic 出入参
│   │   └── services/     # 业务逻辑（认证等，后续 review_service 也放这里）
│   ├── alembic/          # 数据库迁移（禁止 ORM 自动建表）
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/          # axios 封装与接口定义
│       ├── constants/    # 九节点等前后端共用口径
│       ├── layouts/      # 管理员后台框架（侧栏 + 顶栏）
│       ├── router/       # 路由与角色守卫
│       ├── stores/       # Pinia
│       ├── styles/       # 设计令牌（主题只改 theme.css）
│       └── views/        # 页面
└── start-dev.bat         # 一键启动：检查数据库服务 → 起前后端 → 开浏览器
```

## 快速开始

```bash
# 1. 数据库：确认本机 PostgreSQL 16 服务已启动（服务名 postgresql-x64-16）
#    首次需建业务账号与库：
#    CREATE ROLE thesis LOGIN PASSWORD 'thesis_dev_pwd';
#    CREATE DATABASE thesis OWNER thesis ENCODING 'UTF8';

# 2. 后端
cd backend
cp ../.env.example .env          # 填 JWT_SECRET
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed            # 内置账号
python -m app.db.seed_demo       # 可选：24 名演示学生，仅供看板预览
uvicorn app.main:app --port 8000 --reload

# 3. 前端
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Windows 上也可以直接双击 `start-dev.bat`：脚本会检查数据库服务与端口占用，分别起前后端窗口，8 秒后打开浏览器。

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：`GET /api/health`

## 演示账号

| 角色 | 用户名 | 密码 | 落地页 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `123456` | `/admin` 管理后台 |
| 教师 | `teacher` | `123456` | `/` 工作台 |
| 学生 | `student` | `123456` | `/` 工作台 |

不开放注册，账号由管理员创建；登录方式以后可能换成微信扫码，因此认证逻辑集中在 `services/auth_service.py`，换方式不影响其他模块。

## 业务流程（九节点）

```
选题/双向选择 → 任务书下达 → 开题报告/开题答辩 → 中期检查 → 查重检测
→ 论文定稿 → 评阅 → 答辩 → 归档/评优
```

其中 **选题 / 开题 / 中期 / 查重 / 定稿** 五个节点后期可能接入智能体审阅，界面上用金色圆点标注（`AI_STAGES`）；其余节点始终人工流转。

## 接口约定

- 统一响应体：`{ "code": 0, "message": "ok", "data": ... }`
- HTTP 状态码如实返回（401 未登录、403 越权、422 参数错误），前端据此分支
- 业务异常 / 参数校验异常 / 文件异常由全局处理器转成友好文案

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | 登录，返回 JWT |
| GET | `/api/auth/me` | 登录 | 当前用户 |
| GET | `/api/stats/overview` | ADMIN | 概览：学生/教师人数、九阶段分布、最近登录 |

## 开发进度

- [x] **P1 登录与权限**：三角色账号、JWT、路由守卫、统一响应与全局异常
- [x] **概览看板**：管理员后台框架（侧栏 + 顶栏）、九节点流程分布、指标卡、最近登录
- [ ] **P2 学生与课题建档**：学生档案 CRUD、学生账号发放、课题指派、教师名下学生
- [ ] **P3 材料中心**：分阶段材料上传与版本记录
- [ ] **P4 阶段审核**：教师放行 / 退回，流转日志
- [ ] **P5 统计报表**：导出与更多维度
- [ ] **P6 智能体接入**：`review_service` 接口位与建议展示

## 说明

- 数据库变更一律走 Alembic，不用 ORM 自动建表。
- 主题色与字体集中在 `frontend/src/styles/theme.css`，组件内只引用变量。
- `seed_demo` 生成的 24 名学生是**虚构演示数据**，用于看板预览，P2 之后应以管理员录入的真实名单为准。
