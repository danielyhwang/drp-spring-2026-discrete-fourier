import argparse
import logging
import os
from typing import List, Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s' # Optional: makes the output cleaner
)

def write_bmp():
    pass


def get_DQT(file_handle) -> List[Any]:
    pass
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
        
        DQT = None
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
                    logger.warn(f"JFIF Minor Version {JFIF_minor_ver} not in range 0-2")
                if not 0 <= units <= 2:
                    logger.warn(f"Invalid units specifier {units}")


                unit_strings = ["pixels", "pixels/inch", "pixels/cm"]

                logger.debug(
                    f"APP0 Parsed as\n"
                    f"    APP0 length: {APP0_length}\n"
                    f"    JFIF identifier: \"{JFIF_identifier}\"\n"
                    f"    JFIF version: {JFIF_major_ver}.0{JFIF_minor_ver}\n"
                    f"    X, Y units: {unit_strings[units]}\n"
                    f"    Xdensity: {Xdensity}\n"
                    f"    Ydensity: {Ydensity}\n"
                    f"    Xthumbnail: {Xthumbnail}\n"
                    f"    Ythumbnail: {Ythumbnail}"
                )
            elif marker == b'\xFF\xE1':
                logger.warning("EXIF detected! Header Parsing not supported!")
            elif marker == b'\xFF\xE2':
                logger.warning("EXIF detected! Header Parsing not supported")
            elif b'\xFF\xE0' <= marker <= b'\xFF\xEF':
                logger.warning("Unsupported APPn Type detected!")
            elif marker == b'\xFF\xDB':
                logger.debug("DQT marker found! Parsing DQT!")
                DQT = get_DQT(f)
            elif marker == b'\xFF\xC4':
                DHT = get_DHT(f)
                logger.debug("DHT marker found! Parsing DHT!")
            else:
                logger.error(f"Unsupported segment marker: \"{marker.hex()}\"!")
                raise NotImplementedError(f"Unsupported segment marker: \'{marker.hex(sep='\'').upper()}!")
        

        



parser = argparse.ArgumentParser()
parser.add_argument('filename')
args = parser.parse_args()
print(args.filename)
read_jpeg(args.filename)