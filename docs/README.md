# 玉米重点品种数字展示平台：项目文档

本文档集面向平台第一阶段建设：优先完成可在微信、抖音及二维码场景中访问的 H5 展示平台，同时提供一个够用、易维护的基础管理后台。

## 文档目录

1. [总体开发方案](./01-development-plan.md)
2. [Windows 开发与测试环境搭建](./02-windows-dev-test-environment.md)
3. [Windows 运行环境搭建与运维](./03-windows-runtime-deployment.md)
4. [Windows 环境软件下载链接](./04-windows-download-links.md)
5. [详细功能需求与迭代基线](./05-detailed-functional-requirements.md)
6. [Sprint 1 实施记录](./06-sprint-1-implementation.md)
7. [Sprint 2 实施记录](./07-sprint-2-implementation.md)
8. [Sprint 3 实施记录](./08-sprint-3-implementation.md)
9. [区域联系人与咨询线索实施记录](./09-regional-contacts-and-inquiries.md)
10. [Sprint 4：传播和留资实施记录](./10-sprint-4-sharing-and-leads.md)
11. [DDMP 迁移到第二台开发机与双机开发](./18-two-machine-development-migration.md)

## 当前决策摘要

- 架构：Django 单体应用，不拆微服务。
- 第一阶段：展示端优先，基础管理后台同步建设。
- 前端：Django 模板、HTML、CSS 和少量 JavaScript；需要局部交互时使用 HTMX。
- 后端：Python 3.13、Django 5.2 LTS。
- 数据库：PostgreSQL 17。
- Windows Web 服务：Waitress；HTTPS 和反向代理：Caddy。
- 发布节奏：一周一个 Sprint，测试环境每周发布，运行环境按验收结果发布。
- 暂不纳入：微信小程序、抖音小程序、微服务、Redis、消息队列、复杂 CRM、视频转码和高级 BI。

## 环境约定

| 环境 | 用途 | 建议位置 |
|---|---|---|
| 开发环境 | 编码、单元测试、页面调试 | 开发人员 Windows 电脑，`D:\DDMP` |
| 测试环境 | 业务验收、手机端及微信/抖音内测试 | 独立 Windows 主机，`D:\DDMP-TEST` |
| 运行环境 | 正式试运行和后续生产使用 | Windows Server，`D:\DDMP-RUNTIME` |

三个环境必须使用不同数据库、不同密钥、不同域名和不同上传文件目录。测试环境不得直接连接正式数据库。
