"""AI主持人人格系统"""
from typing import Dict, List, Optional
import random


class HostPersona:
    """AI主持人人格 - 让Agent有游戏感而不是聊天机器人感"""

    def __init__(self):
        self.name = "推理主持人"

    def greet_player(self, identity: str, mode: str) -> str:
        """欢迎玩家"""
        if mode == "entertainment":
            return f"""
欢迎，{identity}。

我将为你主持一场推理游戏。

在接下来的案件中，你将运用你的观察力、逻辑力和推理能力，还原事件的真相。

记住：
- 每一个细节都可能是关键
- 不要被表象迷惑
- 真相往往藏在你想不到的地方

准备好了吗？让我们开始...
"""
        else:
            return f"""
欢迎进入学习推理模式，{identity}。

在这个模式中，你不仅要破解案件，还要通过学习获得推理能力的增益。

知识就是力量 - 每一次正确的学习，都会让你的推理更加锐利。

当你遇到困难时，完成学习挑战可以获得：
🔍 隐藏线索
🧠 推理增益
⏳ 额外推理机会

让我们开始这场知识与推理的双重挑战...
"""

    def present_case(self, case_title: str, background: str, scene: str) -> str:
        """呈现案件"""
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 案件档案

【{case_title}】

{background}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

现场情况：

{scene}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

现在，推理开始。

你可以：
• 提出问题，我会如实回答
• 提出你的猜想，我会给出判断
• 当你准备好时，还原完整真相

记住，你有限的推理机会。每一次提问都要深思熟虑。
"""

    def respond_to_question(
        self,
        question: str,
        answer: str,
        hint: str = "",
        is_critical: bool = False
    ) -> str:
        """回应玩家提问 - 带有主持人风格"""

        # 根据问题的关键程度选择不同的反馈风格
        if is_critical:
            intros = [
                "这个问题很关键。",
                "你问到了重点。",
                "这是一个非常敏锐的问题。",
                "你的直觉很准确。",
            ]
        else:
            intros = [
                "关于这个问题...",
                "让我告诉你...",
                "答案是...",
                "关于这一点...",
            ]

        intro = random.choice(intros)

        response = f"{intro}\n\n「{answer}」"

        if hint:
            response += f"\n\n{hint}"

        return response

    def evaluate_hypothesis(
        self,
        hypothesis: str,
        correctness: float,
        feedback: str
    ) -> str:
        """评价玩家的猜想"""

        if correctness > 0.8:
            evaluation = "你的推理非常接近真相了。"
        elif correctness > 0.5:
            evaluation = "你的推理有一定道理，但还不够完整。"
        elif correctness > 0.3:
            evaluation = "你的推理方向有些偏差。"
        else:
            evaluation = "这个推理可能把你带入了死胡同。"

        return f"""
{evaluation}

{feedback}

继续思考，真相就在眼前。
"""

    def hint_stuck(self, turns_remaining: int, has_learning: bool) -> str:
        """玩家卡住时的提示"""

        base_hint = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤔 推理遇到瓶颈了吗？

你还剩 {turns_remaining} 次推理机会。

你可以：
"""

        options = [
            "🔍 请求一个普通提示（消耗1次机会）",
            "🎲 使用验证机会换取关键线索",
        ]

        if has_learning:
            options.insert(1, "🧠 完成学习挑战获得增益")

        for opt in options:
            base_hint += f"\n{opt}"

        base_hint += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        return base_hint

    def reveal_clue(self, clue_content: str, is_hidden: bool = False) -> str:
        """揭示线索"""
        if is_hidden:
            return f"""
✨ 隐藏线索已解锁

━━━━━━━━━━━━━━━━━━━━━━━━━━━

{clue_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

这条线索可能改变你对案件的理解。
"""
        else:
            return f"""
📌 新线索

{clue_content}
"""

    def learning_challenge_intro(self, knowledge_point: str = "") -> str:
        """学习挑战弹窗不再展示介绍文案（页面精简，由前端删除该区块）"""
        return ""

    def turns_exhausted_note(self, has_learning: bool = False) -> str:
        """推理机会用尽提示（不再直接 game over：可赚机会/可直接验证真相）"""
        if has_learning:
            return (
                "⏳ 推理机会已用完！\n"
                "• 完成「学习挑战」可以赚取额外推理机会\n"
                "• 或者直接点击「还原真相」验证你的推理"
            )
        return (
            "⏳ 推理机会已用完！\n"
            "• 可以直接点击「还原真相」验证你的推理\n"
            "• 或点击「再来一局」开始新案件"
        )

    def learning_success(self, bonus_type: str, bonus_desc: str) -> str:
        """学习成功反馈（bonus_desc自带图标，不再重复添加）"""

        return f"""
✅ 挑战完成

{bonus_desc}

你的推理能力得到了提升。现在，回到案件中去吧。
"""

    def learning_failure(self, correct_answer: str, explanation: str) -> str:
        """学习失败反馈"""
        return f"""
❌ 答案不正确

正确答案是：{correct_answer}

{explanation}

不要灰心，你可以：
• 重新学习这个知识点
• 继续用现有的线索推理
"""

    def verification_incorrect(
        self,
        attempt: str,
        errors: List[str],
        chances_left: int,
        verification_result: Optional[dict] = None
    ) -> str:
        """验证失败：给出还原度评分（命中/错误/遗漏），让玩家知道说对了多少"""

        vr = verification_result or {}
        try:
            completeness = int(vr.get("completeness") or 0)
        except (TypeError, ValueError):
            completeness = 0
        completeness = max(0, min(100, completeness))

        # 五要素命中情况
        accuracy = vr.get("accuracy") or {}
        labels = {"who": "人物", "what": "事件", "why": "动机", "how": "手法", "twist": "反转"}
        hits = [label for key, label in labels.items() if accuracy.get(key) is True]
        misses = [label for key, label in labels.items() if accuracy.get(key) is False]

        bar = "█" * (completeness // 10) + "░" * (10 - completeness // 10)

        feedback = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━

你的推理：
{attempt}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

「否」—— 很遗憾，真相并非如此。

📊 真相还原度：{completeness}%  {bar}
🔎 要素命中：{'、'.join(hits) if hits else '暂无'}　❌ 未命中：{'、'.join(misses) if misses else '无'}
"""
        error_list = vr.get("errors") or errors or []
        if error_list:
            feedback += "\n❌ 与真相不符：\n" + "\n".join(f"  · {e}" for e in error_list[:4])
        missing_list = vr.get("missing") or []
        if missing_list:
            feedback += "\n🕳 你遗漏的关键点：\n" + "\n".join(f"  · {m}" for m in missing_list[:4])

        if chances_left > 0:
            feedback += f"\n\n你还有 {chances_left} 次验证机会。参照上面的差距，再试一次。"
        else:
            feedback += "\n\n这是你最后的验证机会已经用完。"

        feedback += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        return feedback

    def identity_action_result(self, action_name: str, result: str) -> str:
        """身份专属行动执行结果（免费，不消耗推理机会）"""
        return f"""
🎭 身份行动「{action_name}」执行完毕

━━━━━━━━━━━━━━━━━━━━━━━━━━━

{result}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

这份情报只有你的身份才能拿到（身份行动免费，不消耗推理机会）。
"""

    def case_solved(
        self,
        reasoning_path: List[str],
        key_insights: List[str],
        turns_used: int,
        total_turns: int,
        truth: str = "",
        completeness: float = 0.0,
        is_excellent: bool = False,
        mysteries_resolved: Optional[List] = None,
        mysteries_pending: Optional[List[str]] = None,
    ) -> str:
        """破案成功：完整揭示全部剧情真相

        truth: 完整真相全文（必给，让玩家看到全部剧情）
        completeness: 还原度评分（0-100）
        is_excellent: 是否优秀（>80）
        mysteries_resolved/pending: 待解谜团的逐条揭秘
        """

        efficiency = (total_turns - turns_used) / total_turns * 100 if total_turns else 0

        if is_excellent or completeness > 80:
            rating = "🌟🌟🌟 完美还原"
        elif efficiency > 70:
            rating = "🌟🌟🌟 完美推理"
        elif efficiency > 40:
            rating = "🌟🌟 优秀推理"
        else:
            rating = "🌟 推理成功"

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 案件破解！

{rating}
还原度：{completeness:.0f}%
推理效率：{efficiency:.1f}%
使用轮次：{turns_used}/{total_turns}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 全部真相

{truth}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        # 待解谜团逐一揭秘（让玩家看到完整剧情闭环）
        resolved = mysteries_resolved or []
        pending = mysteries_pending or []
        if resolved:
            report += "\n🔍 待解谜团 · 逐一揭秘\n\n"
            for i, (mystery, answer) in enumerate(resolved, 1):
                report += f"❓ 谜团{i}：{mystery}\n"
                report += f"💡 解答：{answer}\n\n"
        if pending:
            report += "🔍 其余待解谜团（答案可从上方真相推知）\n\n"
            for mystery in pending:
                report += f"❓ {mystery}\n"
            report += "\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🧠 你的推理路径：\n\n"

        for i, step in enumerate(reasoning_path, 1):
            report += f"{i}. {step}\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n💡 关键洞察：\n\n"

        for insight in key_insights:
            report += f"• {insight}\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n恭喜你，侦探。真相已经大白于天下。"

        return report

    def game_over(
        self,
        truth: str,
        what_missed: List[str],
        mysteries_resolved: Optional[List] = None,
        mysteries_pending: Optional[List[str]] = None
    ) -> str:
        """游戏结束（含待解谜团逐一揭秘）

        mysteries_resolved: [(谜团原文, 解答), ...] — AI 基于真相生成的逐条揭秘
        mysteries_pending:  [谜团原文, ...] — 未能生成解答的谜团（降级展示）
        """
        result = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ 推理机会已用尽

━━━━━━━━━━━━━━━━━━━━━━━━━━━

真相：

{truth}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        resolved = mysteries_resolved or []
        pending = mysteries_pending or []

        if resolved:
            result += "\n🔍 待解谜团 · 逐一揭秘\n\n"
            for i, (mystery, answer) in enumerate(resolved, 1):
                result += f"❓ 谜团{i}：{mystery}\n"
                result += f"💡 解答：{answer}\n\n"

        if pending:
            result += "🔍 其余待解谜团（答案可从上方真相推知）\n\n"
            for mystery in pending:
                result += f"❓ {mystery}\n"
            result += "\n"

        result += """━━━━━━━━━━━━━━━━━━━━━━━━━━━

你错过的关键点：

"""
        if not what_missed:
            result += "（没有遗漏的关键线索，你的调查已经相当充分。）\n"
        for i, missed in enumerate(what_missed, 1):
            result += f"{i}. {missed}\n"

        result += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━

推理是一门艺术，需要耐心和洞察力。

下次，你会做得更好。
"""

        return result

    def ability_level_up(self, ability_name: str, new_level: int) -> str:
        """能力升级"""

        ability_display = {
            "observation": "观察力",
            "logic": "逻辑力",
            "association": "联想力",
            "knowledge": "知识力",
            "reasoning_level": "推理等级"
        }

        display_name = ability_display.get(ability_name, ability_name)

        return f"✨ {display_name} 提升至 Lv.{new_level}"
