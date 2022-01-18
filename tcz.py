#!/usr/bin/env python3
#

import argparse
import nimporter, save_monger
import os
import sys
import time
from pathlib import Path
from zipfile import ZipFile

def get_path():
    match sys.platform.lower():
        case "windows" | "win32":
            return Path(os.path.expandvars(r"%APPDATA%\Godot\app_userdata\Turing Complete"))
        case "darwin":
            return Path("~/Library/Application Support/Godot/app_userdata/Turing Complete").expanduser()
        case "linux":
            potential_paths = [Path("~/.local/share/godot/app_userdata/Turing Complete").expanduser(),
                               Path(os.path.expandvars("/mnt/c/Users/${USER}/AppData/Roaming/godot/app_userdata/Turing Complete/"))]  # WSL
        case _:
            print(f"Don't know where to find Turing Complete save on {sys.platform=}")
            return None
    for base_path in potential_paths:
        if base_path.exists():
            return base_path
    print("You need Turing Complete installed to use everything here")
    return None

def append_zip(zip, base, file):
    arcname = file.relative_to(base.parent)
    if file.stat().st_size == 0:
        print(f"Ignoring empty file {arcname}")
        return
    print(arcname)
    zip.write(file, arcname)

def main(options):
    component_paths: dict[int, Path] = dict()
    component_data: dict = dict()
    base = get_path()
    assert base.exists(), f"Path does not exist: {base}"
    schematics = base / "schematics"
    timestr = time.strftime("%Y%m%d-%H%M%S")
    for level_name in options.level:
        level = schematics / level_name
        zip_path = base.parent / f"{level_name.replace(os.path.sep, '_')}_{timestr}.zip"
        print(f"Writing {zip_path}")
        with ZipFile(zip_path, "w") as zip:
            for p in list(level.rglob("circuit.data")):
                append_zip(zip, base, p)
    if not options.architecture:
        return
    component_factory = schematics / "component_factory"
    architecture = schematics / "architecture"
    paths = list(component_factory.rglob("circuit.data"))
    for idx, circuit_data in enumerate(paths):
        print(f"Loading components [{idx+1}/{len(paths)}]... ", end="\r")
        data = save_monger.parse_state(list(circuit_data.read_bytes()))
        component_id = data["save_version"]
        component_paths[component_id] = circuit_data
        component_data[component_id] = data
    print("")
    for architecture_name in options.architecture:
        dir = architecture / architecture_name
        circuit_data = dir / "circuit.data"
        assembly_data = dir / "assembly.data"
        data = save_monger.parse_state(list(circuit_data.read_bytes()))
        zip_path = base.parent / f"{architecture_name}_{timestr}.zip"
        print(f"Writing {zip_path}")
        with ZipFile(zip_path, "w") as zip:
            for p in [circuit_data, assembly_data] + list(dir.rglob("*.assembly")):
                append_zip(zip, base, p)
            def add_deps(deps):
                for dependency in deps:
                    assert dependency in component_paths, f"Dependency: {dependency} not found"
                    dep = component_paths[dependency]
                    append_zip(zip, base, dep)
                    add_deps(component_data[dependency]["dependencies"])
            add_deps(data["dependencies"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="tcz")
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help="Increase log level")
    parser.add_argument('-a', '--architecture',
                        action='append',
                        default=[],
                        help="Name of architecture schematic")
    parser.add_argument('-l', '--level',
                        action='append',
                        default=[],
                        help="Name of level/schematic file, eg '-l not_gate' or '-l not_gate/Default'")
    parser.add_argument('-e', '--include-empty-files',
                        action='store_true',
                        default=False)
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    options = parser.parse_args()
    assert options.architecture or options.level, "-a or -l is required"
    main(options)
