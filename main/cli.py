import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Static Program Analyzer CLI"
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to the source code file (Java or C++)"
    )

    parser.add_argument(
        "--lang",
        required=True,
        choices=["java", "cpp"],
        help="Programming language"
    )

    parser.add_argument(
        "--analysis",
        nargs="+",
        choices=["pointer", "live", "reaching"],
        required=True,
        help="Analyses to run"
    )

    args = parser.parse_args()

    print("=== CLI INPUT SUMMARY ===")
    print("Source file:", args.file)
    print("Language:", args.lang)
    print("Analyses:", args.analysis)

if __name__ == "__main__":
    main()
