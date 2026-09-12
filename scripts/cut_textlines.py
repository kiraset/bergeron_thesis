import os
import re
import xml.etree.ElementTree as ET


# ============================================================
# SETTINGS
# ============================================================

INPUT_FOLDER = "bignon_blocks_clean"
OUTPUT_FOLDER = "bignon_lines_cut_sloped"

# Lines narrower than this are treated as independent marginal notes.
SHORT_LINE_LIMIT = 450

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================
# ALTO NAMESPACE
# ============================================================

ALTO_NAMESPACE = "http://www.loc.gov/standards/alto/ns-v4#"
ET.register_namespace("", ALTO_NAMESPACE)
NS = {"alto": ALTO_NAMESPACE}


# ============================================================
# READ AND WRITE COORDINATES
# ============================================================

def read_coordinates(text):
    """Convert '100 200 300 400' into [(100, 200), (300, 400)]."""

    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)

    if len(numbers) % 2 != 0:
        raise ValueError("Odd number of coordinates")

    return [
        (float(numbers[i]), float(numbers[i + 1]))
        for i in range(0, len(numbers), 2)
    ]


def format_number(value):
    """Write 500.0 as '500', but retain a real decimal such as 500.25."""

    if float(value).is_integer():
        return str(int(value))
    return str(round(value, 6)).rstrip("0").rstrip(".")


def coordinates_to_string(points):
    return " ".join(
        f"{format_number(x)} {format_number(y)}"
        for x, y in points
    )


def get_baseline_points(textline):
    baseline = textline.attrib.get("BASELINE")
    if not baseline:
        return []
    return read_coordinates(baseline)


# ============================================================
# READ THE TWO SLOPING TEXTBLOCK EDGES
# ============================================================

def get_textblock_edges(textblock):
    """Return the left and right edges of a four-point TextBlock polygon.

    Each edge is stored as two points: (top point, bottom point).
    The order in which the four polygon points are encoded does not matter.
    """

    polygon = textblock.find("alto:Shape/alto:Polygon", NS)

    if polygon is None or "POINTS" not in polygon.attrib:
        raise ValueError("TextBlock has no Polygon POINTS")

    points = read_coordinates(polygon.attrib["POINTS"])

    # The previous TextBlock-cleaning script creates exactly four corners.
    if len(points) != 4:
        raise ValueError(
            f"TextBlock polygon has {len(points)} points instead of 4"
        )

    # The two points with the smallest Y values are the top corners;
    # the other two are the bottom corners.
    points_from_top_to_bottom = sorted(points, key=lambda point: point[1])
    top_corners = points_from_top_to_bottom[:2]
    bottom_corners = points_from_top_to_bottom[2:]

    top_left = min(top_corners, key=lambda point: point[0])
    top_right = max(top_corners, key=lambda point: point[0])
    bottom_left = min(bottom_corners, key=lambda point: point[0])
    bottom_right = max(bottom_corners, key=lambda point: point[0])

    left_edge = (top_left, bottom_left)
    right_edge = (top_right, bottom_right)

    return left_edge, right_edge


def boundary_x_at_y(boundary_edge, y):
    """Calculate the X coordinate of a sloping boundary at a given Y.

    Example:
        top point    = (1800, 100)
        bottom point = (1820, 2100)

    Halfway down, at Y=1100, the boundary is at X=1810.
    """

    (top_x, top_y), (bottom_x, bottom_y) = boundary_edge

    if bottom_y == top_y:
        raise ValueError("TextBlock boundary has no vertical height")

    fraction_down = (y - top_y) / (bottom_y - top_y)

    return top_x + fraction_down * (bottom_x - top_x)


# ============================================================
# DECIDE WHETHER A POINT IS INSIDE THE TEXTBLOCK
# ============================================================

def distance_from_boundary(point, boundary_edge):
    """Horizontal signed distance from the sloping boundary.

    Positive means the point lies to the right of the boundary.
    Negative means it lies to the left.
    """

    x, y = point
    return x - boundary_x_at_y(boundary_edge, y)


def point_is_inside(point, boundary_edge, margin_side):
    distance = distance_from_boundary(point, boundary_edge)

    if margin_side == "left":
        return distance >= 0
    else:
        return distance <= 0


def intersection_with_boundary(first_point, second_point, boundary_edge):
    """Find where a segment between two points crosses the sloping edge."""

    first_distance = distance_from_boundary(first_point, boundary_edge)
    second_distance = distance_from_boundary(second_point, boundary_edge)

    denominator = first_distance - second_distance
    if denominator == 0:
        # This should only occur for a segment parallel to the boundary.
        return first_point

    fraction = first_distance / denominator

    first_x, first_y = first_point
    second_x, second_y = second_point

    crossing_y = first_y + fraction * (second_y - first_y)
    crossing_x = boundary_x_at_y(boundary_edge, crossing_y)

    return crossing_x, crossing_y


# ============================================================
# CLIP AN OPEN BASELINE
# ============================================================

def clip_baseline(points, boundary_edge, margin_side):
    """Remove the part of an open baseline lying outside the TextBlock."""

    if not points:
        return []

    new_points = []
    previous_point = points[0]
    previous_inside = point_is_inside(
        previous_point, boundary_edge, margin_side
    )

    if previous_inside:
        new_points.append(previous_point)

    for current_point in points[1:]:
        current_inside = point_is_inside(
            current_point, boundary_edge, margin_side
        )

        # The segment crosses the boundary whenever its two ends are on
        # different sides. Insert the exact crossing point.
        if previous_inside != current_inside:
            crossing = intersection_with_boundary(
                previous_point, current_point, boundary_edge
            )
            new_points.append(crossing)

        if current_inside:
            new_points.append(current_point)

        previous_point = current_point
        previous_inside = current_inside

    return new_points


# ============================================================
# CLIP A CLOSED POLYGON
# ============================================================

def clip_polygon(points, boundary_edge, margin_side):
    """Remove the part of a closed polygon lying outside the TextBlock."""

    if not points:
        return []

    new_points = []

    # A polygon is closed, so the point before the first is the final point.
    previous_point = points[-1]
    previous_inside = point_is_inside(
        previous_point, boundary_edge, margin_side
    )

    for current_point in points:
        current_inside = point_is_inside(
            current_point, boundary_edge, margin_side
        )

        if current_inside:
            if not previous_inside:
                new_points.append(
                    intersection_with_boundary(
                        previous_point, current_point, boundary_edge
                    )
                )
            new_points.append(current_point)

        elif previous_inside:
            new_points.append(
                intersection_with_boundary(
                    previous_point, current_point, boundary_edge
                )
            )

        previous_point = current_point
        previous_inside = current_inside

    return new_points


# ============================================================
# PROCESS ONE LONG LINE
# ============================================================

def process_long_line(textline, boundary_edge, margin_side):
    """Keep the main-text part and cut away the marginal part."""

    baseline_points = get_baseline_points(textline)

    polygon = textline.find("alto:Shape/alto:Polygon", NS)
    if polygon is None or "POINTS" not in polygon.attrib:
        print("    WARNING: line has no Polygon POINTS")
        return False

    polygon_points = read_coordinates(polygon.attrib["POINTS"])

    if len(baseline_points) < 2:
        print("    WARNING: not enough baseline points")
        return False

    if len(polygon_points) < 3:
        print("    WARNING: too few Polygon points")
        return False

    new_baseline = clip_baseline(
        baseline_points, boundary_edge, margin_side
    )
    new_polygon = clip_polygon(
        polygon_points, boundary_edge, margin_side
    )

    if len(new_baseline) < 2 or len(new_polygon) < 3:
        print("    WARNING: clipping would leave invalid geometry")
        return False

    original_hpos = float(textline.attrib.get("HPOS", 0))
    original_width = float(textline.attrib.get("WIDTH", 0))

    # The TextLine bounding box must enclose the new polygon.
    polygon_x_values = [x for x, y in new_polygon]
    new_hpos = min(polygon_x_values)
    new_right = max(polygon_x_values)
    new_width = new_right - new_hpos

    textline.attrib["BASELINE"] = coordinates_to_string(new_baseline)
    polygon.attrib["POINTS"] = coordinates_to_string(new_polygon)
    textline.attrib["HPOS"] = format_number(new_hpos)
    textline.attrib["WIDTH"] = format_number(new_width)

    # In this corpus, each TextLine contains exactly one String.
    string = textline.find("alto:String", NS)
    if string is not None:
        string.attrib["HPOS"] = format_number(new_hpos)
        string.attrib["WIDTH"] = format_number(new_width)

    print(
        f"    Modified long {margin_side.upper()}-margin line: "
        f"HPOS {format_number(original_hpos)} -> {format_number(new_hpos)}, "
        f"WIDTH {format_number(original_width)} -> {format_number(new_width)}"
    )

    return True


# ============================================================
# PROCESS ONE TEXTLINE
# ============================================================

def process_textline(
    textline,
    boundary_edge,
    margin_side,
    textline_number
):
    baseline_points = get_baseline_points(textline)

    if not baseline_points:
        print(f"    WARNING: line {textline_number} has no BASELINE")
        return False

    line_reaches_margin = any(
        not point_is_inside(point, boundary_edge, margin_side)
        for point in baseline_points
    )

    if not line_reaches_margin:
        return False

    line_width = float(textline.attrib.get("WIDTH", 0))

    if line_width < SHORT_LINE_LIMIT:
        print(
            f"    Deleting line {textline_number}: "
            f"WIDTH={format_number(line_width)}"
        )
        return True

    print(
        f"    Long margin line {textline_number}: "
        f"WIDTH={format_number(line_width)}"
    )

    process_long_line(textline, boundary_edge, margin_side)
    return False


# ============================================================
# REMOVE TEXTLINE FROM TREE
# ============================================================

def remove_textline(root, textline):
    for parent in root.iter():
        for child in list(parent):
            if child is textline:
                parent.remove(textline)
                return


# ============================================================
# PROCESS ONE TEXTBLOCK
# ============================================================

def process_textblock(root, textblock, block_number, page_number):
    try:
        left_edge, right_edge = get_textblock_edges(textblock)
    except ValueError as error:
        print(f"  TextBlock {block_number}: {error}")
        return

    if page_number % 2 == 0:
        margin_side = "left"
        boundary_edge = left_edge
    else:
        margin_side = "right"
        boundary_edge = right_edge

    textlines = textblock.findall(".//alto:TextLine", NS)
    if not textlines:
        return

    print(
        f"  TextBlock {block_number}: "
        f"{margin_side.upper()} edge "
        f"{boundary_edge[0]} -> {boundary_edge[1]}, "
        f"TextLines={len(textlines)}"
    )

    for line_number, textline in enumerate(textlines, start=1):
        delete_line = process_textline(
            textline,
            boundary_edge,
            margin_side,
            line_number
        )

        if delete_line:
            remove_textline(root, textline)


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(input_path, output_path, page_number):
    tree = ET.parse(input_path)
    root = tree.getroot()

    textblocks = root.findall(".//alto:TextBlock", NS)
    if not textblocks:
        print(f"No TextBlock: {os.path.basename(input_path)}")
        return

    print(f"  Found {len(textblocks)} TextBlock(s)")

    for block_number, textblock in enumerate(textblocks, start=1):
        process_textblock(
            root,
            textblock,
            block_number,
            page_number
        )

    tree.write(
        output_path,
        encoding="UTF-8",
        xml_declaration=True
    )


# ============================================================
# PROCESS ALL XML FILES
# ============================================================

def main():
    for filename in sorted(os.listdir(INPUT_FOLDER)):
        if not filename.lower().endswith(".xml"):
            continue

        match = re.search(
            r"_page(\d+)\.xml$",
            filename,
            re.IGNORECASE
        )

        if not match:
            print(f"Skipping (page number not found): {filename}")
            continue

        page_number = int(match.group(1))
        print(f"\nProcessing: {filename}")

        input_path = os.path.join(INPUT_FOLDER, filename)
        output_path = os.path.join(OUTPUT_FOLDER, filename)

        process_file(input_path, output_path, page_number)

    print("\nDone!")


if __name__ == "__main__":
    main()
