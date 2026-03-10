from collections import defaultdict

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