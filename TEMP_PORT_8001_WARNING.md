# ⚠️ 临时端口警告 - TEMPORARY PORT WARNING

## 当前状态
**后端正在使用临时端口 8001**

## 原因
- 标准端口 8000 被顽固进程占用（PID 4940, 26504, 6724）
- 所有清理手段均失败（taskkill / PowerShell / VBS 自提权）
- 用户于 2026-06-21 17:55 授权临时使用 8001 端口

## 当前配置
- **后端地址**: `http://localhost:8001`
- **健康检查**: `http://localhost:8001/health` ✅ 正常
- **API 文档**: `http://localhost:8001/docs`

## ⚠️ 重要提醒

### 前端需要修改
前端 API baseURL 必须临时改为 `http://localhost:8001`：

**文件**: `frontend/src/api/request.ts` 或类似的配置文件

```typescript
// 临时修改
const baseURL = 'http://localhost:8001'  // 原来是 8000
```

### 恢复到 8000 端口的步骤

**一旦 8000 端口可用，必须立即切回：**

1. **停止当前后端**：
   ```bash
   # 找到 PID 22496
   taskkill //PID 22496 //F
   ```

2. **清理 8000 端口**（重启计算机最有效）

3. **在 8000 端口重启**：
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **恢复前端配置**：
   ```typescript
   const baseURL = 'http://localhost:8000'  // 恢复标准端口
   ```

## 授权记录

- **授权版本**: Constitution v1.3.0
- **授权时间**: 2026-06-21 17:55
- **授权期限**: ≤ 24 小时（超时需重新授权）
- **解除条件**: 8000 端口释放后立即切回
- **宪法文件**: `.specify/memory/constitution.md` (VIII-C 条款)

## 检查 8000 端口是否可用

```bash
netstat -ano | grep ":8000" | grep LISTENING
# 如果没有输出，说明 8000 端口已释放，可以切回
```

---

**此文件在切回 8000 端口后应立即删除**
