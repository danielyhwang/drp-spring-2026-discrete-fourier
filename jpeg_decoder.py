import argparse
import logging
import os
import numpy as np
from typing import List, Any
from struct import unpack

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)

interleaved_order =  [[0, 1, 5, 6, 14, 15, 27, 28], 
                      [2, 4, 7, 13, 16, 26, 29, 42],
                      [3, 8, 12, 17, 25, 30, 41, 43],
                      [9, 11, 18, 24, 31, 40, 44, 53],
                      [10, 19, 23, 32, 39, 45, 52, 54], 
                      [20, 22, 33, 38, 46, 51, 55, 60], 
                      [21, 34, 37, 47, 50, 56, 59, 61], 
                      [35, 36, 48, 49, 57, 58, 62, 63]]

def write_bmp():
    pass


def get_DQT(DQTs, file_handle):
    DQT = np.zeros((8, 8))
    Lq = int.from_bytes(file_handle.read(2), byteorder='big')
    

    interleaved_DQT = None
    remaining_length = Lq - 2
    
    while remaining_length != 0:
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
            f"""\tQuantization Precision: {precision_strings[Pq]}\n"""
            f"""\tTable Identifier: {Tq}"""
        )

        DQT = np.zeros((8, 8))
        if (Pq == 0):
            interleaved_DQT = unpack(">64B", file_handle.read(64))
            remaining_length -= 64
        else:
            interleaved_DQT = unpack(">64H", file_handle.read(128))
            remaining_length -= 128
        for i in range(64):
            x, y = i // 8, i % 8
            DQT[x][y] = interleaved_DQT[interleaved_order[x][y]]
        DQTs[Tq] = DQT
def get_DHT(file_handle) -> List[Any]:
    pass
def read_jpeg(file_name: str):
    cnt = 0
    with open(file_name, "rb") as f:
        SOI_marker = f.read(2)
        if SOI_marker != b'\xFF\xD8':
            logger.error("incorrect SOI marker")
            exit()
        logger.debug(f"Correct SOI marker. Proceeding.")
        
        DQTs = [[] for _ in range(4)]
        DHT = None

        while (True):
            marker = f.read(2)
            if marker == b'\xFF\xE0':
                logger.debug(f"Correct APP0 Marker. Proceeding.")
                APP0_length = int.from_bytes(f.read(2), byteorder='big')
                logger.debug(f"APP0 length read as {APP0_length}")
                
                f.seek(-2, os.SEEK_CUR) # move back to start of APP0 header
                APP0 = f.read(APP0_length)
                
                APP0_length = int.from_bytes(APP0[0:2], byteorder='big')
                JFIF_identifier = APP0[2:7].decode('ascii')
                JFIF_major_ver = APP0[7]
                JFIF_minor_ver = APP0[8]
                units = APP0[9]
                Xdensity = int.from_bytes(APP0[10:12])
                Ydensity = int.from_bytes(APP0[12:14])
                Xthumbnail = APP0[14]
                Ythumbnail = APP0[15]

                if (JFIF_identifier != "JFIF\0"):
                    logger.warn(f"JFIF Identifier \"{JFIF_identifier}\" != \"JFIF\\0\"")
                if (JFIF_major_ver != 1):
                    logger.warn(f"JFIF Major Version {JFIF_major_ver} != 1")
                if not 0 <= JFIF_minor_ver <= 2:
                    logger.warn(f"JFIF Minor Version {JFIF_minor_ver} not in range .00-.02")
                if not 0 <= units <= 2:
                    logger.warn(f"Invalid units specifier {units}")


                unit_strings = ["pixels", "pixels/inch", "pixels/cm"]

                logger.debug(
                    f"APP0 Parsed as\n"
                    f"\tAPP0 length: {APP0_length}\n"
                    f"\tJFIF identifier: \"{JFIF_identifier}\"\n"
                    f"\tJFIF version: {JFIF_major_ver}.0{JFIF_minor_ver}\n"
                    f"\tX, Y units: {unit_strings[units]}\n"
                    f"\tXdensity: {Xdensity}\n"
                    f"\tYdensity: {Ydensity}\n"
                    f"\tXthumbnail: {Xthumbnail}\n"
                    f"\tYthumbnail: {Ythumbnail}"
                )
            elif marker == b'\xFF\xE1':
                logger.warning("EXIF detected! Header Parsing not supported!")
            elif marker == b'\xFF\xE2':
                logger.warning("EXIF detected! Header Parsing not supported")
            elif b'\xFF\xE0' <= marker <= b'\xFF\xEF':
                logger.warning("Unsupported APPn Type detected!")
            elif marker == b'\xFF\xDB':
                logger.debug("DQT marker found! Parsing DQT!")
                get_DQT(DQTs, f)
            elif marker == b'\xFF\xC4':
                DHT = get_DHT(f)
                logger.error("DHT marker found! DHT based encoding methods not supported!")
                exit()
            else:
                logger.error(f"Unsupported segment marker: \"{marker.hex()}\"!")
                raise NotImplementedError(f"Unsupported segment marker: \'{marker.hex(sep='\'').upper()}!")
        

        



parser = argparse.ArgumentParser()
parser.add_argument('filename')
args = parser.parse_args()
read_jpeg(args.filename)