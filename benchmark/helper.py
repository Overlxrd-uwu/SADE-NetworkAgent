import argparse
import csv
import os
from collections import OrderedDict


CUR_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(CUR_DIR)

DEFAULT_INPUT = os.path.join(REPO_DIR, "results", "0_summary", "evaluation_summary.csv")
DEFAULT_OUTPUT = os.path.join(CUR_DIR, "benchmark_failed.csv")


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_fail_case(row: dict) -> bool:
    detection_score = _to_float(row.get("detection_score"))
    llm_final_outcome_score = _to_float(row.get("llm_judge_final_outcome_score"))

    # Rule 1: detection_score != 1 is always a fail, regardless of judge score.
    if detection_score != 1.0:
        return True

    # Rule 2: detection_score == 1 but final outcome score < 3 is also a fail.
    if llm_final_outcome_score is None:
        return True
    return llm_final_outcome_score < 3.0


def build_failed_benchmark(input_csv: str, output_csv: str) -> tuple[int, int]:
    failed_cases: OrderedDict[tuple[str, str, str], None] = OrderedDict()
    total_rows = 0

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            if not is_fail_case(row):
                continue

            key = (
                row["root_cause_name"].strip(),
                row["net_env"].strip(),
                row["scenario_topo_size"].strip(),
            )
            failed_cases[key] = None

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["problem", "scenario", "topo_size"])
        writer.writeheader()
        for problem, scenario, topo_size in failed_cases.keys():
            writer.writerow(
                {
                    "problem": problem,
                    "scenario": scenario,
                    "topo_size": topo_size,
                }
            )

    return total_rows, len(failed_cases)


def main():
    parser = argparse.ArgumentParser(
        description="Build a rerun benchmark CSV from evaluation_summary.csv by filtering failing cases."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Path to evaluation_summary.csv",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Path to write the filtered benchmark CSV",
    )
    args = parser.parse_args()

    total_rows, failed_count = build_failed_benchmark(args.input, args.output)
    print(f"Read {total_rows} rows from: {args.input}")
    print(f"Wrote {failed_count} failing benchmark rows to: {args.output}")


if __name__ == "__main__":
    main()
