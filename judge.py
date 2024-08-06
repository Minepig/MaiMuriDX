from typing import TYPE_CHECKING
from collections.abc import Sequence

from core import JUDGE_TPS, Pad
from action import ActionExtraPadDown
from simai import SimaiNote

if TYPE_CHECKING:
    from action import Action


# The muri detector work flow:
#  1. simai source file is read and parse by [parser.SimaiParser], producing a sequence of [SimaiNote]
#  2. [parser.SimaiParser] workup the sequence, makes some modifications
#  3. Generate a sequence of [action.Action] according to the note sequence
#  4. two sequences are fed into [judge.JudgeManager]
#  5. [judge.JudgeManager] is ticked, performing actions, maintaining the touchpad states, updating notes
#  6. [render.RenderManager] access two sequence saving in [judge.JudgeManager] and do rendering stuffs

# 无理分类：
# 内屏无理：slide剩余2个区及以下时触碰结尾的A区，蹭出非critical判定。判定方法是模拟全内屏击打实时计算判定
# 外屏无理：slide需要先外键击打再进入A区，此处认为时间间隔约为3帧(50ms)，若有同头tap会被蹭绿。
#         判定时认为slide启动时刻后1~12帧(16.67~200ms)期间只要出现同头tap即为外无
# 多押无理：同时出现超过2个触点。判定时可将重叠的slide触点合并，一组touch group若总半径不超过一定限度可认为是单手配置，
#         slide撞touch时该touch视为无需处理，不构成多押
# 撞尾无理：slide轨迹进入A区的时刻该位置出现tap会被蹭绿。判定时认为slide轨迹中部在引导星星进入A区时刻的±200ms内出现tap为撞尾；
#         对于slide终点，区间取 (进入A区时刻-200ms ~ 星星结束+150ms) 与 (进入A区时刻±200ms) 中较大者
# 叠键无理：同一时刻，同一判定区需要处理两个非slide的note，例如hold夹tap，对于超慢slide占用某个判定区时该判定区出现note，也认为是叠键
#         判定方法是模拟击打，若某个判定区已被按下时再次尝试按下这个判定区，pad down事件就会被吞掉。

class JudgeManager:
    def __init__(self):
        self.note_sequence: Sequence[SimaiNote] | None = None
        self.action_sequence: Sequence[Action] | None = None
        self.timer = -JUDGE_TPS * 3
        self.note_pointer = 0
        self.action_pointer = 0
        self.active_notes: list[SimaiNote] = []
        self.active_actions: list[Action] = []
        self.pad_states = 0
        self.finished_notes: list[SimaiNote] = []

    def load_chart(self, note_sequence: "Sequence[SimaiNote]", action_sequence: "Sequence[Action]"):
        self.note_sequence = note_sequence
        self.action_sequence = action_sequence
        self.timer = -JUDGE_TPS * 3
        self.note_pointer = 0
        self.action_pointer = 0
        self.active_notes = []
        self.active_actions = []
        self.pad_states = 0
        self.finished_notes = []

    def tick(self, elapsed_time: float):
        last_timer = self.timer
        self.timer += elapsed_time

        for note in self.note_sequence[self.note_pointer:]:
            if self.timer >= note.moment - JUDGE_TPS:
                self.note_pointer += 1
                self.active_notes.append(note)
            else:
                break
        for action in self.action_sequence[self.action_pointer:]:
            if self.timer >= action.moment - JUDGE_TPS:
                self.action_pointer += 1
                self.active_actions.append(action)
            else:
                break

        # update touchpads
        next_pad_state = 0
        pad_down_set = set()
        finished_actions = []
        for action in self.active_actions:
            if isinstance(action, ActionExtraPadDown) and last_timer <= action.moment < self.timer:
                pad_down_set.add(action.pad)

            circle = action.update(self.timer)
            if circle is None:
                continue
            # calculate circle overlap
            center, radius = circle
            for pad in Pad:
                if abs(pad.vec - center) <= (pad.radius + radius):
                    next_pad_state |= 1 << pad.value

            # TODO: 轨迹重合的星星动作合并

            if action.finish(self.timer):
                finished_actions.append(action)

        for action in finished_actions:
            self.active_actions.remove(action)

        pad_down_this_tick = (~self.pad_states) & next_pad_state
        self.pad_states = next_pad_state
        pad_dict = {}
        for pad in Pad:
            pad_dict[pad] = bool(next_pad_state & (1 << pad.value))
            if pad_down_this_tick & (1 << pad.value):
                pad_down_set.add(pad)

        # notify pad down events
        for pad in pad_down_set:
            for note in self.active_notes:
                # in time order
                if note.on_pad_down(self.timer, pad):
                    # ret val == True -> event consumed
                    break

        # update routine
        for note in self.active_notes:
            note.update(self.timer, pad_dict)
            if note.finish(self.timer):
                self.finished_notes.append(note)
        for note in self.finished_notes:
            self.active_notes.remove(note)

    def clear_finished_notes(self):
        self.finished_notes = []





if __name__ == "__main__":
    pass

