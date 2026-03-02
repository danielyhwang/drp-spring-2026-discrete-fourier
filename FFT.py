import math

def FFT(signal, inverse=False):
    """
    Recursive PM DIT FFT for arbitrary-length signals from the textbook.
    Input is zero-padded to the next power of 2.

    Parameters:
        signal:  list of real or complex values (time domain if forward,
                 frequency domain if inverse)
        inverse: if True, computes the IFFT (normalised by 1/N)

    Returns:
        list of complex values
    """
    n = len(signal)

    # Pad to the next power of 2
    m = 1
    while m < n:
        m <<= 1
    padded = list(signal) + [0] * (m - n)

    result = _fft(padded, inverse)

    if inverse:
        result = [x / m for x in result]

    return result


def _fft(signal, inverse):
    n = len(signal)
    if n == 1:
        return [complex(signal[0])]

    sign = 1 if inverse else -1
    even = _fft(signal[0::2], inverse)
    odd  = _fft(signal[1::2], inverse)

    # Twiddle factors  e^(sign * 2πik/n) = cos(2πk/n) + sign*i*sin(2πk/n)
    w = [complex(math.cos(2 * math.pi * k / n), sign * math.sin(2 * math.pi * k / n))
         for k in range(n // 2)]

    return (
        [even[k] + w[k] * odd[k] for k in range(n // 2)] +
        [even[k] - w[k] * odd[k] for k in range(n // 2)]
    ) 


x = [0,1,0,1,0,1]
print(FFT(x))