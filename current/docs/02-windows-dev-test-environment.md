# Windows 开发与测试环境搭建

## 1. 文档目的

本文说明如何在 Windows 上建立可重复的开发环境和独立测试环境。当前仓库尚未创建业务代码，因此命令中的模块名 `config`、依赖文件路径等是后续工程应遵守的约定。

## 2. 环境隔离原则

| 项目 | 开发环境 | 测试环境 |
|---|---|---|
| 代码目录 | `D:\DDMP` | `D:\DDMP-TEST\app` |
| Python 虚拟环境 | 仓库内 `.venv` | `D:\DDMP-TEST\venv` |
| 数据库 | `ddmp_dev` | `ddmp_test` |
| 数据库用户 | `ddmp_dev_user` | `ddmp_test_user` |
| 上传文件 | `D:\DDMP\.local\media` | `D:\DDMP-TEST\data\media` |
| DEBUG | `True` | `False` |
| 域名 | `localhost` | 独立测试域名 |
| 真实客户数据 | 禁止 | 原则上禁止，必要时脱敏 |

开发和测试环境不得使用正式数据库密码、正式 `SECRET_KEY` 或正式上传目录。

## 3. 推荐软件版本

| 软件 | 推荐版本 | 说明 |
|---|---|---|
| Windows | Windows 11 64 位 | 开发电脑 |
| PowerShell | Windows PowerShell 5.1 或 PowerShell 7 | 文档命令使用 PowerShell |
| Git | 当前稳定版 | 代码版本管理 |
| Python | 3.13.x 64 位 | 安装时勾选加入 PATH |
| Django | 5.2.x LTS | 由项目依赖文件锁定 |
| PostgreSQL | 17.x 64 位 | 开发与测试保持同一主版本 |
| 浏览器 | Edge/Chrome 当前稳定版 | 桌面调试 |
| 编辑器 | VS Code 或 PyCharm | 按开发人员习惯选择 |

不要使用 Beta、RC 或每日构建版本。Python 包版本由仓库依赖锁定文件控制，不在每台电脑上手工选择。

## 4. 开发环境搭建

### 4.0 自动配置用户环境变量

基础软件安装完成后，可在普通 PowerShell（不需要管理员权限）中执行项目脚本：

```powershell
Set-Location D:\DDMP
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-dev-env.ps1
```

脚本会把真实 Python、Python Scripts、Python Launcher 和 VS Code 放到当前用户 PATH 前部，并设置：

```text
DDMP_HOME=D:\DDMP
PYTHONUTF8=1
PIP_DISABLE_PIP_VERSION_CHECK=1
```

脚本不会全局设置 `PYTHONPATH`、`DJANGO_SETTINGS_MODULE`、`DATABASE_URL` 或任何密码。执行后关闭并重新打开 PowerShell、VS Code 和 Codex。

### 4.1 安装基础软件

按顺序安装：

1. Git for Windows。
2. Python 3.13 64 位，启用 `Add python.exe to PATH`。
3. PostgreSQL 17 64 位，可同时安装 pgAdmin。
4. VS Code/PyCharm。

安装后打开新的 PowerShell 窗口验证：

```powershell
git --version
py -3.13 --version
psql --version
```

如果 `psql` 无法识别，将 PostgreSQL 的 `bin` 目录加入系统 PATH，然后重新打开终端。

### 4.2 获取代码和创建虚拟环境

项目代码创建后，在 `D:\DDMP` 执行：

```powershell
Set-Location D:\DDMP
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements\dev.txt
```

如果系统禁止执行激活脚本，可仅对当前用户设置：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

也可以不激活虚拟环境，直接使用 `.\.venv\Scripts\python.exe` 和 `.\.venv\Scripts\pip.exe`。

### 4.3 创建开发数据库

先以 PostgreSQL 管理员身份进入 `psql`：

```powershell
psql -U postgres
```

执行以下 SQL，并将示例密码替换为本机专用强密码：

```sql
CREATE ROLE ddmp_dev_user LOGIN PASSWORD 'replace-with-local-password';
CREATE DATABASE ddmp_dev OWNER ddmp_dev_user ENCODING 'UTF8';
```

退出：

```sql
\q
```

验证连接：

```powershell
psql -h 127.0.0.1 -U ddmp_dev_user -d ddmp_dev
```

### 4.4 建立本地环境变量文件

后续项目应提供 `.env.example`，开发人员复制为 `.env`：

```powershell
Copy-Item .env.example .env
```

开发环境至少需要：

```dotenv
DJANGO_ENV=development
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=仅用于本机开发的随机长字符串
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
DJANGO_CSRF_TRUSTED_ORIGINS=http://192.168.1.100:8000
DATABASE_URL=postgresql://ddmp_dev_user:本机密码@127.0.0.1:5432/ddmp_dev
MEDIA_ROOT=D:/DDMP/.local/media
STATIC_ROOT=D:/DDMP/.local/static
```

`.env` 必须加入 `.gitignore`。仓库只能提交不含秘密值的 `.env.example`。

如果数据库密码含有 `@`、`:`、`/` 等字符，必须进行 URL 编码；也可以由项目采用分项数据库环境变量，避免连接串转义问题。

### 4.5 初始化并启动项目

项目代码具备后执行：

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py createsuperuser
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

开发服务器仅用于本机开发，不可用于测试环境或运行环境。

访问地址：

- 展示端：`http://127.0.0.1:8000/`
- 管理后台：`http://127.0.0.1:8000/admin/`
- 健康检查：`http://127.0.0.1:8000/health/`

需要同一 Wi-Fi 手机联调时，将示例中的 `192.168.1.100` 替换为开发机 WLAN IPv4 地址，并只向当前局域网开放 TCP 8000。手机使用 `http://开发机IP:8000/` 访问。IP 由 DHCP 变更后要同步更新 `.env` 和防火墙规则；开发服务不得直接暴露到互联网。

### 4.6 开发环境日常检查

```powershell
ruff check .
ruff format --check .
pytest
python manage.py check
python manage.py makemigrations --check --dry-run
```

提交代码前上述检查必须通过。数据库模型变更必须提交迁移文件。

## 5. 测试环境搭建

### 5.1 测试主机要求

- 建议使用独立 Windows 11 或 Windows Server 主机。
- 测试主机应尽量接近运行环境的软件版本。
- 微信和抖音内真实测试必须使用手机可访问的 HTTPS 域名。
- 若测试环境开放到互联网，必须限制后台访问、使用强密码并保持系统更新。

仅使用 `localhost` 或局域网 IP，无法完整验证微信分享域名、HTTPS、跨设备访问和抖音内置浏览器行为。

### 5.2 推荐目录

```text
D:\DDMP-TEST\
├─ app\              # 测试版本代码
├─ venv\             # Python 虚拟环境
├─ config\           # 不进入 Git 的环境配置
├─ data\media\       # 测试上传文件
├─ data\static\      # collectstatic 输出
├─ logs\              # 应用和代理日志
└─ backups\           # 测试备份
```

### 5.3 创建测试数据库

```sql
CREATE ROLE ddmp_test_user LOGIN PASSWORD 'replace-with-test-password';
CREATE DATABASE ddmp_test OWNER ddmp_test_user ENCODING 'UTF8';
```

数据库只监听本机或受控内网，不向公网开放 5432 端口。

### 5.4 安装测试版本

```powershell
py -3.13 -m venv D:\DDMP-TEST\venv
D:\DDMP-TEST\venv\Scripts\python.exe -m pip install --upgrade pip
D:\DDMP-TEST\venv\Scripts\pip.exe install -r D:\DDMP-TEST\app\requirements\prod.txt

Set-Location D:\DDMP-TEST\app
D:\DDMP-TEST\venv\Scripts\python.exe manage.py migrate
D:\DDMP-TEST\venv\Scripts\python.exe manage.py collectstatic --noinput
D:\DDMP-TEST\venv\Scripts\python.exe manage.py check --deploy
```

测试环境变量建议放在 `D:\DDMP-TEST\config\.env`，并通过启动脚本或 Windows 服务传入。测试环境必须设置：

```dotenv
DJANGO_ENV=test
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=测试环境独立随机密钥
DJANGO_ALLOWED_HOSTS=test.example.com
DATABASE_URL=postgresql://ddmp_test_user:测试密码@127.0.0.1:5432/ddmp_test
MEDIA_ROOT=D:/DDMP-TEST/data/media
STATIC_ROOT=D:/DDMP-TEST/data/static
```

### 5.5 使用 Waitress 启动测试服务

在项目根目录执行：

```powershell
Set-Location D:\DDMP-TEST\app
D:\DDMP-TEST\venv\Scripts\python.exe -m waitress `
  --listen=127.0.0.1:8100 `
  config.wsgi:application
```

测试环境不应直接暴露 8100 端口，应由 Caddy 代理 HTTPS 请求。测试环境的 Windows 服务配置可参照运行环境文档，只需替换目录、端口和域名。

### 5.6 测试数据管理

- 优先使用构造数据。
- 需要接近真实数据时，应删除或替换手机号、姓名和地址等隐私字段。
- 测试图片可使用经授权素材，不能从运行环境长期同步客户上传内容。
- 每次大版本验收前可重建测试数据库，确保迁移可从零执行。
- 测试环境产生的客户线索不得进入真实销售跟进流程。

## 6. 微信与抖音测试准备

测试环境至少准备：

1. 一个测试子域名，例如 `test.example.com`。
2. 公网 DNS 解析。
3. HTTPS 证书。
4. 防火墙开放 80/443，关闭公网 8000/8100/5432。
5. 微信和抖音内置浏览器实机。
6. 带不同 `source` 参数的测试链接和二维码。

建议验证以下链接：

```text
https://test.example.com/?source=wechat_moments
https://test.example.com/?source=wechat_channels
https://test.example.com/?source=douyin_video
https://test.example.com/?source=field_qrcode
```

检查项目：

- 页面加载速度和图片尺寸。
- 分享标题、描述和封面。
- 表单输入、隐私同意和提交结果。
- 返回、刷新、重复提交。
- 微信/抖音浏览器中的电话链接和视频播放。
- 后台能否正确识别来源参数。

## 7. 常见故障排查

### Python 命令找不到

优先使用 Python Launcher：

```powershell
py -0p
py -3.13 --version
```

### PowerShell 无法激活虚拟环境

使用虚拟环境内 Python 的完整路径，或为当前用户启用 `RemoteSigned`，不要修改整台服务器为不受限制策略。

### PostgreSQL 连接失败

依次检查：

1. PostgreSQL Windows 服务是否运行。
2. 端口是否为 5432。
3. 数据库、用户和密码是否对应当前环境。
4. `.env` 是否被正确加载。
5. 密码在连接字符串中是否需要 URL 编码。

### 静态文件在测试环境缺失

确认执行：

```powershell
python manage.py collectstatic --noinput
```

并检查 Caddy 指向的静态文件目录与 `STATIC_ROOT` 一致。

### 手机无法访问测试地址

检查公网 DNS、Windows 防火墙、云安全组、80/443 端口和证书。局域网地址不能代替正式的微信/抖音 HTTPS 测试。

开发机同一 Wi-Fi 联调还应检查：服务是否监听 `0.0.0.0:8000`、手机是否关闭了移动数据/VPN、路由器是否启用了 AP/客户端隔离，以及防火墙规则的远程网段是否仍与 WLAN 地址一致。

## 8. 环境验收清单

- [ ] Python、Git、PostgreSQL 版本正确。
- [ ] 虚拟环境位于规定目录。
- [ ] 开发和测试数据库完全分离。
- [ ] `.env` 未提交 Git。
- [ ] 数据库迁移可从零执行。
- [ ] 自动测试和 `manage.py check` 通过。
- [ ] 测试环境使用 `DEBUG=False`。
- [ ] Waitress 仅监听 `127.0.0.1`。
- [ ] 测试域名通过 HTTPS 访问。
- [ ] 微信和抖音内置浏览器完成实机验证。
- [ ] 测试环境日志、备份目录可写。
