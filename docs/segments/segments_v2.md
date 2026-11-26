# Target segment list v2 (2026-11-24)

Data file: [segments_v2.csv](segments_v2.csv), 37 segments in total. Sources:

- **Draft**: the recovered research draft from 2026-11-23, with 24 segments. The original files are in [source_2026-11-23/](source_2026-11-23/); the website evidence in them was not checked page by page.
- **New**: 13 segments, derived from the 508 customer units in Dolibarr (the part of `lookalike_units.csv` with `label=positive` that is matched to LinkedIn).

## Purpose

This list is the second layer of the scorer: first determine what a company does and which segment it belongs to, then score by segment.

- Only the company's main business is considered; country plays no part in scoring.
- Keywords and LinkedIn industries are used to **explain** the scoring result, not to **decide** it. Keywords alone hit only 33% of customers.
- The main basis is the business description, compared with the company description by similarity.

## Rules decided

| Rule | Decision |
|---|---|
| Banks, telecom operators | Kept as segments, use limited to IT asset and server inventory (user, 2026-11-24) |
| Size and research institutes | Companies with fewer than 51 employees and research institutes are **lowered to low priority, not excluded** (user, 2026-11-24). They do fit our business, but contacting them is worth less and sales have higher-priority targets. See "Scoring output" below |
| Large restaurant chains | Count as targets, classed under `contract_catering`; small restaurants and small cafés do not count |
| "Could use it" | Only counts as a target when the tracked objects are its core assets or core business |
| competitor / supplier | Those directly selling tracking, location or RFID solutions (including tracker and reader OEMs and fleet-management solutions) are competitors, not targets; supporting and adjacent systems in our industry are suppliers. General manufacturers count as targets even if they produce components |

## Segment overview

A rough classification using keywords plus LinkedIn industries assigned 90% of the 508 customers and 88% of the 1,101 prospects to a segment. "Customer business-line share" counts only customers whose business line can be determined; it is the share that actually bought each line and can be used to check the "Primary/secondary" column.

| segment_id | Name | Segment family | Customers | Prospects | Customer business-line share geoloc / rfid / cloud | Primary/secondary (draft + corrections) | Share of customers with LinkedIn employee count < 51 | Source |
|---|---|---|---:|---:|---|---|---:|---|
| `industrial_manufacturing` | Industrial manufacturing companies | Industrial manufacturing | 79 | 193 | 0.38 / 0.6 / 0.28 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.3 | Draft |
| `local_government` | Local government and municipalities | Healthcare and public services | 33 | 59 | 0.33 / 0.8 / 0.0 | rfid (primary); geoloc (primary); ubi_cloud (secondary) | 0.48 | New |
| `industrial_laundry` | Industrial laundry services | Linen, textiles and workwear | 29 | 46 | 0.0 / 1.0 / 0.15 | rfid (primary); ubi_cloud (secondary) | 0.62 | Draft |
| `construction_contractors` | Construction contractors | Construction and heavy-asset operations | 26 | 74 | 0.95 / 0.05 / 0.05 | geoloc (primary); ubi_cloud (secondary) | 0.31 | Draft |
| `third_party_logistics` | Third-party logistics and warehousing | Logistics, transport and supply chain | 25 | 24 | 0.44 / 0.44 / 0.31 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.2 | Draft |
| `apparel_footwear_retail` | Apparel and footwear retail | Retail and distribution | 21 | 42 | 0.0 / 1.0 / 0.25 | rfid (primary); ubi_cloud (secondary) | 0.33 | Draft |
| `hotels_hospitality` | Hotels and hospitality | Linen, textiles and workwear | 21 | 92 | 0.0 / 1.0 / 0.5 | rfid (primary); ubi_cloud (secondary) | 0.1 | Draft |
| `wholesale_distribution` | Wholesale and distribution | Retail and distribution | 16 | 35 | 0.38 / 0.62 / 0.25 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.44 | New |
| `waste_management` | Waste collection, recycling and treatment | Food and resources | 15 | 36 | 0.78 / 0.44 / 0.11 | geoloc (primary); ubi_cloud (secondary) | 0.47 | Draft (scope widened) |
| `food_processing` | Food and agricultural processing | Food and resources | 15 | 42 | 0.17 / 1.0 / 0.33 | rfid (primary); ubi_cloud (secondary) | 0.2 | Draft |
| `hospitals_healthcare` | Hospitals and healthcare providers | Healthcare and public services | 15 | 45 | 0.08 / 0.77 / 0.38 | geoloc (primary); rfid (primary); ubi_cloud (secondary) | 0.07 | Draft |
| `freight_transport` | Freight transportation companies | Logistics, transport and supply chain | 13 | 21 | 0.89 / 0.33 / 0.44 | geoloc (primary); ubi_cloud (secondary) | 0.23 | Draft |
| `specialty_retail_ecommerce` | Specialty retail and e-commerce | Retail and distribution | 12 | 18 | 0.25 / 0.88 / 0.12 | rfid (primary); ubi_cloud (secondary) | 0.08 | Draft |
| `it_asset_services` | IT equipment leasing, maintenance and outsourcing | IT-asset-intensive organizations | 12 | 19 | 0.57 / 0.57 / 0.29 | rfid (primary); ubi_cloud (secondary) | 0.25 | New |
| `event_services` | Event production and services | Culture, events and venues | 11 | 9 | 0.6 / 0.5 / 0.2 | geoloc (primary); rfid (secondary); ubi_cloud (secondary) | 0.45 | Draft |
| `financial_institutions` | Banking and financial institutions | IT-asset-intensive organizations | 11 | 13 | 0.29 / 0.71 / 0.71 | rfid (primary); ubi_cloud (secondary) | 0.55 | Draft |
| `automotive_manufacturing` | Automotive manufacturing and suppliers | Industrial manufacturing | 11 | 13 | 0.29 / 0.71 / 0.29 | rfid (primary); ubi_cloud (secondary) | 0.09 | Draft |
| `aerospace_manufacturing` | Aerospace and defense manufacturing | Industrial manufacturing | 10 | 26 | 0.43 / 0.57 / 0.14 | geoloc (primary); rfid (secondary); ubi_cloud (secondary) | 0.3 | Draft (merged with defense) |
| `energy_utilities` | Energy and utilities | Construction and heavy-asset operations | 9 | 16 | 0.57 / 0.43 / 0.43 | geoloc (primary); rfid (primary); ubi_cloud (secondary) | 0.33 | New |
| `cultural_institutions_venues` | Cultural institutions and venues | Culture, events and venues | 9 | 14 | 0.4 / 0.6 / 0.2 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.22 | Draft |
| `construction_equipment_rental` | Construction equipment rental | Construction and heavy-asset operations | 6 | 10 | 1.0 / 0.0 / 0.0 | geoloc (primary); ubi_cloud (secondary) | 0.5 | Draft |
| `leisure_sports_venues` | Leisure parks, sports venues and federations | Culture, events and venues | 6 | 5 | 0.0 / 1.0 / 0.33 | geoloc (primary); rfid (secondary); ubi_cloud (secondary) | 0.33 | New |
| `textile_manufacturing` | Textile and linen manufacturing | Linen, textiles and workwear | 6 | 13 | 0.0 / 1.0 / 0.0 | rfid (primary); ubi_cloud (secondary) | 0.67 | Draft |
| `research_labs` | Research institutes and laboratories | IT-asset-intensive organizations | 5 | 5 | 0.0 / 1.0 / 0.0 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.0 | New |
| `agriculture_cooperatives` | Agriculture and agricultural cooperatives | Food and resources | 5 | 25 | 0.5 / 0.5 / 0.0 | geoloc (primary); rfid (secondary); ubi_cloud (secondary) | 0.2 | New |
| `social_care_residential` | Care homes, disability services and residences | Healthcare and public services | 5 | 17 | 0.0 / 0.75 / 0.25 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.8 | New |
| `grocery_supermarket_chains` | Grocery and supermarket chains | Retail and distribution | 5 | 3 | 0.5 / 0.75 / 0.5 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.0 | Draft |
| `contract_catering` | Contract catering and large restaurant chains | Food and resources | 4 | 12 | 1.0 / 0.0 / 0.0 | rfid (primary); ubi_cloud (secondary) | 0.0 | New |
| `security_inspection` | Security, patrol and inspection services | Transport and infrastructure | 4 | 5 | 0.33 / 0.67 / 0.33 | geoloc (primary); ubi_cloud (secondary) | 0.0 | New |
| `airports_aviation_services` | Airports and aviation ground services | Transport and infrastructure | 4 | 5 | 0.67 / 0.33 / 0.0 | geoloc (primary); rfid (secondary); ubi_cloud (secondary) | 0.25 | New |
| `beverage_bottling` | Beverage and bottled water production | Food and resources | 3 | 7 | 1.0 / 0.0 / 0.0 | rfid (primary); ubi_cloud (secondary) | 0.33 | Draft |
| `telecommunications_operators` | Telecommunications operators | IT-asset-intensive organizations | 2 | 10 | 0.0 / 1.0 / 0.5 | rfid (primary); ubi_cloud (secondary) | 0.0 | Draft |
| `passenger_transport` | Urban transit and passenger transport | Transport and infrastructure | 2 | 1 | 0.5 / 0.5 / 0.5 | geoloc (primary); ubi_cloud (secondary) | 0.0 | New |
| `facility_services` | Facility management and cleaning services | Linen, textiles and workwear | 2 | 9 | 1.0 / 0.0 / 0.0 | rfid (primary); geoloc (secondary); ubi_cloud (secondary) | 0.0 | New |
| `vehicle_dealerships` | Vehicle dealerships | Retail and distribution | 2 | 3 | – | geoloc (primary); ubi_cloud (secondary) | 0.0 | New |
| `postal_parcel_network` | Postal and parcel networks | Logistics, transport and supply chain | 1 | 0 | 0.0 / 1.0 / 0.0 | rfid (primary); ubi_cloud (secondary) | 0.0 | Draft |
| `rail_transport_operators` | Rail transport and infrastructure operators | Transport and infrastructure | 1 | 1 | 1.0 / 1.0 / 1.0 | geoloc (primary); ubi_cloud (secondary) | 0.0 | Draft |

This rough classification used keywords, so some segments are undercounted, for example textile manufacturing, contract catering and rail. Customer counts only show that a segment really has customers; they do not reflect the true distribution. Recompute once the Layer 1 classifier is built.

## What changed from the draft

- Added LinkedIn industries and keywords to industrial laundry, textile manufacturing, specialty retail and industrial manufacturing. The reason is that many customers are listed only under industries such as `Laundry and Drycleaning Services`, chemicals, packaging or jewellery retail, which the original list could not match.
- Added workwear and uniforms: the website has a UBI Workwear product page, but the draft had no matching segment.
- Merged aerospace with defense manufacturing (Thales, Airbus, etc.).
- Widened hazardous waste to general waste: 13 customers are under Environmental Services, and most do not treat hazardous waste.
- Two LinkedIn industry names in the draft never appeared in the roughly 40,000 scraped company pages and were removed. All other industry names in the list were checked and do exist.

## The draft's 6 open questions: recommendations

1. **The three retail segments**: mutually exclusive sub-segments under "Retail and distribution" (the new wholesale and vehicle dealership segments also go here). Each company gets one primary segment; a secondary segment is added only when its description explicitly states two main businesses.
2. **The three logistics segments**: same as above, the primary segment follows the main business. Mixed logistics groups get at most two segments, taking the higher-scoring one. The business lines of these three are similar, so which one takes priority matters little.
3. **The linen chain**: classify by what the company **itself** does, not by "who pays". Laundries, hotels, hospitals and textile manufacturers are all targets; scoring does not need to determine who the buyer is.
4. **`industrial_manufacturing`**: the catch-all manufacturing segment. If there is evidence for a specific sub-segment such as automotive, aerospace, food, beverage or textile, use the specific one.
5. **The four inferred segments**:
   - banks and telecom: the user has confirmed keeping them;
   - textile manufacturing: 23 customers are under the Textile Manufacturing industry, enough evidence;
   - beverages: customers include France Boissons, PepsiCo, etc.; also kept.
6. **Compliance and industry names**: robots.txt cannot be re-checked, but this does not affect scoring. LinkedIn industry names have been checked against the actually scraped data (see the previous section).

## Scoring output: fit and priority kept separate

Scoring answers two different questions, output as two columns:

1. **Fit**: which of our segments matches what this company does, and how well. Business only, not size.
2. **Priority**: whether this company is worth sales contacting now.
   - companies with fewer than 51 employees are lowered to low priority;
   - segments with `segment_priority=low` (currently only `research_labs`) are also lowered to low priority.

Low priority does not mean no fit. These companies stay on the list, just ranked lower. So when evaluating fit, small customers and research-institute customers still count as correct examples.

Which number to use for size: the LinkedIn employee count is the number of people who list this company as their employer, which heavily underestimates organisations whose staff rarely use LinkedIn. By this number, 34% of current customers are below 51, including 48% of municipalities and 62% of laundries. We recommend using instead the lower bound of the company's own declared employee range (`employee_count_range`); by that measure only 19% of customers are below 51. When the declared employee range is missing, record it as "unknown" and do not lower the priority.

## IT services, media and consulting customers with closed orders

For customers like Econocom, CFI, Ouest-France and Accenture, the type was assigned automatically by rules; it was not confirmed whether they use the products themselves or resell them to others. The user decided on 2026-11-24: **any company with a closed order counts as a customer**. So, like other customers, they count as correct examples when evaluating the scorer, and the `it_asset_services` segment is also kept.
