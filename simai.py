from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from itertools import accumulate

from core import Pad, JudgeResult, \
                 TAP_CRITICAL, TAP_AVAILABLE, TOUCH_CRITICAL, TOUCH_AVAILABLE, \
                 SLIDE_CRITICAL, SLIDE_AVAILABLE, SLIDE_LEADING
from slides import SlideInfo, WifiInfo
from util import get_covering_circle

if TYPE_CHECKING:
    from action import Action

class SimaiNote(metaclass=ABCMeta):
    def __init__(self, cursor: tuple[int, int, str], moment: float):
        """
        Base class of all simai notes.

        @param cursor: line & column No in original file
        @param moment: the music timestamp when note is activated, in ticks
        """
        self.cursor: tuple[int, int, str] = cursor
        self.moment: float = moment
        self.judge: JudgeResult = JudgeResult.Not_Yet
        self.judge_moment: float = -1
        self.judge_action: "Action | None" = None

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
        if now - self.moment > self._get_critical_delta():
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
        self.idx = idx
        self.is_slide_head = False

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
        self.on_slide = False
        self.group_parent: "SimaiTouchGroup | None" = None

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

        points = [t.pad.vec for t in self.children]
        center, radius = get_covering_circle(points)
        self.center = center
        self.radius = radius

        self.on_slide = False
        self.threshold = len(self.children) * 0.51

        self.effect_generated = [False] * len(self.children)

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
        self.shapes = tuple(shapes)
        self.segment_infos = tuple(SlideInfo.get(k) for k in shapes)
        self.start = self.segment_infos[0].start
        self.end = self.segment_infos[-1].end

        self.available_moment = moment - SLIDE_LEADING     # slide is available 100ms before star is hit
        self.wait_duration = wait
        self.shoot_moment = moment + wait

        if durations is not None:
            self.durations = tuple(durations)
        else:
            lengths = [info.path.length() for info in self.segment_infos]
            total_length = sum(lengths)
            self.durations = tuple(x * total_duration / total_length for x in lengths)
        assert len(self.segment_infos) == len(self.durations)
        self.segment_shoot_moments = tuple(accumulate(self.durations, initial=self.shoot_moment))
        self.end_moment = self.segment_shoot_moments[-1]

        self.last_area_duration = (1 - self.segment_infos[-1].pad_enter_time[-1].t) * self.durations[-1]
        self.critical_moment = self.end_moment - self.last_area_duration
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
        self.judge_sequence = tuple(judge_sequence)
        self.partition = tuple(partition)     # denoting whether a judge area is between 2 segments
        self.segment_idx_bias = tuple(segment_idx_bias)     # the idx of 1st area of each segment in the full sequence
        self.total_area_num = len(self.judge_sequence)

        # variable fields
        self.before_slide = False
        self.after_slide = False  # indicating standard single-stroke slide
        self.cur_area_idx = 0
        self.cur_segment_idx = 0
        self.pressing: Pad | None = None
        self.area_judge_actions: "list[tuple[Action, float] | None]" = [None] * self.total_area_num

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
            return

        while self.cur_area_idx < self.total_area_num:
            if not self._progress_slide_once(now, pad_states, pad_up_this_tick):
                break

        if self.cur_area_idx >= self.total_area_num:
            self.judge_moment = now
            delta = now - self.critical_moment
            self.judge = JudgeResult.Critical if (abs(delta) <= self.critical_delta) else JudgeResult.Bad
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
        if self.pressing is None:
            # pad down
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
            # pad up
            if pad_states[self.pressing] is None:
                self.pressing = None
                self.cur_area_idx += 1
                return True

        if self._can_skip_area():
            # try to skip current area
            for pad in self.judge_sequence[self.cur_area_idx + 1]:
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
        self.end = self.info.end

        self.available_moment = moment - SLIDE_LEADING
        self.wait_duration = wait
        self.shoot_moment = moment + wait
        self.duration = duration
        self.end_moment = moment + wait + duration
        self.last_area_duration = (1 - self.info.pad_enter_time[-1].t) * self.duration
        self.critical_moment = self.end_moment - self.last_area_duration
        self.critical_delta = min(SLIDE_AVAILABLE, (SLIDE_CRITICAL + self.last_area_duration / 4))

        self.total_area_num = len(self.info.tri_judge_sequence[1])      # all 3 lanes is length 4

        # variable fields
        self.after_slide = False
        self.cur_area_idxes = [0, 0, 0]
        self.pressing: list[Pad | None] = [None, None, None]
        self.lane_finished = [False, False, False]
        self.area_judge_actions: "list[list[tuple[Action, float] | None]]" = [[None] * self.total_area_num for _ in range(3)]

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

        if all(self.lane_finished):
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
    # s = [Pad.C, Pad.B6, Pad.B7, Pad.D7, Pad.E7]
    # touches = [SimaiTouch((0, 0), 0, p.name) for p in s]
    # touches.sort(key=lambda x: x.pad.value)
    # print(*touches, sep="/")
    # group: SimaiTouchGroup = SimaiParser._workup_each(touches)[0]
    # print(group.radius, group.center)

