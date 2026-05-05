#!/usr/bin/env python3
"""
Extract NSIS installer by finding and decompressing zlib blocks.
"""
import sys
import zlib
import os

def extract_nsis(exe_path, output_dir):
    with open(exe_path, 'rb') as f:
        data = f.read()
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Find zlib-compressed blocks (starts with 0x78)
    pos = 0
    extracted = 0
    
    while pos < len(data) - 10:
        # Look for zlib header (0x78 0x01, 0x78 0x9C, 0x78 0xDA)
        if data[pos] == 0x78 and data[pos+1] in (0x01, 0x9C, 0xDA):
            try:
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                result = decompressor.decompress(data[pos:])
                if len(result) > 100:  # Only save if substantial
                    out_path = os.path.join(output_dir, f'block_{pos:08x}.bin')
                    with open(out_path, 'wb') as out:
                        out.write(result)
                    extracted += 1
                    print(f'Extracted block at 0x{pos:x}, size {len(result)}')
            except:
                pass
        pos += 1
    
    print(f'Total blocks extracted: {extracted}')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <exe_file> <output_dir>')
        sys.exit(1)
    extract_nsis(sys.argv[1], sys.argv[2])
