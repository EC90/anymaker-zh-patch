# Anymaker 简中汉化包（anymaker-zh-patch）

[![Release](https://img.shields.io/badge/release-v1.0.0--b25436400-blue)](../../releases)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/code-MIT-green)

非官方社区补丁：让 **[Anymaker](https://store.steampowered.com/app/4435340/)**（Steam 抢先体验）在英文界面下显示**简体中文**——利用游戏自带但尚未启用的官方中文数据（语言表 zh 列 + 随包简中字体），外加少量社区短译。**本仓库不含任何游戏文本**：所有翻译在安装时从玩家本机游戏文件实时推导。

## 快速开始

| 你是… | 做法 |
|---|---|
| 普通玩家 | 下载 [Release](../../releases) 的 `anymaker-zh-installer.exe`（免 Python，双击即用）或 zip 包；见下 |
| AI agent / 自动化 | 读 [AGENTS.md](AGENTS.md) 与 [install.json](install.json)，按机器可读流程安装 |
| 译者 / 共建者 | 编辑 [润色词典.csv](润色词典.csv) 提 PR，见下方共建指南 |

### 安装（zip 形态，需 Python 3.8+）

1. 完全退出游戏；
2. 双击 `一键安装.bat`（或 `python 安装汉化.py install`）；
3. 启动游戏，界面即为中文。安装器自动定位 Steam 库，并在自己旁边保留原始文件备份。

### 卸载

- 双击 `一键卸载.bat`（或 `python 安装汉化.py uninstall`）；
- 或任何时候用 Steam「验证文件完整性」彻底还原。

### 游戏更新后

重新运行安装即可（幂等）：补丁按内容匹配而非版本号，新文件重新推导；官方新增词条若已带中文会自动生效。

## 原理（为什么这样是安全的）

1. **官方数据**：游戏文件内实测含 30 种语言的完整翻译（含简繁中文）与 Noto Sans SC/TC 字体，仅因商店页未声明中文而不可见。本补丁不引入任何外部翻译文本。
2. **四步安装**：①语言表 en 列 := zh 列（游戏以英文运行，显示中文）②简中字体替换西文字体槽（原拉丁字体无 CJK 字形）③定义表 name 字段汉化（组件/物品/生物名）④`game.gcl` 内嵌英文串等长替换（英文界面的实际显示源）。
3. **字节级安全**：gcl 替换采用**等长 NUL 填充**（总文件大小严格不变、零偏移位移），只碰前导 NUL 或长度前缀签名的独立常量，且排除纯小写词条（引擎功能性常量保护）。
4. **三级回滚**：安装器自带备份 → `uninstall` 一键还原 → Steam 验证完整性兜底。

## 共建指南

- **改词入口只有一个文件**：[润色词典.csv](润色词典.csv)，三列 `类型,键,中文`：
  - `gcl`：界面英文原文 → 中文（受**等长字节限制**：中文字节数=字数×3，不得超过原英文字符数）；
  - `name`：定义表条目 id → 显示名（组件/物品/生物，无长度限制）；
  - `tsv`：语言表行 id → 译文（en/zh 双列同改，无长度限制）。
- 工作清单与规则详见 [docs/09_润色与打包指南.md](docs/09_润色与打包指南.md)（docs/ 为研发过程文档脱敏存档）。
- PR 前请本地跑 `python 安装汉化.py install` 验证你的词条生效（status 会报告未生效项）。

## 已知边界

- `MUSIC / MOUSE / ULTRA` 等 5 字节内短词与 F7 调试面板部分条目仍为英文（等长替换放不下双字中文）；
- 官方若在 Steam 语言列表启用简体中文：`uninstall` 后直接在属性里选中文即可（数据同源），本补丁退役。

## 致谢

- **Anymaker** 官方（Geometa）——所有翻译与字体的实际来源；
- **Stormworks** 社区汉化（BKN46 等）——机械/载具术语参照。

## 免责声明

非官方作品，与 Geometa / Steam 无关。修改本地游戏文件属用户自担风险；本补丁不绕过任何 DRM，可随时完整卸载。仅分发脚本与少量社区短译词，不分发任何游戏内容。

## 许可

- 代码（`安装汉化.py` 及构建脚本）：[MIT](LICENSE)
- 词典与文档（`润色词典.csv`、`使用说明.md`、`docs/`）：CC BY-NC-SA 4.0
