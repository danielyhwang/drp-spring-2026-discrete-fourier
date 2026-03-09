# README


## jpeg_encoder.py
Contains ```bmp_parser()```, ```rgb_to_ycbcr()```, etc.
### ```bmp_parser()```
* Only supports compression methods BI_RGB and BI_BITFIELDS
### ```rgb_to_ycbcr()```
* Ignores alpha channels
* Returns data in Non-interleaved data ordering as specified by JPEG Standard Section A.2.2


### test images
2x2.bmp
* has alpha channel, but all alpha=255

4x2.bmp
* has alpha channel; some rows are alpha=127