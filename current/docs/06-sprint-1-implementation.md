# Sprint 1 实施记录：首页可访问

## 1. 实施结果

Sprint 1 已完成第一个可运行增量：

- Django 5.2 LTS 单体工程骨架。
- 响应式公开首页。
- Django 管理后台登录入口。
- 可后台维护的单例站点配置。
- 应用及数据库健康检查。
- 开发、测试和生产配置隔离基础。
- 控制台与滚动文件日志。
- pytest、pytest-django 和 Ruff 检查链。
- Windows 一键启动和全量检查脚本。
- Git 仓库初始化。

## 2. 对应功能编号

| 功能编号 | 状态 | 说明 |
|---|---|---|
| `FE-GLOBAL-001` | 已完成基础版 | 响应式框架、移动端断点、统一视觉样式 |
| `FE-GLOBAL-002` | 已完成基础版 | 首页、平台介绍、示范点占位和联系入口 |
| `FE-GLOBAL-003` | 已完成基础版 | 页脚、公司名称和联系电话配置 |
| `FE-HOME-001` | 已完成基础版 | 主视觉、主副标题和行动按钮 |
| `ADM-AUTH-001` | 已完成 | 使用 Django 后台安全登录 |
| `ADM-CONFIG-001` | 部分完成 | 站点、公司、Logo、首屏、电话和页脚；分享图等后续补充 |
| `SYS-HEALTH-001` | 已完成 | 检查应用和数据库，失败时不暴露详情 |
| `SYS-CONFIG-001` | 已完成基础版 | `.env`、开发兜底和生产强制配置 |
| `SYS-LOG-001` | 已完成基础版 | 控制台和滚动文件日志 |

## 3. 页面与地址

本地启动后：

- 首页：`http://127.0.0.1:8000/`
- 后台：`http://127.0.0.1:8000/admin/`
- 健康检查：`http://127.0.0.1:8000/health/`

## 4. 启动方式

首次安装：

```powershell
Set-Location D:\DDMP
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

日常启动：

```powershell
.\scripts\run-dev.ps1
```

如果 PowerShell 阻止脚本，可仅对当前窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 5. 验证方式

```powershell
.\scripts\check.ps1
```

该脚本依次运行 Ruff、pytest、Django 系统检查和迁移一致性检查。

本次完成时的自动验证结果：

- 5 项 pytest 测试通过。
- Ruff lint 通过。
- Ruff format 检查通过。
- Django system check 通过。
- 数据库迁移一致性检查通过。
- 真实 HTTP 首页、后台登录、CSS 和健康检查均返回 200。

## 6. 数据库说明

为使 Sprint 1 在没有数据库密码的情况下立即运行，开发环境未配置 `DATABASE_URL` 时使用 `.local/db.sqlite3`。以下环境仍强制 PostgreSQL：

- 正式运行环境必须提供 `DATABASE_URL`。
- 测试共享环境按环境文档使用 PostgreSQL。
- Sprint 2 开始业务数据模型前，应建立 `ddmp_dev` 和开发账号并切换到 PostgreSQL。

SQLite 仅是本机第一迭代兜底，不改变正式技术路线。

## 7. 暂未完成

- 未创建后台超级管理员；需要由项目负责人执行 `createsuperuser` 并设置个人密码。
- 品种、卖点和示范点业务模型属于 Sprint 2。
- 当前首页中的示范点和咨询按钮为后续功能入口。
- 微信分享配置、二维码、线索表单属于 Sprint 4—5。
- 运行环境 Caddy/Waitress 服务尚未正式部署。

## 8. 下一迭代建议

Sprint 2 按以下顺序开发：

1. `ADM-VAR-001` 至 `ADM-VAR-003`：品种管理。
2. `ADM-SP-001`：核心卖点管理。
3. `ADM-SITE-001`、`ADM-SITE-002`：示范点管理。
4. `FE-VAR-001`、`FE-VAR-002`：品种详情。
5. `FE-SITE-001`、`FE-SITE-002`：示范点列表和详情。
6. `FE-HOME-002`、`FE-HOME-003`：首页接入真实内容。

