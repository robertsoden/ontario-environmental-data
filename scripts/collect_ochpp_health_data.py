#!/usr/bin/env python3
"""Collect and process OCHPP health indicator data.

This script processes health indicator data from the Ontario Community Health
Profiles Partnership (OCHPP) and joins it with Public Health Unit boundaries.

OCHPP provides health indicators in Excel format that must be manually downloaded
from: https://www.ontariohealthprofiles.ca/dataTablesON.php

Usage:
    1. Download Excel files from OCHPP website
    2. Place them in data/raw/ochpp/
    3. Run this script: python scripts/collect_ochpp_health_data.py

The script will:
    - Load PHU boundaries from Ontario GeoHub
    - Process OCHPP Excel files
    - Join indicators with PHU boundaries
    - Output GeoJSON with health indicators
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
import pandas as pd

from ontario_data.sources.health import PublicHealthClient, OCHPP_INDICATOR_CATEGORIES

# Directories
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw" / "ochpp"
OUTPUT_DIR = DATA_DIR / "processed" / "health"


async def collect_phu_boundaries() -> gpd.GeoDataFrame:
    """Fetch PHU boundaries from Ontario GeoHub."""
    print("\n🏥 Fetching Public Health Unit boundaries...")

    client = PublicHealthClient()
    phu_gdf = await client.get_phu_boundaries()

    if phu_gdf.empty:
        print("❌ Failed to fetch PHU boundaries")
        return gpd.GeoDataFrame()

    print(f"✅ Fetched {len(phu_gdf)} Public Health Units")
    return phu_gdf


def load_ochpp_excel_files(raw_dir: Path) -> pd.DataFrame:
    """Load and combine OCHPP Excel files.

    OCHPP files have complex structure:
    - Multiple sheets (General Notes + data sheets)
    - Header rows at top (title, date, copyright)
    - Data starts around row 4-6
    - Region ID and Region Name columns

    Args:
        raw_dir: Directory containing OCHPP Excel files

    Returns:
        Combined DataFrame with all indicators
    """
    if not raw_dir.exists():
        print(f"⚠️  OCHPP data directory not found: {raw_dir}")
        print("   Please create the directory and add OCHPP Excel files.")
        return pd.DataFrame()

    excel_files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls"))

    if not excel_files:
        print(f"⚠️  No Excel files found in {raw_dir}")
        print("   Download data from: https://www.ontariohealthprofiles.ca/dataTablesON.php")
        return pd.DataFrame()

    print(f"\n📊 Found {len(excel_files)} OCHPP Excel files:")

    # Combine all Excel files
    all_data = []
    for excel_file in excel_files:
        try:
            xl = pd.ExcelFile(excel_file)

            # Find data sheet (skip "General Notes", "Notes", etc.)
            data_sheets = [s for s in xl.sheet_names
                          if "note" not in s.lower() and "info" not in s.lower()]

            if not data_sheets:
                print(f"   ⚠️  No data sheet found in {excel_file.name}")
                continue

            for sheet_name in data_sheets:
                df = load_ochpp_sheet(excel_file, sheet_name)
                if df is not None and not df.empty:
                    # Extract indicator name from filename or sheet
                    indicator_name = extract_indicator_name(excel_file.name, sheet_name)
                    all_data.append((indicator_name, df))
                    print(f"   ✓ {excel_file.name} [{sheet_name}]: {len(df)} regions, indicator: {indicator_name}")

        except Exception as e:
            print(f"   ❌ Error loading {excel_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    # Combine all dataframes by region name
    # Track which indicators we've already added to avoid duplicates
    seen_indicators = set()
    combined = None

    for indicator_name, df in all_data:
        if "region_name" not in df.columns:
            continue

        # Skip if we already have this indicator
        if indicator_name in seen_indicators:
            continue

        # Rename the value column to the indicator name
        # Look for "indicator_value" (set by sheet loader) or rate/prevalence columns
        value_cols = [c for c in df.columns if c not in ["region_id", "region_name"]]
        if value_cols:
            rate_col = None

            # First priority: indicator_value column (set by multi-header parser)
            if "indicator_value" in df.columns:
                rate_col = "indicator_value"

            # Second priority: columns containing "rate", "prevalence", "age-standardized"
            if rate_col is None:
                for vc in value_cols:
                    vc_lower = str(vc).lower()
                    if any(term in vc_lower for term in ["rate", "prevalence", "age-standardized", "age standardized"]):
                        if df[vc].dtype in ['float64', 'int64']:
                            rate_col = vc
                            break

            # Third priority: first numeric column that's not Region ID
            if rate_col is None:
                for vc in value_cols:
                    vc_lower = str(vc).lower()
                    if df[vc].dtype in ['float64', 'int64'] and "region" not in vc_lower and "id" not in vc_lower and "unnamed" not in vc_lower:
                        rate_col = vc
                        break

            if rate_col:
                df = df[["region_name", rate_col]].copy()
                df = df.rename(columns={rate_col: indicator_name})
            else:
                df = df[["region_name", value_cols[0]]].copy()
                df = df.rename(columns={value_cols[0]: indicator_name})

        seen_indicators.add(indicator_name)

        if combined is None:
            combined = df
        else:
            combined = combined.merge(df, on="region_name", how="outer")

    if combined is None:
        return pd.DataFrame()

    # Rename to phu_name for joining
    combined = combined.rename(columns={"region_name": "phu_name"})

    # Ensure phu_name is string type
    combined["phu_name"] = combined["phu_name"].astype(str)

    # Remove Ontario total row
    combined = combined[~combined["phu_name"].str.contains("Ontario|Province", case=False, na=False)]

    print(f"\n✅ Combined {len(combined)} regions with {len(combined.columns)-1} indicators")
    return combined


def load_ochpp_sheet(excel_file: Path, sheet_name: str) -> pd.DataFrame:
    """Load a single OCHPP data sheet.

    OCHPP files have complex multi-row headers. This function:
    1. Finds the header rows
    2. Reads with multi-level headers
    3. Extracts the "Total" column for rate/prevalence indicators

    Args:
        excel_file: Path to Excel file
        sheet_name: Name of sheet to load

    Returns:
        DataFrame with region_name and indicator values
    """
    # Read without headers first to find the header rows
    df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

    # Find the header row (contains "Region" or similar)
    header_row = None
    for idx, row in df_raw.iterrows():
        row_str = " ".join(str(v).lower() for v in row.values if pd.notna(v))
        if "region" in row_str and ("name" in row_str or "id" in row_str):
            header_row = idx
            break

    if header_row is None:
        return None

    # Check if there's a sub-header row (Male/Female/Total)
    sub_header_row = header_row + 1
    if sub_header_row < len(df_raw):
        sub_row_str = " ".join(str(v).lower() for v in df_raw.iloc[sub_header_row].values if pd.notna(v))
        has_sub_header = any(term in sub_row_str for term in ["male", "female", "total"])
    else:
        has_sub_header = False

    # Re-read with proper headers
    if has_sub_header:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=[header_row, sub_header_row])
        # Flatten multi-level columns and find the rate/Total column
        flat_cols = []
        rate_col_idx = None
        region_name_idx = None

        for i, col in enumerate(df.columns):
            if isinstance(col, tuple):
                main_header = str(col[0]).lower()
                sub_header = str(col[1]).lower()

                # Handle Region Name column
                if "region" in main_header and "name" in main_header:
                    flat_name = "region_name"
                    region_name_idx = i
                # Handle Region ID column
                elif "region" in main_header and "id" in main_header:
                    flat_name = "region_id"
                # Look for age-standardized rate with Total
                elif ("rate" in main_header or "prevalence" in main_header or "age-standardized" in main_header):
                    if "total" in sub_header and rate_col_idx is None:
                        rate_col_idx = i
                        flat_name = "indicator_value"
                    else:
                        flat_name = f"{col[0]}_{col[1]}".replace(" ", "_")
                else:
                    flat_name = f"{col[0]}_{col[1]}".replace(" ", "_")

                flat_cols.append(flat_name)
            else:
                flat_cols.append(str(col))

        df.columns = flat_cols
    else:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)

    # Find region name column
    region_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if "region" in col_str and "name" in col_str:
            region_col = col
            break

    if region_col is None:
        # Try second column (first is often Region ID)
        cols = [c for c in df.columns if "unnamed" not in str(c).lower()]
        if len(cols) > 1:
            region_col = cols[1]
        elif len(df.columns) > 1:
            region_col = df.columns[1]

    if region_col is None:
        return None

    # Rename and clean
    df = df.rename(columns={region_col: "region_name"})
    df = df.dropna(subset=["region_name"])

    # Keep only rows with valid region names (not NaN, not headers)
    df = df[df["region_name"].astype(str).str.len() > 2]
    df = df[~df["region_name"].astype(str).str.contains("Unnamed|NaN|male|female", case=False, na=False)]

    return df


def extract_indicator_name(filename: str, sheet_name: str) -> str:
    """Extract a clean indicator name from filename or sheet name.

    Args:
        filename: Excel filename
        sheet_name: Sheet name

    Returns:
        Clean indicator name
    """
    # Common OCHPP filename patterns
    indicator_map = {
        "diabetes": "diabetes_rate",
        "hbp": "hypertension_rate",
        "asthma": "asthma_rate",
        "copd": "copd_rate",
        "mhv": "mental_health_visits",
        "mha": "mental_health_admissions",
        "edv": "ed_visits",
        "hosp": "hospitalizations",
        "surg": "surgical_procedures",
        "med": "medical_admissions",
        "acsc": "ambulatory_care_sensitive",
        "rpdb": "population",
        "sca": "screening_coverage",
        "2pcc": "primary_care_attachment",
    }

    # Check filename first
    filename_lower = filename.lower()
    for pattern, name in indicator_map.items():
        if pattern in filename_lower:
            return name

    # Check sheet name
    sheet_lower = sheet_name.lower()
    for pattern, name in indicator_map.items():
        if pattern in sheet_lower:
            return name

    # Fallback: clean up sheet name
    clean_name = sheet_name.replace("_", " ").replace("-", " ")
    clean_name = "".join(c for c in clean_name if c.isalnum() or c == " ")
    return clean_name.strip().lower().replace(" ", "_")[:30]


def standardize_indicator_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize indicator column names to match our models.

    Args:
        df: DataFrame with raw OCHPP column names

    Returns:
        DataFrame with standardized column names
    """
    # Common OCHPP column name patterns -> our standard names
    column_mapping = {
        # Chronic disease
        "diabetes": "diabetes_rate",
        "hypertension": "hypertension_rate",
        "copd": "copd_rate",
        "asthma": "asthma_rate",
        "chronic obstructive": "copd_rate",

        # Mental health
        "mental health ed": "mental_health_ed_rate",
        "mental health hospital": "mental_health_hospitalizations",
        "self-reported mental": "self_reported_mental_health_good",

        # Mortality
        "all-cause mortality": "all_cause_mortality_rate",
        "premature mortality": "premature_mortality_rate",
        "life expectancy": "life_expectancy",
        "infant mortality": "infant_mortality_rate",

        # Access to care
        "primary care": "primary_care_attachment",
        "cancer screening": "cancer_screening_rate",
        "regular health care provider": "primary_care_attachment",
    }

    renamed_cols = {}
    for col in df.columns:
        col_lower = col.lower()
        for pattern, standard_name in column_mapping.items():
            if pattern in col_lower:
                renamed_cols[col] = standard_name
                break

    if renamed_cols:
        df = df.rename(columns=renamed_cols)
        print(f"   Standardized {len(renamed_cols)} column names")

    return df


# Mapping of PHUs to Ontario Health Regions
PHU_TO_OH_REGION = {
    # West Region
    "Chatham-Kent Health Unit": "West",
    "Grey Bruce Health Unit": "West",
    "Huron Perth Health Unit": "West",
    "Lambton Health Unit": "West",
    "Middlesex-London Health Unit": "West",
    "Southwestern Public Health": "West",
    "Windsor-Essex County Health Unit": "West",
    # Central Region
    "Brant County Health Unit": "Central",
    "Haldimand-Norfolk Health Unit": "Central",
    "Halton Region Health Department": "Central",
    "Hamilton Public Health Services": "Central",
    "Niagara Region Public Health": "Central",
    "Peel Public Health": "Central",
    "Region of Waterloo, Public Health": "Central",
    "Wellington-Dufferin-Guelph Health Unit": "Central",
    "York Region Public Health": "Central",
    # Toronto Region
    "Toronto Public Health": "Toronto",
    # East Region
    "Durham Region Health Department": "East",
    "Eastern Ontario Health Unit": "East",
    "Hastings and Prince Edward Counties Health Unit": "East",
    "Kingston, Frontenac and Lennox & Addington Public Health": "East",
    "Leeds, Grenville and Lanark District Health Unit": "East",
    "Ottawa Public Health": "East",
    "Peterborough Public Health": "East",
    "Renfrew County and District Health Unit": "East",
    "Simcoe Muskoka District Health Unit": "East",
    # North East Region
    "Algoma Public Health": "North East",
    "North Bay Parry Sound District Health Unit": "North East",
    "Porcupine Health Unit": "North East",
    "Public Health Sudbury & Districts": "North East",
    "Timiskaming Health Unit": "North East",
    # East Region (additional)
    "Haliburton, Kawartha, Pine Ridge District Health Unit": "East",
    # North West Region
    "Northwestern Health Unit": "North West",
    "Thunder Bay District Health Unit": "North West",
}


def join_indicators_with_phu(
    phu_gdf: gpd.GeoDataFrame,
    indicators_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Join health indicators with PHU boundaries.

    If indicators are at Ontario Health Region level (6 regions),
    maps PHUs to their parent region to assign values.

    Args:
        phu_gdf: GeoDataFrame with PHU boundaries
        indicators_df: DataFrame with health indicators

    Returns:
        GeoDataFrame with joined data
    """
    if indicators_df.empty:
        print("⚠️  No indicator data to join")
        return phu_gdf

    if "phu_name" not in indicators_df.columns:
        print("❌ No phu_name column in indicators data")
        return phu_gdf

    # Check if this is region-level data (6 OH Regions) vs PHU-level (31 PHUs)
    region_names = {"west", "central", "toronto", "east", "north east", "north west"}
    indicator_names = set(indicators_df["phu_name"].str.lower().str.strip())

    if indicator_names.issubset(region_names | {"province of ontario", "province of ontario "}):
        print("   📍 Detected Ontario Health Region-level data")
        print("   Mapping PHUs to their parent OH Regions...")
        return join_via_region_mapping(phu_gdf, indicators_df)

    # Standard PHU-level join
    indicators_df["_join_key"] = (
        indicators_df["phu_name"]
        .str.lower()
        .str.strip()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
    )

    phu_gdf["_join_key"] = (
        phu_gdf["name"]
        .str.lower()
        .str.strip()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
    )

    # Perform join
    joined = phu_gdf.merge(indicators_df, on="_join_key", how="left")
    joined = joined.drop(columns=["_join_key"])

    # Count successful joins
    non_null_cols = [c for c in indicators_df.columns if c not in ["phu_name", "_join_key"]]
    if non_null_cols:
        matched = joined[non_null_cols[0]].notna().sum()
        print(f"✅ Joined {matched}/{len(phu_gdf)} PHUs with indicator data")

    return joined


def join_via_region_mapping(
    phu_gdf: gpd.GeoDataFrame,
    indicators_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Join region-level indicators to PHUs via mapping."""
    # Normalize region names in indicators
    indicators_df = indicators_df.copy()
    indicators_df["_region_key"] = (
        indicators_df["phu_name"]
        .str.lower()
        .str.strip()
    )

    # Add OH Region to PHU data
    phu_gdf = phu_gdf.copy()

    def get_region(phu_name):
        if pd.isna(phu_name):
            return None
        # Try exact match first
        if phu_name in PHU_TO_OH_REGION:
            return PHU_TO_OH_REGION[phu_name]
        # Try fuzzy match
        phu_lower = phu_name.lower()
        for known_phu, region in PHU_TO_OH_REGION.items():
            if known_phu.lower() in phu_lower or phu_lower in known_phu.lower():
                return region
        return None

    phu_gdf["oh_region"] = phu_gdf["name"].apply(get_region)
    phu_gdf["_region_key"] = phu_gdf["oh_region"].str.lower()

    # Show mapping results
    mapped = phu_gdf["oh_region"].notna().sum()
    print(f"   Mapped {mapped}/{len(phu_gdf)} PHUs to OH Regions")

    # Join on region
    joined = phu_gdf.merge(
        indicators_df.drop(columns=["phu_name"]),
        on="_region_key",
        how="left",
    )
    joined = joined.drop(columns=["_region_key"])

    # Count successful joins
    indicator_cols = [c for c in indicators_df.columns if c not in ["phu_name", "_region_key"]]
    if indicator_cols:
        matched = joined[indicator_cols[0]].notna().sum()
        print(f"✅ Assigned regional indicators to {matched}/{len(phu_gdf)} PHUs")

    return joined


async def main():
    """Main collection workflow."""
    print("=" * 60)
    print("OCHPP Health Indicators Data Collection")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch PHU boundaries
    phu_gdf = await collect_phu_boundaries()

    if phu_gdf.empty:
        print("\n❌ Cannot proceed without PHU boundaries")
        return

    # Save PHU boundaries separately
    phu_output = OUTPUT_DIR / "phu_boundaries.geojson"
    phu_gdf.to_file(phu_output, driver="GeoJSON")
    print(f"   Saved PHU boundaries to {phu_output}")

    # Step 2: Load OCHPP Excel files
    indicators_df = load_ochpp_excel_files(RAW_DIR)

    if indicators_df.empty:
        print("\n⚠️  No OCHPP data found. PHU boundaries saved without indicators.")
        print("\nTo add health indicators:")
        print(f"  1. Download Excel files from https://www.ontariohealthprofiles.ca/dataTablesON.php")
        print(f"  2. Place them in {RAW_DIR}")
        print("  3. Re-run this script")
        return

    # Step 3: Standardize column names
    indicators_df = standardize_indicator_names(indicators_df)

    # Step 4: Join with PHU boundaries
    health_gdf = join_indicators_with_phu(phu_gdf, indicators_df)

    # Step 5: Save output
    output_file = OUTPUT_DIR / "health_indicators.geojson"
    health_gdf.to_file(output_file, driver="GeoJSON")

    print("\n" + "=" * 60)
    print("Collection Complete!")
    print("=" * 60)
    print(f"\nOutput files:")
    print(f"  - PHU boundaries: {phu_output}")
    print(f"  - Health indicators: {output_file}")

    # Print available indicators
    indicator_cols = [
        c for c in health_gdf.columns
        if c not in ["geometry", "name", "name_fr", "phu_id", "area_sq_km", "phu_name"]
        and not c.startswith("_")
    ]
    if indicator_cols:
        print(f"\nAvailable indicators ({len(indicator_cols)}):")
        for col in sorted(indicator_cols):
            non_null = health_gdf[col].notna().sum()
            print(f"  - {col}: {non_null}/{len(health_gdf)} PHUs with data")


if __name__ == "__main__":
    asyncio.run(main())
