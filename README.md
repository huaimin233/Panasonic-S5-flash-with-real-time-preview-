# Panasonic DC-S5 Fn2 实时曝光预览与闪光同步

点按 Fn2 进入环境光曝光预览，可用取景画面判断背景曝光。调整光圈、快门速度或有效 ISO 档位时，实时预览保持。拍摄时半按对焦，再按到底即可正常引闪。也可从实时预览直接按到底拍摄。

| 适用范围 | 已验证条件 |
| --- | --- |
| 机身 | Panasonic DC-S5 一代（MC801），固件 2.9 |
| 部署环境 | Windows、Python 3、WinUSB，临时服务模式 USB `04DA:2370` |
| 测试闪光灯 | 神牛 Godox iT32 |
| 闪光模式 | 「强制闪光开」「强制闪光开/红眼降低」已通过实机测试 |
| 生命周期 | 补丁驻留在易失 RAM，拔电池冷启动后需重新部署 |

搭配 iT32 时，使用M档，机身菜单只有「强制闪光开」「强制闪光开/红眼降低」「强制闪光关」可选，只实测了这三种模式。其余两种闪光模式未实测，使用时可能出现预览或引闪异常。

在 ISO 51200 已到上限的情况下继续往增大方向拨，机身仍会退出实时预览。

在闪光灯未开启高速同步时，即使在实时预览状态下将快门速度调整至250以上，取消闪光预览时快门速度仍会自动变为250。

## 开始使用

先完成 [相机设置](USAGE.md#相机设置) 和 [USB 准备](USAGE.md#准备)，再在项目根目录用 PowerShell 运行。

```powershell
python .\deploy_shutter_preview.py deploy
```

看到 `Installation armed` 后拨一格 ISO，让机身发布一次设置。随后点按 Fn2，等待实时预览稳定后拍摄。

- [使用说明](USAGE.md) 涵盖服务模式、部署、状态检查、拍摄、回滚和构建。
- [地址与实现](docs/TECHNICAL.md) 记录固件入口、取景设置包、状态机、控制区和实测结果。

## 目录

| 路径 | 内容 |
| --- | --- |
| [`src/`](src/) | 三段 Thumb-2 汇编源码 |
| [`payloads/`](payloads/) | 已实测负载对应的三个预编译文件 |
| [`deploy_shutter_preview.py`](deploy_shutter_preview.py) | 部署、状态检查与回滚入口 |
| [`s5svc.py`](s5svc.py) | 随包提供的 Windows USB 服务模块 |
| [`build.ps1`](build.ps1) | 使用 GNU Arm Embedded 工具链重新构建 |
| [`check_pin_packet.py`](check_pin_packet.py) | Capstone 反汇编和 Unicorn 仿真检查 |

部署使用随包附带的 `s5svc.py` 与预编译文件。Windows 端需要 Python 和 WinUSB。开发依赖及复现方法见 [构建与仿真](USAGE.md#构建与仿真)。

## 免责声明
项目与 Panasonic 无关，纯属个人兴趣爱好。

## 致谢
[USER-HFC/Lumix_Tool](https://github.com/USER-HFC/Lumix_Tool) 提供工具箱、WinUSB 驱动安装、RAM 诊断等工具
