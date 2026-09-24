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
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import winreg

APP_ID = "4435340"
TSVS = ["languages.tsv", "languages_components.tsv", "languages_items.tsv",
        "languages_journal.tsv", "languages_manual.tsv"]
# 游戏 25480554 起新增的描述表（官方自带 zh 全量译文）；存在才处理，旧版游戏自动跳过
TSVS_OPTIONAL = ["languages_component_descriptions.tsv", "languages_item_descriptions.tsv"]
JSONS = ["vehicle_component_definitions.json", "inventory_definitions.json",
         "creature_definitions.json", "zombie_definitions.json"]
FONT_REG, FONT_SC = "noto_sans_regular.ttf", "noto_sans_sc_regular.ttf"

MANUAL = {'Bloom Intensity': '泛光强度', 'Bloom Threshold': '泛光阈值', 'Camera Shake': '镜头震动', 'Damage Vignette': '伤害暗角', 'Fog Blur': '模糊', 'Frame Rate': '帧率', 'Shadow Cascades': '阴影级联', 'Shadow Depth': '阴影深度', 'Shadow Texel Density': '阴影纹素密度', 'Ocean Magnitude': '海浪强度', 'FOV Override': '视场覆盖', 'Detach camera': '分离镜头', 'Reset Camera': '重置镜头', 'Handheld Intensity': '手持稳定强度', 'Handheld Motion': '手持晃动', 'Smooth Mouse Input': '平滑鼠标输入', 'Free Move Speed': '自由移速', 'Grass Subdiv': '草细分', 'Tree Subdiv': '树细分', 'Light Main': '主光', 'Light Sky': '天光', 'Light Back': '背光', 'Light Up': '顶光', 'Light Down': '底光', 'Light Volumes': '光照体积', 'Render First Person Head': '渲染第一人称头部', 'Time of Day': '昼夜', 'Enable Weather': '启用天气', 'Override Weather': '覆盖天气', 'Override Time': '覆盖时间', 'Weather Cloud': '云量', 'Weather Fog': '雾', 'Weather Rain': '降雨', 'Weather Wind': '风力', 'Weather Temp': '气温', 'Weather Offset X': '天气偏移X', 'Weather Offset Y': '天气偏移Y', 'Rain Factor': '雨量', 'Temperature Factor': '温度系数', 'Pause Clouds': '暂停云层', 'Pause Physics': '暂停物理', 'Step Physics': '单步物理', 'Color Palette': '颜色面板', 'First Person View': '第一人称', 'Player (First Person)': '玩家(第一人称)', 'Player (Third Person)': '玩家(第三人称)', 'UI Grid Size': '界面网格', 'Instant Item Actions': '即时物品动作', 'Item Names': '物品名', 'None selected': '未选择', 'File name': '文件名', 'Filter (space separated)': '过滤（空格分隔）', 'Join Local': '本地', 'Noise Octaves': '噪声倍频', 'Noise Persistence': '噪声持续度', 'Orientation Smoothing': '朝向平滑', 'Orientation Smoothing Factor': '朝向平滑系数', 'Train Wheel': '火车轮', 'GAME MENU': '游戏菜单', 'Save Game': '保存游戏', 'Load Game': '加载游戏', 'New Game': '新游戏', 'Multiplayer': '多人游戏', 'Options': '选项', 'Return to Game': '返回游戏', 'Exit to Main Menu': '退出至主菜单', 'Feedback': '反馈', 'Profile': '个人资料', 'Exit': '退出', 'Back': '返回', 'Yes': '是', 'No': '否'}
COMPACT = {'Exit to Main Menu': '回到主菜单', 'Save Game': '存档', 'Load Game': '读档', 'TOOLTIP DETAIL': '提示详细', 'SAVING GAME...': '保存中...', 'STEERING SENS.': '转向灵敏', 'Reset to Default': '恢复默认', 'MULTIPLAYER HOST': '建立主机', 'CLIENT DESTROYED': '客户端断开', 'PAUSE MENU TOGGLE': '暂停菜单', 'TOGGLE FREE MOVE': '自由移动', 'Upload to Workshop': '上传到工坊', 'This game is full.': '游戏已满员', 'Any unsaved progress will be lost': '未保存的进度将会丢失', 'Press key to rebind': '按键重新绑定', 'Press gamepad button to rebind': '按手柄键重新绑定', 'Press key/mouse button to rebind': '按键或鼠标重新绑定', 'Select Logic Node': '选逻辑节点', 'Select Logic Link Node': '选择逻辑链接点', 'Add Edge to Plate': '加板材边缘', 'Find and equip a Wheel.': '找个车轮装上。', 'CREATING WORKSHOP ITEM...': '创建工坊物品中...', 'UPDATING WORKSHOP ITEM...': '更新工坊物品中...', 'DELETING WORKSHOP ITEM...': '删除工坊物品中...', 'Multiplayer': '联机', 'Creative Dome:': '创造穹顶', "Open the inventory, hover the Canned Beans you picked up and press '###' to drop it on the floor.": "打开物品栏，选中罐装豆，按 '###' 丢到地上。", "Open the inventory, hover the Water you picked up and press '###' to drop it on the floor.": "打开物品栏，选中水，按 '###' 丢到地上。", 'Play as though always in the creative dome. Free building, unlimited use of items, no zombies, no loot and no player damage. Unleash your creativitiy without worrying about survival.': '如同在创意穹顶中游玩：自由建造，物品无限使用，无僵尸与战利品，玩家不会受伤。尽情创造，无需担心生存。', 'Press ### on keyboard or ### on gamepad to cancel': '按键盘 ### 或手柄 ### 取消', "Press '###' while hovering the door to open it.": "把光标移到门上按 '###' 打开。", 'insert ### at index ### of list ###': '将###插入列表###索引###', 'remove from list ### at index ###': '删除列表###索引###处', 'item at index ### of list ###': '列表###索引###项', 'create parameter ### named ###': '创建参数###命名###', 'create member ### named ###': '创建成员###命名###', 'create output ### named ###': '创建输出###命名###', 'create input ### named ###': '创建输入###命名###', 'create ### named ###': '创建###命名###', 'add ### to list ###': '###加入列表###', 'set ### to ###': '设###为###', 'clear list ###': '清空 ###', 'GAME MENU': '菜单', 'New Game': '开局', 'Open Inventory': '物品栏', 'Programmable 1': '可编程键1', 'WINDOW MODE': '窗口化', 'ROTATE LEFT': '左旋转', 'ROTATE RIGHT': '右旋转', 'ROTATE DOWN': '下旋转', 'ROTATE UP': '上旋转', 'DELETE SAVE': '删存档', 'Start Drag': '拖拽', 'Swap Items': '交换', 'AUTOSAVES': '存档', 'NO FILTER': '无过滤', 'RECEIVING': '接收中', 'BELT NODE': '皮带点', 'Move the Game Manual to the hotbar.': '把游戏手册移到快捷栏。', 'Save name too short.': '名字太短。', 'Remove Logic Link': '移除逻辑链', 'Save Clipboard': '存剪贴板', 'Load from File': '从文件读', 'NODE ### SPEED': '节点###速', 'LEFT ROLL NODE': '左横滚点', 'GEAR 1 RATIO': '1档比', 'GEAR 2 RATIO': '2档比', 'GEAR 3 RATIO': '3档比', 'GEAR 4 RATIO': '4档比', 'GEAR 5 RATIO': '5档比', 'GEAR 6 RATIO': '6档比', 'GEAR 7 RATIO': '7档比', 'GEAR 8 RATIO': '8档比', 'Last Played': '最近玩', 'OIL QUALITY': '油品', 'LIQUID NODE': '液体点', 'BREECH NODE': '后膛点', 'BLADE COUNT': '叶片数', 'FLOW FACTOR': '流量值', 'GAME BANNED': '被封禁', 'PAINT TOOLS': '喷漆', 'SAVE SCRIPT': '存脚本', 'LOAD SCRIPT': '读脚本', 'Rotate Left': '左旋转', 'Rotate Down': '下旋转', 'Rotate Up': '上旋转', 'Unlock Axis': '解轴向', 'Lock Axis': '锁轴向', 'Cancel Drag': '取消拖', 'Change Mode': '切模式', 'Apply Paint': '应用漆', 'Remove Node': '删节点', 'Remove Edge': '删边缘', 'Add Edge': '加边', 'Drag Zombie': '拖僵尸', 'VALUE ###': '值 ###', 'New Save': '新建', 'NEW GAME': '开局', 'DUNGEONS': '地牢', 'GAMEPLAY': '玩法', 'FOG BLUR': '雾化', 'OCCUPIED': '占用', 'Sandbox:': '沙盒:', 'Use on Component': '用于部件', 'TOOLBAR RIGHT': '右工具栏', 'TOOLBAR LEFT': '左工具栏', 'Toolbar Right': '工具栏右', 'Toolbar Left': '工具栏左', 'Enter Name...': '命名...', 'THROTTLE NODE': '油门节点', 'CONNECTING...': '连接中...', 'ITEM UNLOCKED': '已解锁', 'Use on Target': '对目标用', 'Hold to Equip': '按住装备', 'Hold to Cover': '按住覆盖', 'Regenerate': '重生成', 'NO GEARBOX': '无变速', 'TRACK NODE': '履带点', 'BRAKE NODE': '制动点', 'PITCH NODE': '俯仰点', 'DATA NODE': '数据点', 'FUEL NODE': '燃料点', 'OIL NODE': '油点', 'SET PETROL': '设汽油', 'SET AIR': '设气', 'SET OIL': '设油', 'TILT PITCH': '倾俯仰', 'TILT YAW': '倾航', 'GEAR COUNT': '齿轮数', 'ONBOARDING': '引导', 'Raise Item': '举物品', 'Lower Item': '放物品', 'Enter Seat': '入座', 'Exit Seat': '离座', 'EXIT SEAT': '离座', 'Climb Rope': '爬绳', 'Grab Rope': '抓绳', 'Close Menu': '关菜单', 'Open Menu': '开菜单', 'Enter Grid': '进网格', 'Exit Grid': '出网格', 'Clear Slot': '清槽位', 'Stop Paint': '停绘制', 'PROGRAM 1': '编程1', 'PROGRAM 2': '编程2', 'PROGRAM 3': '编程3', 'COVERED': '覆盖', 'POWERED': '通电', 'DAMAGED': '损坏', 'Reason:': '原因:', 'PEDAL L': '踏板L', 'PEDAL R': '踏板R', 'SLOT 1': '槽1', 'SLOT 2': '槽2', 'SLOT 3': '槽3', 'Programmable 2': '编程键2', 'Programmable 3': '编程键3', 'TRIGGER NODE': '触发点', 'COOLANT NODE': '冷却点', 'CLUTCH NODE': '离合点', 'FOOD & DRINK': '饮食', 'Save to File': '存到文件', 'Add Waypoint': '加路径点', 'SAVE GAME': '存游戏', 'LOAD SAVE': '读存档', 'GAME OVER': '结束', 'RECORDING': '录音中', 'SEAT POSE': '坐姿', 'Step Over': '单步过', 'Step Out': '步出', 'Step In': '步入', 'Free Move': '自由移', 'Load Ammo': '装弹', 'INVERT X': 'X反转', 'INVERT Y': 'Y反转', 'SERVER': '服务', 'CAMERA': '相机', 'LOADED': '上膛', 'WORKSHOP': '工坊', 'Pull Pin': '拔销', 'Add Logic Link': '加逻辑链', 'MAX PLAYERS': '最多人', 'Use on Self': '对己用', 'Enter Mount': '进挂点', 'Exit Mount': '出挂点', 'Packet loss': '丢包率', 'Career Mode:': '职业:', 'New Career': '新职业', 'LOADING...': '载入...', 'Paint Cell': '绘单元', 'PROFILE': '档案', 'RELOAD': '换弹', 'Reload': '换弹', 'L PEDAL SENS.': '左踏灵敏', 'R PEDAL SENS.': '右踏灵敏', 'INCAPACITATED': '已失能', 'Begin Edge': '起边缘', 'Cancel Plate': '取消板', 'Add Plate': '加板材', 'Creative Dome': '创造穹顶', 'Smoke Grenade': '烟雾弹', 'Dead Drop': '藏匿点', 'Duplicate Tool': '复制工具', 'Legal Agreement': '法律协议', 'Inventory': '物品栏', 'Journal': '日志', 'Vehicle': '载具', 'Player': '玩家', 'Window': '窗口', 'Building': '建造', 'Sandbox': '沙盒', 'Activate': '启动', 'Cancel': '取消', 'Delete': '删除', 'Rotate': '旋转', 'Climb': '攀爬', 'Height': '高度', 'CHARACTER': '角色', 'INTERACT': '互动', 'THROTTLE': '油门', 'TEMPERATURE': '温度', 'PRESSURE': '压力', 'INSIGNIA': '徽章', 'QUALITY': '画质', 'SHADOWS': '阴影', 'VEHICLE': '载具', 'CONTENT': '内容', 'PLAYERS': '玩家', 'OUTPUT': '输出', 'BREECH': '后膛', 'BUTTON': '按钮', 'RADIUS': '半径', 'Definition': '定义', 'Toggle': '切换', 'Off': '关', 'Eat': '吃'}
CREATURE_ZH = {'black_bear': '黑熊', 'bald_eagle': '白头海雕', 'opossum': '北美负鼠', 'alaska_mountain_goat': '阿拉斯加白山羊', 'alaska_reindeer': '阿拉斯加驯鹿', 'arctic_fox': '北极狐', 'bighorn_sheep': '大角羊', 'black_tailed_deer': '黑尾鹿', 'bobcat': '短尾猫', 'canada_goose': '加拿大雁', 'coyote': '郊狼', 'golden_eagle': '金雕', 'gray_fox': '灰狐', 'grizzly_bear': '灰熊', 'horned_puffin': '角嘴海雀', 'interior_wolf': '内陆狼', 'moose': '驼鹿', 'mountain_lion': '美洲狮', 'musk_ox': '麝牛', 'osprey': '鹗', 'peccary': '西貒', 'pileated_woodpecker': '北美黑啄木鸟', 'polar_bear': '北极熊', 'raccoon': '浣熊', 'red_fox': '赤狐', 'red_tailed_hawk': '红尾鵟', 'ringtail_cat': '环尾浣熊', 'roosevelt_elk': '罗斯福马鹿', 'spotted_owl': '斑点林鸮', 'turkey_vulture': '红头美洲鹫', 'white_shepherd': '白色牧羊犬', 'white_tailed_kite': '白尾鸢', 'monster_s': '怪物', 'monster_m': '怪物', 'monster_centipede': '蜈蚣', 'monster_burrower': '掘地者', 'monster_acid': '酸液怪', 'monster_crusher': '碾压者', 'monster_carrier': '携带者', 'monster_eel': '鳗怪', 'zombie_basic': '僵尸', 'zombie_fast': '僵尸', 'zombie_tank': '变异僵尸', 'zombie_acid': '变异僵尸', 'zombie_ambush': '变异僵尸', 'zombie_spawn': '变异僵尸'}
KNOWN_BUILDS = ["25422107", "25436400", "25480554"]
VERSION = "1.1.1"
UPDATE_JSON_URL = "https://raw.githubusercontent.com/EC90/anymaker-zh-patch/main/update.json"
GITHUB_RELEASES = "https://github.com/EC90/anymaker-zh-patch/releases/latest"
DESCS = {'Storage 6x6.': '储物 6×6。', 'Storage 5x8.': '储物 5×8。', 'Storage 5x10.': '储物 5×10。', 'Output = -1 x input.': '输出 = 输入 × -1。', 'Rain resistance 12%.': '防雨 12%。', 'Restores 50% thirst.': '恢复 50% 水分。', 'Restores 50% hunger.': '恢复 50% 饱食度。', 'Storage grid 8 by 14.': '储物格 8×14。', 'Storage grid 8 by 22.': '储物格 8×22。', 'Fits a knife holster.': '可装匕首刀鞘。', 'Fits a machete sheath.': '可装砍刀刀鞘。', 'Joins four small gas pipe nodes.': '连接四个小号气管节点。', 'Joins four large gas pipe nodes.': '连接四个大号气管节点。', 'Joins three small gas pipe nodes.': '连接三个小号气管节点。', 'Output = absolute value of input.': '输出 = 输入的绝对值。', 'Joins three large gas pipe nodes.': '连接三个大号气管节点。', 'Joins four small liquid pipe nodes.': '连接四个小号液管节点。', 'Output = A + B, limited to -1 to 1.': '输出 = A + B，限制在 -1 到 1。', 'Joins four large liquid pipe nodes.': '连接四个大号液管节点。', 'Joins three small liquid pipe nodes.': '连接三个小号液管节点。', 'Joins three large liquid pipe nodes.': '连接三个大号液管节点。', 'Insulation 1 C. Rain resistance 20%.': '保温 1 C，防雨 20%。', 'Insulation 1 C. Rain resistance 12%.': '保温 1 C，防雨 12%。', 'Insulation 5 C. Rain resistance 60%.': '保温 5 C，防雨 60%。', 'Insulation 5 C. Rain resistance 80%.': '保温 5 C，防雨 80%。', 'Insulation 5 C. Rain resistance 40%.': '保温 5 C，防雨 40%。', 'Restores 50% hunger. No tool needed.': '恢复 50% 饱食度，无需工具。', 'Two handed. Knocks fixed props loose.': '双手持用，可把固定道具敲松。', 'Output = the larger of inputs A and B.': '输出 = A、B 输入中的较大者。', 'Insulation 2.3 C. Rain resistance 20%.': '保温 2.3 C，防雨 20%。', 'Insulation 1.7 C. Rain resistance 40%.': '保温 1.7 C，防雨 40%。', 'Insulation 2.3 C. Rain resistance 28%.': '保温 2.3 C，防雨 28%。', 'Insulation 1.7 C. Rain resistance 12%.': '保温 1.7 C，防雨 12%。', 'Insulation 2.3 C. Rain resistance 40%.': '保温 2.3 C，防雨 40%。', 'Insulation 1.7 C. Rain resistance 28%.': '保温 1.7 C，防雨 28%。', 'Insulation 6.7 C. Rain resistance 80%.': '保温 6.7 C，防雨 80%。', 'Insulation 3.3 C. Rain resistance 20%.': '保温 3.3 C，防雨 20%。', 'Insulation 6.7 C. Rain resistance 60%.': '保温 6.7 C，防雨 60%。', 'Insulation 3.3 C. Rain resistance 40%.': '保温 3.3 C，防雨 40%。', 'Insulation 1.3 C. Rain resistance 12%.': '保温 1.3 C，防雨 12%。', 'Output = the smaller of inputs A and B.': '输出 = A、B 输入中的较小者。', '30 rounds. Loads the revolver directly.': '30 发，直接为左轮装弹。', 'Fits the ir missile launcher. One shot.': '适配红外导弹发射器，单发。', 'Fits a top rail. Iron sight, no battery.': '装于顶部导轨，机械瞄具，无需电池。', 'Fits the visor mount on the safety helmet.': '装于安全帽的护目镜座。', 'Joins a small gas pipe node to a large one.': '连接小号与大号气管节点。', 'Momentary. Mechanical link reads 1 while held.': '瞬时式：按住期间机械连杆读数为 1。', 'Joins a small liquid pipe node to a large one.': '连接小号与大号液管节点。', 'Outputs altitude in m. Connect with data port.': '输出海拔（米），经数据端口连接。', 'Fits an air filter component of the same size.': '适配同尺寸的空气滤清器组件。', 'Hold and use to raise. 8 degree field of view.': '按住使用升起，视场角 8 度。', 'Marks the spawn location. Needle points north.': '标记出生点位置，指针指向北。', 'Deflects up to 20 degrees from mechanical link.': '随机械连杆偏转至多 20 度。', 'Holds 3 drinks. Each drink restores 50% thirst.': '容纳 3 份饮品，每份恢复 50% 水分。', 'Fits a battery component of the same size. 4 kWh.': '适配同尺寸电池组件，容量 4 kWh。', 'Fits a battery component of the same size. 2 kWh.': '适配同尺寸电池组件，容量 2 kWh。', 'Straight pipe fitting, small gas node at each end.': '直管接头，两端为小号气管节点。', 'Straight pipe fitting, large gas node at each end.': '直管接头，两端为大号气管节点。', 'Clears infection and restores 20% blood. Self only.': '治愈感染并恢复 20% 血量，仅限本人使用。', 'Storage 8x5. Cannot be stored in another container.': '储物 8×5，无法放入其它容器。', 'Joins two data link points. Extends or turns a link.': '连接两个数据链路点，可延伸或转折链路。', 'Takes a battery cell, lasts about 50 min. 60 m beam.': '使用一节电池，续航约 50 分钟，射程 60 米。', 'Storage 8x10. Cannot be stored in another container.': '储物 8×10，无法放入其它容器。', 'Storage 8x20. Cannot be stored in another container.': '储物 8×20，无法放入其它容器。', 'Fits a signal detector. Tunes it to one transponder.': '适配信号探测器，将其调谐到一个应答器。', 'Straight pipe fitting, small liquid node at each end.': '直管接头，两端为小号液管节点。', 'Ballast, about 4 kg per voxel. Stretches in all axes.': '压载物，每体素约 4 kg，可沿各轴拉伸。', 'Straight pipe fitting, large liquid node at each end.': '直管接头，两端为大号液管节点。', 'Joins two electric link points. Extends or turns a link.': '连接两个电力链路点，可延伸或转折链路。', 'Holds a spare car, van, quadbike, 4x4 or truck wheel item.': '容纳一个备用车轮（轿车/厢式车/四轮摩托/四驱车/卡车）。', 'Mounts a safety visor. Insulation 1 C. Rain resistance 20%.': '可安装安全护目镜，保温 1 C，防雨 20%。', 'Fits a top rail. 6 degree field of view. No battery needed.': '装于顶部导轨，视场角 6 度，无需电池。', '30 rounds. Loads the 45 pistol magazine and smg45 magazine.': '30 发，为 45 手枪弹匣与 SMG45 弹匣装弹。', 'Driven by torque face. Produces thrust only while submerged.': '由扭矩面驱动，仅在水下产生推力。', 'Stops bleeding. Hold to apply to yourself or another player.': '止血，按住对自己或他人使用。', 'Fits a top rail. 10 degree field of view. No battery needed.': '装于顶部导轨，视场角 10 度，无需电池。', 'Latching. Each press toggles mechanical link between 0 and 1.': '自锁式，每按一次在 0 与 1 之间切换机械连杆。', 'Occupies the body and legs slots. Insulation 8.3 C. Rainproof.': '占用身体与腿部槽位，保温 8.3 C，防雨。', 'Restores 50% blood. Hold to apply to yourself or another player.': '恢复 50% 血量，按住对自己或他人使用。', 'Bolt action, 308. Takes the sniper magazine only. Top rail only.': '栓动，.308，仅用狙击步枪弹匣，仅顶部导轨。', 'Draws outside air into a small gas pipe. Fits an air filter item.': '将外部空气吸入小号气管，可装空气滤清器物品。', 'Draws outside air into a large gas pipe. Fits an air filter item.': '将外部空气吸入大号气管，可装空气滤清器物品。', 'Splits one mechanical link into two. Both outputs equal the input.': '把一路机械连杆分成两路，两路输出都等于输入。', 'Carries one long gun on the back. Cannot be stored in a container.': '背负一把长枪，无法放入其它容器。', 'Passes a mechanical link through unchanged. Extends or turns a link.': '机械连杆原样传递，可延伸或转折链路。', 'Output = input x scale, limited to -1 to 1. Scale set in properties.': '输出 = 输入 × 倍率，限制在 -1 到 1，倍率在属性中设置。', 'Automatic, 900 rpm, 9mm. Takes the smg magazine only. Top rail only.': '全自动，900 发/分，9mm，仅用冲锋枪弹匣，仅顶部导轨。', 'Automatic, 800 rpm, 9mm. Takes the smg magazine only. Top rail only.': '全自动，800 发/分，9mm，仅用冲锋枪弹匣，仅顶部导轨。', 'Automatic, 700 rpm, 9mm. Takes the smg magazine only. Top rail only.': '全自动，700 发/分，9mm，仅用冲锋枪弹匣，仅顶部导轨。', 'Lights when mechanical link reads 1 or illuminated data input is set.': '机械连杆读数为 1 或照明数据输入置位时点亮。', 'Outputs rps: rotation rate about its up axis. Connect with data port.': '输出转速（rps）：绕自身上轴的旋转速率，经数据端口连接。', 'Output = input + offset, limited to -1 to 1. Offset set in properties.': '输出 = 输入 + 偏移，限制在 -1 到 1，偏移在属性中设置。', 'Inline on a small gas pipe. Outputs temperature in C on its data port.': '串接于小号气管，经数据端口输出温度（C）。', 'Occupies the body and legs slots. Insulation 5 C. Rain resistance 60%.': '占用身体与腿部槽位，保温 5 C，防雨 60%。', 'Automatic, 1100 rpm, 762. Takes the mg 3 magazine only. Top rail only.': '全自动，1100 发/分，7.62，仅用 MG3 弹匣，仅顶部导轨。', 'Fits a top rail. Reticle needs a battery cell and must be switched on.': '装于顶部导轨，分划需电池并需开启。', 'Swipe on a keycard reader. Opens only the reader with the matching key.': '在读卡器上刷卡，只打开密钥匹配的读卡器。', 'Occupies the body and legs slots. Insulation 6.7 C. Rain resistance 80%.': '占用身体与腿部槽位，保温 6.7 C，防雨 80%。', 'Occupies the feet and legs slots. Insulation 3.3 C. Rain resistance 80%.': '占用足部与腿部槽位，保温 3.3 C，防雨 80%。', '20 rounds. Loads the sniper magazine and the bolt action rifle directly.': '20 发，直接为狙击步枪弹匣与栓动步枪装弹。', 'Opens a small gas pipe to the atmosphere. Vents exhaust and draws in air.': '使小号气管通向大气，排出废气并吸入空气。', 'Inline on a small liquid pipe. Outputs temperature in C on its data port.': '串接于小号液管，经数据端口输出温度（C）。', 'Opens a large gas pipe to the atmosphere. Vents exhaust and draws in air.': '使大号气管通向大气，排出废气并吸入空气。', 'Ignite to burn for 20 min, 64 m radius. Can be thrown. Cannot be put out.': '点燃后燃烧 20 分钟，半径 64 米，可投掷，无法扑灭。', 'Hold primary on a damaged component or cracked window to fully repair it.': '对受损组件或破裂车窗按住主键即可完全修复。', 'Dead-end tap on a small gas pipe. Outputs pressure in Pa on its data port.': '小号气管的末端取样口，经数据端口输出压力（Pa）。', 'Grab to hang on. Mechanical link and active data output read 1 while held.': '抓住即可悬挂，握持期间机械连杆与激活数据输出读数为 1。', 'Converts exhaust back into air, 40% of contents per second. Fits gas ports.': '把废气回转为空气，每秒转化存量的 40%，适配气端口。', 'Storage 1x1. Mounts on the pouch point of a helmet or any attachment point.': '储物 1×1，装于头盔腰包点或任意挂载点。', 'Semi-automatic, 45. Takes the 45 pistol magazine only. No attachment slots.': '半自动，.45，仅用 45 手枪弹匣，无挂载槽位。', 'Automatic, 750 rpm, 762. Takes the gpmg magazine only. No attachment slots.': '全自动，750 发/分，7.62，仅用通用机枪弹匣，无挂载槽位。', 'Fits an attachment point. Takes a battery cell, lasts about 1 h. 60 m beam.': '装于挂载点，使用一节电池，续航约 1 小时，射程 60 米。', 'Semi-automatic, 9mm. Takes the hp pistol magazine only. No attachment slots.': '半自动，9mm，仅用 HP 手枪弹匣，无挂载槽位。', 'Semi-automatic, 9mm. Takes the m9 pistol magazine only. No attachment slots.': '半自动，9mm，仅用 M9 手枪弹匣，无挂载槽位。', '20 rounds. Loads the battle rifle magazine, mg 3 magazine and gpmg magazine.': '20 发，为战斗步枪弹匣、MG3 弹匣与通用机枪弹匣装弹。', 'Hang any item on its face. Items stay visible and can be picked straight off.': '任何物品都可挂在其表面，物品保持可见，可直接取下。', 'Dead-end tap on a small liquid pipe. Outputs pressure in Pa on its data port.': '小号液管的末端取样口，经数据端口输出压力（Pa）。', 'Outputs its data input value as a mechanical link. Requires no electric power.': '把数据输入值输出为机械连杆，无需电力。', 'Plugs into a port socket. Link ports with the data tool to form a data network.': '插入端口座，用数据工具连接端口组成数据网络。', 'Storage 5x7. 4 attachment points for pouches, radios, lights, rope and patches.': '储物 5×7，4 个挂载点可挂腰包、电台、灯具、绳索与补丁。', 'Storage 6x8. 6 attachment points for pouches, radios, lights, rope and patches.': '储物 6×8，6 个挂载点可挂腰包、电台、灯具、绳索与补丁。', 'Storage 5x9. 3 attachment points for pouches, radios, lights, rope and patches.': '储物 5×9，3 个挂载点可挂腰包、电台、灯具、绳索与补丁。', 'Storage 5x6. 4 attachment points for pouches, radios, lights, rope and patches.': '储物 5×6，4 个挂载点可挂腰包、电台、灯具、绳索与补丁。', 'Outputs acceleration along its up axis, positive upward. Connect with data port.': '输出沿自身上轴的加速度，向上为正，经数据端口连接。', 'Tap to toggle mechanical link between 0 and 0.5. Hold 0.5 s to read 1 while held.': '轻按在 0 与 0.5 间切换机械连杆；按住 0.5 秒后握持期间读数为 1。', 'Automatic, 715 rpm, 556. Takes the lmg magazine only. Top rail and silencer slot.': '全自动，715 发/分，5.56，仅用轻机枪弹匣，顶部导轨与消音器槽位。', 'Holds a spare construction, tractor, loader, earthmover or heavyloader wheel item.': '容纳一个备用工程车轮（工程车/拖拉机/装载机/推土机/重型装载机）。', 'Joins two torque faces. Mechanical link above 0.75 disengages, below 0.25 engages.': '连接两个扭矩面，机械连杆高于 0.75 分离、低于 0.25 接合。', 'Fits an oil filter component. Removes pollutant from oil. Wears out as it filters.': '适配机油滤清器组件，滤除机油污染物，过滤中会逐渐损耗。', 'Stops bleeding and restores 30% blood. Hold to apply to yourself or another player.': '止血并恢复 30% 血量，按住对自己或他人使用。', 'Stops bleeding and restores 20% blood. Hold to apply to yourself or another player.': '止血并恢复 20% 血量，按住对自己或他人使用。', 'Attaches one end to a rope hook point and hangs loose. 20 m, fixed. Can be climbed.': '一端系于绳钩点后垂挂，固定长 20 米，可攀爬。', 'Outputs north angle: heading of its forward axis in degrees. Connect with data port.': '输出北向角：自身前轴的航向（度），经数据端口连接。', 'Occupies the body, head, legs and ears slots. Insulation 6.7 C. Rain resistance 80%.': '占用身体、头部、腿部与耳部槽位，保温 6.7 C，防雨 80%。', 'Fits the g17 pistol torch slot only. Takes a battery cell. Use to switch on and off.': '仅适配 G17 手枪电筒槽，使用一节电池，交互即可开关。', 'Hooks into a tow hitch within one voxel and roughly in line. Released from the hitch.': '在一格体素内大致对齐时钩住牵引挂扣，从挂扣处释放。', 'Fits any gas port face. Large pipe node. Pipe links only join nodes of the same size.': '适配任意气端口面，大号管节点；管路只连接同尺寸节点。', 'Fits any gas port face. Small pipe node. Pipe links only join nodes of the same size.': '适配任意气端口面，小号管节点；管路只连接同尺寸节点。', 'Stretchable strip of port sockets. Every data port plugged in joins the same network.': '可伸缩的端口座条带，插入的每个数据端口都并入同一网络。', 'Momentary. Mechanical link reads 1 once the lever completes its travel, 0 on release.': '瞬时式：操纵杆行程到底时机械连杆读 1，松开读 0。', 'Fits a helmet. Takes a battery cell, lasts about 1.5 h. Switch on and off while worn.': '装于头盔，使用一节电池，续航约 1.5 小时，佩戴时可开关。', "Fits a helicopter rotor or tail rotor. Blade length is set in the rotor's properties.": '适配直升机旋翼或尾桨，桨叶长度在旋翼属性中设置。', 'Fit liquid port. Mechanical link reads 1 above 4.9 kPa and 0 below 2.9 kPa. Holds 1 L.': '适配液端口；压力高于 4.9 kPa 时机械连杆读 1、低于 2.9 kPa 读 0，容量 1 升。', 'Use on a microcontroller component to open its code editor. Closes when you walk away.': '对微控制器组件使用以打开代码编辑器，走远自动关闭。', 'Semi-automatic, 762. Takes the battle rifle magazine only. Top rail and silencer slot.': '半自动，7.62，仅用战斗步枪弹匣，顶部导轨与消音器槽位。', 'Snap to activate. Glows for 60 min, 3 m radius. Can be thrown. Cannot be switched off.': '折亮即激活，发光 60 分钟，半径 3 米，可投掷，无法关闭。', 'Brakes a shaft between two torque faces. Braking force follows mechanical link, 0 to 1.': '制动两个扭矩面之间的转轴，制动力随机械连杆 0 到 1 变化。', 'Fits the wheel component. Radius 0.43 m, width 0.16 m. Cannot be stored in a container.': '适配车轮组件，半径 0.43 米、宽 0.16 米，无法放入其它容器。', 'Holds 7 rounds. Fits the 45 pistol. Use to load one round at a time from a 45 ammo box.': '容 7 发，适配 45 手枪，从 45 弹药盒逐发装填。', 'Fits a top rail. 12 degree field of view. Needs a battery cell and must be switched on.': '装于顶部导轨，视场角 12 度，需电池并需开启。', 'Connects two gas interface components. 2.5 m; extend or retract between 0.5 m and 20 m.': '连接两个气体接口组件，长 2.5 米，可在 0.5 至 20 米间伸缩。', 'Fits any liquid port face. Small pipe node. Pipe links only join nodes of the same size.': '适配任意液端口面，小号管节点；管路只连接同尺寸节点。', 'Fits any liquid port face. Large pipe node. Pipe links only join nodes of the same size.': '适配任意液端口面，大号管节点；管路只连接同尺寸节点。', 'Plugs into a port socket. Link ports with the electric tool to form an electric network.': '插入端口座，用电力工具连接端口组成电力网络。', 'Attach a rope to each side. Rope passes through until the tension of both sides matches.': '两侧各系一根绳，绳会滑移直到两侧张力相等。', 'Connects two data interface components. 2.5 m; extend or retract between 0.5 m and 20 m.': '连接两个数据接口组件，长 2.5 米，可在 0.5 至 20 米间伸缩。', 'Stretchable strip of port sockets. Every electric port plugged in joins the same network.': '可伸缩的端口座条带，插入的每个电力端口都并入同一网络。', 'Holds 13 rounds. Fits the hp pistol. Use to load one round at a time from a 9mm ammo box.': '容 13 发，适配 HP 手枪，从 9mm 弹药盒逐发装填。', 'Holds 15 rounds. Fits the m9 pistol. Use to load one round at a time from a 9mm ammo box.': '容 15 发，适配 M9 手枪，从 9mm 弹药盒逐发装填。', 'Holds 100 rounds. Fits the mg. Use to load one round at a time from a 556 rifle ammo box.': '容 100 发，适配机枪，从 5.56 步枪弹药盒逐发装填。', 'Carries 40 365mm shells round a 90 degree bend between its two belt faces. Holds 3 shells.': '在两个弹链面之间转 90 度弯输送 40 枚 365mm 弹，容 3 枚。', 'Holds 17 rounds. Fits the g17 pistol. Use to load one round at a time from a 9mm ammo box.': '容 17 发，适配 G17 手枪，从 9mm 弹药盒逐发装填。', 'Holds 50 rounds. Fits the mg 3. Use to load one round at a time from a 762 rifle ammo box.': '容 50 发，适配 MG3，从 7.62 步枪弹药盒逐发装填。', 'Fits the g17 pistol sight slot only. Reticle needs a battery cell and must be switched on.': '仅适配 G17 手枪瞄具槽，分划需电池并需开启。', 'Connects two liquid interface components. 2.5 m; extend or retract between 0.5 m and 20 m.': '连接两个液体接口组件，长 2.5 米，可在 0.5 至 20 米间伸缩。', 'Holds 100 rounds. Fits the gpmg. Use to load one round at a time from a 762 rifle ammo box.': '容 100 发，适配通用机枪，从 7.62 步枪弹药盒逐发装填。', 'Stores air or exhaust under pressure. 9.5 L plus 3.3 L per voxel of stretch. Fits gas ports.': '储存压缩空气或废气，基础 9.5 升、每拉伸体素加 3.3 升，适配气端口。', 'Storage 1x1. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 1×1，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 3x2. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 3×2，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 1x2. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 1×2，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 2x2. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 2×2，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 2x3. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 2×3，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 3x3. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 3×3，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Fits a front rail. Iron sight, no battery. Used only when nothing is fitted to the top rail.': '装于前部导轨，机械瞄具，无需电池，仅在顶部导轨空置时可用。', 'Links a lower shaft to a parallel upper shaft at 1:1, same direction. Stretch to set spacing.': '以 1:1 同向连接下轴与平行的上轴，拉伸以设定间距。', 'Plays the signal data input from a microphone or antenna. Range 8 to 64 m, set in properties.': '播放来自麦克风或天线的信号数据输入，范围 8 至 64 米，属性中设置。', 'Latch. Output goes to 1 when input A rises above 0.75 and to 0 when input B rises above 0.75.': '锁存：输入 A 升破 0.75 时输出置 1，输入 B 升破 0.75 时置 0。', 'Stores air or exhaust under pressure. 39.7 L plus 9.3 L per voxel of stretch. Fits gas ports.': '储存压缩空气或废气，基础 39.7 升、每拉伸体素加 9.3 升，适配气端口。', 'Break action, 12 gauge. Holds 1 round. Loaded by hand from shotgun ammo. No attachment slots.': '折动式，12 号口径，容 1 发，从霰弹弹药手动装填，无挂载槽位。', 'Bolts to an engine coolant port. Small pipe. Fit two so coolant circulates through a radiator.': '安装于发动机冷却液口，小号管；装两个可使冷却液经散热器循环。', 'Bolts to an engine coolant port. Large pipe. Fit two so coolant circulates through a radiator.': '安装于发动机冷却液口，大号管；装两个可使冷却液经散热器循环。', 'Holds 30 rounds. Fits the rifle a3. Use to load one round at a time from a 556 rifle ammo box.': '容 30 发，适配 A3 步枪，从 5.56 步枪弹药盒逐发装填。', 'Connects two electrical interface components. 2.5 m; extend or retract between 0.5 m and 20 m.': '连接两个电气接口组件，长 2.5 米，可在 0.5 至 20 米间伸缩。', 'Draws 50 W. Fit electric port. Lit whenever powered; switch with an electric relay. Range 10 m.': '功耗 50 W，适配电力端口，通电即亮，用继电器开关，射程 10 米。', 'Hold either end to slide, 1 s for full travel. Mechanical link reads 0 to 1 and holds position.': '按住任一端滑动，全行程 1 秒，机械连杆读数 0 到 1 并保持位置。', 'Stores air or exhaust under pressure. 103.6 L plus 18.6 L per voxel of stretch. Fits gas ports.': '储存压缩空气或废气，基础 103.6 升、每拉伸体素加 18.6 升，适配气端口。', 'Fixes a broken leg, restoring full movement speed. Hold to apply to yourself or another player.': '治疗骨折，恢复全部移动速度，按住对自己或他人使用。', 'Automatic, 715 rpm, 556. Takes the lmg magazine only. Side rail and silencer slot. No top rail.': '全自动，715 发/分，5.56，仅用轻机枪弹匣，侧导轨与消音器槽位，无顶部导轨。', 'Loads the cannon 120mm, one shell at a time. Stores in a 120mm shell holder. 10 m blast radius.': '为 120mm 加农炮逐发装填，存放于 120mm 弹壳座，爆炸半径 10 米。', 'Loads a smoke discharger. Bursts 1.5 s after launch. Smoke lasts 30 s and drifts with the wind.': '为烟幕弹发射器装填，发射 1.5 秒后爆开，烟幕持续 30 秒并随风飘移。', 'Fits a helmet. Takes a battery cell, lasts about 1.5 h. Switch on and off while worn. 60 m beam.': '装于头盔，使用一节电池，续航约 1.5 小时，佩戴时可开关，射程 60 米。', 'Holds 25 rounds. Fits the submachine gun 45. Use to load one round at a time from a 45 ammo box.': '容 25 发，适配冲锋枪 45，从 45 弹药盒逐发装填。', '12 cartridges. Loads the single shot shotgun, pump action shotgun and shotgun tactical directly.': '12 发，直接为单发霰弹枪、泵动霰弹枪与战术霰弹枪装填。', 'Bolts to an engine fuel port. Small pipe. Draws fuel itself once the engine turns; no pump needed.': '安装于发动机燃油口，小号管，发动机转动即自行吸油，无需油泵。', 'Bolts to an engine fuel port. Large pipe. Draws fuel itself once the engine turns; no pump needed.': '安装于发动机燃油口，大号管，发动机转动即自行吸油，无需油泵。', 'Revives an incapacitated player and raises every vital to at least 15%. Hold on the downed player.': '复苏倒地玩家并把各项生命体征升到至少 15%，对倒地玩家按住使用。', 'Holds 10 rounds. Fits the rifle sniper. Use to load one round at a time from a 308 rifle ammo box.': '容 10 发，适配狙击步枪，从 .308 步枪弹药盒逐发装填。', 'Holds 20 rounds. Fits the battle rifle. Use to load one round at a time from a 762 rifle ammo box.': '容 20 发，适配战斗步枪，从 7.62 步枪弹药盒逐发装填。', 'Holds one machete. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '容纳一把砍刀，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', '30 rounds. Loads the hp pistol magazine, m9 pistol magazine, g17 pistol magazine and smg magazine.': '30 发，为 HP 手枪弹匣、M9 手枪弹匣、G17 手枪弹匣与冲锋枪弹匣装弹。', 'Loads the autocannon 40mm belt and ammo mag 40mm. Stores in a 40mm shell holder. 6 m blast radius.': '为 40mm 机炮弹链与 40mm 弹匣装填，存放于 40mm 弹壳座，爆炸半径 6 米。', 'Opens a small liquid pipe to the outside. Dumps liquid overboard. Draws in seawater when submerged.': '使小号液管通向外界，向外排出液体，浸水时吸入海水。', 'Fits the retractable wheel components. Radius 0.6 m, width 0.28 m. Cannot be stored in a container.': '适配收放式车轮组件，半径 0.6 米、宽 0.28 米，无法放入其它容器。', 'Automatic, 850 rpm, 556. Takes the mg magazine only. Top rail, two side rails and underbarrel rail.': '全自动，850 发/分，5.56，仅用机枪弹匣，顶部导轨、双侧导轨与下挂导轨。', 'Mount on a seat main control face. Mechanical links: steering -1 to 1, left and right pedals 0 to 1.': '安装于座椅主控制面，机械连杆：转向 -1 到 1，左右踏板 0 到 1。', 'Needle sweeps a fixed arc for input -1 to 1. Input is mechanical link plus display value data input.': '指针在固定弧度内指示 -1 到 1 的输入，输入为机械连杆加显示值数据输入。', 'Automatic, 800 rpm, 9mm. Takes the smg magazine only. Top rail, two side rails and underbarrel rail.': '全自动，800 发/分，9mm，仅用冲锋枪弹匣，顶部导轨、双侧导轨与下挂导轨。', 'Fits a weapon mount or pintle mount. Needs gmg ammo in the mount. Automatic, 340 rpm, 40mm grenades.': '适配武器架或枢轴架，架上需榴弹机枪弹药，全自动，340 发/分，40mm 榴弹。', '100 rounds. Fits the ammo slot of a weapon mount or pintle mount. Feeds the m2 only. Not refillable.': '100 发，装于武器架或枢轴架弹药槽，仅供 M2，不可续填。', 'Fits any rifle rail: top, front, side or underbarrel. Takes a battery cell. Use to switch on and off.': '适配任意步枪导轨（顶部/前部/侧/下挂），使用一节电池，交互开关。', 'Fits battery-powered handheld items: torches, radios, goggles, sights and the signal detector. 16 Wh.': '适配电池手持物品：电筒、电台、护目镜、瞄具与信号探测器，容量 16 Wh。', 'Fits the wheel and tyre mount components. Radius 0.3 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.3 米、宽 0.16 米，无法放入其它容器。', 'Deflects up to 20 degrees from mechanical link. Force rises with airspeed and area. Stretch to enlarge.': '随机械连杆偏转至多 20 度，力随空速与面积增大，拉伸以增大。', 'Deflects up to 90 degrees from mechanical link. Force rises with airspeed and area. Stretch to enlarge.': '随机械连杆偏转至多 90 度，力随空速与面积增大，拉伸以增大。', 'Bolts to a liquid tank or radiator port. Fill or siphon with a hand-held container such as a jerry can.': '安装于液罐或散热器端口，用油桶等手持容器加注或抽取。', 'Wear in the hat slot. Takes a battery cell, lasts about 1.5 h. Switch on and off while worn. 40 m beam.': '佩戴于头部槽位，使用一节电池，续航约 1.5 小时，佩戴时可开关，射程 40 米。', '2 attachment points for pouches, radios, lights, rope and patches. Insulation 5 C. Rain resistance 60%.': '2 个挂载点可挂腰包、电台、灯具、绳索与补丁，保温 5 C，防雨 60%。', '1 attachment points for pouches, radios, lights, rope and patches. Insulation 5 C. Rain resistance 60%.': '1 个挂载点可挂腰包、电台、灯具、绳索与补丁，保温 5 C，防雨 60%。', '4 attachment points for pouches, radios, lights, rope and patches. Insulation 5 C. Rain resistance 60%.': '4 个挂载点可挂腰包、电台、灯具、绳索与补丁，保温 5 C，防雨 60%。', 'Fits the wheel and tyre mount components. Radius 0.31 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.31 米、宽 0.16 米，无法放入其它容器。', 'Fits the wheel and tyre mount components. Radius 0.34 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.34 米、宽 0.16 米，无法放入其它容器。', 'Fits the wheel and tyre mount components. Radius 0.33 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.33 米、宽 0.16 米，无法放入其它容器。', 'Fits the wheel and tyre mount components. Radius 0.36 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.36 米、宽 0.16 米，无法放入其它容器。', 'Fits the wheel and tyre mount components. Radius 0.39 m, width 0.16 m. Cannot be stored in a container.': '适配车轮与轮胎座组件，半径 0.39 米、宽 0.16 米，无法放入其它容器。', 'Holds 30 rounds. Fits the assault rifle 107. Use to load one round at a time from a 556 rifle ammo box.': '容 30 发，适配 107 突击步枪，从 5.56 步枪弹药盒逐发装填。', 'Holds 20 L. Spawns full of oil. Use on a liquid fill port to fill or siphon the connected tank at 1 L/s.': '容 20 升，出生时满装机油，对液体加注口使用可按每秒 1 升加注或抽取连接的罐。', 'Locks into a truck hitch within one voxel and in line. Released from the hitch. Data output is_connected.': '一格体素内对齐时锁入卡车挂扣，从挂扣处释放，数据输出 is_connected。', 'Hold 0.5 s to open or close the cover. Tap with the cover open to toggle mechanical link between 0 and 1.': '按住 0.5 秒开合护盖，护盖打开时轻按在 0 与 1 间切换机械连杆。', 'Automatic, 850 rpm, 556. Takes the rifle 107 magazine only. Top rail, underbarrel rail and silencer slot.': '全自动，850 发/分，5.56，仅用 107 步枪弹匣，顶部导轨、下挂导轨与消音器槽位。', 'Holds one tactical knife. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '容纳一把战术刀，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', '20 rounds. Loads the rifle magazine, rifle 107 magazine, rifle a3 magazine, lmg magazine and mg magazine.': '20 发，为步枪弹匣、107 步枪弹匣、A3 步枪弹匣、轻机枪弹匣与机枪弹匣装弹。', '500 rounds. Fits the ammo slot of a weapon mount or pintle mount. Feeds the minigun only. Not refillable.': '500 发，装于武器架或枢轴架弹药槽，仅供加特林，不可续填。', 'Mount on a seat main control face. Mechanical links: roll and pitch -1 to 1, left and right pedals 0 to 1.': '安装于座椅主控制面，机械连杆：横滚与俯仰 -1 到 1，左右踏板 0 到 1。', 'Fits the g17 pistol silencer slot. Shots alert enemies at a fifth of the range and muzzle flash is halved.': '适配 G17 手枪消音器槽，枪声警敌范围降为五分之一，枪口焰减半。', 'Holds 20 L. Spawns full of water. Use on a liquid fill port to fill or siphon the connected tank at 1 L/s.': '容 20 升，出生时满装水，对液体加注口使用可按每秒 1 升加注或抽取连接的罐。', 'Bolts to an oil port on an engine or jet part. Small pipe. Fit two so oil circulates through an oil filter.': '安装于发动机或喷气部件的机油口，小号管；装两个可使机油经滤清器循环。', 'Bolts to an oil port on an engine or jet part. Large pipe. Fit two so oil circulates through an oil filter.': '安装于发动机或喷气部件的机油口，大号管；装两个可使机油经滤清器循环。', 'Deflects up to 69 degrees from mechanical link. 5 times stronger submerged than in air. Stretch to enlarge.': '随机械连杆偏转至多 69 度，水下受力为空气中的 5 倍，拉伸以增大。', 'Holds 20 L. Spawns full of petrol. Use on a liquid fill port to fill or siphon the connected tank at 1 L/s.': '容 20 升，出生时满装汽油，对液体加注口使用可按每秒 1 升加注或抽取连接的罐。', 'Fits a top rail in place of a sight. 24 degree field of view. Needs a battery cell and must be switched on.': '装于顶部导轨以替代瞄具，视场角 24 度，需电池并需开启。', 'Fits the tyre mount and wheel medium components. Radius 0.73 m, width 0.7 m. Cannot be stored in a container.': '适配轮胎座与中型车轮组件，半径 0.73 米、宽 0.7 米，无法放入其它容器。', 'Fits the tyre mount and wheel medium components. Radius 0.56 m, width 0.7 m. Cannot be stored in a container.': '适配轮胎座与中型车轮组件，半径 0.56 米、宽 0.7 米，无法放入其它容器。', 'Fits the tyre mount and wheel medium components. Radius 0.62 m, width 0.7 m. Cannot be stored in a container.': '适配轮胎座与中型车轮组件，半径 0.62 米、宽 0.7 米，无法放入其它容器。', 'Pump action, 12 gauge. Holds 7 rounds. Loaded by hand, one round at a time, from shotgun ammo. Top rail only.': '泵动式，12 号口径，容 7 发，从霰弹弹药逐发手动装填，仅顶部导轨。', 'Holds one pistol or revolver. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '容纳一把手枪或左轮，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Fit two liquid ports and an oil filter item. Oil passes only with a filter fitted. Removes pollutant from oil.': '适配两个液端口与机油滤清器物品，装滤芯才过油，滤除机油污染物。', 'Fits upstream of the jet engine. Required for the engine to run. Fit two oil manifolds. Wears when low on oil.': '位于喷气发动机上游，发动机运转必需；装两个机油歧管，缺油时磨损。', 'Fully restores blood. Does not stop bleeding or fix a broken leg. Hold to apply to yourself or another player.': '完全恢复血量，但不能止血或治疗骨折，按住对自己或他人使用。', 'Connects gas pipes between vehicles. Press two gas interfaces face to face, or link with a gas hose. Small pipe.': '跨载具连接气管，两个气体接口对贴或用气软管连接，小号管。', 'Rigid road wheel for a wide track, 0.6 m wide. Radius 0.23 m. Turns only in a closed track loop with a sprocket.': '宽履带（0.6 米）用刚性负重轮，半径 0.23 米，仅在闭合履带环内随驱动轮转动。', 'Rigid road wheel for a wide track, 0.6 m wide. Radius 0.43 m. Turns only in a closed track loop with a sprocket.': '宽履带（0.6 米）用刚性负重轮，半径 0.43 米，仅在闭合履带环内随驱动轮转动。', 'Hold on a component, plate, edge or node to remove it. Components, plates and edges are refunded. Nodes are not.': '对组件/板材/边缘/节点按住即可移除；组件、板材与边缘返还成本，节点不返还。', 'Use on a component to open its properties: name, key binds, limits and other settings. Closes when you walk away.': '对组件使用打开属性：名称、按键绑定、限位等设置，走远自动关闭。', '50 rounds. Fits the ammo slot of a weapon mount or pintle mount. Feeds the grenade launcher only. Not refillable.': '50 发，装于武器架或枢轴架弹药槽，仅供榴弹发射器，不可续填。', 'Driven by torque face. Reels rope in or out with shaft rotation, 0.5 to 20 m. Mechanical link disengages the drum.': '由扭矩面驱动，随转轴转动收放绳索，0.5 至 20 米，机械连杆可脱开卷筒。', 'Inline shut-off on a small gas pipe. Closed by default. Opens when mechanical link passes 0.75, closes below 0.25.': '小号气管的串联截止阀，默认关闭；机械连杆超 0.75 开启、低于 0.25 关闭。', 'Inline shut-off on a large gas pipe. Closed by default. Opens when mechanical link passes 0.75, closes below 0.25.': '大号气管的串联截止阀，默认关闭；机械连杆超 0.75 开启、低于 0.25 关闭。', 'Connects a mechanical interface out to a mechanical interface in. 2.5 m; extend or retract between 0.5 m and 20 m.': '连接机械接口输出与机械接口输入，长 2.5 米，可在 0.5 至 20 米间伸缩。', 'Rigid road wheel for a narrow track, 0.12 m wide. Radius 0.08 m. Turns only in a closed track loop with a sprocket.': '窄履带（0.12 米）用刚性负重轮，半径 0.08 米，仅在闭合履带环内随驱动轮转动。', 'Rigid road wheel for a narrow track, 0.12 m wide. Radius 0.16 m. Turns only in a closed track loop with a sprocket.': '窄履带（0.12 米）用刚性负重轮，半径 0.16 米，仅在闭合履带环内随驱动轮转动。', 'Carries 40 365mm shells between its two belt faces. Stretches along its length; holds one shell per voxel plus one.': '两个弹链面之间输送 40 枚 365mm 弹，沿长度拉伸，每体素容一弹加一。', 'Pump action, 12 gauge. Holds 5 rounds. Loaded by hand, one round at a time, from shotgun ammo. No attachment slots.': '泵动式，12 号口径，容 5 发，从霰弹弹药逐发手动装填，无挂载槽位。', 'Needle turns half a revolution per unit of input, unlimited. Input is mechanical link plus display value data input.': '指针每单位输入转半圈，圈数不限，输入为机械连杆加显示值数据输入。', 'Semi-automatic, 9mm. Takes the g17 pistol magazine only. Slots for the g17 reflex sight, g17 torch and g17 silencer.': '半自动，9mm，仅用 G17 手枪弹匣，含 G17 反射瞄具、G17 电筒与 G17 消音器槽位。', 'Fits a weapon mount or pintle mount. Needs an m2 ammo can in the mount. Automatic, 600 rpm, 50 cal explosive rounds.': '适配武器架或枢轴架，架上需 M2 弹箱，全自动，600 发/分，12.7mm 爆炸弹。', 'Mechanical link reads 1 when on, 0 when off. Toggle by interacting, or from a seat with the button set in properties.': '开时机械连杆读 1、关时读 0，交互切换，或由座椅按属性中设置的按键切换。', 'Rigid road wheel for a standard track, 0.28 m wide. Radius 0.18 m. Turns only in a closed track loop with a sprocket.': '标准履带（0.28 米）用刚性负重轮，半径 0.18 米，仅在闭合履带环内随驱动轮转动。', 'Rigid road wheel for a standard track, 0.28 m wide. Radius 0.34 m. Turns only in a closed track loop with a sprocket.': '标准履带（0.28 米）用刚性负重轮，半径 0.34 米，仅在闭合履带环内随驱动轮转动。', 'Inline shut-off on a small liquid pipe. Closed by default. Opens when mechanical link passes 0.75, closes below 0.25.': '小号液管的串联截止阀，默认关闭；机械连杆超 0.75 开启、低于 0.25 关闭。', 'Inline shut-off on a large liquid pipe. Closed by default. Opens when mechanical link passes 0.75, closes below 0.25.': '大号液管的串联截止阀，默认关闭；机械连杆超 0.75 开启、低于 0.25 关闭。', 'Draws 50 W. Fit electric port. Sounds whenever powered; switch with an electric relay. Sound effect set in properties.': '功耗 50 W，适配电力端口，通电即响，用继电器开关，音效在属性中设置。', 'Fits the fan face of a radiator. Draws 90 W. Fit electric port. Cooling scales with fan size relative to the radiator.': '装于散热器风扇面，功耗 90 W，适配电力端口，散热随风扇与散热器的相对尺寸变化。', 'Fits the landing gear and landing gear dual components. Radius 0.25 m, width 0.165 m. Cannot be stored in a container.': '适配起落架与双起落架组件，半径 0.25 米、宽 0.165 米，无法放入其它容器。', 'Bolt action, 308. Holds 5 rounds. Loaded by hand, one round at a time, from a 308 rifle ammo box. No attachment slots.': '栓动，.308，容 5 发，从 .308 步枪弹药盒逐发手动装填，无挂载槽位。', 'Fits a weapon mount or pintle mount. Needs a minigun ammo can in the mount. Automatic, 3000 rpm, 762 explosive rounds.': '适配武器架或枢轴架，架上需加特林弹箱，全自动，3000 发/分，7.62 爆炸弹。', 'Hold use to pull the pin, hold throw to throw. 5 s fuse from the pin pull. 6 m blast radius. Fits an attachment point.': '按住使用拔销、按住投掷键投出，拔销后 5 秒引信，爆炸半径 6 米，可挂载。', 'Draws 50 W. Fit electric port. Lit whenever powered; switch with an electric relay. Range 50 m, sweeps once per second.': '功耗 50 W，适配电力端口，通电即亮，用继电器开关，射程 50 米，每秒扫描一次。', 'Output flips between 0 and 1 each time the input rises above 0.75. Input must fall below 0.25 before it can flip again.': '输入每次升破 0.75 时输出在 0 与 1 间翻转；输入须先降回 0.25 以下才能再次翻转。', 'Fits at the downstream end of the jet chain. Required for the engine to run. Produces thrust, rising with engine speed.': '位于喷气链末端，发动机运转必需，产生推力并随发动机转速增大。', 'Fits the fan face of a radiator. Draws 250 W. Fit electric port. Cooling scales with fan size relative to the radiator.': '装于散热器风扇面，功耗 250 W，适配电力端口，散热随风扇与散热器的相对尺寸变化。', 'Fits the fan face of a radiator. Draws 980 W. Fit electric port. Cooling scales with fan size relative to the radiator.': '装于散热器风扇面，功耗 980 W，适配电力端口，散热随风扇与散热器的相对尺寸变化。', 'Fits the fan face of a radiator. Draws 1620 W. Fit electric port. Cooling scales with fan size relative to the radiator.': '装于散热器风扇面，功耗 1620 W，适配电力端口，散热随风扇与散热器的相对尺寸变化。', 'Connects liquid pipes between vehicles. Press two liquid interfaces face to face, or link with a liquid hose. Small pipe.': '跨载具连接液管，两个液体接口对贴或用液软管连接，小号管。', 'Diverter on a small gas pipe. Inlet feeds the right outlet while mechanical link is below 0.25, the left outlet above 0.75.': '小号气管分流阀：机械连杆低于 0.25 时入口通右出口，高于 0.75 通左出口。', 'Outputs tilt: angle of its up axis from vertical in degrees. 0 level, 90 on its side, 180 inverted. Connect with data port.': '输出倾角：上轴偏离竖直的角度（度），水平为 0、侧立 90、倒置 180，经数据端口连接。', 'Bolts to the jet engine fuel port. Small pipe. Throttle is a mechanical link input. Draws fuel itself once the engine turns.': '安装于喷气发动机燃油口，小号管，油门为机械连杆输入，发动机转动即自行吸油。', 'Fixed ratio between two torque faces. Ratio set by input and output properties, 1 to 8 each. Reverse flips output direction.': '两个扭矩面间固定齿比，齿比由输入输出属性设定（各 1 到 8），倒挡反转输出方向。', 'Joins the drive shafts of two vehicles face to face with another torque interface. Small torque face. Disconnects beyond 4 cm.': '用另一扭矩接口使两载具传动轴对接，小号扭矩面，错位超 4 厘米断开。', 'Diverter on a small liquid pipe. Inlet feeds the right outlet while mechanical link is below 0.25, the left outlet above 0.75.': '小号液管分流阀：机械连杆低于 0.25 时入口通右出口，高于 0.75 通左出口。', 'Holds 30 rounds. Fits the rifle short barrel and rifle long barrel. Use to load one round at a time from a 556 rifle ammo box.': '容 30 发，适配短管步枪与长管步枪，从 5.56 步枪弹药盒逐发装填。', 'Fits a top rail on its own, in place of a scope. Thermal, 8 degree field of view. Needs a battery cell and must be switched on.': '独立装于顶部导轨以替代瞄准镜，热成像，视场角 8 度，需电池并需开启。', 'Sprung road wheel for a wide track, 0.6 m wide. Radius 0.23 m, travel 0.16 m. Turns only in a closed track loop with a sprocket.': '宽履带（0.6 米）用弹簧负重轮，半径 0.23 米、行程 0.16 米，仅在闭合履带环内随驱动轮转动。', 'Sprung road wheel for a wide track, 0.6 m wide. Radius 0.43 m, travel 0.24 m. Turns only in a closed track loop with a sprocket.': '宽履带（0.6 米）用弹簧负重轮，半径 0.43 米、行程 0.24 米，仅在闭合履带环内随驱动轮转动。', 'Driven by torque face. Fit 2 to 6 rotor blade items, 0.5 to 2 m. Collective mechanical link, -1 to 1, sets thrust and direction.': '由扭矩面驱动，装 2 至 6 片桨叶物品（0.5 至 2 米），总距机械连杆（-1 到 1）设定推力与方向。', 'Automatic, 600 rpm, 45. Takes the smg45 magazine only. Top rail, front rail, two side rails, underbarrel rail and silencer slot.': '全自动，600 发/分，.45，仅用 SMG45 弹匣，顶部导轨、前部导轨、双侧导轨、下挂导轨与消音器槽位。', 'Double action, 357 magnum. Holds 6 rounds. Loaded by hand, one round at a time, from a 357 magnum ammo box. No attachment slots.': '双动式，.357 马格南，容 6 发，从 .357 马格南弹药盒逐发手动装填，无挂载槽位。', 'Fits a top rail on its own, in place of a scope. Thermal, 16 degree field of view. Needs a battery cell and must be switched on.': '独立装于顶部导轨以替代瞄准镜，热成像，视场角 16 度，需电池并需开启。', 'Drag between two points to lay a beam 8 cm thick. Costs 1 per grid cell of length. Reload locks the drag axis. Secondary cancels.': '在两点间拖放铺设 8 厘米厚梁，每格长度耗 1，装填键锁定拖拽轴，副键取消。', 'Automatic, 850 rpm, 556. Takes the rifle magazine only. Top rail, front rail, two side rails, underbarrel rail and silencer slot.': '全自动，850 发/分，5.56，仅用步枪弹匣，顶部导轨、前部导轨、双侧导轨、下挂导轨与消音器槽位。', 'Shows display value data input as 1 digit, 0 to 9. Negative values show 0. Requires a powered microcontroller on the data network.': '把显示值数据输入显示为 1 位数（0 到 9），负值显示 0，需数据网络上有通电的微控制器。', 'Driven by torque face. Charges the electric network through an electric port. Output rises with rps, peaking at 1.1 kW at 100 rps.': '由扭矩面驱动，经电力端口为电力网络充电，输出随转速上升，100 转/秒时峰值 1.1 kW。', 'Drag between two points to lay a beam 24 cm thick. Costs 1 per grid cell of length. Reload locks the drag axis. Secondary cancels.': '在两点间拖放铺设 24 厘米厚梁，每格长度耗 1，装填键锁定拖拽轴，副键取消。', 'Switch for an electric network. Fitted electric ports are joined while on. Activate mechanical link: on above 0.75, off below 0.25.': '电力网络开关，开启时接通所装电力端口；机械连杆超 0.75 接通、低于 0.25 断开。', 'Sprung road wheel for a narrow track, 0.12 m wide. Radius 0.08 m, travel 0.08 m. Turns only in a closed track loop with a sprocket.': '窄履带（0.12 米）用弹簧负重轮，半径 0.08 米、行程 0.08 米，仅在闭合履带环内随驱动轮转动。', 'Sprung road wheel for a narrow track, 0.12 m wide. Radius 0.16 m, travel 0.08 m. Turns only in a closed track loop with a sprocket.': '窄履带（0.12 米）用弹簧负重轮，半径 0.16 米、行程 0.08 米，仅在闭合履带环内随驱动轮转动。', 'Fits a helmet or an attachment point. Takes a battery cell, lasts about 8 h. Flashes once per second. Switch on and off while worn.': '装于头盔或挂载点，使用一节电池，续航约 8 小时，每秒闪烁一次，佩戴时可开关。', 'Holds 30 rounds. Fits the light machine gun m1 and light machine gun sa. Use to load one round at a time from a 556 rifle ammo box.': '容 30 发，适配 M1 轻机枪与 SA 轻机枪，从 5.56 步枪弹药盒逐发装填。', 'Fits any rifle rail: top, front, side or underbarrel. Takes a battery cell. Use to switch on and off. Does not change the aim view.': '适配任意步枪导轨（顶部/前部/侧/下挂），使用一节电池，交互开关，不影响瞄准视野。', 'Automatic, 650 rpm, 556. Takes the rifle a3 magazine only. Top rail, front rail, two side rails, underbarrel rail and silencer slot.': '全自动，650 发/分，5.56，仅用 A3 步枪弹匣，顶部导轨、前部导轨、双侧导轨、下挂导轨与消音器槽位。', 'Shows display value data input as 3 digits, 0 to 999. Negative values show 0. Requires a powered microcontroller on the data network.': '把显示值数据输入显示为 3 位数（0 到 999），负值显示 0，需数据网络上有通电的微控制器。', 'Two needles, each sweeping a fixed arc for input -1 to 1. Inputs are mechanical links A and B plus display value A and B data inputs.': '双指针各在固定弧度内指示 -1 到 1，输入为机械连杆 A/B 加显示值 A/B 数据输入。', 'Pairs with a hinge pin: place one on the other in the editor to start a hinged body. Connect and release by interacting with the pin.': '与铰链销配对：编辑器中叠放即可建立铰接体，交互销子来连接与释放。', 'Sprung road wheel for a standard track, 0.28 m wide. Radius 0.18 m, travel 0.16 m. Turns only in a closed track loop with a sprocket.': '标准履带（0.28 米）用弹簧负重轮，半径 0.18 米、行程 0.16 米，仅在闭合履带环内随驱动轮转动。', 'Sprung road wheel for a standard track, 0.28 m wide. Radius 0.34 m, travel 0.24 m. Turns only in a closed track loop with a sprocket.': '标准履带（0.28 米）用弹簧负重轮，半径 0.34 米、行程 0.24 米，仅在闭合履带环内随驱动轮转动。', 'Joins the data networks of two vehicles. Connects face to face with another data interface or by data cable. Disconnects beyond 4 cm.': '连接两载具的数据网络，与另一数据接口对贴或用数据线连接，错位超 4 厘米断开。', "While recording data input is set, picks up the nearest player's voice within 32 m and outputs it on signal for a speaker or antenna.": '录音数据输入置位时，拾取 32 米内最近玩家的语音并经信号输出给扬声器或天线。', 'Passes 40 365mm shells between separate bodies. Two join automatically when their faces meet nose to nose and part when pulled apart.': '在独立机体间传送 40 枚 365mm 弹，两个单元弹头相对即自动接合，拉开即分离。', 'Belt output of a small engine. Turns at engine speed; a pulley wheel on its belt turns 2.5 times faster. Reverse flips belt direction.': '小型发动机的皮带输出，随发动机转速转动；其上皮带轮转速为 2.5 倍，倒挡反转皮带方向。', 'Belt output of a large engine. Turns at engine speed; a pulley wheel on its belt turns 6.7 times faster. Reverse flips belt direction.': '大型发动机的皮带输出，随发动机转速转动；其上皮带轮转速为 6.7 倍，倒挡反转皮带方向。', 'Draws 50 W. Fit electric port. Lit whenever powered; switch with an electric relay. Range 100 m. Tilt and beam width set in properties.': '功耗 50 W，适配电力端口，通电即亮，用继电器开关，射程 100 米，俯仰与光束宽度在属性中设置。', 'Shows display value data input as 5 digits, 0 to 99999. Negative values show 0. Requires a powered microcontroller on the data network.': '把显示值数据输入显示为 5 位数（0 到 99999），负值显示 0，需数据网络上有通电的微控制器。', 'Belt output of a medium engine. Turns at engine speed; a pulley wheel on its belt turns 3.9 times faster. Reverse flips belt direction.': '中型发动机的皮带输出，随发动机转速转动；其上皮带轮转速为 3.9 倍，倒挡反转皮带方向。', 'Mount on a seat control face. Momentary: mechanical link reads 1 pushed forward, -1 pulled back, 0 at rest. Moved with program 1 and 2.': '装于座椅控制面，瞬时式：前推读 1、后拉读 -1、松开归 0，用可编程键 1 和 2 操纵。', 'Bolts to an engine exhaust port. Small pipe. Exhaust at 300C. Back pressure above 39 kPa cuts engine power; the engine stops at 196 kPa.': '安装于发动机排气口，小号管；废气 300C，背压超 39 kPa 削减功率、196 kPa 熄火。', 'Bolts to an engine exhaust port. Large pipe. Exhaust at 300C. Back pressure above 39 kPa cuts engine power; the engine stops at 196 kPa.': '安装于发动机排气口，大号管；废气 300C，背压超 39 kPa 削减功率、196 kPa 熄火。', 'Each press steps to the next position, wrapping round. Count 2 to 12, set in properties. Mechanical link reads position divided by count.': '每按一次进到下一档位并循环，档位数 2 到 12 在属性中设置，机械连杆读数为位置除以档数。', 'Pairs with a mounting pin: place one on the other in the editor to start a detachable body. Lock and release by interacting with the pin.': '与安装销配对：编辑器中叠放即可建立可分离体，交互销子来锁定与释放。', 'Swipe a keycard with the matching key. On accept, mechanical link and accept data output read 1 for 1 s. A wrong key sets reject for 1 s.': '刷密钥匹配的门禁卡：通过时机械连杆与 accept 数据输出置 1 持续 1 秒，错误则 reject 置 1 秒。', 'Rod end of a hydraulic ram. Link to a same-size hydraulic connector base with the hydraulic tool. Has no liquid nodes; driven from the base.': '液压缸的杆端，用液压工具连接同尺寸液压接头座；自身无液节点，由座端驱动。', 'Dead-end belt section loaded by hand with 40 365mm shells. Its belt face joins the chain toward the gun. Holds one shell per voxel plus one.': '手动装填 40 枚 365mm 弹的末端弹链段，其弹链面朝向炮方向接入链条，每体素容一弹加一。', 'Mount on a seat control face. Shift with program 1 and 2. Gear count 2 to 10, set in properties. Mechanical link reads gear divided by count.': '装于座椅控制面，用可编程键 1 和 2 换挡，档数 2 到 10 在属性中设置，机械连杆读数为档位除以档数。', 'Fits car, van, quadbike and 4x4 wheel items. Drive from torque face. Steers up to 32 degrees from steering mechanical link. Brake link 0 to 1.': '适配轿车/厢式车/四轮摩托/四驱车车轮物品，由扭矩面驱动，随转向机械连杆最多转 32 度，刹车连杆 0 到 1。', 'Pairs with a rail: place one on the other in the editor to start a sliding body. Interact to attach to a rail within one voxel, or to release.': '与滑轨配对：编辑器中叠放即可建立滑动体，交互可吸附一格内的滑轨或释放。', 'Transfers heat between a gas and a liquid without mixing. Gas ports on one end, liquid ports on the other. Stretch longer for faster transfer.': '在气体与液体间不混合换热，一端气端口、另一端液端口，拉得越长换热越快。', 'Hold and use to open the insignia editor. Canvas 12x12 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 12×12 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 12x24 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 12×24 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 24x12 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 24×12 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 24x24 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 24×24 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 36x12 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 36×12 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 36x24 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 36×24 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 48x12 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 48×12 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Hold and use to open the insignia editor. Canvas 48x24 pixels. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '按住使用打开徽章编辑器，画布 48×24 像素，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Draws up to 10 kW. Fit electric port. Runs at 30 rps whenever powered. Reverse and power set in properties. Target rps can be set by data link.': '功耗最高 10 kW，适配电力端口，通电即以 30 转/秒运转，反转与功率在属性中设置，目标转速可经数据链设定。', 'Draws up to 60 kW. Fit electric port. Runs at 30 rps whenever powered. Reverse and power set in properties. Target rps can be set by data link.': '功耗最高 60 kW，适配电力端口，通电即以 30 转/秒运转，反转与功率在属性中设置，目标转速可经数据链设定。', 'Bolts to an engine air port. Small pipe. Throttle is a mechanical link input. Intake pressure above 9.8 kPa adds power, up to double at 98 kPa.': '安装于发动机进气口，小号管，油门为机械连杆输入，进气压力超 9.8 kPa 增功、98 kPa 时翻倍。', 'Bolts to an engine air port. Large pipe. Throttle is a mechanical link input. Intake pressure above 9.8 kPa adds power, up to double at 98 kPa.': '安装于发动机进气口，大号管，油门为机械连杆输入，进气压力超 9.8 kPa 增功、98 kPa 时翻倍。', 'Fits upstream of the jet engine. Prevents particle wear. Fit two oil manifolds. Pumps outside air into a large gas pipe while the engine turns.': '位于喷气发动机上游，防颗粒磨损；装两个机油歧管，发动机转动时把外部空气泵入大号气管。', 'Hold use to pull the pin, hold throw to throw. 3 s fuse from the pin pull. Smoke lasts 60 s and drifts with the wind. Fits an attachment point.': '按住使用拔销、按住投掷键投出，拔销后 3 秒引信，烟幕持续 60 秒并随风飘移，可挂载。', 'Draws up to 120 kW. Fit electric port. Runs at 30 rps whenever powered. Reverse and power set in properties. Target rps can be set by data link.': '功耗最高 120 kW，适配电力端口，通电即以 30 转/秒运转，反转与功率在属性中设置，目标转速可经数据链设定。', 'Holds a battery item of the same type, fitted by hand. 4 kWh. Fit electric port. Charged by an alternator on the same network. Damage empties it.': '容纳同类型电池物品（手工装入），容量 4 kWh，适配电力端口，由同网络发电机充电，受损即放空。', 'Holds a battery item of the same type, fitted by hand. 2 kWh. Fit electric port. Charged by an alternator on the same network. Damage empties it.': '容纳同类型电池物品（手工装入），容量 2 kWh，适配电力端口，由同网络发电机充电，受损即放空。', 'Locks onto a tow bar within one voxel and roughly in line. Mechanical link of 1 releases it and blocks reconnection. Breaks free under heavy load.': '一格体素内大致对齐时锁入牵引杆，机械连杆为 1 时释放并阻止重连，重载下会脱开。', 'Place a mounting knuckle on it in the editor to start a detachable body. Interact to lock onto an aligned knuckle within one voxel, or to release.': '编辑器中在其上放安装座即可建立可分离体，交互锁定一格内对齐的安装座或释放。', 'Attaches to rope hook points, winches and pulleys, or to yourself. 2.5 m; extend or retract in 0.1 m steps between 0.5 m and 20 m. Can be climbed.': '连接绳钩点、绞盘与滑轮，或系在自己身上，长 2.5 米，可在 0.5 至 20 米间以 0.1 米步进伸缩，可攀爬。', 'Joins the electric networks of two vehicles. Connects face to face with another electrical interface or by electric cable. Disconnects beyond 4 cm.': '连接两载具的电力网络，与另一电气接口对贴或用电缆连接，错位超 4 厘米断开。', 'Transfers heat between two gas circuits without mixing. Ports on one end are circuit A, the other end circuit B. Stretch longer for faster transfer.': '在两条气回路间不混合换热，一端为回路 A、另一端回路 B，拉得越长换热越快。', 'Sends a mechanical link value to a mechanical interface in on another vehicle. Connects face to face or by mechanical cable. Disconnects beyond 4 cm.': '把机械连杆值发送到另一载具的机械接口输入，对贴或用机械缆连接，错位超 4 厘米断开。', 'Pairs with a rail ballscrew: place one on the other in the editor to start a driven sliding body. Holds position; moves only when the ballscrew turns.': '与滚珠丝杠配对：编辑器中叠放即可建立从动滑动体，可保持位置，仅丝杠转动时移动。', 'Drives a wide track, 0.6 m wide. Radius 0.23 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '宽履带（0.6 米）驱动轮，半径 0.23 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', 'Drives a wide track, 0.6 m wide. Radius 0.43 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '宽履带（0.6 米）驱动轮，半径 0.43 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', 'Draws 10 W. Fit electric port. Runs a script that reads and writes every component on its data network. Powers displays and backlights on that network.': '功耗 10 W，适配电力端口，运行脚本读写其数据网络上的全部组件，并为该网络的显示屏与背光供电。', 'Transfers heat between two liquid circuits without mixing. Ports on one end are circuit A, the other end circuit B. Stretch longer for faster transfer.': '在两条液回路间不混合换热，一端为回路 A、另一端回路 B，拉得越长换热越快。', 'Drives a narrow track, 0.12 m wide. Radius 0.08 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '窄履带（0.12 米）驱动轮，半径 0.08 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', 'Drives a narrow track, 0.12 m wide. Radius 0.16 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '窄履带（0.12 米）驱动轮，半径 0.16 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', 'Joins two vehicles or structures into one. Align a surface or frame edge of each within 4 cm, then hold primary. The lighter one merges into the heavier.': '把两个载具或结构合为一体：各取一个表面或框架边在 4 厘米内对齐后按住主键，较轻者并入较重者。', 'Place a rail slider on it in the editor to start a sliding body. Stretches along its length and holds one slider per voxel. Sliders run freely end to end.': '编辑器中在其上放滑块即可建立滑动体，沿长度拉伸，每体素容一个滑块，滑块可全程自由滑动。', 'Receives a mechanical link value from a mechanical interface out on another vehicle. Connects face to face or by mechanical cable. Disconnects beyond 4 cm.': '接收另一载具机械接口输出的机械连杆值，对贴或用机械缆连接，错位超 4 厘米断开。', 'Drives a standard track, 0.28 m wide. Radius 0.18 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '标准履带（0.28 米）驱动轮，半径 0.18 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', 'Drives a standard track, 0.28 m wide. Radius 0.34 m. Drive from torque face. Loop the track over it and roller wheels of the same width with the belt tool.': '标准履带（0.28 米）驱动轮，半径 0.34 米，由扭矩面驱动，用皮带工具把履带与同宽滚轮环包其上。', "Takes a battery cell, lasts about 2 h, and a frequency cartridge. Beeps faster when pointed at the cartridge's transponder and as you close in. Range 10 km.": '使用一节电池（约 2 小时）与频率卡；指向卡的应答器且越靠近时蜂鸣越快，范围 10 公里。', 'Belt wheel on a torque face, radius 0.04 m. Belt to an engine wheel or pulley wheel with the belt tool. Speed scales by radius ratio. Reverse flips direction.': '扭矩面上的皮带轮，半径 0.04 米，用皮带工具连到发动机轮或皮带轮，速度按半径比缩放，倒挡反转。', 'Storage 1x2. 1 attachment points for pouches, radios, lights, rope and patches. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 1×2，1 个挂载点可挂腰包、电台、灯具、绳索与补丁，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Storage 2x2. 1 attachment points for pouches, radios, lights, rope and patches. Attaches to an attachment point on a vest, jacket, backpack, trousers or pouch.': '储物 2×2，1 个挂载点可挂腰包、电台、灯具、绳索与补丁，挂载于背心/夹克/背包/裤子/腰包上的挂载点。', 'Fixed mount. Takes an M2, grenade launcher or minigun and its matching ammo can. Fires while trigger mechanical link is above 0.75. Aims where the mount points.': '固定武器架，装 M2/榴弹发射器/加特林及配套弹箱，扳机机械连杆超 0.75 时开火，朝架设方向射击。', 'One unguided missile, cannot be reloaded. Flies straight with no drop. 12 m blast radius. Backblast injures anyone within 10 m behind you. Top rail for a sight.': '一发无制导导弹，不可再装填，直飞无下坠，爆炸半径 12 米，尾焰伤害身后 10 米内人员，顶部可装瞄具。', 'Flexible belt end. Link two with the belt tool, up to 1.2 m apart, to carry 40 365mm shells between separate bodies. The run tethers the bodies to that distance.': '柔性弹链端，用皮带工具连接两个（相距至多 1.2 米）在独立机体间输送 40 枚 365mm 弹，链段把机体牵制在该距离。', 'Fits the silencer slot on rifles, submachine gun 45, battle rifle and light machine guns. Shots alert enemies at a fifth of the range and muzzle flash is halved.': '适配步枪、冲锋枪 45、战斗步枪与轻机枪的消音器槽，枪声警敌范围降为五分之一，枪口焰减半。', 'Mount on a seat control face. Mechanical link reads 0 to 1, moved with program 1 and 2. Sticky holds position, moving 0.6 per second; non-sticky springs back to 0.': '装于座椅控制面，机械连杆读数 0 到 1，用可编程键 1 和 2 操纵；自保持式以每秒 0.6 移动并保持，非自保持式回弹到 0。', 'Needle turns half a revolution per unit of input, unlimited. Feed north angle divided by 180 for a heading. Input is mechanical link plus display value data input.': '指针每单位输入转半圈，圈数不限；输入北向角除以 180 即航向，输入为机械连杆加显示值数据输入。', 'Mount on a seat control face. Mechanical link reads -1 to 1, moved with program 1 and 2. Sticky holds position, moving 0.6 per second; non-sticky springs back to 0.': '装于座椅控制面，机械连杆读数 -1 到 1，用可编程键 1 和 2 操纵；自保持式以每秒 0.6 移动并保持，非自保持式回弹到 0。', 'Holds water, petrol or oil, 0.5 L per voxel; stretch to size. Ruptures on hard impact; explodes holding over 10 L of petrol. Fits liquid ports and a liquid fill port.': '储水/汽油/机油，每体素 0.5 升，可拉伸定容；猛烈撞击会破裂，装汽油超 10 升会爆炸，适配液端口与液体加注口。', 'Click connected edges to trace a flat, convex loop; closing the loop fills it with a plate. All edges must be the same size. Cost scales with area. Secondary cancels.': '点击相连边缘勾出平面凸多边形，闭合即填充为板材，所有边须同尺寸，成本随面积，副键取消。', 'Click connected edges to trace a flat, convex loop; closing the loop fills it with a hatch. All edges must be the same size. Cost scales with area. Secondary cancels.': '点击相连边缘勾出平面凸多边形，闭合即填充为舱口，所有边须同尺寸，成本随面积，副键取消。', 'Click connected edges to trace a flat, convex loop; closing the loop fills it with a window. All edges must be the same size. Cost scales with area. Secondary cancels.': '点击相连边缘勾出平面凸多边形，闭合即填充为车窗，所有边须同尺寸，成本随面积，副键取消。', 'Cools its liquid toward air temperature. Fit a radiator fan for more cooling. Holds 3 L; stretch for more. Circulate coolant through it with a pump. Leaks when damaged.': '把其液体向气温冷却，装散热风扇增强散热，容量 3 升可拉伸扩容，用泵驱动冷却液循环，受损泄漏。', 'Cools its liquid toward air temperature. Fit a radiator fan for more cooling. Holds 12 L; stretch for more. Circulate coolant through it with a pump. Leaks when damaged.': '把其液体向气温冷却，装散热风扇增强散热，容量 12 升可拉伸扩容，用泵驱动冷却液循环，受损泄漏。', 'Click connected edges to trace a flat, convex loop; closing the loop fills it with an opening. All edges must be the same size. Cost scales with area. Secondary cancels.': '点击相连边缘勾出平面凸多边形，闭合即填充为开口，所有边须同尺寸，成本随面积，副键取消。', 'Holds 30 rounds. Fits the submachine gun k pdw, submachine gun a3, smg a3t, submachine gun a4 and submachine gun sd. Use to load one round at a time from a 9mm ammo box.': '容 30 发，适配 K-PDW、A3 冲锋枪、SMG A3T、A4 冲锋枪与 SD 冲锋枪，从 9mm 弹药盒逐发装填。', 'Shows the temperature of liquid and gas nodes, links and component contents on nearby vehicles as a colour scale, -15 C to 60 C. Hover a component for its exact reading.': '以色阶（-15C 到 60C）显示附近载具的液/气节点、管路及组件内温度，悬停组件可看精确读数。', 'Driven by torque face. Fit two gas ports; pumps from the first fitted to the second. Head 2 kPa per rps. Reverse the shaft or set reverse in properties to swap direction.': '由扭矩面驱动，装两个气端口，从先装的泵向后装的；扬程每转 2 kPa，反转轴或在属性设反向可换向。', 'Connects gas nodes. Drag from one node to another on the same vehicle. Primary in empty space adds a waypoint. Dragging onto an existing link removes it. Secondary cancels.': '连接气体节点：在同载具上从一个节点拖到另一个，空处按主键加中间点，拖到已有管路上为删除，副键取消。', 'Hold use to pull the pin, hold throw to throw. 5 s fuse from the pin pull. Stuns anyone in line of sight within 12 m for up to 5 s, less at range. Fits an attachment point.': '按住使用拔销、按住投掷键投出，拔销后 5 秒引信，致盲 12 米视线内人员至多 5 秒（随距离衰减），可挂载。', 'Connects data nodes. Drag from one node to another on the same vehicle. Primary in empty space adds a waypoint. Dragging onto an existing link removes it. Secondary cancels.': '连接数据节点：在同载具上从一个节点拖到另一个，空处按主键加中间点，拖到已有链路上为删除，副键取消。', 'Pairs with a latch handle or latch pin: place it on either in the editor to start a latched body. Relatches whenever within one voxel of a free one. Data output is_connected.': '与锁扣手柄或锁扣销配对：编辑器中叠放即可建立锁扣体，靠近空闲锁扣一格内自动回锁，数据输出 is_connected。', 'Connects two belt nodes of the same type on the same vehicle, or an ammo belt to a weapon. Each node takes one belt. Nodes must lie in the same plane and face along the belt.': '连接同载具上两个同类型弹链节点或弹链到武器，每节点一条链，节点须共面且沿链向。', 'Fits at the upstream end of the jet chain. Torque face turns with the engine shaft; drive it to start the engine or take power from it. Gear ratio 1 to 128, set in properties.': '位于喷气链上游，扭矩面随发动机轴转动，驱动它可启动发动机或取力，齿比 1 到 128 在属性中设置。', 'Connects liquid nodes. Drag from one node to another on the same vehicle. Primary in empty space adds a waypoint. Dragging onto an existing link removes it. Secondary cancels.': '连接液体节点：在同载具上从一个节点拖到另一个，空处按主键加中间点，拖到已有管路上为删除，副键取消。', 'Locks onto a truck hitch kingpin within one voxel and in line. Mechanical link of 1 releases it and blocks reconnection. Data output is_connected. Breaks free under heavy load.': '一格体素内对齐时锁入卡车挂扣主销，机械连杆为 1 时释放并阻止重连，数据输出 is_connected，重载下脱开。', 'Connects electric nodes. Drag from one node to another on the same vehicle. Primary in empty space adds a waypoint. Dragging onto an existing link removes it. Secondary cancels.': '连接电力节点：在同载具上从一个节点拖到另一个，空处按主键加中间点，拖到已有线路上为删除，副键取消。', 'Fires 40 365mm shells at 2 rounds per second, 850 m/s, while trigger mechanical link is above 0.75. Feed from an ammo mag 40mm through ammo belt 40mm sections into its belt face.': '扳机机械连杆超 0.75 时以每秒 2 发、850 米/秒射速发射 40 枚 365mm 弹，经 40mm 弹匣与 40mm 弹链段供弹至其弹链面。', 'Fits a top rail on its own, in place of a scope. Night vision, 8 degree field of view. Needs a battery cell and must be switched on. Has a side rail for a gun torch or laser sight.': '独立装于顶部导轨以替代瞄准镜，夜视，视场角 8 度，需电池并需开启，侧导轨可装枪灯或激光瞄具。', 'Takes a battery cell, lasts about 8 h. 6 channels. Voice reaches radios on the same channel up to 2000 m, weaker with distance. Hold secondary to transmit, reload to change channel.': '使用一节电池（约 8 小时），6 信道；同信道电台通联至 2000 米（随距离减弱），按住副键发话，装填键换信道。', 'Fits a top rail on its own, in place of a scope. Night vision, 16 degree field of view. Needs a battery cell and must be switched on. Has a side rail for a gun torch or laser sight.': '独立装于顶部导轨以替代瞄准镜，夜视，视场角 16 度，需电池并需开启，侧导轨可装枪灯或激光瞄具。', 'Advances 40 365mm shells one slot every 0.25 s while its small torque face turns above 0.1 rps; reverse rotation feeds backwards. Shells pushed off an open belt end drop to the floor.': '小扭矩面转速超 0.1 转/秒时每 0.25 秒推进 40 枚 365mm 弹一格，反转反向供弹，开放链端推出的弹落地。', 'Driven by torque face. One-way gas pump: flows inlet to outlet whichever way the shaft turns. Head 1 kPa per rps. Feed an air manifold above 9.8 kPa for extra engine power. Small pipe.': '由扭矩面驱动，单向气泵：无论轴向如何都从入口流向出口，扬程每转 1 kPa，给进气歧管供超 9.8 kPa 可增功，小号管。', 'Driven by torque face. Fit two liquid ports; pumps from the first fitted to the second. Reverse the shaft or set reverse in properties to swap direction. Flow factor set in properties.': '由扭矩面驱动，装两个液端口，从先装的泵向后装的；反转轴或在属性设反向可换向，流量系数在属性中设置。', 'Driven by torque face. One-way gas pump: flows inlet to outlet whichever way the shaft turns. Head 1 kPa per rps. Feed an air manifold above 9.8 kPa for extra engine power. Large pipe.': '由扭矩面驱动，单向气泵：无论轴向如何都从入口流向出口，扬程每转 1 kPa，给进气歧管供超 9.8 kPa 可增功，大号管。', 'Takes an M2, grenade launcher or minigun and its matching ammo can. Interact to man it, also from a seat. Traverse up to 90 degrees each side and elevation 45 degrees, set in properties.': '装 M2/榴弹发射器/加特林及配套弹箱，交互或从座椅操控，水平每侧至多 90 度、俯仰 45 度，属性中设置。', 'Place a latch knuckle on it in the editor to start a latched body. Locks to a knuckle within one voxel; mechanical link of 0.5 or more unlatches. Data outputs is_connected and is_engaged.': '编辑器中在其上放锁扣座即可建立锁扣体，锁定一格内锁扣；机械连杆 ≥0.5 解锁，数据输出 is_connected 与 is_engaged。', 'Place a latch knuckle on it in the editor to start a latched body. Locks to a knuckle within one voxel whenever released; hold to unlatch and pull. Data outputs is_connected and is_engaged.': '编辑器中在其上放锁扣座即可建立锁扣体，释放时锁入一格内锁扣，按住解锁并拉出，数据输出 is_connected 与 is_engaged。', 'Fits a small engine. Shift by mechanical link: above 0.75 shifts up, below -0.75 shifts down, return to centre between shifts. Stretch for 2 to 8 gears. Ratios and reverse set in properties.': '适配小型发动机，机械连杆换挡：超 0.75 升挡、低于 -0.75 降挡，两次换挡间回中；拉伸可得 2 到 8 挡，齿比与倒挡在属性中设置。', 'Fits truck wheel items. Drive from torque face. Hydraulic steering up to 40 degrees from two liquid nodes. Spring brake: held on until gas pressure passes 39.2 kPa, fully released at 58.8 kPa.': '适配卡车车轮物品，由扭矩面驱动，双液节点液压转向至多 40 度；弹簧刹车：气压超 39.2 kPa 松、58.8 kPa 全松。', 'Place a hinge knuckle on it in the editor to start a hinged body, or interact to connect or release a knuckle within one voxel. Swings up to 180 degrees; min and max properties narrow the range.': '编辑器中在其上放铰链座即可建立铰接体，或交互连接/释放一格内锁扣，最大摆动 180 度，属性可限范围。', 'Holds a stack of one building piece. Snaps to the building grid. Rotate up or down cycles variants. Floor pieces placed on bare terrain start a new structure. Free in sandbox or a creative dome.': '叠放一种建筑件，吸附建筑网格，上/下旋转切换变体，地形上放地板件即新建结构，沙盒或创造穹顶内免费。', 'Bullets and melee weapon hits on the plates do no damage. Zombie attacks are not blocked. 3 attachment points for pouches, radios, lights, rope and patches. Insulation 3.3 C. Rain resistance 40%.': '板材免疫枪弹与近战伤害（僵尸攻击除外），3 个挂载点可挂腰包、电台、灯具、绳索与补丁，保温 3.3 C，防雨 40%。', 'Place a rail ballscrew slider on it in the editor to start a driven sliding body. Turn its small torque face to move the slider, about 12.6 mm per revolution. Locks at either end. Takes one slider.': '编辑器中在其上放滚珠丝杠滑块即可建立从动滑动体，转动小扭矩面驱动滑块，每转约 12.6 毫米，两端锁定，容一个滑块。', 'Fires one 120 570mm shell at 1600 m/s. Fit gas port on the breech: above 4.9 kPa the breech opens to load a shell by hand, vent to close. Fires when closed and trigger mechanical link is above 0.75.': '发射一枚 120×570mm 弹，初速 1600 米/秒；炮尾装气端口：超 4.9 kPa 开膛人工装弹、泄气关膛，闭膛且扳机机械连杆超 0.75 时击发。', 'Bullets and melee weapon hits on the helmet do no damage. Zombie attacks are not blocked. Mounts a helmet torch, strobe light, night vision goggles and one pouch. Insulation 1 C. Rain resistance 20%.': '头盔免疫枪弹与近战伤害（僵尸攻击除外），可装头盔灯、频闪灯、夜视镜与一个腰包，保温 1 C，防雨 20%。', 'Takes an ir missile. Aim down the sight and stand still on a vehicle over 500 kg, in clear view within 2000 m, for 6 s to lock. The missile climbs to 200 m then dives on the target. 12 m blast radius.': '装红外导弹：沿瞄具瞄准，在 500 公斤以上载具上静止且 2000 米内无遮挡 6 秒锁定，导弹爬升到 200 米后俯冲，爆炸半径 12 米。', 'Splits input to left and right outputs at a set ratio. Outputs turn together. Ratio set by input and output properties, 1 to 8. Mechanical link above 0.75 disconnects both outputs, below 0.25 reconnects.': '把输入按设定齿比分给左右输出，输出同转；齿比由输入输出属性设定（1 到 8），机械连杆超 0.75 分离两输出、低于 0.25 接合。', 'Draws 20 W. Fit electric port. Channels 0 to 5. While transmitting sends its signal and 8 bool, 8 integer and 8 number data inputs; otherwise receives the strongest same-channel transmitter within 2000 m.': '功耗 20 W，适配电力端口，信道 0 到 5；发射时送出信号与 8 组布尔/整数/数值数据输入，否则接收 2000 米内最强同信道发射端。', 'Holds a stack of one component type. Hold primary to place; a placement costs 1, more when stretched. Drag the handles of stretchable parts, then confirm with secondary. Free in sandbox or a creative dome.': '叠放一种组件，按住主键放置；每次放置耗 1（拉伸件更多），拉伸件拖动手柄后副键确认，沙盒或创造穹顶内免费。', 'Cylinder end of a hydraulic ram. Link to a same-size hydraulic connector with the hydraulic tool; the gap when linked sets the length. Liquid nodes A and B: fluid into A extends, into B retracts. 8 L per m.': '液压缸的缸端，用液压工具连接同尺寸液压接头，连接时的间距即行程；液节点 A/B：进 A 伸出、进 B 缩回，每米 8 升。', 'Cylinder end of a hydraulic ram. Link to a same-size hydraulic connector with the hydraulic tool; the gap when linked sets the length. Liquid nodes A and B: fluid into A extends, into B retracts. 16 L per m.': '液压缸的缸端，用液压工具连接同尺寸液压接头，连接时的间距即行程；液节点 A/B：进 A 伸出、进 B 缩回，每米 16 升。', 'Cylinder end of a hydraulic ram. Link to a same-size hydraulic connector with the hydraulic tool; the gap when linked sets the length. Liquid nodes A and B: fluid into A extends, into B retracts. 24 L per m.': '液压缸的缸端，用液压工具连接同尺寸液压接头，连接时的间距即行程；液节点 A/B：进 A 伸出、进 B 缩回，每米 24 升。', 'Driven by torque face. Fit 2 to 6 rotor blade items, 2 to 8 m. Lift rises with rps, blade length and count. Pitch, left roll and right roll are mechanical links; collective is the average of both roll inputs.': '由扭矩面驱动，装 2 至 6 片桨叶物品（2 至 8 米），升力随转速、桨长与片数上升；俯仰与左右横滚为机械连杆，总距为两横滚输入的平均值。', 'Connects a mechanical out node to a mechanical in node. Drag from one node to another on the same vehicle. Primary in empty space adds a waypoint. Dragging onto an existing link removes it. Secondary cancels.': '连接机械输出节点到机械输入节点：同载具上从一个节点拖到另一个，空处按主键加中间点，拖到已有连杆上为删除，副键取消。', 'Takes a steering wheel, flight stick or flight yoke on its main control face and up to 8 throttles or shifters on its side faces. Controls must be the same way up as the seat; one facing backwards is inverted.': '主控制面装方向盘/飞行杆/操纵盘，侧面至多装 8 个油门或换挡器；控制器须与座椅同向，反向安装即反向。', 'Secondary cycles copy, paste and delete. Copy: hold on a vehicle and drag to select. Paste is free. Reload saves to or loads from a file or the workshop. Paste and delete only work in sandbox or a creative dome.': '副键循环 复制/粘贴/删除：复制=在载具上按住并拖选，粘贴免费，装填键存取文件或创意工坊，粘贴与删除仅限沙盒或创造穹顶。', 'Fits a large engine. Shifts pneumatically: fit two gas ports, first placed shifts up, second shifts down. A pulse above 29.4 kPa shifts once and must drop below 19.6 kPa before the next. Stretch for 2 to 8 gears.': '适配大型发动机，气动换挡：装两个气端口，先装的升挡、后装的降挡，超 29.4 kPa 脉冲换挡一次、须落回 19.6 kPa 以下才可再换，拉伸可得 2 到 8 挡。', 'Fits a medium engine. Shifts pneumatically: fit two gas ports, first placed shifts up, second shifts down. A pulse above 29.4 kPa shifts once and must drop below 19.6 kPa before the next. Stretch for 2 to 8 gears.': '适配中型发动机，气动换挡：装两个气端口，先装的升挡、后装的降挡，超 29.4 kPa 脉冲换挡一次、须落回 19.6 kPa 以下才可再换，拉伸可得 2 到 8 挡。', 'Fits either side of the jet engine in the jet chain. Six torque faces turn with the engine shaft; drive one to start the engine or take power from it. Gear ratio 1 to 128, set in properties. Fit two oil manifolds.': '装于喷气链中喷气发动机两侧，六个扭矩面随发动机轴转动，驱动一个即可启动或取力，齿比 1 到 128 在属性中设置，装两个机油歧管。', 'Connects a hydraulic connector node to a hydraulic connector base node of the same size, on the same or another vehicle. One connection per node. The cylinder is built to the measured span. Use again to disconnect.': '把液压接头节点连到同尺寸液压接头座节点（可跨载具），每节点一连接，缸体按实测跨距生成，再次使用断开。', 'Splits input to left and right outputs at a set ratio. Outputs turn together. Rear output passes input through at 1:1. Ratio set by input and output properties, 1 to 8. Mechanical link above 0.75 disconnects both outputs.': '把输入按设定齿比分给左右输出，输出同转，后输出 1:1 直通；齿比 1 到 8，机械连杆超 0.75 分离两输出。', 'One can, one colour. Secondary cycles fill, brush, pencil, erase brush, erase pencil and flood. Fill paints a component, edge, plate face or cable. Brush and pencil draw on plates. Flood recolours every match on the vehicle.': '一罐一色，副键循环 填充/刷/铅笔/擦刷/擦笔/漫灌；填充上色组件/边/板面/线缆，刷与铅笔在板上作画，漫灌重涂全车同色。', 'Consumes fuel and air. Produces exhaust. Requires 6 rps to start. Fit air manifold, fuel manifold, input and output oil manifolds, input and output coolant manifolds. Max temp 160C. Compatible with small engine wheel, small gearbox.': '燃油与空气混合燃烧，排出废气，需 6 转/秒启动；装进气歧管、燃油歧管、进出机油歧管与进出冷却液歧管，最高温度 160C，兼容小发动机轮与小变速箱。', 'Consumes fuel and air. Produces exhaust. Requires 6 rps to start. Fit air manifold, fuel manifold, input and output oil manifolds, input and output coolant manifolds. Max temp 160C. Compatible with large engine wheel, large gearbox.': '燃油与空气混合燃烧，排出废气，需 6 转/秒启动；装进气歧管、燃油歧管、进出机油歧管与进出冷却液歧管，最高温度 160C，兼容大发动机轮与大变速箱。', 'Consumes fuel and air. Produces exhaust. Requires 6 rps to start. Fit air manifold, fuel manifold, input and output oil manifolds, input and output coolant manifolds. Max temp 160C. Compatible with medium engine wheel, medium gearbox.': '燃油与空气混合燃烧，排出废气，需 6 转/秒启动；装进气歧管、燃油歧管、进出机油歧管与进出冷却液歧管，最高温度 160C，兼容中发动机轮与中变速箱。', 'Burns petrol with outside air. Requires a jet compressor upstream and a jet exhaust downstream on its jet faces. Fit jet fuel manifold and two oil manifolds. Requires 2 rps to start, spun up through a jet gearbox. Max temp 1400C. Wears without a jet particle separator.': '汽油与外部空气混合燃烧，上游需喷气压气机、下游需喷气尾喷管；装喷气燃油歧管与两个机油歧管，需 2 转/秒启动（经喷气变速箱带转），最高温度 1400C，无颗粒分离器会磨损。'}   # 兜底用的人工译文（仅当官方描述表缺失时启用）
STATE_FILE = "安装状态.json"


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


def active_tsvs(rom):
    """返回当前游戏实际存在的语言表（5 表 + 25480554 起新增的描述表）。"""
    return [n for n in TSVS + TSVS_OPTIONAL if os.path.isfile(os.path.join(rom, n))]


def official_desc_map(rom):
    """官方描述译文：新增描述表按 id → zh（25480554+ 官方自带 316+348 条全量中文）。"""
    out = {}
    for n in TSVS_OPTIONAL:
        p = os.path.join(rom, n)
        if not os.path.isfile(p):
            continue
        rows, _, _ = tsv_rows(p)
        h = rows[0]
        ii, iz = h.index(b"id"), h.index(b"zh")
        for r in rows[1:]:
            if len(r) > iz and r[iz].strip():
                out[r[ii].decode()] = r[iz].decode()
    return out


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
    converted = [n for n in active_tsvs(rom) if not pristine(os.path.join(rom, n))]
    if converted:
        bdir = os.path.join(here(), "备份_tsv")
        if all(os.path.isfile(os.path.join(bdir, n)) for n in active_tsvs(rom)):
            src_rom = bdir
            print("检测到 TSV 已汉化：翻译对照改用首次安装备份。")
        else:
            sys.exit(f"TSV 已汉化但缺少原始备份（{converted}）。\n"
                     "请先在 Steam 中『验证文件完整性』恢复官方文件后重试。")
    for n in active_tsvs(rom):
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
    for n in active_tsvs(rom):
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
    # 描述译文：优先官方新增描述表的 zh 列（25480554+，316+348 条全量官方中文）；
    # 仅当游戏无描述表（旧版）时才退回内置人工译文 DESCS。
    off_desc = official_desc_map(rom)
    use_official = bool(off_desc)
    print(f"  描述译文来源：{'官方描述表 ' + str(len(off_desc)) + ' 条' if use_official else '内置人工译文（无官方描述表）'}")
    for name, mapping in maps.items():
        p = os.path.join(data, name)
        if not os.path.isfile(p):
            print(f"  跳过缺失文件: {name}")
            continue
        with open(p, encoding="utf-8") as fh:
            j = json.load(fh)
        hit = dhit = 0
        for e in j["definitions"]:
            eid = e.get("id", "")
            zh = mapping.get(eid)
            if zh and e.get("name") != zh:
                e["name"] = zh
                hit += 1
            d = e.get("description")
            if d:
                dzh = off_desc.get(eid) or (None if use_official else DESCS.get(d))
                if dzh and d != dzh:
                    e["description"] = dzh
                    dhit += 1
        if hit or dhit:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(j, fh, ensure_ascii=False, indent=4)
                fh.write("\n")
        print(f"  {name}: name 汉化 {hit} 条，描述汉化 {dhit} 条")


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
    for n in active_tsvs(rom):
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


def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def fetch_update_info():
    req = urllib.request.Request(UPDATE_JSON_URL,
                                 headers={"User-Agent": f"anymaker-zh-patch/{VERSION}"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def download_dict(info):
    last_err = None
    for url in (info.get("dict_url"), info.get("dict_mirror")):
        if not url:
            continue
        try:
            req = urllib.request.Request(url,
                                         headers={"User-Agent": f"anymaker-zh-patch/{VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            want = (info.get("dict_sha256") or "").lower()
            got = hashlib.sha256(data).hexdigest()
            if want and got != want:
                raise RuntimeError(f"词典 SHA-256 校验不符（期望 {want[:12]}… 实得 {got[:12]}…），已放弃")
            return data
        except Exception as e:
            last_err = e
    raise RuntimeError(f"全部下载源失败：{last_err}")


def do_update(interactive=True):
    """检查汉化更新；有则询问并更新词典+重装。网络失败如实打印。返回 True=已更新。"""
    try:
        info = fetch_update_info()
    except Exception as e:
        print(f"⚠ 更新检查失败：无法连接 GitHub（{type(e).__name__}: {e}）")
        print("  本次跳过更新检查，安装/卸载功能不受影响。")
        return False
    remote = str(info.get("version", "0"))
    if _version_tuple(remote) <= _version_tuple(VERSION):
        print(f"汉化已是最新（v{VERSION}，{info.get('date', '')}）")
        return False
    print(f"★ 发现汉化更新 v{remote}（当前 v{VERSION}）")
    print(f"  更新说明：{info.get('notes', '')}")
    print(f"  安装器新版本：{info.get('release_url', GITHUB_RELEASES)}（exe 本体需手动下载替换）")
    if interactive:
        try:
            if not sys.stdin.isatty():
                print("  [非交互环境] 未自动更新——可运行 update 子命令或菜单 4 手动更新")
                return False
            ans = input("  是否更新词典并重新应用汉化？[Y/n]: ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("", "y", "yes"):
            print("  已跳过更新。")
            return False
    try:
        data = download_dict(info)
    except Exception as e:
        print(f"⚠ 更新失败（词典下载/校验）：{e}")
        return False
    p = os.path.join(here(), "润色词典.csv")
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(here(), "润色词典.bak.csv"))
    open(p, "wb").write(data)
    print("  词典已更新（旧版备份为 润色词典.bak.csv），正在重新应用汉化…")
    with _Tee(os.path.join(here(), "安装日志.txt")):
        _do_install()
    return True


def check_game_update():
    """检测游戏 buildid 是否自上次安装后变化。返回 (旧, 新) 或 None。"""
    p = os.path.join(here(), STATE_FILE)
    if not os.path.exists(p):
        return None
    try:
        st = json.load(open(p, encoding="utf-8"))
        old = st.get("buildid")
        game, acf = find_game()
        new = buildid(acf)
        return (old, new) if old and old != new else None
    except Exception:
        return None


def save_state(game, bid):
    import datetime
    with open(os.path.join(here(), STATE_FILE), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"installer_version": VERSION, "buildid": bid,
                   "date": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")


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
    save_state(game, bid)
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
    for n in active_tsvs(rom) + [FONT_REG] + JSONS:
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
        {"install": cmd_install, "status": cmd_status, "uninstall": cmd_uninstall,
         "update": lambda: do_update(interactive=sys.stdin.isatty())}.get(
            cmd, lambda: print(__doc__))()
    else:
        # 启动即自动检查汉化更新 + 游戏版本变动检测（网络失败如实提示后继续）
        do_update(interactive=True)
        gu = check_game_update()
        if gu:
            old, new = gu
            print(f"★ 游戏已更新（buildid {old} → {new}），官方更新覆盖了汉化的部分文件。")
            try:
                ans = input("  是否立即重新应用汉化？[Y/n]: ").strip().lower() if sys.stdin.isatty() \
                    else "n"
            except EOFError:
                ans = "n"
            if ans in ("", "y", "yes"):
                with _Tee(os.path.join(here(), "安装日志.txt")):
                    _do_install()
            else:
                print("  已跳过——稍后可在菜单选 1 重新应用。")
        print()
        print("==== Anymaker 简中汉化包 ====")
        print("  1) 安装 / 更新汉化")
        print("  2) 查看状态")
        print("  3) 卸载，还原官方文件")
        print("  4) 检查汉化更新")
        print("  0) 退出")
        try:
            choice = input("请选择 [1/2/3/4/0]: ").strip()
        except EOFError:
            choice = "2"
        {"1": cmd_install, "2": cmd_status, "3": cmd_uninstall,
         "4": lambda: do_update(interactive=True)}.get(choice, lambda: None)()
