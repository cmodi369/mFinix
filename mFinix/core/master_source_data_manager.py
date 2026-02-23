import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

import mFinix.constants.constants as const
from mFinix.util import log


class MasterSourceDataManager:
    """
    Source-agnostic manager for handling master data files (Holdings, Ledger, Tradebook).
    Handles saving raw uploads, merging them into master files with deduplication,
    and archiving.
    """

    def __init__(self, docs_path: Path = None):
        self.docs_path = docs_path or const.DOCS_PATH
        self.raw_path = const.DOCS_RAW_PATH
        self.master_path = const.DOCS_MASTER_PATH
        self.archive_path = const.DOCS_ARCHIVE_PATH
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure all required directories exist."""
        for path in [self.raw_path, self.master_path, self.archive_path]:
            path.mkdir(parents=True, exist_ok=True)

    def _archive_file(self, file_path: Path):
        """Move a file to the archive folder with a timestamp."""
        if not file_path.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        archive_name = f"{timestamp}_{file_path.name}"
        shutil.copy(file_path, self.archive_path / archive_name)

    def save_raw_file(
        self, content: bytes, source: str, original_filename: str
    ) -> Path:
        """Save a raw uploaded file."""
        source_raw_path = self.raw_path / source
        source_raw_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        target_path = source_raw_path / f"{timestamp}_{original_filename}"

        with open(target_path, "wb") as f:
            f.write(content)

        log.info(f"Saved raw file from {source}: {target_path}")
        return target_path

    def merge_and_update_master(
        self,
        new_data_path: Path,
        master_filename: str,
        subset_cols: List[str],
        date_col: Optional[str] = None,
        sort_ascending: bool = True,
    ) -> Path:
        """
        Merge a new data file into the master file, deduplicating and archiving.
        """
        master_file_path = self.master_path / master_filename

        try:
            # Load new data
            if new_data_path.suffix.lower() == ".csv":
                df_new = pd.read_csv(new_data_path)
            elif new_data_path.suffix.lower() in [".xls", ".xlsx"]:
                # For Excel, we might need specific logic if there are multiple sheets
                # but for simplicity, we'll read the first sheet or as per standard
                df_new = pd.read_excel(new_data_path)
            else:
                raise ValueError(f"Unsupported file format: {new_data_path.suffix}")

            if master_file_path.exists():
                # Archive existing master before update
                self._archive_file(master_file_path)

                # Load existing master
                if master_file_path.suffix.lower() == ".csv":
                    df_master = pd.read_csv(master_file_path)
                else:
                    df_master = pd.read_excel(master_file_path)

                # Combine
                df_combined = pd.concat([df_master, df_new], ignore_index=True)
            else:
                df_combined = df_new

            # Deduplicate
            # We use 'last' to keep the latest information if there's a conflict
            df_combined = df_combined.drop_duplicates(subset=subset_cols, keep="last")

            # Sort by date if provided
            if date_col and date_col in df_combined.columns:
                try:
                    df_combined[date_col] = pd.to_datetime(
                        df_combined[date_col], format="mixed", dayfirst=False
                    )
                    df_combined = df_combined.sort_values(
                        by=date_col, ascending=sort_ascending
                    )
                except Exception as e:
                    log.warning(f"Failed to sort {master_filename} by {date_col}: {e}")

            # Save master
            if master_file_path.suffix.lower() == ".csv":
                df_combined.to_csv(master_file_path, index=False)
            else:
                df_combined.to_excel(master_file_path, index=False)

            log.info(f"Updated master file: {master_file_path}")
            return master_file_path

        except Exception as e:
            log.error(f"Failed to merge {new_data_path} into {master_filename}: {e}")
            raise
