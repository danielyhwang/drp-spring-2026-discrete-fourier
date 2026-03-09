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



def jpeg_encode(file_path, quality=50):
    image = bmp_parser(file_path)
    
    # This function should take the input image (as a 2D array of pixel data) and perform the JPEG encoding steps
    # The steps include:
    # 2. Convert RGB to YCbCr color space
    ycbcr_data = rgb_to_ycbcr(image)
    
    # 3. Subsample the chroma channels (Cb and Cr) if necessary (e.g., 4:2:0 subsampling)
    # For simplicity, we will skip this step for now
    
    # 4. Divide the image into 8x8 blocks and apply the DCT to each block
    # For simplicity, we will skip this step for now
    
    # 5. Quantize the DCT coefficients using a quantization matrix based on the quality factor
    # For simplicity, we will skip this step for now
    
    # 5. Interleave the quantized coefficients according to the zig-zag pattern
    interleaved_data = interleaver(ycbcr_data)
    
    # 6. Perform entropy coding (e.g., Huffman coding) on the interleaved data
    # For simplicity, we will skip this step for now
    
    return interleaved_data
    


print(bmp_parser('2x2.bmp'))
