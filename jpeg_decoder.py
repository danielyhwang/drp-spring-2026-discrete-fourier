import argparse
import logging
import os
import numpy as np
from typing import List, Any
from struct import unpack
from constants import JFIF_unit_strings, SOF_type_strings, interleaved_order

logger = logging.getLogger(__name__)


def write_bmp():
    pass


def get_DQT(DQTs, file_handle):
    DQT = np.zeros((8, 8))
    Lq = int.from_bytes(file_handle.read(2), byteorder='big')


    remaining_length = Lq - 2

    while remaining_length != 0:
        interleaved_DQT = None
        PqTq = file_handle.read(1)[0]
        remaining_length -= 1
        Pq = (PqTq >> 4) & 0xf

        if not 0 <= Pq <= 1:
            logger.error("Quantization Precision not in range 0-1!")
            exit()
        Tq = PqTq & 0xf
        if not 0 <= Tq <= 3:
            logger.error("Quantization Table Identifier not in range 0-3!")
            exit()

        precision_strings = ["8-bit", "16-bit"]

        logger.debug(
            f"""DQT Segment Length: {Lq}\n"""
            f"""\t\tQuantization Precision: {precision_strings[Pq]}\n"""
            f"""\t\tTable Identifier: {Tq}"""
        )

        DQT = np.zeros((8, 8))
        if Pq == 0:
            interleaved_DQT = unpack(">64B", file_handle.read(64))
            remaining_length -= 64
        else:
            interleaved_DQT = unpack(">64H", file_handle.read(128))
            remaining_length -= 128
        for i in range(64):
            x, y = i // 8, i % 8
            DQT[x][y] = interleaved_DQT[interleaved_order[x][y]]
        DQTs[Tq] = DQT


def get_DHT(DHTs, file_handle):
    Lh = int.from_bytes(file_handle.read(2), byteorder="big")
    file_handle.seek(-2, os.SEEK_CUR)
    file_handle.read(Lh)


def read_jpeg(file_name: str):
    cnt = 0
    with open(file_name, "rb") as f:
        SOI_marker = f.read(2)
        if SOI_marker != b'\xFF\xD8':
            logger.error("incorrect SOI marker")
            exit()
        logger.debug(f"Correct SOI marker. Proceeding.")

        DQTs = [[] for _ in range(4)]
        DHTs = None
        SOF_type = None
        C = []
        H = []
        V = []
        Tq = []

        while (True):
            marker = f.read(2)
            if marker == b'\xFF\xE0':
                logger.debug(f"Correct APP0 Marker. Proceeding.")
                APP0_length = int.from_bytes(f.read(2), byteorder='big')
                logger.debug(f"APP0 length read as {APP0_length}")

                f.seek(-2, os.SEEK_CUR)  # move back to start of APP0 header
                APP0 = f.read(APP0_length)
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
            elif marker == b'\xFF\xE1':
                logger.warning("EXIF detected! Header Parsing not supported!")
                return
            elif marker == b'\xFF\xE2':
                logger.warning("EXIF detected! Header Parsing not supported")
                return
            elif b'\xFF\xE0' <= marker <= b'\xFF\xEF':
                logger.warning("Unsupported APPn Type detected!")
                return
            elif marker == b'\xFF\xDB':
                logger.debug("DQT marker found! Parsing DQT!")
                get_DQT(DQTs, f)
            elif marker == b'\xFF\xC4':
                get_DHT(DHTs, f)
                logger.debug("DHT marker found! \"Parsing\" DHT!")
                # exit()
            elif b'\xFF\xC0' <= marker <= b'\xFF\xCF':
                SOF_type = marker[1] - 0xC0
                SOF_header = f.read(8)
                Lf, P, Y, X, Nf = unpack(">HBHHB", SOF_header)

                logger.debug(
                    f"SOF Header Type: {SOF_type_strings[SOF_type]}\n"
                    f"\t\tHeader Length: {Lf}\n"
                    f"\t\tSample Precision: {P}\n"
                    f"\t\tNumber of Lines: {Y}\n"
                    f"\t\tSamples per Line: {X}\n"
                    f"\t\tNumber of Image Components: {Nf}"
                )

                for i in range(Nf):
                    Ci, HiVi, Tqi = unpack(">BBB", f.read(3))
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
                    C.append(Ci)
                    H.append(Hi)
                    V.append(Vi)
                    Tq.append(Tqi)

                    logger.debug(f"SOF Component {i}\n"
                                 f"\t\tComponent Identifer: {Ci}\n"
                                 f"\t\tHorizontal Sampling Factor: {Hi}\n"
                                 f"\t\tVertical Sampling Factor: {Vi}\n"
                                 f"\t\tQuantization Table Destination: {Tqi}"
                                 )
            elif marker == b'\xFF\xDA':
                logger.debug(f"SOS Component found! Parsing SOS!")
                SOS_length = int.from_bytes(f.read(2), byteorder="big")
                f.seek(-2, os.SEEK_CUR)
                f.read(SOS_length)
                pass
            else:
                logger.error(f"Unsupported segment marker: \"{marker.hex()}\"!")
                return

        # begin SOF parsing


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

read_jpeg(args.filename)
