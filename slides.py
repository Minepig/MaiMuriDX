from typing import NamedTuple
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence, Collection
from dataclasses import dataclass
from enum import Enum
from cmath import phase
from math import degrees

from svg.parser import parse_path
from svg.path import Path, Move
from core import MAIN_SCALE, Pad


# ==================== Basic Definition ====================

@dataclass(slots=True, frozen=True)
class SlideBasicData:
    key: str
    shape_svg: str
    real_path_svg: str | None
    judge_sequence: Sequence[str | Collection[str]]
    arrow_segments: Sequence[int]
    pad_enter_time: Sequence[tuple[str, float]]


_basic_slide = {
    # ========== Straight ==========
    "1-3": SlideBasicData(
        "1-3",
        "M723.688,96.538 L983.462,723.688",
        "M744.354,146.429 L962.797,673.797",
        ["A1", ["A2", "B2"], "A3"],
        [0, 3, 8, 13],
        [("D2", 0.191789), ("E2", 0.191789), ("A2", 0.378), ("B2", 0.378), ("D3", 0.622), ("E3", 0.622),
         ("A3", 0.808211)],
    ),
    "1-4": SlideBasicData(
        "1-4",
        "M723.688,96.538 L723.688,983.462",
        "M723.688,136.370 L723.688,943.630",
        ["A1", "B2", "B3", "A4"],
        [0, 3, 9, 13, 18],
        [("E2", 0.179274), ("B2", 0.318), ("B3", 0.5), ("E4", 0.682), ("A4", 0.820726)],
    ),
    "1-5": SlideBasicData(
        "1-5",
        "M723.688,96.538 L356.312,983.462",
        "M709.706,130.294 L370.294,949.706",
        ["A1", "B1", "C", "B5", "A5"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B5", 0.66), ("A5", 0.837061)],
    ),
    "1-6": SlideBasicData(
        "1-6",
        "M723.688,96.538 L96.538,723.688",
        "M695.523,124.703 L124.703,695.523",
        ["A1", "B8", "B7", "A6"],
        [0, 3, 9, 13, 18],
        [("E1", 0.179274), ("B8", 0.318), ("B7", 0.5), ("E7", 0.682), ("A6", 0.820726)],
    ),
    "1-7": SlideBasicData(
        "1-7",
        "M723.688,96.538 L96.538,356.312",
        "M744.354,146.429 L146.429,335.646",
        ["A1", ["A8", "B8"], "A7"],
        [0, 3, 8, 13],
        [("D1", 0.191789), ("E1", 0.191789), ("A8", 0.378), ("B8", 0.378), ("D8", 0.622), ("E8", 0.622),
         ("A7", 0.808211)],
    ),

    # ========== Lightning shape ==========
    "1s5": SlideBasicData(
        "1s5",
        "M723.688,96.538 L356.312,463.914 723.688,616.086 356.312,983.462",
        "M695.523,124.703 L356.312,463.914 723.688,616.086 384.477,955.297",
        ["A1", "B8", "B7", "C", "B3", "B4", "A5"],
        [0, 3, 9, 12, 17, 21, 25, 30],
        [("E1", 0.110923), ("B8", 0.196307), ("B7", 0.308658), ("C", 0.419819), ("B3", 0.606909), ("B4", 0.691342),
         ("E5", 0.803693), ("A5", 0.889077)],
    ),

    # ========== V-shape ==========
    "1v2": SlideBasicData(
        "1v2",
        "M723.688,96.538 L540,540 983.462,356.312",
        "M709.706,130.294 L540,540 949.706,370.294",
        ["A1", "B1", "C", "B2", "A2"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B2", 0.66), ("A2", 0.837061)],
    ),
    "1v3": SlideBasicData(
        "1v3",
        "M723.688,96.538 L540,540 983.462,723.688",
        "M709.706,130.294 L540,540 949.706,709.706",
        ["A1", "B1", "C", "B3", "A3"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B3", 0.66), ("A3", 0.837061)],
    ),
    "1v4": SlideBasicData(
        "1v4",
        "M723.688,96.538 L540,540 723.688,983.462",
        "M709.706,130.294 L540,540 709.706,949.706",
        ["A1", "B1", "C", "B4", "A4"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B4", 0.66), ("A4", 0.837061)],
    ),
    "1v6": SlideBasicData(
        "1v6",
        "M723.688,96.538 L540,540 96.538,723.688",
        "M709.706,130.294 L540,540 130.294,709.706",
        ["A1", "B1", "C", "B6", "A6"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B6", 0.66), ("A6", 0.837061)],
    ),
    "1v7": SlideBasicData(
        "1v7",
        "M723.688,96.538 L540,540 96.538,356.312",
        "M709.706,130.294 L540,540 130.294,370.294",
        ["A1", "B1", "C", "B7", "A7"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B7", 0.66), ("A7", 0.837061)],
    ),
    "1v8": SlideBasicData(
        "1v8",
        "M723.688,96.538 L540,540 356.312,96.538",
        "M709.706,130.294 L540,540 370.294,130.294",
        ["A1", "B1", "C", "B8", "A8"],
        [0, 3, 7, 12, 15, 19],
        [("B1", 0.2), ("C", 0.38), ("B8", 0.66), ("A8", 0.837061)],
    ),

    # ========== L-shape (Grand V) ==========
    "1V72": SlideBasicData(
        "1V72",
        "M723.688,96.538 L96.538,356.312 983.462,356.312",
        None,
        ["A1", ["A8", "B8"], "A7", "B8", "B1", "A2"],
        [0, 3, 8, 17, 23, 27, 32],
        [("D1", 0.083149), ("E1", 0.083149), ("A8", 0.16388), ("B8", 0.16388), ("D8", 0.269665), ("E8", 0.269665),
         ("A7", 0.350396), ("E8", 0.535096), ("B8", 0.613678), ("B1", 0.716773), ("E2", 0.819867), ("A2", 0.89845)],
    ),
    "1V73": SlideBasicData(
        "1V73",
        "M723.688,96.538 L96.538,356.312 983.462,723.688",
        None,
        ["A1", ["A8", "B8"], "A7", "B7", "C", "B3", "A3"],
        [0, 3, 9, 17, 21, 27, 30, 34],
        [("D1", 0.079442), ("E1", 0.079442), ("A8", 0.156573), ("B8", 0.156573), ("D8", 0.257641), ("E8", 0.257641),
         ("A7", 0.334772), ("B7", 0.531371), ("C", 0.636812), ("B3", 0.800831), ("A3", 0.904553)],
    ),
    "1V74": SlideBasicData(
        "1V74",
        "M723.688,96.538 L96.538,356.312 723.688,983.462",
        None,
        ["A1", ["A8", "B8"], "A7", "B6", "B5", "A4"],
        [0, 3, 9, 17, 23, 27, 32],
        [("D1", 0.083149), ("E1", 0.083149), ("A8", 0.16388), ("B8", 0.16388), ("D8", 0.269665), ("E8", 0.269665),
         ("A7", 0.350396), ("E7", 0.535096), ("B6", 0.613678), ("B5", 0.716773), ("E5", 0.819867), ("A4", 0.89845)],
    ),
    "1V75": SlideBasicData(
        "1V75",
        "M723.688,96.538 L96.538,356.312 356.312,983.462",
        None,
        ["A1", ["A8", "B8"], "A7", ["A6", "B6"], "A5"],
        [0, 3, 9, 18, 23, 28],
        [("D1", 0.095895), ("E1", 0.095895), ("A8", 0.189), ("B8", 0.189), ("D8", 0.311), ("E8", 0.311),
         ("A7", 0.404105), ("D7", 0.595895), ("E7", 0.595895), ("A6", 0.689), ("B6", 0.689), ("D6", 0.811),
         ("E6", 0.811), ("A5", 0.904105)],
    ),

    # ========== Circle Arc (CCW) ==========
    # When solving circle slide, use a slightly smaller circle path rather than the slide path itself.
    "1<1": SlideBasicData(
        "1<1",
        "M723.688,96.538 A480,480 0 0,0 356.312,983.462 A480,480 0 0,0 723.688,96.538",
        "M709.706,130.294 A443.462,443.462 0 0,0 370.294,949.706 A443.462,443.462 0 1,0 709.706,130.294",
        ["A1", "A8", "A7", "A6", "A5", "A4", "A3", "A2", "A1"],
        [0, 3, 11, 19, 27, 35, 43, 51, 59, 63],
        [("D1", 0.037582), ("A8", 0.087418), ("D8", 0.162582), ("A7", 0.212418), ("D7", 0.287582), ("A6", 0.337418),
         ("D6", 0.412582), ("A5", 0.462418), ("D5", 0.537582), ("A4", 0.587418), ("D4", 0.662582), ("A3", 0.712418),
         ("D3", 0.787582), ("A2", 0.837418), ("D2", 0.912582), ("A1", 0.962418)],
    ),
    "1<2": SlideBasicData(
        "1<2",
        "M723.688,96.538 A480,480 0 1,0 983.462,356.312",
        "M709.706,130.294 A443.462,443.462 0 1,0 949.706,370.294",
        ["A1", "A8", "A7", "A6", "A5", "A4", "A3", "A2"],
        [0, 3, 11, 19, 27, 35, 43, 51, 55],
        [("D1", 0.042951), ("A8", 0.099906), ("D8", 0.185808), ("A7", 0.242764), ("D7", 0.328665), ("A6", 0.385621),
         ("D6", 0.471522), ("A5", 0.528478), ("D5", 0.614379), ("A4", 0.671335), ("D4", 0.757236), ("A3", 0.814192),
         ("D3", 0.900094), ("A2", 0.957049)],
    ),
    "1<3": SlideBasicData(
        "1<3",
        "M723.688,96.538 A480,480 0 1,0 983.462,723.688",
        "M709.706,130.294 A443.462,443.462 0 1,0 949.706,709.706",
        ["A1", "A8", "A7", "A6", "A5", "A4", "A3"],
        [0, 3, 11, 19, 27, 35, 43, 47],
        [("D1", 0.050109), ("A8", 0.116557), ("D8", 0.216776), ("A7", 0.283224), ("D7", 0.383443), ("A6", 0.449891),
         ("D6", 0.550109), ("A5", 0.616557), ("D5", 0.716776), ("A4", 0.783224), ("D4", 0.883443), ("A3", 0.949891)],
    ),
    "1<4": SlideBasicData(
        "1<4",
        "M723.688,96.538 A480,480 0 1,0 723.688,983.462",
        "M709.706,130.294 A443.462,443.462 0 1,0 709.706,949.706",
        ["A1", "A8", "A7", "A6", "A5", "A4"],
        [0, 3, 11, 19, 27, 35, 39],
        [("D1", 0.060131), ("A8", 0.139869), ("D8", 0.260131), ("A7", 0.339869), ("D7", 0.460131), ("A6", 0.539869),
         ("D6", 0.660131), ("A5", 0.739869), ("D5", 0.860131), ("A4", 0.939869)],
    ),
    "1<5": SlideBasicData(
        "1<5",
        "M723.688,96.538 A480,480 0 0,0 356.312,983.462",
        "M709.706,130.294 A443.462,443.462 0 0,0 370.294,949.706",
        ["A1", "A8", "A7", "A6", "A5"],
        [0, 3, 11, 19, 27, 31],
        [("D1", 0.075164), ("A8", 0.174836), ("D8", 0.325164), ("A7", 0.424836), ("D7", 0.575164), ("A6", 0.674836),
         ("D6", 0.825164), ("A5", 0.924836)],
    ),
    "1<6": SlideBasicData(
        "1<6",
        "M723.688,96.538 A480,480 0 0,0 96.538,723.688",
        "M709.706,130.294 A443.462,443.462 0 0,0 130.294,709.706",
        ["A1", "A8", "A7", "A6"],
        [0, 3, 11, 19, 23],
        [("D1", 0.100218), ("A8", 0.233115), ("D8", 0.433552), ("A7", 0.566448), ("D7", 0.766885), ("A6", 0.899782)],
    ),
    "1<7": SlideBasicData(
        "1<7",
        "M723.688,96.538 A480,480 0 0,0 96.538,356.312",
        "M709.706,130.294 A443.462,443.462 0 0,0 130.294,370.294",
        ["A1", "A8", "A7"],
        [0, 3, 11, 15],
        [("D1", 0.150328), ("A8", 0.349672), ("D8", 0.650328), ("A7", 0.849672)],
    ),
    "1<8": SlideBasicData(
        "1<8",
        "M723.688,96.538 A480,480 0 0,0 356.312,96.538",
        "M709.706,130.294 A443.462,443.462 0 0,0 370.294,130.294",
        ["A1", "A8"],
        [0, 3, 7],
        [("D1", 0.300655), ("A8", 0.699345)],
    ),

    # ========== U-shape (CCW around center) ==========
    "1p1": SlideBasicData(
        "1p1",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 1,0 723.688,540.000 L723.688,96.538",
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "A1"],
        [0, 3, 9, 12, 15, 18, 21, 24, 28, 33],
        [("E1", 0.099093), ("B8", 0.17537), ("B7", 0.275739), ("B6", 0.365444), ("B5", 0.455148), ("B4", 0.544852),
         ("B3", 0.634556), ("B2", 0.724261), ("E2", 0.82463), ("A1", 0.900907)],
    ),
    "1p2": SlideBasicData(
        "1p2",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 0,0 669.887,669.887 L983.462,356.312",
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "B3", "A2"],
        [0, 3, 9, 12, 15, 18, 21, 25, 30],
        [("E1", 0.108876), ("B8", 0.192652), ("B7", 0.302912), ("B6", 0.401456), ("B5", 0.5), ("B4", 0.598544),
         ("B3", 0.697088), ("E3", 0.807348), ("A2", 0.891124)],
    ),
    "1p3": SlideBasicData(
        "1p3",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 0,0 540.000,723.688 L983.462,723.688",
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "A3"],
        [0, 3, 9, 12, 15, 18, 22, 27],
        [("E1", 0.120758), ("B8", 0.213712), ("B7", 0.336025), ("B6", 0.445342), ("B5", 0.554658), ("B4", 0.663975),
         ("E4", 0.786288), ("A3", 0.879242)],
    ),
    "1p4": SlideBasicData(
        "1p4",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 0,0 410.113,669.887 L723.688,983.462",
        None,
        ["A1", "B8", "B7", "B6", "B5", "A4"],
        [0, 3, 9, 12, 15, 19, 24],
        [("E1", 0.135579), ("B8", 0.239942), ("B7", 0.377267), ("B6", 0.5), ("B5", 0.622733), ("E5", 0.760058),
         ("A4", 0.864421)],
    ),
    "1p5": SlideBasicData(
        "1p5",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 0,0 356.312,540.000 L356.312,983.462",
        None,
        ["A1", "B8", "B7", "B6", "A5"],
        [0, 3, 9, 12, 16, 21],
        [("E1", 0.154547), ("B8", 0.27351), ("B7", 0.430048), ("B6", 0.569952), ("E6", 0.72649), ("A5", 0.845453)],
    ),
    "1p6": SlideBasicData(
        "1p6",
        ("M723.688,96.538 L410.113,410.113 A183.688,183.688 0 1,0 669.887,669.887"
         "A183.688,183.688 0 1,0 410.113,410.113 L96.538,723.688"),
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "B1", "B8", "B7", "A6"],
        [0, 3, 9, 12, 15, 18, 21, 24, 27, 30, 33, 37, 42],
        [("E1", 0.078061), ("B8", 0.138183), ("B7", 0.217269), ("B6", 0.287952), ("B5", 0.358635), ("B4", 0.429317),
         ("B3", 0.5), ("B2", 0.570683), ("B1", 0.641365), ("B8", 0.712048), ("B7", 0.782731), ("E7", 0.861817),
         ("A6", 0.921939)]
    ),
    "1p7": SlideBasicData(
        "1p7",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 1,0 540.000,356.312 L96.538,356.312",
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "B1", "B8", "A7"],
        [0, 3, 9, 12, 15, 18, 21, 24, 27, 30, 34, 39],
        [("E1", 0.084019), ("B8", 0.148693), ("B7", 0.233795), ("B6", 0.309853), ("B5", 0.385912), ("B4", 0.461971),
         ("B3", 0.538029), ("B2", 0.614088), ("B1", 0.690147), ("B8", 0.766205), ("E8", 0.851307), ("A7", 0.915981)],
    ),
    "1p8": SlideBasicData(
        "1p8",
        "M723.688,96.538 L410.113,410.113 A183.688,183.688 0 1,0 669.887,410.113 L356.312,96.538",
        None,
        ["A1", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "B1", "A8"],
        [0, 3, 9, 12, 15, 18, 21, 24, 27, 31, 36],
        [("E1", 0.090935), ("B8", 0.160934), ("B7", 0.253041), ("B6", 0.33536), ("B5", 0.41768), ("B4", 0.5),
         ("B3", 0.58232), ("B2", 0.66464), ("B1", 0.746959), ("E1", 0.839066), ("A8", 0.909065)],
    ),

    # ========== Cup-shape (CCW around center-right) ==========
    "1pp1": SlideBasicData(
        "1pp1",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 943.845,413.512 L723.688,96.538",
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", "A1"],
        [0, 3, 7, 12, 17, 24, 30, 35],
        [("B1", 0.1165), ("C", 0.2215), ("B4", 0.3732), ("E4", 0.4542), ("A3", 0.5255), ("D3", 0.6535),
         ("A2", 0.7315), ("D2", 0.8535), ("E2", 0.8535), ("A1", 0.933315)],
    ),
    "1pp2": SlideBasicData(
        "1pp2",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 983.462,540.000 L983.462,356.312",
        None,
        ["A1", "B1", "C", "B4", "A3", "A2"],
        [0, 3, 7, 12, 17, 24, 28],
        [("B1", 0.1454), ("C", 0.2765), ("B4", 0.4666), ("E4", 0.5666), ("A3", 0.6583), ("D3", 0.8146),
         ("A2", 0.916833)],
    ),
    "1pp3": SlideBasicData(
        "1pp3",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 0,0 802.981,757.860 L983.462,723.688",
        None,
        ["A1", "B1", "C", "B4", "A3"],
        [0, 3, 7, 12, 17, 22],
        [("B1", 0.1855), ("C", 0.3566), ("B4", 0.5964), ("E4", 0.7312), ("A3", 0.849092)],
    ),
    "1pp4": SlideBasicData(
        "1pp4",
        ("M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 983.462,540.000"
         "A221.731,221.731 0 1,0 560.735,633.623 L723.688,983.462"),
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", "B1", "C", "B4", "A4"],
        [0, 3, 7, 12, 17, 24, 31, 36, 41, 45, 49],
        [("B1", 0.0823), ("C", 0.1588), ("B4", 0.2694), ("E4", 0.3274), ("A3", 0.3793), ("D3", 0.4716), ("A2", 0.5284),
         ("E2", 0.6207), ("B1", 0.6726), ("C", 0.7506), ("B4", 0.8613), ("A4", 0.933673)],
    ),
    "1pp5": SlideBasicData(
        "1pp5",
        ("M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 983.462,540.000"
         "A221.731,221.731 0 0,0 554.421,461.340 L356.312,983.462"),
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", "B1", "C", "B5", "A5"],
        [0, 3, 7, 12, 17, 24, 31, 36, 41, 45, 49],
        [("B1", 0.0825), ("C", 0.1605), ("B4", 0.2705), ("E4", 0.3278), ("A3", 0.3815), ("D3", 0.4725), ("A2", 0.5292),
         ("E2", 0.6238), ("B1", 0.6739), ("C", 0.7518), ("B5", 0.8572), ("A5", 0.933545)],
    ),
    "1pp6": SlideBasicData(
        "1pp6",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 637.167,356.565 L96.538,723.688",
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", "B1", ["C", "B8"], ["B6", "B7"], "A6"],
        [0, 3, 7, 12, 17, 24, 31, 36, 40, 44, 48],
        [("B1", 0.0844), ("C", 0.1624), ("B4", 0.2743), ("E4", 0.3333), ("A3", 0.3849), ("D3", 0.4808),
         ("A2", 0.5375), ("E2", 0.6352), ("B1", 0.6863), ("B8", 0.7622), ("C", 0.7622), ("B7", 0.8184),
         ("B6", 0.8628), ("E7", 0.8773), ("A6", 0.933545)],
    ),
    "1pp7": SlideBasicData(
        "1pp7",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 748.948,318.638 L96.538,356.312",
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", "B1", "B8", "A7"],
        [0, 3, 7, 12, 17, 24, 31, 37, 41, 46],
        [("B1", 0.0896), ("C", 0.1732), ("B4", 0.2882), ("E4", 0.3516), ("A3", 0.4063), ("D3", 0.5066),
         ("A2", 0.5672), ("E2", 0.6695), ("B1", 0.7227), ("B8", 0.7967), ("E8", 0.8705), ("A7", 0.927354)],
    ),
    "1pp8": SlideBasicData(
        "1pp8",
        "M723.688,96.538 L560.735,446.377 A221.731,221.731 0 1,0 858.620,340.558 L356.312,96.538",
        None,
        ["A1", "B1", "C", "B4", "A3", "A2", ["A1", "B1"], "A8"],
        [0, 3, 7, 12, 17, 24, 31, 36, 41],
        [("B1", 0.0977), ("C", 0.1888), ("B4", 0.3195), ("E4", 0.3883), ("A3", 0.4485), ("D3", 0.5605),
         ("A2", 0.6255), ("D2", 0.7354), ("E2", 0.7354), ("A1", 0.7945), ("B1", 0.7945), ("D1", 0.8712),
         ("E1", 0.8712), ("A8", 0.942918)],
    ),

    # ========== Wifi shape ==========
    # Center Lane
    "1w5": SlideBasicData(
        "1w5",
        "M723.688,96.538 L356.312,983.462",
        None,
        ["A1", "B1", "C", ["B5", "A5"]],
        [0, 2, 5, 8, 11],
        [("E1", 0.191789), ("B1", 0.191789), ("E2", 0.191789), ("B2", 0.31), ("B8", 0.31), ("C", 0.4), ("B3", 0.5),
         ("B7", 0.5), ("B4", 0.618), ("B6", 0.618), ("B5", 0.666), ("E5", 0.75), ("E6", 0.75), ("A4", 0.823636),
         ("D5", 0.823636), ("A5", 0.823636), ("D6", 0.823636), ("A6", 0.823636)],
    ),
    # Right Lane and real path of right hand (A1 -> D5)
    "1Wi4": SlideBasicData(
        "1Wi4",
        "M723.688,96.538 L723.688,983.462",
        "M723.688,96.538 L540,1020",
        ["A1", "B2", "B3", ["A4", "D5"]],
        [],
        [],
    ),
    # Left Lane and real path of left hand (A1 -> D6)
    "1Wi6": SlideBasicData(
        "1Wi6",
        "M723.688,96.538 L96.538,723.688",
        "M723.688,96.538 L200.589,879.411",
        ["A1", "B8", "B7", ["A6", "D6"]],
        [],
        [],
    ),
}


# ==================== Standard Slide Mapping ====================
# Use basic definition to generate all possible (standard) slides

class SlidePath:
    """This is a wrapper class, to rotate and reflect slide path.
        Rotation is applied after reflection. Reflection is relative to the starting point (1>3 -> 1<7)"""

    __slots__ = ["path", "reflect", "rotate", "_coeff"]

    def __init__(self, path: Path | None, reflect1c5: bool = False, rotate45cw: int = 0):
        self.path = path
        self.reflect = reflect1c5
        self.rotate = rotate45cw
        if reflect1c5:
            self._coeff = Pad[("D8", "D1", "D2", "D3", "D4", "D5", "D6", "D7")[rotate45cw]].unitvec
        else:
            self._coeff = Pad[("D3", "D4", "D5", "D6", "D7", "D8", "D1", "D2")[rotate45cw]].unitvec
        self._coeff *= MAIN_SCALE

    def point(self, pos: float) -> complex:
        """calculate point coordinate relative to center
        :param pos in range [0, 1]"""

        c = self.path.point(pos) - (540 + 540j)
        if self.reflect:
            c = c.conjugate()
        return c * self._coeff

    def tangent(self, pos: float) -> complex:
        """calculate tangent vector at a certain point, not normalized
        :param pos in range [0, 1]"""

        c = self.path.tangent(pos)
        if self.reflect:
            c = c.conjugate()
        c *= self._coeff
        return c

    def length(self) -> float:
        """calculate path length"""
        return self.path.length()

    def __repr__(self):
        return f"SlidePath({repr(self.path)}, {self.reflect}, {self.rotate})"


class SlideType(Enum):
    Straight = "-"
    Circle_CCW = "<"
    Circle_CW = ">"
    Curve_CCW = "p"
    Curve_CW = "q"
    Lightning_S = "s"
    Lightning_Z = "z"
    V_Shape = "v"
    BigCurve_CCW = "pp"
    BigCurve_CW = "qq"
    L_Shape_CCW = "V-"
    L_Shape_CW = "V+"
    Wifi = "w"
    Invalid = "??"


class PadTimePair(NamedTuple):
    pad: Pad
    t: float


class SlideInfoBase(metaclass=ABCMeta):
    """Base class of SlideInfo and WifiInfo, only defines shared helper functions"""

    @abstractmethod
    def __init__(self):
        # some type annotation things ...
        self.key = str()
        self.start = int()
        self.end = int()
        self.type_ = SlideType.Invalid
        self.path = SlidePath(None, False, 0)
        self.arrow_segments: tuple[int, ...] = ()
        self.pad_enter_time: tuple[PadTimePair, ...] = ()
        self.total_arrow_count = int()
        self.arrow_points: tuple[tuple[complex, float], ...] = ()

    # ========== Helper functions ==========
    @staticmethod
    def _parse_svg(svg: str) -> Path:
        p = parse_path(svg)
        if isinstance(p[0], Move):
            del p[0]
        return p

    @staticmethod
    def _transform_judge_sequence(
            seq: Sequence[str | Collection[str]], reflect: bool = False, rotate45cw: int = 0
    ) -> list[set[Pad]]:
        """Rotation is applied after reflection. Reflection is relative to the starting point (1>3 -> 1<7)"""
        result = []
        for item in seq:
            t = (item,) if isinstance(item, str) else item
            s = set()
            for a in t:
                p = Pad[a]
                if reflect:
                    p = p.reflect1c5()
                p = p.rotate45cw(rotate45cw)
                s.add(p)
            result.append(s)
        return result

    @staticmethod
    def _transform_pad_enter_time(
            seq: Sequence[tuple[str, float]], reflect: bool = False, rotate45cw: int = 0
    ) -> list[PadTimePair]:
        """Rotation is applied after reflection. Reflection is relative to the starting point (1>3 -> 1<7)"""
        result = []
        for a, time in seq:
            p = Pad[a]
            if reflect:
                p = p.reflect1c5()
            p = p.rotate45cw(rotate45cw)
            result.append(PadTimePair(p, time))
        return result



class SlideInfo(SlideInfoBase):
    """Data class for standard slides (excluding wifi)"""
    _entries = {}

    def __init__(
            self,
            key: str,
            start: int,
            end: int,
            type_: SlideType,
            path: SlidePath,
            real_path: SlidePath | None,
            judge_sequence: Sequence[Collection[Pad]],
            arrow_segments: Sequence[int],
            pad_enter_time: Sequence[PadTimePair],
    ):
        self.key = key
        self.start = start
        self.end = end
        self.type_ = type_

        # some helper fields for skipping check
        if (type_ == SlideType.L_Shape_CCW) or (type_ == SlideType.L_Shape_CW):
            self.is_L = True
            self.is_special_L = ((end - start) % 8 == 4)
        else:
            self.is_L = False
            self.is_special_L = False

        self.path = self.real_path = path
        # if real_path is None:
        #     self.real_path = path
        # else:
        #     self.real_path = real_path

        j = []
        for item in judge_sequence:
            j.append(frozenset(item))
        self.judge_sequence = tuple(j)

        self.arrow_segments = tuple(arrow_segments)

        assert len(arrow_segments) == len(judge_sequence) + 1

        self.pad_enter_time = tuple(sorted(pad_enter_time, key=lambda x: x[1]))

        assert {self.pad_enter_time[-1][0]} == self.judge_sequence[-1]

        self.total_arrow_count = arrow_segments[-1]
        l = []
        length = self.path.length()
        for i in range(self.total_arrow_count):
            pos = (i + 1) * 47.112 / length
            d = self.path.tangent(pos)
            c = self.path.point(pos)
            a = degrees(phase(-d))
            l.append((c, a))
        self.arrow_points = tuple(l)

    @classmethod
    def clear_all(cls):
        """Clear all slide info"""
        cls._entries.clear()

    @classmethod
    def get(cls, key: str) -> "SlideInfo":
        """Acquire the info of a standard slide"""
        return cls._entries[key]

    @classmethod
    def get_all(cls) -> "Collection[SlideInfo]":
        return cls._entries.values()

    @classmethod
    def _alias(cls, alias: str, key: str):
        cls._entries[alias] = cls._entries[key]

    # ========== Register all standard slides ==========
    @classmethod
    def _register(
            cls, key: str, start: int, end: int, type_: SlideType, data: SlideBasicData, reflect: bool, rotate: int
    ):
        path = SlidePath(cls._parse_svg(data.shape_svg), reflect, rotate)
        if data.real_path_svg is None:
            real_path = path
        else:
            real_path = SlidePath(cls._parse_svg(data.real_path_svg), reflect, rotate)

        judge_sequence = cls._transform_judge_sequence(data.judge_sequence, reflect, rotate)
        pad_enter_time = cls._transform_pad_enter_time(data.pad_enter_time, reflect, rotate)

        cls._entries[key] = cls(
            key, start, end, type_, path, real_path, judge_sequence, data.arrow_segments, pad_enter_time
        )

    @classmethod
    def generate_all(cls):
        """Initialize all standard slides"""
        cls.clear_all()
        for start in range(1, 9):
            # Straight
            for dist in [2, 3, 4, 5, 6]:
                end = (start + dist) % 8 or 8
                key = "%d-%d" % (start, end)
                data = _basic_slide["1-%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.Straight, data, False, start - 1)

            # Circle, pq-shape, ppqq-shape
            for dist in range(8):
                # CCW
                end = (start + dist) % 8 or 8

                key = ("%d<%d" if start in [1, 2, 7, 8] else "%d>%d") % (start, end)
                data = _basic_slide["1<%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.Circle_CCW, data, False, start - 1)
                if 5 <= dist <= 7:
                    cls._alias("%d^%d" % (start, end), key)

                key = "%dp%d" % (start, end)
                data = _basic_slide["1p%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.Curve_CCW, data, False, start - 1)

                key = "%dpp%d" % (start, end)
                data = _basic_slide["1pp%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.BigCurve_CCW, data, False, start - 1)

                # CW
                end = (start - dist) % 8 or 8

                key = ("%d>%d" if start in [1, 2, 7, 8] else "%d<%d") % (start, end)
                data = _basic_slide["1<%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.Circle_CW, data, True, start - 1)
                if 5 <= dist <= 7:
                    cls._alias("%d^%d" % (start, end), key)

                key = "%dq%d" % (start, end)
                data = _basic_slide["1p%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.Curve_CW, data, True, start - 1)

                key = "%dqq%d" % (start, end)
                data = _basic_slide["1pp%d" % (dist + 1)]
                cls._register(key, start, end, SlideType.BigCurve_CW, data, True, start - 1)

            # v-shape
            for dist in [1, 2, 3, 5, 6, 7]:
                data = _basic_slide["1v%d" % (dist + 1)]
                end = (start + dist) % 8 or 8
                key = "%dv%d" % (start, end)
                cls._register(key, start, end, SlideType.V_Shape, data, False, start - 1)

            # lightning
            data = _basic_slide["1s5"]
            end = (start - 4) % 8 or 8
            key = "%ds%d" % (start, end)
            cls._register(key, start, end, SlideType.Lightning_S, data, False, start - 1)
            key = "%dz%d" % (start, end)
            cls._register(key, start, end, SlideType.Lightning_Z, data, True, start - 1)

            # L-shape
            for dist in [1, 2, 3, 4]:
                data = _basic_slide["1V7%d" % (dist + 1)]

                end = (start + dist) % 8 or 8
                mid = (start - 2) % 8 or 8
                key = "%dV%d%d" % (start, mid, end)
                cls._register(key, start, end, SlideType.L_Shape_CCW, data, False, start - 1)

                end = (start - dist) % 8 or 8
                mid = (start + 2) % 8 or 8
                key = "%dV%d%d" % (start, mid, end)
                cls._register(key, start, end, SlideType.L_Shape_CW, data, True, start - 1)


class WifiInfo(SlideInfoBase):
    """Data class for wifi slide"""
    _entries = {}

    def __init__(
            self,
            key: str,
            start: int,
            end: int,
            tri_path: tuple[SlidePath, SlidePath, SlidePath],
            di_real_path: tuple[SlidePath, SlidePath],
            tri_judge_sequence: tuple[Sequence[Collection[Pad]], Sequence[Collection[Pad]], Sequence[Collection[Pad]]],
            arrow_segments: Sequence[int],
            pad_enter_time: Sequence[PadTimePair],
    ):
        self.key = key
        self.start = start
        self.end = end
        self.type_ = SlideType.Wifi

        self.end_ccw = (end - 1) % 8 or 8
        self.end_cw = (end + 1) % 8 or 8

        self.tri_path = tri_path
        self.path = tri_path[1]
        self.di_real_path = di_real_path

        trij = []
        for lane in tri_judge_sequence:
            j = []
            for item in lane:
                j.append(frozenset(item))
            trij.append(tuple(j))
        self.tri_judge_sequence = tuple(trij)

        self.arrow_segments = tuple(arrow_segments)

        self.pad_enter_time = tuple(sorted(pad_enter_time, key=lambda x: x[1]))

        self.total_arrow_count = t = arrow_segments[-1]
        l = []
        for i in range(self.total_arrow_count):
            pos = (i + 0.8) / (t + 2.3)
            d = self.path.tangent(pos)
            c = self.path.point(pos)
            a = 67.5 - degrees(phase(d))
            l.append((c, a))
        self.arrow_points = tuple(l)

    @classmethod
    def clear_all(cls):
        """Clear all slide info"""
        cls._entries.clear()

    @classmethod
    def get(cls, key: str) -> "WifiInfo":
        """Acquire the info of a standard slide"""
        return cls._entries[key]

    @classmethod
    def get_all(cls) -> "Collection[WifiInfo]":
        return cls._entries.values()

    @classmethod
    def generate_all(cls):
        """Initialize all wifi slides"""
        cls.clear_all()
        for start in range(1, 9):
            data_mid = _basic_slide["1w5"]
            data_ccw = _basic_slide["1Wi4"]
            data_cw = _basic_slide["1Wi6"]
            end = (start - 4) % 8 or 8
            key = "%dw%d" % (start, end)

            path_mid = SlidePath(cls._parse_svg(data_mid.shape_svg), False, start - 1)
            path_ccw = SlidePath(cls._parse_svg(data_ccw.shape_svg), False, start - 1)
            path_cw = SlidePath(cls._parse_svg(data_cw.shape_svg), False, start - 1)
            tri_path = (path_ccw, path_mid, path_cw)

            real_path_ccw = SlidePath(cls._parse_svg(data_ccw.real_path_svg), False, start - 1)
            real_path_cw = SlidePath(cls._parse_svg(data_cw.real_path_svg), False, start - 1)
            if start in [1, 2, 7, 8]:
                di_real_path = (real_path_cw, real_path_ccw)    # left hand, right hand
            else:
                di_real_path = (real_path_ccw, real_path_cw)

            judge_mid = cls._transform_judge_sequence(data_mid.judge_sequence, False, start - 1)
            judge_ccw = cls._transform_judge_sequence(data_ccw.judge_sequence, False, start - 1)
            judge_cw = cls._transform_judge_sequence(data_cw.judge_sequence, False, start - 1)
            tri_judge = (judge_ccw, judge_mid, judge_cw)

            pad_enter_time = cls._transform_pad_enter_time(data_mid.pad_enter_time, False, start - 1)

            cls._entries[key] = cls(
                key, start, end, tri_path, di_real_path, tri_judge, data_mid.arrow_segments, pad_enter_time
            )


def init():
    SlideInfo.generate_all()
    WifiInfo.generate_all()


if __name__ == "__main__":
    init()
    print(len(SlideInfo._entries))
    # for key, info in WifiInfo._entries.items():
    #     print(info.pad_enter_time[-1])
    import pygame
    pygame.init()
    screen = pygame.display.set_mode([540, 540])
    screen.blit(pygame.image.load("images/background/Default_Background.png").convert_alpha(), (0, 0))
    for info in SlideInfo._entries.values():
        if info.type_ != SlideType.BigCurve_CCW and info.type_ != SlideType.BigCurve_CW:
            continue
        points = []
        for i in range(10000):
            c = info.path.point(i / 10000) + complex(270, 270)
            points.append((c.real, c.imag))
        pygame.draw.aalines(screen, [0, 233, 255], False, points)
        pygame.display.flip()
    pygame.image.save(screen, "dummy/slide_only_ppqq.png")
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False


