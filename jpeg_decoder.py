import argparse
import logging
import os
import numpy as np
from typing import List, Any, Dict, Tuple
from struct import unpack
from constants import JFIF_unit_strings, SOF_type_strings, interleaved_order, DQT_PRECISION_8_BIT, DQT_PRECISION_16_BIT, \
    DQT_PRECISION_STRINGS, TABLE_CLASS_STRINGS
import numpy.typing as npt
logger = logging.getLogger(__name__)


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


class JPEGDecoder:
    def __init__(self, filename):
        self.number_of_image_components = None
        self.samples_per_line = None
        self.number_of_lines = None
        self.sample_precision = None
        self.APP_segments: List[Any] = []
        self.QuantizationTables: Dict[Tuple[int, int], npt.NDArray[Any, Any]] = {}
        self.HuffmanTables: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}
        self.file_handle = open(filename, "rb")
        self.SOF_type = None
        self.C: List[int] = []
        self.H: List[int] = []
        self.V: List[int] = []
        self.Tq: List[int] = []
        self.scan_components: Dict[int, Dict[str, int]] = {}
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

        # begin SOF parsing
        raise NotImplementedError("Image reading time!")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('-debug', '-g', action='store_true')
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