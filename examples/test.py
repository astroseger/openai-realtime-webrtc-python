import numpy as np
import av


def numpy_to_audioframe(array, sample_rate=48000):
    """
    Convert a Numpy array to a PyAV AudioFrame

    Parameters:
        array: numpy array of shape (960, 1) and dtype int16
        sample_rate: sample rate, default 48000Hz

    Returns:
        av.AudioFrame: PyAV AudioFrame object
    """
    # Create audio frame with correct format
    frame = av.AudioFrame(
        samples=len(array),          # number of samples
        layout='mono',               # mono
        format='s16',               # signed 16-bit integer
    )
    frame.rate = sample_rate
    frame.pts = 0

    # Ensure the array is one-dimensional
    if array.ndim == 2:
        array = array.squeeze()

    # Copy data into frame plane
    frame.planes[0].update(array.tobytes())

    return frame


# Example usage
array = np.random.randint(-32768, 32767, (960, 1), dtype=np.int16)
audio_frame = numpy_to_audioframe(array)
