# 公网代码发布工具（保留生产数据）

适用目标：将开发机的新源代码部署到 Windows 公网服务器，同时保留服务器现有数据库记录和上传图片/视频。

相关范围：FR-OPS-01、FR-OPS-02。

> 脚本文件名暂时保留 `migration-package`，兼容服务器现有操作习惯；当前生成和接受的包已经改为 `ddmp-code-*` 代码包。

## 1. 安全边界

日常发布工具保证：

- 不执行 `dumpdata`、`flush` 或 `loaddata`。
- 不把开发机数据库放入发布包。
- 不把开发机 `.local\media` 放入发布包。
- 不删除、覆盖或镜像 `D:\DDMP-RUNTIME\data\media`。
- 不修改服务器 `D:\DDMP-RUNTIME\config\.env`。
- 旧的 `ddmp-migration-*.zip` 不会被自动选中，并会被新版应用脚本拒绝。

部署默认会执行 Django `migrate`，使代码自带的数据库迁移增加必要的表或字段。该操作不会清空数据库或导入开发数据，但属于数据库结构升级。确认本次没有模型变更时，可以手工加 `-SkipMigrations`；日常自动批处理建议保留迁移步骤，避免代码与数据库结构不一致。

## 2. 代码包内容

开发机执行打包后生成：

```text
.local\release\ddmp-code-YYYYMMDD-HHMMSS\
├─ code\                 # 应用源代码
└─ manifest.json         # code_only 安全标识
```

同时生成同名 ZIP：

```text
.local\release\ddmp-code-YYYYMMDD-HHMMSS.zip
```

代码目录不包含 `.env`、`.venv`、`.local`、数据库文件、日志、RAR 和旧 ZIP。

## 3. 开发机生成代码包

运行：

```powershell
D:\DDMP\scripts\build-latest-migration-package.bat
```

批处理会明确提示“source-code-only”，完成后列出最新的 `ddmp-code-*.zip`。

也可以从仓库根目录执行：

```powershell
.\scripts\build-migration-package.ps1
```

生成结果位于：

```text
D:\DDMP\.local\release\
```

## 4. 复制到服务器

每次复制以下三个文件，并覆盖服务器上的旧部署脚本：

```text
D:\DDMP-RUNTIME\incoming\ddmp-code-YYYYMMDD-HHMMSS.zip
D:\DDMP-RUNTIME\incoming\apply-migration-package.ps1
D:\DDMP-RUNTIME\incoming\apply-latest-migration-package.bat
```

不要再把 `ddmp-migration-*.zip` 用于日常公网更新。

## 5. 服务器一键发布

右键“以管理员身份运行”或在管理员 PowerShell 中执行：

```powershell
D:\DDMP-RUNTIME\incoming\apply-latest-migration-package.bat
```

批处理只查找最新的 `ddmp-code-*.zip`，随后：

1. 校验 `manifest.json` 必须是 `package_type=code_only`。
2. 拒绝包含 `data` 或 `media` 目录的包。
3. 停止 `DDMP-App`。
4. 将当前代码备份到 `D:\DDMP-RUNTIME\backups\app`。
5. 覆盖 `D:\DDMP-RUNTIME\app\current` 源代码。
6. 安装或更新 `requirements\prod.txt`。
7. 执行已提交的 Django 数据库结构迁移。
8. 执行 `collectstatic` 和生产配置检查。
9. 启动 `DDMP-App` 并检查 `/health/`。

服务器数据库业务记录以及 `D:\DDMP-RUNTIME\data\media` 全程保留。

## 6. 指定代码包发布

管理员 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force

D:\DDMP-RUNTIME\incoming\apply-migration-package.ps1 `
  -PackagePath D:\DDMP-RUNTIME\incoming\ddmp-code-YYYYMMDD-HHMMSS.zip `
  -RuntimeRoot D:\DDMP-RUNTIME `
  -PublicHost bzb889.originseed.com.cn `
  -ServiceName DDMP-App
```

确认本次绝对没有模型或迁移变化时，才可以增加：

```powershell
-SkipMigrations
```

## 7. 发布验证

服务器本机：

```powershell
curl.exe -i `
  -H "Host: bzb889.originseed.com.cn" `
  -H "X-Forwarded-Proto: https" `
  http://127.0.0.1:8000/health/
```

公网检查：

```powershell
curl.exe -I https://bzb889.originseed.com.cn/
curl.exe -I https://bzb889.originseed.com.cn/varieties/bzb889/
```

发布后重点确认：

- 后台原有账号仍能登录。
- 公网线索、示范户和田间采集记录仍存在。
- 原有图片、视频仍能打开。
- 首页、品种详情、示范点和二维码访问正常。
- 新版静态样式已经生效。

## 8. 代码回滚

每次发布前的代码位于：

```text
D:\DDMP-RUNTIME\backups\app\before-YYYYMMDD-HHMMSS\
```

代码回滚时停止 `DDMP-App`，把对应备份恢复到 `app\current`，重新执行 `collectstatic`，然后启动服务。

如果该版本包含数据库结构迁移，不要直接删除生产数据或反向导入开发数据库；应根据迁移内容单独制定回滚方案。
