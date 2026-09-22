#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anymaker 简中汉化包 · 整合安装器（非官方社区补丁，自担风险，可完整卸载）。

原理：利用游戏自带但未启用的官方简中数据（languages_*.tsv 的 zh 列 + 简中字体）：
  ① 语言 TSV：en 列 := zh 列（游戏英文运行，显示中文）
  ② 字体：noto_sans_sc 覆盖 noto_sans_regular（英文语言原用拉丁字体，无中文字形）
  ③ 定义表 JSON：组件/物品/生物/僵尸 name 字段汉化（译名取自本机 TSV，生物为内置表）
  ④ game.gcl 内嵌英文串严格替换（英文界面的实际显示源；只碰前导 NUL 的独立常量、
     等长 NUL 填充、排除小写词条——避免引擎功能性常量受损）
翻译对全部从你本机游戏文件推导，本安装器不含游戏文本。
游戏更新后重新运行 install 即可（幂等）。用法：
  python 安装汉化.py install    # 安装/更新汉化
  python 安装汉化.py status     # 查看状态
  python 安装汉化.py uninstall  # 从备份完整还原
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import winreg

APP_ID = "4435340"
TSVS = ["languages.tsv", "languages_components.tsv", "languages_items.tsv",
        "languages_journal.tsv", "languages_manual.tsv"]
JSONS = ["vehicle_component_definitions.json", "inventory_definitions.json",
         "creature_definitions.json", "zombie_definitions.json"]
FONT_REG, FONT_SC = "noto_sans_regular.ttf", "noto_sans_sc_regular.ttf"

MANUAL = {'Bloom Intensity': '泛光强度', 'Bloom Threshold': '泛光阈值', 'Camera Shake': '镜头震动', 'Damage Vignette': '伤害暗角', 'Fog Blur': '模糊', 'Frame Rate': '帧率', 'Shadow Cascades': '阴影级联', 'Shadow Depth': '阴影深度', 'Shadow Texel Density': '阴影纹素密度', 'Ocean Magnitude': '海浪强度', 'FOV Override': '视场覆盖', 'Detach camera': '分离镜头', 'Reset Camera': '重置镜头', 'Handheld Intensity': '手持稳定强度', 'Handheld Motion': '手持晃动', 'Smooth Mouse Input': '平滑鼠标输入', 'Free Move Speed': '自由移速', 'Grass Subdiv': '草细分', 'Tree Subdiv': '树细分', 'Light Main': '主光', 'Light Sky': '天光', 'Light Back': '背光', 'Light Up': '顶光', 'Light Down': '底光', 'Light Volumes': '光照体积', 'Render First Person Head': '渲染第一人称头部', 'Time of Day': '昼夜', 'Enable Weather': '启用天气', 'Override Weather': '覆盖天气', 'Override Time': '覆盖时间', 'Weather Cloud': '云量', 'Weather Fog': '雾', 'Weather Rain': '降雨', 'Weather Wind': '风力', 'Weather Temp': '气温', 'Weather Offset X': '天气偏移X', 'Weather Offset Y': '天气偏移Y', 'Rain Factor': '雨量', 'Temperature Factor': '温度系数', 'Pause Clouds': '暂停云层', 'Pause Physics': '暂停物理', 'Step Physics': '单步物理', 'Color Palette': '颜色面板', 'First Person View': '第一人称', 'Player (First Person)': '玩家(第一人称)', 'Player (Third Person)': '玩家(第三人称)', 'UI Grid Size': '界面网格', 'Instant Item Actions': '即时物品动作', 'Item Names': '物品名', 'None selected': '未选择', 'File name': '文件名', 'Filter (space separated)': '过滤（空格分隔）', 'Join Local': '本地', 'Noise Octaves': '噪声倍频', 'Noise Persistence': '噪声持续度', 'Orientation Smoothing': '朝向平滑', 'Orientation Smoothing Factor': '朝向平滑系数', 'Train Wheel': '火车轮', 'GAME MENU': '游戏菜单', 'Save Game': '保存游戏', 'Load Game': '加载游戏', 'New Game': '新游戏', 'Multiplayer': '多人游戏', 'Options': '选项', 'Return to Game': '返回游戏', 'Exit to Main Menu': '退出至主菜单', 'Feedback': '反馈', 'Profile': '个人资料', 'Exit': '退出', 'Back': '返回', 'Yes': '是', 'No': '否'}
COMPACT = {'Exit to Main Menu': '回到主菜单', 'Save Game': '存档', 'Load Game': '读档', 'TOOLTIP DETAIL': '提示详细', 'SAVING GAME...': '保存中...', 'STEERING SENS.': '转向灵敏', 'Reset to Default': '恢复默认', 'MULTIPLAYER HOST': '建立主机', 'CLIENT DESTROYED': '客户端断开', 'PAUSE MENU TOGGLE': '暂停菜单', 'TOGGLE FREE MOVE': '自由移动', 'Upload to Workshop': '上传到工坊', 'This game is full.': '游戏已满员', 'Any unsaved progress will be lost': '未保存的进度将会丢失', 'Press key to rebind': '按键重新绑定', 'Press gamepad button to rebind': '按手柄键重新绑定', 'Press key/mouse button to rebind': '按键或鼠标重新绑定', 'Select Logic Node': '选逻辑节点', 'Select Logic Link Node': '选择逻辑链接点', 'Add Edge to Plate': '加板材边缘', 'Find and equip a Wheel.': '找个车轮装上。', 'CREATING WORKSHOP ITEM...': '创建工坊物品中...', 'UPDATING WORKSHOP ITEM...': '更新工坊物品中...', 'DELETING WORKSHOP ITEM...': '删除工坊物品中...', 'Multiplayer': '联机', 'Creative Dome:': '创造穹顶', "Open the inventory, hover the Canned Beans you picked up and press '###' to drop it on the floor.": "打开物品栏，选中罐装豆，按 '###' 丢到地上。", "Open the inventory, hover the Water you picked up and press '###' to drop it on the floor.": "打开物品栏，选中水，按 '###' 丢到地上。", 'Play as though always in the creative dome. Free building, unlimited use of items, no zombies, no loot and no player damage. Unleash your creativitiy without worrying about survival.': '如同在创意穹顶中游玩：自由建造，物品无限使用，无僵尸与战利品，玩家不会受伤。尽情创造，无需担心生存。', 'Press ### on keyboard or ### on gamepad to cancel': '按键盘 ### 或手柄 ### 取消', "Press '###' while hovering the door to open it.": "把光标移到门上按 '###' 打开。", 'insert ### at index ### of list ###': '将###插入列表###索引###', 'remove from list ### at index ###': '删除列表###索引###处', 'item at index ### of list ###': '列表###索引###项', 'create parameter ### named ###': '创建参数###命名###', 'create member ### named ###': '创建成员###命名###', 'create output ### named ###': '创建输出###命名###', 'create input ### named ###': '创建输入###命名###', 'create ### named ###': '创建###命名###', 'add ### to list ###': '###加入列表###', 'set ### to ###': '设###为###', 'clear list ###': '清空 ###', 'GAME MENU': '菜单', 'New Game': '开局', 'Open Inventory': '物品栏', 'Programmable 1': '可编程键1', 'WINDOW MODE': '窗口化', 'ROTATE LEFT': '左旋转', 'ROTATE RIGHT': '右旋转', 'ROTATE DOWN': '下旋转', 'ROTATE UP': '上旋转', 'DELETE SAVE': '删存档', 'Start Drag': '拖拽', 'Swap Items': '交换', 'AUTOSAVES': '存档', 'NO FILTER': '无过滤', 'RECEIVING': '接收中', 'BELT NODE': '皮带点', 'Move the Game Manual to the hotbar.': '把游戏手册移到快捷栏。', 'Save name too short.': '名字太短。', 'Remove Logic Link': '移除逻辑链', 'Save Clipboard': '存剪贴板', 'Load from File': '从文件读', 'NODE ### SPEED': '节点###速', 'LEFT ROLL NODE': '左横滚点', 'GEAR 1 RATIO': '1档比', 'GEAR 2 RATIO': '2档比', 'GEAR 3 RATIO': '3档比', 'GEAR 4 RATIO': '4档比', 'GEAR 5 RATIO': '5档比', 'GEAR 6 RATIO': '6档比', 'GEAR 7 RATIO': '7档比', 'GEAR 8 RATIO': '8档比', 'Last Played': '最近玩', 'OIL QUALITY': '油品', 'LIQUID NODE': '液体点', 'BREECH NODE': '后膛点', 'BLADE COUNT': '叶片数', 'FLOW FACTOR': '流量值', 'GAME BANNED': '被封禁', 'PAINT TOOLS': '喷漆', 'SAVE SCRIPT': '存脚本', 'LOAD SCRIPT': '读脚本', 'Rotate Left': '左旋转', 'Rotate Down': '下旋转', 'Rotate Up': '上旋转', 'Unlock Axis': '解轴向', 'Lock Axis': '锁轴向', 'Cancel Drag': '取消拖', 'Change Mode': '切模式', 'Apply Paint': '应用漆', 'Remove Node': '删节点', 'Remove Edge': '删边缘', 'Add Edge': '加边', 'Drag Zombie': '拖僵尸', 'VALUE ###': '值 ###', 'New Save': '新建', 'NEW GAME': '开局', 'DUNGEONS': '地牢', 'GAMEPLAY': '玩法', 'FOG BLUR': '雾化', 'OCCUPIED': '占用', 'Sandbox:': '沙盒:', 'Use on Component': '用于部件', 'TOOLBAR RIGHT': '右工具栏', 'TOOLBAR LEFT': '左工具栏', 'Toolbar Right': '工具栏右', 'Toolbar Left': '工具栏左', 'Enter Name...': '命名...', 'THROTTLE NODE': '油门节点', 'CONNECTING...': '连接中...', 'ITEM UNLOCKED': '已解锁', 'Use on Target': '对目标用', 'Hold to Equip': '按住装备', 'Hold to Cover': '按住覆盖', 'Regenerate': '重生成', 'NO GEARBOX': '无变速', 'TRACK NODE': '履带点', 'BRAKE NODE': '制动点', 'PITCH NODE': '俯仰点', 'DATA NODE': '数据点', 'FUEL NODE': '燃料点', 'OIL NODE': '油点', 'SET PETROL': '设汽油', 'SET AIR': '设气', 'SET OIL': '设油', 'TILT PITCH': '倾俯仰', 'TILT YAW': '倾航', 'GEAR COUNT': '齿轮数', 'ONBOARDING': '引导', 'Raise Item': '举物品', 'Lower Item': '放物品', 'Enter Seat': '入座', 'Exit Seat': '离座', 'EXIT SEAT': '离座', 'Climb Rope': '爬绳', 'Grab Rope': '抓绳', 'Close Menu': '关菜单', 'Open Menu': '开菜单', 'Enter Grid': '进网格', 'Exit Grid': '出网格', 'Clear Slot': '清槽位', 'Stop Paint': '停绘制', 'PROGRAM 1': '编程1', 'PROGRAM 2': '编程2', 'PROGRAM 3': '编程3', 'COVERED': '覆盖', 'POWERED': '通电', 'DAMAGED': '损坏', 'Reason:': '原因:', 'PEDAL L': '踏板L', 'PEDAL R': '踏板R', 'SLOT 1': '槽1', 'SLOT 2': '槽2', 'SLOT 3': '槽3', 'Programmable 2': '编程键2', 'Programmable 3': '编程键3', 'TRIGGER NODE': '触发点', 'COOLANT NODE': '冷却点', 'CLUTCH NODE': '离合点', 'FOOD & DRINK': '饮食', 'Save to File': '存到文件', 'Add Waypoint': '加路径点', 'SAVE GAME': '存游戏', 'LOAD SAVE': '读存档', 'GAME OVER': '结束', 'RECORDING': '录音中', 'SEAT POSE': '坐姿', 'Step Over': '单步过', 'Step Out': '步出', 'Step In': '步入', 'Free Move': '自由移', 'Load Ammo': '装弹', 'INVERT X': 'X反转', 'INVERT Y': 'Y反转', 'SERVER': '服务', 'CAMERA': '相机', 'LOADED': '上膛', 'WORKSHOP': '工坊', 'Pull Pin': '拔销', 'Add Logic Link': '加逻辑链', 'MAX PLAYERS': '最多人', 'Use on Self': '对己用', 'Enter Mount': '进挂点', 'Exit Mount': '出挂点', 'Packet loss': '丢包率', 'Career Mode:': '职业:', 'New Career': '新职业', 'LOADING...': '载入...', 'Paint Cell': '绘单元', 'PROFILE': '档案', 'RELOAD': '换弹', 'Reload': '换弹', 'L PEDAL SENS.': '左踏灵敏', 'R PEDAL SENS.': '右踏灵敏', 'INCAPACITATED': '已失能', 'Begin Edge': '起边缘', 'Cancel Plate': '取消板', 'Add Plate': '加板材', 'Creative Dome': '创造穹顶', 'Smoke Grenade': '烟雾弹', 'Dead Drop': '藏匿点', 'Duplicate Tool': '复制工具', 'Legal Agreement': '法律协议', 'Inventory': '物品栏', 'Journal': '日志', 'Vehicle': '载具', 'Player': '玩家', 'Window': '窗口', 'Building': '建造', 'Sandbox': '沙盒', 'Activate': '启动', 'Cancel': '取消', 'Delete': '删除', 'Rotate': '旋转', 'Climb': '攀爬', 'Height': '高度', 'CHARACTER': '角色', 'INTERACT': '互动', 'THROTTLE': '油门', 'TEMPERATURE': '温度', 'PRESSURE': '压力', 'INSIGNIA': '徽章', 'QUALITY': '画质', 'SHADOWS': '阴影', 'VEHICLE': '载具', 'CONTENT': '内容', 'PLAYERS': '玩家', 'OUTPUT': '输出', 'BREECH': '后膛', 'BUTTON': '按钮', 'RADIUS': '半径', 'Definition': '定义', 'Toggle': '切换', 'Off': '关', 'Eat': '吃'}
CREATURE_ZH = {'black_bear': '黑熊', 'bald_eagle': '白头海雕', 'opossum': '北美负鼠', 'alaska_mountain_goat': '阿拉斯加白山羊', 'alaska_reindeer': '阿拉斯加驯鹿', 'arctic_fox': '北极狐', 'bighorn_sheep': '大角羊', 'black_tailed_deer': '黑尾鹿', 'bobcat': '短尾猫', 'canada_goose': '加拿大雁', 'coyote': '郊狼', 'golden_eagle': '金雕', 'gray_fox': '灰狐', 'grizzly_bear': '灰熊', 'horned_puffin': '角嘴海雀', 'interior_wolf': '内陆狼', 'moose': '驼鹿', 'mountain_lion': '美洲狮', 'musk_ox': '麝牛', 'osprey': '鹗', 'peccary': '西貒', 'pileated_woodpecker': '北美黑啄木鸟', 'polar_bear': '北极熊', 'raccoon': '浣熊', 'red_fox': '赤狐', 'red_tailed_hawk': '红尾鵟', 'ringtail_cat': '环尾浣熊', 'roosevelt_elk': '罗斯福马鹿', 'spotted_owl': '斑点林鸮', 'turkey_vulture': '红头美洲鹫', 'white_shepherd': '白色牧羊犬', 'white_tailed_kite': '白尾鸢', 'monster_s': '怪物', 'monster_m': '怪物', 'monster_centipede': '蜈蚣', 'monster_burrower': '掘地者', 'monster_acid': '酸液怪', 'monster_crusher': '碾压者', 'monster_carrier': '携带者', 'monster_eel': '鳗怪', 'zombie_basic': '僵尸', 'zombie_fast': '僵尸', 'zombie_tank': '变异僵尸', 'zombie_acid': '变异僵尸', 'zombie_ambush': '变异僵尸', 'zombie_spawn': '变异僵尸'}
KNOWN_BUILDS = ["25422107", "25436400"]


def here():
    if getattr(sys, "frozen", False):  # PyInstaller 打包后取 exe 所在目录
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def game_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq game.exe"],
                         capture_output=True).stdout
    return b"game.exe" in out


def find_game():
    """注册表 SteamPath + libraryfolders.vdf 定位游戏目录与 appmanifest。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam, _ = winreg.QueryValueEx(k, "SteamPath")
    except OSError:
        sys.exit("注册表未找到 Steam，请手动确认安装路径。")
    libs = [steam]
    lf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    if os.path.isfile(lf):
        for m in re.finditer(r'"path"\s+"([^"]+)"', open(lf, encoding="utf-8", errors="ignore").read()):
            libs.append(m.group(1).replace("\\\\", "\\"))
    for lib in libs:
        acf = os.path.join(lib, "steamapps", f"appmanifest_{APP_ID}.acf")
        if os.path.isfile(acf):
            game = os.path.join(lib, "steamapps", "common", "Anymaker")
            if os.path.isdir(game):
                return game, acf
    sys.exit("未找到 Anymaker 安装（Steam 库列表：" + "; ".join(libs) + "）")


def buildid(acf):
    m = re.search(rb'"buildid"\s+"(\d+)"', open(acf, "rb").read())
    return m.group(1).decode() if m else "?"


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def tsv_rows(path):
    data = open(path, "rb").read()
    trailing = data.endswith(b"\n")
    lines = data.split(b"\n")
    if trailing:
        lines = lines[:-1]
    rows, crs = [], []
    for line in lines:
        if line.endswith(b"\r"):
            rows.append(line[:-1].split(b"\t")); crs.append(True)
        else:
            rows.append(line.split(b"\t")); crs.append(False)
    return rows, crs, trailing


def tsv_dump(path, rows, crs, trailing):
    out = b"\n".join(b"\t".join(r) + (b"\r" if f else b"") for r, f in zip(rows, crs))
    if trailing:
        out += b"\n"
    open(path, "wb").write(out)


def load_pairs_from_tsvs(rom):
    """en→zh 对照（en 取原始 en 列）。若 TSV 已被本包转换，改用首次安装备份。"""
    def pristine(path):
        rows, _, _ = tsv_rows(path)
        h = rows[0]
        ie, iz = h.index(b"en"), h.index(b"zh")
        nz = neq = 0
        for r in rows[1:]:
            if r[iz].strip():
                nz += 1
                if r[ie] == r[iz]:
                    neq += 1
        return nz == 0 or neq / nz < 0.5

    pairs = {}
    src_rom = rom
    converted = [n for n in TSVS if not pristine(os.path.join(rom, n))]
    if converted:
        bdir = os.path.join(here(), "备份_tsv")
        if all(os.path.isfile(os.path.join(bdir, n)) for n in TSVS):
            src_rom = bdir
            print("检测到 TSV 已汉化：翻译对照改用首次安装备份。")
        else:
            sys.exit(f"TSV 已汉化但缺少原始备份（{converted}）。\n"
                     "请先在 Steam 中『验证文件完整性』恢复官方文件后重试。")
    for n in TSVS:
        rows, _, _ = tsv_rows(os.path.join(src_rom, n))
        h = rows[0]
        ie, iz = h.index(b"en"), h.index(b"zh")
        for r in rows[1:]:
            en, zh = r[ie].decode(), r[iz].decode()
            if en.strip() and zh.strip() and any(c.isalpha() for c in en) and not en.islower():
                pairs[en.strip()] = zh.strip()
    return pairs


def load_override():
    out = {}
    path = os.path.join(here(), "润色词典.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.reader(fh):
                if len(r) >= 3 and r[0].strip() == "gcl" and r[1].strip() and r[2].strip():
                    out[r[1].strip()] = r[2].strip()
    return out


def load_override_name():
    out = {}
    path = os.path.join(here(), "润色词典.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.reader(fh):
                if len(r) >= 3 and r[0].strip() == "name" and r[1].strip() and r[2].strip():
                    out[r[1].strip()] = r[2].strip()
    return out


def step1_tsv(rom):
    for n in TSVS:
        p = os.path.join(rom, n)
        rows, crs, trailing = tsv_rows(p)
        h = rows[0]
        ie, iz, ncols = h.index(b"en"), h.index(b"zh"), len(h)
        changed = 0
        for r in rows[1:]:
            if len(r) != ncols:
                sys.exit(f"{n} 列数异常，中止。")
            if r[iz].strip() and r[ie] != r[iz]:
                r[ie] = r[iz]
                changed += 1
        tsv_dump(p, rows, crs, trailing)
        print(f"  {n}: en:=zh {changed} 行")


def step2_font(rom):
    fonts = os.path.join(rom, "fonts")
    shutil.copyfile(os.path.join(fonts, FONT_SC), os.path.join(fonts, FONT_REG))
    print(f"  字体: {FONT_REG} <- {FONT_SC}")


def step3_json(game, pairs_unused):
    data = os.path.join(game, "rom", "data")
    rom = os.path.join(game, "rom")
    def idmap(tsvname):
        rows, _, _ = tsv_rows(os.path.join(rom, tsvname))
        h = rows[0]
        return {r[h.index(b"id")].decode(): r[h.index(b"zh")].decode()
                for r in rows[1:] if r[h.index(b"zh")].strip()}
    ov = load_override_name()
    maps = {
        "vehicle_component_definitions.json": idmap("languages_components.tsv"),
        "inventory_definitions.json": idmap("languages_items.tsv"),
        "creature_definitions.json": dict(CREATURE_ZH),
        "zombie_definitions.json": dict(CREATURE_ZH),
    }
    for m in maps.values():
        m.update(ov)
    for name, mapping in maps.items():
        p = os.path.join(data, name)
        if not os.path.isfile(p):
            print(f"  跳过缺失文件: {name}")
            continue
        with open(p, encoding="utf-8") as fh:
            j = json.load(fh)
        hit = 0
        for e in j["definitions"]:
            zh = mapping.get(e.get("id", ""))
            if zh and e.get("name") != zh:
                e["name"] = zh
                hit += 1
        if hit:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(j, fh, ensure_ascii=False, indent=4)
                fh.write("\n")
        print(f"  {name}: name 汉化 {hit} 条")


def budget_at(data, start, end):
    if end >= len(data) or data[end] != 0:
        return 0
    ln = end - start
    if start >= 1 and data[start - 1] == 0:
        return ln
    if start >= 4 and data[start - 4:start] == ln.to_bytes(4, "little"):
        return ln
    return 0


def step4_gcl(game, pairs):
    merged = dict(pairs)
    merged.update(MANUAL)
    merged.update(COMPACT)
    merged.update(load_override())
    gcl = os.path.join(game, "bin", "game.gcl")
    raw = open(gcl, "rb").read()
    data = bytearray(raw)
    lookup = {en.encode(): zh.encode() for en, zh in merged.items() if zh.strip()}
    print(f"  gcl: 单遍扫描 81MB（{len(lookup)} 词条），请勿关闭窗口…")
    patched = skipped = 0
    i, n = 0, len(data)
    next_mile = n // 10
    while i < n:
        j = data.find(b"\x00", i)
        if j < 0:
            j = n
        if j > i:
            zb = lookup.get(bytes(data[i:j]))
            if zb is not None:
                if len(zb) <= j - i:
                    data[i:j] = zb + b"\x00" * (j - i - len(zb))
                    patched += 1
                else:
                    skipped += 1
        i = j + 1
        if i > next_mile:
            print(f"    … {i * 100 // n}%")
            next_mile += n // 10
    assert len(data) == len(raw), "gcl 大小变化！"
    open(gcl, "wb").write(bytes(data))
    print(f"  gcl: 替换 {patched} 词条（译超长跳过 {skipped}），大小不变")


def backup(game, bid):
    bdir = os.path.join(here(), f"备份_{bid}")
    if os.path.isdir(bdir):
        print(f"备份已存在（保留原始首份）: {bdir}")
        return
    os.makedirs(bdir)
    rom, fonts = os.path.join(game, "rom"), os.path.join(game, "rom", "fonts")
    tsvdir = os.path.join(here(), "备份_tsv")
    os.makedirs(tsvdir, exist_ok=True)
    for n in TSVS:
        shutil.copy2(os.path.join(rom, n), os.path.join(bdir, n))
        dst = os.path.join(tsvdir, n)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(rom, n), dst)  # 纯净 TSV 备份（翻译对照源）
    shutil.copy2(os.path.join(fonts, FONT_REG), os.path.join(bdir, FONT_REG))
    for n in JSONS:
        p = os.path.join(rom, "data", n)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(bdir, n))
    shutil.copy2(os.path.join(game, "bin", "game.gcl"), os.path.join(bdir, "game.gcl"))
    with open(os.path.join(bdir, "SHA256SUMS.txt"), "w", encoding="utf-8") as fh:
        for f in os.listdir(bdir):
            fh.write(f"{sha256(os.path.join(bdir, f))}  {f}\n")
    print(f"已备份原始文件 → {bdir}")


class _Tee:
    """stdout 同步写入安装日志，便于事后排查（控制台一闪而过也有据可查）。"""
    def __init__(self, path):
        import datetime
        self.fh = open(path, "a", encoding="utf-8")
        self.fh.write(f"\n==== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ====\n")
    def __enter__(self):
        outer = self
        class W:
            def write(s, t):
                outer.old.write(t)
                outer.fh.write(t)
            def flush(s):
                outer.old.flush()
                outer.fh.flush()
        self.old = sys.stdout
        sys.stdout = W()
        return self
    def __exit__(self, *a):
        sys.stdout = self.old
        self.fh.close()


def cmd_install():
    with _Tee(os.path.join(here(), "安装日志.txt")):
        _do_install()


def _do_install():
    if game_running():
        sys.exit("游戏正在运行，请先退出。")
    game, acf = find_game()
    bid = buildid(acf)
    print(f"游戏目录: {game}\nbuildid: {bid}" +
          ("" if bid in KNOWN_BUILDS else "\n⚠ 未测试过的版本：脚本按内容推导应兼容，装后请验证；异常先 uninstall。"))
    pairs = load_pairs_from_tsvs(os.path.join(game, "rom"))
    backup(game, bid)
    print("① 语言 TSV en:=zh")
    step1_tsv(os.path.join(game, "rom"))
    print("② 字体替换")
    step2_font(os.path.join(game, "rom"))
    print("③ JSON name 汉化")
    step3_json(game, pairs)
    print("④ gcl 内嵌串替换")
    step4_gcl(game, pairs)
    print()
    print("=" * 46)
    print("安装完成！启动游戏验证中文显示。")
    print("若界面仍为英文或游戏异常：把 exe 旁的 安装日志.txt")
    print("发给维护者，或选 3 卸载还原。")
    print("=" * 46)


def cmd_status():
    game, acf = find_game()
    bid = buildid(acf)
    print("buildid:", bid)
    rom = os.path.join(game, "rom")
    for n in TSVS:
        rows, _, _ = tsv_rows(os.path.join(rom, n))
        h = rows[0]
        ie, iz = h.index(b"en"), h.index(b"zh")
        nz = neq = 0
        for r in rows[1:]:
            if r[iz].strip():
                nz += 1
                neq += (r[ie] == r[iz])
        print(f"  {n:28} en==zh {neq}/{nz}")
    gcl = open(os.path.join(game, "bin", "game.gcl"), "rb").read()
    print("  gcl 汉化痕迹:", sum(gcl.count(w.encode()) for w in ["返回游戏", "存档", "开局"]))
    print("  字体为 SC:", sha256(os.path.join(rom, "fonts", FONT_REG)) ==
          sha256(os.path.join(rom, "fonts", FONT_SC)))
    print("  备份:", [d for d in os.listdir(here()) if d.startswith("备份_")])


def cmd_uninstall():
    with _Tee(os.path.join(here(), "安装日志.txt")):
        _do_uninstall()


def _do_uninstall():
    if game_running():
        sys.exit("游戏正在运行，请先退出。")
    game, acf = find_game()
    bid = buildid(acf)
    bdir = os.path.join(here(), f"备份_{bid}")
    if not os.path.isdir(bdir):
        sys.exit(f"当前 buildid {bid} 无备份。请用 Steam『验证文件完整性』还原。")
    rom, fonts = os.path.join(game, "rom"), os.path.join(game, "rom", "fonts")
    for n in TSVS + [FONT_REG] + JSONS:
        dst = os.path.join(fonts, n) if n == FONT_REG else (
            os.path.join(rom, "data", n) if n in JSONS else os.path.join(rom, n))
        if os.path.isfile(os.path.join(bdir, n)):
            shutil.copy2(os.path.join(bdir, n), dst)
            print("还原:", n)
    shutil.copy2(os.path.join(bdir, "game.gcl"), os.path.join(game, "bin", "game.gcl"))
    print("还原: game.gcl")
    print("卸载完成。如仍异常请用 Steam 验证文件完整性。")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        {"install": cmd_install, "status": cmd_status, "uninstall": cmd_uninstall}.get(
            cmd, lambda: print(__doc__))()
    else:
        # 双击运行（无参数）→ 交互菜单；非交互环境（管道）默认显示状态
        print("==== Anymaker 简中汉化包 ====")
        print("  1) 安装 / 更新汉化")
        print("  2) 查看状态")
        print("  3) 卸载，还原官方文件")
        print("  0) 退出")
        try:
            choice = input("请选择 [1/2/3/0]: ").strip()
        except EOFError:
            choice = "2"
        {"1": cmd_install, "2": cmd_status, "3": cmd_uninstall}.get(choice, lambda: None)()
