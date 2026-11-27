"""Functions for interpreting resource_tracker outputs."""

import os
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

__all__ = [
    "parse_single_junit_result_xml",
    "write_benchmarks_per_tst",
    "read_benchmarks_per_tst",
    "plot_benchmarks_per_tst",
]


def parse_single_junit_result_xml(source):
    """
    Parse a single junit result XML output.

    Parameters
    ----------
    source : str or fileobj
        Filename or file object containing XML data.

    Returns
    -------
    test_date : str
        Date the test was run.

    peakmem_dict : dict
        Dictionary mapping a test to another dictionary
        containing its benchmark statistics, e.g.::

            {
                (classname, name): {
                    "passed": 1,
                    "peakmem": 0.1,
                    "time": 10
                }
            }

    Raises
    ------
    ValueError
        Unexpected XML layout.
    """

    # Create the Element Tree object from the XML file and get the top level root.
    tree = ET.parse(source)
    root = tree.getroot()

    # Save all the info into the following dictionary.
    peakmem_dict = defaultdict(dict)

    # The first element is called testsuites, this only contains one testsuite, which
    # has the datetime in which the tests were ran, variable called timestamp, in UT.
    test_date = None
    for element in root.iter("testsuites"):
        items = element.findall("testsuite")[0]
        if items is not None:
            test_date = items.attrib["timestamp"]
            break
        else:
            raise ValueError("XML format change!")

    if test_date is None:
        raise ValueError("No test date found in XML file.")

    # All test cases will be under the testsuite element, as follows:
    #
    # <testcase classname="pkg.module" name="test_name" time="16.539">
    #   <failure message="...">...</failure>
    #   <properties>
    #     <property name="tracked-peakmem" value="802075618"/>
    #     <property name="tracked-time" value="16.49477450037375"/>
    #   </properties>
    # </testcase>
    #
    for element in root.iter("testcase"):
        tracked_mem_elements = element.findall("properties/property")

        # If this list does not exist, no memory peak was recorded.
        if not tracked_mem_elements:
            continue

        # Some tests have the same name but are in different modules,
        # so we need tuple as unique key.
        # Also make sure the names are friendly for filename
        # serialization later.
        classname = element.attrib["classname"].replace(".", "__")
        testname = element.attrib["name"].replace("/", "__")
        key = (classname, testname)

        # Save the peak memory (bytes) and run time (seconds).
        for prop in tracked_mem_elements:
            for attrname in ("peakmem", "time"):
                if prop.attrib["name"] == f"tracked-{attrname}":
                    peakmem_dict[key][attrname] = prop.get("value")

        # Save the test status.
        failure = element.findall("failure")
        if failure:
            peakmem_dict[key]["passed"] = 0
        else:
            peakmem_dict[key]["passed"] = 1

    return test_date, peakmem_dict


def _key_to_filename(key):
    """Serialize key from peakmem_dict into filename."""
    classname, testname = key
    return f"{classname}__{testname}.csv"


# The _tst instead of _test so pytest will not collect this.
def write_benchmarks_per_tst(source, strun_verfile="", outdir="."):
    """
    Rewrite junit output for per-test benchmark ingestion.

    Parameters
    ----------
    source : str or fileobj
        Filename or file object containing XML data
        to be parsed by :func:`parse_single_junit_result_xml`.

    strun_verfile : str
        Additional file with ``strun --version`` output for
        the version combo that generated ``source``.
        This file is needed because junit does not store the info
        but we want to track it for benchmark results over time.
        It is a plain text file with the following content::

            stpipe: A.B.C
            jwst: X.Y.Z

    outdir : str
        Output directory where one file per test will be
        written to. These files are meant to be updated
        over time. If a file exists, it will be appended to;
        otherwise, a new file will be created. Old contents
        are not re-validated nor checked for duplicates.

    Returns
    -------
    file_list : list of str
        List of written files for auditing.
    """
    test_date, peakmem_dict = parse_single_junit_result_xml(source)
    outpath = Path(outdir)
    file_list = []

    if strun_verfile:
        origlines = Path(strun_verfile).read_text()
        versions = dict(map(str.strip, c.split(":")) for c in origlines.strip().split("\n"))
    else:
        versions = {"stpipe": "unknown", "jwst": "unknown"}

    for key, val in peakmem_dict.items():
        fname = outpath / _key_to_filename(key)
        file_list.append(str(fname))
        if not fname.exists():
            with open(fname, "w") as fout:
                fout.write(f"# classname: {key[0]}\n")
                fout.write(f"# testname: {key[1]}\n")
                fout.write("test_date,passed,peakmem,time,stpipe,jwst\n")
                fout.write(f"{test_date},{val['passed']},{val['peakmem']},{val['time']},{versions['stpipe']},{versions['jwst']}\n")
        else:
            with open(fname, "a") as fout:
                fout.write(f"{test_date},{val['passed']},{val['peakmem']},{val['time']},{versions['stpipe']},{versions['jwst']}\n")

    return file_list


def read_benchmarks_per_tst(csvfile):
    """
    Read in data generated by :func:`write_benchmarks_per_tst`.

    .. note:: This needs astropy to be installed.

    Parameters
    ----------
    csvfile : str
        CSV file with pre-defined format.

    Returns
    -------
    tbl : QTable
        Astropy QTable with benchmark data.
        Class and test names are in table metadata.
    """
    try:
        from astropy import units as u
        from astropy.table import QTable
    except ImportError:
        raise ImportError("Install astropy to use this function") from None

    tbl = QTable.read(
        csvfile,
        format="ascii.csv",
        comment="#",
        guess=False,
        units={"peakmem": u.byte, "time": u.s},
    )

    # Make metadata more easily accessible.
    comments = tbl.meta["comments"]
    d = dict(map(str.strip, c.split(":")) for c in comments)
    del tbl.meta["comments"]
    tbl.meta.update(d)

    return tbl


def plot_benchmarks_per_tst(csv_input, savefig=""):
    """
    Visualize benchmark statistics for a single test.

    .. note:: This needs astropy and matplotlib to be installed.

    Parameters
    ----------
    csvfile : str or QTable
        CSV file for input into or Astropy QTable returned by
        :func:`read_benchmarks_per_tst`.

    savefig : str
        If provided, generated plot will be saved to the
        given file path and interactive mode is disabled.
        Otherwise, interactive mode is enabled
        (whether the plot actually shows up or not
        depends on your terminal settings).
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from astropy import units as u
        from astropy.table import QTable
        from astropy.visualization import quantity_support
    except ImportError:
        raise ImportError("Install astropy and matplotlib to use this function") from None

    if not isinstance(csv_input, QTable):
        tbl = read_benchmarks_per_tst(csv_input)
    else:
        tbl = csv_input

    # TODO: How to visualize this also?
    #passed = tbl["passed"].data

    peakmem = tbl["peakmem"].to(u.GB)
    runtime = tbl["time"]
    xticks = np.arange(runtime.size)
    xlabels = tbl["jwst"]  # jwst, stpipe, test_date
    plot_title = f"{tbl.meta['classname']}, {tbl.meta['testname']}"

    if savefig:
        plt.ioff()
    else:
        plt.ion()

    quantity_support()
    fig, axes = plt.subplots(2, 1, sharex=True)

    ax0 = axes[0]
    ax0.plot(peakmem, c="k", marker="o", ls="")
    ax0.set_title(plot_title)

    ax1 = axes[1]
    ax1.plot(runtime, c="k", marker="o", ls="")
    ax1.set_xticks(xticks, labels=xlabels)

    plt.draw()
    if savefig:
        fig.savefig(savefig)
