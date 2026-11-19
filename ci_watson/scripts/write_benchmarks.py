from argparse import ArgumentParser

from ci_watson.resource_tracker_utils import write_benchmarks_per_tst
from ci_watson.version import version as ci_watson_version

__all__ = []


def main():
    parser = ArgumentParser(description="Ingest junit XML output with test benchmarks for a run into CSV files, one per test. See API documentation for ci_watson.resource_tracker_utils.write_benchmarks_per_tst() for more details.")
    parser.add_argument(
        "source",
        help="junit XML output for a pytest run.",
    )
    parser.add_argument(
        "--strun-version",
        type=str,
        default="",
        help="Plain text file with output from strun --version associated with source. If not given, only test date is available for audit.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory where benchmarks are being collected over time. Default is current directory.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ci-watson {ci_watson_version}",
        help="Print package version and exit.",
    )

    args = parser.parse_args()
    source = args.source
    stver = args.strun_version
    outdir = args.output_dir
    print(f"Processing\n  junit XML {source}\n  strun version from {stver}\n  Output directory {outdir}")

    file_list = write_benchmarks_per_tst(
        source, strun_verfile=stver, outdir=outdir)
    print(f"Wrote/updated")
    for fname in file_list:
        print(f"  {fname}")


if __name__ == "__main__":
    main()
