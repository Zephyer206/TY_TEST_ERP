import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import import_shanghai_wanxiang_prices as imp

def test_preview_includes_customer_part_name_and_material():
    test_xlsx = Path(__file__).parent.parent / 'data' / 'source' / 'wanxiang_shanghai_prices.xlsx'
    if not test_xlsx.exists():
        return
    result = imp.preview(str(test_xlsx))
    assert 'rows' in result
    assert len(result['rows']) > 0
    for row in result['rows']:
        assert 'customer_part_name' in row
        assert 'material_name' in row

def test_bootstrap_rejection_without_flag():
    try:
        imp.apply_import('/nonexistent.xlsx', None, bootstrap_from_excel=False)
        assert False, "should have raised"
    except:
        pass

def test_norm_customer():
    assert imp.norm_customer('万向钱潮（上海）') == '万向钱潮(上海)'
    assert imp.norm_customer('test）name（') == 'test)name('
