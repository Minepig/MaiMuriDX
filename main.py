import pathlib
import traceback
from collections.abc import Sequence

from action import Action, ActionSlide
from core import CANVAS_CENTER, CANVAS_SIZE, Pad, JUDGE_TPS, RENDER_FPS, REPORT_WRITER
from judge import JudgeManager, StaticMuriChecker
from majparse import NoteActionConverter, SimaiParser
from render import EffectRenderer, NoteRenderer, PressEffect, SlideJudgeEffect, SimpleJudgeEffect
from simai import SimaiNote, SimaiTouchGroup
from slides import init as init_slides
init_slides()

import pygame as pg
pg.init()


class GameRenderer:
    background_path = "images/background/Default_Background.png"

    def __init__(self):
        self.canvas = pg.display.set_mode((CANVAS_SIZE, CANVAS_SIZE))
        self.background = pg.Surface(self.canvas.get_size()).convert()
        self.layer_slide = pg.Surface(self.canvas.get_size()).convert_alpha()
        self.layer_note = pg.Surface(self.canvas.get_size()).convert_alpha()
        self.layer_state = pg.Surface(self.canvas.get_size()).convert_alpha()
        self.layer_action = pg.Surface(self.canvas.get_size()).convert_alpha()
        self.layer_effect = pg.Surface(self.canvas.get_size()).convert_alpha()
        self.canvas_rect = self.canvas.get_rect()

        self.layer_slide.set_alpha(255)
        self.layer_note.set_alpha(255)
        self.layer_state.set_alpha(50)
        self.layer_action.set_alpha(160)
        self.layer_effect.set_alpha(200)

        bg = pg.image.load(self.background_path).convert()
        # if bg.get_size() != (CANVAS_SIZE, CANVAS_SIZE):
        #     bg = pg.transform.smoothscale(bg, (CANVAS_SIZE, CANVAS_SIZE))
        bg.set_alpha(120)
        circle = pg.image.load("images/background/1080Circle_Rev.png").convert_alpha()
        outline = pg.image.load("images/background/outline.png").convert_alpha()
        self.background.blit(bg, (0, 0))
        self.background.blit(outline, (25, 25))
        self.background.blit(circle, (0, 0))

        self.font = pg.font.Font(None, 40)
        self.effect_renderer = EffectRenderer()
        self.action_renderer = EffectRenderer()
        self.note_renderer = NoteRenderer()

        self.note_renderer.load_images(
            pg.image.load("images/notes/tap.png").convert_alpha(),
            pg.image.load("images/notes/each.png").convert_alpha(),
            pg.image.load("images/notes/double_star_each.png").convert_alpha(),
            pg.image.load("images/notes/break.png").convert_alpha(),
            pg.image.load("images/notes/star.png").convert_alpha(),
            pg.image.load("images/notes/hold.png").convert_alpha(),
            pg.image.load("images/notes/slide.png").convert_alpha(),
            [pg.image.load("images/notes/wifi_%d.png" % i).convert_alpha() for i in range(11)]
        )
        SlideJudgeEffect.load_images(
            pg.image.load("images/judge/slide_l.png").convert_alpha(),
            pg.image.load("images/judge/slide_r.png").convert_alpha(),
            pg.image.load("images/judge/slidecircle_l.png").convert_alpha(),
            pg.image.load("images/judge/slidecircle_r.png").convert_alpha(),
            pg.image.load("images/judge/wifi_u.png").convert_alpha(),
            pg.image.load("images/judge/wifi_d.png").convert_alpha(),
        )
        SimpleJudgeEffect.load_images(
            pg.image.load("images/judge/simple.png").convert_alpha(),
        )

    def clear_canvas(self):
        self.layer_slide.fill([0, 0, 0, 0])
        self.layer_note.fill([0, 0, 0, 0])
        self.layer_state.fill([0, 0, 0, 0])
        self.layer_action.fill([0, 0, 0, 0])
        self.layer_effect.fill([0, 0, 0, 0])
        self.canvas.blit(self.background, [0, 0])

    def render_active_notes(self, active_notes: Sequence[SimaiNote], now: float):
        for note in reversed(active_notes):
            self.note_renderer.render(note, self.layer_note, self.layer_slide, now)

    def render_active_actions(self, active_actions: Sequence[Action], now: float):
        # for action in active_actions:
        #     circle = action.update(now)
        #     if circle is not None:
        #         c, r = circle
        #         self.action_renderer.add_effect(PressEffect(now, c, r))
        self.action_renderer.update_and_render(self.layer_action, now)

    def render_pad_state(self, pad_state: int):
        for pad in Pad:
            if pad_state & (1 << pad.value):
                pos = pad.vec + CANVAS_CENTER
                pg.draw.circle(self.layer_state, [255, 255, 0], [pos.real, pos.imag], pad.radius)

    def render_effect(self, now: float):
        self.effect_renderer.update_and_render(self.layer_effect, now)

    def render_time(self, time_in_second: float, tps: float):
        if time_in_second < 0:
            m, s = divmod(abs(time_in_second), 60)
            msg = "-%02d:%05.2f" % (int(m), s)
        else:
            m, s = divmod(time_in_second, 60)
            msg = "%02d:%05.2f" % (int(m), s)
        surf = self.font.render(msg, True, [255, 255, 255])
        self.layer_effect.blit(surf, [10, 10])
        surf = self.font.render("%.2f" % tps, True, [255, 255, 255])
        self.layer_effect.blit(surf, [10, 40])

    def render_all_layers(self):
        self.canvas.blit(self.layer_slide, [0, 0])
        self.canvas.blit(self.layer_note, [0, 0])
        self.canvas.blit(self.layer_state, [0, 0])
        self.canvas.blit(self.layer_action, [0, 0])
        self.canvas.blit(self.layer_effect, [0, 0])
        pg.display.update()


class Game:
    def __init__(self, no_render: bool = False):
        if not no_render:
            self.renderer = GameRenderer()
        self.clock = pg.time.Clock()
        self.timer_ms = 0
        self.last_frame_ms = 0
        self.judge_manager = JudgeManager()
        self.pause = True
        self.running = True

    def event_loop(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_SPACE:
                    self.pause = not self.pause
                    if self.pause:
                        pg.mixer.music.pause()
                    else:
                        pg.mixer.music.unpause()

    def load_chart(self, chart: list[SimaiNote]):
        actions = NoteActionConverter.generate_action(chart)
        self.judge_manager.load_chart(chart, actions)

    def run_no_render(self):
        REPORT_WRITER.writeln("========== 静态检查 ==========")
        entries = StaticMuriChecker.check(self.judge_manager.note_sequence)
        REPORT_WRITER.writeln()
        REPORT_WRITER.writeln("========== 动态检查 ==========")
        total = len(self.judge_manager.note_sequence)
        while self.judge_manager.note_pointer < total or len(self.judge_manager.active_notes) > 0:
            self.judge_manager.tick(1)
        REPORT_WRITER.writeln()
        counter = [0, 0, 0, 0, 0, 0, 0, 0]
        for record in entries:
            if record["type"] == "Overlap":
                counter[0] += 1
            elif record["type"] == "SlideHeadTap":
                counter[1] += 1
            elif record["type"] == "TapOnSlide":
                counter[2] += 1
        for record in self.judge_manager.muri_record_list:
            if record["type"] == "Overlap":
                counter[4] += 1
            elif record["type"] == "SlideHeadTap":
                counter[6] += 1
            elif record["type"] == "TapOnSlide":
                counter[7] += 1
            elif record["type"] == "MultiTouch":
                counter[3] += 1
            elif record["type"] == "SlideTooFast":
                counter[5] += 1
        REPORT_WRITER.writeln(("检测完成，静态检查共发现 %d 个叠键无理、%d 个外键无理、%d 个撞尾无理，" +
                               "动态检查共发现 %d 个多押无理、%d 个叠键无理、%d 个内屏无理、%d 个外键无理、%d 个撞尾无理")
                               % tuple(counter))

    def run(self):
        REPORT_WRITER.writeln("========== 静态检查 ==========")
        entries = StaticMuriChecker.check(self.judge_manager.note_sequence)
        REPORT_WRITER.writeln()
        REPORT_WRITER.writeln("========== 动态检查 ==========")
        REPORT_WRITER.writeln("请在弹出的 pygame 窗口中按空格开始播放谱面并检查 ...")
        self.last_frame_ms = self.timer_ms = pg.time.get_ticks()
        while self.running:
            self.event_loop()

            self.clock.tick(200)
            timer_new = pg.time.get_ticks()
            elapsed_ticks = (timer_new - self.timer_ms) * JUDGE_TPS / 1000
            # print(elapsed_ticks)
            self.timer_ms = timer_new
            if self.judge_manager.timer < 0 and self.judge_manager.timer + elapsed_ticks > 0:
                pg.mixer.music.play()
                pass

            if not self.pause:
                this_frame_touch_points, hand_count, finished_notes = self.judge_manager.tick(elapsed_ticks)

                for note in finished_notes:
                    self.renderer.note_renderer.generate_judge_effect(note, self.renderer.effect_renderer)
                for note in self.judge_manager.active_notes:
                    if isinstance(note, SimaiTouchGroup):
                        self.renderer.note_renderer.generate_judge_effect(note, self.renderer.effect_renderer)

                for c, r, t, action in this_frame_touch_points:
                    flag = isinstance(action, ActionSlide)
                    self.renderer.action_renderer.add_effect(PressEffect(self.judge_manager.timer, c, r, flag, hand_count > 2))

            if timer_new - self.last_frame_ms >= 1000 / RENDER_FPS:
                self.renderer.clear_canvas()
                self.renderer.render_active_notes(self.judge_manager.active_notes, self.judge_manager.timer)
                self.renderer.render_active_actions(self.judge_manager.active_actions, self.judge_manager.timer)
                self.renderer.render_pad_state(self.judge_manager.pad_states)
                self.renderer.render_effect(self.judge_manager.timer)
                self.renderer.render_time(self.judge_manager.timer / JUDGE_TPS, self.clock.get_fps())
                self.renderer.render_all_layers()
                self.last_frame_ms = timer_new

        REPORT_WRITER.writeln()
        counter = [0, 0, 0, 0, 0, 0, 0, 0]
        for record in entries:
            if record["type"] == "Overlap":
                counter[0] += 1
            elif record["type"] == "SlideHeadTap":
                counter[1] += 1
            elif record["type"] == "TapOnSlide":
                counter[2] += 1
        for record in self.judge_manager.muri_record_list:
            if record["type"] == "Overlap":
                counter[4] += 1
            elif record["type"] == "SlideHeadTap":
                counter[6] += 1
            elif record["type"] == "TapOnSlide":
                counter[7] += 1
            elif record["type"] == "MultiTouch":
                counter[3] += 1
            elif record["type"] == "SlideTooFast":
                counter[5] += 1
        REPORT_WRITER.writeln(("检测完成，静态检查共发现 %d 个叠键无理、%d 个外键无理、%d 个撞尾无理，" +
                               "动态检查共发现 %d 个多押无理、%d 个叠键无理、%d 个内屏无理、%d 个外键无理、%d 个撞尾无理")
                               % tuple(counter))




if __name__ == "__main__":
    print("输入谱面文件路径: ")
    path_to_chart = pathlib.Path(input())
    if path_to_chart.is_dir():
        path_to_chart = path_to_chart / "maidata.txt"
    path_to_track = path_to_chart.parent / "track.mp3"
    # path_to_bg = path_to_track.parent / "bg.jpg"
    # if path_to_bg.exists():
    #     GameRenderer.background_path = path_to_bg
    pg.mixer.music.load(path_to_track)
    pg.mixer.music.set_volume(0.3)

    first = 0
    charts = {}

    with path_to_chart.open("r", encoding="utf-8") as f:
        text = f.read()
        commands = text.split("&")
        for command in commands:
            if command.startswith("first="):
                first = float(command[6:])
            elif command.startswith("inote_"):
                x = command[6]
                charts[x] = command[8:]

    print("可用难度:", ", ".join(charts.keys()))
    d = input("请输入难度: ")
    chart_str = charts[d]
    flag = bool(input("是否关闭渲染？(不输入任何内容即为否) "))

    try:
        REPORT_WRITER.writeln_no_stdout("谱面文件：%s\n难度：%s\n" % (path_to_chart, d))
        game = Game(flag)
        chart = SimaiParser.parse_simai_chart(chart_str, first)
        game.load_chart(chart)
        REPORT_WRITER.writeln("谱面加载完成，共%d个note" % len(chart))
        if flag:
            game.run_no_render()
        else:
            game.run()
        pg.quit()
    except Exception:
        traceback.print_exc()
        REPORT_WRITER.writeln(traceback.format_exc())

    saving = True
    while saving:
        print("是否保存到文件？请输入输出文件路径，否则不保存")
        output_path = input()
        if output_path:
            output_path = pathlib.Path(output_path)
            if output_path.suffix == "":
                output_path = output_path.with_suffix(".txt")
            if output_path.exists():
                flag = bool(input('"%s" 已经存在，是否覆盖？(不输入任何内容即为否) ' % output_path))
            else:
                flag = True
            if flag:
                with output_path.open("w", encoding="utf-8") as f:
                    REPORT_WRITER.dump(f)
                saving = False
        else:
            saving = False
