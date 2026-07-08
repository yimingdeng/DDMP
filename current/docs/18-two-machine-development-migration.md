# DDMP 迁移到第二台开发机与双机开发

相关范围：`SYS-CONFIG-001`、`SYS-BACKUP-001`。

## 推荐方案

代码和 Django migration 文件通过 Git 同步；每台电脑分别维护 `.env`、`.venv`、开发数据库和 `.local\media`。不要通过网盘自动同步整个仓库目录，也不要让两台电脑同时打开同一个 SQLite 文件。

这样可以保证代码历史可追踪，同时避免本机密钥、客户信息、日志和上传文件进入 Git。

## 当前机器的迁移前状态

截至 2026-07-07：

- `main` 已建立基线提交并配置 `origin`；本轮迁移准备修改提交、推送后即可供新机克隆。
- 当前开发环境使用 `.local\db.sqlite3`，不是 PostgreSQL。
- `.env`、`.venv` 和 `.local` 已被 Git 忽略。
- 当前 SQLite 文件约 568 KiB；媒体目录有 12 个文件，均属于本机数据，不通过 Git 同步。
- Django system check 和 migration drift check 已通过。

迁移前仍需由仓库所有者确认远程仓库的可见性和第二台机器的访问权限。仓库应保持私有；如果远程仓库不是私有仓库，应先处理可见性，再继续迁移。

## 一、当前机器：迁移前确认并推送

先确认忽略规则正常，并检查将要提交的文件：

```powershell
Set-Location D:\DDMP
git status --short
git check-ignore .env .venv .local test.sqlite3 test.zip
git remote -v
```

运行完整验证：

```powershell
.\scripts\check.ps1
```

如果有待迁移的代码修改，提交并推送：

```powershell
git add <本次修改文件>
git status --short
git commit -m "<清晰的变更说明>"
git push
```

提交前必须确认列表中没有 `.env`、`.local`、数据库文件、媒体文件、日志、RAR/ZIP/7Z 或真实客户数据。

## 二、第二台机器：安装和初始化

安装 Git for Windows 和 Python 3.13。项目当前可先使用 SQLite；需要与共享环境保持一致时，再安装 PostgreSQL 17 并为该电脑创建独立开发库。

```powershell
git clone <私有远程仓库地址> <本机目标目录>
Set-Location <本机目标目录>
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap-dev-machine.ps1
.\scripts\check.ps1
```

初始化脚本会：

1. 创建仓库内的 `.venv`。
2. 安装 `requirements\dev.txt`。
3. 在缺少 `.env` 时从示例创建，并生成本机开发密钥。
4. 执行已提交的 Django 迁移和 `manage.py check`。

它不会复制或覆盖已有 `.env`，也不会从其他机器带入数据库或媒体。

编辑第二台机器的 `.env`：

- 将 `DJANGO_ALLOWED_HOSTS` 和 `DJANGO_CSRF_TRUSTED_ORIGINS` 改为第二台机器的局域网 IP。
- SQLite 开发可保持 `DATABASE_URL=`。
- PostgreSQL 开发应使用第二台机器专属用户、密码和数据库。
- 默认的媒体、静态收集和日志目录均位于仓库的 `.local` 下，无需填写绝对路径；确有需要时再在 `.env` 中为该机器单独设置绝对路径。

如果新机的 Python 启动命令不是 `py`，可显式指定，例如：

```powershell
.\scripts\bootstrap-dev-machine.ps1 -PythonCommand python
```

## 三、是否迁移当前开发数据

通常不迁移：在第二台机器执行迁移后使用构造数据，或者运行 `seed_demo`。两台机器各自维护开发数据，代码中的模型变更通过 Django migration 同步。

确实需要延续当前 SQLite 测试数据时：

1. 停止两台机器上的 Django 开发服务。
2. 通过加密 U 盘或公司批准的加密传输方式复制 `.local\db.sqlite3`。
3. 如页面依赖上传文件，只复制 `.local\media`。
4. 不复制 `.env`、`.venv`、`.local\logs`、`.local\static` 或 `.local\release`。
5. 在第二台机器运行 `manage.py migrate` 和 `manage.py check`。

SQLite 库可能含账号、电话或采集记录，因此不得提交 Git、放入公开网盘或发送到聊天工具。若数据来自生产环境，先做脱敏；开发机不得直接连接生产数据库。

## 四、双机日常开发流程

每次开始工作：

```powershell
git status --short
git pull --ff-only
.\.venv\Scripts\python.exe manage.py migrate
```

完成一个小任务后：

```powershell
.\scripts\check.ps1
git add <本次修改文件>
git commit -m "<清晰的变更说明>"
git push
```

换到另一台电脑前，必须先提交并推送；另一台电脑开始前必须先拉取。不要用未提交文件在两台机器间覆盖复制。

模型变更必须运行 `makemigrations`，把生成的 migration 与代码一起提交。拉取后运行：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

如果两台电脑修改了同一文件，先在当前分支解决冲突并通过检查，再继续开发。不要强制推送 `main`。

## 五、验收清单

- [ ] 私有远程仓库已配置，`main` 可正常推送和拉取。
- [ ] 第二台电脑已配置自己的 Git 身份与远程仓库凭据，未复制第一台电脑的凭据文件。
- [ ] `.env`、`.venv`、`.local` 和归档文件未被 Git 跟踪。
- [ ] 第二台电脑使用独立 `.env` 和随机开发密钥。
- [ ] 第二台电脑的局域网 IP、CSRF 来源和媒体路径正确。
- [ ] `bootstrap-dev-machine.ps1` 执行成功。
- [ ] Ruff、pytest、Django check 和 migration check 全部通过。
- [ ] 两台电脑均能从干净检出启动项目。
- [ ] 如迁移开发数据，传输介质受控且数据已确认不含未授权生产信息。
