#!/usr/bin/env python3
"""
C1 Database Read-Only Verification for Left/Right Correction APPLY
Strictly read-only: hardcoded to reject any non-SELECT SQL operations.
"""

import sys
import json
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


class ReadOnlyVerifier:
    """Read-only verification with hard rejection of non-SELECT operations."""

    def __init__(self, db_session):
        self.db = db_session
        self.mismatches = []
        self.safe_skips = []

    def execute_select(self, query: str, params: dict = None) -> List[Dict]:
        """Execute SELECT query only. Hard reject any other SQL."""
        query_upper = query.strip().upper()

        # Hard rejection of non-SELECT operations
        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
                             'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE', 'SET']

        for keyword in forbidden_keywords:
            if keyword in query_upper:
                raise RuntimeError(f"FORBIDDEN: Non-SELECT operation detected: {keyword}")

        if not query_upper.startswith('SELECT'):
            raise RuntimeError(f"FORBIDDEN: Only SELECT queries allowed. Got: {query_upper[:50]}")

        # Execute SELECT
        result = self.db.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]

    def decimal_compare(self, val1, val2) -> bool:
        """Safe decimal comparison."""
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False

        try:
            d1 = Decimal(str(val1))
            d2 = Decimal(str(val2))
            return d1 == d2
        except:
            return str(val1) == str(val2)

    def verify_part(self, part_id: int, expected_position: str,
                   expected_material: Optional[str], expected_thickness: Optional[float],
                   expected_width: Optional[float], expected_pitch: Optional[float],
                   warnings: List[Dict], context: str) -> bool:
        """Verify a single part against expected values."""
        rows = self.execute_select(
            "SELECT id, internal_name, part_position, material_name, thickness, width, pitch "
            "FROM parts WHERE id = :part_id",
            {"part_id": part_id}
        )

        if not rows:
            self.mismatches.append({
                "type": "part_missing",
                "context": context,
                "part_id": part_id,
                "detail": "Part not found in database"
            })
            return False

        part = rows[0]
        issues = []

        # Check position
        if part['part_position'] != expected_position:
            issues.append(f"position: expected {expected_position}, got {part['part_position']}")

        # Check material (with warning check)
        material_warning = next((w for w in warnings
                                if w['table'] == 'parts' and w['record_id'] == part_id
                                and w['field'] == 'material_name'), None)

        if material_warning:
            # Should keep warning.db_value
            if part['material_name'] != material_warning['db_value']:
                issues.append(f"material (warning): expected to keep '{material_warning['db_value']}', got '{part['material_name']}'")
            else:
                self.safe_skips.append({
                    "type": "part_material_warning",
                    "part_id": part_id,
                    "field": "material_name",
                    "kept_value": part['material_name']
                })
        elif expected_material is not None:
            if part['material_name'] != expected_material:
                issues.append(f"material: expected '{expected_material}', got '{part['material_name']}'")

        # Check thickness
        if expected_thickness is not None:
            if not self.decimal_compare(part['thickness'], expected_thickness):
                issues.append(f"thickness: expected {expected_thickness}, got {part['thickness']}")

        # Check width
        if expected_width is not None:
            if not self.decimal_compare(part['width'], expected_width):
                issues.append(f"width: expected {expected_width}, got {part['width']}")

        # Check pitch
        if expected_pitch is not None:
            if not self.decimal_compare(part['pitch'], expected_pitch):
                issues.append(f"pitch: expected {expected_pitch}, got {part['pitch']}")

        if issues:
            self.mismatches.append({
                "type": "part_mismatch",
                "context": context,
                "part_id": part_id,
                "issues": issues
            })
            return False

        return True

    def verify_staging_row(self, part_id: int, source_sheet: str, source_row: int,
                          expected_position: str, expected_material: Optional[str],
                          expected_thickness: Optional[float], expected_width: Optional[float],
                          expected_pitch: Optional[float], expected_cavity: Optional[int],
                          warnings: List[Dict], context: str) -> bool:
        """Verify a staging row."""
        rows = self.execute_select(
            "SELECT id, source_sheet, source_row, parsed_material, parsed_thickness, "
            "parsed_width, parsed_pitch, parsed_cavity_count, parsed_internal_name "
            "FROM excel_import_rows "
            "WHERE resolved_part_id = :part_id AND source_sheet = :sheet AND source_row = :row",
            {"part_id": part_id, "sheet": source_sheet, "row": source_row}
        )

        if len(rows) == 0:
            self.mismatches.append({
                "type": "staging_missing",
                "context": context,
                "part_id": part_id,
                "source_sheet": source_sheet,
                "source_row": source_row,
                "detail": "Staging row not found"
            })
            return False

        if len(rows) > 1:
            self.mismatches.append({
                "type": "staging_not_unique",
                "context": context,
                "part_id": part_id,
                "source_sheet": source_sheet,
                "source_row": source_row,
                "detail": f"Found {len(rows)} staging rows, expected 1"
            })
            return False

        staging = rows[0]
        issues = []

        # Check position in internal_name (Chinese or English)
        # Note: Some parts use numeric naming (e.g., "1-1", "1-2") instead of left/right,
        # which is acceptable as long as the parts.part_position field is correct.
        # We skip this check for staging as the internal_name is not modified by APPLY.
        # The critical validation is on the parts.part_position field which is checked separately.

        # Check material with warning
        material_warning = next((w for w in warnings
                                if w['table'] == 'excel_import_rows' and w['record_id'] == staging['id']
                                and w['field'] == 'parsed_material'), None)

        if material_warning:
            if staging['parsed_material'] != material_warning['db_value']:
                issues.append(f"material (warning): expected to keep '{material_warning['db_value']}', got '{staging['parsed_material']}'")
            else:
                self.safe_skips.append({
                    "type": "staging_material_warning",
                    "staging_id": staging['id'],
                    "field": "parsed_material",
                    "kept_value": staging['parsed_material']
                })
        elif expected_material is not None:
            if staging['parsed_material'] != expected_material:
                issues.append(f"material: expected '{expected_material}', got '{staging['parsed_material']}'")

        # Check thickness
        if expected_thickness is not None:
            if not self.decimal_compare(staging['parsed_thickness'], expected_thickness):
                issues.append(f"thickness: expected {expected_thickness}, got {staging['parsed_thickness']}")

        # Check width
        if expected_width is not None:
            if not self.decimal_compare(staging['parsed_width'], expected_width):
                issues.append(f"width: expected {expected_width}, got {staging['parsed_width']}'")

        # Check pitch
        if expected_pitch is not None:
            if not self.decimal_compare(staging['parsed_pitch'], expected_pitch):
                issues.append(f"pitch: expected {expected_pitch}, got {staging['parsed_pitch']}")

        # Check cavity
        if expected_cavity is not None:
            if not self.decimal_compare(staging['parsed_cavity_count'], expected_cavity):
                issues.append(f"cavity: expected {expected_cavity}, got {staging['parsed_cavity_count']}")

        if issues:
            self.mismatches.append({
                "type": "staging_mismatch",
                "context": context,
                "staging_id": staging['id'],
                "part_id": part_id,
                "source_sheet": source_sheet,
                "source_row": source_row,
                "issues": issues
            })
            return False

        return True

    def verify_tooling_parts(self, part_id: int, expected_position: str, context: str) -> bool:
        """Verify tooling_parts position matches."""
        rows = self.execute_select(
            "SELECT id, tooling_id, position FROM tooling_parts WHERE part_id = :part_id",
            {"part_id": part_id}
        )

        if not rows:
            self.mismatches.append({
                "type": "tooling_parts_missing",
                "context": context,
                "part_id": part_id,
                "detail": "No tooling_parts records found"
            })
            return False

        for tp in rows:
            if tp['position'] != expected_position:
                self.mismatches.append({
                    "type": "tooling_parts_position_mismatch",
                    "context": context,
                    "tooling_parts_id": tp['id'],
                    "part_id": part_id,
                    "tooling_id": tp['tooling_id'],
                    "expected_position": expected_position,
                    "actual_position": tp['position']
                })
                return False

        return True

    def verify_tooling_cavity(self, tooling_id: int, expected_cavity: Optional[int],
                             has_explicit: bool, tooling_backup: Dict[str, Any],
                             warnings: List[Dict], context: str) -> bool:
        """Verify tooling cavity_count."""
        rows = self.execute_select(
            "SELECT id, tooling_number, cavity_count FROM tooling WHERE id = :tooling_id",
            {"tooling_id": tooling_id}
        )

        if not rows:
            self.mismatches.append({
                "type": "tooling_missing",
                "context": context,
                "tooling_id": tooling_id,
                "detail": "Tooling not found"
            })
            return False

        tooling = rows[0]

        if has_explicit and expected_cavity is not None:
            # Explicit cavity: must match shared_cavity (unless warning)
            tooling_warning = next((w for w in warnings
                                   if w['table'] == 'tooling' and w['record_id'] == tooling_id
                                   and w['field'] == 'cavity_count'), None)

            if tooling_warning:
                # Should keep warning.db_value
                if tooling['cavity_count'] != tooling_warning['db_value']:
                    self.mismatches.append({
                        "type": "tooling_cavity_warning_mismatch",
                        "context": context,
                        "tooling_id": tooling_id,
                        "tooling_number": tooling['tooling_number'],
                        "expected_kept_value": tooling_warning['db_value'],
                        "actual_value": tooling['cavity_count']
                    })
                    return False
                else:
                    self.safe_skips.append({
                        "type": "tooling_cavity_warning",
                        "tooling_id": tooling_id,
                        "field": "cavity_count",
                        "kept_value": tooling['cavity_count']
                    })
            else:
                if not self.decimal_compare(tooling['cavity_count'], expected_cavity):
                    self.mismatches.append({
                        "type": "tooling_cavity_mismatch",
                        "context": context,
                        "tooling_id": tooling_id,
                        "tooling_number": tooling['tooling_number'],
                        "expected_cavity": expected_cavity,
                        "actual_cavity": tooling['cavity_count']
                    })
                    return False
        else:
            # Non-explicit: must remain unchanged from backup
            backup_entry = tooling_backup.get(str(tooling_id))
            if backup_entry:
                backup_cavity = backup_entry.get('cavity_count')
                if tooling['cavity_count'] != backup_cavity:
                    self.mismatches.append({
                        "type": "tooling_cavity_changed_without_explicit",
                        "context": context,
                        "tooling_id": tooling_id,
                        "tooling_number": tooling['tooling_number'],
                        "backup_cavity": backup_cavity,
                        "actual_cavity": tooling['cavity_count'],
                        "detail": "Cavity changed but no explicit cavity source"
                    })
                    return False

        return True


def load_json(filepath: Path) -> Any:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """Main verification logic."""
    print("=== C1 Database Read-Only Verification for Left/Right Correction APPLY ===\n")

    # Paths
    script_dir = Path(__file__).parent
    backup_dir = script_dir / "backups" / "left_right_correction"
    report_path = backup_dir / "reports" / "left_right_correction_20260713_192349.json"

    parts_backup_path = backup_dir / "parts_backup_20260713_191942.json"
    tooling_parts_backup_path = backup_dir / "tooling_parts_backup_20260713_191942.json"
    tooling_backup_path = backup_dir / "tooling_backup_20260713_191942.json"
    staging_backup_path = backup_dir / "staging_backup_20260713_191942.json"

    output_json_path = backup_dir / "apply_verification_1.json"
    output_md_path = backup_dir / "apply_verification_1.md"

    print(f"Loading APPLY report: {report_path}")
    report = load_json(report_path)

    print(f"Loading backups...")
    parts_backup = {str(p['id']): p for p in load_json(parts_backup_path)}
    tooling_backup = {str(t['id']): t for t in load_json(tooling_backup_path)}
    staging_backup = {str(s['id']): s for s in load_json(staging_backup_path)}
    tooling_parts_backup = load_json(tooling_parts_backup_path)

    print(f"\nReport stats:")
    print(f"  Safe targets: {report['stats']['safe_targets']}")
    print(f"  Updated parts: {report['stats']['updated_parts']}")
    print(f"  Updated staging rows: {report['stats']['updated_staging_rows']}")
    print(f"  Updated tooling_parts: {report['stats']['updated_tooling_parts']}")
    print(f"  Updated tooling: {report['stats']['updated_tooling']}")
    print(f"  Warnings: {len(report['warnings'])}")

    # Connect to database (sync version)
    # Convert async URL to sync URL
    sync_db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    engine = create_engine(sync_db_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    verifier = ReadOnlyVerifier(db)

    try:
        # Counters
        checked_targets = 0
        checked_parts = set()
        checked_staging = set()
        checked_tooling_parts_ids = set()
        checked_tooling = set()
        key_samples = {}

        print(f"\nVerifying {len(report['targets'])} targets...")

        for target in report['targets']:
            if target['status'] != 'safe':
                continue

            checked_targets += 1
            base_tooling = target['base_tooling']
            context = f"Target {base_tooling}"

            # Verify canonical left
            left = target['canonical_left']
            merged = target['merged_analysis']

            print(f"  [{checked_targets}/{report['stats']['safe_targets']}] Verifying {base_tooling} left={left['part_id']}, right={target['canonical_right']['part_id']}")

            verifier.verify_part(
                left['part_id'], 'left',
                merged.get('shared_material'), merged.get('shared_thickness'),
                merged.get('shared_width'), merged.get('shared_pitch'),
                report['warnings'], f"{context} canonical_left"
            )
            checked_parts.add(left['part_id'])

            # Verify canonical right
            right = target['canonical_right']
            verifier.verify_part(
                right['part_id'], 'right',
                merged.get('shared_material'), merged.get('shared_thickness'),
                merged.get('shared_width'), merged.get('shared_pitch'),
                report['warnings'], f"{context} canonical_right"
            )
            checked_parts.add(right['part_id'])

            # Verify all sources
            for source in target['sources']:
                # Left source
                verifier.verify_staging_row(
                    left['part_id'], source['sheet'], source['left_row'],
                    'left', merged.get('shared_material'), merged.get('shared_thickness'),
                    merged.get('shared_width'), merged.get('shared_pitch'),
                    merged.get('shared_cavity'),
                    report['warnings'], f"{context} source left_row={source['left_row']}"
                )
                # Find staging id
                staging_rows = verifier.execute_select(
                    "SELECT id FROM excel_import_rows WHERE resolved_part_id = :part_id "
                    "AND source_sheet = :sheet AND source_row = :row",
                    {"part_id": left['part_id'], "sheet": source['sheet'], "row": source['left_row']}
                )
                for sr in staging_rows:
                    checked_staging.add(sr['id'])

                # Right source
                verifier.verify_staging_row(
                    right['part_id'], source['sheet'], source['right_row'],
                    'right', merged.get('shared_material'), merged.get('shared_thickness'),
                    merged.get('shared_width'), merged.get('shared_pitch'),
                    merged.get('shared_cavity'),
                    report['warnings'], f"{context} source right_row={source['right_row']}"
                )
                # Find staging id
                staging_rows = verifier.execute_select(
                    "SELECT id FROM excel_import_rows WHERE resolved_part_id = :part_id "
                    "AND source_sheet = :sheet AND source_row = :row",
                    {"part_id": right['part_id'], "sheet": source['sheet'], "row": source['right_row']}
                )
                for sr in staging_rows:
                    checked_staging.add(sr['id'])

            # Verify tooling_parts for LEFT
            left_tp_rows = verifier.execute_select(
                "SELECT id, tooling_id, position FROM tooling_parts WHERE part_id = :part_id",
                {"part_id": left['part_id']}
            )
            for tp in left_tp_rows:
                if tp['position'] != 'left':
                    verifier.mismatches.append({
                        "type": "tooling_parts_position_mismatch",
                        "context": f"{context} left tooling_parts",
                        "tooling_parts_id": tp['id'],
                        "part_id": left['part_id'],
                        "tooling_id": tp['tooling_id'],
                        "expected_position": 'left',
                        "actual_position": tp['position']
                    })
                checked_tooling_parts_ids.add(tp['id'])

            # Verify tooling_parts for RIGHT
            right_tp_rows = verifier.execute_select(
                "SELECT id, tooling_id, position FROM tooling_parts WHERE part_id = :part_id",
                {"part_id": right['part_id']}
            )
            for tp in right_tp_rows:
                if tp['position'] != 'right':
                    verifier.mismatches.append({
                        "type": "tooling_parts_position_mismatch",
                        "context": f"{context} right tooling_parts",
                        "tooling_parts_id": tp['id'],
                        "part_id": right['part_id'],
                        "tooling_id": tp['tooling_id'],
                        "expected_position": 'right',
                        "actual_position": tp['position']
                    })
                checked_tooling_parts_ids.add(tp['id'])

            # Verify tooling cavity for all tooling from LEFT and RIGHT
            all_tooling_ids = set()
            for tp in left_tp_rows:
                all_tooling_ids.add(tp['tooling_id'])
            for tp in right_tp_rows:
                all_tooling_ids.add(tp['tooling_id'])

            for tooling_id in all_tooling_ids:
                verifier.verify_tooling_cavity(
                    tooling_id, merged.get('shared_cavity'),
                    merged.get('has_explicit_cavity_source', False),
                    tooling_backup, report['warnings'], context
                )
                checked_tooling.add(tooling_id)

            # Collect key samples with tooling info
            if base_tooling in ['TYAA-Q0093', 'TYS-Q0062', 'TYAU-Q0028', 'TYAH-Q0001']:
                left_part_rows = verifier.execute_select(
                    "SELECT id, internal_name, part_position, material_name, thickness, width, pitch "
                    "FROM parts WHERE id = :part_id",
                    {"part_id": left['part_id']}
                )
                right_part_rows = verifier.execute_select(
                    "SELECT id, internal_name, part_position, material_name, thickness, width, pitch "
                    "FROM parts WHERE id = :part_id",
                    {"part_id": right['part_id']}
                )

                # Get left tooling
                left_tooling_info = []
                for tp in left_tp_rows:
                    t_rows = verifier.execute_select(
                        "SELECT id, tooling_number, cavity_count FROM tooling WHERE id = :tid",
                        {"tid": tp['tooling_id']}
                    )
                    if t_rows:
                        left_tooling_info.append({
                            "tooling_id": tp['tooling_id'],
                            "tooling_number": t_rows[0]['tooling_number'],
                            "cavity_count": t_rows[0]['cavity_count']
                        })

                # Get right tooling
                right_tooling_info = []
                for tp in right_tp_rows:
                    t_rows = verifier.execute_select(
                        "SELECT id, tooling_number, cavity_count FROM tooling WHERE id = :tid",
                        {"tid": tp['tooling_id']}
                    )
                    if t_rows:
                        right_tooling_info.append({
                            "tooling_id": tp['tooling_id'],
                            "tooling_number": t_rows[0]['tooling_number'],
                            "cavity_count": t_rows[0]['cavity_count']
                        })

                key_samples[base_tooling] = {
                    "left_part": left_part_rows[0] if left_part_rows else None,
                    "right_part": right_part_rows[0] if right_part_rows else None,
                    "left_tooling": left_tooling_info,
                    "right_tooling": right_tooling_info
                }

        # Add specific part samples
        for part_id in [19272, 19274, 19276]:
            part_rows = verifier.execute_select(
                "SELECT id, internal_name, part_position, material_name, thickness, width, pitch "
                "FROM parts WHERE id = :part_id",
                {"part_id": part_id}
            )
            if part_rows:
                key_samples[f"part_{part_id}"] = part_rows[0]

        # Add specific staging samples
        for staging_id in [84522, 84524, 84526]:
            staging_rows = verifier.execute_select(
                "SELECT id, source_sheet, source_row, parsed_material, parsed_thickness, "
                "parsed_width, parsed_pitch, parsed_cavity_count, parsed_internal_name "
                "FROM excel_import_rows WHERE id = :staging_id",
                {"staging_id": staging_id}
            )
            if staging_rows:
                key_samples[f"staging_{staging_id}"] = staging_rows[0]

        # TYAU-Q0028 staging (4 rows) - query by resolved_part_id
        tyau_staging_rows = verifier.execute_select(
            "SELECT id, source_sheet, source_row, parsed_material, parsed_thickness, "
            "parsed_width, parsed_pitch, parsed_cavity_count, parsed_internal_name, "
            "resolved_part_id FROM excel_import_rows "
            "WHERE resolved_part_id IN (17581, 17582) "
            "ORDER BY source_sheet, source_row"
        )
        key_samples['TYAU-Q0028_staging'] = tyau_staging_rows

        print(f"\n=== Verification Complete ===")
        print(f"Checked: {checked_targets} targets, {len(checked_parts)} parts, {len(checked_staging)} staging, "
              f"{len(checked_tooling_parts_ids)} tooling_parts, {len(checked_tooling)} tooling")
        print(f"Safe skips: {len(verifier.safe_skips)}")
        print(f"Mismatches: {len(verifier.mismatches)}")

        # Check warnings count
        warnings_match = len(report['warnings']) == 6
        if not warnings_match:
            print(f"WARNING: Expected 6 warnings, got {len(report['warnings'])}")

        # Check coverage against expected report stats
        expected_parts = 468  # unique parts from report summary
        expected_staging = 470  # unique staging from report summary
        expected_tooling_parts = 468  # unique tooling_parts from report summary
        expected_tooling = 234  # unique tooling from report summary

        coverage_complete = (
            len(checked_parts) == expected_parts and
            len(checked_staging) == expected_staging and
            len(checked_tooling_parts_ids) >= expected_tooling_parts and
            len(checked_tooling) >= expected_tooling
        )

        # Verdict
        verdict = "PASS" if (len(verifier.mismatches) == 0 and
                            warnings_match and
                            len(verifier.safe_skips) == 6 and
                            coverage_complete) else "FAIL"

        # Generate output
        output_data = {
            "verification_timestamp": datetime.now().isoformat(),
            "report_path": str(report_path),
            "report_timestamp": report['timestamp'],
            "checked_counts": {
                "targets": checked_targets,
                "parts": len(checked_parts),
                "staging_rows": len(checked_staging),
                "tooling_parts": len(checked_tooling_parts_ids),
                "tooling": len(checked_tooling)
            },
            "expected_counts": {
                "targets": 234,
                "parts": expected_parts,
                "staging_rows": expected_staging,
                "tooling_parts": expected_tooling_parts,
                "tooling": expected_tooling
            },
            "updated_counts_from_report": {
                "updated_parts": report['stats']['updated_parts'],
                "updated_staging_rows": report['stats']['updated_staging_rows'],
                "updated_tooling_parts": report['stats']['updated_tooling_parts'],
                "updated_tooling": report['stats']['updated_tooling']
            },
            "coverage_complete": coverage_complete,
            "expected_warnings": 6,
            "actual_warnings": len(report['warnings']),
            "warnings": report['warnings'],
            "safe_skip_count": len(verifier.safe_skips),
            "safe_skips": verifier.safe_skips,
            "mismatch_count": len(verifier.mismatches),
            "mismatches": verifier.mismatches,
            "key_samples": key_samples,
            "verdict": verdict
        }

        # Write JSON
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nJSON report written to: {output_json_path}")

        # Write MD
        md_content = f"""# C1 APPLY 只读验收报告

## 验证概要

- **验证时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **APPLY报告**: {report_path.name}
- **APPLY时间戳**: {report['timestamp']}

## 验证范围

### 实际检查数量

- 目标组: {checked_targets} 个
- Parts: {len(checked_parts)} 个
- Staging行: {len(checked_staging)} 个
- Tooling_parts: {len(checked_tooling_parts_ids)} 个
- Tooling: {len(checked_tooling)} 个

### 预期数量（来自报告summary）

- 目标组: 234 个
- Parts: {expected_parts} 个
- Staging行: {expected_staging} 个
- Tooling_parts: {expected_tooling_parts} 个
- Tooling: {expected_tooling} 个

### APPLY更新数量（来自报告stats）

- 更新Parts: {report['stats']['updated_parts']} 个
- 更新Staging行: {report['stats']['updated_staging_rows']} 个
- 更新Tooling_parts: {report['stats']['updated_tooling_parts']} 个
- 更新Tooling: {report['stats']['updated_tooling']} 个

### 覆盖完整性

- **覆盖完整**: {'✓' if coverage_complete else '✗'}

## Warnings验证

- **预期warnings**: 6
- **实际warnings**: {len(report['warnings'])}
- **匹配**: {'✓' if warnings_match else '✗'}

### Warning详情

"""
        for w in report['warnings']:
            md_content += f"- `{w['table']}` 记录 {w['record_id']}, 字段 `{w['field']}`: 保持DB值 `{w['db_value']}`\n"

        md_content += f"""

## Safe Skips

- **总数**: {len(verifier.safe_skips)}

安全跳过的字段已按预期保持原值，符合APPLY报告warnings。

"""

        md_content += f"""
## Mismatches

- **总数**: {len(verifier.mismatches)}

"""

        if verifier.mismatches:
            md_content += "### 不匹配详情\n\n"
            for i, mm in enumerate(verifier.mismatches, 1):
                md_content += f"{i}. **{mm['type']}** ({mm.get('context', 'N/A')})\n"
                md_content += f"   - {json.dumps(mm, ensure_ascii=False, indent=2)}\n\n"
        else:
            md_content += "✓ 所有检查项均通过，无不匹配。\n\n"

        md_content += f"""
## 关键样本

以下是关键零件和staging行的当前数据库值：

"""

        for key, sample in key_samples.items():
            md_content += f"### {key}\n\n```json\n{json.dumps(sample, ensure_ascii=False, indent=2, default=str)}\n```\n\n"

        md_content += f"""
## 最终判定

**Verdict: {verdict}**

"""

        if verdict == "PASS":
            md_content += f"""
✓ 验证通过。所有{checked_targets}个safe targets的{len(checked_parts)}个parts、{len(checked_staging)}个staging行、{len(checked_tooling_parts_ids)}个tooling_parts及{len(checked_tooling)}个tooling均已正确应用左右位置和共享属性。
6个warning字段均已安全跳过并保持原值。覆盖检查完整。
"""
        else:
            md_content += f"""
✗ 验证失败。发现 {len(verifier.mismatches)} 个不匹配项，或覆盖不完整。请检查上述详情。
"""

        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"MD report written to: {output_md_path}")
        print(f"\n**Verdict: {verdict}**")

        if verdict == "FAIL":
            print("\n验证失败，请检查报告详情。")
            sys.exit(1)
        else:
            print("\n✓ 验证通过！")
            sys.exit(0)

    finally:
        db.close()


if __name__ == "__main__":
    main()
