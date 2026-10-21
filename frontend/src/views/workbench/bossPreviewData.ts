// Layout-only sample records. Do not treat these values as live ERP metrics.
export type StageKey = 'stamp' | 'paint' | 'pack' | 'ship'
export type Tone = 'green' | 'amber' | 'red' | 'blue'
export interface StageDefinition { key: StageKey; name: string; icon: string; base: number; bad?: number; rework?: number; factor: number; products: string[] }
export interface DevelopmentProduct { id: string; name: string; type: string; stage: string; owner: string; due?: string; tone: Tone; lastAction?: string; observe?: boolean }
export interface CompletedProduct { name: string; type: string; date: string; basis: string; owner: string }
export interface BacklogItem { key: StageKey; name: string; quantity: number; icon: string; count: number; oldest: number; owner: string; items: string[] }
export interface OrderItem { id: string; client: string; product: string; due: string; quantity: number; shipped?: number; owner: string; state: string; tone: Tone }
export interface Issue { title: string; tag: string; description: string; icon: string; owner: string; expected: string; impact: string; reason: string; next: string }
export const TODAY = '2026-10-17'
export const DEMO_MIN = '2026-09-01'
const DAY_MS = 86400000
export const dateOf = (s: string) => new Date(`${s}T00:00:00Z`)
const dateString = (date: Date) => date.toISOString().slice(0, 10)
export const addDays = (s: string, n: number) => dateString(new Date(dateOf(s).getTime() + n * DAY_MS))
export const dateLabel = (s: string) => `${Number(s.slice(5, 7))}月${Number(s.slice(8, 10))}日`
export const fmt = (n: number) => new Intl.NumberFormat('zh-CN').format(n)
export const sum = (values: number[]) => values.reduce((a, b) => a + b, 0)
export function splitTotal(total: number) { const first = [.29, .23, .20, .16].map(r => Math.floor(total * r)); return [...first, total - sum(first)] }
export const stageDefinitions: StageDefinition[] = [
  {key:'stamp', name:'冲压完成量', icon:'factory', base:2480, bad:18, rework:8, factor:.78, products:['电控箱安装板','车身固定支架','连接器屏蔽罩','电机固定座','传感器支撑片']},
  {key:'paint', name:'喷涂完成量', icon:'paint', base:1860, bad:24, rework:120, factor:.70, products:['电控箱安装板','电机固定座','车身固定支架','设备外罩','传感器支撑片']},
  {key:'pack', name:'包装完成量', icon:'box', base:1400, bad:4, rework:6, factor:.74, products:['车身固定支架','电控箱安装板','电机固定座','连接器屏蔽罩','传感器支撑片']},
  {key:'ship', name:'实际发货量', icon:'truck', base:3200, factor:.62, products:['电控箱安装板','车身固定支架','连接器屏蔽罩','电机固定座','设备外罩']}
];

export const development: DevelopmentProduct[] = [
  {id:'DEV-26018',name:'车身固定支架',type:'连续模',stage:'待PPAP批准',owner:'张工',due:'2026-10-20',tone:'blue'},
  {id:'DEV-26012',name:'电控箱安装板',type:'工程模',stage:'试模调整',owner:'王工',due:'2026-10-16',tone:'amber'},
  {id:'DEV-26009',name:'连接器屏蔽罩',type:'软模',stage:'交付观察中',owner:'李工',lastAction:'2026-09-29',observe:true,tone:'green'},
  {id:'DEV-26020',name:'电机固定座',type:'连续模',stage:'模具加工',owner:'张工',due:'2026-10-26',tone:'blue'},
  {id:'DEV-26021',name:'传感器支撑片',type:'连续模',stage:'试模验证',owner:'赵工',due:'2026-10-25',tone:'blue'},
  {id:'DEV-26022',name:'座椅调节连接板',type:'连续模',stage:'结构设计',owner:'陈工',due:'2026-11-02',tone:'blue'},
  {id:'DEV-26023',name:'电池固定压板',type:'连续模',stage:'待PPAP批准',owner:'赵工',due:'2026-10-22',tone:'blue'},
  {id:'DEV-26024',name:'底盘连接片',type:'连续模',stage:'试模验证',owner:'张工',due:'2026-10-28',tone:'blue'},
  {id:'DEV-26025',name:'线束固定卡座',type:'工程模',stage:'模具加工',owner:'王工',due:'2026-10-27',tone:'blue'},
  {id:'DEV-26026',name:'设备安装底板',type:'工程模',stage:'待PPAP批准',owner:'陈工',due:'2026-10-24',tone:'blue'},
  {id:'DEV-26027',name:'端子连接支架',type:'工程模',stage:'结构设计',owner:'王工',due:'2026-10-30',tone:'blue'},
  {id:'DEV-26028',name:'控制器散热片',type:'软模',stage:'交付观察中',owner:'李工',lastAction:'2026-10-03',observe:true,tone:'green'},
  {id:'DEV-26029',name:'仪表安装支架',type:'软模',stage:'交付观察中',owner:'赵工',lastAction:'2026-10-08',observe:true,tone:'green'},
  {id:'DEV-26030',name:'风道固定片',type:'软模',stage:'样品制作',owner:'李工',due:'2026-10-23',tone:'amber'},
  {id:'DEV-26031',name:'电机端盖垫片',type:'软模',stage:'客户验证',owner:'赵工',due:'2026-10-26',tone:'amber'},
  {id:'DEV-26032',name:'侧板加强筋',type:'软模',stage:'软模制作',owner:'陈工',due:'2026-10-28',tone:'amber'},
  {id:'DEV-26033',name:'锁扣安装片',type:'软模',stage:'改样处理中',owner:'李工',due:'2026-10-24',tone:'amber'},
  {id:'DEV-26034',name:'铰链定位片',type:'软模',stage:'样品验证',owner:'陈工',due:'2026-10-29',tone:'amber'}
];
export const completedDevelopment: CompletedProduct[] = [
  {name:'支撑连接角码',type:'软模',date:'2026-10-03',basis:'连续30天无后续操作',owner:'李工'},
  {name:'前梁加强片',type:'连续模',date:'2026-10-07',basis:'客户已批准PPAP',owner:'张工'},
  {name:'箱体限位支架',type:'工程模',date:'2026-10-09',basis:'客户已批准PPAP',owner:'王工'},
  {name:'面板安装弹片',type:'软模',date:'2026-10-13',basis:'连续30天无后续操作',owner:'赵工'},
  {name:'电池侧板压片',type:'连续模',date:'2026-10-16',basis:'客户已批准PPAP',owner:'陈工'}
];

export const backlog: BacklogItem[] = [
  {key:'paint',name:'待喷涂',quantity:18640,icon:'paint',count:5,oldest:4,owner:'喷涂部',items:['电控箱安装板','电机固定座','车身固定支架','设备外罩','传感器支撑片']},
  {key:'pack',name:'待包装',quantity:9280,icon:'box',count:5,oldest:2,owner:'包装部',items:['车身固定支架','电控箱安装板','电机固定座','连接器屏蔽罩','传感器支撑片']},
  {key:'ship',name:'待发货',quantity:12400,icon:'truck',count:5,oldest:3,owner:'发货部',items:['电控箱安装板','车身固定支架','连接器屏蔽罩','电机固定座','设备外罩']}
];

export const orders: OrderItem[] = [
  {id:'SO-2610081',client:'华辰电气',product:'电控箱安装板',due:'2026-10-16',quantity:2400,owner:'刘经理',state:'逾期1天',tone:'red'},
  {id:'SO-2610093',client:'远景汽车部件',product:'车身固定支架',due:'2026-10-18',quantity:3600,owner:'陈经理',state:'明日交付',tone:'amber'},
  {id:'SO-2610102',client:'卓越电子',product:'连接器屏蔽罩',due:'2026-10-18',quantity:2800,owner:'林经理',state:'明日交付',tone:'amber'},
  {id:'SO-2610108',client:'恒远机电',product:'电机固定座',due:'2026-10-18',quantity:1600,owner:'刘经理',state:'明日交付',tone:'amber'},
  {id:'SO-2610112',client:'华辰电气',product:'设备外罩',due:'2026-10-18',quantity:2000,owner:'陈经理',state:'明日交付',tone:'amber'},
  ...Array.from({length:7},(_,i)=>({id:`SO-26100${30+i}`,client:['华辰电气','远景汽车部件','卓越电子'][i%3],product:['安装定位片','连接支架','固定底座'][i%3],due:`2026-10-${12+i%5}`,quantity:0,shipped:[1200,1600,2000,1800,2400,1600,2000][i],owner:'销售部',state:'已发货',tone:'green' as Tone}))
];
export const issues: Issue[] = [
  {title:'电控箱安装板交付逾期',tag:'交付',description:'2,400件待发货 · 逾期1天',icon:'truck',owner:'刘经理 · 销售部',expected:'2026-10-18',impact:'影响华辰电气订单 SO-2610081，共2,400件。',reason:'客户运输车辆调整，订单已包装入库，等待确认提货时间。',next:'协调客户确认提货安排，并在今日内反馈预计发出时间。'},
  {title:'电控箱安装板开发延期',tag:'开发',description:'工程模试模调整 · 延期1天',icon:'cube',owner:'王工 · 开发部',expected:'2026-10-20',impact:'影响 DEV-26012 工程模开发进度，尚未进入PPAP批准阶段。',reason:'试模后发现孔位偏差，正在调整定位结构。',next:'完成模具调整并复测，更新验证结果与PPAP准备时间。'},
  {title:'电机固定座喷涂返工',tag:'质量',description:'120件待返工 · 需跟进交付影响',icon:'paint',owner:'周主管 · 喷涂部',expected:'2026-10-18',impact:'涉及电机固定座120件；返工数量单独记录。',reason:'涂层外观检查发现局部流挂，需要返修并重新检验。',next:'安排返修并复检合格，已计入合格产量的产品避免重复累计。'},
  {title:'软模改样方案待协调',tag:'协调',description:'锁扣安装片 · 等待方案确认',icon:'flag',owner:'李工 · 开发部',expected:'2026-10-19',impact:'影响锁扣安装片改样与后续客户验证。',reason:'客户提出安装面尺寸调整，开发与生产需要共同确认可行方案。',next:'确认修改方案、责任人与交付时间；相关操作后重新计算软模观察期。'}
];

export const observationDays = (item: DevelopmentProduct) => item.lastAction ? Math.max(0, Math.round((dateOf(addDays(item.lastAction, 30)).getTime() - dateOf(TODAY).getTime()) / DAY_MS)) : 0
export const PERIODS: Record<string, [string, string]> = { today: [TODAY, TODAY], week: ['2026-10-12', TODAY], month: ['2026-10-01', TODAY] }
const dailyRecords: Record<string, string | number>[] = []
for (let date = DEMO_MIN; date <= TODAY; date = addDays(date, 1)) {
  const dayIndex = Math.floor((dateOf(date).getTime() - dateOf(DEMO_MIN).getTime()) / DAY_MS)
  const row: Record<string, string | number> = { date }
  stageDefinitions.forEach((stage, i) => {
    const wave = .68 + ((dayIndex * (i + 3) + i * 7) % 29) / 40
    row[stage.key] = date === TODAY ? stage.base : Math.round(stage.base * wave * stage.factor / 10) * 10
    if (stage.bad !== undefined) {
      row[`${stage.key}Bad`] = date === TODAY ? stage.bad : Math.round(stage.bad * wave * .7)
      row[`${stage.key}Rework`] = date === TODAY ? stage.rework || 0 : Math.round((stage.rework || 0) * wave * .6)
    }
  })
  dailyRecords.push(row)
}
export const rangeRecords = (start: string, end: string) => dailyRecords.filter(r => String(r.date) >= start && String(r.date) <= end)
export const totalFor = (key: string, start: string, end: string) => rangeRecords(start, end).reduce((total, row) => total + Number(row[key] || 0), 0)
export const sparkPoints = (key: StageKey) => {
  const values = rangeRecords('2026-10-11', TODAY).map(r => Number(r[key]))
  const min = Math.min(...values) * .8, max = Math.max(...values) * 1.1
  return values.map((value, i) => `${i * 14},${22 - (value - min) / (max - min) * 19}`).join(' ')
}
