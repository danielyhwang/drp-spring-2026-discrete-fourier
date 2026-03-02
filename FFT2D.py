import FFT
def FFT2D(image, inverse=False):
    """
    2D FFT by applying 1D FFT to rows and then columns.

    Parameters:
        image: 2D list of real or complex values (spatial domain if forward,
               frequency domain if inverse)
        inverse: if True, computes the IFFT (normalised by 1/(M*N))
    Output:
        2D list of complex values
    """
    # Apply 1D FFT to each row
    intermediate = [FFT.FFT(row, inverse) for row in image]

    # Transpose to apply 1D FFT to columns
    transposed = list(zip(*intermediate))

    # Apply 1D FFT to each column
    final = [FFT.FFT(col, inverse) for col in transposed]

    return [list(row) for row in zip(*final)]  # Transpose back to original orientation