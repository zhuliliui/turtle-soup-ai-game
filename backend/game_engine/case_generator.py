"""案件生成器 - 根据用户身份生成定制海龟汤"""
from typing import Dict, List, Optional, Tuple
from models.game_state import CaseInfo, Clue
from ai_host.llm_client import LLMError, extract_json
import uuid


class CaseGenerator:
    """根据身份和学习内容生成定制化案件"""

    def __init__(self, llm_client):
        self.llm = llm_client
        # 两层生成缓存：真相层按事件缓存（同事件换身份=同一个案子），视角层按（事件,身份）缓存
        self._truth_cache: Dict[str, Dict] = {}
        self._perspective_cache: Dict[Tuple[str, str], Dict] = {}

    async def generate_case(
        self,
        identity: str,
        mode: str = "entertainment",
        learning_context: Optional[Dict] = None,
        clue_count: int = 3
    ) -> CaseInfo:
        """生成案件（clue_count：按玩家等级决定的开局线索数）"""

        if mode == "entertainment":
            return await self._generate_entertainment_case(identity, clue_count)
        else:
            return await self._generate_learning_case(identity, learning_context, clue_count)

    # ==================== 两层生成架构 ====================
    # 真相层（事件决定，与身份无关）+ 视角层（身份决定线索与专属行动）
    # 同一事件换不同身份开局 = 同一个案子、不同的情报入口

    async def generate_case_from_premise(
        self, premise: str, on_status=None, clue_count: int = 3
    ) -> Tuple[CaseInfo, str]:
        """一句话生成海龟汤（两层架构）

        on_status: 异步回调，用于向前端推送生成进度（"正在提取身份..."等）
        clue_count: 按玩家等级决定的开局线索数

        返回: (案件信息, 玩家身份)
        """
        premise = (premise or "").strip()[:500]

        async def _status(text: str):
            if on_status:
                try:
                    await on_status(text)
                except Exception:
                    pass

        # 第一步：拆分事件与身份（轻量调用）
        await _status("🔍 正在分析你的一句话...")
        try:
            split = await self._extract_event_identity(premise)
            event = (split.get("event") or "").strip()
            identity = (split.get("identity") or "").strip()
        except Exception as e:
            print(f"[案件生成] 事件/身份拆分失败: {e}，整句按原话处理")
            event, identity = premise, ""

        # 类型B：只有身份没有事件 → 原创贴合身份的案件（单次生成，不走缓存）
        if not event:
            await _status("🎭 正在围绕你的身份原创案件...")
            return await self._generate_case_one_shot(premise)

        # 类型A：有事件 → 先真相层（事件级缓存，同事件换身份直接复用）
        await _status("🧩 正在构建案件真相...")
        try:
            truth_core = await self._get_truth_core(event)
        except Exception as e:
            print(f"[案件生成] 真相层生成失败: {e}，回退单次生成")
            return await self._generate_case_one_shot(premise)

        final_identity = identity or "侦探"

        # 视角层：初始线索/隐藏线索/身份专属行动（事件+身份级缓存）
        await _status(f"👁 正在生成「{final_identity}」视角的线索与行动...")
        try:
            layer = await self._get_perspective_layer(event, final_identity, truth_core, clue_count)
        except Exception as e:
            print(f"[案件生成] 视角层生成失败: {e}，回退单次生成")
            return await self._generate_case_one_shot(premise)

        case = self._compose_case(truth_core, layer)
        return case, final_identity

    async def _extract_event_identity(self, premise: str) -> Dict:
        """从一句话中拆分出事件和身份（轻量调用，max_tokens很小所以快）"""
        prompt = f"""
分析这句话，拆分出"事件"和"玩家身份"两部分。

句子："{premise}"

规则：
- 身份：句子中以"我是..."表达的玩家角色（如"我是他的老师"→"老师"）；没有则填空字符串
- 事件：句子中描述的具体事件/事故/案件（如"小明昨晚失踪了"）；只保留事件本身的描述；只有身份没有事件则为空字符串
- 第一人称经历（重要）：若句子是"我……"的亲身经历描述（如"我在医院醒来，记不起自己是谁"），则：
  * 身份 = 这位第一人称当事人的角色称呼（如"失忆的住院病人"）
  * 事件 = 改写为第三人称的同一事件（如"有人在医院醒来，失去了记忆"）

只返回JSON：
{{"event": "事件原文，无则空字符串", "identity": "身份，无则空字符串"}}
"""
        data = await self.llm.generate_json(prompt, max_tokens=300, temperature=0.1)
        return {
            "event": str(data.get("event") or "").strip(),
            "identity": str(data.get("identity") or "").strip()
        }

    async def _get_truth_core(self, event: str) -> Dict:
        """真相层：由事件决定，与玩家身份无关。同一事件命中缓存直接复用（换身份秒出同一个案子）"""
        key = event.strip()
        if key in self._truth_cache:
            print(f"[案件生成] 真相层命中缓存: {key[:30]}")
            return self._truth_cache[key]

        prompt = f"""
你是一个海龟汤案件设计大师。请围绕下面这个事件，设计海龟汤案件的"真相内核"。

事件："{event}"

要求：
1. 真相要有反转、符合逻辑、有悬疑感，不能一眼看穿
2. 背景与现场描述保持中立客观，不要面向任何特定身份的玩家（后续会按玩家身份生成视角线索）
3. 待解谜团2-4个
4. 自洽约束（非常重要）：background 与 scene_description 必须包含至少一处能支撑真相反转的铺垫——
   真相里的关键实体（家族、公司、婚约、仇怨、职业等）要在背景或现场中点到名字或明显暗示，
   禁止让后续线索引用一个背景完全没铺垫、凭空冒出来的家族/组织/情节
5. 禁止悬空伏笔（与要求4配套）：background / scene_description / victim_info 里写下的每一条显著事实
   （人物关系、异常事件、反常举动），都必须在 truth 的五个字段中被实际使用、解释或明确点破其干扰作用。
   写真相前先逐条自查：背景里的每个反常点，真相接住了吗？接不住的就不要写进背景——宁可背景朴素，
   也不留「这句话到底干嘛的」的废线。
6. 反转必须是颠覆而非补充：twist 不能只是「把表面事件补充完整」的平铺真相。
   标准：玩家只看背景时会形成某个自然判断（谁是坏人/什么性质/谁可疑），twist 必须推翻或反转这个判断——
   揭晓后玩家的反应应是「原来根本不是这样」。检验法：把 twist 遮住，若背景+常识足以推出真相，就是失败的反转；
   反转的线索依据要能回溯到背景或谜团（情理之中），但结论必须出乎意料（意料之外）。

只返回JSON：
{{
    "title": "案件标题",
    "background": "事件背景（中立描述，2-3句话）",
    "victim_info": "关键人物信息",
    "scene_description": "现场描述",
    "truth": {{
        "who": "真凶/关键人物",
        "what": "真正发生了什么",
        "why": "动机",
        "how": "手法",
        "twist": "反转点"
    }},
    "mysteries": ["待解谜团1", "待解谜团2"]
}}
"""
        data = await self.llm.generate_json(prompt, max_tokens=1500, temperature=0.8)
        if not data.get("title") or not isinstance(data.get("truth"), dict):
            raise ValueError("真相内核缺少标题或truth")
        self._truth_cache[key] = data
        return data

    async def _get_perspective_layer(
        self, event: str, identity: str, truth_core: Dict, clue_count: int = 3
    ) -> Dict:
        """视角层：初始线索/隐藏线索/身份专属行动，由身份决定。同事件+同身份+同线索数命中缓存"""
        clue_count = max(1, int(clue_count or 3))
        key = (event.strip(), identity.strip(), clue_count)
        if key in self._perspective_cache:
            print(f"[案件生成] 视角层命中缓存: {identity} @ {event[:20]} (线索{clue_count})")
            return self._perspective_cache[key]

        t = truth_core.get("truth") or {}
        truth_brief = (
            f"谁：{t.get('who', '')}\n发生了什么：{t.get('what', '')}\n"
            f"动机：{t.get('why', '')}\n手法：{t.get('how', '')}\n反转点：{t.get('twist', '')}"
        )

        prompt = f"""
你是一个海龟汤案件设计大师。案件真相已经确定，现在要为一位特定身份的玩家生成"视角情报"。

事件："{event}"
玩家身份：{identity}

案件真相（玩家不可见，仅用于保证线索与真相强相关）：
{truth_brief}

初始线索的核心规则（非常重要）：
- **必须正好生成 {clue_count} 条初始线索**（这是玩家当前等级对应的开局线索数，多一条少一条都不行）
- 每条初始线索必须严格从玩家身份的第一人称视角出发，只写"这个身份的人才知道、才能观察到、才能接触到"的信息
- 【交互形态硬约束】本游戏是纯语言问答游戏，玩家只能说话（提问/打听/陈述），不能做肢体动作：
  所有线索、身份行动必须通过"观察、听说、回忆、打听、灵体感知"等非肢体方式获得；
  禁止出现"翻找、搜查、翻阅、潜入、撬锁、搬运"等需要肢体操作的描述；
  玩家是鬼魂时更不能触碰实物（碰不到任何东西），只能用灵体感知替代（如"飘近办公桌，桌面残留的记忆碎片涌入脑海"）
- 换一个身份开局，初始线索集合应当明显不同（视角决定情报），但案件真相不变
- 每条线索附 perspective 字段，不超过12个字，简短标注情报来源（示例：委托信息、职业观察、现场亲历、邻居闲谈），禁止写成长句
- 自洽约束：线索里出现的人名、家族、公司、组织、事件，必须能在事件原文或案件真相里找到出处；
  禁止编造真相中不存在的新的家族/势力/前史（如真相没提"抢亲"，线索就不得出现"抢亲"情节）
- 【玩家人物卡一致性】在 scene_intro 中给玩家明确的剧中称呼（可含姓名），姓名与性别必须与玩家身份匹配
  （如"十八线女明星"→女性人物，绝不能写成男性）；后续线索引用玩家时一律用同一称呼；
  玩家人物卡与其他角色（凶手/死者/嘉宾等）严格区分，绝不能把玩家混同或替换成另一个人

身份专属行动规则：
- 设计2个只有这个身份才能执行的调查行动（如老师→调阅请假记录；警察→申请技术侦查）
- result 字段写执行后获得的情报：必须与真相强相关、有推理价值，以第一人称视角描述
- 行动不能直接揭示全部真相，而是提供关键拼图

可询问人物规则：
- 列出4-6个与案件相关、且玩家这个身份在剧情中能接触到的人物（如小区保安、死者的室友、物业前台）
- 用简短称呼（2-6字），不要重复玩家自己的身份

玩家死亡规则（玄幻设定，非常重要）：
- 默认玩家是活着的角色；但若玩家身份在剧情中已经死亡（如"坠楼的女孩""遇害的学生"），不要回避——
  启用玄幻设定：玩家以鬼魂/灵体状态开局，保留完整调查能力（飘行观察、触碰物品感知残留记忆、
  对感知敏感者低语等），scene_intro 开头即交代灵体状态与玄幻世界观
- 鬼魂视角下：身份专属行动要符合灵体能力（如"回溯死亡时刻""附身旁观""托梦示警"）；
  可询问人物中安排1-2位能感知灵体的角色（灵媒、小孩、猫狗、濒死老人）
- 玄幻元素只用于解释玩家视角，案件真相本身保持现实逻辑；twist 可以与"玩家已死"有关（玩家自己最初不知道自己死了），制造反转

只返回JSON：
{{
    "scene_intro": "第一人称开场（2句话：你是谁、你与这个事件的关系、你此刻的状态）",
    "revealed_clues": [
        {{"content": "初始线索（身份视角）", "critical": false, "perspective": "来源标注（≤12字，如：委托信息）"}}
    ],
    "hidden_clues": [
        {{"content": "隐藏线索", "critical": true, "trigger": "触发条件", "perspective": "来源标注（≤12字，如：身份情报）"}}
    ],
    "identity_actions": [
        {{"name": "行动名（不超过8字）", "desc": "行动说明（一句话）", "result": "执行后获得的情报（身份视角，与真相强相关）"}}
    ],
    "askable_people": ["人物称呼1", "人物称呼2"]
}}
初始线索必须正好 {clue_count} 条，隐藏线索2-3条。
"""
        data = await self.llm.generate_json(prompt, max_tokens=2000, temperature=0.7)
        if not data.get("revealed_clues"):
            raise ValueError("视角层缺少初始线索")
        # 严格对齐到等级要求的线索数（LLM 常不守条数）
        data["revealed_clues"] = self._fit_clue_count(data.get("revealed_clues"), clue_count)
        self._perspective_cache[key] = data
        return data

    def _compose_case(self, truth_core: Dict, layer: Dict) -> CaseInfo:
        """真相层+视角层组装成案件（背景前置第一人称开场，增强代入感）"""
        intro = str(layer.get("scene_intro") or "").strip()
        background = truth_core.get("background") or ""
        if intro:
            background = f"{intro}\n\n{background}"

        case_data = {
            "title": truth_core.get("title"),
            "background": background,
            "victim_info": truth_core.get("victim_info"),
            "scene_description": truth_core.get("scene_description"),
            "truth": truth_core.get("truth") or {},
            "mysteries": truth_core.get("mysteries") or [],
            "revealed_clues": layer.get("revealed_clues") or [],
            "hidden_clues": layer.get("hidden_clues") or []
        }
        case = self._build_case_info(case_data)
        case.identity_actions = [
            {"name": str(a.get("name")).strip(), "desc": str(a.get("desc") or "").strip(), "result": str(a.get("result")).strip()}
            for a in (layer.get("identity_actions") or [])
            if isinstance(a, dict) and a.get("name") and a.get("result")
        ]
        case.askable_people = [
            str(p).strip() for p in (layer.get("askable_people") or [])
            if isinstance(p, str) and p.strip()
        ][:6]
        return case

    # ==================== 单次生成（兜底路径） ====================

    async def _generate_case_one_shot(self, premise: str) -> Tuple[CaseInfo, str]:
        """单次调用生成完整案件（两层架构任一环节失败时的兜底）"""
        premise = (premise or "").strip()[:500]

        prompt = f"""
你是一个海龟汤案件设计大师。玩家用一句话给出了故事起点和/或自己的身份。

玩家的一句话："{premise}"

先判断句子类型，再按对应方式设计案件：
- 类型A【身份+事件】（如"小明昨晚失踪了。我是他的老师"）：提取玩家身份，以该事件为案件核心扩写
- 类型B【只有身份】（如"我是一个学生"、"我是个医生"，没有具体事件）：提取玩家身份，围绕这个身份的日常视角，原创设计一个该身份会卷入的悬疑案件（如学生→校园悬疑；医生→医院谜案），案件要贴合身份视角、合理可信
- 句子里没有任何身份信息：身份默认"侦探"，围绕句子内容（若有）或自由原创案件

【玩家死亡=鬼魂视角（玄幻设定）】若玩家身份在剧情中已经死亡，玩家以鬼魂/灵体状态开局：
保留调查能力（飘行观察、触碰物品感知残留记忆、托梦示警等），开场背景交代灵体设定与玄幻世界观；
初始线索与身份行动符合鬼魂视角，可加入1-2位能感知灵体的角色（灵媒、小孩、猫狗、濒死老人）。
玄幻只用于解释玩家视角，案件真相保持现实逻辑；twist 可与"玩家已死"相关制造反转。

【玩家人物卡一致性（非常重要）】
- 为玩家固定唯一的人物卡：姓名、性别、身份，必须与玩家给出的身份匹配
  （如"十八线女明星"→女性人物；绝不能把玩家写成男性角色）
- 全篇（背景、现场、线索、真相 who 字段、可询问人物）中"玩家这个人物"的姓名和性别保持唯一一致
- 玩家可以是剧情人物之一，但其他关键角色（凶手/死者/嘉宾等）必须是独立于玩家人物卡的其他人，
  不得中途把玩家替换或混同成另一个人物（尤其异性角色）
- 若剧情含灵魂互换等玄幻设定：玩家人物卡以"灵魂所属"为准（性别随玩家身份），
  身壳变化只能作为 twist 揭示，不得推翻玩家人物卡的姓名与性别

任务：
1. 提取玩家身份（如"我是他的老师"→"老师"；"我是个学生"→"学生"）
2. 以上述方式确定案件核心，扩写成完整的海龟汤案件
3. 真相要有反转、符合逻辑、有悬疑感，不能一眼看穿。反转必须是颠覆而非补充：
   twist 不能只是"把表面事件补充完整"，要推翻玩家根据背景形成的自然判断（谁是坏人/什么性质/谁可疑），
   揭晓后玩家的反应应是"原来根本不是这样"
4. 初始线索2-4条，隐藏线索2-3条（需深入推理才能发现）
5. 待解谜团2-4个

初始线索的核心规则（非常重要）：
- 每条初始线索必须严格从玩家身份的第一人称视角出发，只写"这个身份的人才知道、才能观察到、才能接触到"的信息
- 【交互形态硬约束】本游戏是纯语言问答游戏，玩家只能说话（提问/打听/陈述），不能做肢体动作：
  所有线索必须通过"观察、听说、回忆、打听、灵体感知"等非肢体方式获得；
  禁止出现"翻找、搜查、翻阅、潜入、撬锁、搬运"等需要肢体操作的描述；
  玩家是鬼魂时更不能触碰实物，只能用灵体感知替代
- 线索内容要直接体现身份视角，例如：
  * 老师身份→学生的在校表现、成绩异动、师生谈话内容
  * 警察身份→现场勘查记录、法医初步结论、监控调阅情况
  * 医生身份→体检异常指标、病房观察细节
  * 家长身份→孩子在家反常举动、家庭财务异动
- 每条线索附 perspective 字段，不超过12个字，简短标注情报来源（示例：委托信息、职业观察、现场亲历、邻居闲谈），禁止写成长句
- 同一事件如果换不同身份开局，初始线索的集合应当明显不同（视角决定情报），但案件真相不变

请以JSON格式返回：
{{
    "player_identity": "老师",
    "title": "案件标题",
    "background": "案件背景（基于玩家的一句话自然扩写，2-3句话）",
    "victim_info": "关键人物信息",
    "scene_description": "现场描述",
    "truth": {{
        "who": "真凶/关键人物",
        "what": "真正发生了什么",
        "why": "动机",
        "how": "手法",
        "twist": "反转点"
    }},
    "revealed_clues": [
        {{"content": "初始线索1（以玩家身份视角描述）", "critical": false, "perspective": "来源标注（≤12字，如：委托信息）"}},
        {{"content": "初始线索2（以玩家身份视角描述）", "critical": true, "perspective": "来源标注（≤12字，如：现场亲历）"}}
    ],
    "hidden_clues": [
        {{"content": "隐藏线索1", "critical": true, "trigger": "触发条件", "perspective": "来源标注（≤12字，如：身份情报）"}}
    ],
    "mysteries": ["待解谜团1", "待解谜团2"]
}}
"""

        try:
            response = await self.llm.generate(prompt)
            data = self._parse_case_response(response)

            # 兼容两种返回结构：{player_identity, case:{...}} 或 案件字段直接平铺
            if isinstance(data, dict) and isinstance(data.get("case"), dict):
                identity = str(data.get("player_identity") or "侦探")
                case_data = data["case"]
            else:
                identity = str((data or {}).get("player_identity") or "侦探")
                case_data = data or {}

            if not case_data.get("title"):
                raise ValueError("生成的案件缺少标题")
        except Exception as e:
            print(f"[案件生成] 一句话模式生成失败: {str(e)}，使用模板兜底")
            # 兜底：模板案件 + 玩家原句作为背景开头，身份默认侦探
            case_data = CaseTemplates.get_detective_case()
            case_data["background"] = f"{premise}\n\n" + case_data["background"]
            identity = "侦探"

        return self._build_case_info(case_data), identity

    @staticmethod
    def _fit_clue_count(clues: list, target: int) -> list:
        """把初始线索数量对齐到 target 条。

        LLM 常不严格遵守条数要求：多了就截断（保留 critical 的），
        少了就用通用观察补足，保证「等级 → 线索数」的规则稳定生效。
        """
        target = max(1, int(target or 3))
        clues = list(clues or [])
        # 保证每条线索都有 perspective（身份视角来源），缺失时补默认值
        for c in clues:
            if isinstance(c, dict) and not str(c.get("perspective") or "").strip():
                c["perspective"] = "身份视角"
        if len(clues) > target:
            # 截断时优先保留 critical 线索，维持关键信息不丢
            critical = [c for c in clues if isinstance(c, dict) and c.get("critical")]
            normal = [c for c in clues if not (isinstance(c, dict) and c.get("critical"))]
            return (critical + normal)[:target]
        if len(clues) < target:
            fillers = [
                {"content": "现场有一处细节与常理不符", "critical": False, "perspective": "现场观察"},
                {"content": "某个人的说法前后存在矛盾", "critical": False, "perspective": "走访听闻"},
                {"content": "遗留物品上能找到一条额外线索", "critical": False, "perspective": "物证检查"},
                {"content": "时间线上有一段无法解释的空白", "critical": False, "perspective": "时间核对"},
                {"content": "有人似乎在刻意隐瞒什么", "critical": False, "perspective": "直觉判断"},
                {"content": "现场的气味/温度有异常", "critical": False, "perspective": "感官细节"},
            ]
            i = 0
            while len(clues) < target:
                clues.append(dict(fillers[i % len(fillers)]))
                i += 1
        return clues

    async def _generate_entertainment_case(self, identity: str, clue_count: int = 3) -> CaseInfo:
        """生成纯娱乐模式案件"""
        clue_count = max(1, int(clue_count or 3))

        prompt = f"""
你是一个海龟汤案件设计大师。现在要为一位身份是「{identity}」的玩家生成一个定制化的海龟汤案件。

要求：
1. 案件要符合这个身份的视角和专业背景
2. 真相要有反转，不能一眼看穿
3. **初始线索必须正好 {clue_count} 条**（这是玩家等级对应的开局线索数，多一条少一条都不行）
4. 有2-3条隐藏线索，只有深入推理才能发现
5. 案件要有悬疑感，但真相要符合逻辑
6. 初始线索要从「{identity}」的第一人称视角出发，写这个身份才知道、才能观察到的信息

请以JSON格式返回：
{{
    "title": "案件标题",
    "background": "案件背景（2-3句话）",
    "victim_info": "受害者/关键人物信息",
    "scene_description": "现场描述",
    "truth": {{
        "who": "真凶/关键人物",
        "what": "真正发生了什么",
        "why": "动机",
        "how": "手法",
        "twist": "反转点"
    }},
    "revealed_clues": [
        {{"content": "初始线索1（以「{identity}」的第一人称视角描述，写这个身份才知道/才能观察到的信息）", "critical": false, "perspective": "来源标注（≤12字，如：职业观察）"}},
        {{"content": "初始线索2（同上，身份视角）", "critical": true, "perspective": "来源标注（≤12字，如：现场亲历）"}}
    ],
    "hidden_clues": [
        {{"content": "隐藏线索1", "critical": true, "trigger": "当玩家问到XXX时揭示"}},
        {{"content": "隐藏线索2", "critical": true, "trigger": "当推理进度达到50%时揭示"}}
    ],
    "mysteries": [
        "待解谜团1",
        "待解谜团2",
        "待解谜团3"
    ]
}}
"""

        try:
            response = await self.llm.generate(prompt)
            case_data = self._parse_case_response(response)

            # 验证必要字段是否存在
            if not case_data or not case_data.get("title"):
                print(f"LLM生成案件失败，使用模板案件。Response: {response[:200]}")
                case_data = CaseTemplates.get_detective_case()

            # 确保至少有初始线索，并对齐到等级要求的条数
            if not case_data.get("revealed_clues") or len(case_data.get("revealed_clues", [])) == 0:
                print("警告：生成的案件没有初始线索，添加默认线索")
                case_data["revealed_clues"] = [
                    {"content": "案发现场没有打斗痕迹", "critical": False},
                    {"content": "受害者手中握着重要物品", "critical": True}
                ]
            case_data["revealed_clues"] = self._fit_clue_count(
                case_data.get("revealed_clues"), clue_count
            )

        except (LLMError, Exception) as e:
            print(f"生成案件时发生错误: {str(e)}")
            # 使用模板案件作为fallback
            case_data = CaseTemplates.get_detective_case()

        # 兜底：模板案件也统一对齐到等级要求的线索数
        case_data["revealed_clues"] = self._fit_clue_count(
            case_data.get("revealed_clues"), clue_count
        )
        return self._build_case_info(case_data)

    async def _generate_learning_case(
        self,
        identity: str,
        learning_context: Dict,
        clue_count: int = 3
    ) -> CaseInfo:
        """生成学习模式案件 - 将知识点融入案件"""
        clue_count = max(1, int(clue_count or 3))

        knowledge_points = learning_context.get("knowledge_points", [])
        subject = learning_context.get("subject", "")

        prompt = f"""
你是一个教育游戏设计大师。现在要为一位{identity}设计一个融合了学习内容的推理案件。

学习主题：{subject}
核心知识点：
{chr(10).join(f"- {kp}" for kp in knowledge_points[:5])}

设计要求：
1. 案件的真相要和这些知识点产生关联
2. 玩家需要理解这些知识才能完全破案
3. 但不要做成考试题，要让知识自然地融入推理过程
4. 案件本身要有悬疑性和推理价值
5. 玩家在推理过程中会自然地接触和运用这些知识
6. **初始线索必须正好 {clue_count} 条**（玩家等级对应的开局线索数）

例如：
- 如果是生物学的"细胞分裂"，可以设计一个关于克隆或遗传的悬疑案件
- 如果是物理学的"光的折射"，可以设计一个利用光学原理制造假象的案件
- 如果是历史的"丝绸之路"，可以设计一个古代商队的谜案

请以JSON格式返回：
{{
    "title": "案件标题",
    "background": "案件背景（融入学习主题）",
    "victim_info": "关键人物信息",
    "scene_description": "现场描述",
    "truth": {{
        "who": "真凶/关键人物",
        "what": "真正发生了什么",
        "why": "动机",
        "how": "手法（要和知识点相关）",
        "twist": "反转点",
        "knowledge_applied": "案件中如何运用了哪些知识点"
    }},
    "revealed_clues": [
        {{"content": "初始线索", "critical": false, "related_knowledge": null}},
        {{"content": "知识相关线索", "critical": true, "related_knowledge": "具体知识点"}}
    ],
    "hidden_clues": [
        {{"content": "隐藏线索", "critical": true, "trigger": "触发条件", "related_knowledge": "知识点"}}
    ],
    "mysteries": ["待解谜团列表"]
}}
"""

        try:
            response = await self.llm.generate(prompt)
            case_data = self._parse_case_response(response)

            if not case_data or not case_data.get("title"):
                print("[案件生成] 学习模式案件生成失败，使用模板案件兜底")
                case_data = CaseTemplates.get_detective_case()
        except Exception as e:
            print(f"[案件生成] 学习模式案件生成出错: {str(e)}，使用模板案件兜底")
            case_data = CaseTemplates.get_detective_case()

        # 学习模式同样按等级对齐线索数
        case_data["revealed_clues"] = self._fit_clue_count(
            case_data.get("revealed_clues"), clue_count
        )
        return self._build_case_info(case_data)

    def _parse_case_response(self, response: str) -> Dict:
        """解析LLM返回的案件数据"""
        result = extract_json(response)
        if result is not None:
            print(f"[案件生成] JSON解析成功")
            return result
        print(f"[案件生成] JSON解析失败")
        return {}

    def _build_case_info(self, case_data: Dict) -> CaseInfo:
        """构建CaseInfo对象"""

        case = CaseInfo(
            case_id=str(uuid.uuid4()),
            title=case_data.get("title") or "未命名案件",
            background=case_data.get("background") or "",
            victim_info=case_data.get("victim_info") or "",
            scene_description=case_data.get("scene_description") or "",
            truth=case_data.get("truth") or {},
            mysteries=case_data.get("mysteries") or []
        )

        # 构建初始线索（跳过缺content的无效条目）
        for clue_data in case_data.get("revealed_clues") or []:
            if not isinstance(clue_data, dict) or not clue_data.get("content"):
                continue
            clue = Clue(
                clue_id=str(uuid.uuid4()),
                content=clue_data["content"],
                revealed=True,
                critical=bool(clue_data.get("critical", False)),
                related_knowledge=clue_data.get("related_knowledge"),
                perspective=str(clue_data.get("perspective") or "")
            )
            case.revealed_clues.append(clue)

        # 构建隐藏线索
        for clue_data in case_data.get("hidden_clues") or []:
            if not isinstance(clue_data, dict) or not clue_data.get("content"):
                continue
            clue = Clue(
                clue_id=str(uuid.uuid4()),
                content=clue_data["content"],
                revealed=False,
                critical=bool(clue_data.get("critical", False)),
                related_knowledge=clue_data.get("related_knowledge"),
                perspective=str(clue_data.get("perspective") or "")
            )
            clue.trigger = clue_data.get("trigger", "")  # 添加触发条件
            case.hidden_clues.append(clue)

        # 兜底：确保至少有一条初始线索，否则玩家无从下手
        if not case.revealed_clues:
            print("[案件生成] 警告：案件没有初始线索，添加默认线索")
            case.revealed_clues.append(Clue(
                clue_id=str(uuid.uuid4()),
                content="案发现场没有打斗痕迹",
                revealed=True,
                critical=False
            ))

        return case


class CaseTemplates:
    """案件模板库 - 快速生成用于测试"""

    @staticmethod
    def get_detective_case() -> Dict:
        """侦探身份案件模板"""
        return {
            "title": "午夜图书馆的密室",
            "background": "市图书馆管理员李明在密闭的古籍室中被发现死亡。门窗紧锁，无人进出。监控显示他昨晚10点独自进入，今早被发现时已无生命迹象。",
            "victim_info": "李明，42岁，在图书馆工作20年，负责古籍修复。性格孤僻，但工作认真。",
            "scene_description": "古籍室是一个密闭空间，恒温恒湿。李明倒在工作台前，手中握着一本泛黄的古书。室内没有打斗痕迹，但空气中有淡淡的杏仁味。",
            "truth": {
                "who": "李明自己",
                "what": "李明在修复一本被氰化物污染的古籍时，吸入了挥发的毒气",
                "why": "这本古籍来自二战时期的实验室，内页曾被浸泡在氰化物溶液中作为间谍密写",
                "how": "古籍在密闭的恒湿环境中，氰化物重新活化并挥发",
                "twist": "看似他杀的密室，实际上是一场意外事故。真正的'凶手'是一本被遗忘的历史"
            },
            "revealed_clues": [
                {"content": "密室完全密闭，门窗紧锁", "critical": True},
                {"content": "空气中有杏仁味", "critical": True},
                {"content": "李明手中握着一本泛黄古籍", "critical": True}
            ],
            "hidden_clues": [
                {
                    "content": "这本古籍的来源记录显示，它来自1940年代的德国实验室",
                    "critical": True,
                    "trigger": "询问古籍来源"
                },
                {
                    "content": "李明的工作记录显示，他昨天刚刚打开这本尘封80年的古籍",
                    "critical": True,
                    "trigger": "查看工作记录"
                },
                {
                    "content": "古籍室的恒湿系统昨晚湿度异常升高到90%",
                    "critical": False,
                    "trigger": "检查环境系统"
                }
            ],
            "mysteries": [
                "李明为何会死在密室中？",
                "杏仁味意味着什么？",
                "那本古籍有什么特殊之处？",
                "为什么没有打斗痕迹？"
            ]
        }
