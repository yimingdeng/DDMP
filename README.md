# 玉米重点品种数字展示平台

这是平台第一阶段的 Django 单体项目。当前已完成响应式展示、品种/示范点管理、图片与视频、区域联系人、咨询线索、分享元数据、来源追踪和渠道二维码。

## 快速开始

```powershell
Set-Location D:\DDMP
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

访问：

- 首页：<http://127.0.0.1:8000/>
- 演示品种：<http://127.0.0.1:8000/varieties/demo-corn-a/>
- 示范点：<http://127.0.0.1:8000/sites/>
- 后台：<http://127.0.0.1:8000/admin/>
- 健康检查：<http://127.0.0.1:8000/health/>

同一 Wi-Fi 手机访问（当前开发机地址）：<http://192.168.1.232:8000/>。开发机 IP 变化后，需要同步修改 `.env` 中的 `DJANGO_ALLOWED_HOSTS` 和 `DJANGO_CSRF_TRUSTED_ORIGINS`。

完整文档见 [docs/README.md](./docs/README.md)。

迁移到第二台开发机或双机开发时，见
[docs/18-two-machine-development-migration.md](./docs/18-two-machine-development-migration.md)。
