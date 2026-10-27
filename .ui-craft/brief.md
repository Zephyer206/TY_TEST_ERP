# Zephyr ERP interface brief

Manufacturing ERP for Chinese-speaking engineering, sales, production and warehouse teams. Existing Vue 3, Element Plus and VXE components remain the implementation stack.

## Design intent
Preserve the current blue-gray palette, compact desktop workbench and business navigation. Improve reading hierarchy, form grouping, recovery states and keyboard access. Use neutral surfaces, one operational accent and tabular numbers. No decorative entrance animations for tables or repeated navigation.

## Constraints
- Existing design references live in `design-system/zephyr-erp/`; running CSS tokens are the current source of truth.
- All backend requests go through registered domain API modules.
- Real browser acceptance is required; compilation alone is insufficient.
- Preserve existing work and business records during UI acceptance.
- Controls must remain usable at narrow viewport widths and with reduced motion.

## Refinement settings
Craft 7; motion 2; density 7; variance 3. Signature detail: calm technical data with clear section dividers and persistent long-form actions.

## Learned constraints
- Name the workbench overview tab 总览.
- Inquiry engineering selects a press type, never an individual machine. Types combine tonnage and axis configuration, for example 160T 双轴 and 200T 双轴. Actual machine assignment belongs to production scheduling.
- Show separate dual-axis tonnage filters in scheduling; a generic 双轴 filter does not identify the required capacity.
- Split standard/dual-axis labels only when both variants exist at the same tonnage. Sole dual-axis capacities such as 300T and 400T retain one tonnage option; preserve their axis metadata without adding duplicate options.

## QR presentation principle — user instruction, 2026-10-24

In the QR workspaces, lead with orders, parts, materials, batches, quantities, status and process steps. QR supports scan-to-locate, stable identity, printing and traceability. By default, long payloads, QR images and database IDs must not become the page title or dominate the main content; show them in supporting details or when a scanning/printing task needs them.

Unbound label management may lead with the stable label identifier because no business association exists yet. Show missing business information honestly; do not invent an order, part, customer or quantity. Screen hierarchy must not reduce the printed QR below its scannable physical size or remove its quiet zone; retain the printing contract's label dimensions.

This is a new presentation principle explicitly provided by the user on 2026-10-24. It is separate from the three business answers accepted on 2026-10-13 and does not add a business clarification answer, requirement ID, success criterion or task.
