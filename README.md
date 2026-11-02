# 色標識の認識に応じたロボットアームの条件付き搬送

Gazeboのカメラ画像から赤・青の標識を分類し、ROS 2経由でCRANE+ V2の動作を切り替えるデモ。青なら待機、赤なら保存済みの計画軌道で箱を把持・搬送・配置。

## 実行方法

1. [環境構築](docs/setup.md)：M1 Mac、Colima / Docker、ROS 2 Humble、Gazebo Fortress。
2. [デモ手順](docs/demo.md)：カメラを起動し、青→赤の順に動作を確認。
3. 問題がある場合は[トラブルシューティング](docs/troubleshooting.md)を参照。

## 処理の流れ

```text
Gazeboカメラ → ros_gz_bridge → camera_ai.py + classifier_core.py
  → /pai/sort_command → ai_guided_replay_v2.py
    → 青：待機
    → 赤：replay_pick_place.py → CRANE+ V2による箱の搬送
```

## ファイルの役割

| パス | 役割 |
|---|---|
| `PAI_gazebo_camera/crane_plus_camera.launch.py` / `table_camera.sdf` | Gazebo・ロボット・MoveIt 2の起動 |
| `PAI_gazebo_camera/models/` | カメラと赤・青の標識モデル |
| `PAI_gazebo_camera/scripts/bridge_camera.sh` | Gazebo画像をROS 2へ転送 |
| `PAI_gazebo_camera/camera_ai.py` / `classifier_core.py` | 色領域の抽出とGaussian Naive Bayesによる分類 |
| `PAI_gazebo_camera/preview_camera.py` | カメラ画像を保存して確認 |
| `PAI_gazebo_camera/tests/` | 画像処理の確認用テスト |
| `pai_record_color.sh` | カメラの配置と色標識の切り替え |
| `ai_guided_replay_v2.py` | 判定の待受と動作選択 |
| `replay_pick_place.py` / `pick_place_trajectories.json` | 保存済み13区間の計画軌道を再生 |
| [sample/camera_snapshot.png](sample/camera_snapshot.png) | 保存済みのカメラ画像サンプル |

認識対象の標識と搬送する箱は別物である。標識の切り替えと分類プログラムの起動は手動で行う。軌道再生中の経路再計画は行わないため、記録時と同じ初期状態のGazeboシーンを使う。

実行時の画像（`camera_snapshot.png` / `.ppm`）とイベントログ（`pai_demo_events.jsonl`）はルートに生成され、Git管理対象外。`sample/`の保存画像は上書きしない。
