# openai-realtime-webrtc-python

# A Python library for real-time audio streaming with the OpenAI Realtime API over WebRTC.

## Features

- Real-time audio communication over WebRTC
- Support for OpenAI Realtime API
- Automatic audio device management
- Automatic sample rate conversion
- Low-latency audio streaming
- Audio buffering management
- Pause/resume streaming support



## Requirements

- Python 3.7+
- Supported operating systems: Windows, macOS, Linux
- Audio device support

### Dependencies
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

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/openai-realtime-webrtc-python.git
cd openai-realtime-webrtc-python
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS

```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install in development mode:
```bash
pip install -e .
```

## Usage

1. Set up environment variables:
Create a `.env` file and add your OpenAI API key:
```bash
OPENAI_API_KEY=your-api-key-here
```

2. Basic example:
```python
import asyncio
from openai_realtime_webrtc import OpenAIWebRTCClient

async def main():
    # Create client instance
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

    # Define transcription callback
    def on_transcription(text: str):
        print(f"Transcription: {text}")

    client.on_transcription = on_transcription

    # Define event callback (for tools/function calling)
    def on_event(event: dict):
        print(f"Event: {event}")

    client.on_event = on_event

    try:
        # Start streaming
        await client.start_streaming()
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Stop streaming
        await client.stop_streaming()

if __name__ == "__main__":
    asyncio.run(main())
```

To add support for tools (function calling) at initialization, pass a `tools` list to the constructor. The client will automatically send a `session.update` (embedding `tools` and `tool_choice` in the `session` field) on session creation to register these tools.
For an example of handling function call events (e.g. for follow-up requests), see `examples/basic_streaming.py`.


3. Run the example:
```bash
python examples/basic_streaming.py
```




## Contributing
Pull requests and issues are welcome!

## License

MIT License

## Changelog

### v0.1.0
- Initial release
- Implement basic WebRTC audio streaming functionality
- Support for OpenAI Realtime API
- Automatic audio device management
- Audio resampling support
