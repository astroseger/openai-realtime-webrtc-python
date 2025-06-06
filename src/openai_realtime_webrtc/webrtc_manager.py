import asyncio
import aiohttp
import json
import logging
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, MediaStreamTrack
from typing import Dict, Any, Optional
from .audio_output import AudioOutput

logger = logging.getLogger(__name__)


class WebRTCManager:
    OPENAI_API_BASE = "https://api.openai.com/v1"
    REALTIME_SESSION_URL = f"{OPENAI_API_BASE}/realtime/sessions"
    REALTIME_URL = f"{OPENAI_API_BASE}/realtime"

    def __init__(self):
        self.ice_servers = [
            RTCIceServer(
                urls=["stun:stun.l.google.com:19302"]
            )
        ]
        self.audio_output: Optional[AudioOutput] = None
        self.peer_connection: Optional[RTCPeerConnection] = None

    async def create_connection(self) -> RTCPeerConnection:
        """Create a new WebRTC peer connection."""
        config = RTCConfiguration(iceServers=self.ice_servers)
        self.peer_connection = RTCPeerConnection(config)

        # 初始化音频输出
        self.audio_output = AudioOutput()
        await self.audio_output.start()

        @self.peer_connection.on("track")
        async def on_track(track: MediaStreamTrack):
            logger.info(f"Received {track.kind} track from remote")
            if track.kind == "audio":
                @track.on("ended")
                async def on_ended():
                    if self.audio_output:
                        await self.audio_output.stop()

                while True:
                    try:
                        frame = await track.recv()
                        if self.audio_output and frame:
                            await self.audio_output.play_frame(frame)
                    except Exception as e:
                        logger.error(
                            f"Error processing remote audio frame: {str(e)}")
                        break

        @self.peer_connection.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state changed to: {self.peer_connection.connectionState}")
            if self.peer_connection.connectionState == "failed":
                if self.audio_output:
                    await self.audio_output.stop()

        @self.peer_connection.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(f"ICE connection state changed to: {self.peer_connection.iceConnectionState}")

        return self.peer_connection

    async def cleanup(self):
        """Clean up resources."""
        if self.audio_output:
            await self.audio_output.stop()
            self.audio_output = None

        if self.peer_connection:
            await self.peer_connection.close()
            self.peer_connection = None

    async def get_ephemeral_token(self, api_key: str, model: str) -> str:
        """Get an ephemeral token from OpenAI."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "voice": "alloy"  # 默认使用 alloy 声音
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.REALTIME_SESSION_URL,
                    headers=headers,
                    json=data
                ) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        raise Exception(
                            f"Failed to get ephemeral token: {error_text}")

                    result = await response.json()
                    return result["client_secret"]["value"]

        except Exception as e:
            logger.error(f"Failed to get ephemeral token: {str(e)}")
            raise

    async def connect_to_openai(
        self,
        api_key: str,
        model: str,
        offer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Connect to OpenAI's WebRTC endpoint using ephemeral token."""
        try:
            # 1. 获取临时token
            ephemeral_token = await self.get_ephemeral_token(api_key, model)

            # 2. 使用临时token建立WebRTC连接
            headers = {
                "Authorization": f"Bearer {ephemeral_token}",
                "Content-Type": "application/sdp"
            }

            # 3. 发送SDP offer并获取answer
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.REALTIME_URL}?model={model}",
                    headers=headers,
                    data=offer.sdp
                ) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        raise Exception(f"OpenAI WebRTC error: {error_text}")

                    sdp_answer = await response.text()
                    return {
                        "type": "answer",
                        "sdp": sdp_answer
                    }

        except Exception as e:
            logger.error(f"Failed to connect to OpenAI: {str(e)}")
            raise

    async def handle_ice_candidate(
        self,
        peer_connection: RTCPeerConnection,
        candidate: Dict[str, Any]
    ):
        """Handle incoming ICE candidate."""
        try:
            await peer_connection.addIceCandidate(candidate)
        except Exception as e:
            logger.error(f"Error adding ICE candidate: {str(e)}")
            raise
