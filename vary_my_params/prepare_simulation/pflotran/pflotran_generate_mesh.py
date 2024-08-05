import logging
import os
from pathlib import Path

from ...config import Parameter


def write_mesh_and_border_files(parameters: dict[str, Parameter], output_dir: Path) -> None:
    write_lines_to_file("mesh.uge", render_mesh(parameters), output_dir)

    north, east, south, west = render_borders(parameters)
    write_lines_to_file("north.ex", north, output_dir)
    write_lines_to_file("east.ex", east, output_dir)
    write_lines_to_file("south.ex", south, output_dir)
    write_lines_to_file("west.ex", west, output_dir)


def write_lines_to_file(file_name: str, output_strings: list[str], output_dir: Path):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(f"{output_dir}/{file_name}", "w") as file:
        file.writelines(output_strings)


def render_mesh(parameters: dict[str, Parameter]) -> list[str]:
    xGrid, yGrid, zGrid = parameters.get("number_cells").value
    cellXWidth, cellYWidth, cellZWidth = parameters.get("cell_resolution").value

    volume = cellXWidth * cellYWidth * cellZWidth
    if cellXWidth == cellYWidth == cellZWidth:
        faceArea = cellXWidth**2
    else:
        logging.error(
            "The grid is not cubic - look at create_grid_unstructured.py OR "
            + "2D case and settings.yaml depth for z is not adapted"
        )
        raise ValueError("Grid is not cubic")

    # CELLS <number of cells>
    # <cell id> <x> <y> <z> <volume>
    # ...
    # CONNECTIONS <number of connections>
    # <cell id a> <cell id b> <face center coordinate x> <face y> <face z> <area of the face>

    output_string_cells = ["CELLS " + str(xGrid * yGrid * zGrid)]
    output_string_connections = [
        "CONNECTIONS " + str((xGrid - 1) * yGrid * zGrid + xGrid * (yGrid - 1) * zGrid + xGrid * yGrid * (zGrid - 1))
    ]

    cellID_1 = 1

    for k in range(0, zGrid):
        zloc = (k + 0.5) * cellZWidth

        for j in range(0, yGrid):
            yloc = (j + 0.5) * cellYWidth

            for i in range(0, xGrid):
                xloc = (i + 0.5) * cellXWidth

                output_string_cells.append(f"\n{cellID_1} {xloc} {yloc} {zloc} {volume}")
                cellID_1 += 1

                gridCellID_1 = i + 1 + j * xGrid + k * xGrid * yGrid
                if i < xGrid - 1:
                    xloc_local = (i + 1) * cellXWidth
                    cellID_2 = gridCellID_1 + 1
                    output_string_connections.append(
                        f"\n{gridCellID_1} {cellID_2} {xloc_local} {yloc} {zloc} {faceArea}"
                    )
                if j < yGrid - 1:
                    yloc_local = (j + 1) * cellYWidth
                    cellID_2 = gridCellID_1 + xGrid
                    output_string_connections.append(
                        f"\n{gridCellID_1} {cellID_2} {xloc} {yloc_local} {zloc} {faceArea}"
                    )
                if k < zGrid - 1:
                    zloc_local = (k + 1) * cellZWidth
                    cellID_2 = gridCellID_1 + xGrid * yGrid
                    output_string_connections.append(
                        f"\n{gridCellID_1} {cellID_2} {xloc} {yloc} {zloc_local} {faceArea}"
                    )

    return output_string_cells + ["\n"] + output_string_connections


def render_borders(parameters: dict[str, Parameter]):
    xGrid, yGrid, zGrid = parameters.get("number_cells").value
    cellXWidth, cellYWidth, cellZWidth = parameters.get("cell_resolution").value

    if cellXWidth == cellYWidth == cellZWidth:
        faceArea = cellXWidth**2
    else:
        logging.error(
            "The grid is not cubic - look at create_grid_unstructured.py OR "
            + "2D case and settings.yaml depth for z is not adapted"
        )
        raise ValueError("Grid is not cubic")

    output_string_east = ["CONNECTIONS " + str(yGrid * zGrid)]
    output_string_west = ["CONNECTIONS " + str(yGrid * zGrid)]

    output_string_north = ["CONNECTIONS " + str(xGrid * zGrid)]
    output_string_south = ["CONNECTIONS " + str(xGrid * zGrid)]

    yloc_south = 0
    xloc_west = 0
    yloc_north = yGrid * cellYWidth
    xloc_east = xGrid * cellXWidth

    for k in range(0, zGrid):
        zloc = (k + 0.5) * cellZWidth

        for i in range(0, xGrid):
            xloc = (i + 0.5) * cellXWidth
            cellID_north = (xGrid * (yGrid - 1)) + i + 1 + k * xGrid * yGrid
            cellID_south = i + 1 + k * xGrid * yGrid
            output_string_north.append(f"\n{cellID_north} {xloc} {yloc_north} {zloc} {faceArea}")
            output_string_south.append(f"\n{cellID_south} {xloc} {yloc_south} {zloc} {faceArea}")

        for j in range(0, yGrid):
            yloc = (j + 0.5) * cellYWidth
            cellID_east = (j + 1) * xGrid + k * xGrid * yGrid
            cellID_west = j * xGrid + 1 + k * xGrid * yGrid
            output_string_east.append(f"\n{cellID_east} {xloc_east} {yloc} {zloc} {faceArea}")
            output_string_west.append(f"\n{cellID_west} {xloc_west} {yloc} {zloc} {faceArea}")

    return (output_string_north, output_string_east, output_string_south, output_string_west)
