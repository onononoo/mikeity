"""
makes the site's favicons from a large photo.

    python tools/make_favicon.py [photo]

writes static/favicon.ico (16, 32 and 48 pixels, for every browser) and
static/favicon.png (180 pixels, for phones and bookmarks). the photo is
cropped to a square around its middle first, so a face stays readable even
at 16 pixels. needs pillow (pip install pillow). only run it when the photo
changes; the site build just copies the results.
"""

import os
import sys

from PIL import Image, ImageEnhance

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
default_photo = os.path.join(root, "monkeys-of-africa-featured-scaled-3137690517.webp")

# how much of the photo to keep around the center (1.0 = all of it)
zoom = 0.8


def square_crop(img, keep):
    w, h = img.size
    side = int(min(w, h) * keep)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def main(photo):
    img = Image.open(photo).convert("RGB")
    img = square_crop(img, zoom)
    # tiny icons look washed out, so add a little contrast and sharpness
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Sharpness(img).enhance(1.4)

    out = os.path.join(root, "static")
    ico = os.path.join(out, "favicon.ico")
    png = os.path.join(out, "favicon.png")
    img.save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    img.resize((180, 180), Image.LANCZOS).save(png, optimize=True)

    for path in (ico, png):
        print(f"wrote {os.path.relpath(path, root)} ({os.path.getsize(path):,} bytes)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else default_photo)
