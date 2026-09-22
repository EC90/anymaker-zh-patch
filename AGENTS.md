# AGENTS.md — Agent/Harness 安装指引（机器可读版）

本文件面向 AI agent / 自动化 harness，描述如何替用户安装、验证、卸载本汉化包。人类用户请读 [README.md](README.md)。机器可读元数据见 [install.json](install.json)。

## 目标

Anymaker（Steam AppID **4435340**，Windows，Early Access）界面汉化：启用游戏自带但未启用的官方简中数据。补丁只改本地文件、可完整回滚、不含游戏文本分发。

## 前置检查

1. **定位游戏**：读注册表 `HKCU\Software\Valve\Steam` → `SteamPath`；解析 `<SteamPath>\steamapps\libraryfolders.vdf` 中所有 `"path"` 库；在 `<库>\steamapps\` 下找 `appmanifest_4435340.acf` 与 `common\Anymaker\` 目录。（安装器内置此逻辑，agent 只需确认游戏已安装。）
2. **游戏未运行**：`tasklist /FI "IMAGENAME eq game.exe"` 不得含 game.exe。
3. **Python 3.8+** 在 PATH（`python --version`）；缺失则使用 `anymaker-zh-installer.exe`。

## 安装

```bash
git clone https://github.com/EC90/anymaker-zh-patch.git   # 或下载 Release zip
cd anymaker-zh-patch
python 安装汉化.py install
```

- 也可直接调用安装器子进程；退出码非 0 视为失败，读 stdout 诊断。
- exe 形态：`anymaker-zh-installer.exe install`（参数同上，工作目录=exe 所在目录）。

## 验证

```bash
python 安装汉化.py status
```

预期输出：5 个语言表 `en==zh` 达满值、`gcl 汉化痕迹` > 0、`字体为 SC: True`、`备份:` 列表非空。最终验收以用户启动游戏看到中文界面为准。

## 卸载 / 回滚

```bash
python 安装汉化.py uninstall     # 按安装时备份还原（当前 buildid）
```

跨版本/备份丢失时：Steam 库 → 右键游戏 → 属性 → 已安装文件 → **验证文件完整性**（权威还原）。agent 不得向用户承诺"官方中文"，本补丁为非官方社区件。

## 游戏更新后（抗更新流程）

EA 高频更新会重置部分文件。检测：`status` 显示 `en==zh` 大幅下降或 gcl 痕迹归零 → 重新执行 `install`（幂等，翻译对新文件按内容重新推导）。无需重下载补丁。

## 约束与安全须知（agent 必读）

- 安装器会修改游戏目录文件；**只经安装器操作**，不要自行改写游戏文件。
- gcl 替换为字节等长替换，安装器内置引擎常量保护（小写词条/锚点校验）；若安装后游戏启动异常 → `uninstall` 并回报现象。
- 安装器旁会生成 `备份_<buildid>\` 与 `备份_tsv\`，**勿删除**（卸载依赖）。
- 不要把备份目录、任何游戏文件提交回本仓库。
