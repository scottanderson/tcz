#!/usr/bin/env python3
#

import argparse
import nimporter
import os
import save_monger
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
            for base_path in potential_paths:
                if base_path.exists():
                    return base_path
            raise f"Unable to find TC save directory"
    raise f"Platform not supported: {sys.platform=}"


def append_zip(
        zip: ZipFile,
        arcname: str,
        file: Path,
        options: argparse.Namespace):
    if file.stat().st_size == 0:
        if not options.include_empty_files:
            if options.verbose > 1:
                print(f"Ignoring empty file {arcname}")
            return
        if options.verbose > 1:
            print(f"Including empty file {arcname}")
    if options.verbose > 0:
        print(arcname)
    zip.write(file, arcname)


def zip_level(
        base: Path,
        level_name: str,
        zip_path: Path,
        options: argparse.Namespace):
    try:
        print(f"Writing {zip_path}")
        with ZipFile(zip_path, "w") as zip:
            dir = base / "schematics" / level_name
            for p in list(dir.rglob("circuit.data")):
                arcname = p.relative_to(base.parent)
                append_zip(zip, arcname, p, options)
    except:
        zip_path.unlink(missing_ok=True)
        raise


def zip_arch(
        component_paths: dict[int, Path],
        component_data: dict,
        base: Path,
        zip_path: Path,
        arch_dir: Path,
        options: argparse.Namespace):
    try:
        print(f"Writing {zip_path}")
        with ZipFile(zip_path, "w") as zip:
            _zip_arch(component_paths, component_data,
                      base, zip, arch_dir, options)
    except:
        zip_path.unlink(missing_ok=True)
        raise


def _zip_arch(
        component_paths: dict[int, Path],
        component_data: dict,
        base: Path,
        zip: ZipFile,
        arch_dir: Path,
        options):
    circuit_data = arch_dir / "circuit.data"
    assembly_data = arch_dir / "assembly.data"
    for p in [circuit_data, assembly_data] + list(arch_dir.rglob("*.assembly")):
        arcname = p.relative_to(base.parent)
        append_zip(zip, arcname, p, options)
    instruction_rules_data = arch_dir / "instruction_rules.data"
    if instruction_rules_data.exists():
        arcname = instruction_rules_data.relative_to(base.parent)
        append_zip(zip, arcname, instruction_rules_data, options)
    component_factory = base / "schematics" / "component_factory"

    def add_deps(deps):
        for dependency in deps:
            assert dependency in component_paths, f"Dependency: {dependency} of {arch_dir.name} not found"
            dep = component_paths[dependency]
            # arcname = dep.relative_to(base.parent)
            arcpath = component_factory / arch_dir.name / dep.parent.name / dep.name
            arcname = arcpath.relative_to(base.parent)
            append_zip(zip, arcname, dep, options)
            add_deps(component_data[dependency]["dependencies"])
    data = save_monger.parse_state(list(circuit_data.read_bytes()))
    add_deps(data["dependencies"])


def main(options):
    component_paths: dict[int, Path] = dict()
    component_data: dict = dict()
    base = get_path()
    assert base.exists(), f"Path does not exist: {base}"
    schematics = base / "schematics"
    timestr = time.strftime("%Y%m%d-%H%M%S")
    for level_name in options.level:
        zip_path = base.parent / f"{level_name.replace(os.path.sep, '_')}_{timestr}.zip"
        zip_level(base, level_name, zip_path, options)
    if options.level:
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
        zip_path = base.parent / f"{architecture_name}_{timestr}.zip"
        arch_dir = architecture / architecture_name
        zip_arch(component_paths, component_data,
                 base, zip_path, arch_dir, options)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="tcz")
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help="Increase log level")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', '--architecture',
                       action='append',
                       default=[],
                       help="Name of architecture schematic")
    group.add_argument('-l', '--level',
                       action='append',
                       default=[],
                       help="Name of level/schematic file, eg '-l not_gate' or '-l not_gate/Default'")
    parser.add_argument('-e', '--include-empty-files',
                        action='store_true',
                        default=False)
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    options = parser.parse_args()
    main(options)
