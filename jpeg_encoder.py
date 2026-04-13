import math
import os
import struct
import argparse


BLOCK_SIZE = 8

# JPEG stores each 8x8 block in zig-zag order so low-frequency values come first
# and long runs of trailing zeros are more likely after quantization.
ZIGZAG_ORDER = [
    (0, 0), (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2),
    (2, 1), (3, 0), (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5),
    (1, 4), (2, 3), (3, 2), (4, 1), (5, 0), (6, 0), (5, 1), (4, 2),
    (3, 3), (2, 4), (1, 5), (0, 6), (0, 7), (1, 6), (2, 5), (3, 4),
    (4, 3), (5, 2), (6, 1), (7, 0), (7, 1), (6, 2), (5, 3), (4, 4),
    (3, 5), (2, 6), (1, 7), (2, 7), (3, 6), (4, 5), (5, 4), (6, 3),
    (7, 2), (7, 3), (6, 4), (5, 5), (4, 6), (3, 7), (4, 7), (5, 6),
    (6, 5), (7, 4), (7, 5), (6, 6), (5, 7), (6, 7), (7, 6), (7, 7),
]

STD_LUMINANCE_QUANTIZATION_MATRIX = [
    [16, 11, 10, 16, 24, 40, 51, 61],
    [12, 12, 14, 19, 26, 58, 60, 55],
    [14, 13, 16, 24, 40, 57, 69, 56],
    [14, 17, 22, 29, 51, 87, 80, 62],
    [18, 22, 37, 56, 68, 109, 103, 77],
    [24, 35, 55, 64, 81, 104, 113, 92],
    [49, 64, 78, 87, 103, 121, 120, 101],
    [72, 92, 95, 98, 112, 100, 103, 99],
]

STD_CHROMINANCE_QUANTIZATION_MATRIX = [
    [17, 18, 24, 47, 99, 99, 99, 99],
    [18, 21, 26, 66, 99, 99, 99, 99],
    [24, 26, 56, 99, 99, 99, 99, 99],
    [47, 66, 99, 99, 99, 99, 99, 99],
    [99, 99, 99, 99, 99, 99, 99, 99],
    [99, 99, 99, 99, 99, 99, 99, 99],
    [99, 99, 99, 99, 99, 99, 99, 99],
    [99, 99, 99, 99, 99, 99, 99, 99],
]

# These are the standard baseline JPEG Huffman tables from the JFIF/JPEG spec.
# We use them directly rather than trying to learn custom tables from the image.
BITS_DC_LUMINANCE = [0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
                     0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
VALS_DC_LUMINANCE = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                     0x08, 0x09, 0x0A, 0x0B]

BITS_AC_LUMINANCE = [0x00, 0x02, 0x01, 0x03, 0x03, 0x02, 0x04, 0x03,
                     0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D]
VALS_AC_LUMINANCE = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
    0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
    0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
    0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
    0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
]

BITS_DC_CHROMINANCE = [0x00, 0x03, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
                       0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
VALS_DC_CHROMINANCE = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                       0x08, 0x09, 0x0A, 0x0B]

BITS_AC_CHROMINANCE = [0x00, 0x02, 0x01, 0x02, 0x04, 0x04, 0x03, 0x04,
                       0x07, 0x05, 0x04, 0x04, 0x00, 0x01, 0x02, 0x77]
VALS_AC_CHROMINANCE = [
    0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12, 0x41,
    0x51, 0x07, 0x61, 0x71, 0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91,
    0xA1, 0xB1, 0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0, 0x15, 0x62, 0x72, 0xD1,
    0x0A, 0x16, 0x24, 0x34, 0xE1, 0x25, 0xF1, 0x17, 0x18, 0x19, 0x1A, 0x26,
    0x27, 0x28, 0x29, 0x2A, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44,
    0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58,
    0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74,
    0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
    0x88, 0x89, 0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A,
    0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4,
    0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
    0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA,
    0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF2, 0xF3, 0xF4,
    0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
]


def bmp_parser(file_path, ost=False):
    # Read an uncompressed 24-bit or 32-bit BMP file into a 2D list of pixels.
    # Pixels are returned in top-to-bottom image order, regardless of BMP storage.
    del ost
    with open(file_path, "rb") as f:
        if f.read(2) != b"BM":
            raise ValueError("Unsupported file format; expected BMP")

        f.seek(10)
        data_offset = int.from_bytes(f.read(4), "little")
        dib_header_size = int.from_bytes(f.read(4), "little")
        width = int.from_bytes(f.read(4), "little", signed=True)
        raw_height = int.from_bytes(f.read(4), "little", signed=True)
        top_down = raw_height < 0
        height = abs(raw_height)
        f.seek(2, 1)
        bitsperpixel = int.from_bytes(f.read(2), "little")
        compression_method = int.from_bytes(f.read(4), "little")

        if dib_header_size < 40:
            raise ValueError("Unsupported BMP DIB header")
        if bitsperpixel not in (24, 32):
            raise ValueError("Only 24-bit and 32-bit BMP images are supported")
        if compression_method not in (0, 3):
            raise ValueError("Unsupported BMP compression method")

        bytes_per_pixel = bitsperpixel // 8
        # BMP rows are padded out to a multiple of 4 bytes.
        row_stride = ((width * bytes_per_pixel + 3) // 4) * 4

        f.seek(data_offset)
        pixel_data = []
        for _ in range(height):
            row_bytes = f.read(row_stride)
            row = []
            for x in range(width):
                start = x * bytes_per_pixel
                blue = row_bytes[start]
                green = row_bytes[start + 1]
                red = row_bytes[start + 2]
                if bytes_per_pixel == 4:
                    alpha = row_bytes[start + 3]
                    row.append((red, green, blue, alpha))
                else:
                    row.append((red, green, blue))
            pixel_data.append(row)

        if not top_down:
            pixel_data.reverse()

        return pixel_data


def rgb_to_ycbcr(pixel_data):
    # Convert RGB pixels into the YCbCr color space used by JPEG.
    # Alpha, if present, is ignored.
    if len(pixel_data) == 0 or len(pixel_data[0]) == 0:
        return []

    alpha = len(pixel_data[0][0]) == 4
    ycbcr_data = []
    for row in pixel_data:
        ycbcr_row = []
        for pixel in row:
            r, g, b = pixel[:3] if alpha else pixel
            y = _clamp_byte(round(0.299 * r + 0.587 * g + 0.114 * b))
            cb = _clamp_byte(round(-0.168736 * r - 0.331264 * g + 0.5 * b + 128))
            cr = _clamp_byte(round(0.5 * r - 0.418688 * g - 0.081312 * b + 128))
            ycbcr_row.append((y, cb, cr))
        ycbcr_data.append(ycbcr_row)
    return ycbcr_data


def interleaver(data_array):
    # Flatten one 8x8 block into JPEG's zig-zag coefficient order.
    return [data_array[row][col] for row, col in ZIGZAG_ORDER]


def make_block(data_array, block_size=BLOCK_SIZE):
    # Break a 2D channel into block_size x block_size blocks.
    # If the dimensions are not multiples of 8, pad by repeating edge values.
    if not data_array or not data_array[0]:
        return []

    height = len(data_array)
    width = len(data_array[0])
    padded_height = ((height + block_size - 1) // block_size) * block_size
    padded_width = ((width + block_size - 1) // block_size) * block_size

    padded_data = []
    for i in range(padded_height):
        src_i = min(i, height - 1)
        row = []
        for j in range(padded_width):
            src_j = min(j, width - 1)
            row.append(data_array[src_i][src_j])
        padded_data.append(row)

    blocks = []
    for i in range(0, padded_height, block_size):
        for j in range(0, padded_width, block_size):
            block = [row[j:j + block_size] for row in padded_data[i:i + block_size]]
            blocks.append(block)
    return blocks


def quantization(block, luminance=True, quality=50):
    # Divide each DCT coefficient by the corresponding quantization step size.
    # Luminance and chrominance use different standard base tables.
    quantization_matrix = build_quantization_matrix(luminance=luminance, quality=quality)
    return [
        [int(round(block[i][j] / quantization_matrix[i][j])) for j in range(BLOCK_SIZE)]
        for i in range(BLOCK_SIZE)
    ]


def build_quantization_matrix(luminance=True, quality=50):
    # Scale the standard JPEG quantization matrix based on the requested quality.
    # Quality 50 is the standard table; higher quality means less aggressive quantization.
    quality = max(1, min(100, quality))
    base = STD_LUMINANCE_QUANTIZATION_MATRIX if luminance else STD_CHROMINANCE_QUANTIZATION_MATRIX
    scale = 5000 // quality if quality < 50 else 200 - 2 * quality
    return [
        [min(255, max(1, (value * scale + 50) // 100)) for value in row]
        for row in base
    ]


def forward_dct(block):
    # Apply the 2D DCT to one 8x8 block after level shifting by 128.
    result = [[0.0 for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
    cosines = [[math.cos(((2 * x + 1) * u * math.pi) / 16.0) for x in range(BLOCK_SIZE)]
               for u in range(BLOCK_SIZE)]

    for u in range(BLOCK_SIZE):
        for v in range(BLOCK_SIZE):
            total = 0.0
            for x in range(BLOCK_SIZE):
                for y in range(BLOCK_SIZE):
                    total += block[x][y] * cosines[u][x] * cosines[v][y]
            cu = 1 / math.sqrt(2) if u == 0 else 1.0
            cv = 1 / math.sqrt(2) if v == 0 else 1.0
            result[u][v] = 0.25 * cu * cv * total
    return result


def jpeg_encode(file_path, quality=50, output_path=None):
    # Full baseline JPEG pipeline:
    # 1. Parse BMP pixels
    # 2. Convert RGB to YCbCr and level shift
    # 3. Split each channel into 8x8 blocks
    # 4. Apply the DCT
    # 5. Quantize coefficients
    # 6. Zig-zag scan each block
    # 7. Entropy-code the coefficients
    # 8. Write the final JPEG container
    image = bmp_parser(file_path)
    if not image:
        raise ValueError("Input BMP contains no pixel data")

    height = len(image)
    width = len(image[0])

    ycbcr_data = rgb_to_ycbcr(image)
    y_channel = [[pixel[0] - 128 for pixel in row] for row in ycbcr_data]
    cb_channel = [[pixel[1] - 128 for pixel in row] for row in ycbcr_data]
    cr_channel = [[pixel[2] - 128 for pixel in row] for row in ycbcr_data]

    y_blocks = make_block(y_channel)
    cb_blocks = make_block(cb_channel)
    cr_blocks = make_block(cr_channel)

    # Transform spatial-domain samples into frequency-domain coefficients.
    quantized_y_blocks = [quantization(forward_dct(block), luminance=True, quality=quality) for block in y_blocks]
    quantized_cb_blocks = [quantization(forward_dct(block), luminance=False, quality=quality) for block in cb_blocks]
    quantized_cr_blocks = [quantization(forward_dct(block), luminance=False, quality=quality) for block in cr_blocks]

    # Reorder coefficients so entropy coding sees long zero runs more often.
    zigzag_y = [interleaver(block) for block in quantized_y_blocks]
    zigzag_cb = [interleaver(block) for block in quantized_cb_blocks]
    zigzag_cr = [interleaver(block) for block in quantized_cr_blocks]

    jpeg_bytes = build_jpeg_bytes(width, height, zigzag_y, zigzag_cb, zigzag_cr, quality)

    if output_path is None:
        base, _ = os.path.splitext(file_path)
        output_path = f"{base}.jpg"

    with open(output_path, "wb") as f:
        f.write(jpeg_bytes)

    return output_path


def build_jpeg_bytes(width, height, y_blocks, cb_blocks, cr_blocks, quality):
    # Assemble the JPEG headers and append the entropy-coded scan data.
    if not (len(y_blocks) == len(cb_blocks) == len(cr_blocks)):
        raise ValueError("Y, Cb, and Cr block counts must match for 4:4:4 encoding")

    lum_q = build_quantization_matrix(luminance=True, quality=quality)
    chr_q = build_quantization_matrix(luminance=False, quality=quality)

    dc_lum_table = build_huffman_table(BITS_DC_LUMINANCE, VALS_DC_LUMINANCE)
    ac_lum_table = build_huffman_table(BITS_AC_LUMINANCE, VALS_AC_LUMINANCE)
    dc_chr_table = build_huffman_table(BITS_DC_CHROMINANCE, VALS_DC_CHROMINANCE)
    ac_chr_table = build_huffman_table(BITS_AC_CHROMINANCE, VALS_AC_CHROMINANCE)

    entropy_writer = BitWriter()
    # DC coefficients are differential-coded per component, so track the previous
    # Y, Cb, and Cr DC values separately.
    previous_dc = [0, 0, 0]

    for index in range(len(y_blocks)):
        encode_block(entropy_writer, y_blocks[index], dc_lum_table, ac_lum_table, previous_dc, 0)
        encode_block(entropy_writer, cb_blocks[index], dc_chr_table, ac_chr_table, previous_dc, 1)
        encode_block(entropy_writer, cr_blocks[index], dc_chr_table, ac_chr_table, previous_dc, 2)

    entropy_data = entropy_writer.finish()

    data = bytearray()
    data.extend(write_marker(0xD8))
    data.extend(write_app0())
    data.extend(write_dqt(0, lum_q))
    data.extend(write_dqt(1, chr_q))
    data.extend(write_sof0(width, height))
    data.extend(write_dht(0, 0, BITS_DC_LUMINANCE, VALS_DC_LUMINANCE))
    data.extend(write_dht(1, 0, BITS_AC_LUMINANCE, VALS_AC_LUMINANCE))
    data.extend(write_dht(0, 1, BITS_DC_CHROMINANCE, VALS_DC_CHROMINANCE))
    data.extend(write_dht(1, 1, BITS_AC_CHROMINANCE, VALS_AC_CHROMINANCE))
    data.extend(write_sos())
    data.extend(entropy_data)
    data.extend(write_marker(0xD9))
    return bytes(data)


def encode_block(writer, block, dc_table, ac_table, previous_dc, component_index):
    # JPEG encodes the DC term as a difference from the previous block's DC.
    dc_diff = block[0] - previous_dc[component_index]
    previous_dc[component_index] = block[0]

    dc_size = category(dc_diff)
    code, length = dc_table[dc_size]
    writer.write_bits(code, length)
    if dc_size > 0:
        writer.write_bits(amplitude_bits(dc_diff, dc_size), dc_size)

    # AC coefficients are run-length encoded: the upper nibble stores the run of
    # zeros, and the lower nibble stores the bit-width of the next nonzero value.
    zero_run = 0
    for coefficient in block[1:]:
        if coefficient == 0:
            zero_run += 1
            continue

        while zero_run >= 16:
            zrl_code, zrl_len = ac_table[0xF0]
            writer.write_bits(zrl_code, zrl_len)
            zero_run -= 16

        ac_size = category(coefficient)
        symbol = (zero_run << 4) | ac_size
        code, length = ac_table[symbol]
        writer.write_bits(code, length)
        writer.write_bits(amplitude_bits(coefficient, ac_size), ac_size)
        zero_run = 0

    if zero_run > 0:
        eob_code, eob_len = ac_table[0x00]
        writer.write_bits(eob_code, eob_len)


def category(value):
    # The category is the number of magnitude bits needed to store the value.
    if value == 0:
        return 0
    return abs(value).bit_length()


def amplitude_bits(value, size):
    # Negative JPEG coefficient values are stored using the complemented form.
    if size == 0:
        return 0
    if value >= 0:
        return value
    return value + ((1 << size) - 1)


def build_huffman_table(bits, values):
    # Expand the JPEG "counts per bit length" representation into actual
    # canonical Huffman codes.
    table = {}
    code = 0
    value_index = 0
    for bit_length, count in enumerate(bits, start=1):
        for _ in range(count):
            table[values[value_index]] = (code, bit_length)
            code += 1
            value_index += 1
        code <<= 1
    return table


def write_marker(marker):
    # JPEG markers are always 0xFF followed by a marker byte.
    return bytes((0xFF, marker))


def write_segment(marker, payload):
    # Most JPEG marker segments store a 2-byte big-endian length including
    # the length field itself.
    return write_marker(marker) + struct.pack(">H", len(payload) + 2) + payload


def write_app0():
    # Minimal JFIF APP0 segment so image viewers recognize the file cleanly.
    payload = bytearray()
    payload.extend(b"JFIF\x00")
    payload.extend((0x01, 0x01))
    payload.append(0x00)
    payload.extend(struct.pack(">H", 1))
    payload.extend(struct.pack(">H", 1))
    payload.extend((0x00, 0x00))
    return write_segment(0xE0, payload)


def write_dqt(table_id, matrix):
    # Quantization tables are written in zig-zag order inside the JPEG file.
    payload = bytearray()
    payload.append(table_id)
    for row, col in ZIGZAG_ORDER:
        payload.append(matrix[row][col])
    return write_segment(0xDB, payload)


def write_sof0(width, height):
    # SOF0 declares a baseline DCT image with 3 components in 4:4:4 sampling.
    payload = bytearray()
    payload.append(8)
    payload.extend(struct.pack(">H", height))
    payload.extend(struct.pack(">H", width))
    payload.append(3)
    payload.extend((1, 0x11, 0))
    payload.extend((2, 0x11, 1))
    payload.extend((3, 0x11, 1))
    return write_segment(0xC0, payload)


def write_dht(table_class, table_id, bits, values):
    # DHT stores one Huffman table: either DC (class 0) or AC (class 1).
    payload = bytearray()
    payload.append((table_class << 4) | table_id)
    payload.extend(bits)
    payload.extend(values)
    return write_segment(0xC4, payload)


def write_sos():
    # SOS starts the entropy-coded scan and selects which Huffman tables each
    # component should use.
    payload = bytearray()
    payload.append(3)
    payload.extend((1, 0x00))
    payload.extend((2, 0x11))
    payload.extend((3, 0x11))
    payload.extend((0x00, 0x3F, 0x00))
    return write_segment(0xDA, payload)


def _clamp_byte(value):
    # Keep color conversion results in the valid 8-bit sample range.
    return max(0, min(255, value))


class BitWriter:
    def __init__(self):
        # Bits are accumulated into a buffer and flushed a byte at a time.
        self._buffer = 0
        self._count = 0
        self._output = bytearray()

    def write_bits(self, value, length):
        # JPEG entropy-coded data must byte-stuff 0x00 after every emitted 0xFF.
        if length == 0:
            return
        self._buffer = (self._buffer << length) | value
        self._count += length
        while self._count >= 8:
            self._count -= 8
            byte = (self._buffer >> self._count) & 0xFF
            self._output.append(byte)
            if byte == 0xFF:
                self._output.append(0x00)
        self._buffer &= (1 << self._count) - 1 if self._count else 0

    def finish(self):
        # Pad the final byte with 1 bits, as required by the JPEG spec.
        if self._count > 0:
            pad = (1 << (8 - self._count)) - 1
            self.write_bits(pad, 8 - self._count)
        return bytes(self._output)


def main():
    # Simple command-line entry point for encoding a BMP into a JPEG.
    parser = argparse.ArgumentParser(description="Encode a BMP image as a baseline JPEG.")
    parser.add_argument("input_bmp", help="Path to the input BMP image")
    parser.add_argument("output_jpg", nargs="?", help="Path to the output JPEG image")
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=50,
        help="JPEG quality from 1 to 100 (default: 50)",
    )
    args = parser.parse_args()

    output_path = jpeg_encode(args.input_bmp, quality=args.quality, output_path=args.output_jpg)
    print(output_path)


if __name__ == "__main__":
    main()
