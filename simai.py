from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from itertools import accumulate

from core import Pad, JudgeResult, \
                 TAP_CRITICAL, TAP_AVAILABLE, TOUCH_CRITICAL, TOUCH_AVAILABLE, \
                 SLIDE_CRITICAL, SLIDE_AVAILABLE, SLIDE_LEADING, SLIDE_DELTA_SHIFT, FLAG_WIFI_NEED_C
from slides import SlideInfo, WifiInfo
from util import get_covering_circle

if TYPE_CHECKING:
    from action import Action

class SimaiNote(metaclass=ABCMeta):
    def __init__(self, cursor: tuple[int, int, str], moment: float):
        """
        Base class of all simai notes.

        @param cursor: line & column No & note string in original file
        @param moment: the music timestamp when note is activated, in ticks
        """
        self.cursor: tuple[int, int, str] = cursor
        self.moment: float = moment
        self.judge: JudgeResult = JudgeResult.Not_Yet
        self.judge_moment: float = -1
        self.judge_action: "Action | None" = None   # 用来记录导致这个 note 判定的 action

    @abstractmethod
    def update(self, now: float, pad_states: "dict[Pad, Action | None]", pad_up_this_tick: "dict[Pad, Action | None]") -> None:
        """
        Update note routine.

        @param now: current music timestamp in ticks
        @param pad_states: current pad states (pressed or not) and its cause
        @param pad_up_this_tick: not None if a touchpad has ON -> OFF in this tick
        """
        raise NotImplementedError

    @abstractmethod
    def on_pad_down(self, now: float, pad: "Pad", action: "Action | None") -> bool:
        """
        Call when a touchpad is just pressed down.

        @param now: current music timestamp in ticks
        @param pad: the touchpad pressed
        @param action: the action causing this press
        @return: True if the pad down event is consumed
        """
        raise NotImplementedError

    @abstractmethod
    def finish(self, now: float) -> bool:
        """
        whether the note is finished

        @param now: current music timestamp in ticks
        """
        raise NotImplementedError

    def __repr__(self):
        return "<Simai \"{2}\" L{0}, C{1}>".format(*self.cursor)


class SimaiSimpleNote(SimaiNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, pad: Pad):
        """
        Base class of tap/hold/touch/touchhold.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param pad: the position of the note
        """
        super().__init__(cursor, moment)
        self.pad: Pad = pad

    @abstractmethod
    def _get_available_delta(self):
        raise NotImplementedError

    @abstractmethod
    def _get_critical_delta(self):
        raise NotImplementedError

    def update(self, now: float, pad_states: "dict[Pad, Action | None]", pad_up_this_tick: "dict[Pad, Action | None]"):
        if self.judge != JudgeResult.Not_Yet:
            return
        if now - self.moment > self._get_available_delta():
            # Too late
            self.judge = JudgeResult.Bad
            self.judge_moment = now
            # print("too late", self.moment)

    def on_pad_down(self, now: float, pad: Pad, action: "Action | None") -> bool:
        if self.judge != JudgeResult.Not_Yet:
            return False
        delta = now - self.moment
        if delta < -self._get_available_delta():
            return False
        if pad != self.pad:
            return False
        self.judge_moment = now
        self.judge_action = action
        self.judge = JudgeResult.Critical if (abs(delta) <= self._get_critical_delta()) else JudgeResult.Bad
        return True


class SimaiTap(SimaiSimpleNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, idx: int):
        """
        A Tap note.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param idx: the position of the note (1~8)
        """
        super().__init__(cursor, moment, Pad(idx % 8))
        self.idx = idx      # 这个指的是键号
        self.is_slide_head = False      # 表示是拍划的Tap，于是可以不生成action

    def set_slide_head(self, is_slide_head: bool):
        self.is_slide_head = is_slide_head

    def _get_available_delta(self):
        return TAP_AVAILABLE

    def _get_critical_delta(self):
        return TAP_CRITICAL

    def finish(self, now: float) -> bool:
        return self.judge != JudgeResult.Not_Yet


class SimaiHold(SimaiSimpleNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, idx: int, duration: float):
        """
        A Hold note.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param idx: the position of the note (1~8)
        @param duration: the duration of the note, in ticks
        """
        super().__init__(cursor, moment, Pad(idx % 8))
        self.idx = idx
        self.duration = duration
        self.end_moment = self.moment + self.duration

    def _get_available_delta(self):
        return TAP_AVAILABLE

    def _get_critical_delta(self):
        return TAP_CRITICAL

    def finish(self, now: float) -> bool:
        return now > self.end_moment


class SimaiTouch(SimaiSimpleNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, pad: str):
        """
        A TouchTap note.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param pad: the position of the note (A1, B3, C, E8, etc.)
        """
        super().__init__(cursor, moment, Pad[pad])
        self.on_slide = False       # 被slide撞到了，所以不用生成action
        self.group_parent: "SimaiTouchGroup | None" = None  # 如果是touchgroup的一员，这个属性会引用touchgroup对象，否则就是None

    def set_on_slide(self, on_slide: bool):
        self.on_slide = on_slide

    def set_group_parent(self, group_parent: "SimaiTouchGroup | None"):
        self.group_parent = group_parent

    def _get_available_delta(self):
        return TOUCH_AVAILABLE

    def _get_critical_delta(self):
        return TOUCH_CRITICAL

    def finish(self, now: float) -> bool:
        return self.judge != JudgeResult.Not_Yet


class SimaiTouchGroup(SimaiNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, children: Iterable[SimaiTouch]):
        """
        A group of adjacent TouchTap notes.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param children: the touch notes in this group
        """
        super().__init__(cursor, moment)
        self.children: tuple[SimaiTouch, ...] = tuple(children)
        for touch in children:
            touch.set_group_parent(self)

        # 计算最小覆盖圆，用于后续生成action
        points = [t.pad.vec for t in self.children]
        center, radius = get_covering_circle(points)
        self.center = center
        self.radius = radius

        self.on_slide = False       # 如果组里每一个touch都被slide撞了，那么这一整个组都不需要action了
        self.threshold = len(self.children) * 0.51  # 用来处理半数以上容错的

        self.effect_generated = [False] * len(self.children)    # 用来指示组里每个touch有没有显示过判定特效

    def set_on_slide(self, on_slide: bool):
        self.on_slide = on_slide

    def update(self, now: float, pad_states: "dict[Pad, Action | None]", pad_up_this_tick: "dict[Pad, Action | None]"):
        n = 0
        for touch in self.children:
            touch.update(now, pad_states, pad_up_this_tick)
            if touch.judge != JudgeResult.Not_Yet:
                n += 1
        if n >= self.threshold:
            # more than 50% is judged -> judge remaining
            for touch in self.children:
                touch.on_pad_down(now, touch.pad, None)

    def on_pad_down(self, now: float, pad: Pad, action: "Action") -> bool:
        for touch in self.children:
            if touch.on_pad_down(now, pad, action):
                return True
        return False

    def finish(self, now: float) -> bool:
        return all(touch.finish(now) for touch in self.children)


class SimaiTouchHold(SimaiSimpleNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, pad: str, duration: float):
        """
        A TouchHold note.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        @param pad: the position of the note (A1, B3, C, E8, etc.)
        @param duration: the duration of the note, in ticks
        """
        super().__init__(cursor, moment, Pad[pad])
        self.duration = duration
        self.end_moment = self.moment + self.duration

    def _get_available_delta(self):
        return TOUCH_AVAILABLE

    def _get_critical_delta(self):
        return TOUCH_CRITICAL

    def finish(self, now: float) -> bool:
        return now > self.end_moment


# ==================== Slide ====================
class SimaiSlideChain(SimaiNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, shapes: Iterable[str],
                 wait: float, durations: Iterable[float] = None, total_duration: float = None):
        """
        A festival Slide chain.
        Timeline: |- wait -| |- duration 1 -| |- duration 2 -| ... |- duration N -|

        @param cursor: line & column No in original file
        @param moment: the music timestamp when slide-track is activated and begins waiting (in ticks)
        @param shapes: a sequence of slide shape, denoting festival slide chain (e.g. ["1-3", "3-5", "5-7"])
        @param wait: the waiting time before slide-star shoots (in ticks)
        @param durations: the duration of each slide segment (in ticks)
        @param total_duration: the total duration of the entire slide chain (in ticks),
                                if durations is specified, this is ignored
        """
        if durations is None and total_duration is None:
            raise TypeError("either `durations` or `total_duration` need to be specified")

        super().__init__(cursor, moment)
        self.shapes = tuple(shapes)     # 存储了slidechain里每一段的形状，比如1-3-5这里就是("1-3", "3-5")
        self.segment_infos: tuple[SlideInfo, ...] = tuple(SlideInfo.get(k) for k in shapes)     # 每一段的信息
        self.start = self.segment_infos[0].start    # 整个slidechain的起点
        self.end = self.segment_infos[-1].end       # 终点

        self.available_moment = moment - SLIDE_LEADING     # slide is available 50ms before star is hit （slide入判）
        self.wait_duration = wait       # 初始等待时间（一般是一拍，但是单位是tick）
        self.shoot_moment = moment + wait   # slide启动时刻

        # 计算出每一个slide段的划动时间
        if durations is not None:
            self.durations = tuple(durations)
        else:
            lengths = [info.path.length() for info in self.segment_infos]
            total_length = sum(lengths)
            self.durations = tuple(x * total_duration / total_length for x in lengths)
        assert len(self.segment_infos) == len(self.durations)
        # 下面这个元组元素数比slide段数多一项，最后一项其实就是slide的结束时刻
        self.segment_shoot_moments = tuple(accumulate(self.durations, initial=self.shoot_moment))
        self.end_moment = self.segment_shoot_moments[-1]

        # 引导星星在最后一个区停留的时长
        self.last_area_duration = (1 - self.segment_infos[-1].critical_proportion) * self.durations[-1]
        # 正解时刻，即引导星星进入最后一个区的时刻
        self.critical_moment = self.end_moment - self.last_area_duration
        # critical判定时长，需要考虑区间扩展机制
        self.critical_delta = min(SLIDE_AVAILABLE, (SLIDE_CRITICAL + self.last_area_duration / 4))

        judge_sequence = list(self.segment_infos[0].judge_sequence)
        partition = [False] * len(judge_sequence)
        segment_idx_bias = [0]
        for info in self.segment_infos[1:]:
            assert info.judge_sequence[0] == judge_sequence[-1]
            segment_idx_bias.append(len(judge_sequence) - 1)
            judge_sequence.extend(info.judge_sequence[1:])
            partition[-1] = True
            partition.extend([False] * (len(info.judge_sequence) - 1))
        partition.append(False)
        self.judge_sequence = tuple(judge_sequence)     # 整个slidechain的判定队列，每一项都是若干个 Pad 的集合
        self.partition = tuple(partition)     # 如果某一个判定段介于两段slide之间（例如1-3-5的A3）那么这一项就是True，否则False
        self.segment_idx_bias = tuple(segment_idx_bias)    # 每一段slide的第一个判定段的index
        self.total_area_num = len(self.judge_sequence)     # 判定队列总长

        # variable fields
        self.before_slide = False   # 在一笔画中且后面还有别的slide，生成action有用
        self.after_slide = False    # 在一笔画中且前面还有别的slide，生成action有用
        self.cur_area_idx = 0       # 现在判定到判定队列里哪一个判定段
        self.cur_segment_idx = 0    # 现在判定到哪一段slide
        self.pressing: Pad | None = None        # 现在正在按下的判定区，如果现在没有按下就是None
        # 下面这个列表用来存放每一个判定段分别是被什么action判定掉的，以及相应的判定时刻
        self.area_judge_actions: "list[tuple[Action, float] | None]" = [None] * self.total_area_num

    def get_segment_idx(self, now: float) -> int:
        """where is the guiding star now? return segment index
        (Assuming shoot_moment <= now <= end_moment)"""
        idx = 0
        for idx, t in enumerate(self.segment_shoot_moments):
            if t > now:
                break
        return idx - 1

    def set_before_slide(self, before_slide: bool):
        self.before_slide = before_slide

    def set_after_slide(self, after_slide: bool):
        self.after_slide = after_slide

    def on_pad_down(self, now: float, pad: "Pad", action: "Action | None") -> bool:
        return False  # slide do not check pad down event

    def finish(self, now: float) -> bool:
        return now > self.end_moment + SLIDE_AVAILABLE or self.judge == JudgeResult.Bad

    def update(self, now: float, pad_states: "dict[Pad, Action | None]", pad_up_this_tick: "dict[Pad, Action | None]"):
        if self.judge != JudgeResult.Not_Yet:
            return
        if now < self.available_moment:
            # 还没开始判定
            return

        while self.cur_area_idx < self.total_area_num:
            # 下面这个函数会进行一轮判定区检查，如果有变化的话返回值就是True
            if not self._progress_slide_once(now, pad_states, pad_up_this_tick):
                break

        if self.cur_area_idx >= self.total_area_num:
            # slide划完了，进行判定
            self.judge_moment = now
            delta = now - self.critical_moment
            # SLIDE_DELTA_SHIFT的具体含义看开发笔记里的maimai判定全解
            if (abs(delta) <= self.critical_delta) or (abs(delta + SLIDE_DELTA_SHIFT) <= SLIDE_CRITICAL):
                self.judge = JudgeResult.Critical
            else:
                self.judge = JudgeResult.Bad
            return

        if now > self.end_moment + SLIDE_AVAILABLE:
            # Too late
            self.judge = JudgeResult.Bad
            self.judge_moment = now

    def _can_skip_area(self):
        if self.cur_area_idx >= self.total_area_num - 1:
            # last area. this is to avoid some IndexError
            return False

        if self.pressing is not None:
            # when current area is pressed, skipping is always available
            return True

        if len(self.segment_infos) == 1:
            info = self.segment_infos[0]
            if info.is_special_L:
                return self.cur_area_idx != 1 and self.cur_area_idx != 3
            elif info.is_L:
                return self.cur_area_idx != 1

        # any non V-shape (including slide chain)
        if self.total_area_num >= 4:
            return True

        # length 2 slide: first area unskippable
        # length 3 slide: second area unskippable
        return self.cur_area_idx != (self.total_area_num - 2)

        # In fact, a slide chain starting with V-shape is wrongly treated as a single V-shape slide in maimai program
        # Example: 1V73q4 is wrongly treated as 1V74, so A8/B8 (2nd area) is unskippable
        #          1V73qq5 is wrongly treated as 1V75, so A8/B8 (2nd area) and B7 (4th area) is unskipable
        # But I think this is a bug, so I make all slide chain free-to-skip

        # P.S. 1-3-5 is not identical to 1V35, since 1-3-5 is not a V-shape slide, and its length is more than 3
        #      so A2/B2, A4/B4 are both skippable

    def _progress_slide_once(self, now: float, pad_states: "dict[Pad, Action | None]",
                             pad_up_this_tick: "dict[Pad, Action | None]") -> bool:
        # 进行一轮判定区检查
        # pad_states 记录的是一个pad有没有被按下，如果有value就是导致按下的action，否则value就是None
        # pad_up_this_tick 记录的是一个pad是不是这个tick内刚刚被松开，value的含义同上

        if self.pressing is None:
            # check pad down
            for pad in self.judge_sequence[self.cur_area_idx]:
                if pad_states[pad] is not None:
                    self.pressing = pad
                    self.area_judge_actions[self.cur_area_idx] = (pad_states[pad], now)
                    if self.cur_area_idx >= self.total_area_num - 1:
                        # last area
                        self.cur_area_idx += 1
                        self.judge_action = pad_states[pad]
                    if self.partition[self.cur_area_idx]:
                        # last area of a segment
                        self.cur_segment_idx += 1
                    return True

        else:
            # check pad up
            if pad_states[self.pressing] is None:
                self.pressing = None
                self.cur_area_idx += 1
                return True

        if self._can_skip_area():
            # try to skip current area
            for pad in self.judge_sequence[self.cur_area_idx + 1]:
                # if a pad has just been release in this tick, treat it as still being pressed
                if pad_states[pad] is not None or pad_up_this_tick[pad] is not None:
                    self.pressing = pad
                    self.cur_area_idx += 1
                    self.area_judge_actions[self.cur_area_idx] = ((pad_states[pad] or pad_up_this_tick[pad]), now)
                    if self.cur_area_idx >= self.total_area_num - 1:
                        # last area
                        self.cur_area_idx += 1
                        self.judge_action = pad_states[pad]
                    if self.partition[self.cur_area_idx]:
                        # last area of a segment
                        self.cur_segment_idx += 1
                    return True

        return False


class SimaiWifi(SimaiNote):
    def __init__(self, cursor: tuple[int, int, str], moment: float, shape: str, wait: float, duration: float):
        """
        A Wifi Slide.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when slide-track is activated and begins waiting (in ticks)
        @param shape: slide shape such as 1w5
        @param wait: the waiting time before slide-star shoots (in ticks)
        @param duration: the duration of the wifi slide (in ticks)
        """
        super().__init__(cursor, moment)
        self.shape = shape
        self.info = WifiInfo.get(shape)
        self.start = self.info.start
        self.end = self.info.end    # 这个终点是simai语里的终点，例如1w5的5

        # 下面这些属性同slidechain，但是wifi只有一段所以不需要列表了
        self.available_moment = moment - SLIDE_LEADING
        self.wait_duration = wait
        self.shoot_moment = moment + wait
        self.duration = duration
        self.end_moment = moment + wait + duration
        self.last_area_duration = (1 - self.info.critical_proportion) * self.duration
        self.critical_moment = self.end_moment - self.last_area_duration
        self.critical_delta = min(SLIDE_AVAILABLE, (SLIDE_CRITICAL + self.last_area_duration / 4))

        self.total_area_num = len(self.info.tri_judge_sequence[1])      # all 3 lanes is length 4

        # variable fields
        self.after_slide = False            # 同slidechain，wifi后面不会接一笔画所以不需要before_slide
        self.cur_area_idxes = [0, 0, 0]     # 每一轨分别判到第几段
        self.pressing: list[Pad | None] = [None, None, None]    # 每一轨分别正在按下什么pad
        self.lane_finished = [False, False, False]      # 每一轨是否已完成
        # 同slidechain，记录了每一个判定段分别是被什么action判定掉的，以及相应的判定时刻
        self.area_judge_actions: "list[list[tuple[Action, float] | None]]" = [[None] * self.total_area_num for _ in range(3)]
        self.pad_c_passed = not FLAG_WIFI_NEED_C    # 是否已经检测到C区抬手判（模拟旧框wifi用）

    def set_after_slide(self, after_slide: bool):
        self.after_slide = after_slide

    def on_pad_down(self, now: float, pad: "Pad", action: "Action | None") -> bool:
        return False

    def finish(self, now: float) -> bool:
        return now > self.end_moment + SLIDE_AVAILABLE or self.judge == JudgeResult.Bad

    def update(self, now: float, pad_states: "dict[Pad, Action | None]", pad_up_this_tick: "dict[Pad, Action | None]"):
        if self.judge != JudgeResult.Not_Yet:
            return
        if now < self.available_moment:
            return

        for lane in range(3):
            while self.cur_area_idxes[lane] < self.total_area_num:
                if not self._progress_lane_once(now, lane, pad_states, pad_up_this_tick):
                    break
        # 模拟旧框的C区抬手判
        if not self.pad_c_passed and self.cur_area_idxes[1] > 0 and pad_up_this_tick[Pad.C] is not None:
            self.pad_c_passed = True
            self.area_judge_actions[1][2] = (pad_up_this_tick[Pad.C], now)

        if all(self.lane_finished) and self.pad_c_passed:
            self.judge_moment = now
            delta = now - self.critical_moment
            self.judge = JudgeResult.Critical if (abs(delta) <= self.critical_delta) else JudgeResult.Bad
            return

        if now > self.end_moment + SLIDE_AVAILABLE:
            # Too late
            self.judge = JudgeResult.Bad
            self.judge_moment = now

    def _progress_lane_once(self, now: float, lane: int, pad_states: "dict[Pad, Action | None]",
                            pad_up_this_tick: "dict[Pad, Action | None]") -> bool:
        # 对某一轨进行一次判定区检查，基本上和slidechain的逻辑是一样的
        if self.pressing[lane] is None:
            for pad in self.info.tri_judge_sequence[lane][self.cur_area_idxes[lane]]:
                if pad_states[pad] is not None:
                    self.pressing[lane] = pad
                    self.area_judge_actions[lane][self.cur_area_idxes[lane]] = (pad_states[pad], now)
                    if self.cur_area_idxes[lane] >= self.total_area_num - 1:
                        self.cur_area_idxes[lane] += 1
                        self.lane_finished[lane] = True
                        self.judge_action = pad_states[pad]     # 最后完成的lane会覆写掉这个field
                    return True

        else:
            if pad_states[self.pressing[lane]] is None:
                self.pressing[lane] = None
                self.cur_area_idxes[lane] += 1
                return True

        if self.cur_area_idxes[lane] < self.total_area_num - 1:
            for pad in self.info.tri_judge_sequence[lane][self.cur_area_idxes[lane] + 1]:
                if pad_states[pad] is not None or pad_up_this_tick[pad] is not None:
                    self.pressing[lane] = pad
                    self.cur_area_idxes[lane] += 1
                    self.area_judge_actions[lane][self.cur_area_idxes[lane]] = (
                        (pad_states[pad] or pad_up_this_tick[pad]), now
                    )
                    if self.cur_area_idxes[lane] >= self.total_area_num - 1:
                        self.cur_area_idxes[lane] += 1
                        self.lane_finished[lane] = True
                        self.judge_action = pad_states[pad]
                    return True

        return False



if __name__ == "__main__":
    print(type(SimaiWifi))
    # l = list(Pad)
    # from random import sample
    s = ["E2", "E3", "B2"]
    touches = [SimaiTouch((0, 0, ""), 0, p) for p in s]
    touches.sort(key=lambda x: x.pad.value)
    # print(*touches, sep="/")
    group = SimaiTouchGroup((0, 0, ""), 0, touches)
    print(group.radius, group.center)

