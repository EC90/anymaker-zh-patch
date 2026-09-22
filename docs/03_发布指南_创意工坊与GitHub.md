# 发布指南：创意工坊与 GitHub

判定背景见 [01_可行性研究.md](01_可行性研究.md) §5：**GitHub ✅ 现在就做；创意工坊 ❌ 现状无门，观察哨跟进**。本文件给出两条渠道的具体路径与触发后的动作。

## 1. 总原则

1. **diff-only 分发**：对外仓库/发布物不含完整游戏 TSV（那是游戏资产）；只含改动行差异（id + 新 zh 文本）+ 从玩家本地文件重建完整件的工具。
2. **buildid 绑定**：每个发布版本注明并测试于具体 buildid；游戏更新后未重新验证的补丁不下发新 tag。
3. **官方优先**：官方 zh 是基底；社区校对的价值是纠错与润色，发现官方译名错误时优先回馈官方（§4），官方采纳后本工程该条 diff 退役。

## 2. GitHub 发布路径（主渠道）

### 2.1 建议仓库结构（建仓时以此为准）

```
anymaker-zh-proofread/
├── README.md            ← 定位/安装方法/兼容 buildid 表/免责声明
├── glossary/            ← 术语表（id,en,zh,context 分表 CSV；由工具从 TSV 生成，不手改）
├── patches/             ← diff 文件：每文件每批一个（如 languages.tsv.json：[{id, zh_new, reason}]）
├── tools/
│   ├── apply.py         ← 安装：定位玩家本地 Steam 库→备份原 TSV→按 diff 重建修改版→写回
│   ├── revert.py        ← 回滚：从备份还原
│   └── verify.py        ← 校验：02 指南 §5 清单的自动化版
├── docs/                ← 翻译规范/变更日志的公开子集
└── CHANGELOG.md         ← 按 buildid×批次记录每条改动（id/旧译/新译/理由）
```

### 2.2 release 打包形态

- 资产：`patch-zh_b<buildid>_<seq>.zip`，内含 diff JSON + apply/revert 脚本 + 该版 CHANGELOG 摘要；**不含游戏原文件**。
- tag 命名：`v<序号>-b<buildid>`（如 `v0.1-b25422107`）。
- apply 脚本要点（写脚本时的需求基线）：
  1. 通过注册表或常见路径探测 SteamLibrary 与 `appmanifest_4435340.acf`，**核对 buildid 与补丁声明一致**，不一致则警告退出；
  2. 备份原 TSV 到同目录 `.bak_<buildid>/`（幂等：已有备份不覆盖）；
  3. 按 diff 逐 id 改 zh 列，逐项执行 02 指南 §5 校验后写回（UTF-8 无 BOM/CRLF）；
  4. 输出改动计数与失败清单。
- README 必含：免责声明（非官方、自担风险、可一键回滚）、兼容 buildid 表、与官方更新的冲突说明（游戏验证完整性即还原官方文件）。

### 2.3 与 BKN46/stormworks-translate-chn 的差异（刻意为之）

Stormworks 社区仓整包分发 `language.tsv`，因为官方工坊机制本身就以该文件为载荷。本作无该机制，且官方中文已存在，整包分发只剩风险没有收益——diff-only 是有意 diverge，不是疏漏。

## 3. 创意工坊：现状判定与开放后的预案

**现状（buildid 25422107，符号+社区证据）**：工坊接口仅载具蓝图一条通路；游戏无语言文件加载口（工坊语言物品生效所需机制不存在）。结论：语言类内容现阶段无法上工坊。

**观察哨与监控**（详细清单见 01 可行性 §5.2）：
```bash
grep -E "buildid" "<Steam库>/steamapps/appmanifest_4435340.acf"   # 更新后先核版本
grep -aoE "[A-Za-z0-9_/.]*workshop[A-Za-z0-9_/.]*language[A-Za-z0-9_/.]*" \
  "<AM_GAME>/bin/game.gcl" | sort -u     # 交叉符号
```
另盯：商店页语言列表、官方 Discord/公告、工坊物品类型是否扩展。

**开放后预案（占位，以届时实测为准）**：
1. 用 steamcmd 免订阅下载官方示例/首个语言物品，实测其文件结构与加载路径（方法照搬 `<SW参照工作区>\AI相关\Steam创意工坊Lua提取与示例编写规程.md` 的流程）；
2. 将本工程 diff 产物转换为目标格式，经游戏内上传入口（前作经验：上传走游戏内 UI，非外部 publisher 工具）发布；
3. GitHub 转为协作上游，工坊为分发终态（BKN46 模式：工坊版可能比仓库新，发布脚本以仓库为源）。

## 4. 向官方回馈勘误

- 渠道：官方 Discord（`数据库\07` 收录的官方入口）为主，工坊评论区/Steam 讨论区为辅。
- 口径模板：`buildid + TSV 文件名 + 行 id + en 原文 + 现译 + 建议译 + 理由（截图/语境）`；一批多条合并成一个反馈帖。
- 官方采纳后：在 CHANGELOG 标记该条 "upstream-fixed"，下个 buildid 基线核对后从 diff 中移除。

## 5. 版权与社区规范

- 不再分发：完整 TSV、gcl、任何游戏二进制/资源；术语表含 en+zh 文本对，属少量引用+转换性使用，保持"最小必要"（术语表仅收 id/en/zh/context 四列，不搬运其余 27 语列）。
- 工具不注入、不绕过 DRM；apply 脚本只写语言 TSV 五个文件。
- 命名与宣传明确"非官方社区校对包"，不暗示官方背书。
