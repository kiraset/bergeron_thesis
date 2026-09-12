from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET

BASE_FOLDER = Path(__file__).resolve().parent
INPUT_FOLDER = BASE_FOLDER / "bignon"
OUTPUT_FOLDER = BASE_FOLDER / "bignon_cut_simple"

# "parity": even filename page numbers = left margin; odd = right margin.
# Or set manually to "left" or "right".
MARGIN_SIDE = "parity"

# Maximum horizontal movement per unit of vertical movement.
MAX_SLOPE = 0.15

# Ignore very short almost-vertical fragments.
# A candidate must cover at least this fraction of the TextBlock height.
# Example: 0.08 means at least 8% of the block height.
MIN_FRAGMENT_HEIGHT_RATIO = 0.08

OUTWARD_PADDING = 0

URI = "http://www.loc.gov/standards/alto/ns-v4#"
NS = {"alto": URI}
ET.register_namespace("", URI)


def get_points(polygon):
    tokens = polygon.attrib.get("POINTS", "").replace(",", " ").split()
    if len(tokens) % 2:
        raise ValueError("Odd number of polygon coordinates")
    values = [float(token) for token in tokens]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Non-finite polygon coordinate")
    points = list(zip(values[::2], values[1::2]))
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(set(points)) < 4:
        raise ValueError("Fewer than four distinct polygon points")
    return points


def find_vertical_stretches(points, side, middle_x, region_height):
    """Find almost-vertical polygon edges only in the margin-facing half."""
    stretches = []

    for index in range(len(points)):
        first_point = points[index]
        second_point = points[(index + 1) % len(points)]

        if first_point[1] > second_point[1]:
            first_point, second_point = second_point, first_point

        top_x, top_y = first_point
        bottom_x, bottom_y = second_point

        vertical_distance = bottom_y - top_y
        horizontal_distance = abs(bottom_x - top_x)

        if vertical_distance == 0:
            continue

        # Ignore tiny vertical fragments that could be accidental polygon edges.
        if vertical_distance < region_height * MIN_FRAGMENT_HEIGHT_RATIO:
            continue

        if side == "left":
            on_correct_side = max(top_x, bottom_x) < middle_x
        else:
            on_correct_side = min(top_x, bottom_x) > middle_x

        if not on_correct_side:
            continue

        if horizontal_distance / vertical_distance <= MAX_SLOPE:
            stretches.append((first_point, second_point))

    return stretches


def mean_x(stretch):
    (top_x, _), (bottom_x, _) = stretch
    return (top_x + bottom_x) / 2


def vertical_length(stretch):
    (_, top_y), (_, bottom_y) = stretch
    return bottom_y - top_y


def choose_innermost_stretch(stretches, side):
    """Choose the candidate closest to the main text area."""
    if not stretches:
        raise ValueError("No almost-vertical edge on the selected side")

    if side == "left":
        # Main text lies to the right, so choose the rightmost candidate.
        return max(
            stretches,
            key=lambda stretch: (mean_x(stretch), vertical_length(stretch))
        )
    else:
        # Main text lies to the left, so choose the leftmost candidate.
        return min(
            stretches,
            key=lambda stretch: (mean_x(stretch), -vertical_length(stretch))
        )


def x_on_stretch_line(stretch, y):
    """Extend the chosen stretch as a straight line and get X at Y."""
    (top_x, top_y), (bottom_x, bottom_y) = stretch
    vertical_distance = bottom_y - top_y
    if vertical_distance == 0:
        raise ValueError("Chosen edge has no vertical extent")
    slope = (bottom_x - top_x) / vertical_distance
    return top_x + slope * (y - top_y)


def reconstruct(points, side):
    left = min(x for x, _ in points)
    right = max(x for x, _ in points)
    top = min(y for _, y in points)
    bottom = max(y for _, y in points)

    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise ValueError("Empty bounding box")

    middle_x = (left + right) / 2

    # 1. Search only the half where marginalia occur.
    stretches = find_vertical_stretches(points, side, middle_x, height)

    # 2. Pick the candidate closest to the main text.
    chosen = choose_innermost_stretch(stretches, side)

    # 3. Extend that candidate to the original top and bottom Y coordinates.
    top_x = x_on_stretch_line(chosen, top)
    bottom_x = x_on_stretch_line(chosen, bottom)

    if side == "left":
        top_x -= OUTWARD_PADDING
        bottom_x -= OUTWARD_PADDING
    else:
        top_x += OUTWARD_PADDING
        bottom_x += OUTWARD_PADDING

    top_x = round(top_x)
    bottom_x = round(bottom_x)
    top = math.floor(top)
    bottom = math.ceil(bottom)

    # 4. Keep the opposite side simple using its original extreme X.
    if side == "left":
        right = math.ceil(right)
        if max(top_x, bottom_x) >= right:
            raise ValueError("Estimated boundary collapses the region")
        corners = [
            (top_x, top),
            (right, top),
            (right, bottom),
            (bottom_x, bottom),
        ]
    else:
        left = math.floor(left)
        if min(top_x, bottom_x) <= left:
            raise ValueError("Estimated boundary collapses the region")
        corners = [
            (left, top),
            (top_x, top),
            (bottom_x, bottom),
            (left, bottom),
        ]

    return corners, chosen, stretches


def process_textblock(block, side):
    polygon = block.find("alto:Shape/alto:Polygon", NS)
    if polygon is None:
        raise ValueError("No direct TextBlock polygon")

    new_points, chosen, candidates = reconstruct(get_points(polygon), side)

    polygon.set(
        "POINTS",
        " ".join(f"{x} {y}" for x, y in new_points)
    )

    xs, ys = zip(*new_points)
    block.set("HPOS", str(min(xs)))
    block.set("VPOS", str(min(ys)))
    block.set("WIDTH", str(max(xs) - min(xs)))
    block.set("HEIGHT", str(max(ys) - min(ys)))

    print(f"    {side.upper()}: {len(candidates)} candidate vertical edge(s)")
    print(f"    chosen edge: {chosen[0]} -> {chosen[1]}")
    print(f"    POINTS: {polygon.get('POINTS')}")


def main():
    if MARGIN_SIDE not in {"parity", "left", "right"}:
        raise SystemExit('MARGIN_SIDE must be "parity", "left", or "right"')
    if INPUT_FOLDER.resolve() == OUTPUT_FOLDER.resolve():
        raise SystemExit("Input and output folders must be different")
    if not INPUT_FOLDER.is_dir():
        raise SystemExit(f"Input folder not found: {INPUT_FOLDER}")

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    changed = 0
    skipped = 0
    files = sorted(
        path for path in INPUT_FOLDER.iterdir()
        if path.suffix.lower() == ".xml"
    )

    for path in files:
        side = MARGIN_SIDE

        if side == "parity":
            match = re.search(r"_page(\d+)\.xml$", path.name, re.IGNORECASE)
            if not match:
                print(f"SKIP FILE (no _pageNUMBER suffix): {path.name}")
                continue
            page_number = int(match.group(1))
            side = "left" if page_number % 2 == 0 else "right"

        print(f"\nProcessing: {path.name}")

        try:
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
            tree = ET.parse(path, parser=parser)
        except (ET.ParseError, OSError) as error:
            print(f"  SKIP FILE: {error}")
            continue

        blocks = tree.getroot().findall(".//alto:TextBlock", NS)

        for number, block in enumerate(blocks, 1):
            print(f"  TextBlock {number} ({block.get('ID', 'no ID')})")
            try:
                process_textblock(block, side)
                changed += 1
            except ValueError as error:
                skipped += 1
                print(f"    UNCHANGED: {error}")

        tree.write(
            OUTPUT_FOLDER / path.name,
            encoding="UTF-8",
            xml_declaration=True
        )

    print(f"\nDone. Changed blocks: {changed}; unchanged blocks: {skipped}.")
    print(f"Output: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
