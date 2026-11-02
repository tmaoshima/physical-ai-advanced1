# トラブルシューティング

[READMEに戻る](../README.md) · [デモ手順](demo.md)

Gazebo → ROS 2 → カメラ → 分類 → 動作の順に確認する。

| 症状 | 確認・対応 |
|---|---|
| noVNCに接続できない | Macで`docker ps`と`docker exec ai_robot_book supervisorctl status`を確認。接続先は`http://localhost:6080/` |
| `IP_MULTICAST_IF failed`などのDDSエラー | A〜Dすべてで`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`と`ROS_LOCALHOST_ONLY=1`を設定して起動し直す |
| `/joint_states`が届かない | `ros2 control list_controllers`で3つのコントローラが`active`か確認。`ros2 topic echo /clock --once`で時刻も確認 |
| Gazeboが起動時に落ちる | MacでColimaとRosettaの状態を確認。[環境構築](setup.md)を参照 |
| Gazebo側に画像Topicがない | `ign topic -l`に`/pai/camera/image`があるか確認。AのSensors・描画エラーと、Dの`pai_record_color.sh blue`の成否を確認 |
| 画像Topicはあるが画像取得がタイムアウトする | Cのブリッジが動作中か確認。`ros2 topic info -v /pai/camera/image`でROS側の配信を確認 |
| 画像の中央に色標識が映らない | Dで`pai_record_color.sh blue`を再実行して画像を確認。改善しない場合はGazeboを初期状態から再起動 |
| PNGが作られない | Pillowがない場合はPPMのみ保存されるため、`camera_snapshot.ppm`を確認 |
| 画像が届くが分類を拒否する | スナップショットの標識・照明・位置を確認。曖昧な色や背景のみの画像は分類しない実装 |
| 赤判定でも動かない | Bが`waiting_for_ai`で待受中か、900秒の制限時間が切れていないか確認。軌道JSONと`replay_pick_place.py`の存在も確認 |
| 動くが箱を搬送できない | Gazeboを再起動し、箱とアームを記録時の初期状態に戻す。他の制御ノードが動いていないか確認 |

## ロボット制御側のイベント

| イベント | 意味 |
|---|---|
| `waiting_for_ai` | 判定を待受中 |
| `held_blue_no_motion` | 青を受信し、軌道を送らず待機 |
| `executing_red` | 赤を受信し、軌道再生を開始 |
| `completed_red_motion` | 全13区間の軌道Actionが完了 |
| `failed_red_motion` | 再生プロセスが失敗。Bの直前のエラーを確認 |
| `timeout_no_red` | 待受時間内に赤判定が届かなかった |

