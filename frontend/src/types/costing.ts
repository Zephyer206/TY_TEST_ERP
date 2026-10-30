export interface TreatmentItem { item_key: string; name: string; requirements: string; source: string }
export interface SurfaceTreatment { status: 'pending' | 'none' | 'required'; revision: number; items: TreatmentItem[] }
export interface Candidate { alias_id: number; part_id: number; tooling_id: number; spec_id: number | null; customer_part_no: string; part_name: string; material_name: string; tooling_number: string; mold_type: string; spec_twph: string; eligibility: string; reason: string }
export interface MaterialPrice { id: number; code: string; name: string; density: string | null; material_price: string | null; scrap_price: string | null }
export interface ChargeRule { id: number; name: string; rate: string; unit: string; calc_mode: string }
export interface CostResult { rule_version: string; material: { amount: string | null; gross_weight_g: string | null; net_weight_g: string | null; net_weight_basis: string; issues: string[] }; surface_amount: string | null; known_subtotal: string; total: string | null; completeness: string; issues: string[]; optional_costs: {category: string;name: string;selected:boolean;amount:string|null}[] }
export interface CostingTask { id: number; name: string; customer_id: number; customer?: string }
export interface CostingItem { id: number; version: number; part_id: number; alias_id: number; tooling_id: number; spec_id: number | null; customer_part_no: string; part_name: string; tooling_number: string; latest_revision_id: number | null; result: CostResult | null }
export interface CostingRevision { id: number; revision_no: number; inputs: any; context: any; result: CostResult; created_at: string; reason: string }
export interface ImportRow { row: number; customer_part_no: string; tooling_number: string; candidates: Candidate[]; status: string; reason: string; source_reference?: Record<string,unknown> }
