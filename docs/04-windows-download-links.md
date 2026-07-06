# Windows 环境软件下载链接

以下链接均为官方网站或项目官方发布页。开发电脑先安装“必须安装”部分；Caddy 和 WinSW 只在测试、运行环境需要。

## 1. 开发电脑必须安装

| 软件 | 下载链接 | 选择说明 |
|---|---|---|
| Python 3.13 | [Python Windows 官方下载](https://www.python.org/downloads/windows/) | 选择最新的 Python 3.13.x、`Windows installer (64-bit)`；安装时启用 PATH |
| Git for Windows | [Git Windows 官方安装页](https://git-scm.com/install/windows.html) | 普通 Intel/AMD 电脑选择 x64 Setup |
| PostgreSQL 17 | [PostgreSQL Windows 官方安装页](https://www.postgresql.org/download/windows/) | 选择 PostgreSQL 17.x、Windows x86-64；安装器可同时安装 pgAdmin |
| Visual Studio Code | [VS Code 官方下载](https://code.visualstudio.com/download) | 开发电脑选择 Windows `User Installer x64` |

## 2. VS Code 推荐扩展

安装 VS Code 后，从扩展市场安装：

| 扩展 | 官方链接 | 用途 |
|---|---|---|
| Python | [Microsoft Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python) | Python 解释器、调试和测试集成 |
| Pylance | [Microsoft Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) | 类型提示和代码导航 |
| Ruff | [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) | Python 格式和静态检查 |

不需要安装 Node.js、Java、Redis、Docker Desktop 或 Visual Studio；第一阶段技术方案不依赖它们。

## 3. 测试和运行环境安装

测试、运行主机除 Python 和 PostgreSQL 外，还需要：

| 软件 | 下载链接 | 选择说明 |
|---|---|---|
| Caddy | [Caddy 官方下载](https://caddyserver.com/download) | Windows amd64 标准版，不选择第三方插件 |
| WinSW | [WinSW 官方 Releases](https://github.com/winsw/winsw/releases) | 选择稳定版的 64 位可执行文件，不使用 alpha/pre-release |

Waitress、Django、pytest、Ruff 等 Python 包不单独从网页下载。项目创建依赖文件后，通过虚拟环境统一安装：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements\dev.txt
```

测试和运行环境使用：

```powershell
pip install -r requirements\prod.txt
```

## 4. 当前推荐选择

截至 2026 年 6 月，项目约定：

- Python：3.13 系列最新补丁版。
- Django：5.2 LTS 系列，由依赖文件锁定。
- PostgreSQL：17 系列最新补丁版。
- Git、VS Code、Caddy：安装时的当前稳定版。
- WinSW：稳定版，不安装 3.x alpha 预发布版本。

不要下载 32 位、ARM64、embeddable、source、Beta、RC、alpha 或 portable 版本，除非电脑硬件或部署方式明确需要。

## 5. 安装后验证

重新打开 PowerShell，执行：

```powershell
git --version
py -3.13 --version
psql --version
code --version
```

测试/运行主机另外执行：

```powershell
caddy version
```

如果 `psql` 或 `caddy` 无法识别，需要把相应可执行文件目录加入系统 PATH，再重新打开 PowerShell。
