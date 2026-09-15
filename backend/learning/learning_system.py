"""学习系统 - 知识点提取和习题生成"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import uuid
import re
from ai_host.llm_client import extract_json


class ExerciseType(Enum):
    SINGLE_CHOICE = "single_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class ExerciseDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class Exercise:
    """习题"""
    exercise_id: str
    exercise_type: ExerciseType
    difficulty: ExerciseDifficulty
    question: str
    options: Optional[List[str]] = None  # 选择题选项
    correct_answer: str = ""
    explanation: str = ""  # 解析
    knowledge_point: str = ""  # 关联的知识点
    reward_type: str = "extra_turn"  # insight, logic, knowledge, extra_turn, hidden_clue


@dataclass
class LearningMaterial:
    """学习材料"""
    material_id: str
    title: str
    content: str
    subject: str
    knowledge_points: List[str]


class KnowledgeExtractor:
    """知识点提取器"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def extract_knowledge_points(
        self,
        material: str,
        subject: str = ""
    ) -> LearningMaterial:
        """从学习材料中提取知识点"""

        prompt = f"""
你是一个教育专家。请从以下学习材料中提取核心知识点。

{f'学科：{subject}' if subject else ''}

学习材料：
\"\"\"
{material[:3000]}  # 限制长度避免超token
\"\"\"

任务：
1. 识别材料的主题和学科领域
2. 提取5-10个核心知识点
3. 每个知识点要清晰、独立、可测试
4. 按重要性排序

返回JSON格式：
{{
    "title": "材料标题/主题",
    "subject": "学科领域",
    "knowledge_points": [
        "知识点1：具体描述",
        "知识点2：具体描述",
        "知识点3：具体描述"
    ]
}}

示例：
材料是关于"光合作用"的，知识点应该是：
- "光合作用的定义和本质"
- "光合作用的反应方程式"
- "光合作用的场所和条件"
- "光反应和暗反应的区别"
等等。
"""

        response = await self.llm.generate(prompt)
        data = self._parse_json(response) or {}

        # 兜底：解析失败时至少给出一个可用知识点，避免后续除零
        knowledge_points = data.get("knowledge_points") or []
        if not knowledge_points:
            print("[学习系统] 知识点提取失败，使用默认知识点兜底")
            knowledge_points = [f"{subject or '材料'}的整体理解与应用"]

        return LearningMaterial(
            material_id=str(uuid.uuid4()),
            title=data.get("title") or "学习材料",
            content=material,
            subject=data.get("subject") or subject,
            knowledge_points=knowledge_points
        )

    def _parse_json(self, response: str) -> Optional[Dict]:
        """解析JSON响应"""
        return extract_json(response)


class ExerciseGenerator:
    """习题生成器"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def generate_exercises(
        self,
        learning_material: LearningMaterial,
        count: int = 3,
        difficulty: ExerciseDifficulty = ExerciseDifficulty.MEDIUM,
        rotate_index: int = 0,
        avoid_questions: Optional[List[str]] = None
    ) -> List[Exercise]:
        """根据知识点生成习题

        rotate_index: 轮转序号（每次挑战递增），让题型与知识点轮转变化——保证每次题目不一样
        avoid_questions: 已出过的题目列表，写进 prompt 要求 AI 避免重复出题
        """

        exercises = []

        # 生成不同类型的题目
        types_to_generate = [
            ExerciseType.SINGLE_CHOICE,
            ExerciseType.TRUE_FALSE,
            ExerciseType.SHORT_ANSWER
        ]

        # 兜底：知识点列表为空时使用占位，避免除零崩溃
        knowledge_points = learning_material.knowledge_points or ["材料整体理解"]
        avoid = [str(q) for q in (avoid_questions or []) if q]

        for i in range(min(count, len(types_to_generate))):
            idx = rotate_index + i
            exercise_type = types_to_generate[idx % len(types_to_generate)]
            knowledge_point = knowledge_points[idx % len(knowledge_points)]

            exercise = await self._generate_single_exercise(
                knowledge_point=knowledge_point,
                exercise_type=exercise_type,
                difficulty=difficulty,
                material_content=learning_material.content,
                avoid_questions=avoid
            )

            if exercise:
                exercises.append(exercise)

        return exercises

    async def _generate_single_exercise(
        self,
        knowledge_point: str,
        exercise_type: ExerciseType,
        difficulty: ExerciseDifficulty,
        material_content: str,
        avoid_questions: Optional[List[str]] = None
    ) -> Optional[Exercise]:
        """生成单个习题（含防泄露校验：题干不得把答案写上屏）"""

        async def dispatch(leak_warning: bool = False) -> Optional[Exercise]:
            if exercise_type == ExerciseType.SINGLE_CHOICE:
                return await self._generate_choice_question(
                    knowledge_point, difficulty, material_content, avoid_questions,
                    leak_warning=leak_warning
                )
            elif exercise_type == ExerciseType.TRUE_FALSE:
                return await self._generate_true_false_question(
                    knowledge_point, difficulty, material_content, avoid_questions,
                    leak_warning=leak_warning
                )
            elif exercise_type == ExerciseType.SHORT_ANSWER:
                return await self._generate_short_answer_question(
                    knowledge_point, difficulty, material_content, avoid_questions
                )
            return None

        # 出题全程兜底：LLM 网络/解析异常一律转成 None，由上层走「习题生成失败」提示，绝不 500
        try:
            exercise = await dispatch()
        except Exception as e:
            print(f"[出题] 生成异常（{exercise_type}）：{e}")
            exercise = None

        # LLM 偶发返回无法解析的内容（空回复/非 JSON）时自动重试一次
        if exercise is None:
            try:
                exercise = await dispatch()
                if exercise is not None:
                    print("[出题] 首次生成失败，重试成功")
            except Exception as e:
                print(f"[出题] 重试仍异常（{exercise_type}）：{e}")
                exercise = None

        # 第一道防线：剥离 LLM 复读到题干里的知识点标注（【…】块 / 知识点N：前缀）
        if exercise:
            exercise.question = self._strip_knowledge_label(exercise.question)

        # 防泄露兜底：选择/判断题题干若出现答案词或词条卡片特征，重新生成一次
        leak_prone = exercise_type in (ExerciseType.SINGLE_CHOICE, ExerciseType.TRUE_FALSE)
        if exercise and leak_prone and self._question_leaks_answer(exercise):
            print("[出题] 检测到题干泄露答案，重新生成中...")
            try:
                exercise = await dispatch(leak_warning=True)
            except Exception as e:
                print(f"[出题] 防泄露重生成异常：{e}")
                exercise = None
            if exercise:
                exercise.question = self._strip_knowledge_label(exercise.question)
            if exercise and self._question_leaks_answer(exercise):
                print("[出题] 二次生成仍有泄露迹象，放行（避免阻塞游戏）")

        return exercise

    @staticmethod
    def _strip_knowledge_label(q: str) -> str:
        """剥离 LLM 复读到题干里的知识点标注：【…】块、知识点N：前缀、开头残留连字符"""
        s = (q or "").strip()
        s = re.sub(r"【[^】]*】", "", s)  # 正常题干不含【】块
        s = re.sub(r"^\s*知识点\s*\d*\s*[：:．.、]?\s*", "", s)
        s = re.sub(r"^\s*[-—–]+\s*", "", s)
        return s.strip()

    def _question_leaks_answer(self, exercise: Exercise) -> bool:
        """检测题干是否泄露答案（词条卡片上屏 / 答案词出现在选择题题干）"""
        q = (exercise.question or "").lower()
        if not q:
            return False

        # 词条卡片特征：释义/搭配/同义词/知识点标注直接上屏
        for marker in ("同义词", "常用搭配", "反义词", "词根词缀", "例句:", "知识点"):
            if marker in q:
                return True
        # 【…】知识卡片块（正常题干不该出现）
        if re.search(r"【[^】]*】", q):
            return True
        # 词条词性标注模式上屏，如 "demonstrate (v.)"
        if re.search(r"[a-z]{3,}\s*\((?:v|n|adj|adv|vt|vi)\.?\)", q):
            return True

        # 选择题：正确答案文本或知识点中的英文词出现在题干 = 送分（单复数变体归一后比较）
        if exercise.exercise_type == ExerciseType.SINGLE_CHOICE:
            sensitive = set(re.findall(r"[A-Za-z]{4,}", self._correct_option_text(exercise)))
            sensitive |= set(re.findall(r"[A-Za-z]{4,}", exercise.knowledge_point or ""))
            sensitive_variants: set = set()
            for w in sensitive:
                sensitive_variants |= self._en_word_variants(w)
            q_words: set = set()
            for w in re.findall(r"[A-Za-z]{4,}", q):
                q_words |= self._en_word_variants(w)
            return bool(sensitive_variants & q_words)

        return False

    @staticmethod
    def _en_word_variants(w: str) -> set:
        """英文词变体集合：原词 + 常见单复数/所有格还原（perspectives→{perspective,…}）"""
        w = (w or "").lower()
        variants = {w}
        if len(w) > 4:
            if w.endswith("ies"):
                variants.add(w[:-3] + "y")
                variants.add(w[:-3])
            if w.endswith("es"):
                variants.add(w[:-2])
            if w.endswith("s"):
                variants.add(w[:-1])
        return variants

    @staticmethod
    def _correct_option_text(exercise: Exercise) -> str:
        """取正确答案的完整选项文本（字母选项 -> 选项内容）"""
        ans = (exercise.correct_answer or "").strip()
        for opt in (exercise.options or []):
            s = str(opt).strip()
            if s == ans or re.sub(r"^[A-D][\.、\)]\s*", "", s).strip().lower() == ans.lower():
                return s
        return ans

    @staticmethod
    def _no_leak_section() -> str:
        """出题防泄露铁律（所有题型共用）"""
        return """
防泄露铁律（必须遵守）：
- question 只包含题干本身：严禁附加词条说明、知识卡片、中文释义、常用搭配、同义词列表等任何提示文字。
- 严禁在 question 中出现任何知识点标注——包括但不限于【知识点1: …】、知识点1：…、「知识点」字样、【…】方括号块。知识点只是给你确定考查方向的依据，绝不能出现在题目里。
- 严禁把答案词本身或其变体写进 question（含单复数变体）——玩家看到即等于送分，属于废题。
- 严禁摘抄/复述/改写学习材料原文的句子：题目必须是你对知识点的全新原创表述，玩家粘贴的资料一个字都不能出现在题目里。
- 知识点的含义讲解必须放在 explanation（解析）里：玩家答题后通过解析学到该知识点，题目本身保持无提示。
"""

    @staticmethod
    def _avoid_section(avoid_questions: Optional[List[str]]) -> str:
        """构造「已出过的题目，不要重复」提示段"""
        if not avoid_questions:
            return ""
        recent = "\n".join(f"- {q[:80]}" for q in avoid_questions[-10:])
        return f"""
已出过的题目（新题必须换不同角度考查，禁止与下面这些重复或高度相似）：
{recent}
"""

    async def _generate_choice_question(
        self,
        knowledge_point: str,
        difficulty: ExerciseDifficulty,
        material_content: str,
        avoid_questions: Optional[List[str]] = None,
        leak_warning: bool = False
    ) -> Exercise:
        """生成单选题"""

        diff_desc = {
            ExerciseDifficulty.EASY: "简单，直接考查概念",
            ExerciseDifficulty.MEDIUM: "中等，需要理解和应用",
            ExerciseDifficulty.HARD: "困难，需要分析和推理"
        }

        leak_warn_section = "\n⚠️ 注意：你上一次生成的题目把答案直接写进了题干！这次必须彻底避免。\n" if leak_warning else ""

        prompt = f"""
根据以下知识点生成一道单选题。

知识点（仅供你确定考查方向，不得原文出现在题目中）：{knowledge_point}
{self._avoid_section(avoid_questions)}

难度：{diff_desc[difficulty]}
{leak_warn_section}
要求：
1. 题目要准确、清晰，必须是围绕知识点的全新原创题（不得摘抄学习材料原文）
2. 4个选项，只有1个正确
3. 错误选项要有迷惑性，不能明显错误
4. explanation 必须包含知识点讲解：先解释该知识点的含义/用法（题目里不能出现的讲解放这里），再说明为什么选对、其他选项错在哪里
{self._no_leak_section()}
返回JSON：
{{
    "question": "题目内容",
    "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
    "correct_answer": "A",
    "explanation": "详细解析，说明为什么选A，其他选项错在哪里"
}}
"""

        response = await self.llm.generate(prompt)
        data = self._parse_json(response) or {}

        question = str(data.get("question") or "").strip()
        options = [str(o).strip() for o in (data.get("options") or []) if str(o).strip()]
        # LLM 偶发返回无法解析的内容：返回 None 走上层重试与「习题生成失败」兜底，绝不抛裸异常
        if not question or len(options) < 2:
            print("[出题] 选择题返回内容不完整，放弃本题")
            return None

        return Exercise(
            exercise_id=str(uuid.uuid4()),
            exercise_type=ExerciseType.SINGLE_CHOICE,
            difficulty=difficulty,
            question=question,
            options=options,
            correct_answer=str(data.get("correct_answer") or ""),
            explanation=str(data.get("explanation") or ""),
            knowledge_point=knowledge_point,
            reward_type=self._assign_reward_type()
        )

    async def _generate_true_false_question(
        self,
        knowledge_point: str,
        difficulty: ExerciseDifficulty,
        material_content: str,
        avoid_questions: Optional[List[str]] = None,
        leak_warning: bool = False
    ) -> Exercise:
        """生成判断题"""

        leak_warn_section = "\n⚠️ 注意：你上一次生成的题目把答案或词条说明直接写进了陈述！这次必须彻底避免。\n" if leak_warning else ""

        prompt = f"""
根据知识点生成一道判断题（对/错）。

知识点（仅供你确定考查方向，不得原文出现在题目中）：{knowledge_point}
{self._avoid_section(avoid_questions)}
{leak_warn_section}
要求：
1. 陈述要清晰明确，必须是围绕知识点的全新原创表述（不得摘抄学习材料原文）
2. 不能模棱两可
3. explanation 必须包含知识点讲解：先解释该知识点的含义/用法（题目里不能出现的讲解放这里），再说明判断依据
{self._no_leak_section()}
返回JSON：
{{
    "question": "判断题陈述",
    "correct_answer": "对/错",
    "explanation": "解析说明"
}}
"""

        response = await self.llm.generate(prompt)
        data = self._parse_json(response) or {}

        question = str(data.get("question") or "").strip()
        # 解析失败/题干为空 → 返回 None 走上层重试与兜底
        if not question:
            print("[出题] 判断题返回内容不完整，放弃本题")
            return None

        return Exercise(
            exercise_id=str(uuid.uuid4()),
            exercise_type=ExerciseType.TRUE_FALSE,
            difficulty=difficulty,
            question=question,
            options=["对", "错"],
            correct_answer=str(data.get("correct_answer") or ""),
            explanation=str(data.get("explanation") or ""),
            knowledge_point=knowledge_point,
            reward_type=self._assign_reward_type()
        )

    async def _generate_short_answer_question(
        self,
        knowledge_point: str,
        difficulty: ExerciseDifficulty,
        material_content: str,
        avoid_questions: Optional[List[str]] = None
    ) -> Exercise:
        """生成简答题"""

        prompt = f"""
根据知识点生成一道简答题。

知识点（仅供你确定考查方向，题干中如需提及该概念只可出现概念名称本身，不得附释义/搭配/同义词）：{knowledge_point}
{self._avoid_section(avoid_questions)}
要求：
1. 问题要开放但有明确答题要点
2. 列出标准答案的关键要点（3-5个）
3. 答案不要太长，控制在100字以内
4. question 只包含问题本身，严禁附加词条说明、知识卡片等提示文字

返回JSON：
{{
    "question": "简答题问题",
    "key_points": ["要点1", "要点2", "要点3"],
    "sample_answer": "参考答案",
    "explanation": "评分标准说明"
}}
"""

        response = await self.llm.generate(prompt)
        data = self._parse_json(response) or {}

        # 对于简答题，将关键要点作为评分依据
        key_points = data.get("key_points") or []
        if not isinstance(key_points, list):
            key_points = [str(key_points)]

        return Exercise(
            exercise_id=str(uuid.uuid4()),
            exercise_type=ExerciseType.SHORT_ANSWER,
            difficulty=difficulty,
            question=data.get("question") or "",
            correct_answer=str(key_points),  # 存储为字符串
            explanation=data.get("explanation") or "",
            knowledge_point=knowledge_point,
            reward_type=self._assign_reward_type()
        )

    def _assign_reward_type(self) -> str:
        """分配奖励类型"""
        import random
        rewards = ["insight", "logic", "knowledge", "extra_turn", "hidden_clue"]
        return random.choice(rewards)

    def _parse_json(self, response: str) -> Optional[Dict]:
        """解析JSON"""
        return extract_json(response)


class ExerciseGrader:
    """习题评分器"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def grade_exercise(
        self,
        exercise: Exercise,
        user_answer: str
    ) -> Dict:
        """评分习题"""

        if exercise.exercise_type in [ExerciseType.SINGLE_CHOICE, ExerciseType.TRUE_FALSE]:
            return self._grade_objective_question(exercise, user_answer)
        else:
            return await self._grade_subjective_question(exercise, user_answer)

    def _grade_objective_question(
        self,
        exercise: Exercise,
        user_answer: str
    ) -> Dict:
        """评分客观题（选择题、判断题）"""

        import re

        def tf_normalize(ans: str) -> str:
            ans = (ans or "").strip().upper()
            # 判断题常见变体归一化
            if ans in ("TRUE", "T", "对", "正确", "√", "YES", "Y"):
                return "对"
            if ans in ("FALSE", "F", "错", "错误", "×", "NO", "N"):
                return "错"
            return ans

        def letter_of(ans: str) -> str:
            """提取开头的选项字母（A-D）。要求字母后是分隔符/空白/结尾，
            避免把 ARP、B超 这类单词误判成选项字母"""
            m = re.match(r'^([A-D])(?=\s*[.、．:：，,]|\s+|$)', (ans or "").strip(), re.IGNORECASE)
            return m.group(1).upper() if m else ""

        def strip_letter(ans: str) -> str:
            """去掉「A. 」这类选项前缀，返回剩余文本"""
            m = re.match(r'^[A-D]\s*[.、．:：，,]\s*(.+)$', (ans or "").strip(), re.IGNORECASE)
            return m.group(1).strip() if m else (ans or "").strip()

        u_raw = (user_answer or "").strip()
        c_raw = (exercise.correct_answer or "").strip()

        u_letter, c_letter = letter_of(u_raw), letter_of(c_raw)
        if u_letter and c_letter:
            # 两边都能提取出选项字母 → 直接比字母（覆盖用户提交整段「A. xxx」的情况）
            is_correct = u_letter == c_letter
        elif u_letter or c_letter:
            # 一边是字母一边是文字：借助 options 把字母解析成选项文字再比对
            letter, other_text = (u_letter, strip_letter(c_raw)) if u_letter else (c_letter, strip_letter(u_raw))
            target_text = None
            for opt in (exercise.options or []):
                if letter_of(opt) == letter:
                    target_text = strip_letter(opt)
                    break
            is_correct = bool(target_text) and target_text.upper() == other_text.upper()
            if not is_correct:
                # 兜底走判断题归一化（对/错）
                is_correct = tf_normalize(u_raw) == tf_normalize(c_raw)
        else:
            is_correct = tf_normalize(u_raw) == tf_normalize(c_raw)

        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "feedback": exercise.explanation if not is_correct else "回答正确！",
            "correct_answer": exercise.correct_answer
        }

    async def _grade_subjective_question(
        self,
        exercise: Exercise,
        user_answer: str
    ) -> Dict:
        """评分主观题（简答题）- 使用AI评分"""

        # 解析关键要点
        import ast
        try:
            key_points = ast.literal_eval(exercise.correct_answer)
        except:
            key_points = []

        prompt = f"""
你是一个公正的阅卷老师。请评判学生的简答题回答。

题目：{exercise.question}

标准答案的关键要点：
{chr(10).join(f"- {kp}" for kp in key_points)}

学生的回答：
\"\"\"{user_answer}\"\"\"

评分标准：
- 每个关键要点20分
- 表述清晰、逻辑正确可加分
- 完全正确满分100分
- 达到60分及格

返回JSON：
{{
    "score": 75,
    "is_correct": true/false,  # 60分及以上为正确
    "covered_points": ["学生答对的要点1", "要点2"],
    "missing_points": ["遗漏的要点1"],
    "feedback": "评语，指出优点和不足"
}}
"""

        response = await self.llm.generate(prompt)
        result = self._parse_json(response) or {}

        # score可能是字符串，安全转换
        try:
            score = float(result.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        return {
            "is_correct": score >= 60,
            "score": score,
            "feedback": result.get("feedback") or "",
            "covered_points": result.get("covered_points") or [],
            "missing_points": result.get("missing_points") or []
        }

    def _parse_json(self, response: str) -> Optional[Dict]:
        """解析JSON"""
        return extract_json(response)
