"""推理判断引擎 - 核心AI系统"""
from typing import Dict, List, Tuple, Optional
from models.game_state import GameState, InquiryType, InquiryRecord, Clue
from ai_host.llm_client import LLMError, extract_json
import re
import uuid
import time


class ReasoningEngine:
    """
    推理判断引擎 - 让AI成为真正的游戏主持人

    核心职责：
    1. 判断玩家提问的质量和方向
    2. 计算推理进度
    3. 决定何时揭示线索
    4. 评估猜想的准确性
    5. 检测卡住状态
    """

    # 流式输出的分隔标记：标记前=玩家可见的主持人台词，标记后=系统用JSON
    STREAM_MARKER = "<<<SOUP_JSON>>>"

    def __init__(self, llm_client):
        self.llm = llm_client

    async def process_inquiry(
        self,
        game_state: GameState,
        inquiry_type: InquiryType,
        content: str,
        active_buffs: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """
        处理玩家的推理输入

        active_buffs: 本次提问生效的能力增益（{"knowledge": True, ...}），由控制器 peek，成功后消耗

        返回: (AI回应, 状态更新信息)
        """

        if inquiry_type == InquiryType.QUESTION:
            return await self._process_question(game_state, content, active_buffs)
        elif inquiry_type == InquiryType.HYPOTHESIS:
            return await self._process_hypothesis(game_state, content)
        elif inquiry_type == InquiryType.VERIFICATION:
            return await self._process_verification(game_state, content)
        else:
            raise ValueError(f"未知的推理类型: {inquiry_type}")

    # ==================== 流式处理（边生成边推送主持人台词） ====================

    async def process_inquiry_stream(self, game_state: GameState, inquiry_type: InquiryType, content: str, active_buffs: Optional[Dict] = None):
        """流式处理玩家的推理输入

        异步生成器：先 yield ("delta", 台词增量) 若干次，最后 yield ("final", (ai_response, state_updates))。
        LLM 输出格式：主持人台词在前，<<<SOUP_JSON>>> 标记后跟系统用JSON。
        JSON 解析失败抛 LLMError（上层重试，不消耗推理机会）。
        active_buffs: 本次提问生效的能力增益（仅 QUESTION 使用），控制附加输出字段。
        """
        if inquiry_type == InquiryType.QUESTION:
            prompt = self._build_question_stream_prompt(game_state, content, active_buffs)
        elif inquiry_type == InquiryType.HYPOTHESIS:
            prompt = self._build_hypothesis_stream_prompt(game_state, content)
        elif inquiry_type == InquiryType.VERIFICATION:
            prompt = self._build_verification_stream_prompt(game_state, content)
        else:
            raise ValueError(f"未知的推理类型: {inquiry_type}")

        full = ""
        pushed = 0
        # 防止部分标记字符（如"<"、"<<")泄漏进台词流：末尾保留 marker长度-1 的字符待确认
        holdback = len(self.STREAM_MARKER) - 1
        async for delta in self.llm.generate_stream(prompt):
            full += delta
            idx = full.find(self.STREAM_MARKER)
            if idx >= 0:
                clean = full[:idx]
            else:
                clean = full[:-holdback] if len(full) > holdback else ""
            if len(clean) > pushed:
                yield ("delta", clean[pushed:])
                pushed = len(clean)

        if not full.strip():
            raise LLMError("AI返回了空内容")

        # 解析标记后的JSON；LLM漏掉标记时从全文兜底提取
        json_part = full.split(self.STREAM_MARKER, 1)[1] if self.STREAM_MARKER in full else full
        data = extract_json(json_part) or extract_json(full)
        if data is None:
            print(f"[推理引擎] 流式JSON解析失败, 原始响应: {full[:300]}")
            raise LLMError("AI返回了无法解析的内容，请重试")

        if inquiry_type == InquiryType.QUESTION:
            answer = str(data.get("answer") or "").strip()
            # 二元判定保险：非"是"一律按"否"处理（判定反馈只能是或否）
            if answer not in ("是", "否"):
                answer = "否"
            print(f"[推理引擎] answer字段值: '{answer}'")

            # 死亡断言二次核验：便宜模型在「死了 vs 被藏/带走/失踪」上易翻车，
            # 答「是」时用独立核验调用逐字对照真相，未死亡则强制翻转为「否」
            if answer == "是" and self._is_death_assertion(content):
                verdict = await self._verify_death_claim(game_state, content)
                print(f"[推理引擎] 死亡核验: {verdict or '(核验失败,维持原判定)'}")
                if verdict == "未死亡":
                    answer = "否"

            # 推理进度 = 玩家累计还原的真相百分比（truth_coverage），只进不退
            state_updates = {
                "progress_delta": self._coverage_delta(game_state, data.get("truth_coverage")),
                "revealed_info": [answer],
                "is_critical": bool(data.get("is_critical", False))
            }

            if data.get("should_reveal_clue") and game_state.case.hidden_clues:
                revealed_clue = self._find_and_reveal_clue(game_state, data.get("clue_to_reveal"))
                if revealed_clue:
                    state_updates["revealed_clue"] = revealed_clue

            # 权威台词用确定性模板组装（保证判定干净只有是/否，流式文本仅提供打字机效果）
            ai_response = self._format_question_response(
                answer=answer,
                hint="",
                is_critical=state_updates["is_critical"],
                buff_data=self._collect_buff_fields(data, active_buffs)
            )
            yield ("final", (ai_response, state_updates))

        elif inquiry_type == InquiryType.HYPOTHESIS:
            dialogue = self._clean_dialogue(full)
            state_updates = {
                "progress_delta": self._coverage_delta(game_state, data.get("truth_coverage")),
                "correctness": data.get("correctness", 0),
                "revealed_info": []
            }
            ai_response = dialogue or self._format_hypothesis_response(data)
            yield ("final", (ai_response, state_updates))

        else:  # VERIFICATION
            # 判定规则：还原度>60 破案成功（升1级）；>80 优秀（升2级）
            try:
                completeness = float(data.get("completeness", 0) or 0)
            except (TypeError, ValueError):
                completeness = 0.0
            is_correct = completeness > 60
            is_excellent = completeness > 80
            data["is_correct"] = is_correct
            data["is_excellent"] = is_excellent
            data["completeness"] = completeness
            state_updates = {
                "case_solved": is_correct,
                "game_over": True,   # 还原真相是决胜一击：成功破案、失败终局（最终由 controller 结算）
                "verification_result": data
            }
            yield ("final", ("", state_updates))

    def _clean_dialogue(self, full_text: str) -> str:
        """提取标记前的主持人台词，并截断LLM漏写标记时可能漏出的JSON/代码围栏"""
        text = full_text.split(self.STREAM_MARKER, 1)[0]
        for stop in ("```", "\n{"):
            i = text.find(stop)
            if i >= 0:
                text = text[:i]
        return text.strip()

    # 死亡类断言识别：这类问题最容易出现「死了 vs 被藏/带走/失踪」的判定矛盾
    DEATH_PATTERN = re.compile(
        r"(死了|死了吗|死了么|死没死|死没|是被杀|被杀|杀害|遇害|被害|自杀|他杀|"
        r"身亡|去世|杀死|害死|毒死|勒死|谋杀|死于|尸)"
    )

    # 「询问他人」目标解析（与前端 looksLikeAskPerson 规则一致）：
    # 「问周远：发生什么了」→ (周远, 发生什么了)；「问题目难不难」不匹配（「问题」被排除）
    ASK_TARGET_PATTERN = re.compile(
        r"^\s*(?:问问|询问|打听|请教|问)(?![题卷目案])\s*(.{1,8}?)\s*[：:，,。！？\s]\s*(.+)$",
        re.DOTALL,
    )

    @classmethod
    def _is_death_assertion(cls, question: str) -> bool:
        """玩家提问是否涉及死亡状态断言（需要触发二次核验）"""
        return bool(cls.DEATH_PATTERN.search(question or ""))

    async def _verify_death_claim(self, game_state: GameState, question: str) -> str:
        """死亡断言二次核验：强制先引用真相原文再下结论，防止凭问题里的字面复读。

        返回 '死亡' / '未死亡'，调用失败或解析不出结论返回 ''（不推翻原判定）。
        """
        prompt = f"""核验任务（必须先引用原文，再下结论，不许凭印象猜测）。

案件真相：
{self._format_truth(game_state.case.truth)}

玩家陈述：「{question}」

第一步：从真相原文中逐字抄写与陈述中对象（人/动物）生死有关的一句原文；没有则写"原文未提及生死"。
第二步：另起一行写 结论：死亡 或 结论：未死亡。
规则：原文写明死亡（死了/遇害/尸体/杀害等）才是「死亡」；被藏匿、被带走、失踪、昏迷、离开都算「未死亡」。"""
        try:
            resp = await self.llm.generate(prompt, max_tokens=150, temperature=0.1)
            text = (resp or "").strip()
            # 只信「结论：」行；解析不出结论一律返回''维持原判定（保守，不误杀）
            m = re.search(r"结论[：:]\s*(未死亡|死亡)", text)
            return m.group(1) if m else ""
        except LLMError:
            return ""

    @staticmethod
    def _coverage_delta(game_state: GameState, raw_coverage) -> float:
        """把 LLM 估算的「累计真相还原度」换算成本次进度增量（只进不退）。

        进度条语义 = 玩家目前还原了多少真相，而非按轮次累加：
        delta = clamp(coverage, 0, 100) - 当前进度，负值归零（进度不回退）。
        LLM 未返回 coverage 时增量记 0（宁可不动也不虚涨）。
        """
        try:
            coverage = float(raw_coverage)
        except (TypeError, ValueError):
            return 0.0
        coverage = max(0.0, min(100.0, coverage))
        current = float(game_state.reasoning_progress or 0)
        return max(0.0, coverage - current)

    def _build_question_stream_prompt(self, game_state: GameState, question: str, active_buffs: Optional[Dict] = None) -> str:
        context = self._build_reasoning_context(game_state)
        buff_section = self._build_buff_instruction(active_buffs)
        return f"""
你是一个海龟汤游戏的AI主持人。玩家正在推理案件。

**海龟汤游戏规则：主持人对提问只能回答"是"或"否"，不能透露任何细节！**

案件真相：
{self._format_truth(game_state.case.truth)}

当前已揭示的线索：
{self._format_clues(game_state.case.revealed_clues)}

玩家的身份：{game_state.user_identity}
{context}
玩家的提问："{question}"
{buff_section}
你的输出分两部分：

第一部分（玩家可见的主持人台词）：
- 最多两行：第一行可选一句简短反应（不超过15字，绝不能暗示答案方向），第二行单独一行只写「是」或「否」
- 判定标准：问题与事实相符→「是」；与事实不符、无法从事实推出、或与案件无关→「否」
- 除「是」「否」两个词外，不得出现任何判定性或提示性文字
- **第一部分第二行的「是」/「否」必须与下面JSON中answer字段的值完全一致（同一次判断）**

第二部分（系统数据，玩家不可见）：
另起一行输出标记 <<<SOUP_JSON>>>，然后输出JSON：
{{
    "answer": "是",
    "is_critical": true,
    "truth_coverage": 30,
    "reasoning": "内部分析",
    "should_reveal_clue": false,
    "clue_to_reveal": ""
}}

truth_coverage 判断标准（0-100 整数，推理进度条的依据）：
- 含义：综合目前已有的全部线索和对话，玩家**累计还原了完整真相的百分之几**——不是本次回答的质量分！
- 五要素（谁/发生了什么/动机/手法/反转）基本拼齐才应接近 90-100
- 只有玩家拼出真相的**新关键部分**时才明显提升；泛泛之问、重复提问、细枝末节不得提升
- 当前累计还原度约 {game_state.reasoning_progress:.0f}%，新估值不得无故大幅偏离它

判定自检（必须先在 reasoning 字段里完成，再写 answer）：
① 把玩家的陈述拆成一条条事实断言（主语/状态/动作分开看）
② 逐条对照「案件真相」原文：**全部断言都被真相支持才答「是」；任何一条不符即答「否」**
③ 状态类断言逐字核验，绝不凭语感：
   - 「死了」≠「被藏/被带走/失踪/离开」——真相里角色或动物只是被藏匿、带走、失踪，一律不能对"死了"答「是」
   - 「自杀」≠「他杀」；「在自己家」≠「潜入别人家」；「A干的」≠「B干的」
④ 玩家陈述只对了一半（人或地点或手法错一个）也是「否」——完整判定会在还原真相阶段给出
"""

    @staticmethod
    def _build_buff_instruction(active_buffs: Optional[Dict]) -> str:
        """构造能力增益的附加输出指令（未激活时返回空串，prompt 保持不变）"""
        if not active_buffs:
            return ""

        field_lines = []
        if active_buffs.get("knowledge"):
            field_lines.append('- "knowledge_hint": 【📖 知识提示】用一句话补充一条与本案真相相关的背景知识，帮玩家理解案情')
        if active_buffs.get("association"):
            field_lines.append('- "association_link": 【🔗 联想点拨】用一句话点拨两条已解锁线索之间的关联')
        if active_buffs.get("logic"):
            field_lines.append('- "logic_deduction": 【🧠 逻辑推演】用一句话给出排除式判断（基于已问出的事实排除某种可能性）')
        if active_buffs.get("insight"):
            field_lines.append('- "insight_detail": 【🔍 洞察细节】用一句话补充一个尚未明说的关键细节（不得直接道破核心真相）')

        if not field_lines:
            return ""

        return f"""
【能力增益生效】玩家本次提问携带能力增益，你必须在下方 JSON 中额外输出以下字段
（每字段一句话、玩家可见，语气与主持人一致；只描述引导信息，绝不能直接道破真相核心；
 未列出的增益字段不要输出）：
{chr(10).join(field_lines)}
"""

    @staticmethod
    def _collect_buff_fields(data: Dict, active_buffs: Optional[Dict]) -> Optional[Dict]:
        """从 LLM 返回的 JSON 中收集已激活增益的附加内容（无激活或全空返回 None）"""
        if not active_buffs:
            return None
        key_map = {
            "knowledge": "knowledge_hint",
            "association": "association_link",
            "logic": "logic_deduction",
            "insight": "insight_detail",
        }
        out = {}
        for buff_type, key in key_map.items():
            if active_buffs.get(buff_type):
                out[key] = str(data.get(key) or "").strip()
        return out or None

    def _build_hypothesis_stream_prompt(self, game_state: GameState, hypothesis: str) -> str:
        return f"""
你是海龟汤主持人。玩家提出了一个推理猜想。

案件真相：
{self._format_truth(game_state.case.truth)}

已知信息：
{self._format_clues(game_state.case.revealed_clues)}

玩家的猜想：
"{hypothesis}"

你的输出分两部分：

第一部分（玩家可见的主持人台词）：
- 用2-4句话给出引导性反馈：评价猜想方向（接近/有道理/偏差/死胡同），引导下一步思考
- 不得直接说出真相，不得逐条罗列对错清单

第二部分（系统数据，玩家不可见）：
另起一行输出标记 <<<SOUP_JSON>>>，然后输出JSON：
{{
    "correctness": 65,
    "truth_coverage": 40,
    "feedback": "引导性反馈",
    "hint_direction": "下一步应该关注什么"
}}

truth_coverage 判断标准（0-100 整数，推理进度条的依据）：
- 含义：综合目前已有的全部信息，玩家**累计还原了完整真相的百分之几**——不是本次猜想的正确率！
- 五要素（谁/发生了什么/动机/手法/反转）基本拼齐才应接近 90-100
- 只有猜想覆盖了真相的**新关键部分**时才明显提升；重复已知内容不得提升
- 当前累计还原度约 {game_state.reasoning_progress:.0f}%，新估值不得无故大幅偏离它
"""

    def _build_verification_stream_prompt(self, game_state: GameState, truth_claim: str) -> str:
        return f"""
玩家尝试还原完整真相。请严格对比。

正确的真相：
{self._format_truth(game_state.case.truth)}

玩家还原的真相：
"{truth_claim}"

你的输出分两部分：

第一部分（玩家可见的判定）：
- 还原度超过80分（真相基本完整还原，优秀）：输出「是」—— 你完美还原了真相
- 还原度60~80分（重要线索基本还原，成功）：输出「是」—— 你还原了真相
- 还原度60分及以下：输出「否」—— 真相并非如此，不得透露任何错误细节或遗漏点

第二部分（系统数据，玩家不可见）：
另起一行输出标记 <<<SOUP_JSON>>>，然后输出JSON：
{{
    "is_correct": true,
    "completeness": 85,
    "accuracy": {{
        "who": true,
        "what": true,
        "why": false,
        "how": true,
        "twist": false
    }},
    "errors": ["错误点1"],
    "missing": ["遗漏的关键要素1"],
    "reasoning_path_summary": ["推理路径第1步", "第2步", "第3步"],
    "key_insights": ["关键洞察1"]
}}

评分标准（completeness 0-100）：重要线索（谁/做了什么/关键手法/反转点）还原得越多，分数越高。
系统以 completeness>60 作为破案成功（升级1级）、completeness>80 作为优秀（升级2级）的最终判定，请务必给出准确的分数。
"""

    async def _process_question(
        self,
        game_state: GameState,
        question: str,
        active_buffs: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """处理玩家提问"""

        # 构建推理上下文
        context = self._build_reasoning_context(game_state)
        buff_section = self._build_buff_instruction(active_buffs)

        prompt = f"""
你是一个海龟汤游戏的AI主持人。玩家正在推理案件。

**海龟汤游戏规则：主持人只能回答"是"或"否"，不能透露细节！**

案件真相：
{self._format_truth(game_state.case.truth)}

当前已揭示的线索：
{self._format_clues(game_state.case.revealed_clues)}

玩家的身份：{game_state.user_identity}

玩家的提问："{question}"
{buff_section}
你的任务：
1. 根据案件真相，判断这个问题的答案
2. **answer字段必须只能是"是"或"否"两种之一（严格二元）：**
   - "是" - 问题与事实相符
   - "否" - 问题与事实不符、无法从事实推出，或与案件无关
3. 评估这个问题是否触及关键点
4. 估算 truth_coverage：玩家目前累计还原的真相百分比（0-100整数，不是本次回答质量；只有拼出真相的新关键部分才明显提升；五要素基本拼齐才接近90-100）

**重要：不要在answer字段中添加任何解释，只能是"是"或"否"！**

请以JSON格式回复：
{{
    "answer": "是",
    "is_critical": true,
    "quality_score": 75,
    "hint": "",
    "truth_coverage": 30,
    "reasoning": "内部分析（不会显示给玩家）",
    "should_reveal_clue": false,
    "clue_to_reveal": ""
}}

判断标准：
- 触及真相核心的问题：quality_score 80-100
- 方向正确但不够深入：quality_score 60-79
- 相关但偏离重点：quality_score 40-59
- 无关问题：quality_score 0-39

判定自检（必须先在 reasoning 字段里完成，再写 answer）：
① 把玩家的陈述拆成一条条事实断言（主语/状态/动作分开看）
② 逐条对照「案件真相」原文：**全部断言都被真相支持才答「是」；任何一条不符即答「否」**
③ 状态类断言逐字核验，绝不凭语感：
   - 「死了」≠「被藏/被带走/失踪/离开」——真相里角色或动物只是被藏匿、带走、失踪，一律不能对"死了"答「是」
   - 「自杀」≠「他杀」；「在自己家」≠「潜入别人家」；「A干的」≠「B干的」
④ 玩家陈述只对了一半（人或地点或手法错一个）也是「否」——完整判定会在还原真相阶段给出
"""

        response = await self.llm.generate(prompt)
        analysis = self._parse_json_response(response)

        # 二元判定保险：非"是"一律按"否"处理（判定反馈只能是或否）
        answer = str(analysis.get("answer") or "").strip()
        if answer not in ("是", "否"):
            answer = "否"
        analysis["answer"] = answer
        print(f"[推理引擎] answer字段值: '{answer}'")

        # 死亡断言二次核验：答「是」时逐字对照真相复核，未死亡则强制翻转
        if answer == "是" and self._is_death_assertion(question):
            verdict = await self._verify_death_claim(game_state, question)
            print(f"[推理引擎] 死亡核验: {verdict or '(核验失败,维持原判定)'}")
            if verdict == "未死亡":
                answer = "否"
                analysis["answer"] = answer

        # 根据分析结果更新游戏状态（进度=累计真相还原度，只进不退）
        state_updates = {
            "progress_delta": self._coverage_delta(game_state, analysis.get("truth_coverage")),
            "revealed_info": [answer],
            "is_critical": analysis.get("is_critical", False)
        }

        # 检查是否需要揭示隐藏线索
        if analysis.get("should_reveal_clue") and game_state.case.hidden_clues:
            clue_content = analysis.get("clue_to_reveal")
            revealed_clue = self._find_and_reveal_clue(game_state, clue_content)
            if revealed_clue:
                state_updates["revealed_clue"] = revealed_clue

        # 构建主持人风格的回应
        ai_response = self._format_question_response(
            answer=answer,
            hint=analysis.get("hint", ""),
            is_critical=analysis.get("is_critical", False),
            buff_data=self._collect_buff_fields(analysis, active_buffs)
        )

        return ai_response, state_updates

    async def _process_hypothesis(
        self,
        game_state: GameState,
        hypothesis: str
    ) -> Tuple[str, Dict]:
        """评估玩家的猜想"""

        prompt = f"""
你是海龟汤主持人。玩家提出了一个推理猜想。

案件真相：
{self._format_truth(game_state.case.truth)}

已知信息：
{self._format_clues(game_state.case.revealed_clues)}

玩家的猜想：
"{hypothesis}"

评估要求：
1. 判断猜想的正确程度（0-100%）
2. 指出正确的部分
3. 指出错误或遗漏的部分
4. 给出引导性反馈（不直接说答案）
5. 估算 truth_coverage：玩家目前累计还原的真相百分比（0-100整数，不是本次猜想的正确率；只有覆盖真相的新关键部分才明显提升）

返回JSON：
{{
    "correctness": 65,
    "correct_parts": ["正确的推理点1", "正确的推理点2"],
    "wrong_parts": ["错误的推理点1"],
    "missing_parts": ["遗漏的关键点1"],
    "feedback": "引导性反馈",
    "truth_coverage": 40,
    "hint_direction": "下一步应该关注什么"
}}
"""

        response = await self.llm.generate(prompt)
        evaluation = self._parse_json_response(response, "猜想评估")

        ai_response = self._format_hypothesis_response(evaluation)

        state_updates = {
            "progress_delta": self._coverage_delta(game_state, evaluation.get("truth_coverage")),
            "correctness": evaluation.get("correctness", 0),
            "revealed_info": evaluation.get("correct_parts", [])
        }

        return ai_response, state_updates

    async def _process_verification(
        self,
        game_state: GameState,
        truth_claim: str
    ) -> Tuple[str, Dict]:
        """验证玩家还原的真相"""

        prompt = f"""
玩家尝试还原完整真相。请严格对比。

正确的真相：
{self._format_truth(game_state.case.truth)}

玩家还原的真相：
"{truth_claim}"

评分标准（completeness 0-100）：重要线索（谁/做了什么/关键手法/反转点）还原得越多，分数越高。

返回JSON：
{{
    "is_correct": true/false,
    "completeness": 85,
    "accuracy": {{
        "who": true/false,
        "what": true/false,
        "why": true/false,
        "how": true/false,
        "twist": true/false
    }},
    "errors": ["错误点1", "错误点2"],
    "missing": ["遗漏的关键要素1"],
    "reasoning_path_summary": ["推理路径第1步", "第2步", "第3步"],
    "key_insights": ["关键洞察1", "关键洞察2"]
}}

判断：completeness 超过60分即视为破案成功（is_correct=true，升级1级）；超过80分为优秀（升级2级），请给出准确的还原度分数。
"""

        response = await self.llm.generate(prompt)
        verification = self._parse_json_response(response, "真相验证")

        # 判定规则：还原度>60 破案成功（升1级）；>80 优秀（升2级）
        try:
            completeness = float(verification.get("completeness", 0) or 0)
        except (TypeError, ValueError):
            completeness = 0.0
        is_correct = completeness > 60
        is_excellent = completeness > 80
        verification["is_correct"] = is_correct
        verification["is_excellent"] = is_excellent
        verification["completeness"] = completeness

        state_updates = {
            "case_solved": is_correct,
            "game_over": True,   # 还原真相是决胜一击：成功破案、失败终局（最终由 controller 结算）
            "verification_result": verification
        }

        return "", state_updates

    def _find_and_reveal_clue(
        self,
        game_state: GameState,
        clue_content: str
    ) -> Optional[Clue]:
        """找到并揭示隐藏线索"""

        if not game_state.case.hidden_clues:
            return None

        # 使用相似度匹配找到最相关的隐藏线索
        for clue in game_state.case.hidden_clues:
            if self._is_similar(clue.content, clue_content):
                game_state.reveal_clue(clue)
                return clue

        # 如果没找到完全匹配，揭示第一条未揭示的关键线索
        for clue in game_state.case.hidden_clues:
            if clue.critical:
                game_state.reveal_clue(clue)
                return clue

        return None

    def _is_similar(self, text1: str, text2: str, threshold: float = 0.6) -> bool:
        """简单的文本相似度判断"""
        # 简化版本：检查关键词重叠
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        similarity = overlap / max(len(words1), len(words2))

        return similarity >= threshold

    def check_should_reveal_hidden_clue(
        self,
        game_state: GameState
    ) -> Optional[Clue]:
        """检查是否应该主动揭示隐藏线索"""

        # 触发条件：
        # 1. 推理进度达到特定阈值
        # 2. 玩家卡住
        # 3. 剩余轮次较少

        if game_state.reasoning_progress >= 50 and game_state.reasoning_progress < 55:
            # 进度达到50%时揭示一条线索
            for clue in game_state.case.hidden_clues:
                if not clue.revealed and clue.critical:
                    return clue

        if game_state.is_stuck() and game_state.remaining_turns > 3:
            # 卡住且还有机会时给线索
            for clue in game_state.case.hidden_clues:
                if not clue.revealed:
                    return clue

        if game_state.remaining_turns <= 3 and game_state.reasoning_progress < 70:
            # 最后几轮但进度不够时给关键线索
            for clue in game_state.case.hidden_clues:
                if not clue.revealed and clue.critical:
                    return clue

        return None

    def _build_reasoning_context(self, game_state: GameState) -> str:
        """构建推理上下文"""
        context = f"案件：{game_state.case.title}\n"
        context += f"推理进度：{game_state.reasoning_progress:.1f}%\n"
        context += f"剩余轮次：{game_state.remaining_turns}\n"

        if game_state.inquiry_history:
            context += "\n最近的推理历史：\n"
            for record in game_state.inquiry_history[-3:]:
                context += f"- {record.content}\n"

        return context

    def _format_truth(self, truth: Dict) -> str:
        """格式化真相"""
        return f"""
谁：{truth.get('who', '')}
发生了什么：{truth.get('what', '')}
动机：{truth.get('why', '')}
手法：{truth.get('how', '')}
反转点：{truth.get('twist', '')}
"""

    def _format_clues(self, clues: List[Clue]) -> str:
        """格式化线索列表"""
        if not clues:
            return "暂无"
        return "\n".join(f"- {clue.content}" for clue in clues if clue.revealed)

    def _format_question_response(
        self,
        answer: str,
        hint: str,
        is_critical: bool,
        buff_data: Optional[Dict] = None
    ) -> str:
        """格式化提问回应（含能力增益附加内容）"""

        import random

        if is_critical:
            intros = ["这个问题很关键。", "你问到了重点。", "这是一个敏锐的观察。"]
        else:
            intros = ["关于这个问题...", "让我告诉你...", "答案是..."]

        response = f"{random.choice(intros)}\n\n「{answer}」"

        if hint:
            response += f"\n\n{hint}"

        # 能力增益附加内容（仅列出 LLM 实际给出了内容的项）
        if buff_data:
            extras = []
            if buff_data.get("knowledge_hint"):
                extras.append(f"💡 知识提示：{buff_data['knowledge_hint']}")
            if buff_data.get("association_link"):
                extras.append(f"🔗 联想点拨：{buff_data['association_link']}")
            if buff_data.get("logic_deduction"):
                extras.append(f"🧠 逻辑推演：{buff_data['logic_deduction']}")
            if buff_data.get("insight_detail"):
                extras.append(f"🔍 洞察细节：{buff_data['insight_detail']}")
            if extras:
                response += "\n\n" + "\n\n".join(extras)

        return response

    def _format_hypothesis_response(self, evaluation: Dict) -> str:
        """格式化猜想评估"""

        correctness = evaluation.get("correctness", 0)

        if correctness > 80:
            intro = "你的推理非常接近真相了。"
        elif correctness > 50:
            intro = "你的推理有一定道理，但还不够完整。"
        elif correctness > 30:
            intro = "你的推理方向有些偏差。"
        else:
            intro = "这个推理可能把你带入了死胡同。"

        feedback = evaluation.get("feedback", "")

        response = f"{intro}\n\n{feedback}"

        if evaluation.get("hint_direction"):
            response += f"\n\n💡 提示：{evaluation['hint_direction']}"

        return response

    def _parse_json_response(self, response: str, scene: str = "") -> Dict:
        """解析LLM的JSON响应，失败时抛出LLMError（上层会保留玩家机会并允许重试）"""
        result = extract_json(response)
        if result is None:
            print(f"[推理引擎] {scene}JSON解析失败, 原始响应: {response[:300]}")
            raise LLMError("AI返回了无法解析的内容，请重试")
        return result

    async def generate_hint(
        self,
        game_state: GameState,
        hint_type: str = "normal"
    ) -> str:
        """生成提示"""

        prompt = self._build_hint_prompt(game_state, hint_type)
        hint = await self.llm.generate(prompt, max_tokens=800)
        return hint.strip()

    async def generate_hint_stream(self, game_state: GameState, hint_type: str = "normal"):
        """流式生成提示：yield ("delta", 文本增量) ... 最后 yield ("final", 完整提示文本)"""
        prompt = self._build_hint_prompt(game_state, hint_type)
        full = ""
        async for delta in self.llm.generate_stream(prompt, max_tokens=800, temperature=0.7):
            full += delta
            yield ("delta", delta)
        if not full.strip():
            raise LLMError("AI返回了空内容")
        yield ("final", full.strip())

    def _build_hint_prompt(self, game_state: GameState, hint_type: str = "normal") -> str:
        """构建提示生成的提示词"""

        if hint_type == "normal":
            strength = "给出一个方向性的提示，不要泄露具体答案"
        elif hint_type == "strong":
            strength = "给出一个更明确的提示，可以指向关键线索"
        else:
            strength = "给出一个隐晦的提示"

        prompt = f"""
玩家在推理中遇到困难。

案件真相：
{self._format_truth(game_state.case.truth)}

当前进度：{game_state.reasoning_progress:.1f}%

已知线索：
{self._format_clues(game_state.case.revealed_clues)}

最近推理：
{self._format_recent_inquiries(game_state.inquiry_history[-3:])}

请{strength}。

提示要求：
- 不要直接说答案
- 引导玩家关注被忽略的线索
- 或者提示一个新的思考角度

直接返回提示文本即可，不要输出JSON或任何标记。
"""
        return prompt

    async def generate_ask_person_stream(self, game_state: GameState, content: str):
        """流式生成「询问他人」回应：以被询问者的口吻透露一条线索

        yield ("delta", 文本增量) ... 最后 yield ("final", 完整回应文本)
        """
        prompt = self._build_ask_person_prompt(game_state, content)
        full = ""
        async for delta in self.llm.generate_stream(prompt, max_tokens=800, temperature=0.8):
            full += delta
            yield ("delta", delta)
        if not full.strip():
            raise LLMError("AI返回了空内容")
        yield ("final", full.strip())

    def _build_ask_person_prompt(self, game_state: GameState, content: str) -> str:
        """构建「询问他人」的提示词

        被询问人在代码层用正则锁定（与前端 looksLikeAskPerson 规则一致）：
        锁定后 prompt 硬性要求以该人物第一人称回答，杜绝模型角色漂移
        （问陈屿却自称周远、问周远回旁观者视角的翻车）。
        """
        m = self.ASK_TARGET_PATTERN.match(content or "")
        if m:
            target, question = m.group(1).strip(), m.group(2).strip()
            target_block = f"""被询问人（已锁定，必须严格遵守）：{target}

你现在就是{target}本人，正在当面回答玩家的提问。硬性要求：
- 必须以{target}的第一人称说话（「我……」），语气符合其身份
- 你就是{target}，绝不能自称其他人物的名字，也不能以旁观者视角转述{target}做了什么
"""
            ask_line = f"玩家向你（{target}）提问：「{question}」"
        else:
            target_block = """被询问人：从玩家的打听内容中判断玩家想询问谁（人物/角色）。如果没指明，就选一个与案件最相关的人物，以该人物的第一人称回答，且全篇只以该人物身份说话"""
            ask_line = f"玩家的打听内容：{content}"

        prompt = f"""
玩家正在玩海龟汤推理游戏，现在想去打听消息、找人要线索。

玩家身份：{game_state.user_identity}
{ask_line}

{target_block}

案件真相：
{self._format_truth(game_state.case.truth)}

案件背景：
{game_state.case.background}

已知线索：
{self._format_clues(game_state.case.revealed_clues)}

最近推理：
{self._format_recent_inquiries(game_state.inquiry_history[-3:])}

任务：
- 根据案件真相，透露一条与真相一致、且符合你视角的新情报（不要与已知线索重复）
- 只透露情报，不要直接说出完整真相或凶手
- 80字以内，口语化，像真人说话
- 如果玩家问的问题与案件无关，就以你的身份自然地回避

直接返回该人物的说话内容即可，不要输出JSON、旁白或任何标记。
"""
        return prompt

    def _format_recent_inquiries(self, records: List[InquiryRecord]) -> str:
        """格式化最近的推理"""
        if not records:
            return "无"
        return "\n".join(f"- {r.content}" for r in records)
