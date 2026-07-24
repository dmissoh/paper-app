# Paper Golf Notepad Generator

Procedurally generates a printable pen-and-paper golf notepad as a PDF.
Each hole is a 3x5 inch dot-grid course with fairway, rough, sand traps,
water hazards, trees and slopes. All you need to play is a pen and a d6.

Inspired by [Paper Apps GOLF](https://gladdendesign.com/products/paper-apps-golf)
by Gladden Design. If you like this, buy the original notebook. The rules
summary included in the generated PDF is based on their
[official rule guide](https://docs.google.com/document/d/1eg96Ct-RBRHGt00zRe7YDVJfITB_qMgxPOLRiovpQuA/edit).

## What you get

A single PDF containing:

- Cover page
- Rules page with terrain legend
- Per course: a title page with a random course name, 6 mulligan
  checkboxes and a scorecard, followed by 18 randomly generated holes

Every hole is validated to be solvable: a path from tee to hole always
exists that avoids water and trees.

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Usage

```bash
./venv/bin/python generate_golf.py                          # random notebook
./venv/bin/python generate_golf.py --seed 42                # reproducible notebook
./venv/bin/python generate_golf.py --courses 1 --holes 9    # quick round
./venv/bin/python generate_golf.py --out my_notepad.pdf     # custom output name
./venv/bin/python generate_golf.py --selftest               # solvability check
```

The seed is printed on the cover, so any notebook can be regenerated.

## How to play (short version)

Roll a d6 and move the ball that many spaces in a straight line, in any
of the 8 directions. Add 1 when hitting from the fairway, subtract 1
from sand. You may always putt (move 1 space) instead. The ball may fly
over water but never land in it. Trees block shots unless you hit from
the fairway. Slope arrows push the ball 1 space. Par is 6 per hole.
Full rules are on the second page of the generated PDF.

## Printing

Pages are true 3x5 inch. Print 4-up on A4 or Letter from the print
dialog, cut the sheets, and clip or coil-bind them at the top.
