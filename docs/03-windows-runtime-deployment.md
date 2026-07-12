# Windows 运行环境搭建与运维

## 1. 适用范围

本文用于第一阶段正式试运行环境。它以单台 Windows Server 部署为基线，适用于访问量不大、内部维护人员较少的平台。

当日访问量、媒体容量或并发明显增加时，再评估对象存储、CDN、独立数据库或 Linux/容器化迁移；首版不预先增加这些复杂度。

## 2. 推荐配置

### 2.1 操作系统和硬件

| 项目 | 建议 |
|---|---|
| 操作系统 | Windows Server 2022 64 位或更新的受支持版本 |
| CPU | 4 核起步 |
| 内存 | 8 GB 起步；图片处理较多时建议 16 GB |
| 系统盘 | 80 GB 以上 |
| 数据盘 | 100 GB 起步，按图片增长量扩容 |
| 网络 | 固定公网 IP、独立域名、稳定上行带宽 |
| 备份 | 独立磁盘或云对象存储，不能只存本机同一数据盘 |

### 2.2 软件

- Python 3.13.x 64 位。
- Django 5.2.x LTS，由依赖文件锁定。
- PostgreSQL 17.x 64 位。
- Waitress，由依赖文件锁定。
- Caddy 当前稳定版。
- WinSW 当前稳定版，用于把应用注册为 Windows 服务。
- Git 可选；若采用发布包部署，运行服务器可以不安装 Git。

如果服务器位于中国大陆公网，应在开放正式访问前按云服务商和所在地要求完成域名备案，并提前准备能够申请公网证书的正式域名。

## 3. 网络与安全边界

| 端口 | 用途 | 暴露范围 |
|---|---|---|
| 80 | HTTP 跳转到 HTTPS、证书签发 | 公网 |
| 443 | H5 和管理后台 HTTPS | 公网 |
| 8000 | Waitress | 仅 `127.0.0.1` |
| 5432 | PostgreSQL | 仅本机或受控内网 |
| 3389 | 远程桌面 | 仅公司固定 IP/VPN，禁止全网开放 |

服务器上创建专用低权限服务账号运行 Django。日常服务进程不使用域管理员或本地管理员账号。

## 4. 目录规划

```text
D:\DDMP-RUNTIME\
├─ app\current\          # 当前版本代码
├─ app\releases\         # 保留最近发布包
├─ venv\                 # Python 虚拟环境
├─ config\.env           # 生产环境变量，仅管理员和服务账号可读
├─ data\media\           # 用户上传文件
├─ data\static\          # collectstatic 输出
├─ logs\app\             # 应用日志
├─ logs\caddy\           # Web 访问日志
├─ backups\database\     # 数据库备份的本地暂存
├─ backups\media\        # 媒体备份的本地暂存
├─ services\app\         # Django/Waitress 的 WinSW 文件
└─ caddy\                 # caddy.exe、Caddyfile 和服务文件
```

代码发布不能覆盖 `config`、`data`、`logs` 和 `backups`。这些目录不属于 Git 仓库。

## 5. 安装基础软件

1. 安装 Windows 更新并重启。
2. 安装 Python 3.13 64 位。
3. 安装 PostgreSQL 17 64 位及命令行工具。
4. 从官方渠道下载 Caddy Windows 二进制。
5. 从 WinSW 官方发布页下载 64 位程序。
6. 创建专用 Windows 服务账号并授权所需目录。

建议服务账号只拥有以下权限：读取应用代码和生产配置，读写 `data`、`logs` 及 Caddy 状态目录，作为服务登录。它不应拥有交互式远程登录或数据库超级用户权限。

验证：

```powershell
py -3.13 --version
psql --version
D:\DDMP-RUNTIME\caddy\caddy.exe version
```

## 6. 创建运行数据库

进入 PostgreSQL：

```powershell
psql -U postgres
```

创建专用用户和数据库：

```sql
CREATE ROLE ddmp_prod_user LOGIN PASSWORD 'replace-with-strong-production-password';
CREATE DATABASE ddmp_prod OWNER ddmp_prod_user ENCODING 'UTF8';
\q
```

要求：

- 密码使用随机生成的长密码。
- 不让应用使用 `postgres` 超级用户。
- PostgreSQL 只监听本机，除非后续迁移到独立数据库服务器。
- 定期安装当前主版本的安全和修复更新。

## 7. 安装应用

### 7.1 创建虚拟环境

```powershell
py -3.13 -m venv D:\DDMP-RUNTIME\venv
D:\DDMP-RUNTIME\venv\Scripts\python.exe -m pip install --upgrade pip
D:\DDMP-RUNTIME\venv\Scripts\pip.exe install -r D:\DDMP-RUNTIME\app\current\requirements\prod.txt
```

### 7.2 配置环境变量

在 `D:\DDMP-RUNTIME\config\.env` 保存生产配置。至少包括：

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=生产环境随机长密钥
DJANGO_ALLOWED_HOSTS=show.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://show.example.com
DATABASE_URL=postgresql://ddmp_prod_user:生产密码@127.0.0.1:5432/ddmp_prod
MEDIA_ROOT=D:/DDMP-RUNTIME/data/media
STATIC_ROOT=D:/DDMP-RUNTIME/data/static
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

`.env` 的 NTFS 权限仅授予服务器管理员和应用服务账号。不要把 `.env` 放入代码目录或备份到公开位置。

### 7.3 初始化应用

```powershell
Set-Location D:\DDMP-RUNTIME\app\current
D:\DDMP-RUNTIME\venv\Scripts\python.exe manage.py migrate
D:\DDMP-RUNTIME\venv\Scripts\python.exe manage.py generate_marketing_materials --missing-only
D:\DDMP-RUNTIME\venv\Scripts\python.exe manage.py collectstatic --noinput
D:\DDMP-RUNTIME\venv\Scripts\python.exe manage.py check --deploy
D:\DDMP-RUNTIME\venv\Scripts\python.exe manage.py createsuperuser
```

`check --deploy` 出现的安全问题必须逐项确认，不能简单忽略。

## 8. 配置 Waitress Windows 服务

以下示例使用 WinSW。把 WinSW 可执行文件重命名为：

```text
D:\DDMP-RUNTIME\services\app\ddmp-app-service.exe
```

在同目录创建 `ddmp-app-service.xml`：

```xml
<service>
  <id>DDMP-App</id>
  <name>DDMP Django Application</name>
  <description>玉米重点品种数字展示平台</description>
  <executable>D:\DDMP-RUNTIME\venv\Scripts\python.exe</executable>
  <arguments>-m waitress --listen=127.0.0.1:8000 config.wsgi:application</arguments>
  <workingdirectory>D:\DDMP-RUNTIME\app\current</workingdirectory>
  <env name="DJANGO_ENV_FILE" value="D:\DDMP-RUNTIME\config\.env" />
  <startmode>Automatic</startmode>
  <onfailure action="restart" delay="10 sec" />
  <logpath>D:\DDMP-RUNTIME\logs\app</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>10</keepFiles>
  </log>
</service>
```

项目必须实现通过 `DJANGO_ENV_FILE` 加载环境文件；如果最终采用其他加载方式，应同步修改这里和项目文档。

以管理员 PowerShell 安装并启动：

```powershell
Set-Location D:\DDMP-RUNTIME\services\app
.\ddmp-app-service.exe install
.\ddmp-app-service.exe start
Get-Service DDMP-App
```

安装完成后，在 `services.msc` 中把 `DDMP-App` 的“登录”账号改为前述专用服务账号，并重新启动服务。不要让应用长期以 `LocalSystem` 运行。

本机验证：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health/ -UseBasicParsing
```

## 9. 配置 Caddy

在 `D:\DDMP-RUNTIME\caddy\Caddyfile` 创建配置：

```caddyfile
show.example.com {
    encode zstd gzip

    handle_path /static/* {
        root * D:\DDMP-RUNTIME\data\static
        file_server
    }

    handle_path /media/* {
        root * D:\DDMP-RUNTIME\data\media
        header X-Content-Type-Options nosniff
        file_server
    }

    reverse_proxy 127.0.0.1:8000

    log {
        output file D:\DDMP-RUNTIME\logs\caddy\access.log {
            roll_size 50MiB
            roll_keep 10
            roll_keep_for 720h
        }
    }
}
```

将 `show.example.com` 替换为正式域名。正式域名须提前解析到服务器公网 IP，云安全组和 Windows 防火墙须开放 80/443。

验证配置：

```powershell
D:\DDMP-RUNTIME\caddy\caddy.exe validate `
  --config D:\DDMP-RUNTIME\caddy\Caddyfile `
  --adapter caddyfile
```

Caddy 官方支持使用 `sc.exe` 或 WinSW 注册 Windows 服务。为统一维护，建议同样使用 WinSW。把 WinSW 可执行文件重命名为 `D:\DDMP-RUNTIME\caddy\ddmp-caddy-service.exe`，并在同目录创建 `ddmp-caddy-service.xml`：

```xml
<service>
  <id>DDMP-Caddy</id>
  <name>DDMP Caddy Web Server</name>
  <description>DDMP HTTPS and reverse proxy service</description>
  <executable>D:\DDMP-RUNTIME\caddy\caddy.exe</executable>
  <arguments>run --config D:\DDMP-RUNTIME\caddy\Caddyfile --adapter caddyfile</arguments>
  <workingdirectory>D:\DDMP-RUNTIME\caddy</workingdirectory>
  <env name="XDG_DATA_HOME" value="D:\DDMP-RUNTIME\caddy\data" />
  <env name="XDG_CONFIG_HOME" value="D:\DDMP-RUNTIME\caddy\config" />
  <startmode>Automatic</startmode>
  <onfailure action="restart" delay="10 sec" />
  <logpath>D:\DDMP-RUNTIME\logs\caddy</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>10</keepFiles>
  </log>
</service>
```

安装并启动：

```powershell
Set-Location D:\DDMP-RUNTIME\caddy
.\ddmp-caddy-service.exe install
.\ddmp-caddy-service.exe start
Get-Service DDMP-Caddy
```

同样在 `services.msc` 中确认服务登录账号和目录权限。Caddy 服务账号必须能够读写 `D:\DDMP-RUNTIME\caddy\data`，否则自动 HTTPS 证书无法持久保存。

Caddy 启动后验证：

```powershell
Invoke-WebRequest https://show.example.com/health/ -UseBasicParsing
```

## 10. Windows 防火墙

仅开放 Web 端口：

```powershell
New-NetFirewallRule -DisplayName "DDMP HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "DDMP HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

不要为 8000 和 5432 创建公网入站规则。远程桌面应通过 VPN、堡垒机或固定来源 IP 限制。

## 11. 标准发布流程

每次发布按以下顺序执行：

1. 测试环境验收通过并创建版本标签。
2. 通知业务人员短暂维护窗口。
3. 备份运行数据库和媒体目录。
4. 将新版本解压到新的 `releases` 子目录。
5. 安装或更新锁定依赖。
6. 执行迁移计划检查。
7. 停止 `DDMP-App` 服务。
8. 切换 `current` 到新版本，或复制已审核发布包。
9. 执行 `migrate`、`collectstatic` 和 `check --deploy`。
10. 启动 `DDMP-App`，必要时重载 Caddy。
11. 执行健康检查和业务冒烟测试。
12. 记录版本号、发布时间、迁移和验证结果。

建议的发布验证命令：

```powershell
python manage.py showmigrations
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

## 12. 回滚原则

- 纯页面或 Python 代码问题：切换回上一个发布包并重启应用服务。
- 已执行兼容性数据库迁移：通常保留迁移，回滚代码前确认旧代码兼容。
- 删除列、重写数据等破坏性迁移：发布前必须备份；失败时停止服务并恢复数据库。
- 不在故障现场临时执行未评审的反向迁移。
- 媒体文件问题：从独立备份恢复，避免覆盖正常的新文件。

每个数据库迁移应优先采用“先增加、再切换、最后清理”的兼容方式，避免代码发布和数据库变更必须在同一秒完成。

## 13. 备份方案

### 13.1 数据库备份

每天由 Windows 任务计划程序执行 `pg_dump`：

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe' `
  --host 127.0.0.1 `
  --username ddmp_prod_user `
  --format custom `
  --file "D:\DDMP-RUNTIME\backups\database\ddmp_prod.backup" `
  ddmp_prod
```

正式脚本应为文件名加入日期时间，并从受保护位置读取密码，不能把密码直接写入公开脚本或命令历史。

### 13.2 媒体文件备份

每日增量备份 `D:\DDMP-RUNTIME\data\media`，至少再复制到另一块磁盘或云对象存储。

### 13.3 保留策略

- 每日备份：保留 7 份。
- 每周备份：保留 4 份。
- 每月备份：保留 12 份。
- 每季度执行一次完整恢复演练。

本机同一硬盘上的备份不算完整备份。

### 13.4 恢复验证

恢复演练必须在独立测试数据库执行：

```powershell
createdb -h 127.0.0.1 -U postgres ddmp_restore_test
pg_restore -h 127.0.0.1 -U postgres -d ddmp_restore_test ddmp_prod.backup
```

恢复后检查关键表数量、管理员登录、首页、示范点和线索查询。

## 14. 日常运维

### 每日

- 检查首页和健康检查。
- 检查 `DDMP-App`、Caddy、PostgreSQL 服务状态。
- 检查前一晚备份是否成功。
- 查看 500 错误和磁盘剩余空间。

### 每周

- 检查异常登录、重复表单和上传失败。
- 检查日志增长和媒体目录增长。
- 在测试环境安装并验证应用补丁。

### 每月

- 安装 Windows、Python 依赖、PostgreSQL 和 Caddy 的安全更新，先测试后运行。
- 验证管理员账号和权限。
- 检查 HTTPS 证书状态。
- 抽查一次备份可读性。

### 每季度

- 执行数据库和媒体完整恢复演练。
- 清理过期管理员和测试账号。
- 复核隐私数据、日志保留和磁盘容量。

## 15. 监控与日志

首版采用轻量监控：

- `/health/`：应用进程与数据库连接健康。
- Windows 服务状态：应用、Caddy、PostgreSQL。
- Caddy 访问日志：请求、状态码和响应时间。
- Django 应用日志：异常、权限拒绝、表单提交失败。
- 磁盘监控：剩余空间低于 20% 告警。
- 备份任务：成功/失败写入 Windows 事件或独立日志。

日志不得完整记录密码、会话 Cookie、数据库连接串或客户表单内容。手机号在普通日志中应脱敏。

## 16. 安全检查清单

- [ ] `DEBUG=False`。
- [ ] `SECRET_KEY` 和数据库密码仅存在受保护配置中。
- [ ] 全站 HTTPS，HTTP 自动跳转 HTTPS。
- [ ] `ALLOWED_HOSTS` 只包含正式域名。
- [ ] Session 和 CSRF Cookie 启用 Secure。
- [ ] 管理员使用强密码，不共享账号。
- [ ] PostgreSQL、Waitress 不对公网开放。
- [ ] 上传文件校验类型、扩展名和大小。
- [ ] 媒体目录不执行脚本。
- [ ] Windows、PostgreSQL、Python 依赖和 Caddy 定期更新。
- [ ] 日志不记录秘密和完整隐私数据。
- [ ] 数据库和媒体存在异机备份并验证可恢复。

## 17. 上线验收清单

- [ ] 正式域名解析正确。
- [ ] HTTPS 证书有效。
- [ ] 重启服务器后三个服务自动恢复。
- [ ] 首页、详情、示范点和表单可用。
- [ ] 后台登录、内容修改和发布正常。
- [ ] 微信和抖音内置浏览器实机验证通过。
- [ ] 来源参数和二维码统计正确。
- [ ] 数据库和媒体备份成功。
- [ ] 完成一次测试环境恢复。
- [ ] 已记录当前版本号、负责人和应急联系方式。

## 18. 参考资料

- [Django 部署检查清单](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Waitress 文档](https://docs.pylonsproject.org/projects/waitress/en/latest/)
- [PostgreSQL Windows 安装程序](https://www.postgresql.org/download/windows/)
- [Caddy Windows 服务](https://caddyserver.com/docs/running#windows-service)
- [Caddy 安装](https://caddyserver.com/docs/install)
