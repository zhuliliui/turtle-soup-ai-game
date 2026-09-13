"""游戏状态模型"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import uuid


class GameMode(Enum):
    ENTERTAINMENT = "entertainment"
    LEARNING = "learning"


class InquiryType(Enum):
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"
    VERIFICATION = "verification"
    HINT = "hint"


@dataclass
class ReasoningAbility:
    """推理能力值"""
    observation: int = 1
    logic: int = 1
    association: int = 1
    knowledge: int = 1
    reasoning_level: int = 1

    def gain(self, ability_type: str, amount: int = 1):
        """获得能力增益"""
        if hasattr(self, ability_type):
            setattr(self, ability_type, getattr(self, ability_type) + amount)


@dataclass
class ReasoningBonus:
    """推理增益"""
    bonus_type: str  # insight, logic, knowledge, extra_turn
    description: str
    used: bool = False


@dataclass
class Clue:
    """线索"""
    clue_id: str
    content: str
    revealed: bool = False
    critical: bool = False
    related_knowledge: Optional[str] = None
    perspective: str = ""  # 线索的视角来源：为什么"这个身份"的玩家会知道这条信息


@dataclass
class CaseInfo:
    """案件信息"""
    case_id: str
    title: str
    background: str
    victim_info: str
    scene_description: str

    # 真相（玩家不可见）
    truth: Dict[str, str] = field(default_factory=dict)

    # 线索系统
    revealed_clues: List[Clue] = field(default_factory=list)
    hidden_clues: List[Clue] = field(default_factory=list)

    # 谜团
    mysteries: List[str] = field(default_factory=list)

    # 身份专属行动（视角层产物）：[{name, desc, result(保密情报), perspective}]
    identity_actions: List[Dict] = field(default_factory=list)

    # 可询问的人物（视角层产物）：与案件和玩家身份相关的NPC称呼列表
    askable_people: List[str] = field(default_factory=list)


@dataclass
class InquiryRecord:
    """推理记录"""
    inquiry_id: str
    inquiry_type: InquiryType
    content: str
    ai_response: str
    timestamp: float
    revealed_info: List[str] = field(default_factory=list)
    reasoning_progress: float = 0.0


@dataclass
class LearningProgress:
    """学习进度"""
    material_id: str
    knowledge_points: List[str] = field(default_factory=list)
    exercises_completed: int = 0
    exercises_correct: int = 0
    exercises_generated: int = 0  # 已生成的挑战总数（用于题型/知识点轮转，保证每次题目不一样）
    asked_questions: List[str] = field(default_factory=list)  # 已出过的题目（提示 AI 避免重复）
    earned_bonuses: List[ReasoningBonus] = field(default_factory=list)


@dataclass
class GameState:
    """完整游戏状态"""
    game_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: GameMode = GameMode.ENTERTAINMENT

    # 用户身份
    user_identity: str = ""

    # 案件
    case: Optional[CaseInfo] = None

    # 推理系统
    ability: ReasoningAbility = field(default_factory=ReasoningAbility)
    total_turns: int = 10
    remaining_turns: int = 10
    verification_chances: int = 1

    # 推理记录
    inquiry_history: List[InquiryRecord] = field(default_factory=list)
    confirmed_info: List[str] = field(default_factory=list)

    # 推理进度
    reasoning_progress: float = 0.0
    stuck_count: int = 0  # 连续无进展次数

    # 增益系统
    active_bonuses: List[ReasoningBonus] = field(default_factory=list)

    # 身份专属行动运行时状态：[{id, name, desc, result, used}]
    identity_actions: List[Dict] = field(default_factory=list)

    # 对话流水（用于持久化恢复后重建聊天界面）
    inquiry_log: List[Dict] = field(default_factory=list)

    # 学习模式
    learning: Optional[LearningProgress] = None

    # 游戏状态
    game_over: bool = False
    case_solved: bool = False

    def use_turn(self):
        """消耗一次推理机会"""
        if self.remaining_turns > 0:
            self.remaining_turns -= 1

    def add_bonus_turn(self):
        """增加推理机会"""
        self.remaining_turns += 1
        self.total_turns += 1

    def reveal_clue(self, clue: Clue):
        """揭示线索"""
        if self.case:
            clue.revealed = True
            self.case.revealed_clues.append(clue)
            if clue in self.case.hidden_clues:
                self.case.hidden_clues.remove(clue)

    def update_progress(self, progress_delta: float):
        """更新推理进度"""
        old_progress = self.reasoning_progress
        self.reasoning_progress = min(100.0, self.reasoning_progress + progress_delta)

        if abs(progress_delta) < 5:
            self.stuck_count += 1
        else:
            self.stuck_count = 0

        return self.reasoning_progress - old_progress

    def is_stuck(self) -> bool:
        """判断是否卡住"""
        return self.stuck_count >= 3
