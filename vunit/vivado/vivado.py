# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

"""
Utilities for integrating with Vivado
"""

from __future__ import print_function
from subprocess import check_call
from os import makedirs
from os.path import abspath, join, dirname, exists, basename


def add_from_compile_order_file(vunit_obj, compile_order_file):
    """
    Add Vivado IP:s from a compile order file
    """
    compile_order, libraries, include_dirs = _read_compile_order(compile_order_file)

    # Create libraries
    for library_name in libraries:
        vunit_obj.add_library(library_name, vhdl_standard="93")

    # Add all source files to VUnit
    source_files = []

    no_dependency_scan = []
    with_dependency_scan = []
    for library_name, file_name in compile_order:
        is_verilog = file_name.endswith(".v") or file_name.endswith(".vp")

        # Use VUnit dependency scanning for everything in xil_defaultlib
        scan_dependencies = library_name == "xil_defaultlib"
        source_file = vunit_obj.library(library_name).add_source_file(
            file_name,
            no_parse=not scan_dependencies,
            include_dirs=include_dirs if is_verilog else None)

        if scan_dependencies:
            with_dependency_scan.append(source_file)
        else:
            no_dependency_scan.append(source_file)

        source_files.append(source_file)

    # Use hardcoded dependency for everthing outside of xil_defaultlib
    for idx in range(1, len(no_dependency_scan)):
        no_dependency_scan[idx].add_dependency_on(no_dependency_scan[idx - 1])

    # Add dependency of last item in non-dependency scanned files to the each scanned file
    if no_dependency_scan:
        for source_file in with_dependency_scan:
            source_file.add_dependency_on(no_dependency_scan[-1])

    return source_files


def create_compile_order_file(project_file, compile_order_file, vivado_path=None):
    """
    Create compile file from Vivado project
    """
    print("Generating Vivado project compile order into %s ..." % abspath(compile_order_file))

    if not exists(dirname(compile_order_file)):
        makedirs(dirname(compile_order_file))

    print("Extracting compile order ...")
    run_vivado(join(dirname(__file__), "tcl", "extract_compile_order.tcl"),
               tcl_args=[project_file, compile_order_file],
               vivado_path=vivado_path)


def _read_compile_order(file_name):
    """
    Read the compile order file and filter out duplicate files
    """
    compile_order = []
    unique = set()
    include_dirs = set()
    libraries = set()

    with open(file_name, "r") as ifile:

        for line in ifile.readlines():
            library_name, file_type, file_name = line.strip().split(",", maxsplit=2)
            assert file_type in ("Verilog", "VHDL", "Verilog Header")
            libraries.add(library_name)

            # Vivado generates duplicate files for different IP:s
            # using the same underlying libraries. We remove duplicates here
            key = (library_name, basename(file_name))
            if key in unique:
                continue
            unique.add(key)

            if file_type == "Verilog Header":
                include_dirs.add(dirname(file_name))
            else:
                compile_order.append((library_name, file_name))

    return compile_order, libraries, list(sorted(include_dirs))


def run_vivado(tcl_file_name, tcl_args=None, cwd=None, vivado_path=None):
    """
    Run tcl script in Vivado in batch mode.

    Note: the shell=True is important in windows where Vivado is just a bat file.
    """
    vivado = "vivado" if vivado_path is None else join(abspath(vivado_path), "bin", "vivado")
    cmd = "{} -nojournal -nolog -notrace -mode batch -source {}".format(vivado,
                                                                        abspath(tcl_file_name))
    if tcl_args is not None:
        cmd += " -tclargs " + " ".join([str(val) for val in tcl_args])

    print(cmd)
    check_call(cmd, cwd=cwd, shell=True)
