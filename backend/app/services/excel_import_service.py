"""Excel import service with validation rules."""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import re
import hashlib


class ExcelValidationService:
    """Validation rules for Excel import rows."""

    # Header patterns that indicate non-data rows
    HEADER_PATTERNS = [
        r'^序号$',
        r'^NO\.?$',
        r'^客户名称',
        r'^原图产品编号',
        r'^本厂产品',
        r'^材质',
        r'^模具类型',
        r'^返回目录',
        r'^合计',
        r'^总计',
        r'^小计',
    ]

    # Material specification patterns (not real materials)
    SPEC_PATTERNS = [
        r'^T[\d.]+',
        r'^W[\d.]+',
        r'^P[\d.]+',
        r'^\d+[\*×]\d+',  # Width*Thickness format
    ]

    # Valid material patterns
    VALID_MATERIAL_PATTERNS = [
        r'SPCC',
        r'SECC',
        r'SGCC',
        r'SUS\d{3}',
        r'AL\d{4}',
        r'铜',
        r'铝',
        r'不锈钢',
    ]

    def is_header_row(self, row_data: Dict) -> bool:
        """Check if row is a header/title row."""
        # Check first few columns for header patterns
        for key, value in list(row_data.items())[:5]:
            if value and isinstance(value, str):
                for pattern in self.HEADER_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
        return False

    def is_empty_data_row(self, row_data: Dict) -> bool:
        """Check if row has no meaningful data."""
        customer_part_no = row_data.get('原图产品编号', '').strip()
        internal_name = row_data.get('本厂产品名称', '').strip()
        tooling_number = row_data.get('本厂产品编号', '').strip()

        # Row must have at least customer part number or (internal name + tooling number)
        if not customer_part_no and not (internal_name and tooling_number):
            return True

        return False

    def validate_material(self, material: str) -> Tuple[bool, Optional[str]]:
        """Validate that material is not a specification string.

        Returns:
            (is_valid, error_message)
        """
        if not material:
            return True, None

        material = material.strip()

        # Check if it's a spec pattern (invalid)
        for pattern in self.SPEC_PATTERNS:
            if re.search(pattern, material, re.IGNORECASE):
                return False, f"材质字段包含规格数据而非材料名称: {material}"

        # Check if it matches valid material patterns
        for pattern in self.VALID_MATERIAL_PATTERNS:
            if re.search(pattern, material, re.IGNORECASE):
                return True, None

        # If not empty and not matching any pattern, warn but allow
        return True, None

    def validate_mold_type(self, mold_type: str, process_step_count: Optional[int]) -> Tuple[bool, Optional[str]]:
        """Validate mold type and process step count consistency.

        Returns:
            (is_valid, error_message)
        """
        if not mold_type:
            return True, None

        mold_type = mold_type.strip().lower()
        is_continuous = '连续' in mold_type or 'continuous' in mold_type

        # For continuous molds, process_step_count should not be set
        if is_continuous and process_step_count and process_step_count > 1:
            return False, f"连续模不应有工序步数(模数): {process_step_count}"

        # For non-continuous molds (简易模/工程模), process_step_count is expected
        if not is_continuous and mold_type in ['简易模', '工程模']:
            # This is valid, process_step_count will be parsed from "模数" column
            pass

        return True, None

    def parse_cavity_count(self, cavity_str: str) -> Optional[int]:
        """Parse cavity count from explicit strings like '1出2' or '一出二'.

        Left/right wording alone is not cavity evidence: "左右各一套" can
        describe two separate dies or material strips rather than two cavities.

        Args:
            cavity_str: String containing cavity information

        Returns:
            Cavity count or None if not found
        """
        if not cavity_str:
            return None

        text = str(cavity_str)
        patterns = [
            r'1\s*出\s*(\d+|[一二三四五六七八九十两]+)',
            r'一\s*出\s*(\d+|[一二三四五六七八九十两]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            raw_count = match.group(1)
            if raw_count.isdigit():
                return int(raw_count)
            chinese_digits = {
                '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
                '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            }
            if raw_count == '十':
                return 10
            if len(raw_count) == 1:
                return chinese_digits.get(raw_count)

        return None

    def validate_customer_code_conflict(
        self,
        customer_name: str,
        customer_code: str,
        customer_code_mapping: Dict[str, str]
    ) -> Tuple[bool, Optional[str]]:
        """Validate that customer code does not conflict with existing mappings.

        Args:
            customer_name: Customer name from sheet
            customer_code: Customer code to validate
            customer_code_mapping: Dict of {customer_name: customer_code}

        Returns:
            (is_valid, error_message)
        """
        if not customer_code:
            return True, None

        # Check if this name already has a different code
        existing_code = customer_code_mapping.get(customer_name)
        if existing_code and existing_code != customer_code:
            return False, f"客户代号冲突: {customer_name} 已有代号 {existing_code}，新代号 {customer_code}"

        # Check if this code is used by a different customer
        for name, code in customer_code_mapping.items():
            if code == customer_code and name != customer_name:
                return False, f"客户代号冲突: 代号 {customer_code} 已被 {name} 使用"

        return True, None

    def generate_part_fingerprint(
        self,
        tooling_number: str,
        internal_name: str,
        material: Optional[str],
        thickness: Optional[Decimal],
        width: Optional[Decimal],
        pitch: Optional[Decimal],
        position: Optional[str]
    ) -> str:
        """Generate matching fingerprint for part deduplication.

        Fingerprint = hash(tooling_number + normalized_name + material + T/W/P + position)
        """
        # Normalize internal name (remove spaces, convert to lowercase)
        normalized_name = re.sub(r'\s+', '', internal_name.lower()) if internal_name else ''

        # Build fingerprint components
        components = [
            tooling_number or '',
            normalized_name,
            material or '',
            str(thickness) if thickness else '',
            str(width) if width else '',
            str(pitch) if pitch else '',
            position or '',
        ]

        # Create hash
        fingerprint_str = '|'.join(components)
        return hashlib.sha256(fingerprint_str.encode('utf-8')).hexdigest()[:16]

    def validate_row(
        self,
        row_data: Dict,
        customer_code_mapping: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """Validate a single Excel row.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check if header row
        if self.is_header_row(row_data):
            errors.append("表头行，跳过")
            return False, errors

        # Check if empty data row
        if self.is_empty_data_row(row_data):
            errors.append("空数据行（缺少客户件号和模具号）")
            return False, errors

        # Validate material
        material = row_data.get('材质', '')
        is_valid_material, material_error = self.validate_material(material)
        if not is_valid_material:
            errors.append(material_error)

        # Validate mold type
        mold_type = row_data.get('模具类型', '')
        process_step_count_str = row_data.get('模数', '')
        process_step_count = None
        if process_step_count_str and str(process_step_count_str).strip().isdigit():
            process_step_count = int(str(process_step_count_str).strip())

        is_valid_mold, mold_error = self.validate_mold_type(mold_type, process_step_count)
        if not is_valid_mold:
            errors.append(mold_error)

        # Validate customer code
        customer_name = row_data.get('客户名称', '').strip()
        customer_code = row_data.get('客户代号', '').strip()
        if customer_name and customer_code:
            is_valid_code, code_error = self.validate_customer_code_conflict(
                customer_name, customer_code, customer_code_mapping
            )
            if not is_valid_code:
                errors.append(code_error)

        # Return validation result
        is_valid = len(errors) == 0
        return is_valid, errors


class ExcelHeaderMapper:
    """Dynamic header mapping service for Excel import."""

    # Header mapping: standardized_name -> possible_excel_headers
    HEADER_MAPPINGS = {
        '客户名称': ['客户名称', 'Customer Name', '客户'],
        '客户代号': ['客户名称代号', '客户代号', 'Customer Code', '代号'],
        '原图产品编号': ['原图产品编号', '客户产品编号', 'Customer Part No', '客户件号'],
        '原图产品名称1': ['原图产品名称1', '原图产品名称', 'Customer Part Name', '客户件名'],
        '原图产品名称2': ['原图产品名称2'],
        '本厂产品名称': ['本厂产品名称', 'Internal Name', '内部名称', '产品名称'],
        '本厂产品编号': ['本厂产品编号', 'Tooling Number', '模具号', '模具编号'],
        '模具类型': ['模具类型', 'Mold Type', '类型'],
        '模数': ['模数', 'Process Steps', '工序数'],
        '材质': ['材质', 'Material', '材料'],
        'T': ['T', 'Thickness', '厚度'],
        'W': ['W', 'Width', '宽度'],
        'P': ['P', 'Pitch', '步距'],
        '毛重': ['毛重', 'Gross Weight'],
        '净重': ['净重', 'Net Weight'],
        '位置': ['位置', 'Position', 'L/R'],
        'PPAP': ['PPAP', 'PPAP状态'],
        '车型': ['车型', 'Vehicle Model'],
        '吨位': ['吨位', 'Tonnage'],
        '备注': ['备注', 'Remark', 'Note'],
    }

    def find_header_row(self, sheet_data: List[List]) -> Optional[int]:
        """Find the row index containing headers.

        Args:
            sheet_data: List of rows, each row is a list of cell values

        Returns:
            Row index (0-based) or None if not found
        """
        for idx, row in enumerate(sheet_data[:10]):  # Check first 10 rows
            # Convert row to strings
            row_strs = [str(cell).strip() if cell else '' for cell in row]

            # Check if row contains key headers
            key_headers = ['原图产品编号', '本厂产品名称', '本厂产品编号']
            matches = sum(1 for header in key_headers if any(header in cell for cell in row_strs))

            if matches >= 2:  # At least 2 key headers found
                return idx

        return None

    def map_headers(self, header_row: List) -> Dict[int, str]:
        """Map Excel column indices to standardized field names.

        Args:
            header_row: List of header cell values

        Returns:
            Dict mapping {column_index: standardized_field_name}
        """
        column_mapping = {}

        for col_idx, cell_value in enumerate(header_row):
            if not cell_value:
                continue

            cell_str = str(cell_value).strip()

            # Try to match against all known headers
            # Use exact match first, then contains match
            matched = False
            for standard_name, possible_headers in self.HEADER_MAPPINGS.items():
                if matched:
                    break
                for possible_header in possible_headers:
                    # Exact match (case-insensitive)
                    if cell_str == possible_header:
                        column_mapping[col_idx] = standard_name
                        matched = True
                        break
                    # Contains match (for longer headers)
                    if len(possible_header) > 2 and (possible_header in cell_str or cell_str in possible_header):
                        column_mapping[col_idx] = standard_name
                        matched = True
                        break

        return column_mapping

    def extract_row_data(
        self,
        row: List,
        column_mapping: Dict[int, str]
    ) -> Dict[str, any]:
        """Extract data from a row using column mapping.

        Args:
            row: List of cell values
            column_mapping: Dict mapping {column_index: field_name}

        Returns:
            Dict of {field_name: value}
        """
        row_data = {}

        for col_idx, field_name in column_mapping.items():
            if col_idx < len(row):
                value = row[col_idx]
                # Convert to appropriate type
                if value is not None:
                    row_data[field_name] = value

        # Merge 原图产品名称1 and 原图产品名称2 if both exist
        if '原图产品名称1' in row_data or '原图产品名称2' in row_data:
            name1 = str(row_data.get('原图产品名称1', '')).strip()
            name2 = str(row_data.get('原图产品名称2', '')).strip()
            row_data['原图产品名称'] = (name1 + ' ' + name2).strip()

        return row_data
