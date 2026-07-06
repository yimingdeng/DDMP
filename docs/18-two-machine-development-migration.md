# DDMP 迁移到第二台开发机与双机开发

相关范围：`SYS-CONFIG-001`、`SYS-BACKUP-001`。

## 推荐方案

代码和 Django 迁移文件通过 Git 同步；每台电脑分别维护 `.env`、`.venv`、开发数据库和 `.local\media`。不要通过网盘自动同步整个 `D:\DDMP` 目录，也不要让两台电脑同时打开同一个 SQLite 文件。

这样可以保证代码历史可追踪，同时避免本机密钥、客户信息、日志和上传文件进入 Git。

## 当前机器的迁移前状态

截至 2026-07-06：

- Git 仓库尚无首次提交，也没有远程仓库。
- 当前开发环境使用 `.local\db.sqlite3`，不是 PostgreSQL。
- `.env`、`.venv` 和 `.local` 已被 Git 忽略。
- 根目录的 `DDMP-0702.rar` 是本地归档，不应提交。
- `.local\release` 中旧发布包不是第二台开发机所需内容。

首次迁移前必须先完成“建立 Git 基线”和“配置私有远程仓库”。远程仓库地址和账号权限需要由仓库所有者提供。

## 一、当前机器：建立可同步的代码基线

先确认忽略规则正常，并检查将要提交的文件：

```powershell
Set-Location D:\DDMP
git status --short
git check-ignore .env .venv .local DDMP-0702.rar
```

首次提交前运行完整验证：

```powershell
.\scripts\check.ps1
```

然后建立提交并连接私有远程仓库：

```powershell
git add .
git status --short
git commit -m "chore: establish DDMP development baseline"
git remote add origin <私有远程仓库地址>
git push -u origin main
```

提交前必须确认列表中没有 `.env`、`.local`、数据库文件、媒体文件、日志、RAR/ZIP/7Z 或真实客户数据。

## 二、第二台机器：安装和初始化

安装 Git for Windows 和 Python 3.13。项目当前可先使用 SQLite；需要与共享环境保持一致时，再安装 PostgreSQL 17 并为该电脑创建独立开发库。

```powershell
Set-Location D:\
git clone <私有远程仓库地址> DDMP
Set-Location D:\DDMP
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
- `MEDIA_ROOT`、`STATIC_ROOT`、`LOG_DIR` 应指向第二台机器的本地目录。

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
- [ ] `.env`、`.venv`、`.local` 和归档文件未被 Git 跟踪。
- [ ] 第二台电脑使用独立 `.env` 和随机开发密钥。
- [ ] 第二台电脑的局域网 IP、CSRF 来源和媒体路径正确。
- [ ] `bootstrap-dev-machine.ps1` 执行成功。
- [ ] Ruff、pytest、Django check 和 migration check 全部通过。
- [ ] 两台电脑均能从干净检出启动项目。
- [ ] 如迁移开发数据，传输介质受控且数据已确认不含未授权生产信息。
