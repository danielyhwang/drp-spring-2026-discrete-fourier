import argparse
import logging
import os
import struct
import math

import numpy as np
from typing import List, Any, Dict, Tuple
from struct import unpack
from constants import JFIF_unit_strings, SOF_type_strings, interleaved_order, DQT_PRECISION_8_BIT, DQT_PRECISION_16_BIT, \
    DQT_PRECISION_STRINGS, TABLE_CLASS_STRINGS
import numpy.typing as npt
logger = logging.getLogger(__name__)

def _get_idct_matrix() -> npt.NDArray[np.float64]:
    N = 8
    C = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(N):
            if i == 0:
                C[i, j] = 1 / math.sqrt(N)
            else:
                C[i, j] = math.sqrt(2 / N) * math.cos((2 * j + 1) * i * math.pi / (2 * N))
    return C

IDCT_MATRIX = _get_idct_matrix()

def _get_zigzag_to_2d_map() -> Dict[int, Tuple[int, int]]:
    mapping = {}
    for r in range(8):
        for c in range(8):
            mapping[interleaved_order[r][c]] = (r, c)
    return mapping

ZIGZAG_MAP = _get_zigzag_to_2d_map()

def get_codewords(length_table) -> List[tuple[int, int]]:
    counter = 0
    codewords = []
    for length in range(1, 17):
        count = length_table[length - 1]
        for i in range(count):
            codewords.append((length, counter))
            counter += 1
        counter = counter * 2
    return codewords


def bmp_writer(filename: str, rgb_array: np.ndarray):
    if rgb_array is None:
        logger.error("No RGB data.")
        return

    height, width, _ = rgb_array.shape

    row_bytes = width * 3
    padding_length = (4 - (row_bytes % 4)) % 4
    row_size = row_bytes + padding_length
    image_size = row_size * height
    file_size = 54 + image_size

    with open(filename, 'wb') as f:
        # BITMAPFILEHEADER
        # 'BM' signature
        f.write(b'BM')
        f.write(struct.pack('<LHHL', file_size, 0, 0, 54))

        # BITMAPINFOHEADER
        f.write(struct.pack('<LllHHLLllLL',
                            40,  # Header size
                            width,  # Width
                            -height,  # Height (negative = top-down)
                            1,  # Color planes
                            24,  # Bits per pixel (RGB)
                            0,  # Compression (0 = BI_RGB, uncompressed)
                            image_size,  # Image size
                            2835,  # X pixels per meter (~72 DPI)
                            2835,  # Y pixels per meter (~72 DPI)
                            0,  # Total colors in color table
                            0))  # Important color count

        # RGB -> BGR
        bgr_array = rgb_array[:, :, ::-1]
        padding = b'\x00' * padding_length

        # Write row by row to apply padding
        for row in bgr_array:
            f.write(row.tobytes())
            if padding_length > 0:
                f.write(padding)

    logger.info(f"Successfully saved to {filename}")

class JPEGDecoder:
    def __init__(self, filename):
        self.RGB = None
        self.number_of_image_components = None
        self.samples_per_line = None
        self.number_of_lines = None
        self.sample_precision = None
        self.APP_segments: List[Any] = []
        self.QuantizationTables: Dict[int, npt.NDArray[Any, Any]] = {}
        self.HuffmanTables: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}
        self.file_handle = open(filename, "rb")
        self.SOF_type = None
        self.C: List[int] = []
        self.H: List[int] = []
        self.V: List[int] = []
        self.Tq: List[int] = []
        self.scan_components: Dict[int, Dict[str, int]] = {}
        self.bit_buffer = 0
        self.bits_count = 0
        self.reconstructed_components = {}
        self.old_dc = [0, 0, 0, 0]

        self.Ss = 0
        self.Se = 63
        self.Ah = 0
        self.Al = 0
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_handle.close()

    def get_DQT(self):
        DQT = np.zeros((8, 8))
        Lq = int.from_bytes(self.file_handle.read(2), byteorder='big')
        remaining_length = Lq - 2

        while remaining_length != 0:
            PqTq = self.file_handle.read(1)[0]
            remaining_length -= 1
            Pq = (PqTq >> 4) & 0xf

            if Pq != DQT_PRECISION_8_BIT and Pq != DQT_PRECISION_16_BIT:
                logger.error("Quantization Precision not in range 0-1!")
                exit()
            Tq = PqTq & 0xf
            if not 0 <= Tq <= 3:
                logger.error("Quantization Table Identifier not in range 0-3!")
                exit()


            logger.debug(
                f"""DQT Segment Length: {Lq}\n"""
                f"""\t\tQuantization Precision: {DQT_PRECISION_STRINGS[Pq]}\n"""
                f"""\t\tTable Identifier: {Tq}"""
            )

            DQT = np.zeros((8, 8))
            if Pq == 0:
                interleaved_DQT = unpack(">64B", self.file_handle.read(64))
                remaining_length -= 64
            else:
                interleaved_DQT = unpack(">64H", self.file_handle.read(128))
                remaining_length -= 128
            for i in range(64):
                x, y = i // 8, i % 8
                DQT[x][y] = interleaved_DQT[interleaved_order[x][y]]
            self.QuantizationTables[Tq] = DQT

    def get_DHT(self):
        Lh = int.from_bytes(self.file_handle.read(2), byteorder='big')
        remaining_length = Lh - 2
        while remaining_length > 0:
            TcTh = self.file_handle.read(1)[0]
            Tc = (TcTh >> 4) & 0xF
            Th = TcTh & 0xF
            length_table = [0] * 16 # table[i] = codewords with length i + 1
            for i in range(16):
                length_table[i] = self.file_handle.read(1)[0]
            remaining_length -= 17
            DHT_debug_str = (f"Huffman Table Class: {TABLE_CLASS_STRINGS[Tc]}\n\tTable Destination: {Th}\n\tLength Table: "
                         f"{length_table}\n\tDecryption Table:\n")

            codewords = get_codewords(length_table)
            decrypt_table = {}
            for codeword in codewords:
                decrypt_val = self.file_handle.read(1)[0]
                decrypt_table[codeword] = decrypt_val
                remaining_length -= 1
                binary_str = f"{codeword[1]:0{codeword[0]}b}"
                DHT_debug_str += f"\t\t\"0b{binary_str}\" -> {hex(decrypt_table[codeword])}\n"
            logger.debug(DHT_debug_str)
            self.HuffmanTables[(Tc, Th)] = decrypt_table.copy()
        return

    def get_APPn(self, marker):
        if marker == b'\xFF\xE0':
            logger.debug(f"Correct APP0 Marker. Proceeding.")
            APP0_length = int.from_bytes(self.file_handle.read(2), byteorder='big')
            logger.debug(f"APP0 length read as {APP0_length}")

            self.file_handle.seek(-2, os.SEEK_CUR)  # move back to start of APP0 header
            APP0 = self.file_handle.read(APP0_length)
            APP0_length, JFIF_identifier, JFIF_major_ver, JFIF_minor_ver, \
                units, Xdensity, Ydensity, Xthumbnail, Ythumbnail = unpack(
                ">H5sBBBHHBB",
                APP0
            )

            if JFIF_identifier != b"JFIF\x00":
                logger.warning(f"JFIF Identifier \"{JFIF_identifier}\" != \"JFIF\\0\"")
            if JFIF_major_ver != 1:
                logger.warning(f"JFIF Major Version {JFIF_major_ver} != 1")
            if not 0 <= JFIF_minor_ver <= 2:
                logger.warning(f"JFIF Minor Version {JFIF_minor_ver} not in range .00-.02")
            if not 0 <= units <= 2:
                logger.warning(f"Invalid units specifier {units}")

            logger.debug(
                f"APP0 Parsed as\n"
                f"\t\tAPP0 length: {APP0_length}\n"
                f"\t\tJFIF identifier: \"{JFIF_identifier}\"\n"
                f"\t\tJFIF version: {JFIF_major_ver}.0{JFIF_minor_ver}\n"
                f"\t\tX, Y units: {JFIF_unit_strings[units]}\n"
                f"\t\tXdensity: {Xdensity}\n"
                f"\t\tYdensity: {Ydensity}\n"
                f"\t\tXthumbnail: {Xthumbnail}\n"
                f"\t\tYthumbnail: {Ythumbnail}"
            )
        elif b'\xFF\xE1' <= marker <= b'\xFF\xEF':
            logger.warning("Unsupported APPn Type detected! Skipping APPn parsing")
            APPn_length = int.from_bytes(self.file_handle.read(2), byteorder='big')
            self.file_handle.seek(APPn_length-2, os.SEEK_CUR)
        return

    def get_SOF(self, SOF_type):
        SOF_header = self.file_handle.read(8)
        Lf, P, Y, X, Nf = unpack(">HBHHB", SOF_header)
        self.sample_precision = P
        self.number_of_lines = Y
        self.samples_per_line = X
        self.number_of_image_components = Nf

        logger.debug(
            f"SOF Header Type: {SOF_type_strings[SOF_type]}\n"
            f"\t\tHeader Length: {Lf}\n"
            f"\t\tSample Precision: {P}\n"
            f"\t\tNumber of Lines: {Y}\n"
            f"\t\tSamples per Line: {X}\n"
            f"\t\tNumber of Image Components: {Nf}"
        )

        for i in range(Nf):
            Ci, HiVi, Tqi = unpack(">BBB", self.file_handle.read(3))
            Hi = HiVi >> 4
            Vi = HiVi & 0xF
            if not 1 <= Hi <= 4:
                error_str = f"Invalid H{i} value: {Hi}"
                logger.error(error_str)
                return
            if not 1 <= Vi <= 4:
                error_str = f"Invalid V{i} value: {Vi}"
                logger.error(error_str)
                return
            if not 0 <= Tqi <= 3:
                error_str = f"Invalid Tq{i} value: {Tqi}"
                logger.error(error_str)
                return
            self.C.append(Ci)
            self.H.append(Hi)
            self.V.append(Vi)
            self.Tq.append(Tqi)

            logger.debug(f"SOF Component {i}\n"
                         f"\t\tComponent Identifer: {Ci}\n"
                         f"\t\tHorizontal Sampling Factor: {Hi}\n"
                         f"\t\tVertical Sampling Factor: {Vi}\n"
                         f"\t\tQuantization Table Destination: {Tqi}"
                         )

    def get_SOS(self):
        Ls = int.from_bytes(self.file_handle.read(2), byteorder='big')
        Ns = self.file_handle.read(1)[0]

        logger.debug(f"SOS Header Length: {Ls}\n\t\tNumber of Components in Scan: {Ns}")



        for i in range(Ns):
            Cs = self.file_handle.read(1)[0]
            TdTa = self.file_handle.read(1)[0]

            Td = (TdTa >> 4) & 0xF
            Ta = TdTa & 0xF

            self.scan_components[Cs] = {'DC': Td, 'AC': Ta}

            logger.debug(
                f"Component Selector: {Cs}\n"
                f"\t\tDC Table Destination: {Td}\n"
                f"\t\tAC Table Destination: {Ta}"
            )

        Ss, Se, AhAl = unpack(">BBB", self.file_handle.read(3))

        self.Ss = Ss
        self.Se = Se
        self.Ah = (AhAl >> 4) & 0xF
        self.Al = AhAl & 0xF

        logger.debug(
            f"Spectral Selection Start (Ss): {self.Ss}\n"
            f"\t\tSpectral Selection End (Se): {self.Se}\n"
            f"\t\tSuccessive Approximation High (Ah): {self.Ah}\n"
            f"\t\tSuccessive Approximation Low (Al): {self.Al}"
        )

        # Note: Immediately after reading these bytes, self.file_handle is now
        # pointing to the very first byte of the compressed image bitstream.

    def read_bits(self, n):
        if n == 0:
            return 0

        while self.bits_count < n:
            byte = self.file_handle.read(1)
            if not byte:
                raise EOFError()
            byte_val = byte[0]

            if byte_val == 0xFF:
                next_byte = self.file_handle.read(1)
                if next_byte and next_byte[0] == 0x00:
                    # treat 0xFF 0x00 as 0xFF
                    pass
                else:
                    # reset marker handling
                    if next_byte and 0xD0 <= next_byte[0] <= 0xD7:
                        self.old_dc = [0, 0, 0, 0]
                        self.bit_buffer = 0
                        self.bits_count = 0
                        continue
                    elif next_byte and next_byte[0] == 0xD9:  # EOI
                        break

            self.bit_buffer = (self.bit_buffer << 8) | byte_val
            self.bits_count += 8

        result = (self.bit_buffer >> (self.bits_count - n)) & ((1 << n) - 1)
        self.bits_count -= n
        return result

    def decode_huffman(self, table_type, table_id):
        table = self.HuffmanTables[(table_type, table_id)]
        current_bits = 0
        for length in range(1, 17):
            current_bits = (current_bits << 1) | self.read_bits(1)
            if (length, current_bits) in table:
                return table[(length, current_bits)]
        raise ValueError("Invalid Huffman code encountered")

    def receive_extend(self, category):
        if category == 0:
            return 0
        vt = self.read_bits(category)
        if vt < (1 << (category - 1)):
            vt += (-1 << category) + 1
        return vt

    def idct_2d(self, block: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        # Perform 2D IDCT via Matrix Multiplication
        return IDCT_MATRIX.T @ block @ IDCT_MATRIX

    def decode_block(self, component_idx, table_idx_dc, table_idx_ac):
        block_1d = np.zeros(64, dtype=np.float64)

        # get DC
        category = self.decode_huffman(0, table_idx_dc)  # 0 = DC Table
        diff = self.receive_extend(category)
        self.old_dc[component_idx] += diff
        block_1d[0] = self.old_dc[component_idx]

        # get AC
        k = 1
        while k < 64:
            rs = self.decode_huffman(1, table_idx_ac)  # 1 = AC Table
            if rs == 0x00:  # EOB (End of Block)
                break

            run = rs >> 4
            size = rs & 0x0F

            if size == 0:  # ZRL (16 zeroes)
                k += 16
                continue

            k += run
            if k < 64:
                block_1d[k] = self.receive_extend(size)
            k += 1

        block_2d = np.zeros((8, 8), dtype=np.float64)
        for i in range(64):
            r, c = ZIGZAG_MAP[i]
            block_2d[r, c] = block_1d[i]

        q_table = self.QuantizationTables[self.Tq[component_idx]]
        block_2d *= q_table

        return self.idct_2d(block_2d)

    def read_MCUs(self):
        max_h = max(self.H)
        max_v = max(self.V)

        mcu_width = max_h * 8
        mcu_height = max_v * 8

        mcus_x = (self.samples_per_line + mcu_width - 1) // mcu_width
        mcus_y = (self.number_of_lines + mcu_height - 1) // mcu_height


        self.reconstructed_components = {
            i: np.zeros((mcus_y * self.V[i] * 8, mcus_x * self.H[i] * 8), dtype=np.float64)
            for i in range(self.number_of_image_components)
        }

        for y in range(mcus_y):
            for x in range(mcus_x):
                for i, c_id in enumerate(self.C):
                    h_samp = self.H[i]
                    v_samp = self.V[i]

                    dc_id = self.scan_components[c_id]['DC']
                    ac_id = self.scan_components[c_id]['AC']

                    for v in range(v_samp):
                        for h in range(h_samp):
                            try:
                                block = self.decode_block(i, dc_id, ac_id)
                                pixel_y = y * v_samp * 8 + v * 8
                                pixel_x = x * h_samp * 8 + h * 8
                                self.reconstructed_components[i][pixel_y:pixel_y + 8, pixel_x:pixel_x + 8] = block
                            except EOFError:
                                logger.warning("Reached end of file unexpectedly!")
                                break
        full_height = mcus_y * mcu_height
        full_width = mcus_x * mcu_width
        image = np.zeros((full_height, full_width, self.number_of_image_components), dtype=np.float64)

        for i in range(self.number_of_image_components):
            comp = self.reconstructed_components[i]
            scale_y = max_v // self.V[i]
            scale_x = max_h // self.H[i]

            if scale_y > 1 or scale_x > 1:
                comp = np.repeat(np.repeat(comp, scale_y, axis=0), scale_x, axis=1)

            image[:, :, i] = comp

        # YCbCr to RGB mapping
        if self.number_of_image_components >= 3:
            Y = image[:, :, 0] + 128.0
            Cb = image[:, :, 1]
            Cr = image[:, :, 2]

            R = Y + 1.402 * Cr
            G = Y - 0.344136 * Cb - 0.714136 * Cr
            B = Y + 1.772 * Cb

            rgb_image = np.dstack((R, G, B))
        else:
            Y = image[:, :, 0] + 128.0
            rgb_image = np.dstack((Y, Y, Y))

        rgb_image = np.clip(rgb_image, 0, 255).astype(np.uint8)
        rgb_image = rgb_image[:self.number_of_lines, :self.samples_per_line, :]

        logger.info("Decoding Complete.")
        self.RGB = rgb_image
        return rgb_image

    def read_jpeg(self):
        SOI_marker = self.file_handle.read(2)
        if SOI_marker != b'\xFF\xD8':
            logger.error("incorrect SOI marker")
            exit()
        logger.debug(f"Correct SOI marker. Proceeding.")

        while (True):
            marker = self.file_handle.read(2)
            if b'\xFF\xE0' <= marker <= b'\xFF\xEF':
                logger.debug(f"APPn marker found. Proceeding")
                self.get_APPn(marker)
            elif marker == b'\xFF\xDB':
                logger.debug("DQT marker found! Parsing DQT!")
                self.get_DQT()
            elif marker == b'\xFF\xC4':
                logger.debug("DHT marker found! Parsing DHT")
                self.get_DHT()
            elif b'\xFF\xC0' <= marker <= b'\xFF\xCF':
                SOF_type = marker[1] - 0xC0
                self.get_SOF(SOF_type)

            elif marker == b'\xFF\xDA':
                logger.debug(f"SOS Component found! Parsing SOS!")
                self.get_SOS()
                break
            else:
                logger.error(f"Unsupported segment marker: \"{marker.hex()}\"!")
                return
        return self.read_MCUs()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('-debug', '-g', action='store_true')
    parser.add_argument('-out', '-o', default='output.bmp', help="output file path")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(levelname)s - %(message)s'
        )

    with JPEGDecoder(args.filename) as image_reader:
        RGB_tables = image_reader.read_jpeg()
        bmp_writer(args.out, RGB_tables)