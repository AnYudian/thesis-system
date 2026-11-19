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
| POST | `/api/auth/change-password` | 登录 | 本人改密（需原密码，6-72 位） |
| GET | `/api/stats/overview` | ADMIN | 概览：学生/教师人数、九阶段分布、最近登录 |
| GET | `/api/stats/report` | ADMIN | 统计报表：指标、九环节明细、指导教师工作量、近 14 天动态（`days=7..90`） |
| GET | `/api/students` | ADMIN / TEACHER | 学生列表，支持分页、学号/姓名、环节、状态、导师筛选；教师只能看到自己名下 |
| POST | `/api/students` | ADMIN | 新建学生，可同时开通登录账号（用户名=学号，初始密码 123456） |
| GET | `/api/students/{id}` | 按角色 | 学生详情（含课题） |
| PATCH | `/api/students/{id}` | ADMIN | 修改学生信息、换导师、调整当前环节 |
| DELETE | `/api/students/{id}` | ADMIN | 删除学生及其登录账号 |
| GET | `/api/students/me` | STUDENT | 查看自己的档案；未建档时返回 `data: null` |
| PUT | `/api/students/{id}/topic` | ADMIN / 导师本人 | 新增或修改课题 |
| DELETE | `/api/students/{id}/topic` | ADMIN / 导师本人 | 清除课题 |
| GET | `/api/users` | ADMIN | 账号列表，支持分页、角色、启停状态、账号/姓名筛选，含最近登录时间 |
| POST | `/api/users` | ADMIN | 新建教师 / 管理员账号（学生账号随建档开通，不在此创建）；**教师必须填写学院、专业、手机号、QQ** |
| PATCH | `/api/users/{id}` | ADMIN | 修改姓名与教师档案四项、停用 / 启用；不能停用自己，也不能停用最后一个管理员 |
| POST | `/api/users/{id}/reset-password` | ADMIN | 重置为统一初始密码 123456 |
| POST | `/api/users/{id}/set-password` | ADMIN | 给指定账号设置新密码（教师忘了密码时用，不需要原密码） |
| GET | `/api/users/teachers` | ADMIN | 教师列表（指派导师用） |
| POST | `/api/students/import` | ADMIN | 批量导入学生：CSV 或 Excel 复制文本（制表符），6 列且指导教师必填，逐行校验并返回错误行 |
| POST | `/api/students/import/file` | ADMIN | 上传 `.xlsx` 导入（≤5MB），列要求同上，Excel 里存成数字的学号也能识别 |
| POST | `/api/students/assign-teacher` | ADMIN | 批量改派导师：`{student_ids, teacher_id}`，只改归属，不动材料与审核记录 |
| GET | `/api/logs` | ADMIN | 操作日志：登录、账号、建档、课题、材料、审核，支持动作 / 关键词筛选 |
| GET | `/api/materials` | 登录 | 材料列表；学生只看自己，教师只看名下，管理员看全部 |
| POST | `/api/materials` | STUDENT / ADMIN | multipart 上传，同一环节自动递增版本（管理员需带 `student_id`） |
| GET | `/api/materials/{id}/download` | 按角色 | 下载指定版本文件 |
| DELETE | `/api/materials/{id}` | 学生本人 / ADMIN | 删除某个版本 |
| GET | `/api/reviews/pending` | TEACHER（本人名下）/ ADMIN（全校，只读） | 在途学生进度：当前环节、材料份数、指导次数、上次流转；支持 `keyword` / `stage` / `teacher_id` 筛选 |
| GET | `/api/reviews` | 登录 | 审核流转记录，支持学生姓名/学号、环节、动作（通过/退回）、导师筛选与分页；学生只看自己，教师只看名下，管理员看全部 |
| POST | `/api/reviews/{student_id}` | TEACHER（仅指导教师本人） | 通过 / 退回；通过进入下一环节，最后一环通过即归档；退回必须写原因；**中期检查通过前要求指导记录满 10 次** |
| GET | `/api/guidance` | 登录 | 指导记录列表，支持学生、环节筛选；学生只看自己，教师只看名下，管理员看全部 |
| GET | `/api/guidance/summary` | 登录 | 中期检查指导进度（已登记次数 / 要求次数），登录页顶部进度卡用 |
| POST | `/api/guidance` | TEACHER（仅该生导师） | 登记一次指导（multipart）：环节、方式（面谈 / 线上）、时间、内容、证据截图可选 |
| GET | `/api/guidance/{id}/evidence` | 按角色 | 下载该条记录的证据截图 |
| DELETE | `/api/guidance/{id}` | 登记人本人 | 删除自己登记的记录（中期次数同步减少） |

## 开发进度

- [x] **P1 登录与权限**：三角色账号、JWT、路由守卫、统一响应与全局异常
- [x] **概览看板**：管理员后台框架（侧栏 + 顶栏）、九节点流程分布、指标卡、最近登录
- [x] **P2 学生与课题建档**：学生档案 CRUD、学生账号开通、课题录入、教师「我的学生」、学生「我的档案」
- [x] **P3 材料中心**：学生按环节上传（自动版本号）、教师/管理员查看下载、九环节覆盖情况
- [x] **P4 阶段审核**：教师按学生当前环节「通过 / 退回」，通过推进到下一环节（末环自动归档），退回必须写原因并留在原环节；`stage_reviews` 留痕（含材料版本），学生「我的档案」看到退回提示与最近记录，管理员「阶段流转」只读查看全校进度
- [x] **P5 统计报表**：管理员「统计报表」——五项指标、九环节明细、指导教师工作量（通过率 / 最近审核）、近 14 天提交与审核动态、一键导出 CSV
- [x] **P6 系统完善**：账号管理（教师 / 管理员账号创建、启停、重置密码，含自我保护规则）、操作日志查询（9 类业务动作全量留痕）、批量导入学生（逐行校验 + 错误行定位）、列表空状态统一
- [x] **P6.5 管理员端优化**：三种角色均可自助改密（顶栏「修改密码」，需原密码），管理员可给任意账号直接设密；批量导入支持上传 `.xlsx`，**指导教师改为必填**；学生列表支持多选批量指派导师；「阶段流转」新增「流转记录」Tab，可按关键词、环节、动作、指导教师筛选并分页
- [x] **P6.6 教师档案与指导记录**：教师账号新增学院 / 专业 / 手机号 / QQ（新建与编辑时必填，手机与 QQ 做格式校验）；教师「指导记录」按学生登记每一次沟通（环节、方式、时间、内容、证据截图）；**中期检查通过前必须满 10 次**，不足时后端直接拦下、前端禁用「通过」；管理员「学生详情」可追溯导师档案、九环节进度、指导明细与证据、阶段材料、审核历史
- [x] **P6.7 阶段流转合并**：去掉「待处理 / 流转记录」两个 Tab，合成一张在途学生表——顶部按姓名学号、环节、指导教师筛选，行内直接看九环节进度条、材料、指导次数与上次流转；管理员点姓名或「详情」进学生详情页追溯完整审核历史与逐次沟通明细（时间、方式、内容、证据）
- [x] **P6.8 管理员端收尾**：数据概览「最近登录」按角色配色（管理员深蓝 / 教师金 / 学生绿），扫一眼头像即可区分；学生详情里的图片证据改为 46px 缩略图，点击原地放大、关闭即回，不再跳新窗口；PDF 证据仍新窗口打开
- [ ] **P7 智能体接入（暂缓）**：`review_service` 接口位与建议展示（选题 / 开题 / 中期 / 查重 / 定稿）

## 说明

- 阶段审核只能由**该学生的指导教师本人**执行：智能体只出建议，放行权在人；管理员只读，便于监督与统计。
- 中期检查是**唯一有硬门槛**的环节：通过前该生必须有 ≥10 条 `MIDTERM` 指导记录（`guidance_service.MIDTERM_REQUIRED`），不足时返回 422 并提示还差几次；证据截图非必填，但建议留痕。
- 教师档案四项在 `account_service._ensure_teacher_profile` 里统一校验，手机 `1[3-9]\d{9}`、QQ `5-12` 位数字；历史教师由迁移按「计算机学院 / 软件工程」回填，首次编辑时需按实际补全。
- 账号停用只禁止登录，不删除：历史材料、审核记录、日志都要能追溯到人；管理员账号不能停用自己，也不能停到只剩零个启用管理员。
- 审计日志的动作名存英文常量（`LOGIN` / `STAGE_APPROVE`…），中文文案在前端 `constants/actions.ts` 翻译，改文案不影响历史记录。
- 批量导入每行固定 6 列：`学号,姓名,专业,班级,年级,指导教师账号`，**指导教师必填**（教师账号不存在或已停用会整行跳过），表头可留可删；一个学号填错不会拖垮整张名单，错误行会带行号和原因返回。
- 改密后已签发的 JWT 仍然有效（无状态令牌不查库），改密只影响下次登录；如需立即踢下线，后续可加 `token_version` 字段在依赖里比对。
- 统计报表的口径写在 `backend/app/services/report_service.py` 顶部：材料数含历次版本、通过率 = 通过 / 审核总数（无记录显示 —）、平均审核时长按“该环节最新材料提交 → 教师处理”计算，没交材料直接放行的不计入。
- 审核记录只增不改，`material_version` 记录审核当时该环节的版本号，材料后续替换也能回溯“当时看的是哪一版”。

- 数据库变更一律走 Alembic，不用 ORM 自动建表。
- 主题色与字体集中在 `frontend/src/styles/theme.css`，组件内只引用变量。
- 上传文件默认落在 `backend/data/uploads/<学生ID>/<环节>/`，目录名用随机 UUID，原始文件名只存数据库；`data/` 已被 git 忽略。
- `seed_demo` 生成的 24 名学生是**虚构演示数据**，用于看板预览，P2 之后应以管理员录入的真实名单为准。
