import asyncio
import os
import logging
import json
from dotenv import load_dotenv
from openai_realtime_webrtc import OpenAIWebRTCClient
from openai_realtime_webrtc.audio_handler import SAMPLE_RATE, CHANNELS, DTYPE

# Set log level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


async def main():
    # Get API key from environment variable
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    print(f"Audio Configuration:")
    print(f"Sample Rate: {SAMPLE_RATE} Hz")
    print(f"Channels: {CHANNELS} (Mono)")
    print(f"Bit Depth: {DTYPE} (16-bit)")

    # Create client instance with tool definitions (will be registered automatically)
    client = OpenAIWebRTCClient(
        api_key=api_key,
        model="gpt-4o-realtime-preview-2024-12-17",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        frame_duration=20,
        tools=[
            {
                "type": "function",
                "name": "display_color_palette",
                "description": "Call this function when a user asks for a color palette.",
                "parameters": {
                    "type": "object",
                    "strict": True,
                    "properties": {
                        "theme": {
                            "type": "string",
                            "description": "Description of the theme for the color scheme."
                        },
                        "colors": {
                            "type": "array",
                            "description": "Array of five hex color codes based on the theme.",
                            "items": {"type": "string", "description": "Hex color code"}
                        },
                    },
                    "required": ["theme", "colors"],
                },
            }
        ]
    )

    # Define transcription callback
    def on_transcription(text: str):
        print(f"Transcription: {text}")

    client.on_transcription = on_transcription

    # Handle client and server events over the data channel
    def on_event(event: dict):
        print(f"Event: {event}")
        # handle function_call outputs
        if event.get("type") == "response.done" and event.get("response", {}).get("output"):
            for output in event["response"]["output"]:
                if output.get("type") == "function_call" and output.get("name") == "display_color_palette":
                    args = json.loads(output.get("arguments", "{}"))
                    print("--- Color Palette Tool Output ---")
                    print(f"Theme: {args.get('theme')}")
                    for color in args.get('colors', []):
                        print(color)
                    # follow-up: ask for feedback
                    asyncio.create_task(delayed_feedback())

    client.on_event = on_event

    async def delayed_feedback():
        await asyncio.sleep(0.5)
        client.send_client_event({
            "type": "response.create",
            "response": {
                "instructions": (
                    "ask for feedback about the color palette - don't repeat "
                    "the colors, just ask if they like the colors."
                ),
            },
        })

    try:
        # Start streaming
        print("Starting audio streaming... Press Ctrl+C to stop")
        await client.start_streaming()

        # Keep the connection alive
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping streaming...")
    except Exception as e:
        logger.error(f"Error during streaming: {str(e)}")
    finally:
        # Clean up
        await client.stop_streaming()

if __name__ == "__main__":
    asyncio.run(main())
