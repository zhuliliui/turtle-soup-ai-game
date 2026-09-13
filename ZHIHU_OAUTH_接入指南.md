# 知乎 OAuth + 故事改编 接入指南

> 本次改动已完成后，你只剩「领凭证 → 填配置 → 重启」三步。凭证从黑客松赛事页面领取。

## 一、已实现的功能

| 功能 | 端点 | 说明 |
|---|---|---|
| 登录状态查询 | `GET /api/zhihu/config` | 是否已配置 OAuth 凭证 |
| 发起登录 | `GET /api/zhihu/login` | 已配置→302 跳知乎授权页；未配置→演示会话 |
| OAuth 回调 | `GET /api/zhihu/callback` | 换 token → 取用户 → 建 HttpOnly 会话 |
| 当前用户 | `GET /api/zhihu/me` | 前端徽标显示 |
| 退出 | `POST /api/zhihu/logout` | 销毁会话 |
| 知乎故事列表 | `GET /api/zhihu/stories` | 无需鉴权，10 分钟缓存 |
| 故事详情 | `GET /api/zhihu/story/{work_id}` | 无需鉴权 |
| 故事改编开局 | `GET /api/zhihu/story/{work_id}/adapt` | 生成"一句话开局"premise + 归属信息 |

前端：开始弹窗新增**知乎账号条**（登录/退出/头像昵称徽标）和 **📖 知乎故事改编汤面**入口（选故事→自动填开局→直接开局，汤面不剧透原文，归属标注显示在开局区）。

后端新增 `backend/zhihu_integration.py`；`main.py` 已挂载路由。

## 二、领取凭证后的三步配置

1. **领取 App ID / App Key**：登录[赛事活动页](https://www.zhihu.com/hackathon?activity_code=zhihu_hackathon_2026_p2) → 我的项目 → 创建项目后按页面提示领取。
2. **填入 `backend/.env`**（已有占位行）：
   ```
   ZHIHU_OAUTH_APP_ID=领到的AppID
   ZHIHU_OAUTH_APP_KEY=领到的AppKey
   ZHIHU_OAUTH_REDIRECT_URI=https://你的公网域名/api/zhihu/callback
   ```
3. **登记回调地址**：在赛事页面「知乎登录回调地址」填**完全一致**的值（含 https、路径、无尾斜杠），然后重启后端。

## 三、回调地址（公网 HTTPS）

- 回调地址必须是**公网可访问的 HTTPS**，本地 `localhost:8000` 只能用于开发调试（留空 REDIRECT_URI 时自动按当前请求推导）。
- 与小朱工作台同机时，用 Tailscale Funnel 暴露 8000 端口即可得到公网 HTTPS 域名，例如：
  `tailscale funnel 8000` → 回调填 `https://laptop-a763c6tn.taild83cf2.ts.net/api/zhihu/callback`
- Demo 链接同理用该域名对外提供。

## 四、演示模式（未配置凭证时）

- 凭证留空时，「登录知乎」按钮会创建**演示会话**，前端明确显示「演示会话：演示玩家」，不冒充真实知乎登录。
- 知乎故事改编功能**不依赖凭证**，现在就能用（已实测拉到 20 个故事）。
- 评委/社区用户点击 Demo 时若想体验真实知乎登录，请先完成第二节配置。

## 五、安全红线（提交前自查，对照官方检查单）

- [ ] App Key、Access Secret、OAuth token **不在**代码仓库、前端响应、URL、日志、截图、视频中出现（token 只存后端进程内存，前端只拿 HttpOnly cookie）
- [ ] 回调地址与赛事页面登记值**完全一致**
- [ ] 凭证未配置时错误提示真实（演示模式有明确标注，接口失败有真实报错）
- [ ] Demo 从公网能打开并走通核心流程（开一局、故事改编开一局）
- [ ] 提交后去开放平台**重置 Access Secret**（曾在聊天中出现过的凭证一律作废重建）

## 六、实测记录（2026-09-13）

- `story/list` 真实返回 20 个故事（顶层为数组）；`story/{work_id}` 顶层为单对象，**标题在 `chapter_name`**（列表里是 `title`），已做兼容。
- 登录 302 → `openapi.zhihu.com/authorize` 参数齐全（redirect_uri/app_id/response_type/state）。
- 坏 state / 缺授权码的回调均被正确拒绝（400）。
- 演示模式登录→me→退出链路通过；token 交换与 `/user` 需真实凭证后联调（协议字段已按 skill 实测文档实现：回调参数 `authorization_code`，token 表单字段 `code`，`code:20000` 为成功）。
