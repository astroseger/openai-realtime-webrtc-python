import asyncio
import logging
from typing import Optional, Callable, Dict, Any
import sounddevice as sd
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from .audio_handler import AudioHandler, SAMPLE_RATE, CHANNELS
from .audio_output import FRAME_DURATION_MS
from .webrtc_manager import WebRTCManager
from typing import Deque, Dict, Tuple
import json
import uuid

logger = logging.getLogger(__name__)


def get_default_audio_info() -> Tuple[Dict, Dict]:
    """获取默认音频设备的信息"""
    try:
        input_device = sd.query_devices(kind='input')
        output_device = sd.query_devices(kind='output')

        logger.info("Default Input Device:")
        logger.info(f"  Name: {input_device['name']}")
        logger.info(f"  Channels: {input_device['max_input_channels']}")
        logger.info(f"  Sample Rate: {input_device['default_samplerate']}Hz")

        logger.info("Default Output Device:")
        logger.info(f"  Name: {output_device['name']}")
        logger.info(f"  Channels: {output_device['max_output_channels']}")
        logger.info(f"  Sample Rate: {output_device['default_samplerate']}Hz")

        return input_device, output_device
    except Exception as e:
        logger.error(f"Error getting audio device info: {str(e)}")
        raise


class OpenAIWebRTCClient:
    def __init__(
        self,
        api_key: str,
        model: str = "whisper-1",
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        frame_duration: int = FRAME_DURATION_MS
    ):
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration = frame_duration

        self.audio_handler = AudioHandler(
            sample_rate=sample_rate,
            channels=channels,
            frame_duration=frame_duration
        )
        self.webrtc_manager = WebRTCManager()

        self.peer_connection: Optional[RTCPeerConnection] = None
        self.is_streaming = False
        self.on_transcription: Optional[Callable[[str], None]] = None
        # data channel for sending/receiving Realtime API events
        self.data_channel: Optional[Any] = None
        # callback for incoming or sent events (session, responses, etc.)
        self.on_event: Optional[Callable[[Dict[str, Any]], None]] = None

    async def start_streaming(self):
        """Start the audio streaming session."""
        if self.is_streaming:
            logger.warning("Streaming is already active")
            return

        try:
            # Initialize WebRTC connection
            self.peer_connection = await self.webrtc_manager.create_connection()

            # Add audio track for microphone input
            audio_track = self.audio_handler.create_audio_track()
            self.peer_connection.addTransceiver(audio_track, "sendrecv")
            # Create data channel for sending/receiving Realtime API events
            self.data_channel = self.peer_connection.createDataChannel("oai-events")
            self.data_channel.on("open", self._on_data_channel_open)
            self.data_channel.on("message", self._on_data_channel_message)

            # Create and set local description
            offer = await self.peer_connection.createOffer()
            await self.peer_connection.setLocalDescription(offer)

            # Connect to OpenAI's WebRTC endpoint
            response = await self.webrtc_manager.connect_to_openai(
                self.api_key,
                self.model,
                offer
            )

            # Set remote description
            answer = RTCSessionDescription(
                sdp=response["sdp"],
                type=response["type"]
            )
            await self.peer_connection.setRemoteDescription(answer)

            self.is_streaming = True
            logger.info("Streaming started successfully")

        except Exception as e:
            logger.error(f"Failed to start streaming: {str(e)}")
            await self.stop_streaming()
            raise

    async def stop_streaming(self):
        """Stop the audio streaming session."""
        if not self.is_streaming:
            return

        try:
            await self.webrtc_manager.cleanup()
            await self.audio_handler.stop()
            self.is_streaming = False
            logger.info("Streaming stopped successfully")

        except Exception as e:
            logger.error(f"Error while stopping streaming: {str(e)}")
            raise

    async def pause_streaming(self):
        """Pause the audio streaming."""
        if not self.is_streaming:
            return
        await self.audio_handler.pause()

    async def resume_streaming(self):
        """Resume the audio streaming."""
        if not self.is_streaming:
            return
        await self.audio_handler.resume()

    def set_audio_device(self, device_id: str):
        """Set the audio input device."""
        self.audio_handler.set_device(device_id)

    def _handle_transcription(self, text: str):
        """Handle incoming transcription."""
        if self.on_transcription:
            self.on_transcription(text)

    def _on_data_channel_open(self):
        logger.info("Data channel open")

    def _on_data_channel_message(self, message: Any):
        """Handle incoming JSON events from the data channel."""
        try:
            event = json.loads(message)
        except Exception:
            logger.warning(f"Received non-JSON message on data channel: {message}")
            return
        if self.on_event:
            self.on_event(event)

    def send_client_event(self, event: Dict[str, Any]) -> None:
        """Send a client event over the data channel."""
        if not self.data_channel or getattr(self.data_channel, 'readyState', None) != 'open':
            logger.error("Failed to send message - data channel not available")
            return
        # assign event_id if missing
        event_id = event.get('event_id') or str(uuid.uuid4())
        event['event_id'] = event_id
        self.data_channel.send(json.dumps(event))
        # echo sent event to on_event callback
        if self.on_event:
            self.on_event(event)

    def send_text_message(self, text: str) -> None:
        """Send a text message to the model (conversation.item.create + response.create)."""
        msg = {
            'type': 'conversation.item.create',
            'item': {
                'type': 'message',
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': text}
                ],
            },
        }
        self.send_client_event(msg)
        self.send_client_event({'type': 'response.create'})
