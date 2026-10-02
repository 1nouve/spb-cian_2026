from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--end-page",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Save checkpoint every N pages.",
    )

    parser.add_argument(
        "--extra-data",
        action="store_true",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
    )

    return parser.parse_args()


def collect_segment(
    parser,
    rooms,
    segment_name: str,
    start_page: int,
    end_page: int,
    extra_data: bool,
) -> pd.DataFrame:

    settings = {
        "start_page": start_page,
        "end_page": end_page,
    }

    try:
        rows = parser.get_flats(
            deal_type="sale",
            rooms=rooms,
            with_saving_csv=False,
            with_extra_data=extra_data,
            additional_settings=settings,
        )

    except Exception as exc:
        partial = getattr(exc, "partial_results", None)

        if not partial:
            print(
                f"Error in {segment_name}, "
                f"pages {start_page}-{end_page}: {exc}"
            )
            return pd.DataFrame()

        print(
            f"Collection interrupted. "
            f"Saving {len(partial)} partial rows."
        )

        rows = partial

    df = pd.DataFrame(rows)

    if df.empty:
        print(
            f"No listings: {segment_name}, "
            f"pages {start_page}-{end_page}"
        )
        return df

    df["requested_segment"] = segment_name

    # Для студий rooms = 0
    if "rooms_count" in df.columns:
        df["rooms"] = pd.to_numeric(
            df["rooms_count"],
            errors="coerce",
        )

        if segment_name == "studio":
            df["rooms"] = 0

    return df


def prepare_ids(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:
        return df

    if "url" in df.columns:

        offer_id = (
            df["url"]
            .astype(str)
            .str.extract(
                r"/flat/(\d+)",
                expand=False,
            )
        )

        if "offer_id" in df.columns:
            df["offer_id"] = offer_id
        else:
            df.insert(
                0,
                "offer_id",
                offer_id,
            )

    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:
        return df

    before = len(df)

    if (
        "offer_id" in df.columns
        and df["offer_id"].notna().any()
    ):
        df = df.drop_duplicates(
            subset="offer_id",
            keep="first",
        )

    elif "url" in df.columns:
        df = df.drop_duplicates(
            subset="url",
            keep="first",
        )

    removed = before - len(df)

    print(f"Duplicates removed: {removed}")

    return df


def main() -> None:

    args = parse_args()

    if args.start_page < 1:
        raise ValueError(
            "start_page must be >= 1"
        )

    if args.end_page < args.start_page:
        raise ValueError(
            "end_page must be >= start_page"
        )

    if args.chunk_size < 1:
        raise ValueError(
            "chunk_size must be >= 1"
        )


    from cian_parser import CianParser
    from cian_parser.browser import BrowserManager


    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    checkpoint_path = (
        args.output_dir
        / "cian_spb_checkpoint.csv"
    )


    all_frames: list[pd.DataFrame] = []


    parser = CianParser(
        "Санкт-Петербург"
    )

    # Видимый Chromium
    parser._browser = BrowserManager(
        headless=False
    )


    with parser:

        chunk_start = args.start_page


        while chunk_start <= args.end_page:

            chunk_end = min(
                chunk_start
                + args.chunk_size
                - 1,
                args.end_page,
            )


            print()
            print("=" * 60)
            print(
                f"PAGES "
                f"{chunk_start}-{chunk_end}"
            )
            print("=" * 60)


            # -------------------------
            # Студии
            # -------------------------

            studio_df = collect_segment(
                parser=parser,
                rooms="studio",
                segment_name="studio",
                start_page=chunk_start,
                end_page=chunk_end,
                extra_data=args.extra_data,
            )

            if not studio_df.empty:
                all_frames.append(
                    studio_df
                )


            # -------------------------
            # 1–5 комнат
            # -------------------------

            rooms_df = collect_segment(
                parser=parser,
                rooms=(1, 2, 3, 4, 5),
                segment_name="rooms_1_5",
                start_page=chunk_start,
                end_page=chunk_end,
                extra_data=args.extra_data,
            )

            if not rooms_df.empty:
                all_frames.append(
                    rooms_df
                )


            # -------------------------
            # CHECKPOINT
            # -------------------------

            if all_frames:

                checkpoint = pd.concat(
                    all_frames,
                    ignore_index=True,
                )

                checkpoint = prepare_ids(
                    checkpoint
                )

                checkpoint = remove_duplicates(
                    checkpoint
                )

                checkpoint[
                    "collected_at"
                ] = datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="seconds"
                )

                checkpoint.to_csv(
                    checkpoint_path,
                    index=False,
                )


                print()
                print(
                    f"CHECKPOINT SAVED"
                )

                print(
                    f"Pages: "
                    f"{args.start_page}"
                    f"-{chunk_end}"
                )

                print(
                    f"Unique listings: "
                    f"{len(checkpoint)}"
                )

                print(
                    f"File: "
                    f"{checkpoint_path}"
                )


            chunk_start = (
                chunk_end + 1
            )


    # -----------------------------
    # FINAL DATASET
    # -----------------------------

    if not all_frames:
        raise SystemExit(
            "No listings were collected."
        )


    data = pd.concat(
        all_frames,
        ignore_index=True,
    )


    data = prepare_ids(data)

    data = remove_duplicates(data)


    data["collected_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat(
            timespec="seconds"
        )
    )


    stamp = datetime.now().strftime(
        "%Y-%m-%d_%H%M"
    )


    output_path = (
        args.output_dir
        / f"cian_spb_sale_{stamp}.csv"
    )


    data.to_csv(
        output_path,
        index=False,
    )


    print()
    print("=" * 60)
    print("COLLECTION FINISHED")
    print("=" * 60)

    print(
        f"Unique listings: "
        f"{len(data)}"
    )

    print(
        f"Final file: "
        f"{output_path}"
    )

    print(
        f"Checkpoint: "
        f"{checkpoint_path}"
    )


if __name__ == "__main__":
    main()