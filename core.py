from math import sin, cos, radians
from enum import Enum
import json, pathlib, io

# ==================== Constants Definition ====================
# Geometry definitions
CANVAS_SIZE = 540
CANVAS_CENTER = complex(CANVAS_SIZE // 2, CANVAS_SIZE // 2)
MAIN_SCALE = CANVAS_SIZE / 1080

# in 1080x1080, 100px = 5cm
RADIUS_A = CANVAS_SIZE * 100 / 1080
RADIUS_B = CANVAS_SIZE * 75 / 1080
RADIUS_C = CANVAS_SIZE * 105 / 1080
RADIUS_D = CANVAS_SIZE * 65 / 1080
RADIUS_E = CANVAS_SIZE * 60 / 1080

DISTANCE_A = CANVAS_SIZE * 410 / 1080
DISTANCE_B = CANVAS_SIZE * 220 / 1080
DISTANCE_D = CANVAS_SIZE * 440 / 1080
DISTANCE_E = CANVAS_SIZE * 310 / 1080

DISTANCE_TAP = CANVAS_SIZE * 122.5 / 1080       # 这是定义TAP会从距离中心多远的地方冒出来
DISTANCE_EDGE = CANVAS_SIZE * 480 / 1080

DISTANCE_JUDGE_EFF = CANVAS_SIZE * 80 / 1080    # 这是定义判定显示（目前只有Good）会出现在距离判定区中心多远的地方

# Judging definitions
JUDGE_TPF = 3   # make 60 FPS into 180 TPS
JUDGE_TPS = JUDGE_TPF * 60

FAKE_HOLD_DURATION = JUDGE_TPF * 1

TAP_CRITICAL = JUDGE_TPF * 1
TAP_AVAILABLE = JUDGE_TPF * 9

TOUCH_CRITICAL = JUDGE_TPF * 9
TOUCH_AVAILABLE = JUDGE_TPF * 9

SLIDE_CRITICAL = JUDGE_TPF * 14
SLIDE_AVAILABLE = JUDGE_TPF * 36
SLIDE_DELTA_SHIFT = JUDGE_TPF * 3   # SEGA似乎把Slide判定往前移了3帧

# slides accept judging some time earlier than slide star should be hit
# 6 frames (100ms) here, but maybe it's 3 frames?
# True, it's 3 frames.
# Update: well actually there is a 50 ms input delay, so 6 frames, again.
# but we have a release delay of 1.33 frame, so I make this argument 5 frames, lol.
SLIDE_LEADING = JUDGE_TPF * 5   # 星星入判

# Rendering definitions
RENDER_FPS = 60
NOTE_SPEED = 9 / JUDGE_TPF
TOUCH_DURATION = 30 * JUDGE_TPF

# User defined constants
config_path = pathlib.Path(__file__).parent.absolute() / "config.json"
if not config_path.exists():
    with config_path.open("w", encoding="u8") as f:
        obj = {
            "hand_radius_max": 180,
            "hand_radius_wifi": 100,
            "hand_radius_normal": 40,
            "distance_merge_slide": 20,
            "delta_tangent_merge_slide": 3,
            "tap_on_slide_threshold": round(1/JUDGE_TPF, 4),
            "touch_on_slide_threshold": 8,
            "overlay_threshold": 2,
            "collide_threshold": 12,
            "extra_paddown_delay": 3,
            "release_delay": 1,
            "wifi_need_c": False,
        }
        json.dump(obj, f, indent=4)

with config_path.open(encoding="u8") as f:
    obj = json.load(f)

HAND_RADIUS_MAX = CANVAS_SIZE * obj["hand_radius_max"] / 1080      # 单手touch group允许的最大半径
HAND_RADIUS_WIFI = CANVAS_SIZE * obj["hand_radius_wifi"] / 1080     # wifi星星触点半径
HAND_RADIUS_NORMAL = CANVAS_SIZE * obj["hand_radius_normal"] / 1080    # 普通星星触点半径

# 1pp5 & 1qq5 have a distance of 33.76 px
# pp qq star have a distance of 36.54 px to the edge
DISTANCE_MERGE_SLIDE = CANVAS_SIZE * obj["distance_merge_slide"] / 1080  # 允许两个普通星星触点合并的最大距离
DELTA_TANGENT_MERGE_SLIDE = 2 * sin(radians(obj["delta_tangent_merge_slide"]) / 2)    # 允许两个普通星星触点合并的最大方向夹角

TAP_ON_SLIDE_THRESHOLD = JUDGE_TPF * obj["tap_on_slide_threshold"]      # 拍划tap时间容错
TOUCH_ON_SLIDE_THRESHOLD = JUDGE_TPF * obj["touch_on_slide_threshold"]    # slide撞touch时间容错

OVERLAY_THRESHOLD = JUDGE_TPF * obj["overlay_threshold"]   # 叠键无理最大时间差
COLLIDE_THRESHOLD = JUDGE_TPF * obj["collide_threshold"]  # 撞尾/外键无理最大时间差
COLLIDE_EXTRA_DELTA = COLLIDE_THRESHOLD - TAP_AVAILABLE   # 撞尾/外键无理额外冗余时间

# when slide shoots, pad A is touched another time, this defines the delay
# 外无触发A区的延迟，但是目前这个数会和引导星在第一个A区停留的时长对比
# 设定上外无触发A区的时刻不会晚于引导星离开A区
EXTRA_PADDOWN_DELAY = JUDGE_TPF * obj["extra_paddown_delay"]

# when a note finished, the hand will release after several ticks
# 松手延迟，即任何操作在结束后延迟多久才松开判定区
# 4 ticks or 1.333 frame in 60 fps (48th note in bpm > 225 is treated as each)
RELEASE_DELAY = JUDGE_TPF * obj["release_delay"]

# 指定Wifi星星是否需要C区抬手判
FLAG_WIFI_NEED_C = obj["wifi_need_c"]

# ==================== Judge Enum ====================
class JudgeResult(Enum):
    Not_Yet = 0
    Critical = 1
    Bad = 2

# ==================== Touchpad ====================
def angle2vec(multiple_of_22deg5: int) -> complex:
    """starting from 10:30, rotate clockwise by 22.5 degrees"""
    rad = radians((multiple_of_22deg5 % 16) * 22.5 - 135)
    return complex(round(cos(rad), 6), round(sin(rad), 6))


UNITVEC_A = tuple(angle2vec(2 * i + 1) for i in range(8))
UNITVEC_D = tuple(angle2vec(2 * i) for i in range(8))


def vec2coord(v: complex) -> tuple[float, float]:
    p = v + CANVAS_CENTER
    return p.real, p.imag


class Pad(Enum):
    A1 = 1
    A2 = 2
    A3 = 3
    A4 = 4
    A5 = 5
    A6 = 6
    A7 = 7
    A8 = 0
    B1 = 1 | (1 << 3)
    B2 = 2 | (1 << 3)
    B3 = 3 | (1 << 3)
    B4 = 4 | (1 << 3)
    B5 = 5 | (1 << 3)
    B6 = 6 | (1 << 3)
    B7 = 7 | (1 << 3)
    B8 = 0 | (1 << 3)
    D1 = 1 | (2 << 3)
    D2 = 2 | (2 << 3)
    D3 = 3 | (2 << 3)
    D4 = 4 | (2 << 3)
    D5 = 5 | (2 << 3)
    D6 = 6 | (2 << 3)
    D7 = 7 | (2 << 3)
    D8 = 0 | (2 << 3)
    E1 = 1 | (3 << 3)
    E2 = 2 | (3 << 3)
    E3 = 3 | (3 << 3)
    E4 = 4 | (3 << 3)
    E5 = 5 | (3 << 3)
    E6 = 6 | (3 << 3)
    E7 = 7 | (3 << 3)
    E8 = 0 | (3 << 3)
    C = (4 << 3)

    __slots__ = ["_unit", "_vec", "_r"]

    def __init__(self, value):
        g = value >> 3
        if g == 4:
            # Pad C
            self._unit = 0
            self._vec = 0
            self._r = RADIUS_C
            return

        if g == 0:
            # Pad A
            self._unit = UNITVEC_A[value & 0b111]
            self._vec = self._unit * DISTANCE_A
            self._r = RADIUS_A
            return

        if g == 1:
            # Pad B
            self._unit = UNITVEC_A[value & 0b111]
            self._vec = self._unit * DISTANCE_B
            self._r = RADIUS_B
            return

        if g == 2:
            # Pad D
            self._unit = UNITVEC_D[value & 0b111]
            self._vec = self._unit * DISTANCE_D
            self._r = RADIUS_D
            return

        if g == 3:
            # Pad E
            self._unit = UNITVEC_D[value & 0b111]
            self._vec = self._unit * DISTANCE_E
            self._r = RADIUS_E
            return

    @property
    def unitvec(self) -> complex:
        """unit vector from screen center to pad center"""
        return self._unit

    @property
    def vec(self) -> complex:
        """vector from screen center to pad center"""
        return self._vec

    @property
    def radius(self) -> float:
        """touch detecting radius"""
        return self._r

    def check(self, touch_pos: complex, touch_radius: float = 5) -> bool:
        """check if the touch circle intersects with the pad circle"""
        return abs(touch_pos - self._vec) <= (self._r + touch_radius)

    def rotate45cw(self, deg45: int):
        if self.value == 32:
            return self
        v = (self.value & 0b111000) | ((self.value + deg45) & 0b111)
        return self.__class__(v)

    def reflect1c5(self):
        k = (
            "A2", "A1", "A8", "A7", "A6", "A5", "A4", "A3",
            "B2", "B1", "B8", "B7", "B6", "B5", "B4", "B3",
            "D3", "D2", "D1", "D8", "D7", "D6", "D5", "D4",
            "E3", "E2", "E1", "E8", "E7", "E6", "E5", "E4",
            "C"
        )[self.value]
        return self.__class__[k]

    def is_group_a(self):
        return 0 <= self.value <= 7

    def next_to(self, other: "Pad") -> bool:
        v1, v2 = self.value, other.value
        if v1 == v2:
            return False
        if v1 > v2:
            v1, v2 = v2, v1
        # guaranteed v1 < v2
        g1, g2 = v1 >> 3, v2 >> 3
        i1, i2 = v1 & 0b111, v2 & 0b111
        if g2 == 4:
            # ? <-> C
            return g1 == 1  # True if Pad B

        if (g1 == 0 and g2 == 0) or (g1 == 2 and g2 == 2) or (g1 == 3 and g2 == 3) or (g1 == 1 and g2 == 2):
            # A <-> A / D <-> D / E <-> E / B <-> D
            return False

        if g1 == 1 and g2 == 1:
            # B <-> B
            return i2 == ((i1+1) & 0b111) or i2 == ((i1-1) & 0b111)

        if (g1 == 0 and g2 == 1) or (g1 == 2 and g2 == 3):
            # A <-> B / D <-> E
            return i1 == i2

        # A <-> D / A <-> E / B <-> E
        return i2 == ((i1+1) & 0b111) or i2 == i1


class ReportWriter:
    def __init__(self):
        self.buf = io.StringIO()

    def dump(self, file) -> None:
        lines = self.buf.getvalue().splitlines()
        for line in lines:
            print(line, file=file)

    def writeln(self, *args, **kw):
        print(*args, **kw)
        print(*args, **kw, file=self.buf)

    def writeln_no_stdout(self, *args, **kw):
        print(*args, **kw, file=self.buf)

REPORT_WRITER = ReportWriter()


if __name__ == "__main__":
    for a in range(33):
        for b in range(33):
            print(int(Pad(a).next_to(Pad(b))), end="\t")
        print()

