import FFT2D

def bmp_parser(file_path, ost=False):
    # This function should read a BMP file and return the pixel data as a 2D array
    # Assumes for now that the BMP file is uncompressed and uses 24 bits per pixel (BGR format) or 32 bits per pixel (BGRA format)
    with open(file_path, 'rb') as f:
        # Read the BMP header and extract necessary information
        # For example, you might read the width, height, and pixel data offset
        # Then read the pixel data into a 2D array
        if (ost):
            f.seek(10)  # Move to the pixel data offset field in the BMP header
            # print(f.tell())
            data_offset = int.from_bytes(f.read(4), 'little')
            # print(data_offset)
            # print(f.tell())
            f.seek(18)  # Move to the width and height fields in the BMP header
            width = int.from_bytes(f.read(2), 'little')
            # print(f.tell())
            height = int.from_bytes(f.read(2), 'little')
            # print(f.tell())
            f.seek(24)  # Skip color planes (2 bytes) to reach bits per pixel
            bitsperpixel = int.from_bytes(f.read(2), 'little')
            # print(f.tell())
            f.seek(30)
            compression_method = int.from_bytes(f.read(4), 'little')
            # print(f.tell())
        else:
            f.seek(10)  # Move to the pixel data offset field in the BMP header
            data_offset = int.from_bytes(f.read(4), 'little')
            f.seek(18)  # Move to the width and height fields in the BMP header
            width = int.from_bytes(f.read(4), 'little')
            height = abs(int.from_bytes(f.read(4), 'little', signed=True)) #negative height indicates top-down bitmap
            f.seek(28)  # Move to the bits per pixel field in the BMP header
            bitsperpixel = int.from_bytes(f.read(2), 'little') 
            f.seek(30) 
            compression_method = int.from_bytes(f.read(4), 'little')
            # print(f.tell())  
        if compression_method != 0 and compression_method != 3:
            raise ValueError("Unsupported BMP compression method")
        f.seek(data_offset)
        # print(data_offset)
        pixel_data = []
        if (compression_method == 3):
            for y in range(height):
                row = []
                for x in range(width):
                    blue = f.read(1)[0]
                    green = f.read(1)[0]
                    red = f.read(1)[0]
                    alpha = f.read(1)[0]
                    row.append((red, green, blue, alpha))
                pixel_data.append(row)
        else:
            for y in range(height):
                row = []
                for x in range(width):
                    blue = f.read(1)[0]
                    green = f.read(1)[0]
                    red = f.read(1)[0]
                    row.append((red, green, blue))
                pixel_data.append(row)
        
        print(pixel_data)
        return pixel_data
        
def rgb_to_ycbcr(pixel_data):
    # This function should convert the RGB pixel data to YCbCr color space
    # The conversion can be done using the following formulas:
    # Y  = 0.299 * R + 0.587 * G + 0.114 * B
    # Cb = -0.168736 * R - 0.331264 * G + 0.5 * B + 128
    # Cr = 0.5 * R - 0.418688 * G - 0.081312 * B + 128
    if len(pixel_data) == 0 or len(pixel_data[0]) == 0:
        return []
    if len(pixel_data[0][0]) == 4:
        print("Converting RGBA to YCbCr; alpha channel will be ignored")
        alpha = True
    else:
        alpha = False
    ycbcr_data = []
    if alpha:
        for row in pixel_data:
            ycbcr_row = []
            for (r, g, b, a) in row:
                y = int(0.299 * r + 0.587 * g + 0.114 * b)
                cb = int(-0.168736 * r - 0.331264 * g + 0.5 * b + 128)
                cr = int(0.5 * r - 0.418688 * g - 0.081312 * b + 128)
                ycbcr_row.append((y, cb, cr))
            ycbcr_data.append(ycbcr_row)
    else:
        for row in pixel_data:
            ycbcr_row = []
            for (r, g, b) in row:
                y = int(0.299 * r + 0.587 * g + 0.114 * b)
                cb = int(-0.168736 * r - 0.331264 * g + 0.5 * b + 128)
                cr = int(0.5 * r - 0.418688 * g - 0.081312 * b + 128)
                ycbcr_row.append((y, cb, cr))
            ycbcr_data.append(ycbcr_row)
    print(ycbcr_data)
    return ycbcr_data

def interleaver(data_array):
    # This function should interleave the data in the 2D array according to the JPEG zig-zag pattern
    # The zig-zag pattern can be defined as follows for an 8x8 block:
    zigzag_order = [
        (0, 0), (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2),
        (2, 1), (3, 0), (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5),
        (1, 4), (2, 3), (3, 2), (4, 1), (5, 0), (6, 0), (5, 1), (4, 2),
        (3, 3), (2, 4), (1, 5), (0, 6), (0, 7), (1, 6), (2, 5), (3, 4),
        (4, 3), (5, 2), (6, 1), (7, 0), (7, 1), (6, 2), (5, 3), (4, 4),
        (3, 5), (2, 6), (1, 7), (2, 7), (3, 6), (4, 5), (5, 4), (6, 3),
        (7, 2), (7, 3), (6, 4), (5, 5), (4, 6), (3, 7), (4, 7), (5, 6),
        (6, 5), (7, 4), (7, 5), (6, 6), (5, 7), (6, 7), (7, 6), (7, 7)
    ]
    height = len(data_array)
    width = len(data_array[0]) if height > 0 else 0



    interleaved_data = []
    for coord in zigzag_order:
        x, y = coord
        if x < len(data_array) and y < len(data_array[0]):
            interleaved_data.append(data_array[x][y])
    print(interleaved_data)
    return interleaved_data

def make_block(data_array, block_size=8):
    # This function should divide the input data array into blocks of the specified size (e.g., 8x8)
    blocks = []
    for i in range(0, len(data_array), block_size):
        for j in range(0, len(data_array[0]), block_size):
            block = [row[j:j+block_size] for row in data_array[i:i+block_size]]
            blocks.append(block)
    print(blocks)
    return blocks

def quantization(block, luminance=True, quality=50):
    # This function should quantize an 8x8 block based on the specified quality factor
    # The quality factor can be used to scale the standard JPEG quantization matrix
    # Namely, a higher quality factor should result in a lower quantization step size 
    # (i.e., less aggressive quantization), while a lower quality factor should result 
    # in a higher quantization step size (i.e., more aggressive quantization)
    # Quality should usually be between 1 and 100, where 1 is the lowest quality (most aggressive quantization) and 100 is the highest quality (least aggressive quantization)
    # quality = 50 is standard

    standard_luminance_quantization_matrix = [
        [16, 11, 10, 16, 24, 40, 51, 61],
        [12, 12, 14, 19, 26, 58, 60, 55],
        [14, 13, 16, 24, 40, 57, 69, 56],
        [14, 17, 22, 29, 51, 87, 80, 62],
        [18, 22, 37, 56, 68,109,103, 77],
        [24, 35, 55, 64, 81,104,113, 92],
        [49, 64, 78, 87,103,121,120,101],
        [72, 92, 95, 98,112,100,103, 99]
    ]
    standard_chrominance_quantization_matrix = [
        [17, 18, 24, 47, 99, 99, 99, 99],
        [18, 21, 26, 66, 99, 99, 99, 99],
        [24, 26, 56, 99, 99, 99, 99, 99],
        [47, 66, 99, 99, 99, 99, 99, 99],
        [99, 99, 99, 99, 99, 99, 99, 99],
        [99, 99, 99, 99, 99, 99, 99, 99],
        [99, 99, 99, 99, 99, 99, 99, 99],
        [99, 99, 99, 99, 99, 99, 99, 99]
    ]
    if luminance:
        quantization_matrix = [[max(1, int(value / (quality / 50))) for value in row] for row in standard_luminance_quantization_matrix]
    else:
        quantization_matrix = [[max(1, int(value / (quality / 50))) for value in row] for row in standard_chrominance_quantization_matrix]
    quantized_block = [[round(block[i][j] / quantization_matrix[i][j]) for j in range(len(block[0]))] for i in range(len(block))]
    return quantized_block

def jpeg_encode(file_path, quality=50):
    # This function should take the input file (as a .bmp) and perform the JPEG encoding steps
    # The steps include:
    # 1. Read the input image file and extract the pixel data
    image = bmp_parser(file_path)
    
    # 2. Convert RGB to YCbCr color space and perform level shifting (subtract 128 from the Y, Cb, and Cr values, assuming 8-bit samples)
    ycbcr_data = rgb_to_ycbcr(image)
    y = [[pixel[0] for pixel in row] for row in ycbcr_data]
    cb = [[pixel[1] for pixel in row] for row in ycbcr_data]
    cr = [[pixel[2] for pixel in row] for row in ycbcr_data]

    level_shifted_y = [[value - 128 for value in row] for row in y]
    level_shifted_cb = [[value - 128 for value in row] for row in cb]
    level_shifted_cr = [[value - 128 for value in row] for row in cr]

    # 3. Subsample the chroma channels (Cb and Cr) if necessary (e.g., 4:2:0 subsampling)
    # For simplicity, we will skip this step for now
    
    # 4. Divide the image into 8x8 blocks and apply the DCT to each block
    y_blocks = make_block(level_shifted_y)
    cb_blocks = make_block(level_shifted_cb)
    cr_blocks = make_block(level_shifted_cr)
    y_dct_blocks = [FFT2D.fft2d(block) for block in y_blocks]
    cb_dct_blocks = [FFT2D.fft2d(block) for block in cb_blocks]
    cr_dct_blocks = [FFT2D.fft2d(block) for block in cr_blocks]

    # 5. Quantize the DCT coefficients using a quantization matrix based on the quality factor
    quantized_y_blocks = [quantization(block, luminance=True, quality=quality) for block in y_dct_blocks]
    quantized_cb_blocks = [quantization(block, luminance=False, quality=quality) for block in cb_dct_blocks]
    quantized_cr_blocks = [quantization(block, luminance=False, quality=quality) for block in cr_dct_blocks]

    # 6. Interleave the quantized coefficients according to the zig-zag pattern
    interleaved_y_data = interleaver(quantized_y_blocks)
    interleaved_cb_data = interleaver(quantized_cb_blocks)
    interleaved_cr_data = interleaver(quantized_cr_blocks)

    # 7. Perform entropy coding (e.g., Huffman coding) on the interleaved data
        


print(bmp_parser('2x2.bmp'))
