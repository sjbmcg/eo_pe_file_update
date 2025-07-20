#!/usr/bin/env python3
"""
Sprite Sheet Slicer and update the egf file
how it works: python sprite_slicer.py <png_file> <egf1_file> <egf2_file> 
- only works on Windows + gfx013, gfx014 and gfx023
"""

import argparse
import sys
from PIL import Image
import pefile
import io
import ctypes
from ctypes import wintypes
kernel32 = ctypes.windll.kernel32
BeginUpdate = kernel32.BeginUpdateResourceW
BeginUpdate.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
BeginUpdate.restype = wintypes.HANDLE
UpdateRes = kernel32.UpdateResourceW
UpdateRes.argtypes = (wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.WORD, wintypes.LPVOID, wintypes.DWORD)
UpdateRes.restype = wintypes.BOOL
EndUpdate = kernel32.EndUpdateResourceW
EndUpdate.argtypes = (wintypes.HANDLE, wintypes.BOOL)
EndUpdate.restype = wintypes.BOOL

def MAKEINTRESOURCE(i: int) -> wintypes.LPCWSTR:
    return ctypes.cast(ctypes.c_void_p(i & 0xFFFF), wintypes.LPCWSTR)

def get_bitmap_ids(pe_path: str) -> list[int]:
    pe = pefile.PE(pe_path)
    try:
        ids = []
        if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if entry.id == pefile.RESOURCE_TYPE['RT_BITMAP']:
                    for id_entry in entry.directory.entries:
                        if id_entry.id is not None:
                            ids.append(id_entry.id)
        return sorted(set(ids))
    finally:
        pe.close()

def slice_sheet_to_images(img: Image.Image, sprite_w: int, sprite_h: int, start_x: int, start_y: int, 
                         gap_x: int, gap_y: int, rows: int, cols: int) -> list[dict]:
    frames = []
    step_x = sprite_w + gap_x
    step_y = sprite_h + gap_y

    for row in range(rows):
        for col in range(cols):
            if row == 3 and col == 5:
                break
            
            if row == 3 and col == 4:
                w, h = 49, 74
            else:
                w, h = sprite_w, sprite_h

            x = start_x + col * step_x
            y = start_y + row * step_y

            crop = img.crop((x, y, x + w, y + h)).convert('RGB')
            buf = io.BytesIO()
            crop.save(buf, format='BMP')
            data = buf.getvalue()
            dib = data[14:]
            frames.append({'img': crop, 'dib': dib})

        if row == 3:
            break

    extra_x, extra_y, extra_w, extra_h = 141, 311, 44, 39
    extra = img.crop((extra_x, extra_y, extra_x + extra_w, extra_y + extra_h)).convert('RGB')
    buf = io.BytesIO()
    extra.save(buf, format='BMP')
    data = buf.getvalue()
    frames.append({'img': extra, 'dib': data[14:]})

    return frames

def update_pe_with_bitmaps(pe_path: str, dibs: list[bytes], start_id: int):
    hupd = BeginUpdate(pe_path, False)
    if not hupd:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        rt_bitmap = MAKEINTRESOURCE(2)
        
        resource_ids = []
        for i in range(len(dibs)):
            resource_ids.append(start_id + i)
        
        for i, dib in enumerate(dibs):
            resource_id = resource_ids[i]
            name_id = MAKEINTRESOURCE(resource_id)
            buf = (ctypes.c_char * len(dib)).from_buffer_copy(dib)
            if not UpdateRes(hupd, rt_bitmap, name_id, 0x0409, buf, len(dib)):
                raise ctypes.WinError(ctypes.get_last_error())
                
        print(f"Resource IDs used: {resource_ids}")
    finally:
        if not EndUpdate(hupd, False):
            raise ctypes.WinError(ctypes.get_last_error())

def main():
    parser = argparse.ArgumentParser(description='Slice sprite sheet and update EGF files')
    parser.add_argument('png_file', help='PNG sprite sheet file')
    parser.add_argument('egf1_file', help='gfx013.egf file')
    parser.add_argument('egf2_file', help='gfx023.egf file')
    parser.add_argument('--sprite-width', type=int, default=34, help='Sprite width (default: 34)')
    parser.add_argument('--sprite-height', type=int, default=77, help='Sprite height (default: 77)')
    parser.add_argument('--start-x', type=int, default=1, help='Start X position (default: 1)')
    parser.add_argument('--start-y', type=int, default=1, help='Start Y position (default: 1)')
    parser.add_argument('--gap-x', type=int, default=1, help='Gap X between sprites (default: 1)')
    parser.add_argument('--gap-y', type=int, default=1, help='Gap Y between sprites (default: 1)')
    parser.add_argument('--rows', type=int, default=4, help='Number of rows (default: 4)')
    parser.add_argument('--cols', type=int, default=6, help='Number of columns (default: 6)')
    parser.add_argument('--gap1', type=int, default=29, help='Gap before new in gfx013 (default: 29)')
    parser.add_argument('--gap2', type=int, default=1, help='Gap before new in gfx023 (default: 1)')
    parser.add_argument('--first-count', type=int, help='Number of slices for gfx013 (auto-calculated if not specified)')
    parser.add_argument('--output1', default='gfx013_updated.egf', help='Output filename for gfx013 (default: gfx013_updated.egf)')
    parser.add_argument('--output2', default='gfx023_updated.egf', help='Output filename for gfx023 (default: gfx023_updated.egf)')
    
    args = parser.parse_args()

    if args.first_count is None:
        total_sprites = args.rows * args.cols
        args.first_count = min(total_sprites, 22)

    ids1 = get_bitmap_ids(args.egf1_file)
    ids2 = get_bitmap_ids(args.egf2_file)
    last1 = ids1[-1] if ids1 else 0
    last2 = ids2[-1] if ids2 else 0
    next1 = last1 + args.gap1
    next2 = last2 + args.gap2

    sheet = Image.open(args.png_file).convert('RGB')
    frames = slice_sheet_to_images(
        sheet, args.sprite_width, args.sprite_height,
        args.start_x, args.start_y, args.gap_x, args.gap_y,
        args.rows, args.cols
    )
    
    dibs = [f['dib'] for f in frames]
    
    to1 = dibs[:args.first_count]
    to2 = dibs[args.first_count:]

    if to1:
        print(f"Creating {args.output1} with {len(to1)} sprites...")
        with open(args.egf1_file, 'rb') as f:
            with open(args.output1, 'wb') as out:
                out.write(f.read())
        update_pe_with_bitmaps(args.output1, to1, next1)

    if to2:
        print(f"Creating {args.output2} with {len(to2)} sprites...")
        with open(args.egf2_file, 'rb') as f:
            with open(args.output2, 'wb') as out:
                out.write(f.read())
        update_pe_with_bitmaps(args.output2, to2, next2)

    print("Done!")

if __name__ == '__main__':
    main()