#!/usr/bin/env python3
"""pregen — デモ前にバックアップ用ゲームを数本作り溜める。

デモは「その場でライブ生成」が主役だが、万一の生成失敗に備えて games/ に
数本仕込んでおくと、フォールバックで必ずゲームを授与できる(2本デモの保険)。

GX10 のメモリを生成に専念できる状態(=Claude Code を落とした後)で実行すると速い。

使い方:
  python3 pregen.py            # 代表的な数パターンを生成
  python3 pregen.py 6          # 個数指定
"""
import sys
import time

import genfast
import server

# 代表的な遊び味の組み合わせ（多様性重視）
COMBOS = [
    ["a", "a", "a", "a", "a", "a"],  # スコア×破壊×高速×増殖×一掃×加速
    ["b", "b", "b", "b", "b", "b"],  # タイム×避け×思考×制約×回避×増量
    ["a", "b", "a", "a", "b", "a"],  # スコア×避け×高速×増殖×回避×加速
    ["b", "a", "a", "b", "a", "b"],  # タイム×破壊×高速×制約×一掃×増量
    ["a", "a", "b", "a", "a", "b"],  # スコア×破壊×思考×増殖×一掃×増量
    ["b", "b", "a", "b", "b", "a"],  # タイム×避け×高速×制約×回避×加速
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(COMBOS)
    genfast.prewarm()
    for i, ans in enumerate(COMBOS[:n], 1):
        key = server.type_key(ans)
        spec = server.compose_spec(ans)
        t = time.time()
        r = genfast.generate(spec)
        if r["issues"]:
            print(f"[{i}/{n}] {key}: FAILED {r['issues']}")
            continue
        gid = server._save_game(key, r["html"], r["spec"], r["title"])
        print(f"[{i}/{n}] {key}: {r['title']} ({len(r['html'])}B, {round(time.time()-t)}s) -> {gid}")
    print("pregen done.")


if __name__ == "__main__":
    main()
