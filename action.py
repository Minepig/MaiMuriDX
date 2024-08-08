from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from core import RELEASE_DELAY, HAND_RADIUS_MAX

if TYPE_CHECKING:
    from core import Pad
    from simai import SimaiNote
    from slides import SlidePath


class Action(metaclass=ABCMeta):
    def __init__(self, source: "SimaiNote", moment: float, two_hands: bool):
        """
        Base class of all hand actions.

        @param source: the original note producing this action
        @param moment: the music timestamp when action is performed, in ticks
        """
        self.source = source
        self.moment = moment
        self.require_two_hands = two_hands

    @abstractmethod
    def update(self, now: float) -> None | tuple[complex, float]:
        """
        Update action routine.

        @param now: current music timestamp in ticks
        @return: None if no action is performed, or the touch circle in (center, radius)
        """
        raise NotImplementedError

    @abstractmethod
    def finish(self, now: float) -> bool:
        """
        whether the action is finished

        @param now: current music timestamp in ticks
        """
        raise NotImplementedError

    def can_merge(self) -> bool:
        return False


class ActionPress(Action):
    def __init__(
            self, source: "SimaiNote", moment: float, duration: float,
            position: complex, radius: float, tailless: bool = False
    ):
        """
        Press actions, press a position for some time interval.

        @param source: the original note producing this action
        @param moment: the music timestamp when action is performed (press down), in ticks
        @param duration: the duration of the press action in ticks
        @param position: where to press, vector expressed in complex, 0 is at the center of the screen
        @param radius: the radius of the hand in pixels
        @param tailless: no delay release
        """
        super().__init__(source, moment, radius > HAND_RADIUS_MAX)
        self.position = position
        self.duration = duration
        self.radius = radius
        self.end_moment = moment + duration
        if not tailless:
            self.end_moment += RELEASE_DELAY

    def update(self, now: float) -> None | tuple[complex, float]:
        if self.moment <= now < self.end_moment:
            pass
            return self.position, self.radius
        return None

    def finish(self, now: float) -> bool:
        return now >= self.end_moment


class ActionSlide(Action):
    def __init__(
            self, source: "SimaiNote", moment: float, duration: float,
            path: "SlidePath", radius: float, tailless: bool = False, is_wifi = False
    ):
        """
        Slide actions, press a position and move along a path in some time interval.

        @param source: the original note producing this action
        @param moment: the music timestamp when action is performed (press down), in ticks
        @param duration: the duration of the slide action in ticks
        @param path: slide path
        @param radius: the radius of the hand in pixels
        @param tailless: no delay release
        """
        super().__init__(source, moment, False)
        self.duration = duration
        self.radius = radius
        self.path = path
        self.end_moment = moment + duration
        if not tailless:
            self.end_moment += RELEASE_DELAY
        self.is_wifi = is_wifi

    def update(self, now: float) -> None | tuple[complex, float]:
        if self.moment <= now < self.end_moment:
            t = (now - self.moment) / self.duration
            if t >= 1:
                return self.path.point(1), self.radius
            return self.path.point(t), self.radius
        return None

    def finish(self, now: float) -> bool:
        return now >= self.end_moment

    def can_merge(self) -> bool:
        return not self.is_wifi


class ActionExtraPadDown(Action):
    def __init__(self, source: "SimaiNote", moment: float, pad: "Pad", delay: float):
        """
        Dummy action for tap-slide. Won't perform anything by itself.
        When using outer buttons to play tap-slide, pad A is touched about 50 ms later.
        This action is to record that extra touch, but it won't perform that touch by itself.
        Instead, judging manager will check if an action is an instance of this class and create extra pad down event.

        模拟外屏拍星星进入A区时的额外判定

        @param source: the original note producing this action
        @param moment: the music timestamp when action is performed (press down), in ticks
        @param pad: the pad which should be pressed
        """
        super().__init__(source, moment + delay, False)
        self.pad = pad

    def update(self, now: float) -> None | tuple[complex, float]:
        return None

    def finish(self, now: float) -> bool:
        return now > self.moment
