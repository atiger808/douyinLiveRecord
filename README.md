## 声明：本代码库所有代码均只用于学习研究交流，严禁用于包括但不限于商业谋利、破坏系统、盗取个人信息等不良不法行为，违反此声明使用所产生的一切后果均由违反声明使用者承担。

## 侵权或涉及相关利益请联系作者：[知乎](https://www.zhihu.com/people/187927f4a5ab4cc21cdad3beedbbd148)、[抖音](https://www.douyin.com/user/MS4wLjABAAAAPgc1if5_Uap-mnitkVf1RBnSgFW65l8iBdN9uSuGs7A?from_tab_name=main)、[邮箱](mailto:atiger0614@163.com)

> 2025年12月18日



# Douyin Live Recorder（抖音直播录制工具）

> 💡 一款基于 Python + Tkinter 的桌面端抖音直播录制工具，支持多任务并发录制、清晰度选择、自动错误提示和日志记录。

## ✨ 功能特性

- 🎥 **多直播间并发录制**：同时录制多个抖音直播间
- 🔍 **自动解析直播流**：输入直播间号或分享链接，自动获取可用清晰度（标清/高清/蓝光等）
- 🛠️ **增强版 ffmpeg 调用**：
  - 自动注入合法 `User-Agent` 和 `Referer`，避免 403 错误
  - 录制中断自动检测并提示（如：直播结束、流失效、网络异常）
- 🧹 **智能进程管理**：
  - 点击“全部停止”不仅停止当前任务，还会强制终止所有残留的 `ffmpeg.exe` 进程
  - 防止软件意外退出后后台录制仍在运行
- 📁 **录制文件管理**：
  - 自动按“标题_清晰度_时间”命名
  - 一键打开录制目录
- 📝 **日志系统**：
  - 所有操作、错误、状态自动记录到 `logs/app_YYYYMMDD.log`
- 🖥️ **跨平台兼容**：支持 Windows（需 `ffmpeg.exe`）



### 软件界面

<img src="images\F953C615-751C-4b84-AEFE-835BA016D5E6.png" alt="img" style="zoom:75%;" /> !





## 📦 安装与运行

### 前置依赖

- Python 3.8+
- `ffmpeg.exe`（[下载地址](https://www.gyan.dev/ffmpeg/builds/)）
- Windows 系统（推荐）

### 快速开始

1. 克隆仓库：
   ```bash
   git clone https://github.com/atiger808/douyinLiveRecord.git
   cd douyinLiveRecord
   ```

2. 将 `ffmpeg.exe` 放入 `bin/` 目录：

   ```
   douyinLiveRecord/
   ├── bin/
   │   └── ffmpeg.exe
   ├── douyinLiveRecord.py
   └── ...
   ```

   

3. 安装 Python 依赖：

   ```
   pip install -r requirements.txt
   ```

   

4. 运行程序：

   ```
   python douyinLiveRecord.py
   ```

   



### 打包为 EXE（可选）

```
pip install pyinstaller psutil
pyinstaller --onefile --add-data "bin;bin" douyinLiveRecord.py
```

## 📁 项目结构

```
douyinLiveRecord/
├── bin/                  # ffmpeg 可执行文件
├── recordings/           # 录制视频自动保存目录
├── logs/                 # 自动生成的日志文件
├── douyinLiveRecord.py   # 主程序
├── tools.py              # 直播流解析模块（需自行实现）
├── config.py             # 配置文件
└── README.md
```

## ⚠️ 注意事项

- 抖音直播流地址具有时效性（通常 1~2 小时），若录制中途 403，需重新获取流地址。
- 本工具仅用于个人学习与研究，请遵守抖音平台规则，勿用于商业或违规用途。
- `tools.py` 中的 `get_stream_qualities()` 需自行实现（建议基于 WebSocket 实时获取有效流地址）。

## 📜 许可证

MIT License



###### WX: shuaibin99，请我喝一杯咖啡吧(*￣︶￣)

<img src="images/wechat-qrcode.jpg" alt="1766031980889" style="zoom: 100%;" />