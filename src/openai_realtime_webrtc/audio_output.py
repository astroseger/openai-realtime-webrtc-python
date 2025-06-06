import sounddevice as sd
import numpy as np
import asyncio
import logging
from typing import Optional, Deque, Dict, Tuple
from collections import deque
from av import AudioFrame
from scipy import signal

logger = logging.getLogger(__name__)


# Fixed audio configuration
FRAME_DURATION_MS = 20  # WebRTC typically uses 20ms frames
DEFAULT_SAMPLE_RATE = 48000  # Fixed at 48kHz
DEFAULT_CHANNELS = 2    # Fixed to mono
# 960 samples for 20ms at 48kHz
DEFAULT_BLOCK_SIZE = int(DEFAULT_SAMPLE_RATE * FRAME_DURATION_MS / 1000)

DEFAULT_DTYPE = np.int16


class AudioOutput:
    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        dtype: str = DEFAULT_DTYPE,
        block_size: int = DEFAULT_BLOCK_SIZE,
        max_queue_size: int = 50,
        device: Optional[str] = None
    ):
        # Enforce fixed configuration
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.block_size = block_size
        self.max_queue_size = max_queue_size
        self.device = device

        # Calculate buffer sizes
        self.samples_per_frame = int(
            DEFAULT_SAMPLE_RATE * FRAME_DURATION_MS / 1000)

        self.stream: Optional[sd.OutputStream] = None
        self.is_playing = False
        self._queue = asyncio.Queue()
        self._buffer: Deque[np.ndarray] = deque(maxlen=max_queue_size)
        self._task = None
        self._remaining_data = None

    async def start(self):
        """Start audio output stream."""
        if self.is_playing:
            return

        try:
            # Enforce fixed configuration but preserve device's native sample rate to avoid resampling
            self.stream = sd.OutputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=self.channels,  # Force mono
                dtype=self.dtype,        # Force 16-bit
                blocksize=int(self.block_size),
                callback=self._audio_callback,
                prime_output_buffers_using_stream_callback=True
            )
            self.stream.start()
            self.is_playing = True
            self._task = asyncio.create_task(self._process_audio())

        except Exception as e:
            logger.error(f"Failed to start audio output: {str(e)}")
            raise

    async def stop(self):
        """Stop audio output."""
        if not self.is_playing:
            return

        try:
            self.is_playing = False
            if self._task:
                self._task.cancel()
                self._task = None

            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            # Clear buffer
            self._buffer.clear()
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            logger.info("Audio output stopped")
        except Exception as e:
            logger.error(f"Error stopping audio output: {str(e)}")

    def _audio_callback(self, outdata, frames, time, status):
        """Callback for sounddevice output stream."""
        if status:
            logger.warning(f"Audio output status: {status}")

        try:
                # Fetch data from buffer
            if len(self._buffer) > 0:
                data = self._buffer.popleft()
                print(f"=========== data shape: {data.shape}, dtype: {data.dtype}")
                outdata[:] = data.reshape(outdata.shape)
            else:
                # If buffer is empty, output silence
                outdata.fill(0)
        except Exception as e:
            logger.error(f"Error in audio callback: {str(e)}")
            outdata.fill(0)

    async def _process_audio(self):
        """Process audio frames from the queue and maintain the buffer."""
        try:
            while self.is_playing:
                # If buffer is not full, fetch new data from queue
                if len(self._buffer) < self.max_queue_size:
                    try:
                        # Non-blocking fetch with 0.1s timeout
                        data = await asyncio.wait_for(self._queue.get(), 0.1)
                        self._buffer.append(data)
                    except asyncio.TimeoutError:
                        # On timeout, continue loop
                        continue
                    except asyncio.QueueEmpty:
                        # If queue is empty, continue loop
                        continue
                    except Exception as e:
                        logger.error(
                            f"Error getting data from queue: {str(e)}")
                else:
                    # If buffer is full, wait briefly
                    await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logger.info("Audio processing task cancelled")
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")

    async def play_frame(self, frame: AudioFrame):
        """Queue an audio frame for playback."""
        try:
            # Convert AudioFrame to numpy array

            audio_data = frame.to_ndarray()

            # Ensure correct data type
            if audio_data.dtype != self.dtype:
                audio_data = audio_data.astype(self.dtype)

            # If queue is full, remove oldest frame
            if self._queue.qsize() >= self.max_queue_size:
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            # Queue the audio data
            await self._queue.put(audio_data)
        except Exception as e:
            logger.error(f"Error queueing audio frame: {str(e)}")
            raise
