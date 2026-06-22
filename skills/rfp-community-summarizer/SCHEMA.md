# GraphRAG Schema — Entity and Relationship Types

This file is the authoritative schema reference for the DocSync Agent knowledge graph.
When adding new entity or relationship types, update this file **and** the rfp-data-prep SKILL.md.

---

## Entity Types

| Type | Description | Example values |
|---|---|---|
| `client` | The organisation issuing the RFP | Halcyon Agri-Industrial Group, Meridian International Holdings |
| `service_provider` | The firm tendering for the engagement | KPMG |
| `service` | The specific engagement or service line | External Audit Services, ESG & Sustainability Assurance |
| `investor` | Shareholder or PE sponsor of the client | Halcyon Capital Partners LP |
| `standard` | Accounting, auditing, or reporting standard | IFRS 15, ISA 315, ISQM 1, SOX 404(b), ISSB S1 |
| `regulator` | Regulatory or oversight body | PCAOB, FRC, SEC, ACRA, ICAEW, ICPAS |
| `location` | Country or city of operations or HQ | Singapore, United Kingdom, Indonesia |
| `concept` | Audit focus area or complex accounting theme | Revenue Recognition, Biological Asset Valuation, GHG Emissions |
| `lender` | Bank or lender in a credit facility | DBS Bank, OCBC Bank, Standard Chartered |
| `financial_instrument` | Debt facility, fee budget, or financial structure | SGD 350M Syndicated Revolving Credit Facility, Audit Fee Budget SGD 1.2M |
| `acquisition_target` | Entity acquired or under acquisition | PT Agro Nusantara Jaya, Vietnam Fresh Logistics JSC |
| `technology` | System or tool used by the client or auditor | SAP S/4HANA, KPMG Clara, Kyriba, OneStream |
| `exchange` | Stock exchange where client is listed | London Stock Exchange, NYSE |
| `deliverable` | Output produced by the audit engagement | Management Letter, Covenant Compliance Confirmation, Comfort Letter |

---

## Relationship Types

| Type | Direction | Meaning | Example |
|---|---|---|---|
| `requires` | service → standard | Audit engagement requires this standard | Halcyon External Audit → IFRS 15 |
| `issued_by` | service → client | RFP issued by client to service provider | Halcyon External Audit → KPMG |
| `owned_by` | client → investor | Client owned by an investor / PE sponsor | Halcyon → Halcyon Capital Partners LP |
| `governed_by` | entity → regulator | Entity is governed by a regulator or standard | Halcyon → ACRA |
| `located_in` | entity → location | Entity is headquartered in this location | Halcyon → Singapore |
| `operates_in` | entity → location | Entity has operations in this country | Halcyon → Indonesia |
| `has_lender` | client → lender | Client has a lending relationship with this bank | Halcyon → DBS Bank |
| `acquired` | entity → acquisition_target | Entity acquired this target | Halcyon → PT Agro Nusantara Jaya |
| `uses` | entity → technology | Entity uses this system or tool | Meridian → SAP S/4HANA |
| `requires_audit_focus` | standard → concept | Standard creates a specific audit risk area | IAS 41 → Biological Asset Valuation |
| `mentions` | document → entity | Weaker link — document references entity without a primary relationship | — |
| `has_deliverable` | service → deliverable | Audit service produces this deliverable | Halcyon External Audit → Management Letter |
| `listed_on` | client → exchange | Company is listed on this exchange | Meridian → London Stock Exchange |
| `has_instrument` | client → financial_instrument | Client holds this financial instrument | Halcyon → SGD 350M Syndicated RCF |
| `similar_to` | entity ↔ entity | Entities with overlapping scope | Halcyon External Audit ↔ Meridian External Audit |
| `part_of` | entity → entity | Entity is a subsidiary or component of another | DBS → SGD 350M RCF (syndicate member) |
| `has_budget` | service → financial_instrument | Audit engagement has an indicative fee or budget amount | Halcyon External Audit → Audit Fee Budget SGD 1.2M |

---

## Notes on `has_budget`

- **When to extract:** Any time an RFP states an indicative fee budget, fee cap, annual audit cost estimate, or total engagement cost — even as a range (e.g. "SGD 800K–1.2M per annum").
- **Target entity type:** Create a `financial_instrument` entity for the budget value (e.g. `id: audit_fee_budget_halcyon`, `name: "Audit Fee Budget SGD 1.2M"`, `attributes: { amount: "SGD 1.2M", frequency: "per annum" }`).
- **Source → target:** The `service` entity (e.g. `halcyon_external_audit`) is the source; the `financial_instrument` budget entity is the target.
- **Do not use** `has_instrument` for budgets — reserve that for debt facilities and financial structures. Use `has_budget` for fee/cost references only.

---

## Extending the schema

To add a new entity type or relationship type:
1. Add it to this file with description, direction, and an example
2. Add it to the `rfp-data-prep` SKILL.md — both the type list and the extraction guidelines
3. Add it to the **Relationship types** or **Entity types** reference table in `CLAUDE.md` (both `DocSync/` and `Smart_RAG/`)
4. Re-run `rfp-data-prep` to extract the new type from existing documents

The Python scripts (`build_graph.py`, `generate_graph_html.py`, `query_graph.py`) are schema-agnostic — they treat entities and relationships as generic JSON objects and require no changes when the schema is extended.
