# 🧪 手动测试脚本

本目录包含手动测试和调试脚本。

---

## JavaScript 测试脚本

### 报价管理测试
- **test-quote-creation.js** - 报价单创建测试
- **test-quote-dict.js** - 报价字典测试
- **test-quote-dict-manual.js** - 报价字典手动测试

### 前端界面测试
- **test-frontend.js** - 前端功能测试
- **test-browser-full.js** - 浏览器完整测试
- **test-cascader.js** - 级联选择器测试
- **test-tree-endpoint.js** - 树形端点测试

### 数据结构测试
- **test-three-level-structure.js** - 三级结构测试
- **test-all-changes.js** - 所有变更测试
- **test-final-changes.js** - 最终变更测试

### API 调试
- **test-api-fields.js** - API 字段测试
- **test-debug-422.js** - 422 错误调试

## Python 测试脚本

- **read_prices.py** - 读取价格数据
- **read_prices2.py** - 读取价格数据 v2

---

## 使用方法

```bash
# JavaScript 测试（需要 Node.js）
node tests/manual/test-quote-creation.js

# Python 测试
cd tests/manual
python read_prices.py
```

---

**注意**: 这些是手动测试脚本，不是自动化测试。自动化测试请参考 `backend/tests/` 和 `frontend/tests/`。
