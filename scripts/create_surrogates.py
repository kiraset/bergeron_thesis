import os
import csv

# ============================================================
# SETTINGS
# ============================================================

INPUT_FOLDER = "norm"
OUTPUT_FOLDER = "surrogates_norm"

SAMPLE_SIZE = 15000

TEXTS = {
    "mocquet_1617.txt": 4,   # 4 equal zones
    "pyrard_1619.txt": 8,    # 3 equal zones
}

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def make_surrogates(filename, number_of_zones):
    input_path = os.path.join(INPUT_FOLDER, filename)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    words = text.split()
    total_words = len(words)

    stem = os.path.splitext(filename)[0]

    print(f"\n{filename}")
    print(f"Total words: {total_words}")
    print(f"Zones: {number_of_zones}")

    metadata = []

    for i in range(number_of_zones):

        # Boundaries of the equal zone
        zone_start = round(i * total_words / number_of_zones)
        zone_end = round((i + 1) * total_words / number_of_zones)
        zone_length = zone_end - zone_start

        if zone_length < SAMPLE_SIZE:
            raise ValueError(
                f"{filename}: zone {i+1} contains only {zone_length} words, "
                f"which is shorter than SAMPLE_SIZE={SAMPLE_SIZE}."
            )

        # Take one contiguous 15,000-word sample from the centre of the zone
        spare_words = zone_length - SAMPLE_SIZE
        sample_start = zone_start + spare_words // 2
        sample_end = sample_start + SAMPLE_SIZE

        sample_words = words[sample_start:sample_end]

        # Human-readable positions are 1-based and inclusive
        first_word_position = sample_start + 1
        last_word_position = sample_end

        output_filename = f"{stem}_surrogate_{i+1}.txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(" ".join(sample_words))

        metadata.append({
            "source_file": filename,
            "surrogate": output_filename,
            "zone": i + 1,
            "zone_start_word": zone_start + 1,
            "zone_end_word": zone_end,
            "sample_start_word": first_word_position,
            "sample_end_word": last_word_position,
            "sample_size": SAMPLE_SIZE,
        })

        print(
            f"  Surrogate {i+1}: "
            f"zone {zone_start + 1}-{zone_end}; "
            f"sample {first_word_position}-{last_word_position}"
        )

    # Save exact positions for later rolling-stylometry control
    csv_path = os.path.join(OUTPUT_FOLDER, f"{stem}_surrogate_positions.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_file",
                "surrogate",
                "zone",
                "zone_start_word",
                "zone_end_word",
                "sample_start_word",
                "sample_end_word",
                "sample_size",
            ],
        )
        writer.writeheader()
        writer.writerows(metadata)

    print(f"Position table saved: {csv_path}")


# ============================================================
# RUN
# ============================================================

for filename, number_of_zones in TEXTS.items():
    make_surrogates(filename, number_of_zones)

print("\nDone!")
