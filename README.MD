このリポジトリは、2026年6月13日（土）に開催された「DGX Spark ハッカソン」の成果物です。

**ゲーム神社** — 2択に答えて祈ると、ローカル LLM(gpt-oss) がその場でゲームを作って授けてくれる、神託型のゲーム生成体験。

## 動かし方

GX10（NVIDIA GB10）上で ollama に gpt-oss:120b / gpt-oss:20b がある前提。

```bash
# 1) 推奨: 両モデルを温めてから起動（120b設計+20b実装≈36s）
python3 server.py
#    → http://localhost:8770 をブラウザで開く

# 2) メモリが逼迫している時の確実フォールバック（20bのみ・14GB・約29s）
DESIGN_MODEL=gpt-oss:20b python3 server.py

# 別ホストの ollama に繋ぐ場合
OLLAMA_URL=http://<host>:11434 python3 server.py
```

操作は **矢印キー / Z / C のみ**：タイトルで Z → 2択を←→で選び Z → Z連打で祈る → 授かったゲームを遊ぶ → C で神社へ戻る。

## ドキュメント

- [設計仕様書（SSOT）](docs/spec.md) — 体験フロー・制約・生成戦略・GX10実測（付録B）
- [体験コンセプト](docs/concept.md)
- [Agent Game Team Prototype Spec](docs/agent-game-team-prototype.md)

## 構成

- `server.py` — 神社サーバ（祈り受付・授与API・静的配信）
- `genfast.py` — 高速ライブ生成（120b設計→20b実装、reasoning_effort=low で1分以内）
- `web/index.html` — 神社フロント（キー操作のみ）
