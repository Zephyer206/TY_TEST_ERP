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
No additional user design constraints recorded.
