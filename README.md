# PDF Parse

Parse PDF to JSON that is easily consumable by other applications.

The motivation of this project is to parse a PDF into a JSON schema that
maintains the structure and hierarchy of the PDF. This means that text related
to a title is grouped together, and this can happen at multiple levels of the
JSON.

This tool utilizes style information such as color and font size to create
definitions for headers and paragraphs. The inspiration and foundation for this
approach was sampled from [here](https://towardsdatascience.com/extracting-headers-and-paragraphs-from-pdf-using-pymupdf-676e8421c467)

My use case is to translate D&D modules into structured JSON so I can then
import them as a directory based journal structure in my game.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

## Use

```bash
# usage: parse.py [-h] -i INPUT [-m MAX] [-r ROOT]
#
# Extract text from PDF
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -i INPUT, --input INPUT
#                         input file
#   -m MAX, --max MAX     max header
#   -r ROOT, --root ROOT  root header


# example
python3 parse.py --input=input/test.pdf --max=8 --root="h1"
```
