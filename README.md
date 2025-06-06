# openai-realtime-webrtc-python

基于WebRTC的OpenAI实时音频流通信Python库，支持与OpenAI Realtime API进行实时音频交互。

## 功能特点

- 基于WebRTC的实时音频通信
- 支持OpenAI Realtime API
- 自动音频设备管理
- 自动采样率转换
- 低延迟音频传输
- 音频缓冲管理
- 支持暂停/恢复流传输



## 安装要求

- Python 3.7+
- 支持的操作系统：Windows, macOS, Linux
- 音频设备支持

### 依赖项
```bash
sounddevice>=0.4.6
numpy>=1.24.0
websockets>=11.0.3
openai>=1.3.0
aiohttp>=3.8.5
pyaudio>=0.2.13
python-dotenv>=1.0.0
aiortc>=1.6.0
scipy>=1.12.0
```

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/openai-realtime-webrtc-python.git
cd openai-realtime-webrtc-python
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS

```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 开发模式安装：
```bash
pip install -e .
```

## 使用方法

1. 设置环境变量：
创建 `.env` 文件并添加您的OpenAI API密钥：
```bash
OPENAI_API_KEY=your-api-key-here
```

2. 基本使用示例：
```python
import asyncio
from openai_realtime_webrtc import OpenAIWebRTCClient

async def main():
    # 创建客户端实例
    client = OpenAIWebRTCClient(
        api_key="your-api-key",
        model="gpt-4o-realtime-preview-2024-12-17",
        tools=[
            {
                "name": "display_color_palette",
                "description": "Displays the colors palette",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "colors_hex": {
                            "type": "string",
                            "description": "Comma-separated list of color hex values"
                        }
                    },
                    "required": ["colors_hex"]
                }
            }
        ]
    )

    # 定义转录回调
    def on_transcription(text: str):
        print(f"转录文本: {text}")

    client.on_transcription = on_transcription

    # 定义事件回调（可用于工具/函数调用）
    def on_event(event: dict):
        print(f"Event: {event}")

    client.on_event = on_event

    try:
        # 开始流式传输
        await client.start_streaming()
        # 保持连接
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # 停止流式传输
        await client.stop_streaming()

if __name__ == "__main__":
    asyncio.run(main())
```

要在初始化时添加 Tools（函数调用）支持，可向构造函数传递 `tools` 列表，客户端将在会话创建后自动发送 `session.update`（将 `tools` 和 `tool_choice` 嵌入到 `session` 字段中）注册这些工具。
有关处理函数调用事件（如发起后续请求）的示例，请参阅 `examples/basic_streaming.py`。


3. 运行示例：
```bash
python examples/basic_streaming.py
```




## 贡献指南

欢迎提交 Pull Requests 和 Issues！

## 许可证

MIT License

## 更新日志

### v0.1.0
- 初始版本发布
- 实现基本的WebRTC音频流功能
- 支持OpenAI Realtime API
- 自动音频设备管理
- 音频重采样支持
