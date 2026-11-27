from argparse import ArgumentParser

from ci_watson.resource_tracker_utils import plot_benchmarks_per_tst
from ci_watson.version import version as ci_watson_version

__all__ = []


def main():
    parser = ArgumentParser(description="Visualize benchmarks for one test function. See API documentation for ci_watson.resource_tracker_utils.plot_benchmarks_per_tst() for more details.")
    parser.add_argument(
        "csvfile",
        help="CSV file with benchmarks for one test.",
    )
    parser.add_argument(
        "outfile",
        help="Filename for output plot. Example: myplot.png",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ci-watson {ci_watson_version}",
        help="Print package version and exit.",
    )

    args = parser.parse_args()
    csvfile = args.csvfile
    outfile = args.outfile
    plot_benchmarks_per_tst(csvfile, savefig=outfile)
    print(f"Benchmark plot for {csvfile} written to {outfile}")


if __name__ == "__main__":
    main()
