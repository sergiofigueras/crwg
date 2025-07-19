#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import bz2
import codecs
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter

from tqdm import tqdm
from transliterate import translit
from transliterate.base import TranslitLanguagePack, registry
from transliterate.discover import autodiscover


__author__  = "Igor Ivanov, @lctrcl"
__license__ = "GPL"
__version__ = "0.4"
__banner__  = f"Custom Russian Wordlists Generator {__version__}"

dictionary_urls = {
    "ruscorpora":  "https://ruscorpora.ru/new/ngrams/1grams-3.zip",
    "opencorpora": "https://opencorpora.org/files/export/dict/dict.opcorpora.txt.bz2",
}


# --------------------------------------------------------------------------- #
# Argument parser with nicer error handling
# --------------------------------------------------------------------------- #
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"error: {message}\n")
        self.print_help()
        sys.exit(2)


# --------------------------------------------------------------------------- #
# Transliteration helpers
# --------------------------------------------------------------------------- #
autodiscover()      # discover installed language packs

class ReverseInverseRussianLanguagePack(TranslitLanguagePack):
    """‘ru_inv_en’ – teclado russo digitado em layout QWERTY inglês."""
    language_code = "ru_inv_en"
    language_name = "ru_inv_en"
    mapping = (
        "йцукенгшщзхъфывапролджэёячсмитьбю",
        "qwertyuiop[]asdfghjkl;'\\zxcvbnm,.",
    )

registry.register(ReverseInverseRussianLanguagePack)


# --------------------------------------------------------------------------- #
# Helper for urllib reporting
# --------------------------------------------------------------------------- #
def _reporthook(numblocks, blocksize, filesize, url=None):
    base = os.path.basename(url)
    try:
        percent = min((numblocks * blocksize * 100) / filesize, 100)
    except Exception:
        percent = 100
    if numblocks != 0:
        sys.stdout.write("\b" * 70)
        sys.stdout.write("%-66s%3d%%" % (base, percent))


# --------------------------------------------------------------------------- #
# STEP 1 – download and unpack the chosen corpus
# --------------------------------------------------------------------------- #
def downloaddictionaries(dictionary_strings: str):
    url = dictionary_urls[dictionary_strings]

    try:
        print(f"[*] Downloading {dictionary_strings} dictionary")
        name, _ = urllib.request.urlretrieve(
            url,
            os.path.basename(url),
            lambda nb, bs, fs, url=url: _reporthook(nb, bs, fs, url),
        )
    except IOError as e:
        print(f"Can't retrieve {url!r}: {e}")
        return

    # -- ruscorpora: ZIP ----------------------------------------------------- #
    if dictionary_strings == "ruscorpora":
        try:
            print(f"[*] Extracting {dictionary_strings} dictionary")
            z = zipfile.ZipFile(os.path.basename(url))
        except zipfile.BadZipFile as e:
            print(f"Bad zipfile (from {url!r}): {e}")
            return

        for n in z.namelist():
            print(n)
            dest = os.path.join("./", n)
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
            with open(dest, "wb") as f:
                f.write(z.read(n))
        z.close()
        os.unlink(name)

    # -- opencorpora: .bz2 --------------------------------------------------- #
    elif dictionary_strings == "opencorpora":
        print(f"[*] Extracting {dictionary_strings} dictionary")
        uncompresseddata = bz2.BZ2File(os.path.basename(url)).read()
        zname = os.path.splitext(os.path.basename(url))[0]
        with open(zname, "wb") as f:
            f.write(uncompresseddata)


# --------------------------------------------------------------------------- #
# STEP 2 – strip non‑Cyrillic symbols, short words, etc.
# Fixed:   • trata linhas vazias/malformed → sem IndexError
#          • nome de saída corrigido (f‑string)
# --------------------------------------------------------------------------- #
def autoclean(dictionary_strings: str):
    print(f"[*] Autocleaning {dictionary_strings} dictionary")

    # Arquivo‑fonte
    if dictionary_strings == "opencorpora":
        name = os.path.splitext(os.path.basename(dictionary_urls[dictionary_strings]))[0]
        idx  = 0            # palavra na 1.ª coluna
    else:  # ruscorpora
        name = f"{os.path.splitext(os.path.basename(dictionary_urls[dictionary_strings]))[0]}.txt"
        idx  = 1            # palavra na 2.ª coluna

    regex = re.compile(r"[a-zA-Z0-9_]")      # remove latinos/dígitos/_

    out_name = f"{dictionary_strings}_dict_stripped"
    kept = 0

    with codecs.open(name, "r", "utf-8") as fin, \
         codecs.open(out_name, "w", "utf-8") as fout:

        for line in fin:
            if not line.strip():             # ignora linhas vazias
                continue
            parts = line.split()
            if len(parts) <= idx:            # ignora linhas mal‑formadas
                continue

            word = parts[idx]
            if regex.search(word) or len(word) <= 3:
                continue

            fout.write(word.lower() + "\n")
            kept += 1

    print(f"[*] Saved {kept} clean words to {out_name}")


# --------------------------------------------------------------------------- #
# STEP 3 – generate derived dictionaries (translit, ru_inv_en, …)
# --------------------------------------------------------------------------- #
def generatedictionary(source: str, destination: str, gendic: str):
    with codecs.open(source, "r", "utf-8") as f:
        lines = f.read().splitlines()

    print(f"[*] Making {gendic} dictionary: ")

    if gendic == "tran5l1t":
        print("Not implemented yet")
        return

    with codecs.open(destination, "a+", "utf-8") as myfile:
        if gendic == "translit":
            for line in tqdm(lines):
                myfile.write(f"{translit(str(line), 'ru', reversed=True)}\n")

        elif gendic == "ru_inv_en":
            for line in tqdm(lines):
                myfile.write(f"{translit(str(line), gendic)}\n")


# --------------------------------------------------------------------------- #
# STEP 4 – compare with leaked password bases
# --------------------------------------------------------------------------- #
def compare_two_password_bases(source: str, destination: str, dictionary: str):
    with codecs.open(source, "r", "utf-8") as f:
        leaked_passwords = f.read().splitlines()

    with codecs.open(dictionary, "r", "utf-8") as content_file:
        translit_dictionary = content_file.read().splitlines()

    print("[*] Generating statistics: ")
    s   = set(translit_dictionary)
    b3  = [val for val in tqdm(leaked_passwords) if val in s]
    cnt = Counter(b3)

    print("[*] Writing to file: ")
    with codecs.open(destination, "w+", "utf-8") as myfile:
        for k, v in cnt.most_common():
            myfile.write(f"{v} {k} {translit(k, 'ru_inv_en', reversed=True)}\n")

    print("Done")


# --------------------------------------------------------------------------- #
# Entry‑point / CLI
# --------------------------------------------------------------------------- #
def main():
    parser = MyParser(
        description=__banner__,
        epilog=(
            "Usage examples:\n"
            "  python crwg.py --downloaddictionaries ruscorpora --autoclean\n"
            "  python crwg.py -g ru_inv_en -s source.txt -d dest.txt\n"
            "  python crwg.py -c -s leaked.txt -d stats.txt --dictionary opencorpora_dict_stripped_ru_inv_en\n"
        ),
    )

    parser.add_argument(
        "--gendic", "-g",
        choices=["ru_inv_en", "translit", "tran5l1t"],
        help="Generate dictionary from file",
    )
    parser.add_argument(
        "--downloaddictionaries",
        choices=["ruscorpora", "opencorpora"],
        help="Download corpus and unpack",
    )
    parser.add_argument(
        "--autoclean",
        action="store_true",
        help="Autoclean downloaded dictionaries (remove English chars, digits, etc.)",
    )
    parser.add_argument("--source",      "-s", help="Source file")
    parser.add_argument("--destination", "-d", help="Destination file")
    parser.add_argument("--dictionary",          help="Dictionary file (for comparisons)")
    parser.add_argument(
        "--compare_two_password_bases", "-c",
        action="store_true",
        help="Compare two password files",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    print(__banner__)

    # --- workflow orchestration ------------------------------------------- #
    if args.downloaddictionaries:
        downloaddictionaries(args.downloaddictionaries)

    if args.autoclean:
        if not args.downloaddictionaries:
            parser.error("--autoclean requires --downloaddictionaries")
        autoclean(args.downloaddictionaries)

    if args.gendic:
        if not (args.source and args.destination):
            parser.error("--gendic requires --source and --destination")
        generatedictionary(args.source, args.destination, args.gendic)

    if args.compare_two_password_bases:
        if not (args.source and args.destination and args.dictionary):
            parser.error(
                "-c requires -s <leaked_pw_file> -d <stats_file> --dictionary <dict>"
            )
        compare_two_password_bases(args.source, args.destination, args.dictionary)


if __name__ == "__main__":
    main()
