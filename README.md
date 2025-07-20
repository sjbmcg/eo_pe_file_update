# Sprite Sheet Slicer

Slices PNG sprite sheets and embeds sprites as bitmap resources into EGF files. Windows only.

## Usage

```bash
pip install -r requirements.txt
python sprite_slicer.py <png_file> <egf1_file> <egf2_file>
```

Default: 34×77px sprites, 4×6 grid, first 22 to gfx013, rest to gfx023.

Use `--help` for options.