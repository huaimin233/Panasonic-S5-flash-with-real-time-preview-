# 使用说明

## 相机设置

1. 打开机身菜单中的「始终显示预览」，设为 `ON`。
2. 进入「始终显示预览 → SET → 效果」，选择「A模式：光圈，M模式：光圈和快门速度」。
3.打开Fn按键设置，将Fn2设置为「OFF无设置」或「OFF关（禁用按住）」。

## 准备

1. 确认机身为 Panasonic DC-S5 一代（MC801），固件为 2.9。部署脚本会校验已知指令字节。
2. 关机，按住回放键与 AF/AE LOCK 键并开机，随后通过 USB 连接 Windows 电脑。确认服务模式设备 ID 为 `04DA:2370`。
3. 首次连接可用 Zadig 给 `04DA:2370` 设备绑定 WinUSB。若找不到设备，可在 Zadig 开启 `Options → List All Devices` 后核对设备 ID。
4. 在项目根目录打开 PowerShell，确认 `python` 可用。验证环境使用 Python 3.12。部署脚本默认加载项目根目录随附的 `s5svc.py`。

```powershell
python .\deploy_shutter_preview.py status
```

随附的 `s5svc.py` 来自实测使用的 LumixTool 0.3.1 Windows 环境，使用 Python 标准库和 Windows 的 WinUSB。此前配置过 `LUMIX_S5SVC` 的用户，可以在当前 PowerShell 运行 `Remove-Item Env:LUMIX_S5SVC -ErrorAction SilentlyContinue`，切回随包版本。

## 部署

```powershell
python .\deploy_shutter_preview.py deploy
```

看到 `Installation armed` 后，在机身上实际改变一格 ISO，等待固件发布一次设置。脚本会校验代码回读及调度计数增长。成功时可看到以下值。

| 字段 | 运行状态 |
| --- | --- |
| `Installer state` | `3`，机身内安装动作完成 |
| `dispatcher` | `bef4dcbe` |
| `Settings sender` | `6df798b5` |
| `tick` | 连续查询时增长，状态输出显示计数低 16 位，可能回绕 |

`status` 为只读查询。若安装等待超时，先拨到有效的相邻 ISO 档位，再用 `status` 查询。若服务端连接断开，唤醒或重新进入服务模式后先查询当前状态。入口字节未识别时，应核对机型、固件和旧补丁状态。迁移自早期试验版本时，可拔电池冷启动后重新部署。

## 拍摄

1. 选用「强制闪光开」，确认外接闪光灯已就绪。实机测试使用神牛 Godox iT32，模式范围见 [项目首页](README.md)。
2. 点按 Fn2 并松手，等实时预览稳定后构图。可拨动光圈、快门速度与有效 ISO 档位。
3. 半按对焦，再按到底拍摄。也可直接按到底。半按时画面可恢复普通闪光取景。
4. 要手动退出实时预览，再点一次 Fn2。

`Preview=0` 为普通取景，`1` 为环境光设置正在应用，`2` 为实时预览已应用。Fn2 松开后，程序约用四分之一秒收集机身的设置应用确认。ISO 51200 到顶后继续往增大方向拨会退出实时预览。

## 回滚

先退出实时预览，然后运行以下命令。看到 `Removal armed` 后在机身改变一格 ISO，让固件处理回滚请求。

```powershell
python .\deploy_shutter_preview.py rollback
python .\deploy_shutter_preview.py status
```

回滚后的入口字节为 `dispatcher=2de9fc41` 和 `Settings sender=95f8840a`。三个负载位于易失 RAM，拔电池冷启动也会清除当前补丁。

## 构建与仿真

项目附带预编译文件。需要重建时，将 GNU Arm Embedded 工具链加入 `PATH` 后运行构建脚本，或用 `-ToolchainBin` 指定工具链的 `bin` 目录。原版本使用 xPack GNU Arm Embedded GCC 15.2.1，验证时重建了字节一致的三个负载。

```powershell
.\build.ps1
# 或指定工具链目录
.\build.ps1 -ToolchainBin 'C:\path\to\arm-toolchain\bin'
```

构建产物写入 `payloads/`，中间文件在 `.build/`。可用 `-OutputDirectory` 将重建产物写到另一目录以比对。

```powershell
python -m pip install -r .\requirements-dev.txt
python .\check_pin_packet.py
```

仿真覆盖 Fn2 状态转换、光圈／快门速度／ISO 更新、快门事件优先、闪光命令保留及原指令续接。仿真可以离线完成。固件入口及地址定义见 [地址与实现](docs/TECHNICAL.md)。
