import pathlib
import argparse
import sys
import json
from traceback import print_exc

from judge import JudgeManager, StaticMuriChecker
from majparse import NoteActionConverter, SimaiParser
from slides import init as init_slides
init_slides()

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(
            description="Simai Muri Detector"
        )
        parser.add_argument("-f", "--file", required=True, type=pathlib.Path)
        parser.add_argument("-o", "--output", default=None, type=pathlib.Path)
        parser.add_argument("-j", "--json", default=None, type=pathlib.Path)
        parser.add_argument("--first", default=0.0, type=float)
        namespace = parser.parse_args()

        if namespace.output is not None:
            sys.stdout = namespace.output.open(mode="w", encoding="u8")
        with namespace.file.open("r", encoding="u8") as f:
            chart_str = f.read()
        chart = SimaiParser.parse_simai_chart(chart_str, namespace.first)
        actions = NoteActionConverter.generate_action(chart)
        total = len(chart)
        print("谱面加载完成，共%d个note" % total)

        print("========== 静态检查 ==========")
        static_records = StaticMuriChecker.check(chart)
        record = {"static": static_records}

        print("========== 动态检查 ==========")
        judge_manager = JudgeManager()
        judge_manager.load_chart(chart, actions)
        while judge_manager.note_pointer < total or len(judge_manager.active_notes) > 0:
            judge_manager.tick(1)
        record["dynamic"] = judge_manager.muri_record_list

        if namespace.json is not None:
            with namespace.json.open("w", encoding="u8") as f:
                json.dump(record, f)

    except Exception as e:
        print_exc()
        input()


