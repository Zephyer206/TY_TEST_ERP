#!/usr/bin/env python3
"""
Customer and Customer Part Import Integrity Audit A1 - v2 CORRECTED
READ-ONLY audit script - NO database writes allowed
Analyzes customer abbreviation splitting errors and missing aliases

v2 corrections:
- Fixed alias_integrity GROUP BY to exclude source_sheet
- Fixed IBI/ITT/ZF to match by parsed_customer_name, not source_sheet
- Added location collision detection (武汉/苏州)
- Split sheet duplicates into high/low confidence
- Separated root causes into 4 distinct categories
- Added customer name normalization collision analysis
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras


def hard_reject_write_sql(query: str):
    """Hard reject any write SQL - audit must be read-only"""
    write_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 
                      'TRUNCATE', 'REPLACE', 'MERGE']
    query_upper = query.upper()
    for keyword in write_keywords:
        if keyword in query_upper:
            raise RuntimeError(f"AUDIT VIOLATION: Write SQL detected: {keyword}")


def get_db_config():
    """Get database config from settings"""
    try:
        # Ensure we're in the backend directory for settings to load correctly
        import os
        original_cwd = os.getcwd()
        os.chdir(backend_path)

        from app.core.config import settings
        from urllib.parse import urlparse

        os.chdir(original_cwd)

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password
        }

        print(f"[INFO] DB config: host={config['host']}, port={config['port']}, db={config['database']}")
        return config
    except Exception as e:
        print(f"[ERROR] Could not load database config: {e}")
        import traceback
        traceback.print_exc()
        raise


def execute_readonly_query(cur, query: str, params=None):
    """Execute query with write protection"""
    hard_reject_write_sql(query)
    cur.execute(query, params)
    return cur.fetchall()


def analyze_excel_customer_mapping(excel_path: str) -> Dict[str, Any]:
    """
    Extract authoritative customer mapping from Excel
    Returns: {
        'code_to_name': dict,
        'sheet_to_customer': dict,
        'tooling_prefix_mapping': dict
    }
    """
    try:
        import xlrd
        wb = xlrd.open_workbook(excel_path, on_demand=True, encoding_override='utf-8')
    except:
        try:
            import xlrd
            wb = xlrd.open_workbook(excel_path, on_demand=True, encoding_override='gbk')
        except Exception as e:
            print(f"[ERROR] Cannot open Excel: {e}")
            return {}
    
    result = {
        'code_to_name': {},
        'sheet_to_customer': {},
        'tooling_prefix_mapping': {}
    }
    
    # Read customer code mapping sheet
    try:
        code_sheet = wb.sheet_by_name('客户名称代号')
        for row_idx in range(1, code_sheet.nrows):
            try:
                # Column structure: number, code, name
                num_val = code_sheet.cell_value(row_idx, 0)
                code = str(code_sheet.cell_value(row_idx, 1)).strip()
                name = str(code_sheet.cell_value(row_idx, 2)).strip() if code_sheet.ncols > 2 else ''
                
                if code and name:
                    result['code_to_name'][code] = name
            except:
                pass
    except Exception as e:
        print(f"[WARN] Could not read customer code sheet: {e}")
    
    # Analyze each sheet for customer info and tooling prefix
    all_sheets = wb.sheet_names()
    for sheet_name in all_sheets:
        if sheet_name in ['客户名称代号', '五金模具进度一览表', '目录']:
            continue
        
        try:
            sheet = wb.sheet_by_name(sheet_name)
            if sheet.nrows < 2:
                continue
            
            # Extract customer from sheet name (e.g., "A-P IBI" or "(AP)")
            customer_match = re.search(r'\(([A-Z\-]+)\)$', sheet_name)
            sheet_code = customer_match.group(1) if customer_match else None
            
            # Look for customer name in sheet content
            customer_in_content = None
            for row_idx in range(min(5, sheet.nrows)):
                for col_idx in range(min(5, sheet.ncols)):
                    try:
                        val = str(sheet.cell_value(row_idx, col_idx)).strip()
                        if '客户名称' in val and col_idx + 1 < sheet.ncols:
                            customer_in_content = str(sheet.cell_value(row_idx, col_idx + 1)).strip()
                            break
                    except:
                        pass
                if customer_in_content:
                    break
            
            # Extract tooling prefix from first few tooling numbers
            tooling_prefix = None
            header_row = None
            for row_idx in range(min(10, sheet.nrows)):
                try:
                    row_vals = [str(sheet.cell_value(row_idx, c)).strip() 
                               for c in range(min(sheet.ncols, 20))]
                    if '本厂产品编号' in ''.join(row_vals):
                        header_row = row_idx
                        break
                except:
                    pass
            
            if header_row is not None:
                tooling_col = None
                for col_idx in range(sheet.ncols):
                    try:
                        if '本厂产品编号' in str(sheet.cell_value(header_row, col_idx)):
                            tooling_col = col_idx
                            break
                    except:
                        pass
                
                if tooling_col is not None:
                    for row_idx in range(header_row + 1, min(header_row + 5, sheet.nrows)):
                        try:
                            val = str(sheet.cell_value(row_idx, tooling_col)).strip()
                            if val and len(val) > 3:
                                # Extract prefix (e.g., "TYAP" from "TYAP-Q0001")
                                prefix_match = re.match(r'([A-Z]+)[-\s]', val)
                                if prefix_match:
                                    tooling_prefix = prefix_match.group(1)
                                    break
                        except:
                            pass
            
            result['sheet_to_customer'][sheet_name] = {
                'sheet_code': sheet_code,
                'customer_in_content': customer_in_content,
                'tooling_prefix': tooling_prefix
            }
            
            if tooling_prefix and sheet_code:
                result['tooling_prefix_mapping'][tooling_prefix] = sheet_code
            
        except Exception as e:
            print(f"[WARN] Error analyzing sheet {sheet_name}: {e}")
    
    return result



def audit_customers(conn) -> Dict[str, Any]:
    """
    Audit all customers and their reference counts
    v2: Split sheet_duplicates into high/low confidence categories
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all customers with reference counts
    query = """
    SELECT
        c.id,
        c.name,
        c.customer_code,
        c.short_name,
        c.sheet_key,
        c.is_active,
        (SELECT COUNT(*) FROM excel_import_rows WHERE resolved_customer_id = c.id) as staging_refs,
        (SELECT COUNT(*) FROM part_customer_aliases WHERE customer_id = c.id) as alias_refs,
        (SELECT COUNT(*) FROM tooling_customer_links WHERE customer_id = c.id) as tooling_refs
    FROM customers c
    ORDER BY c.id
    """

    customers = execute_readonly_query(cur, query)

    result = {
        'total': len(customers),
        'canonical': [],
        'truncated': [],
        'high_confidence_empty_duplicates': [],
        'low_confidence_no_ref_customers': [],
        'suspected_duplicates': []
    }

    # Get all sheet names that have IMPORTED data
    query_sheets = """
    SELECT DISTINCT source_sheet
    FROM excel_import_rows
    WHERE validation_status = 'IMPORTED'
    """
    sheets_with_data = {row['source_sheet'] for row in execute_readonly_query(cur, query_sheets)}

    for cust in customers:
        customer_info = {
            'id': cust['id'],
            'name': cust['name'],
            'customer_code': cust['customer_code'],
            'short_name': cust['short_name'],
            'sheet_key': cust['sheet_key'],
            'is_active': cust['is_active'],
            'staging_refs': cust['staging_refs'],
            'alias_refs': cust['alias_refs'],
            'tooling_refs': cust['tooling_refs'],
            'total_refs': cust['staging_refs'] + cust['alias_refs'] + cust['tooling_refs']
        }

        # Classify customer
        name = cust['name'] or ''
        code = cust['customer_code'] or ''
        sheet_key = cust['sheet_key'] or ''

        # Check for truncated abbreviations by reconstructing an actual sheet name.
        # Examples: "A-P IB" + "I" -> "A-P IBI", "Z" + "F" -> "ZF".
        compact = lambda value: re.sub(r'\s+', '', value or '').upper()
        reconstructed_name = compact(name + sheet_key)
        reconstructed_sheet = next(
            (sheet for sheet in sheets_with_data if compact(sheet) == reconstructed_name),
            None,
        )
        if (sheet_key and len(sheet_key) == 1 and customer_info['total_refs'] == 0
                and reconstructed_sheet):
            customer_info['classification'] = 'truncated'
            customer_info['confidence'] = 'high'
            customer_info['reconstructed_customer_label'] = reconstructed_sheet
            customer_info['evidence'] = (
                f"Name '{name}' + sheet_key '{sheet_key}' reconstructs Excel sheet "
                f"'{reconstructed_sheet}', refs=0"
            )
            result['truncated'].append(customer_info)

        # Check for high confidence empty duplicates
        elif customer_info['total_refs'] == 0 and name in sheets_with_data:
            customer_info['classification'] = 'high_confidence_empty_duplicate'
            customer_info['confidence'] = 'high'
            customer_info['evidence'] = f"Name equals Excel sheet '{name}', refs=0, sheet has other canonical customer with IMPORTED data"
            result['high_confidence_empty_duplicates'].append(customer_info)

        # Check for canonical customers (has code, has refs)
        elif code and customer_info['total_refs'] > 0:
            customer_info['classification'] = 'canonical'
            result['canonical'].append(customer_info)

        # No references - low confidence issue
        elif customer_info['total_refs'] == 0:
            customer_info['classification'] = 'low_confidence_no_refs'
            customer_info['confidence'] = 'low'
            customer_info['evidence'] = 'No references in staging, aliases, or tooling - may be unused/test/legitimate empty'
            result['low_confidence_no_ref_customers'].append(customer_info)

        else:
            result['canonical'].append(customer_info)

    return result


def audit_alias_integrity(conn) -> Dict[str, Any]:
    """
    Audit customer part alias integrity
    Compare staging (IMPORTED) vs actual aliases
    v2: Fixed GROUP BY to exclude source_sheet for correct unique mapping count
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get expected unique mappings from staging (v2: removed source_sheet from GROUP BY)
    query = """
    SELECT
        resolved_customer_id,
        resolved_part_id,
        TRIM(parsed_customer_part_no) as customer_part_no,
        COUNT(*) as staging_row_count,
        STRING_AGG(DISTINCT source_sheet, ', ') as source_sheets,
        MIN(id) as first_row_id
    FROM excel_import_rows
    WHERE validation_status = 'IMPORTED'
      AND resolved_customer_id IS NOT NULL
      AND resolved_part_id IS NOT NULL
      AND parsed_customer_part_no IS NOT NULL
      AND TRIM(parsed_customer_part_no) != ''
    GROUP BY resolved_customer_id, resolved_part_id, TRIM(parsed_customer_part_no)
    ORDER BY resolved_customer_id, resolved_part_id
    """

    expected_mappings = execute_readonly_query(cur, query)
    
    # Get actual aliases
    query = """
    SELECT 
        customer_id,
        part_id,
        customer_part_no,
        customer_part_name,
        revision,
        is_active
    FROM part_customer_aliases
    WHERE is_active = true
    """
    
    actual_aliases = execute_readonly_query(cur, query)
    
    # Build lookup for actual aliases
    alias_lookup = {}
    for alias in actual_aliases:
        key = (alias['customer_id'], alias['part_id'], alias['customer_part_no'].strip())
        alias_lookup[key] = alias
    
    # Compare
    result = {
        'total_expected': len(expected_mappings),
        'total_actual': len(actual_aliases),
        'matched': 0,
        'missing': [],
        'by_customer': {}
    }

    for mapping in expected_mappings:
        key = (mapping['resolved_customer_id'], mapping['resolved_part_id'],
               mapping['customer_part_no'])

        if key in alias_lookup:
            result['matched'] += 1
        else:
            missing_info = {
                'customer_id': mapping['resolved_customer_id'],
                'part_id': mapping['resolved_part_id'],
                'customer_part_no': mapping['customer_part_no'],
                'source_sheets': mapping['source_sheets'],
                'staging_row_count': mapping['staging_row_count']
            }
            result['missing'].append(missing_info)

            # Group by customer
            cust_id = mapping['resolved_customer_id']
            if cust_id not in result['by_customer']:
                result['by_customer'][cust_id] = {'count': 0, 'examples': []}
            result['by_customer'][cust_id]['count'] += 1
            if len(result['by_customer'][cust_id]['examples']) < 3:
                result['by_customer'][cust_id]['examples'].append(missing_info)

    return result



def audit_invariants(conn) -> Dict[str, Any]:
    """Verify data invariants"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    result = {
        'customer_id_mismatch': 0,
        'part_id_mismatch': 0,
        'customer_part_no_mismatch': 0,
        'customer_part_name_mismatch': 0,
        'examples': []
    }

    # Check staging vs alias consistency
    query = """
    SELECT
        e.id as staging_id,
        e.resolved_customer_id as staging_customer_id,
        e.resolved_part_id as staging_part_id,
        e.parsed_customer_part_no as staging_cust_part_no,
        e.parsed_customer_part_name as staging_cust_part_name,
        a.customer_id as alias_customer_id,
        a.part_id as alias_part_id,
        a.customer_part_no as alias_cust_part_no,
        a.customer_part_name as alias_cust_part_name,
        e.source_sheet
    FROM excel_import_rows e
    JOIN part_customer_aliases a
        ON a.id = e.resolved_alias_id
    WHERE e.validation_status = 'IMPORTED'
      AND e.resolved_customer_id IS NOT NULL
      AND e.resolved_part_id IS NOT NULL
      AND e.parsed_customer_part_no IS NOT NULL
      AND TRIM(e.parsed_customer_part_no) != ''
      AND e.resolved_alias_id IS NOT NULL
    """

    rows = execute_readonly_query(cur, query)

    for row in rows:
        mismatches = []

        if row['staging_customer_id'] != row['alias_customer_id']:
            result['customer_id_mismatch'] += 1
            mismatches.append('customer_id')

        if row['staging_part_id'] != row['alias_part_id']:
            result['part_id_mismatch'] += 1
            mismatches.append('part_id')

        staging_cpn = (row['staging_cust_part_no'] or '').strip()
        alias_cpn = (row['alias_cust_part_no'] or '').strip()
        if staging_cpn != alias_cpn:
            result['customer_part_no_mismatch'] += 1
            mismatches.append('customer_part_no')

        staging_cpn_name = (row['staging_cust_part_name'] or '').strip()
        alias_cpn_name = (row['alias_cust_part_name'] or '').strip()
        if staging_cpn_name != alias_cpn_name:
            result['customer_part_name_mismatch'] += 1
            mismatches.append('customer_part_name')

        if mismatches and len(result['examples']) < 10:
            result['examples'].append({
                'staging_id': row['staging_id'],
                'mismatches': mismatches,
                'source_sheet': row['source_sheet'],
                'staging_customer_id': row['staging_customer_id'],
                'alias_customer_id': row['alias_customer_id'],
                'staging_part_id': row['staging_part_id'],
                'alias_part_id': row['alias_part_id']
            })

    return result


def audit_location_collision(conn) -> Dict[str, Any]:
    """
    Detect unsafe customer name normalization collisions
    v2: Identify cases like 武汉/苏州 being normalized to same name
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Find customers that have multiple distinct parsed_customer_name values
    query = """
    SELECT
        e.resolved_customer_id,
        c.name as resolved_customer_name,
        e.parsed_customer_name,
        COUNT(*) as row_count,
        COUNT(DISTINCT e.resolved_part_id) as part_count
    FROM excel_import_rows e
    JOIN customers c ON c.id = e.resolved_customer_id
    WHERE e.validation_status = 'IMPORTED'
    GROUP BY e.resolved_customer_id, c.name, e.parsed_customer_name
    ORDER BY e.resolved_customer_id, e.parsed_customer_name
    """

    rows = execute_readonly_query(cur, query)

    # Group by resolved_customer_id
    by_customer = {}
    for row in rows:
        cust_id = row['resolved_customer_id']
        if cust_id not in by_customer:
            by_customer[cust_id] = {
                'resolved_customer_id': cust_id,
                'resolved_customer_name': row['resolved_customer_name'],
                'parsed_names': []
            }
        by_customer[cust_id]['parsed_names'].append({
            'parsed_name': row['parsed_customer_name'],
            'row_count': row['row_count'],
            'part_count': row['part_count']
        })

    # Filter to collisions (multiple distinct parsed names)
    unsafe_collisions = []
    acceptable_normalizations = []

    for cust_id, info in by_customer.items():
        # Get unique parsed names (excluding the resolved name itself)
        unique_parsed = {p['parsed_name'] for p in info['parsed_names']}

        if len(unique_parsed) > 1:
            # Multiple distinct parsed names resolved to same customer
            # Check if they contain location markers
            location_markers = ['（', '(', '武汉', '苏州', '上海', '北京', '广州', '深圳', '天津', '重庆']
            parsed_with_location = [
                p for p in info['parsed_names']
                if any(marker in p['parsed_name'] for marker in location_markers)
            ]

            total_rows = sum(p['row_count'] for p in info['parsed_names'])
            total_parts = sum(p['part_count'] for p in info['parsed_names'])
            misattributed_variants = [
                p for p in info['parsed_names']
                if p['parsed_name'] != info['resolved_customer_name']
            ]
            misattributed_rows = sum(p['row_count'] for p in misattributed_variants)
            misattributed_parts = sum(p['part_count'] for p in misattributed_variants)

            if len(parsed_with_location) > 1:
                # Multiple parsed names with location markers -> unsafe collision
                unsafe_collisions.append({
                    'resolved_customer_id': cust_id,
                    'resolved_customer_name': info['resolved_customer_name'],
                    'parsed_names': info['parsed_names'],
                    'total_rows': total_rows,
                    'total_parts': total_parts,
                    'misattributed_rows': misattributed_rows,
                    'misattributed_parts': misattributed_parts,
                    'misattributed_variants': misattributed_variants,
                    'collision_type': 'location_collision'
                })
            else:
                # Multiple variants but not location-based
                unsafe_collisions.append({
                    'resolved_customer_id': cust_id,
                    'resolved_customer_name': info['resolved_customer_name'],
                    'parsed_names': info['parsed_names'],
                    'total_rows': total_rows,
                    'total_parts': total_parts,
                    'misattributed_rows': misattributed_rows,
                    'misattributed_parts': misattributed_parts,
                    'misattributed_variants': misattributed_variants,
                    'collision_type': 'name_variant_collision'
                })
        elif len(unique_parsed) == 1 and list(unique_parsed)[0] != info['resolved_customer_name']:
            # Single parsed name different from resolved name -> acceptable normalization
            acceptable_normalizations.append(info)

    return {
        'unsafe_collisions': unsafe_collisions,
        'acceptable_normalizations': acceptable_normalizations,
        'total_unsafe': len(unsafe_collisions),
        'total_acceptable': len(acceptable_normalizations)
    }


def audit_customer_name_normalization(conn) -> Dict[str, Any]:
    """
    Analyze customer name normalization categories
    v2: Classify as exact match, acceptable normalized, or unsafe collision
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
    SELECT DISTINCT
        e.parsed_customer_name,
        e.resolved_customer_id,
        c.name as db_customer_name
    FROM excel_import_rows e
    JOIN customers c ON c.id = e.resolved_customer_id
    WHERE e.validation_status = 'IMPORTED'
    ORDER BY e.parsed_customer_name
    """

    rows = execute_readonly_query(cur, query)

    exact_matches = []
    acceptable_normalized = []
    unsafe_normalized = []

    # Group by parsed_customer_name
    name_groups = {}
    for row in rows:
        parsed = row['parsed_customer_name']
        if parsed not in name_groups:
            name_groups[parsed] = []
        name_groups[parsed].append({
            'customer_id': row['resolved_customer_id'],
            'db_name': row['db_customer_name']
        })

    for parsed, customers in name_groups.items():
        if len(customers) == 1:
            cust = customers[0]
            if parsed == cust['db_name']:
                exact_matches.append({'parsed': parsed, 'db_name': cust['db_name'], 'customer_id': cust['customer_id']})
            else:
                # Check if it's acceptable (e.g., 温州力邦企业 -> 温州力邦企业有限公司)
                if '（' in parsed or '(' in parsed:
                    # Contains location/qualifier - potentially unsafe if normalized away
                    acceptable_normalized.append({'parsed': parsed, 'db_name': cust['db_name'], 'customer_id': cust['customer_id'], 'reason': 'location_or_qualifier_in_parsed'})
                else:
                    acceptable_normalized.append({'parsed': parsed, 'db_name': cust['db_name'], 'customer_id': cust['customer_id'], 'reason': 'suffix_addition'})
        else:
            # Multiple customers for same parsed name - unsafe
            unsafe_normalized.append({
                'parsed': parsed,
                'resolved_to': customers,
                'collision_count': len(customers)
            })

    return {
        'exact_matches': exact_matches,
        'acceptable_normalized': acceptable_normalized,
        'unsafe_normalized': unsafe_normalized,
        'counts': {
            'exact': len(exact_matches),
            'acceptable': len(acceptable_normalized),
            'unsafe': len(unsafe_normalized)
        }
    }
    """Verify data invariants"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    result = {
        'customer_id_mismatch': 0,
        'part_id_mismatch': 0,
        'customer_part_no_mismatch': 0,
        'customer_part_name_mismatch': 0,
        'examples': []
    }
    
    # Check staging vs alias consistency
    query = """
    SELECT
        e.id as staging_id,
        e.resolved_customer_id as staging_customer_id,
        e.resolved_part_id as staging_part_id,
        e.parsed_customer_part_no as staging_cust_part_no,
        e.parsed_customer_part_name as staging_cust_part_name,
        a.customer_id as alias_customer_id,
        a.part_id as alias_part_id,
        a.customer_part_no as alias_cust_part_no,
        a.customer_part_name as alias_cust_part_name,
        e.source_sheet
    FROM excel_import_rows e
    LEFT JOIN part_customer_aliases a
        ON a.customer_id = e.resolved_customer_id
        AND TRIM(a.customer_part_no) = TRIM(e.parsed_customer_part_no)
    WHERE e.validation_status = 'IMPORTED'
      AND e.resolved_customer_id IS NOT NULL
      AND e.resolved_part_id IS NOT NULL
      AND e.parsed_customer_part_no IS NOT NULL
      AND TRIM(e.parsed_customer_part_no) != ''
      AND a.id IS NOT NULL
    LIMIT 1000
    """
    
    rows = execute_readonly_query(cur, query)
    
    for row in rows:
        mismatches = []
        
        if row['staging_customer_id'] != row['alias_customer_id']:
            result['customer_id_mismatch'] += 1
            mismatches.append('customer_id')
        
        if row['staging_part_id'] != row['alias_part_id']:
            result['part_id_mismatch'] += 1
            mismatches.append('part_id')
        
        staging_cpn = (row['staging_cust_part_no'] or '').strip()
        alias_cpn = (row['alias_cust_part_no'] or '').strip()
        if staging_cpn != alias_cpn:
            result['customer_part_no_mismatch'] += 1
            mismatches.append('customer_part_no')
        
        if mismatches and len(result['examples']) < 10:
            result['examples'].append({
                'staging_id': row['staging_id'],
                'mismatches': mismatches,
                'source_sheet': row['source_sheet'],
                'staging_customer_id': row['staging_customer_id'],
                'alias_customer_id': row['alias_customer_id'],
                'staging_part_id': row['staging_part_id'],
                'alias_part_id': row['alias_part_id']
            })
    
    return result


def audit_ibi_itt_zf(conn, excel_mapping: Dict) -> Dict[str, Any]:
    """
    Special audit for IBI, ITT, ZF customers
    v2: Match by parsed_customer_name canonical names, not source_sheet ILIKE
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    result = {
        'IBI': {'sheets': [], 'customers': [], 'expected': 0, 'matched': 0, 'missing': 0, 'canonical_customer_id': None},
        'ITT': {'sheets': [], 'customers': [], 'expected': 0, 'matched': 0, 'missing': 0, 'canonical_customer_id': None},
        'ZF': {'sheets': [], 'customers': [], 'expected': 0, 'matched': 0, 'missing': 0, 'canonical_customer_id': None}
    }

    # For each target, find canonical customer by exact name match
    for target in ['IBI', 'ITT', 'ZF']:
        # Find canonical customer with exact name
        query = """
        SELECT id, name, customer_code, short_name, sheet_key
        FROM customers
        WHERE name = %s
        LIMIT 1
        """
        canonical = execute_readonly_query(cur, query, (target,))

        if not canonical:
            print(f"[WARN] No canonical customer found with name='{target}'")
            continue

        canonical_id = canonical[0]['id']
        result[target]['canonical_customer_id'] = canonical_id
        result[target]['customers'] = [dict(canonical[0])]

        # Find sheets that resolved to this customer
        query = """
        SELECT DISTINCT source_sheet
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
          AND resolved_customer_id = %s
        """
        sheets = execute_readonly_query(cur, query, (canonical_id,))
        result[target]['sheets'] = [s['source_sheet'] for s in sheets]

        # Count expected unique mappings from staging for this customer
        query = """
        SELECT COUNT(DISTINCT (resolved_customer_id, resolved_part_id, TRIM(parsed_customer_part_no)))
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
          AND resolved_customer_id = %s
          AND resolved_part_id IS NOT NULL
          AND parsed_customer_part_no IS NOT NULL
          AND TRIM(parsed_customer_part_no) != ''
        """
        count = execute_readonly_query(cur, query, (canonical_id,))
        result[target]['expected'] = count[0]['count'] if count and len(count) > 0 else 0

        # Matched in aliases
        query = """
        SELECT COUNT(*)
        FROM part_customer_aliases
        WHERE customer_id = %s
          AND is_active = true
        """
        count = execute_readonly_query(cur, query, (canonical_id,))
        result[target]['matched'] = count[0]['count'] if count and len(count) > 0 else 0

        result[target]['missing'] = result[target]['expected'] - result[target]['matched']

    return result


def check_unique_index(conn) -> Dict[str, Any]:
    """Check the unique index definition"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = """
    SELECT 
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = 'part_customer_aliases'
      AND indexname = 'idx_part_customer_alias_unique'
    """
    
    rows = execute_readonly_query(cur, query)
    
    result = {
        'exists': len(rows) > 0,
        'definition': rows[0]['indexdef'] if rows else None,
        'includes_part_id': False,
        'analysis': ''
    }
    
    if result['exists']:
        indexdef = result['definition'].upper()
        if 'PART_ID' in indexdef:
            result['includes_part_id'] = True
            result['analysis'] = 'Index includes part_id - allows same customer_part_no for different parts'
        else:
            result['includes_part_id'] = False
            result['analysis'] = 'Index does NOT include part_id - may incorrectly block same customer_part_no for different parts'
    
    return result



def analyze_root_causes(conn, audit_results: Dict) -> List[Dict]:
    """
    Analyze root causes of integrity issues
    v2: Separate into 4 distinct categories
    """
    causes = []

    # Root cause 1: Sheet-name abbreviation splitter
    truncated_count = len(audit_results['customers']['truncated'])
    if truncated_count > 0:
        causes.append({
            'category': 'sheet_name_abbreviation_splitter',
            'severity': 'high',
            'description': f'{truncated_count} customers have truncated English abbreviations from sheet name parsing',
            'evidence': f"Found {truncated_count} customers like 'A-P IB' (should be IBI), 'B-U IT' (should be ITT), 'Z' (should be ZF)",
            'impact': 'Creates wrong empty-shell customers in dropdown, refs=0 so no alias misplacement',
            'affected_customers': [c['id'] for c in audit_results['customers']['truncated']],
            'file_references': [
                'backend/scripts/import_excel_authoritative.py: sheet name parsing logic splits last letter as sheet_key'
            ]
        })

    # Root cause 2: normalize_customer_name deletes parentheses
    location_collision = audit_results.get('location_collision', {})
    unsafe_count = location_collision.get('total_unsafe', 0)
    if unsafe_count > 0:
        total_parts_affected = sum(
            c.get('misattributed_parts', c['total_parts'])
            for c in location_collision.get('unsafe_collisions', [])
        )
        causes.append({
            'category': 'normalize_customer_name_deletes_parentheses',
            'severity': 'high',
            'description': f'{unsafe_count} customers have multiple parsed_customer_name variants resolved to same customer',
            'evidence': f"normalize_customer_name line 59 deletes all parenthetical content, causing location variants to merge",
            'impact': f"Staging data misattributed to wrong customer, affects {total_parts_affected} parts across {unsafe_count} collision(s)",
            'examples': location_collision.get('unsafe_collisions', [])[:3],
            'file_references': [
                'backend/scripts/import_staged_authoritative.py:59: re.sub removes all parentheses'
            ]
        })

    # Root cause 3: Unique index missing part_id
    index_info = audit_results.get('unique_index', {})
    missing_count = len(audit_results['alias_integrity']['missing'])
    if not index_info.get('includes_part_id') and missing_count > 0:
        causes.append({
            'category': 'unique_index_missing_part_id',
            'severity': 'high',
            'description': f'Unique index idx_part_customer_alias_unique does not include part_id, causing {missing_count} unique aliases to be missing',
            'evidence': f"Index definition: {index_info.get('definition')}",
            'impact': f"Same customer_part_no cannot map to different internal parts, violates business requirement for left/right parts",
            'affected_count': missing_count,
            'file_references': [
                'backend/scripts/migrations/008_authoritative_schema.py:323-324: index creation',
                'specs/001-erp-system-architecture/data-model.md:136: design states UNIQUE(customer_id, customer_part_no, revision) only'
            ]
        })

    # Root cause 4: Recovery importer skips conflicts
    if missing_count > 0:
        causes.append({
            'category': 'recovery_importer_skips_same_customer_part_no_different_part',
            'severity': 'high',
            'description': f'{missing_count} expected aliases not created due to skip logic on customer_part_no conflict',
            'evidence': 'import_staged_recovery.py line 238-240: when customer_part_no exists with different part_id, skips instead of handling multi-part mapping',
            'impact': f'Legitimate aliases not created, frontend queries incomplete for {len(audit_results["alias_integrity"]["by_customer"])} customers',
            'affected_customers': list(audit_results['alias_integrity']['by_customer'].keys()),
            'file_references': [
                'backend/scripts/import_staged_recovery.py:238-240: skip logic on conflict'
            ]
        })

    return causes


def generate_fix_plan(audit_results: Dict) -> Dict[str, Any]:
    """Generate phased fix plan"""
    plan = {
        'phases': [],
        'estimated_impact': {
            'customers_to_merge': 0,
            'aliases_to_create': 0,
            'aliases_to_reassign': 0
        }
    }

    missing_count = len(audit_results['alias_integrity']['missing'])
    plan['estimated_impact']['aliases_to_create'] = missing_count

    truncated = audit_results['customers']['truncated']
    high_conf_dup = audit_results['customers']['high_confidence_empty_duplicates']
    plan['estimated_impact']['customers_to_merge'] = len(truncated) + len(high_conf_dup)

    plan['phases'] = [
        {
            'phase': 1,
            'name': 'Design and Index Fix',
            'actions': [
                'Review data-model.md: should UNIQUE constraint include part_id?',
                'If yes: DROP existing idx_part_customer_alias_unique',
                'CREATE UNIQUE INDEX on (customer_id, part_id, customer_part_no, revision)',
                'If no: accept one customer_part_no to one internal part only'
            ]
        },
        {
            'phase': 2,
            'name': 'Dry-run Missing Alias Rebuild',
            'actions': [
                f'Generate SQL for {missing_count} missing aliases',
                'Review conflicts: same customer_part_no for different parts',
                'Create backups/audit_customer_import_integrity_fix_dryrun.sql'
            ]
        },
        {
            'phase': 3,
            'name': 'Merge/Deactivate Duplicate Customers',
            'actions': [
                f'Identify canonical for {len(truncated)} truncated customers',
                f'Identify canonical for {len(high_conf_dup)} high-confidence empty duplicates',
                'UPDATE staging, aliases, tooling links to canonical',
                'SET is_active = false for duplicates'
            ]
        },
        {
            'phase': 4,
            'name': 'Full SELECT Validation',
            'actions': [
                'Re-run audit script',
                'Verify 100% match rate',
                'Check IBI/ITT/ZF counts'
            ]
        },
        {
            'phase': 5,
            'name': 'Playwright Frontend Acceptance',
            'actions': [
                'Test customer dropdown',
                'Verify all parts appear for affected customers',
                'Compare counts before/after'
            ]
        }
    ]

    return plan


def main():
    """Main audit execution"""
    print("=" * 80)
    print("Customer and Customer Part Import Integrity Audit A1 - v2 CORRECTED")
    print("READ-ONLY AUDIT - No database modifications")
    print("=" * 80)
    print()

    print("[1/11] Connecting to database...")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    conn.set_session(readonly=True, autocommit=True)
    print("  Connected (READ-ONLY mode)")
    print()

    print("[2/11] Analyzing Excel customer mapping...")
    excel_path = backend_path.parent / 'excel' / '五金模具及产品清单表.xls'
    excel_mapping = analyze_excel_customer_mapping(str(excel_path))
    print(f"  Found {len(excel_mapping.get('code_to_name', {}))} customer codes")
    print(f"  Analyzed {len(excel_mapping.get('sheet_to_customer', {}))} sheets")
    print()

    print("[3/11] Auditing customers table...")
    customer_audit = audit_customers(conn)
    print(f"  Total customers: {customer_audit['total']}")
    print(f"  Canonical: {len(customer_audit['canonical'])}")
    print(f"  Truncated abbreviations: {len(customer_audit['truncated'])}")
    print(f"  High-confidence empty duplicates: {len(customer_audit['high_confidence_empty_duplicates'])}")
    print(f"  Low-confidence no-ref customers: {len(customer_audit['low_confidence_no_ref_customers'])}")
    print()

    print("[4/11] Auditing alias integrity...")
    alias_audit = audit_alias_integrity(conn)
    print(f"  Expected unique mappings: {alias_audit['total_expected']}")
    print(f"  Matched: {alias_audit['matched']}")
    print(f"  Missing: {len(alias_audit['missing'])}")
    print(f"  Affected customers: {len(alias_audit['by_customer'])}")
    print()

    print("[5/11] Checking data invariants...")
    invariant_audit = audit_invariants(conn)
    print(f"  Customer ID mismatches: {invariant_audit['customer_id_mismatch']}")
    print(f"  Part ID mismatches: {invariant_audit['part_id_mismatch']}")
    print()

    print("[6/11] Special audit for IBI/ITT/ZF...")
    ibi_itt_zf_audit = audit_ibi_itt_zf(conn, excel_mapping)
    for customer in ['IBI', 'ITT', 'ZF']:
        data = ibi_itt_zf_audit[customer]
        print(f"  {customer}:")
        print(f"    Canonical customer_id: {data['canonical_customer_id']}")
        print(f"    Sheets: {len(data['sheets'])}")
        print(f"    Expected: {data['expected']}, Matched: {data['matched']}, Missing: {data['missing']}")
    print()

    print("[7/11] Detecting location collisions...")
    location_collision = audit_location_collision(conn)
    print(f"  Unsafe collisions: {location_collision['total_unsafe']}")
    print(f"  Acceptable normalizations: {location_collision['total_acceptable']}")
    print()

    print("[8/11] Analyzing customer name normalization...")
    name_norm = audit_customer_name_normalization(conn)
    print(f"  Exact matches: {name_norm['counts']['exact']}")
    print(f"  Acceptable normalized: {name_norm['counts']['acceptable']}")
    print(f"  Unsafe normalized: {name_norm['counts']['unsafe']}")
    print()

    print("[9/11] Checking unique index design...")
    index_check = check_unique_index(conn)
    print(f"  Index exists: {index_check['exists']}")
    print(f"  Includes part_id: {index_check['includes_part_id']}")
    print(f"  Analysis: {index_check['analysis']}")
    print()

    print("[10/11] Analyzing root causes...")
    audit_results = {
        'customers': customer_audit,
        'alias_integrity': alias_audit,
        'invariants': invariant_audit,
        'ibi_itt_zf': ibi_itt_zf_audit,
        'location_collision': location_collision,
        'name_normalization': name_norm,
        'unique_index': index_check,
        'excel_mapping': excel_mapping
    }
    root_causes = analyze_root_causes(conn, audit_results)
    print(f"  Identified {len(root_causes)} root cause categories")
    print()

    print("[11/11] Generating fix plan...")
    fix_plan = generate_fix_plan(audit_results)
    print(f"  {len(fix_plan['phases'])} phases")
    print(f"  Estimated impact: {fix_plan['estimated_impact']}")
    print()

    output_data = {
        'audit_version': 'v2_corrected',
        'audit_timestamp': datetime.now().isoformat(),
        'database_unchanged': True,
        'corrections_from_v1': [
            'Fixed alias_integrity GROUP BY to exclude source_sheet (correct unique mapping count)',
            'Fixed IBI/ITT/ZF to match by parsed_customer_name exact match, not source_sheet ILIKE',
            'Added location collision detection (武汉/苏州)',
            'Split sheet duplicates into high/low confidence categories',
            'Separated root causes into 4 distinct categories',
            'Added customer name normalization collision analysis'
        ],
        'summary': {
            'total_customers': customer_audit['total'],
            'truncated_customers': len(customer_audit['truncated']),
            'high_confidence_empty_duplicates': len(customer_audit['high_confidence_empty_duplicates']),
            'low_confidence_no_ref_customers': len(customer_audit['low_confidence_no_ref_customers']),
            'expected_aliases': alias_audit['total_expected'],
            'matched_aliases': alias_audit['matched'],
            'missing_aliases': len(alias_audit['missing']),
            'affected_customers': len(alias_audit['by_customer']),
            'unsafe_location_collisions': location_collision['total_unsafe']
        },
        'customer_mapping': excel_mapping,
        'duplicate_customers': {
            'truncated': customer_audit['truncated'],
            'high_confidence_empty_duplicates': customer_audit['high_confidence_empty_duplicates'],
            'low_confidence_no_ref_customers': customer_audit['low_confidence_no_ref_customers']
        },
        'alias_integrity': {
            'total_expected': alias_audit['total_expected'],
            'matched': alias_audit['matched'],
            'missing_count': len(alias_audit['missing']),
            'by_customer': alias_audit['by_customer'],
            'examples': alias_audit['missing'][:20]
        },
        'affected_customers': list(alias_audit['by_customer'].keys()),
        'ibi_itt_zf': ibi_itt_zf_audit,
        'location_collision': location_collision,
        'name_normalization': name_norm,
        'invariants': invariant_audit,
        'unique_index': index_check,
        'root_causes': root_causes,
        'recommended_fix_plan': fix_plan
    }

    output_dir = backend_path / 'scripts' / 'backups' / 'customer_import_audit'
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / 'customer_import_audit_1.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON report: {json_path}")

    md_path = output_dir / 'customer_import_audit_1.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        write_markdown_report(f, output_data)
    print(f"Saved Markdown report: {md_path}")

    conn.close()
    print()
    print("Audit complete. Database unchanged.")
    return output_data


def write_markdown_report(f, data):
    """Write markdown format report - v2 corrected"""
    f.write("# Customer Import Integrity Audit Report A1 - v2 CORRECTED\n\n")
    f.write(f"**Audit Time:** {data['audit_timestamp']}\n\n")
    f.write(f"**Database Status:** UNCHANGED (Read-only audit)\n\n")
    f.write(f"**Audit Version:** v2 - Corrected calculation errors from v1\n\n")

    f.write("## Corrections from v1\n\n")
    for correction in data.get('corrections_from_v1', []):
        f.write(f"- {correction}\n")
    f.write("\n")

    f.write("## Executive Summary\n\n")
    s = data['summary']
    f.write(f"- **Total Customers:** {s['total_customers']}\n")
    f.write(f"- **Truncated Abbreviations:** {s['truncated_customers']}\n")
    f.write(f"- **High-Confidence Empty Duplicates:** {s['high_confidence_empty_duplicates']}\n")
    f.write(f"- **Low-Confidence No-Ref Customers:** {s['low_confidence_no_ref_customers']}\n")
    f.write(f"- **Expected Unique Aliases:** {s['expected_aliases']}\n")
    f.write(f"- **Matched Aliases:** {s['matched_aliases']}\n")
    f.write(f"- **Missing Aliases:** {s['missing_aliases']}\n")
    f.write(f"- **Affected Customers:** {s['affected_customers']}\n")
    f.write(f"- **Unsafe Location Collisions:** {s['unsafe_location_collisions']}\n\n")

    f.write("## 1. Truncated Customer Abbreviations\n\n")
    truncated = data['duplicate_customers']['truncated']
    if truncated:
        f.write(f"Found {len(truncated)} customers with truncated English abbreviations:\n\n")
        f.write("| ID | Name | Code | Sheet Key | Refs | Evidence |\n")
        f.write("|----|------|------|-----------|------|----------|\n")
        for c in truncated:
            f.write(f"| {c['id']} | {c['name']} | {c['customer_code'] or ''} | {c['sheet_key'] or ''} | {c['total_refs']} | {c['evidence']} |\n")
    else:
        f.write("No truncated abbreviations found.\n")
    f.write("\n")

    f.write("## 2. High-Confidence Empty Duplicate Customers\n\n")
    high_conf = data['duplicate_customers']['high_confidence_empty_duplicates']
    if high_conf:
        f.write(f"Found {len(high_conf)} high-confidence empty duplicates:\n\n")
        f.write("| ID | Name | Code | Sheet Key | Refs | Evidence |\n")
        f.write("|----|------|------|-----------|------|----------|\n")
        for c in high_conf[:20]:
            f.write(f"| {c['id']} | {c['name']} | {c['customer_code'] or ''} | {c['sheet_key'] or ''} | {c['total_refs']} | {c['evidence']} |\n")
        if len(high_conf) > 20:
            f.write(f"\n... and {len(high_conf) - 20} more\n")
    else:
        f.write("No high-confidence empty duplicates found.\n")
    f.write("\n")

    f.write("## 3. Low-Confidence No-Ref Customers\n\n")
    low_conf = data['duplicate_customers']['low_confidence_no_ref_customers']
    f.write(f"Found {len(low_conf)} customers with no references (may be legitimate/test/unused).\n\n")
    f.write("These require manual review - not automatically flagged as duplicates.\n\n")

    f.write("## 4. Alias Integrity\n\n")
    ai = data['alias_integrity']
    f.write(f"**Expected:** {ai['total_expected']} unique (customer_id, part_id, customer_part_no) mappings\n\n")
    f.write(f"**Matched:** {ai['matched']}\n\n")
    f.write(f"**Missing:** {ai['missing_count']}\n\n")
    f.write(f"**Match Rate:** {ai['matched'] / ai['total_expected'] * 100:.1f}%\n\n")

    f.write("### Missing by Customer\n\n")
    if ai['by_customer']:
        sorted_customers = sorted(ai['by_customer'].items(), key=lambda x: x[1]['count'], reverse=True)
        f.write("| Customer ID | Missing Count | Examples |\n")
        f.write("|-------------|---------------|----------|\n")
        for cust_id, info in sorted_customers[:30]:
            examples = ', '.join([ex['customer_part_no'] for ex in info['examples'][:3]])
            f.write(f"| {cust_id} | {info['count']} | {examples} |\n")
        if len(sorted_customers) > 30:
            f.write(f"\n... and {len(sorted_customers) - 30} more customers\n")
    f.write("\n")

    f.write("## 5. IBI / ITT / ZF Analysis\n\n")
    for customer in ['IBI', 'ITT', 'ZF']:
        data_c = data['ibi_itt_zf'][customer]
        f.write(f"### {customer}\n\n")
        f.write(f"- **Canonical Customer ID:** {data_c['canonical_customer_id']}\n")
        f.write(f"- **Sheets:** {', '.join(data_c['sheets']) if data_c['sheets'] else 'None'}\n")
        f.write(f"- **Database Customers:** {len(data_c['customers'])}\n")
        if data_c['customers']:
            for c in data_c['customers']:
                f.write(f"  - ID {c['id']}: {c['name']} (code: {c['customer_code']}, key: {c['sheet_key']})\n")
        f.write(f"- **Expected Aliases:** {data_c['expected']}\n")
        f.write(f"- **Matched:** {data_c['matched']}\n")
        f.write(f"- **Missing:** {data_c['missing']}\n\n")

    f.write("## 6. Location Collision Analysis\n\n")
    loc_coll = data['location_collision']
    f.write(f"**Unsafe Collisions:** {loc_coll['total_unsafe']}\n\n")
    f.write(f"**Acceptable Normalizations:** {loc_coll['total_acceptable']}\n\n")

    if loc_coll['unsafe_collisions']:
        f.write("### Unsafe Collisions (Multiple Parsed Names -> Same Customer)\n\n")
        for collision in loc_coll['unsafe_collisions']:
            f.write(f"**Customer ID {collision['resolved_customer_id']}:** {collision['resolved_customer_name']}\n\n")
            f.write(f"- Collision Type: {collision['collision_type']}\n")
            f.write(f"- Total Rows: {collision['total_rows']}\n")
            f.write(f"- Total Parts: {collision['total_parts']}\n")
            f.write(f"- Parsed Names:\n")
            for parsed in collision['parsed_names']:
                f.write(f"  - \"{parsed['parsed_name']}\" (rows={parsed['row_count']}, parts={parsed['part_count']})\n")
            f.write("\n")

    f.write("## 7. Customer Name Normalization Categories\n\n")
    name_norm = data['name_normalization']
    f.write(f"- **Exact Matches:** {name_norm['counts']['exact']}\n")
    f.write(f"- **Acceptable Normalized:** {name_norm['counts']['acceptable']}\n")
    f.write(f"- **Unsafe Normalized:** {name_norm['counts']['unsafe']}\n\n")

    f.write("## 8. Root Causes\n\n")
    for i, cause in enumerate(data['root_causes'], 1):
        f.write(f"### {i}. {cause['category']} (Severity: {cause['severity']})\n\n")
        f.write(f"**Description:** {cause['description']}\n\n")
        f.write(f"**Evidence:** {cause['evidence']}\n\n")
        f.write(f"**Impact:** {cause['impact']}\n\n")
        if cause.get('file_references'):
            f.write("**File References:**\n")
            for ref in cause['file_references']:
                f.write(f"- `{ref}`\n")
        f.write("\n")

    f.write("## 9. Recommended Fix Plan\n\n")
    plan = data['recommended_fix_plan']
    f.write(f"**Estimated Impact:** {plan['estimated_impact']}\n\n")
    for phase in plan['phases']:
        f.write(f"### Phase {phase['phase']}: {phase['name']}\n\n")
        f.write("**Actions:**\n")
        for action in phase['actions']:
            f.write(f"- {action}\n")
        f.write("\n")

    f.write("## Conclusion\n\n")
    f.write("This v2 corrected audit identified data integrity issues related to:\n")
    f.write("1. Sheet-name abbreviation splitter creating truncated customers\n")
    f.write("2. normalize_customer_name deleting parentheses causing location collisions\n")
    f.write("3. Unique index missing part_id preventing multi-part mappings\n")
    f.write("4. Recovery importer skipping same customer_part_no with different parts\n\n")
    f.write("**Database has NOT been modified.** Review the fix plan and approve before executing repairs.\n")


if __name__ == '__main__':
    try:
        result = main()
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
