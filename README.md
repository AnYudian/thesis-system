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
│       ├── utils/        # 体积/时间格式化等展示工具
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

管理员在「学生与课题」里建档时，会同时用**学号作为用户名**开通学生账号，初始密码统一为 `123456`，创建成功后会弹窗显示一次。演示数据里的 24 名学生账号分别是 `20220001` ~ `20220024`，可以直接登录体验学生视角。

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
| GET | `/api/students` | ADMIN / TEACHER | 学生列表，支持分页、学号/姓名、环节、状态、导师筛选；教师只能看到自己名下 |
| POST | `/api/students` | ADMIN | 新建学生，可同时开通登录账号（用户名=学号，初始密码 123456） |
| GET | `/api/students/{id}` | 按角色 | 学生详情（含课题） |
| PATCH | `/api/students/{id}` | ADMIN | 修改学生信息、换导师、调整当前环节 |
| DELETE | `/api/students/{id}` | ADMIN | 删除学生及其登录账号 |
| GET | `/api/students/me` | STUDENT | 查看自己的档案；未建档时返回 `data: null` |
| PUT | `/api/students/{id}/topic` | ADMIN / 导师本人 | 新增或修改课题 |
| DELETE | `/api/students/{id}/topic` | ADMIN / 导师本人 | 清除课题 |
| GET | `/api/users/teachers` | ADMIN | 教师列表（指派导师用） |
| GET | `/api/materials` | 登录 | 材料列表；学生只看自己，教师只看名下，管理员看全部 |
| POST | `/api/materials` | STUDENT / ADMIN | multipart 上传，同一环节自动递增版本（管理员需带 `student_id`） |
| GET | `/api/materials/{id}/download` | 按角色 | 下载指定版本文件 |
| DELETE | `/api/materials/{id}` | 学生本人 / ADMIN | 删除某个版本 |

## 开发进度

- [x] **P1 登录与权限**：三角色账号、JWT、路由守卫、统一响应与全局异常
- [x] **概览看板**：管理员后台框架（侧栏 + 顶栏）、九节点流程分布、指标卡、最近登录
- [x] **P2 学生与课题建档**：学生档案 CRUD、学生账号开通、课题录入、教师「我的学生」、学生「我的档案」
- [x] **P3 材料中心**：学生按环节上传（自动版本号）、教师/管理员查看下载、九环节覆盖情况
- [ ] **P4 阶段审核**：教师放行 / 退回，流转日志
- [ ] **P5 统计报表**：导出与更多维度
- [ ] **P6 智能体接入**：`review_service` 接口位与建议展示

## 说明

- 数据库变更一律走 Alembic，不用 ORM 自动建表。
- 主题色与字体集中在 `frontend/src/styles/theme.css`，组件内只引用变量。
- 上传文件默认落在 `backend/data/uploads/<学生ID>/<环节>/`，目录名用随机 UUID，原始文件名只存数据库；`data/` 已被 git 忽略。
- `seed_demo` 生成的 24 名学生是**虚构演示数据**，用于看板预览，P2 之后应以管理员录入的真实名单为准。
