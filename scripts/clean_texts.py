import os
import re
from pathlib import Path

# === FOLDERS ===
INPUT_FOLDER = "no_norm"
OUTPUT_FOLDER = "norm"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)



SOURCE_REPLACEMENTS = {
    "bignon_1610": [
        "DE L’EXCELLENCE",
        "DE LA FRANCE",
        "DE L’EXCEL. DES ROYS",
        "DE L’EXCEL. DESROYS",
        "ET DV ROYAVME DE FRANCE",
    ],

    "coulon_1643": [
        "L’Vlysse",
        "L’Ulysse",
        "L'Vlysse",
        "Gallo-Belgique",
        "Gallo-belgique",
        "Callo-Belgique",
        "Callo-belgique",
    ],

    "mocquet_1617": [
        "LIVRE IIIII",
        "LIVRE IIII",
        "LIVRE III",
        "LIVRE II",
        "LIVRE I",
        "LIVRE VI",
        "LIVRE V",
        "iiij",
        "iij",
        "ij",
        "VOYAGES DE IEAN MOCQVET",
        "VOYACES DE IEAN MOCQVET",
        "VOYACES DE JEAN MOCQVET",
        "AVANT-PROPOS",
        "PREFACE",
        "Voyages d’Affrique",
        "Voyages d'Affrique",
        "du sieur de Razilly",
        "Du sieur de Razilly",
        "du sieur de Raz illy",
    ],

    "pyrard_1611": [
        "VOYAGE DES FRANCOIS",
        "AVX INDES ORIENTALES",
        "AVXINDES ORIENTALES",
        "AVX INDESORIENTALES",
        "TRAITE' DES ANIMAVX",
        "ARB.ET FRVITS DESINDES",
        "ARB.ET FRVITS DES INDES",
        "ARB. ET FRVITS DES INDES",
    ],

    "pyrard_1619": [
        "YOYAGE DE",
        "FRANÇOIS PYRARD",
        "VOYAGE DE",
        "VOYACE DE",
        "YACE DE",
        "OYAGEDE",
        "OYAGE DE",
        "Traité des Animaux",
        "Arbres, & fruicts des Indes",
        "Aduis pour aller",
    ],

    "leblanc_1634": [
        "du sieur Vincent le Blanc",
        "Les Voyages",
        "III. Partie.",
        "II. Partie.",
    ],

    "leblanc_1649": [
        "du sieur Vincent le Blanc",
        "Les Voyages",
        "III. Partie.",
        "II. Partie.",
    ],

    "bergeron_1629": [
        "TRAICTE",
        "DES NAVIGATIONS",
    ],

    "bergeron_2005": [
    ],

    "martin_1604": [
    ],
}


# ============================================================
# DOCUMENTS IN WHICH THE OLD SCRIPTS REMOVED LINES CONTAINING
# ROMAN PAGE-NUMBER FORMS BEFORE THE I/J NORMALIZATION
# ============================================================

# Roman-number lines are removed from every text before i/j harmonization.
REMOVE_ROMAN_NUMBER_LINES_FOR_ALL = True


# ============================================================
# FRENCH PRONOUNS USED BY STYLO, AFTER THE SAME GRAPHEMIC
# REGULARIZATION APPLIED TO THIS CORPUS:
#
# je -> ie
# tu -> tv
# lui -> lvi
# nous -> novs
# vous -> vovs
# leur -> levr
# eux -> evx
# ============================================================

PRONOUNS = {
    "ie", "me", "moi",
    "tv", "te", "toi",
    "il", "elle", "le", "la", "lvi",
    "se", "soi",
    "novs", "vovs",
    "ils", "elles", "les", "levr", "evx",
}


def source_key(filename):
    """Return the exact corpus key based on the filename stem."""
    stem = Path(filename).stem.lower()

    valid_keys = {
        "bignon_1610",
        "coulon_1643",
        "mocquet_1617",
        "pyrard_1611",
        "pyrard_1619",
        "leblanc_1634",
        "leblanc_1649",
        "bergeron_1629",
        "bergeron_2005",
        "martin_1604",
    }

    if stem not in valid_keys:
        raise ValueError(f"Unexpected corpus filename: {filename}")

    return stem


def clean_text(text, filename):

    key = source_key(filename)

    # --------------------------------------------------
    # 1. Remove source-specific lines containing old
    #    Roman page-number forms, where this was done
    #    in the original individual scripts.
    #    This must happen BEFORE j -> i.
    # --------------------------------------------------

    if REMOVE_ROMAN_NUMBER_LINES_FOR_ALL:
        text = re.sub(
            r"^.*(?:ij|iij|iiij).*$\n?",
            "",
            text,
            flags=re.MULTILINE
        )

    # --------------------------------------------------
    # 2. Remove recurrent source-specific running headers
    #    and page furniture before general normalization.
    # --------------------------------------------------

    for old in SOURCE_REPLACEMENTS.get(key, []):
        text = text.replace(old, "")

    # --------------------------------------------------
    # 2b. Bergeron 2005: remove every whitespace-delimited token
    #     containing "/"
    # --------------------------------------------------

    if key == "bergeron_2005":
        text = re.sub(r"\S*/\S*", " ", text)

    # --------------------------------------------------
    # 3. Handle OCR line-break marker and physical lines
    # --------------------------------------------------

    # If ¬ occurs at the end of a line, join the broken word.
    text = re.sub(r"¬\s*\n", "", text)

    # All remaining physical line breaks become spaces.
    text = text.replace("\n", " ")

    # Remove any remaining ¬.
    text = text.replace("¬", "")

    # --------------------------------------------------
    # 4. Harmonize ampersand and apostrophes
    # --------------------------------------------------

    text = text.replace("&", " et ")

    # Apostrophes become spaces so elided forms are tokenized separately.
    text = re.sub(r"[’']", " ", text)

    # --------------------------------------------------
    # 5. Expand recurrent isolated elided forms and
    #    correct recurrent token forms
    # --------------------------------------------------

    text = text.replace(" avecq ", " avec ")
    text = text.replace(" d ", " de ")
    text = text.replace(" n ", " ne ")
    text = text.replace(" s ", " se ")
    text = text.replace(" m ", " me ")
    text = text.replace(" c ", " ce ")
    text = text.replace(" qv ", " qve ")
    text = text.replace(" i ", " ")
    text = text.replace(" l ", " ")

    # --------------------------------------------------
    # 6. Historical graphemic regularization
    # --------------------------------------------------

    text = text.replace("y", "i")
    text = text.replace("Y", "I")

    text = text.replace("z", "s")
    text = text.replace("Z", "s")

    text = text.replace("u", "v")
    text = text.replace("U", "v")

    text = text.replace("j", "i")
    text = text.replace("J", "i")

    # --------------------------------------------------
    # 7. Remove numbers
    # --------------------------------------------------

    text = re.sub(r"\d+", "", text)

    # --------------------------------------------------
    # 8. Remove punctuation and underscores
    # --------------------------------------------------

    # Keep Unicode letters/digits/underscore and whitespace first;
    # digits are already removed above.
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = text.replace("_", "")

    # --------------------------------------------------
    # 9. Lowercase and normalize whitespace
    # --------------------------------------------------

    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()

    # --------------------------------------------------
    # 10. Delete the French pronouns used by stylo,
    #     converted to the corpus's regularized spelling.
    # --------------------------------------------------

    words = text.split()
    words = [word for word in words if word not in PRONOUNS]
    text = " ".join(words)

    return text


# ============================================================
# PROCESS ALL TXT FILES
# ============================================================

for filename in sorted(os.listdir(INPUT_FOLDER)):

    if not filename.lower().endswith(".txt"):
        continue

    input_path = os.path.join(INPUT_FOLDER, filename)
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    cleaned_text = clean_text(text, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    print(f"Cleaned: {filename}")

print("\nDone!")
