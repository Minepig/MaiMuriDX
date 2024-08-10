from typing import NamedTuple
from collections.abc import Sequence, Iterable

from core import JUDGE_TPF, JUDGE_TPS, DISTANCE_MERGE_SLIDE, JudgeResult, Pad
from core import OVERLAY_THRESHOLD, TOUCH_ON_SLIDE_THRESHOLD, COLLIDE_THRESHOLD, COLLIDE_TAIL_THRESHOLD, TAP_ON_SLIDE_THRESHOLD
from action import ActionExtraPadDown
from simai import SimaiNote, SimaiSlideChain, SimaiWifi, SimaiTap, SimaiHold, SimaiTouch, SimaiTouchHold, SimaiTouchGroup
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

class TouchPoint(NamedTuple):
    center: complex
    radius: float
    source: "Action"


class StaticMuriChecker:
    @staticmethod
    def _flatten_touch_group(note_sequence: Sequence[SimaiNote]):
        for note in note_sequence:
            if isinstance(note, SimaiTouchGroup):
                yield from note.children
            else:
                yield note

    @staticmethod
    def _overlap_record(note: SimaiNote, note2: SimaiNote) -> dict:
        return {
            "type": "Overlap",
            "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
            "cause": {"line": note2.cursor[0], "col": note2.cursor[1], "note": note2.cursor[2]},
        }

    @staticmethod
    def _tap_on_slide_record(note: SimaiNote, slide: SimaiNote, delta: float) -> dict:
        return {
            "type": "TapOnSlide",
            "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
            "cause": {"line": slide.cursor[0], "col": slide.cursor[1], "note": slide.cursor[2]},
            "delta": delta,
        }

    @staticmethod
    def _slide_head_tap_record(note: SimaiNote, slide: SimaiNote, delta: float) -> dict:
        return {
            "type": "SlideHeadTap",
            "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
            "cause": {"line": slide.cursor[0], "col": slide.cursor[1], "note": slide.cursor[2]},
            "delta": delta,
        }

    @classmethod
    def check(cls, note_sequence: Sequence[SimaiNote]):
        muri_records = []
        for i, note in enumerate(cls._flatten_touch_group(note_sequence)):
            for j, note2 in enumerate(cls._flatten_touch_group(note_sequence)):
                if note is note2:
                    continue

                if isinstance(note, SimaiSlideChain):
                    if isinstance(note2, SimaiTap | SimaiHold):
                        if note2.moment < note.shoot_moment or note2.moment > note.end_moment + COLLIDE_THRESHOLD:
                            continue  # 简单剪个枝，这里假设 COLLIDE_THRESHOLD > COLLIDE_TAIL_THRESHOLD

                        # TODO
                        # 这里有一个问题，SlideInfo里记录的进入时刻并不满足顺序关系，因为会有OR判定区之类的东西
                        # 1pp6 和 wifi 受到的影响最大，任何含1-3形状的也有一些影响
                        # 摆烂了，我选择只检查 进入A区±200ms 的撞尾

                        # 首先查第一个区的外无
                        if note2.pad == Pad(note.start % 8) and \
                                TAP_ON_SLIDE_THRESHOLD <= note2.moment - note.shoot_moment <= COLLIDE_THRESHOLD:
                            muri_records.append(cls._slide_head_tap_record(note2, note, note2.moment - note.shoot_moment))
                        # 逐段检查，逐个区检查
                        for info, duration, moment in zip(note.segment_infos, note.durations,
                                                          note.segment_shoot_moments):
                            for p, t in info.pad_enter_time:
                                if p != note2.pad:
                                    continue

                                enter_moment = moment + t * duration
                                # 区间左端点取进入当前区-200ms，但不要早于星星启动
                                start = max(enter_moment - COLLIDE_THRESHOLD, note.shoot_moment + TAP_ON_SLIDE_THRESHOLD)
                                # 区间右端点取两者更晚：进入下一个区 / 进入当前区+200ms
                                # 因为我不能确定“下一个区”，所以只取 进入当前区+200ms
                                end = enter_moment + COLLIDE_THRESHOLD
                                if start <= note2.moment <= end:
                                    muri_records.append(cls._tap_on_slide_record(note2, note, note2.moment - enter_moment))
                        # 对于最后一个区，区间尾额外延长到星星结束+50ms
                        if note2.pad == Pad(note.end % 8) and \
                                note.critical_moment + COLLIDE_THRESHOLD < note2.moment <= note.end_moment + COLLIDE_TAIL_THRESHOLD:
                            muri_records.append(cls._tap_on_slide_record(note2, note, note2.moment - note.critical_moment))

                    # 摆烂了，不查slide和touch叠键了，交给动态检测
                    # elif isinstance(note2, SimaiTouch | SimaiTouchHold):
                    #     for idx, (pad, moment) in enumerate(enter_moments[:-1]):
                    #         if pad != note2.pad:
                    #             continue
                    #         if (moment + TOUCH_ON_SLIDE_THRESHOLD
                    #                 <= note2.moment <= enter_moments[idx+1][1] - TOUCH_ON_SLIDE_THRESHOLD):
                    #             muri_records.append(cls._overlap_record(note2, note))

                elif isinstance(note, SimaiWifi):
                    # 偷个懒，wifi其实只需要查头尾
                    if isinstance(note2, SimaiTap | SimaiHold):
                        if note.start % 8 == note2.idx % 8 and \
                                TAP_ON_SLIDE_THRESHOLD <= note2.moment - note.shoot_moment <= COLLIDE_THRESHOLD:
                            muri_records.append(cls._slide_head_tap_record(note2, note, note2.moment - note.shoot_moment))
                        elif note2.idx % 8 in (note.end % 8, (note.end + 1) % 8, (note.end - 1) % 8):
                            start = note.critical_moment - COLLIDE_THRESHOLD
                            end = max(note.critical_moment + COLLIDE_THRESHOLD, note.end_moment + COLLIDE_TAIL_THRESHOLD)
                            if start <= note2.moment <= end:
                                muri_records.append(cls._tap_on_slide_record(note2, note, note2.moment - note.critical_moment))

                elif isinstance(note, SimaiTap | SimaiTouch):
                    if isinstance(note2, SimaiTap | SimaiTouch):
                        if i < j and note.pad == note2.pad and abs(note.moment - note2.moment) <= OVERLAY_THRESHOLD:
                            muri_records.append(cls._overlap_record(note, note2))

                    elif isinstance(note2, SimaiHold | SimaiTouchHold):
                        if note.pad == note2.pad and \
                                note2.moment - OVERLAY_THRESHOLD <= note.moment <= note2.end_moment + OVERLAY_THRESHOLD:
                            muri_records.append(cls._overlap_record(note, note2))

                elif isinstance(note, SimaiHold | SimaiTouchHold):
                    if isinstance(note2, SimaiHold | SimaiTouchHold):
                        if i < j and note.pad == note2.pad and (
                                note2.moment - OVERLAY_THRESHOLD <= note.moment <= note2.end_moment + OVERLAY_THRESHOLD
                                or note.moment - OVERLAY_THRESHOLD <= note2.moment <= note.end_moment + OVERLAY_THRESHOLD
                        ):
                            muri_records.append(cls._overlap_record(note, note2))


        for record in muri_records:
            if record["type"] == "Overlap":
                msg = "叠键无理：\"{note}\"(L{line},C{col}) 与 ".format_map(record["affected"])
                msg += "\"{note}\"(L{line},C{col}) 重叠".format_map(record["cause"])
                print(msg)
            elif record["type"] == "SlideHeadTap":
                msg = "外键无理：\"{note}\"(L{line},C{col}) 可能被 ".format_map(record["affected"])
                msg += "\"{note}\"(L{line},C{col}) 蹭到 ".format_map(record["cause"])
                msg += "(%+.2f ms)" % (record["delta"] * 1000 / JUDGE_TPS)
                print(msg)
            elif record["type"] == "TapOnSlide":
                msg = "撞尾无理：\"{note}\"(L{line},C{col}) 可能被 ".format_map(record["affected"])
                msg += "\"{note}\"(L{line},C{col}) 蹭到 ".format_map(record["cause"])
                msg += "(%+.2f ms)" % (record["delta"] * 1000 / JUDGE_TPS)
                print(msg)

        return muri_records


class MultiTouchMuri:
    __slots__ = ("_cursors",)
    def __init__(self, cursors: Iterable[tuple[int, int, str]]):
        self._cursors = tuple(sorted(cursors))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cursors == other._cursors

    def __hash__(self):
        return hash(self._cursors)


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
        self.last_pad_source: dict[Pad, Action] = {}
        self.multi_touch_muri: set[MultiTouchMuri] = set()
        self.muri_record_list = []
        self.static_muri_record_list = []

    def load_chart(self, note_sequence: "Sequence[SimaiNote]", action_sequence: "Sequence[Action]"):
        self.note_sequence = note_sequence
        self.action_sequence = action_sequence

    def tick(self, elapsed_time: float) -> tuple[list[TouchPoint], int, list[SimaiNote]]:
        """返回值是三元组。ret[0]: 本tick的触点列表，ret[1]: 手的数量，ret[2]: 本tick完成的note列表"""
        # 更新时钟
        last_timer = self.timer
        self.timer += elapsed_time

        # 将后续note与action激活
        for note in self.note_sequence[self.note_pointer:]:
            if self.timer >= note.moment - JUDGE_TPS * 2:
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

        # ===== 更新触摸状态 =====
        next_pad_state = 0      # 记录下一tick初始时的触摸板状态
        finished_actions: list[Action] = []     # 记录已经完成的action
        this_frame_touch_points: list[TouchPoint] = []      # 记录本tick中的触点

        pad_down_source_dict: dict[Pad, Action] = {}    # 记录本tick触发的pad down事件及其来源
        # 记录本tick触发的pad down事件及其来源
        pad_up_source_dict: dict[Pad, Action | None] = {p: None for p in Pad}
        # 记录下一tick初始时各激活触摸板的来源
        pad_source_dict: dict[Pad, Action | None] = {p: None for p in Pad}
        # 说明：pad_down_source_dict之后会进行迭代操作，故只有真正发生了pad down的pad才会加入其中（dict当set用）
        #      pad_up_source_dict与pad_source_dict之后会传参用作look up，故所有pad都加入其中，预先置为None

        # 首先计算本tick内的触点
        for action in self.active_actions:
            # 外无动作处理
            if isinstance(action, ActionExtraPadDown) and last_timer <= action.moment < self.timer:
                pad_down_source_dict[action.pad] = action

            # 计算当前触点并记录
            circle = action.update(self.timer)
            if circle is not None:
                center, radius = circle
                touch_point = TouchPoint(center, radius, action)

                # 如果当前动作允许触点合并 (目前只有普通slide的触点允许) 则尝试合并
                if not action.can_merge():
                    this_frame_touch_points.append(touch_point)
                else:
                    for center2, radius2, action2 in this_frame_touch_points:
                        if not action2.can_merge():
                            continue
                        if abs(center - center2) < DISTANCE_MERGE_SLIDE:
                            break
                    else:
                        this_frame_touch_points.append(touch_point)

            # 记录已经完成的action，等待清除
            if action.finish(self.timer):
                finished_actions.append(action)

        # 从活动action列表里清除已经完成的action
        for action in finished_actions:
            self.active_actions.remove(action)

        # 计算按下的判定区，以及多押检测
        hand_count = 0
        for center, radius, action in this_frame_touch_points:
            # 找到所有与触点圆相交的判定区
            for pad in Pad:
                if abs(pad.vec - center) <= (pad.radius + radius):
                    next_pad_state |= 1 << pad.value
                    pad_source_dict[pad] = action
            # 记录手数
            if action.require_two_hands:
                hand_count += 2
            else:
                hand_count += 1

        # 出现多押的情况，记录多押无理
        if hand_count > 2:
            affected_cursors = set(a.source.cursor for _0, _1, a in this_frame_touch_points)
            muri = MultiTouchMuri(affected_cursors)
            if muri not in self.multi_touch_muri:
                self.multi_touch_muri.add(muri)     # 记录下来避免重复报告
                self.muri_record_list.append(
                    {
                        "time": self.timer / JUDGE_TPS,
                        "type": "MultiTouch",
                        "hand_count": hand_count,
                        "cause": [{"line": c[0], "col": c[1], "note": c[2]} for c in affected_cursors],
                    }
                )

                s, f = divmod(self.timer / JUDGE_TPF, 60)
                m, s = divmod(int(s), 60)
                msg = "[%02d:%02dF%05.2f] 多押无理：" % (m, s, f)
                msg += "下列note可能形成了%d押\n    " % hand_count
                msg += " ".join("\"{2}\"(L{0},C{1})".format(*n) for n in affected_cursors)
                print(msg)

        # 产生pad down与pad up事件
        # pad up目前只在slide判定中作为参考
        pad_down_this_tick = (~self.pad_states) & next_pad_state
        pad_up_this_tick = self.pad_states & (~next_pad_state)
        for pad in Pad:
            if pad_down_this_tick & (1 << pad.value):
                # 因为新按下的判定区肯定已经按下，直接把之前记录过的action拿来用
                pad_down_source_dict[pad] = pad_source_dict[pad]
            if pad_up_this_tick & (1 << pad.value):
                pad_up_source_dict[pad] = self.last_pad_source[pad]

        self.pad_states = next_pad_state
        self.last_pad_source = pad_source_dict

        # ===== 更新note，计算判定 =====
        finished_notes: list[SimaiNote] = []

        # 发送pad down事件，self.active_notes是时间正序的
        for pad, action in pad_down_source_dict.items():
            for note in self.active_notes:
                if note.on_pad_down(self.timer, pad, action):
                    # retval == True -> event consumed
                    break

        # note的例行更新
        for note in self.active_notes:
            note.update(self.timer, pad_source_dict, pad_up_source_dict)
            if note.finish(self.timer):
                finished_notes.append(note)

        # 从活动note列表里清除已经结束的note
        for note in finished_notes:
            self.active_notes.remove(note)

            # ========== 如果判定结果不是critical说明存在无理 ==========
            if note.judge == JudgeResult.Bad:
                if isinstance(note, SimaiSlideChain):
                    # 是星星，那就是内屏无理
                    record = {
                        "time": self.timer / JUDGE_TPS,
                        "type": "SlideTooFast",
                        "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
                        "judge_areas": [],
                    }

                    s, f = divmod(self.timer / JUDGE_TPF, 60)
                    m, s = divmod(int(s), 60)
                    msg = "[%02d:%02dF%05.2f] 内屏无理：" % (m, s, f)
                    msg += "\"{2}\"(L{0},C{1}) 被提前蹭掉，相关判定区如下".format(*note.cursor)

                    # 首先找到现在slide应当处理到哪个区
                    idx = 0
                    for idx, t in enumerate(note.segment_shoot_moments):
                        if t > self.timer:
                            break
                    idx -= 1
                    p = (self.timer - note.segment_shoot_moments[idx]) / note.durations[idx]
                    if p < 0:
                        p = 0
                    # 我们假装每一段slide的判定区都是等距分布的，反正这里只是估算就够
                    area_idx = int(len(note.segment_infos[idx].judge_sequence) * p) + note.segment_idx_bias[idx]

                    # 我们关心从此时slide应当处理到的判定区起，一直到结尾的所有判定区都是怎么被按掉的
                    for i in range(area_idx, note.total_area_num):
                        entry = note.area_judge_actions[i]
                        area = note.judge_sequence[i]
                        if entry is None:
                            record["judge_areas"].append(
                                {
                                    "area": "/".join(p.name for p in area),
                                    "cause": "skipped",
                                    "time": -1,
                                }
                            )
                            msg += "\n    {0}: {1}".format("/".join(p.name for p in area), "Skipped")
                        else:
                            act, t = entry
                            record["judge_areas"].append(
                                {
                                    "area": "/".join(p.name for p in area),
                                    "cause": {"line": act.source.cursor[0],
                                              "col": act.source.cursor[1],
                                              "note": act.source.cursor[2]},
                                    "time": t / JUDGE_TPS,
                                }
                            )
                            s, f = divmod(t / JUDGE_TPF, 60)
                            m, s = divmod(int(s), 60)
                            msg += "\n    {0}: {1}@{2} (H{3}, S{4}, J{5}, E{6})".format(
                                "/".join(p.name for p in area),
                                "\"{2}\"(L{0},C{1})".format(*act.source.cursor),
                                "%02d:%02dF%05.2f" % (m, s, f),
                                "%+.2f" % ((t - note.moment) * 1000 / JUDGE_TPS),
                                "%+.2f" % ((t - note.shoot_moment) * 1000 / JUDGE_TPS),
                                "%+.2f" % ((t - note.critical_moment) * 1000 / JUDGE_TPS),
                                "%+.2f" % ((t - note.end_moment) * 1000 / JUDGE_TPS),
                            )
                    self.muri_record_list.append(record)
                    print(msg)

                elif isinstance(note, SimaiWifi):
                    record = {
                        "time": self.timer / JUDGE_TPS,
                        "type": "SlideTooFast",
                        "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
                        "judge_areas": [],
                    }
                    s, f = divmod(self.timer / JUDGE_TPF, 60)
                    m, s = divmod(int(s), 60)
                    msg = "[%02d:%02dF%05.2f] 内屏无理：" % (m, s, f)
                    msg += "\"{2}\"(L{0},C{1}) 被提前蹭掉，相关判定区如下".format(*note.cursor)
                    # 首先找到现在slide应当处理到哪个区
                    p = (self.timer - note.shoot_moment) / note.duration
                    if p < 0:
                        p = 0
                    area_idx = int(note.total_area_num * p)
                    # 我们关心从此时slide应当处理到的判定区起，一直到结尾的所有判定区都是怎么被按掉的
                    for i in range(area_idx, note.total_area_num):
                        for j in range(3):
                            entry = note.area_judge_actions[j][i]
                            area = note.info.tri_judge_sequence[j][i]
                            if entry is None:
                                record["judge_areas"].append(
                                    {
                                        "area": "/".join(p.name for p in area),
                                        "cause": "skipped",
                                        "time": -1,
                                    }
                                )
                                msg += "\n    {0}: {1}".format("/".join(p.name for p in area), "Skipped")
                            else:
                                act, t = entry
                                record["judge_areas"].append(
                                    {
                                        "area": "/".join(p.name for p in area),
                                        "cause": {"line": act.source.cursor[0],
                                                  "col": act.source.cursor[1],
                                                  "note": act.source.cursor[2]},
                                        "time": t / JUDGE_TPS,
                                    }
                                )
                                s, f = divmod(t / JUDGE_TPF, 60)
                                m, s = divmod(int(s), 60)
                                msg += "\n    {0}: {1}@{2} (H{3}, S{4}, J{5}, E{6})".format(
                                    "/".join(p.name for p in area),
                                    "\"{2}\"(L{0},C{1})".format(*act.source.cursor),
                                    "%02d:%02dF%05.2f" % (m, s, f),
                                    "%+.2f" % ((t - note.moment) * 1000 / JUDGE_TPS),
                                    "%+.2f" % ((t - note.shoot_moment) * 1000 / JUDGE_TPS),
                                    "%+.2f" % ((t - note.critical_moment) * 1000 / JUDGE_TPS),
                                    "%+.2f" % ((t - note.end_moment) * 1000 / JUDGE_TPS),
                                )
                    self.muri_record_list.append(record)
                    print(msg)

                else:
                    # 不是星星，那有可能是tap/hold提前蹭绿(fast)，或者叠键导致没判上(late)
                    if note.judge_moment < note.moment:
                        self.muri_record_list.append(
                            {
                                "time": self.timer / JUDGE_TPS,
                                "type": "SlideHeadTap" if isinstance(note.judge_action, ActionExtraPadDown) else "TapOnSlide",
                                "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
                                "cause": {"line": note.judge_action.source.cursor[0],
                                          "col": note.judge_action.source.cursor[1],
                                          "note": note.judge_action.source.cursor[2]},
                            }
                        )

                        s, f = divmod(self.timer / JUDGE_TPF, 60)
                        m, s = divmod(int(s), 60)
                        msg = "[%02d:%02dF%05.2f] " % (m, s, f)
                        msg += "外键无理：" if isinstance(note.judge_action, ActionExtraPadDown) else "撞尾无理："
                        msg += "\"{2}\"(L{0},C{1}) 被 ".format(*note.cursor)
                        msg += "\"{2}\"(L{0},C{1}) 蹭到 ".format(*note.judge_action.source.cursor)
                        msg += "(%+.2f ms)" % ((note.judge_moment - note.moment) * 1000 / JUDGE_TPS)

                    else:
                        self.muri_record_list.append(
                            {
                                "time": self.timer / JUDGE_TPS,
                                "type": "Overlap",
                                "affected": {"line": note.cursor[0], "col": note.cursor[1], "note": note.cursor[2]},
                            }
                        )

                        m, s = divmod(self.timer / JUDGE_TPS, 60)
                        msg = "[%02d:%05.2f] 叠键无理：" % (int(m), s)
                        msg += "\"{2}\"(L{0},C{1}) 似乎与另一个note重叠".format(*note.cursor)
                    print(msg)

        return this_frame_touch_points, hand_count, finished_notes






if __name__ == "__main__":
    pass

