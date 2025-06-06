import asyncio
import numpy as np
import sounddevice as sd
from aiortc.mediastreams import MediaStreamTrack, MediaStreamError
from av import AudioFrame
import logging
from typing import Optional
from scipy import signal


logger = logging.getLogger(__name__)

# Export constants for external use
SAMPLE_RATE = 48000
CHANNELS = 1
DTYPE = np.int16


class AudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, audio_handler):
        super().__init__()
        self._audio_handler = audio_handler
        self._queue = asyncio.Queue()
        self._task = None

    async def recv(self):
        """Receive the next frame of audio data."""
        if self._task is None:
            self._task = asyncio.create_task(
                self._audio_handler.start_recording(self._queue))

        try:
            frame = await self._queue.get()
            return frame
        except Exception as e:
            logger.error(f"Error receiving audio frame: {str(e)}")
            raise MediaStreamError("Failed to receive audio frame")


class AudioHandler:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        frame_duration: int = 20,
        dtype: np.dtype = DTYPE,
        device: Optional[str] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration = frame_duration
        self.dtype = dtype
        self.device = device

        # Calculate frame size
        self.frame_size = int(sample_rate * frame_duration / 1000)

        self.stream = None
        self.is_recording = False
        self.is_paused = False
        self._loop = None
        self._pts = 0  # Add this to track the pts

    def create_audio_track(self) -> AudioTrack:
        """Create a new audio track for WebRTC streaming."""
        return AudioTrack(self)

    async def start_recording(self, queue: asyncio.Queue):
        """Start recording audio from the input device."""
        if self.is_recording:
            return

        self.is_recording = True
        self.is_paused = False
        self._loop = asyncio.get_running_loop()
        self._pts = 0  # Reset pts when starting recording

        try:
            def callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio input status: {status}")
                if not self.is_paused:
                    # Ensure input data has the correct format
                    audio_data = indata.copy()

                    # Ensure correct data type
                    if audio_data.dtype != self.dtype:
                        if self.dtype == np.int16:
                            audio_data = (
                                audio_data * 32767).astype(self.dtype)
                        else:
                            audio_data = audio_data.astype(self.dtype)

                    # Create AudioFrame with incrementing pts
                    frame = AudioFrame(
                        samples=len(audio_data),
                        layout='mono',
                        format='s16',  # 16-bit signed integer
                    )
                    frame.rate = self.sample_rate
                    frame.pts = self._pts
                    self._pts += len(audio_data)  # Increment pts by frame size

                    frame.planes[0].update(audio_data.tobytes())

                    asyncio.run_coroutine_threadsafe(
                        queue.put(frame),
                        self._loop
                    )

            self.stream = sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype=self.dtype,
                blocksize=self.frame_size,
                callback=callback
            )
            self.stream.start()

            while self.is_recording:
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in audio recording: {str(e)}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop recording audio."""
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    async def pause(self):
        """Pause audio recording."""
        self.is_paused = True

    async def resume(self):
        """Resume audio recording."""
        self.is_paused = False

    def set_device(self, device_id: str):
        """Set the audio input device."""
        self.device = device_id
        if self.stream:
            # Restart the stream with new device
            self.stream.stop()
            self.stream.close()
            self.stream = None
