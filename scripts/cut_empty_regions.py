import os
import xml.etree.ElementTree as ET


# ============================================================
# SETTINGS
# ============================================================

INPUT_FOLDER = "bignon_almost"
OUTPUT_FOLDER = "bignon_blocks_clean"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================
# ALTO NAMESPACE
# ============================================================

ET.register_namespace(
    '',
    'http://www.loc.gov/standards/alto/ns-v4#'
)

NS = {
    'alto': 'http://www.loc.gov/standards/alto/ns-v4#'
}


# ============================================================
# FIND PARENT ELEMENT
# ============================================================

def find_parent(root, target):

    for parent in root.iter():

        for child in list(parent):

            if child is target:
                return parent

    return None


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(
    input_path,
    output_path
):

    tree = ET.parse(
        input_path
    )

    root = tree.getroot()


    # ========================================================
    # FIND ALL TEXTBLOCKS
    # ========================================================

    textblocks = root.findall(
        ".//alto:TextBlock",
        NS
    )

    if not textblocks:

        print(
            f"No TextBlocks: "
            f"{os.path.basename(input_path)}"
        )

        return


    # ========================================================
    # IDENTIFY BAD TEXTBLOCKS
    # ========================================================

    bad_blocks = []

    for textblock in textblocks:

        width = float(
            textblock.attrib.get(
                "WIDTH",
                0
            )
        )

        if width < 500:

            bad_blocks.append(
                textblock
            )


    if not bad_blocks:

        tree.write(
            output_path,
            encoding="UTF-8",
            xml_declaration=True
        )

        return


    print(
        f"  Found {len(bad_blocks)} "
        f"TextBlock(s) with WIDTH < 500"
    )


    # ========================================================
    # PROCESS BAD TEXTBLOCKS
    # ========================================================

    for bad_block in bad_blocks:

        # ----------------------------------------------------
        # Find its position in the original TextBlock list
        # ----------------------------------------------------

        bad_index = textblocks.index(
            bad_block
        )


        # ----------------------------------------------------
        # Find previous GOOD TextBlock
        # ----------------------------------------------------

        target_block = None

        for i in range(
            bad_index - 1,
            -1,
            -1
        ):

            candidate = textblocks[i]

            if candidate in bad_blocks:
                continue

            target_block = candidate
            break


        # ----------------------------------------------------
        # If there is no previous good block,
        # find the next good block
        # ----------------------------------------------------

        if target_block is None:

            for i in range(
                bad_index + 1,
                len(textblocks)
            ):

                candidate = textblocks[i]

                if candidate in bad_blocks:
                    continue

                target_block = candidate
                break


        # ----------------------------------------------------
        # Get lines
        # ----------------------------------------------------

        textlines = bad_block.findall(
            ".//alto:TextLine",
            NS
        )


        bad_id = bad_block.attrib.get(
            "ID",
            "[no ID]"
        )


        # ----------------------------------------------------
        # If a good TextBlock exists, move the lines
        # ----------------------------------------------------

        if target_block is not None:

            target_id = target_block.attrib.get(
                "ID",
                "[no ID]"
            )

            print(
                f"  Deleting {bad_id}: "
                f"moving {len(textlines)} "
                f"TextLine(s) to {target_id}"
            )


            for textline in textlines:

                parent = find_parent(
                    root,
                    textline
                )

                if parent is not None:

                    parent.remove(
                        textline
                    )

                    target_block.append(
                        textline
                    )


        else:

            print(
                f"  Deleting {bad_id}: "
                f"no good TextBlock available"
            )


        # ----------------------------------------------------
        # Remove bad TextBlock
        # ----------------------------------------------------

        parent = find_parent(
            root,
            bad_block
        )

        if parent is not None:

            parent.remove(
                bad_block
            )


    # ========================================================
    # SAVE
    # ========================================================

    tree.write(
        output_path,
        encoding="UTF-8",
        xml_declaration=True
    )


# ============================================================
# PROCESS ALL XML FILES
# ============================================================

for filename in sorted(
    os.listdir(INPUT_FOLDER)
):

    if not filename.lower().endswith(".xml"):
        continue


    print(
        f"\nProcessing: {filename}"
    )


    input_path = os.path.join(
        INPUT_FOLDER,
        filename
    )

    output_path = os.path.join(
        OUTPUT_FOLDER,
        filename
    )


    process_file(
        input_path,
        output_path
    )


print("\nDone!")