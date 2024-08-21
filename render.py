from abc import abstractmethod, ABCMeta
from math import degrees, pi, tanh
from cmath import phase

from core import CANVAS_SIZE, NOTE_SPEED, TOUCH_DURATION, DISTANCE_TAP, CANVAS_CENTER, DISTANCE_EDGE
from core import JudgeResult, Pad, JUDGE_TPS, DISTANCE_JUDGE_EFF
from simai import SimaiNote, SimaiTap, SimaiHold, SimaiTouch
from simai import SimaiTouchHold, SimaiTouchGroup, SimaiWifi, SimaiSlideChain
from slides import SlideInfo, WifiInfo, SlideType

import pygame as pg



class NoteRenderer:
    def __init__(self):
        self.tap_image: pg.Surface | None = None
        self.each_image: pg.Surface | None = None
        self.break_image: pg.Surface | None = None
        self.star_image: pg.Surface | None = None
        self.hold_image: pg.Surface | None = None
        self.arrow_image: pg.Surface | None = None
        self.wifi_images: list[pg.Surface] | None = None
        self.double_star_each_image: pg.Surface | None = None
        self.slide_track_surfaces: dict[str, list[tuple[pg.Surface, pg.Rect]]] | None = None

    def load_images(self, tap, each, double_star_each, break_, star, hold, arrow, wifi_images):
        self.tap_image = tap
        self.each_image = each
        self.double_star_each_image = double_star_each
        self.break_image = break_
        self.star_image = star
        self.hold_image = hold
        self.arrow_image = arrow
        assert len(wifi_images) == 11
        self.wifi_images = wifi_images
        self.slide_track_surfaces = {}
        for info in SlideInfo.get_all():
            if info.key in self.slide_track_surfaces:
                continue
            surf_and_rects = []
            for i in range(len(info.arrow_segments) - 1):
                surfs = []
                rects = []
                for n in reversed(range(info.arrow_segments[i], info.arrow_segments[i + 1])):
                    pos, angle = info.arrow_points[n]
                    pos += CANVAS_CENTER
                    pic = pg.transform.rotate(self.arrow_image, -angle)
                    r = pic.get_rect()
                    r.center = pos.real, pos.imag
                    surfs.append(pic)
                    rects.append(r)
                rect = rects[0].unionall(rects[1:])
                surf = pg.Surface(rect.size).convert_alpha()
                surf.fill([0, 0, 0, 0])
                for s, r in zip(surfs, rects):
                    surf.blit(s, [r.left - rect.left, r.top - rect.top])
                surf_and_rects.append((surf, rect))
            self.slide_track_surfaces[info.key] = surf_and_rects

        for info in WifiInfo.get_all():
            if info.key in self.slide_track_surfaces:
                continue
            surf_and_rects = []
            for i in range(len(info.arrow_segments) - 1):
                surfs = []
                rects = []
                for n in range(info.arrow_segments[i], info.arrow_segments[i + 1]):
                    pos, angle = info.arrow_points[n]
                    pos += CANVAS_CENTER
                    pic = pg.transform.rotate(self.wifi_images[n], angle)
                    r = pic.get_rect()
                    r.center = pos.real, pos.imag
                    surfs.append(pic)
                    rects.append(r)
                rect = rects[0].unionall(rects[1:])
                surf = pg.Surface(rect.size).convert_alpha()
                surf.fill([0, 0, 0, 0])
                for s, r in zip(surfs, rects):
                    surf.blit(s, [r.left - rect.left, r.top - rect.top])
                surf_and_rects.append((surf, rect))
            self.slide_track_surfaces[info.key] = surf_and_rects


    @staticmethod
    def distance2scale(distance: float) -> float:
        return distance * 0.008 + 0.51


    def _render_tap(self, note: "SimaiTap", surface: pg.Surface, now: float) -> None:
        distance = (now - note.moment) * NOTE_SPEED + DISTANCE_EDGE
        image = self.break_image if note.is_slide_head else self.tap_image

        scale = self.distance2scale(distance)
        if scale < 0:
            # not appear yet
            return

        if distance < DISTANCE_TAP:
            pic = pg.transform.rotozoom(image, 22.5 - note.idx * 45, scale)
            pos = note.pad.unitvec * DISTANCE_TAP + CANVAS_CENTER
            rect = pic.get_rect()
            rect.center = pos.real, pos.imag
            surface.blit(pic, rect)
            return

        pos = note.pad.unitvec * distance + CANVAS_CENTER
        pic = pg.transform.rotate(image, 22.5 - note.idx * 45)
        rect = pic.get_rect()
        rect.center = pos.real, pos.imag
        surface.blit(pic, rect)

    def _render_hold(self, note: "SimaiHold", surface: pg.Surface, now: float) -> None:
        delta = now - note.moment
        delta_end = now - note.end_moment
        distance = delta * NOTE_SPEED + DISTANCE_EDGE
        distance_end = delta_end * NOTE_SPEED + DISTANCE_EDGE

        scale = self.distance2scale(distance)
        if scale < 0:
            # not appear yet
            return

        if distance < DISTANCE_TAP:
            # note head zoom in
            pic = pg.transform.rotozoom(self.hold_image, 22.5 - note.idx * 45, scale)
            pos = note.pad.unitvec * DISTANCE_TAP + CANVAS_CENTER
            rect = pic.get_rect()
            rect.center = pos.real, pos.imag
            surface.blit(pic, rect)
            return

        if note.judge != JudgeResult.Not_Yet:
            # snap note head to judging line
            distance = DISTANCE_EDGE

        # note head position
        pos = note.pad.unitvec * distance + CANVAS_CENTER
        pic = pg.transform.rotate(self.hold_image, 22.5 - note.idx * 45)
        rect = pic.get_rect()
        rect.center = pos.real, pos.imag

        # note tail position
        if distance_end < DISTANCE_TAP:
            # tail not appear yet
            distance_end = DISTANCE_TAP

        # draw hold line
        line_len = round(distance - distance_end)
        line_surf = pg.Surface([60, 60 + line_len]).convert_alpha()
        line_surf.fill([0, 0, 0, 0])
        pg.draw.circle(line_surf, [255, 255, 255], [30, 30], 5)
        pg.draw.rect(line_surf, [255, 255, 255], [25, 30, 10, line_len])
        pg.draw.rect(line_surf, [255, 255, 255], [19, line_len + 25, 22, 10])
        pg.draw.circle(line_surf, [255, 20, 120], [30, 30], 4)
        pg.draw.rect(line_surf, [255, 20, 120], [26, 30, 8, line_len])
        pg.draw.rect(line_surf, [255, 20, 120], [20, line_len + 26, 20, 8])
        line_surf_rotated = pg.transform.rotate(line_surf, 22.5 - note.idx * 45)
        line_rect = line_surf_rotated.get_rect()
        line_pos = note.pad.unitvec * (distance + distance_end) / 2 + CANVAS_CENTER
        line_rect.center = line_pos.real, line_pos.imag

        surface.blit(line_surf_rotated, line_rect)
        surface.blit(pic, rect)

        if note.judge != JudgeResult.Not_Yet:
            self._render_hold_press_effect(surface, note.judge, delta / note.duration, pos)

    def _render_hold_press_effect(self, surface: pg.Surface, judge: JudgeResult, t: float, pos: complex) -> None:
        # render holding effect
        if judge == JudgeResult.Critical:
            color = [255, 255, 0, 255]
        else:
            color = [0, 255, 0, 255]
        circle_rect = pg.Rect(0, 0, 100, 100)
        circle_rect.center = pos.real, pos.imag
        if t > 0:
            pg.draw.arc(surface, color, circle_rect, 2 * pi * (1 - t), 2 * pi, 4)

    def _render_touch(self, note: "SimaiTouch", surface: pg.Surface, now: float) -> None:
        delta = now - note.moment

        a = round(1275 * (delta + TOUCH_DURATION) / TOUCH_DURATION)
        if a <= 0:
            # not appear yet
            return
        if a > 255:
            a = 255
        color = [255, 255, 255, a]
        r = 27 if delta >= 0 else (56 * tanh(-1.5 * delta / TOUCH_DURATION) + 27)

        if note.on_slide:
            image = self.double_star_each_image
        else:
            image = self.each_image

        if a < 255:
            image = image.copy()
            image.set_alpha(a)
        rect = image.get_rect()

        pos = note.pad.vec + CANVAS_CENTER
        rect.center = pos.real, pos.imag
        surface.blit(image, rect)
        pg.draw.circle(surface, color, [pos.real, pos.imag], r, 5)

    def _render_touch_hold(self, note: "SimaiTouchHold", surface: pg.Surface, now: float) -> None:
        delta = now - note.moment

        a = round(1275 * (delta + TOUCH_DURATION) / TOUCH_DURATION)
        if a <= 0:
            # not appear yet
            return
        if a > 255:
            a = 255
        color = [255, 255, 255, a]
        r = 27 if (delta >= 0 or note.judge != JudgeResult.Not_Yet) else (56 * tanh(-1.5 * delta / TOUCH_DURATION) + 27)

        if a < 255:
            image = self.each_image.copy()
            image.set_alpha(a)
        else:
            image = self.each_image
        rect = image.get_rect()

        pos = note.pad.vec + CANVAS_CENTER
        rect.center = pos.real, pos.imag
        surface.blit(image, rect)
        pg.draw.circle(surface, color, [pos.real, pos.imag], r, 5)

        if note.judge != JudgeResult.Not_Yet:
            self._render_hold_press_effect(surface, note.judge, delta / note.duration, pos)

    def _render_slide_track_since(self, surface: pg.Surface, key: str, idx: int) -> None:
        surf_and_rects = self.slide_track_surfaces[key]
        for i in reversed(range(idx, len(surf_and_rects))):
            s, r = surf_and_rects[i]
            surface.blit(s, r)


    def _render_slide_chain(self, note: "SimaiSlideChain", surface: pg.Surface, now: float) -> None:
        if now < note.available_moment:
            # slide track fade in (200 ms)
            a = round(255 * min(1.0, 1 - (note.available_moment - now) * 5 / JUDGE_TPS))
            if a <= 0:
                return

            su = pg.Surface([CANVAS_SIZE, CANVAS_SIZE]).convert_alpha()
            su.fill([0, 0, 0, 0])
            for seg in reversed(note.segment_infos):
                self._render_slide_track_since(su, seg.key, 0)
            su.set_alpha(a)
            surface.blit(su, [0, 0])
            return

        # render slide track
        if note.cur_area_idx < note.total_area_num:
            for i in reversed(range(note.cur_segment_idx + 1, len(note.segment_infos))):
                key = note.segment_infos[i].key
                self._render_slide_track_since(surface, key, 0)
            key = note.segment_infos[note.cur_segment_idx].key
            self._render_slide_track_since(surface, key, note.cur_area_idx - note.segment_idx_bias[note.cur_segment_idx])

        if now <= note.moment:
            # before waiting time start, slide star does not appear
            return

        # render slide star
        if now < note.shoot_moment:
            # slide star fade in
            a = round(255 * min(1.0, 1 - (note.shoot_moment - now) / note.wait_duration))
            if a <= 0:
                return

            pos = note.segment_infos[0].path.point(0) + CANVAS_CENTER
            tangent = note.segment_infos[0].path.tangent(0)
            image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), a / 255 + 0.5)
            image.set_alpha(a)
            rect = image.get_rect()
            rect.center = pos.real, pos.imag
            surface.blit(image, rect)
            return

        if now >= note.end_moment:
            # slide star arrived
            if note.judge == JudgeResult.Critical:
                # already get a critical perfect judgement, slide disappear
                return

            # slide star wait at the end (maybe useless)
            pos = note.segment_infos[-1].path.point(1) + CANVAS_CENTER
            tangent = note.segment_infos[-1].path.tangent(1)
            image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), 1.5)
            rect = image.get_rect()
            rect.center = pos.real, pos.imag
            surface.blit(image, rect)
            return

        # render slide star at current pos
        idx = note.get_segment_idx(now)
        # idx = note.cur_segment_idx
        proportion = (now - note.segment_shoot_moments[idx]) / note.durations[idx]
        pos = note.segment_infos[idx].path.point(proportion) + CANVAS_CENTER
        tangent = note.segment_infos[idx].path.tangent(proportion)
        image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), 1.5)
        rect = image.get_rect()
        rect.center = pos.real, pos.imag
        surface.blit(image, rect)

    def _render_wifi(self, note: "SimaiWifi", surface: pg.Surface, now: float) -> None:
        if now < note.available_moment:
            # slide track fade in (200 ms)
            a = round(255 * min(1.0, 1 - (note.available_moment - now) * 5 / JUDGE_TPS))
            if a <= 0:
                return

            su = pg.Surface([CANVAS_SIZE, CANVAS_SIZE]).convert_alpha()
            su.fill([0, 0, 0, 0])
            self._render_slide_track_since(su, note.info.key, 0)
            su.set_alpha(a)
            surface.blit(su, [0, 0])
            return

        # render slide track
        idx = min(note.cur_area_idxes)
        if not note.pad_c_passed:
            idx = min(idx, note.total_area_num - 1)
        self._render_slide_track_since(surface, note.info.key, idx)

        if now <= note.moment:
            # before waiting time start, slide star does not appear
            return

        # render slide star
        if now < note.shoot_moment:
            # slide star fade in
            a = round(255 * min(1.0, 1 - (note.shoot_moment - now) / note.wait_duration))
            if a <= 0:
                return

            for lane in range(3):
                pos = note.info.tri_path[lane].point(0) + CANVAS_CENTER
                tangent = note.info.tri_path[lane].tangent(0)
                image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), a / 255 + 0.5)
                image.set_alpha(a)
                rect = image.get_rect()
                rect.center = pos.real, pos.imag
                surface.blit(image, rect)
            return

        if now >= note.end_moment:
            # slide star arrived
            if note.judge == JudgeResult.Critical:
                # already get a critical perfect judgement, slide disappear
                return

            # slide star wait at the end (maybe useless)
            for lane in range(3):
                pos = note.info.tri_path[lane].point(1) + CANVAS_CENTER
                tangent = note.info.tri_path[lane].tangent(1)
                image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), 1.5)
                rect = image.get_rect()
                rect.center = pos.real, pos.imag
                surface.blit(image, rect)
            return

        # render slide star at current pos
        proportion = (now - note.shoot_moment) / note.duration
        for lane in range(3):
            pos = note.info.tri_path[lane].point(proportion) + CANVAS_CENTER
            tangent = note.info.tri_path[lane].tangent(proportion)
            image = pg.transform.rotozoom(self.star_image, 270 - degrees(phase(tangent)), 1.5)
            rect = image.get_rect()
            rect.center = pos.real, pos.imag
            surface.blit(image, rect)

    def _render_touch_group(self, note: "SimaiTouchGroup", surface: pg.Surface, now: float) -> None:
        for touch in note.children:
            if touch.finish(now):
                continue
            self._render_touch(touch, surface, now)

    def render(self, note: "SimaiNote", surface: pg.Surface, surface_slide: pg.Surface, now: float):
        """Render note to surface.

        @param note: note to render
        @param surface: surface to blit the note (excluding slide)
        @param surface_slide: surface to blit the slide
        @param now: current time in ticks
        """
        if isinstance(note, SimaiTap):
            self._render_tap(note, surface, now)
        elif isinstance(note, SimaiHold):
            self._render_hold(note, surface, now)
        elif isinstance(note, SimaiTouch):
            self._render_touch(note, surface, now)
        elif isinstance(note, SimaiTouchGroup):
            self._render_touch_group(note, surface, now)
        elif isinstance(note, SimaiTouchHold):
            self._render_touch_hold(note, surface, now)
        elif isinstance(note, SimaiSlideChain):
            self._render_slide_chain(note, surface_slide, now)
        elif isinstance(note, SimaiWifi):
            self._render_wifi(note, surface_slide, now)

    def generate_judge_effect(self, note, effect_renderer: "EffectRenderer") -> None:
        if isinstance(note, SimaiTap):
            color = [255, 255, 0] if note.judge == JudgeResult.Critical else [0, 255, 0]
            distance = (note.judge_moment - note.moment) * NOTE_SPEED + DISTANCE_EDGE
            pos = note.pad.unitvec * distance + CANVAS_CENTER
            effect_renderer.add_effect(HitEffect(color, pos, note.judge_moment))
            if note.judge == JudgeResult.Bad:
                effect_renderer.add_effect(SimpleJudgeEffect(note.judge_moment, note.pad))
        elif isinstance(note, SimaiHold):
            color = [255, 255, 0] if note.judge == JudgeResult.Critical else [0, 255, 0]
            pos = note.pad.unitvec * DISTANCE_EDGE + CANVAS_CENTER
            effect_renderer.add_effect(HitEffect(color, pos, note.end_moment))
            if note.judge == JudgeResult.Bad:
                effect_renderer.add_effect(SimpleJudgeEffect(note.judge_moment, note.pad))
        elif isinstance(note, SimaiTouch):
            color = [255, 255, 0] if note.judge == JudgeResult.Critical else [0, 255, 0]
            effect_renderer.add_effect(HitEffect(color, note.pad.vec + CANVAS_CENTER, note.judge_moment))
            if note.judge == JudgeResult.Bad:
                effect_renderer.add_effect(SimpleJudgeEffect(note.judge_moment, note.pad))
        elif isinstance(note, SimaiTouchGroup):
            for i, touch in enumerate(note.children):
                if note.effect_generated[i]:
                    continue
                if touch.judge == JudgeResult.Not_Yet:
                    continue
                color = [255, 255, 0] if touch.judge == JudgeResult.Critical else [0, 255, 0]
                effect_renderer.add_effect(HitEffect(color, touch.pad.vec + CANVAS_CENTER, touch.judge_moment))
                if touch.judge == JudgeResult.Bad:
                    effect_renderer.add_effect(SimpleJudgeEffect(note.judge_moment, touch.pad))
                note.effect_generated[i] = True
        elif isinstance(note, SimaiTouchHold):
            color = [255, 255, 0] if note.judge == JudgeResult.Critical else [0, 255, 0]
            effect_renderer.add_effect(HitEffect(color, note.pad.vec + CANVAS_CENTER, note.end_moment))
            if note.judge == JudgeResult.Bad:
                effect_renderer.add_effect(SimpleJudgeEffect(note.judge_moment, note.pad))
        elif isinstance(note, SimaiSlideChain):
            if note.judge == JudgeResult.Critical:
                return
            info = note.segment_infos[-1]
            if info.type_ == SlideType.Circle_CW:
                eff = SlideCircleEffect(note.judge_moment, info.end, False)
            elif info.type_ == SlideType.Circle_CCW:
                eff = SlideCircleEffect(note.judge_moment, info.end, True)
            else:
                eff = SlideStraightEffect(note.judge_moment, info.end, info.path.tangent(1))
            effect_renderer.add_effect(eff)
        elif isinstance(note, SimaiWifi):
            if note.judge == JudgeResult.Critical:
                return
            effect_renderer.add_effect(SlideWifiEffect(note.judge_moment, note.end))



class BaseEffect(metaclass=ABCMeta):
    def __init__(self, moment: float):
        self.alive = True
        self.moment = moment

    @abstractmethod
    def update_and_draw(self, surface: pg.Surface, now: float):
        raise NotImplementedError


class HitEffect(BaseEffect):
    def __init__(self, color, pos: complex, moment: float):
        super().__init__(moment)
        self.color = pg.Color(color)
        self.pos = pos.real, pos.imag

    def update_and_draw(self, surface: pg.Surface, now: float):
        delta = now - self.moment
        if delta > (JUDGE_TPS / 3):
            self.alive = False
            return

        r = delta * 180 / JUDGE_TPS
        self.color.a = 255 if delta < (JUDGE_TPS / 6) else round(255 * (2 - delta * 6 / JUDGE_TPS))

        pg.draw.circle(surface, self.color, self.pos, r, 5)


class SimpleJudgeEffect(BaseEffect):
    good_image: pg.Surface = None
    good_images_by_pad = {}

    @classmethod
    def load_images(cls, image: pg.Surface):
        cls.good_image = image
        cls.good_images_by_pad = {}
        for i in range(8):
            pic = pg.transform.rotate(image, 22.5 - 45 * i)
            cls.good_images_by_pad[Pad(i)] = pic
            cls.good_images_by_pad[Pad(i | 8)] = pic
            pic = pg.transform.rotate(image, 45 - 45 * i)
            cls.good_images_by_pad[Pad(i | 16)] = pic
            cls.good_images_by_pad[Pad(i | 24)] = pic
        cls.good_images_by_pad[Pad.C] = image

    def __init__(self, moment: float, pad: Pad):
        super().__init__(moment)
        self.pad = pad
        self.image = self.good_images_by_pad[pad].copy()
        pos = pad.vec - pad.unitvec * DISTANCE_JUDGE_EFF + CANVAS_CENTER
        self.rect = self.image.get_rect()
        self.rect.center = pos.real, pos.imag

    def update_and_draw(self, surface: pg.Surface, now: float):
        delta = now - self.moment
        if delta > (JUDGE_TPS / 2):
            self.alive = False
            return

        if delta < (JUDGE_TPS / 8):
            a = 255 * (delta * 8 / JUDGE_TPS)
        elif delta > (JUDGE_TPS / 4):
            a = 255 * (2 - delta * 4 / JUDGE_TPS)
        else:
            a = 255
        self.image.set_alpha(a)
        surface.blit(self.image, self.rect)


class SlideJudgeEffect(BaseEffect):
    left_image: pg.Surface = None
    right_image: pg.Surface = None
    ccw_image: pg.Surface = None
    cw_image: pg.Surface = None
    wifi_up_image: pg.Surface = None
    wifi_down_image: pg.Surface = None

    @classmethod
    def load_images(cls, left, right, ccw, cw, wifi_up, wifi_down):
        cls.left_image = left
        cls.right_image = right
        cls.ccw_image = ccw
        cls.cw_image = cw
        cls.wifi_up_image = wifi_up
        cls.wifi_down_image = wifi_down

    def __init__(self, moment: float, image: pg.Surface, rect: pg.Rect):
        super().__init__(moment)
        self.image = image
        self.rect = rect

    def update_and_draw(self, surface: pg.Surface, now: float):
        delta = now - self.moment
        if delta > (JUDGE_TPS / 2):
            self.alive = False
            return

        a = 255 if delta < (JUDGE_TPS / 4) else round(255 * (2 - delta * 4 / JUDGE_TPS))
        self.image.set_alpha(a)
        surface.blit(self.image, self.rect)


class SlideStraightEffect(SlideJudgeEffect):
    distance = CANVAS_SIZE * 220 / 1080

    def __init__(self, moment: float, idx: int, tangent: complex):
        angle = degrees(phase(tangent))
        if -90 <= angle < 90:
            image = pg.transform.rotate(self.right_image, -angle)
        else:
            image = pg.transform.rotate(self.left_image, 180 - angle)

        c = CANVAS_CENTER + Pad(idx & 7).unitvec * DISTANCE_EDGE - tangent / abs(tangent) * self.distance
        rect = image.get_rect()
        rect.center = c.real, c.imag
        super().__init__(moment, image, rect)

class SlideCircleEffect(SlideJudgeEffect):
    distance = CANVAS_SIZE * 463 / 1080

    def __init__(self, moment: float, idx: int, is_ccw: bool):
        if is_ccw:
            image = pg.transform.rotate(self.ccw_image, 45 * (8 - idx))
            c = CANVAS_CENTER + Pad((1 + idx & 7) | 24).unitvec * self.distance
        else:
            image = pg.transform.rotate(self.cw_image, -45 * (idx - 1))
            c = CANVAS_CENTER + Pad((idx & 7) | 24).unitvec * self.distance

        rect = image.get_rect()
        rect.center = c.real, c.imag
        super().__init__(moment, image, rect)

class SlideWifiEffect(SlideJudgeEffect):
    distance = CANVAS_SIZE * 406 / 1080

    def __init__(self, moment: float, idx: int):
        if idx in {1, 2, 7, 8}:
            image = pg.transform.rotate(self.wifi_up_image, 22.5 - 45 * idx)
        else:
            image = pg.transform.rotate(self.wifi_down_image, 202.5 - 45 * idx)

        c = complex(270, 270) + Pad(idx & 7).unitvec * self.distance
        rect = image.get_rect()
        rect.center = c.real, c.imag
        super().__init__(moment, image, rect)


class PressEffect(BaseEffect):
    def __init__(self, moment: float, pos: complex, radius: float, is_slide: bool, on_multitouch: bool):
        super().__init__(moment)
        self.pos = pos
        self.radius = radius
        self.is_slide = is_slide
        self.on_multitouch = on_multitouch

    def update_and_draw(self, surface: pg.Surface, now: float):
        delta = now - self.moment
        if delta > (JUDGE_TPS / 5):
            self.alive = False
            return

        t = max(min(delta * 5 / JUDGE_TPS, 1), 0)
        color = [224, 108, 117, 255] if self.on_multitouch else [255, 255, 255, 255]
        color[3] = (1 - t) * 255
        pos = self.pos + CANVAS_CENTER
        r = self.radius * (1 - 0.5 * t) if self.is_slide else self.radius

        pg.draw.circle(surface, color, [pos.real, pos.imag], r, 0)


class EffectRenderer:
    def __init__(self):
        self.effects: set[BaseEffect] = set()

    def add_effect(self, effect: BaseEffect):
        self.effects.add(effect)

    def update_and_render(self, surface: pg.Surface, now: float):
        killed = set()
        for effect in self.effects:
            effect.update_and_draw(surface, now)
            if not effect.alive:
                killed.add(effect)
        self.effects -= killed


