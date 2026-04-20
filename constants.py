from collections import defaultdict
from enum import Enum

JFIF_unit_strings = ["pixels", "pixels/inch", "pixels/cm"]
SOF_type_strings = defaultdict(lambda: "Unknown SOF type", {
    0: "Baseline DCT", 
    1: "Extended sequential DCT, Huffman coding", 
    2: "Progressive DCT, Huffman coding", 
    3: "Lossless (sequential), Huffman coding",
    9: "Extended sequential DCT, arithmetic coding",
    10: "Progressive DCT, arithmetic coding",
    11: "Lossless (sequential), arithmetic coding"
})
interleaved_order =  [[0, 1, 5, 6, 14, 15, 27, 28],
                      [2, 4, 7, 13, 16, 26, 29, 42],
                      [3, 8, 12, 17, 25, 30, 41, 43],
                      [9, 11, 18, 24, 31, 40, 44, 53],
                      [10, 19, 23, 32, 39, 45, 52, 54],
                      [20, 22, 33, 38, 46, 51, 55, 60],
                      [21, 34, 37, 47, 50, 56, 59, 61],
                      [35, 36, 48, 49, 57, 58, 62, 63]]

DQT_PRECISION_8_BIT = 0
DQT_PRECISION_16_BIT = 1

DQT_PRECISION_STRINGS = {
    DQT_PRECISION_8_BIT : "8-bit",
    DQT_PRECISION_16_BIT: "16-bit"
}

TABLE_CLASS_STRINGS = {
    0: "DC or lossless table",
    1: "AC table"
}