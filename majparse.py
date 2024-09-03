from typing import Sequence

from core import Pad, JUDGE_TPS, TOUCH_ON_SLIDE_THRESHOLD, TAP_ON_SLIDE_THRESHOLD, REPORT_WRITER, \
    HAND_RADIUS_NORMAL, HAND_RADIUS_WIFI, EXTRA_PADDOWN_DELAY, DISTANCE_MERGE_SLIDE, DELTA_TANGENT_MERGE_SLIDE
from slides import SlideInfo
from simai import SimaiTap, SimaiHold, SimaiTouch, SimaiTouchHold, SimaiTouchGroup, \
                  SimaiSlideChain, SimaiWifi, SimaiNote
from action import ActionPress, ActionSlide, ActionExtraPadDown, Action


class SimaiParser:
    @classmethod
    def _parse_hold_duration(cls, signature: str, bpm: float) -> float:
        if signature.count("#") > 1:
            raise ValueError("invalid length for hold: %s" % signature)

        if signature.count("#") == 1:
            str1, str2 = signature.split("#", 1)
            if str1 == "":
                # "#x.xxx" format, held-down duration of x.xxx seconds
                return float(str2) * JUDGE_TPS

            # "bpm#x:y" format, held-down duration of y x-th notes at given bpm
            if ":" not in str2:
                raise ValueError("invalid length for hold: %s" % signature)

            a, b = str2.split(":", 1)
            tempbpm = float(str1)
            beats = int(a)
            num = int(b)
            return 240 * num / (tempbpm * beats) * JUDGE_TPS

        # "x:y" format, held-down duration of y x-th notes at current bpm
        if ":" not in signature:
            raise ValueError("invalid length for hold: %s" % signature)

        a, b = signature.split(":", 1)
        beats = int(a)
        num = int(b)
        return 240 * num / (bpm * beats) * JUDGE_TPS

    @classmethod
    def _parse_slide_wait_and_duration(cls, signature: str, bpm: float) -> tuple[float, float]:
        if "###" in signature or signature.count("#") > 3:
            raise ValueError("invalid length for slide: %s" % signature)

        if "##" in signature:
            str1, str2 = signature.split("##", 1)
            wait = float(str1) * JUDGE_TPS

            if "#" in str2:
                # A##B#C:D, or T##bpm#x:y, waiting T seconds, tracing duration of y x-th notes at given bpm
                str3, str4 = str2.split("#", 1)
                tempbpm = float(str3)
                if ":" not in str4:
                    raise ValueError("invalid length for slide: %s" % signature)
                a, b = str4.split(":", 1)
                beats = int(a)
                num = int(b)
                return wait, 240 * num / (tempbpm * beats) * JUDGE_TPS

            if ":" in str2:
                # A##B:C, or T##x:y, waiting T seconds, tracing duration of y x-th notes at current bpm
                a, b = str2.split(":", 1)
                beats = int(a)
                num = int(b)
                return wait, 240 * num / (bpm * beats) * JUDGE_TPS

            # A##B, or T##x.xxx, waiting T seconds, tracing duration of x.xxx seconds
            return wait, float(str2) * JUDGE_TPS

        if "#" in signature:
            str1, str2 = signature.split("#", 1)
            tempbpm = float(str1)
            wait = 60 / tempbpm * JUDGE_TPS

            if ":" in str2:
                # A#B:C, or bpm#x:y, waiting 1 beat at given bpm, tracing duration of y x-th notes at given bpm
                a, b = str2.split(":", 1)
                beats = int(a)
                num = int(b)
                return wait, 240 * num / (tempbpm * beats) * JUDGE_TPS

            # A#B, or bpm#x.xxx, waiting 1 beat at given bpm, tracing duration of x.xxx seconds
            return wait, float(str2) * JUDGE_TPS

        # x:y, waiting 1 beat at current bpm, tracing duration of y x-th notes at current bpm
        if ":" not in signature:
            raise ValueError("invalid length for slide: %s" % signature)

        a, b = signature.split(":", 1)
        beats = int(a)
        num = int(b)
        return 60 / bpm * JUDGE_TPS, 240 * num / (bpm * beats) * JUDGE_TPS

    @classmethod
    def _parse_slide_note(cls, cursor: tuple[int, int, str], slide_str: str, now: float, bpm: float) -> list[SimaiNote]:
        # slide_str always contains one slide, but it can be a slide chain
        if "[" not in slide_str or "]" not in slide_str:
            REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid slide:", slide_str, "duration not found")
            return []

        if "w" in slide_str:
            # wifi slide, must be "A???wB???[XXXX]???" format
            idx = slide_str.index("w")
            idx2 = slide_str.index("[")
            idx3 = slide_str.index("]")

            should_not_contain_digit = slide_str[1:idx] + slide_str[idx+2:idx2] + slide_str[idx3+1:]
            if any(map(lambda c: c in should_not_contain_digit, "12345678")):
                # digit before "w" -> try to chain wifi
                REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid wifi slide:", slide_str,
                                      "wifi slide does not support chaining yet")

            shape = slide_str[0] + slide_str[idx:idx+2]  # delete star tap properties (such as 1bxw5)
            signature = slide_str[idx2+1:idx3]
            try:
                wait, duration = cls._parse_slide_wait_and_duration(signature, bpm)
            except ValueError as e:
                REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str, e)
                return []
            return [SimaiWifi(cursor, now, shape, wait, duration)]

        char_iter = iter(slide_str)
        last_target = next(char_iter)
        shapes: list[str] = []
        wait_and_durations: list[tuple[float, float]] = []
        shape_found = False  # ready to read time signature
        signature_state = 0  # 0 -- begin; 1 -- total duration; 2 -- individual; 3 -- total duration confirmed

        for ch in char_iter:
            if ch == "[":
                # time signature
                if not shape_found:
                    # time signature at start
                    REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str)
                    return []

                shape_found = False
                if signature_state == 0:
                    # time signature after first segment
                    # so it is individual durations
                    signature_state = 2
                elif signature_state == 1:
                    # all segments before do not have signature
                    # slide should end after this signature
                    signature_state = 3
                elif signature_state == 3:
                    # new signature after last signature (total duration)
                    REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str)
                    return []

                signature = ""
                for ch2 in char_iter:
                    if ch2 == "]":
                        break
                    signature += ch2
                try:
                    wait, duration = cls._parse_slide_wait_and_duration(signature, bpm)
                except ValueError as e:
                    REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str, e)
                    return []
                wait_and_durations.append((wait, duration))

            if ch in "-^v<>Vpqsz":
                # shape command
                if signature_state == 3:
                    # additional segment after total time signature
                    REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str)
                    return []

                if shape_found:
                    # last segment does not have a time signature
                    if signature_state == 0:
                        # no time signature after first segment
                        # so assuming there is total duration
                        signature_state = 1

                    elif signature_state == 2:
                        # missing time signature in individual durations case
                        REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str)
                        return []

                shape_found = True
                if ch == "V":
                    # grand V shape
                    mid = next(char_iter)
                    end = next(char_iter)
                    shapes.append(last_target + ch + mid + end)
                    last_target = end
                elif ch == "p" or ch == "q":
                    nxt = next(char_iter)
                    if nxt == ch:
                        # pp/qq shape
                        end = next(char_iter)
                        shapes.append(last_target + ch + nxt + end)
                        last_target = end
                    else:
                        # p/q shape
                        shapes.append(last_target + ch + nxt)
                        last_target = nxt
                else:
                    end = next(char_iter)
                    shapes.append(last_target + ch + end)
                    last_target = end

        # validate all shape
        for shape in shapes:
            try:
                SlideInfo.get(shape)
            except KeyError:
                REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str, "unknown shape", shape)
                return []

        wait = wait_and_durations[0][0]
        if signature_state == 2:
            return [SimaiSlideChain(cursor, now, shapes, wait, [t[1] for t in wait_and_durations])]

        if signature_state == 3:
            return [SimaiSlideChain(cursor, now, shapes, wait, total_duration=wait_and_durations[0][1])]

        # should not arrive here
        REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", slide_str)
        return []

    @classmethod
    def _parse_note(cls, cursor: tuple[int, int, str], note_str: str, now: float, bpm: float) -> list[SimaiNote]:
        if note_str == "":
            return []

        if all(map(lambda c: c in "12345678", note_str)):
            # simple tap each omitting "/"
            result = []
            col = cursor[1] - len(note_str)
            for i, c in enumerate(note_str):
                result.append(SimaiTap((cursor[0], col + i + 1, c), now, int(c)))
            return result

        # single note

        if note_str[0] == "C" or (note_str[0] in "ABDE" and note_str[1] in "12345678"):
            # touch
            if note_str[0] == "C":
                pad_str = "C"
            else:
                pad_str = note_str[:2]

            if "h" in note_str and "[" in note_str and "]" in note_str:
                # real touchhold (if no [a:b] appears, it is fake touchhold, treated as touch)
                signature = note_str[note_str.index("[") + 1 : note_str.index("]")]
                try:
                    duration = cls._parse_hold_duration(signature, bpm)
                except ValueError as e:
                    REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", note_str, e)
                    return []
                return [SimaiTouchHold(cursor, now, pad_str, duration)]

            # touch or fake touchhold
            return [SimaiTouch(cursor, now, pad_str)]

        if note_str[0] not in "12345678":
            REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", note_str)
            return []

        pos = int(note_str[0])

        if any(map(lambda c: c in note_str, "-^v<>Vpqszw")):
            if "?" in note_str or "!" in note_str:
                # headless slide
                result = []
            else:
                # separate the slide head
                col = cursor[1] - len(note_str)
                s = ""
                for c in note_str:
                    if c in "-^v<>Vpqszw":
                        break
                    s += c
                    col += 1
                result = [SimaiTap((cursor[0], col, s + "_"), now, pos)]
            # slide
            if "*" in note_str:
                # same head slide
                first, *remaining = note_str.split("*")
                col = cursor[1] - len(note_str) + len(first)
                result.extend(cls._parse_slide_note((cursor[0], col, first), first, now, bpm))
                for s in remaining:
                    col += 1 + len(s)
                    result.extend(cls._parse_slide_note((cursor[0], col, note_str[0] + "*" + s), note_str[0] + s, now, bpm))
            else:
                result.extend(cls._parse_slide_note(cursor, note_str, now, bpm))
            return result

        if "h" in note_str and "[" in note_str and "]" in note_str:
            # real hold
            signature = note_str[note_str.index("[") + 1 : note_str.index("]")]
            try:
                duration = cls._parse_hold_duration(signature, bpm)
            except ValueError as e:
                REPORT_WRITER.writeln("L:", cursor[0], "C:", cursor[1], "Invalid note:", note_str, e)
                return []
            return [SimaiHold(cursor, now, pos, duration)]

        # tap or fake hold
        return [SimaiTap(cursor, now, pos)]

    @classmethod
    def workup_each(cls, each_list: list[SimaiNote]) -> list[SimaiNote]:
        non_touch_list = []
        touch_list = []
        for note in each_list:
            if isinstance(note, SimaiTouch):
                touch_list.append(note)
            else:
                non_touch_list.append(note)

        touch_count = len(touch_list)
        if touch_count <= 1:
            return non_touch_list + touch_list

        parent_list = list(range(touch_count))  # make every touch be the parent of itself

        for idx1 in range(touch_count):
            for idx2 in range(idx1 + 1, touch_count):
                if not touch_list[idx1].pad.next_to(touch_list[idx2].pad):
                    continue
                # touch1 is next to touch2
                parent1 = parent_list[idx1]
                parent2 = parent_list[idx2]
                if parent1 == parent2:
                    continue
                # change parent
                for i in range(touch_count):
                    if parent_list[i] == parent2:
                        parent_list[i] = parent1

        d = {}
        for i in range(touch_count):
            p = parent_list[i]
            if p not in d:
                d[p] = [i]
            else:
                d[p].append(i)

        refined_touch = []
        for group in d.values():
            if len(group) == 1:
                refined_touch.append(touch_list[group[0]])
                continue
            children = [touch_list[i] for i in group]
            cur = children[0].cursor[0], children[0].cursor[1], "/".join(t.cursor[2] for t in children)
            tg = SimaiTouchGroup(cur, children[0].moment, children)
            refined_touch.append(tg)

        return non_touch_list + refined_touch

    @classmethod
    def parse_simai_chart(cls, chart_str: str, first: float = 0) -> list[SimaiNote]:
        lines = chart_str.splitlines()

        bpm = 0.
        beats = 4
        now = first * JUDGE_TPS    # in ticks
        have_note = False
        current_note = ""
        current_each: list[SimaiNote] = []
        result: list[SimaiNote] = []

        for lineno, line in enumerate(lines, start=1):
            length = len(line)
            line_iter = enumerate(line, start=1)
            for column, ch in line_iter:
                if ch == "|" and (column + 1) < length and line[column + 1] == "|":
                    # comments
                    break

                if ch.isspace():
                    continue

                if ch == "(":
                    # bpm definition
                    have_note = False
                    current_note = ""
                    temp = ""
                    for _, ch2 in line_iter:
                        if ch2 == ")":
                            break
                        temp += ch2
                    try:
                        bpm = float(temp)
                    except ValueError:
                        REPORT_WRITER.writeln("L:", lineno, "C:", column, "Invalid bpm:", temp)
                    continue

                if ch == "{":
                    # beats definition
                    have_note = False
                    current_note = ""
                    temp = ""
                    for _, ch2 in line_iter:
                        if ch2 == "}":
                            break
                        temp += ch2
                    try:
                        beats = int(temp)
                    except ValueError:
                        REPORT_WRITER.writeln("L:", lineno, "C:", column, "Invalid beats:", temp)
                    continue

                if ch == "H" and (column + 2) < length and line[column + 1] == "S" and line[column + 2] == "*":
                    # HS definition, ignore
                    have_note = False
                    current_note = ""
                    for _, ch2 in line_iter:
                        if ch2 == ">":
                            break
                    continue

                if ch == "," or ch == "/" or ch == "`":
                    # time marker, each and fake each, but muri detector treat fake each as true each
                    if have_note:
                        notelist = cls._parse_note((lineno, column, current_note), current_note, now, bpm)
                        if ch == "/":
                            current_each.extend(notelist)
                        else:
                            current_each.extend(notelist)
                            result.extend(cls.workup_each(current_each))
                            current_each = []
                    have_note = False
                    current_note = ""

                    if ch == ",":
                        # time step (in ticks)
                        now += 240 / (bpm * beats) * JUDGE_TPS

                    continue

                if ch in "12345678ABCDE":
                    have_note = True
                if have_note:
                    current_note += ch
                else:
                    REPORT_WRITER.writeln("L:", lineno, "C:", column, "Invalid symbol:", ch)

        cls.post_parse_workup(result)
        result.sort(key=lambda x: x.moment)
        return result

    @classmethod
    def post_parse_workup(cls, chart: Sequence[SimaiNote]) -> None:
        for note in chart:
            if isinstance(note, SimaiTap):
                # check for tap-slide pair (tap occurs when slide shoots)
                for note2 in chart:
                    if isinstance(note2, SimaiSlideChain | SimaiWifi):
                        if note.idx == note2.start and abs(note.moment - note2.shoot_moment) < TAP_ON_SLIDE_THRESHOLD:
                            note.set_slide_head(True)
                            break

            # check if touch is on a slide
            if isinstance(note, SimaiTouch):
                for note2 in chart:
                    if isinstance(note2, SimaiSlideChain) and cls._check_touch_on_slide(note, note2):
                        note.set_on_slide(True)
                        break
                    elif isinstance(note2, SimaiWifi) and cls._check_touch_on_wifi(note, note2):
                        note.set_on_slide(True)
                        break

            if isinstance(note, SimaiTouchGroup):
                for touch in note.children:
                    for note2 in chart:
                        if isinstance(note2, SimaiSlideChain) and cls._check_touch_on_slide(touch, note2):
                            touch.set_on_slide(True)
                            break
                        elif isinstance(note2, SimaiWifi) and cls._check_touch_on_wifi(touch, note2):
                            touch.set_on_slide(True)
                            break
                if all(touch.on_slide for touch in note.children):
                    note.set_on_slide(True)

            # standard single-stroke slide
            if isinstance(note, SimaiSlideChain):
                for note2 in chart:
                    if note is note2:
                        continue
                    if isinstance(note2, SimaiSlideChain | SimaiWifi):
                        if note.end == note2.start \
                                and abs(note.end_moment - note2.shoot_moment) < TAP_ON_SLIDE_THRESHOLD:
                            note2.set_after_slide(True)
                            note.set_before_slide(True)
                            continue

                        if not isinstance(note2, SimaiSlideChain):
                            continue

                        exit_first_moment = (note2.shoot_moment +
                                             note2.segment_infos[0].pad_enter_time[0].t * note2.durations[0])
                        if not note.before_slide and exit_first_moment < note.end_moment < note2.critical_moment:
                            # 一笔画还有一种情况，如果当前slide结尾正好“嵌”进另一个slide
                            # 具体而言，此时有另一个slide的位置和切线与当前slide一致
                            # TODO: 切线改为速度
                            t = note.end_moment - 0.5   # 取即将结束的前 0.5 tick 比较位置和切线避免 edge case
                            p = (t - note.segment_shoot_moments[-2]) / note.durations[-1]
                            pos = note.segment_infos[-1].path.point(p)
                            tan = note.segment_infos[-1].path.tangent(p)
                            tan = tan / abs(tan)

                            idx = note2.get_segment_idx(t)
                            p2 = (t - note2.segment_shoot_moments[idx]) / note2.durations[idx]
                            pos2 = note2.segment_infos[idx].path.point(p2)
                            tan2 = note2.segment_infos[idx].path.tangent(p2)
                            tan2 = tan2 / abs(tan2)

                            if abs(pos - pos2) < DISTANCE_MERGE_SLIDE and abs(tan - tan2) < DELTA_TANGENT_MERGE_SLIDE:
                                note.set_before_slide(True)

                        if not note.after_slide and exit_first_moment < note.shoot_moment < note2.critical_moment:
                            t = note.shoot_moment + 0.5
                            p = 0.5 / note.durations[0]
                            pos = note.segment_infos[0].path.point(p)
                            tan = note.segment_infos[0].path.tangent(p)
                            tan = tan / abs(tan)

                            idx = note2.get_segment_idx(t)
                            p2 = (t - note2.segment_shoot_moments[idx]) / note2.durations[idx]
                            pos2 = note2.segment_infos[idx].path.point(p2)
                            tan2 = note2.segment_infos[idx].path.tangent(p2)
                            tan2 = tan2 / abs(tan2)

                            if abs(pos - pos2) < DISTANCE_MERGE_SLIDE and abs(tan - tan2) < DELTA_TANGENT_MERGE_SLIDE:
                                note.set_after_slide(True)

    @classmethod
    def _check_touch_on_slide(cls, touch: SimaiTouch, slide: SimaiSlideChain) -> bool:
        # check first pad (something like tap-slide pair)
        if touch.pad == Pad(slide.start % 8) and \
                slide.shoot_moment - TAP_ON_SLIDE_THRESHOLD < touch.moment < slide.shoot_moment + TOUCH_ON_SLIDE_THRESHOLD:
            return True
        # check remaining pad
        for info, duration, moment in zip(slide.segment_infos, slide.durations, slide.segment_shoot_moments):
            for p, t in info.pad_enter_time:
                if p != touch.pad:
                    continue
                enter_moment = moment + t * duration
                if abs(touch.moment - enter_moment) < TOUCH_ON_SLIDE_THRESHOLD:
                    return True

    @classmethod
    def _check_touch_on_wifi(cls, touch: SimaiTouch, slide: SimaiWifi) -> bool:
        # check first pad (something like tap-slide pair)
        if touch.pad == Pad(slide.start % 8) and abs(touch.moment - slide.shoot_moment) < TOUCH_ON_SLIDE_THRESHOLD:
            return True
        # check remaining pad
        for p, t in slide.info.pad_enter_time:
            if p != touch.pad:
                continue
            enter_moment = slide.shoot_moment + t * slide.duration
            if abs(touch.moment - enter_moment) < TOUCH_ON_SLIDE_THRESHOLD:
                return True


class NoteActionConverter:
    @classmethod
    def generate_action(cls, chart: Sequence[SimaiNote]) -> Sequence[Action]:
        result = []
        for note in chart:
            if isinstance(note, SimaiTap):
                if note.is_slide_head:
                    continue
                result.append(ActionPress(note, note.moment, 0, note.pad.vec, HAND_RADIUS_NORMAL))
                continue

            elif isinstance(note, SimaiTouch):
                if note.on_slide:
                    continue
                result.append(ActionPress(note, note.moment, 0, note.pad.vec, HAND_RADIUS_NORMAL))
                continue

            elif isinstance(note, SimaiTouchGroup):
                if note.on_slide:
                    continue
                result.append(ActionPress(note, note.moment, 0, note.center, note.radius))
                continue

            elif isinstance(note, SimaiHold | SimaiTouchHold):
                result.append(ActionPress(note, note.moment, note.duration, note.pad.vec, HAND_RADIUS_NORMAL))
                continue

            elif isinstance(note, SimaiSlideChain):
                radius = HAND_RADIUS_NORMAL
                # 生成导致外无的额外动作
                if not note.after_slide:
                    first_area_duration = note.segment_infos[0].pad_enter_time[0].t * note.durations[0]
                    delay = min(EXTRA_PADDOWN_DELAY, first_area_duration)
                    result.append(ActionExtraPadDown(note, note.shoot_moment, Pad(note.start % 8), delay))

                # 对于SlideChain中非最后一段的所有slide，都适用于一笔画情况，即结尾不停留
                pack = list(zip(note.segment_infos, note.durations, note.segment_shoot_moments))
                for info, duration, moment in pack[:-1]:
                    result.append(ActionSlide(note, moment, duration, info.real_path, radius, True, False))
                # 最后一段slide，非一笔画的情况下需要停留一段时间
                info, duration, moment = pack[-1]
                result.append(ActionSlide(note, moment, duration, info.real_path, radius, note.before_slide, False))
                continue

            elif isinstance(note, SimaiWifi):
                # 生成导致外无的额外动作
                if not note.after_slide:
                    first_area_duration = note.info.pad_enter_time[0].t * note.duration
                    delay = min(EXTRA_PADDOWN_DELAY, first_area_duration)
                    result.append(ActionExtraPadDown(note, note.shoot_moment, Pad(note.start % 8), delay))

                result.append(ActionSlide(note, note.shoot_moment, note.duration,
                                          note.info.di_real_path[0], HAND_RADIUS_WIFI, True, True))
                result.append(ActionSlide(note, note.shoot_moment, note.duration,
                                          note.info.di_real_path[1], HAND_RADIUS_WIFI, True, True))
                continue

            # should not reach here
            raise TypeError(f'Unexpected note type: {type(note)}')

        result.sort(key=lambda x: x.moment)
        return result




