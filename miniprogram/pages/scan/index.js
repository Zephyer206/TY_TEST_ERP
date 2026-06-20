/**
 * WeChat Mini Program - Scan Page
 *
 * Handles QR code scanning and displays entity information.
 */

const app = getApp<IAppOption>()
const api = require('../services/api.js')

interface ScanResult {
  qr_code: string
  qr_type: string
  entity_id: string
  entity_name?: string
  entity_type?: string
  details?: Record<string, any>
  timestamp: string
}

interface QRLookupResult {
  qr_code: string
  content: string
  image_base64: string
}

Page({
  data: {
    // Scan state
    scanning: false,
    lastScanTime: 0,

    // Result state
    hasResult: false,
    scanResult: null as ScanResult | null,

    // Error state
    hasError: false,
    errorMessage: '',

    // Entity type labels
    typeLabels: {
      material_batch: '原料批次',
      machine: '机台设备',
      process_flow: '工艺流转',
      part: '零件信息',
      packaging_record: '包装记录',
      coating_record: '喷涂记录',
    } as Record<string, string>,

    // Action buttons based on entity type
    actions: [] as Array<{ label: string; action: string }>,
  },

  onLoad() {
    console.log('Scan page loaded')
  },

  onShow() {
    // Resume scanning when page shows
  },

  /**
   * Start QR code scanning
   */
  startScan() {
    // Prevent rapid scanning
    const now = Date.now()
    if (now - this.data.lastScanTime < 2000) {
      wx.showToast({
        title: '请稍后再试',
        icon: 'none',
      })
      return
    }

    this.setData({ scanning: true, lastScanTime: now })

    // Use WeChat scan API
    wx.scanCode({
      onlyFromCamera: true,
      success: (res) => {
        console.log('Scanned:', res)
        this.handleScanResult(res.result || res.code)
      },
      fail: (err) => {
        console.error('Scan failed:', err)
        this.setData({
          scanning: false,
          hasError: true,
          errorMessage: '扫码失败，请重试',
        })
      },
    })
  },

  /**
   * Handle scan result
   */
  async handleScanResult(code: string) {
    if (!code) {
      this.setData({
        scanning: false,
        hasError: true,
        errorMessage: '未识别到二维码',
      })
      return
    }

    try {
      wx.showLoading({ title: '查询中...' })

      const result = await api.qr.lookup(code) as ScanResult

      // Determine actions based on entity type
      const actions = this.getActionsForType(result.entity_type)

      this.setData({
        scanning: false,
        hasResult: true,
        hasError: false,
        scanResult: result,
        actions,
      })

      wx.hideLoading()
      wx.vibrateShort({ type: 'success' })
    } catch (err: any) {
      console.error('Lookup failed:', err)
      wx.hideLoading()

      this.setData({
        scanning: false,
        hasResult: false,
        hasError: true,
        errorMessage: err.message || '查询失败',
      })

      wx.vibrateShort({ type: 'error' })
    }
  },

  /**
   * Get action buttons for entity type
   */
  getActionsForType(entityType: string | undefined): Array<{ label: string; action: string }> {
    const actions: Record<string, Array<{ label: string; action: string }>> = {
      material_batch: [
        { label: '领料', action: 'pickMaterial' },
        { label: '查看详情', action: 'viewMaterialDetail' },
      ],
      machine: [
        { label: '开始报工', action: 'startReport' },
        { label: '查看状态', action: 'viewMachineDetail' },
      ],
      process_flow: [
        { label: '确认工序', action: 'confirmProcess' },
        { label: '查看工艺', action: 'viewProcessDetail' },
      ],
      packaging_record: [
        { label: '全检入库', action: 'inspectPackaging' },
        { label: '查看记录', action: 'viewPackagingDetail' },
      ],
      coating_record: [
        { label: '开始喷涂', action: 'startCoating' },
        { label: '查看记录', action: 'viewCoatingDetail' },
      ],
      part: [
        { label: '查看零件', action: 'viewPartDetail' },
      ],
    }

    return entityType ? (actions[entityType] || []) : []
  },

  /**
   * Execute action
   */
  async executeAction(e: WechatMiniprogram.TouchEvent) {
    const action = e.currentTarget.dataset.action
    const result = this.data.scanResult

    if (!result) return

    switch (action) {
      case 'pickMaterial':
        this.navigateToPickMaterial(result.entity_id)
        break
      case 'startReport':
        this.navigateToReport(result.entity_id)
        break
      case 'confirmProcess':
        this.navigateToConfirmProcess(result.entity_id)
        break
      case 'inspectPackaging':
        this.navigateToInspectPackaging(result.entity_id)
        break
      case 'startCoating':
        this.navigateToStartCoating(result.entity_id)
        break
      case 'viewMaterialDetail':
      case 'viewMachineDetail':
      case 'viewProcessDetail':
      case 'viewPackagingDetail':
      case 'viewCoatingDetail':
      case 'viewPartDetail':
        this.navigateToDetail(result.entity_type, result.entity_id)
        break
      default:
        wx.showToast({ title: '功能开发中', icon: 'none' })
    }
  },

  /**
   * Navigate to material picking
   */
  navigateToPickMaterial(batchId: string) {
    wx.navigateTo({
      url: `/pages/material/pick/index?batchId=${encodeURIComponent(batchId)}`,
    })
  },

  /**
   * Navigate to production report
   */
  navigateToReport(machineId: string) {
    wx.navigateTo({
      url: `/pages/production/report/index?machineId=${machineId}`,
    })
  },

  /**
   * Navigate to process confirmation
   */
  navigateToConfirmProcess(cardId: string) {
    wx.navigateTo({
      url: `/pages/process/confirm/index?cardId=${cardId}`,
    })
  },

  /**
   * Navigate to packaging inspection
   */
  navigateToInspectPackaging(recordId: string) {
    wx.navigateTo({
      url: `/pages/packaging/inspect/index?recordId=${recordId}`,
    })
  },

  /**
   * Navigate to coating start
   */
  navigateToStartCoating(recordId: string) {
    wx.navigateTo({
      url: `/pages/coating/start/index?recordId=${recordId}`,
    })
  },

  /**
   * Navigate to entity detail page
   */
  navigateToDetail(entityType: string | undefined, entityId: string) {
    const pageMap: Record<string, string> = {
      material_batch: '/pages/material/detail/index',
      machine: '/pages/machine/detail/index',
      process_flow: '/pages/process/detail/index',
      part: '/pages/part/detail/index',
      packaging_record: '/pages/packaging/detail/index',
      coating_record: '/pages/coating/detail/index',
    }

    const page = entityType ? pageMap[entityType] : '/pages/home/index'
    wx.navigateTo({
      url: `${page}?id=${encodeURIComponent(entityId)}`,
    })
  },

  /**
   * Clear result and scan again
   */
  scanAgain() {
    this.setData({
      hasResult: false,
      hasError: false,
      scanResult: null,
    })
    this.startScan()
  },

  /**
   * Copy code to clipboard
   */
  copyCode() {
    if (!this.data.scanResult) return

    wx.setClipboardData({
      data: this.data.scanResult.qr_code,
      success: () => {
        wx.showToast({ title: '已复制', icon: 'success' })
      },
    })
  },

  /**
   * Manual input code
   */
  manualInput() {
    wx.showModal({
      title: '输入条码',
      editable: true,
      placeholderText: '请输入条码编号',
      success: (res) => {
        if (res.confirm && res.content) {
          this.handleScanResult(res.content.trim())
        }
      },
    })
  },
})
