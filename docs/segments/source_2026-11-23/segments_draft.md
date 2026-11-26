# UBI Solutions target customer segment list (recovered research draft)

> Research version: 2026-11-23. Rebuilt from the research report and official-website search records saved by the previous Deep Research round; **not a byte-for-byte copy of the original sandbox files**. The research records cover 40 pages on the main `ubisolutions.net` domain; part of the evidence comes from page index summaries, and the full text was not re-checked page by page. Neither `robots.txt` compliance nor a request interval of at least 1 second has been **independently verified**. This draft is therefore for manual review and should not go directly into automated production scoring rules without checking.

## Definitions and usage

What is classified is the prospect company's **main business**, not the products or technology UBI Solutions sells. Matching input is limited to the LinkedIn company page's description, industry, specialties and employee count; country and region play no part in scoring. The industry names are the proposed LinkedIn industry mapping and should be checked against the LinkedIn industry enum version actually used before deployment. `explicit` means the official website has direct evidence for the industry or customer use case; `inferred` means the customer's main business type was generalized from a specific case or use scenario and does not correspond to a formal, separate industry entry on the website. The primary/secondary ranking of `rfid`, `geoloc` and `ubi_cloud` is a scorer design draft and needs approval from the business team.

## Segment families and segments

### Linen, textiles and workwear

#### Industrial laundry services | `industrial_laundry`

- **French name**: Blanchisserie industrielle
- **English name**: Industrial laundry services
- **Segment family**: Linen, textiles and workwear
- **Business description (customer's perspective)**: We provide specialized linen washing, disinfection, finishing and circulation services for hotel, hospital and institutional customers. Companies typically emphasize central laundry plants, industrial washing capacity, textile rental and continuous delivery.
- **Typical LinkedIn industries**: Facilities Services; Textile Manufacturing; Consumer Services
- **Positive keywords (FR)**: blanchisserie industrielle; location entretien linge; lavage industriel; blanchisserie hospitalière; traitement du linge; entretien textile; linge professionnel
- **Positive keywords (EN)**: industrial laundry; linen rental; commercial laundry; laundry services; linen processing; healthcare laundry; textile care
- **Positive keywords (ES)**: lavandería industrial; alquiler de ropa blanca; lavado industrial; lavandería hospitalaria; tratamiento de ropa; servicios de lavandería; mantenimiento textil
- **Confusable non-examples / how to tell apart**: Suppliers selling washing machines, dryers and laundry chemicals are not laundry operators. There must be business evidence of providing washing services, linen rental or linen circulation.
- **Problems we solve**: Linen loss, unclear customer ownership, hard-to-count inventory, tracking across washing stages, and circulation costs.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-laundry/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **Customers / partners explicitly named on the website**: AP-HP; BIH de Saint Germain en Laye; Interhospitalia; Fishers
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Hotels and hospitality | `hotels_hospitality`

- **French name**: Hôtellerie et hébergement
- **English name**: Hotels and hospitality
- **Segment family**: Linen, textiles and workwear
- **Business description (customer's perspective)**: We operate hotels, holiday accommodation or hotel groups, providing guests with rooms and lodging services. Company descriptions often mention hotel brands, guestrooms, reception services, accommodation facilities and property operations.
- **Typical LinkedIn industries**: Hospitality; Hotels and Motels
- **Positive keywords (FR)**: hôtel; hôtellerie; chaîne hôtelière; hébergement; chambres; établissement hôtelier; accueil des clients
- **Positive keywords (EN)**: hotel; hospitality; hotel chain; accommodation; guestrooms; lodging; guest services
- **Positive keywords (ES)**: hotel; hostelería; cadena hotelera; alojamiento; habitaciones; establecimiento hotelero; huéspedes
- **Confusable non-examples / how to tell apart**: Hotel booking software, hotel equipment dealers and short-term rental platforms are not hotel operators. Identify companies that actually operate accommodation facilities.
- **Problems we solve**: Linen loss and in-room linen allocation, inventory reconciliation, laundry handovers and operating costs.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-intelligent-hospitality/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **Customers / partners explicitly named on the website**: PPHE; Hilton
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Textile and linen manufacturing | `textile_manufacturing`

- **French name**: Fabrication textile et linge professionnel
- **English name**: Textile and linen manufacturing
- **Segment family**: Linen, textiles and workwear
- **Business description (customer's perspective)**: We design and produce bedding, linen or other textiles for institutional customers. Companies typically describe weaving, sewing, finished-goods production and their ability to supply customers or distribution channels.
- **Typical LinkedIn industries**: Textile Manufacturing; Apparel Manufacturing
- **Positive keywords (FR)**: fabricant textile; production de linge; tissage; confection; textile professionnel; linge de maison; industrie textile
- **Positive keywords (EN)**: textile manufacturer; linen production; weaving; garment production; institutional linens; textile factory; textile industry
- **Positive keywords (ES)**: fabricante textil; producción de ropa blanca; tejido; confección; textil profesional; fábrica textil; industria textil
- **Confusable non-examples / how to tell apart**: Laundry service providers and textile retailers are different from manufacturers. The key is a self-described activity of production, weaving, sewing and ex-factory supply, not just cleaning or selling.
- **Problems we solve**: Tracking linen identity and movement from production through delivery and the usage cycle.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/; https://ubisolutions.net/fr/solution/ubi-laundry/
- **Customers / partners explicitly named on the website**: TGL / Tissus Gisèle
- **Confidence**: `inferred`
- **Inference reason**: The TGL linen-tracking customer case on the official website supports the textile production stage, but textile manufacturing is not set up as a separate industry entry.

### Healthcare and public services

#### Hospitals and healthcare providers | `hospitals_healthcare`

- **French name**: Hôpitaux et établissements de santé
- **English name**: Hospitals and healthcare providers
- **Segment family**: Healthcare and public services
- **Business description (customer's perspective)**: We operate hospitals, treatment centers or general healthcare facilities, providing patients with medical care, nursing and inpatient services. Descriptions usually mention departments, clinical services, medical teams and healthcare facilities.
- **Typical LinkedIn industries**: Hospitals and Health Care; Medical Practices
- **Positive keywords (FR)**: hôpital; établissement de santé; centre hospitalier; soins aux patients; services hospitaliers; pharmacie hospitalière; équipement médical
- **Positive keywords (EN)**: hospital; healthcare provider; medical center; patient care; clinical services; hospital pharmacy; healthcare facilities
- **Positive keywords (ES)**: hospital; centro sanitario; atención al paciente; servicios hospitalarios; farmacia hospitalaria; centros médicos; equipamiento hospitalario
- **Confusable non-examples / how to tell apart**: Medical device manufacturers, clinic software vendors and pharmaceutical wholesalers are not hospital operators. The main activity should be actually providing medical care and hospital management services.
- **Problems we solve**: Locating equipment on wards, restocking drugs and consumables, counting hospital linen, recovering assets and inventory accuracy.
- **Business lines (primary/secondary)**: geoloc (primary); rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/hospital-assets-tracking/; https://ubisolutions.net/fr/solution/e-kanban-optimise-la-gestion-des-medicaments-en-pharmacie/; https://ubisolutions.net/fr/solution/ubi-laundry/; https://ubisolutions.net/it/products/etichette-elettroniche/
- **Customers / partners explicitly named on the website**: AP-HP
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Retail and distribution

#### Apparel and footwear retail | `apparel_footwear_retail`

- **French name**: Commerce de détail de vêtements et chaussures
- **English name**: Apparel and footwear retail
- **Segment family**: Retail and distribution
- **Business description (customer's perspective)**: We sell clothing, footwear and fashion accessories to consumers and operate physical stores or online retail channels. Company descriptions often emphasize brands, collections, store networks and omnichannel sales.
- **Typical LinkedIn industries**: Retail Apparel and Fashion; Retail
- **Positive keywords (FR)**: enseigne de mode; vente de vêtements; chaussures; magasins; distribution textile; prêt-à-porter; omnicanal
- **Positive keywords (EN)**: fashion retailer; apparel retail; footwear; retail stores; clothing chain; ready-to-wear; omnichannel
- **Positive keywords (ES)**: cadena de moda; venta de ropa; calzado; tiendas; distribución textil; prêt-à-porter; omnicanal
- **Confusable non-examples / how to tell apart**: Apparel design software, clothing equipment vendors and contract factories that only produce garments are not retail operators. There must be consumer-facing store or e-commerce sales.
- **Problems we solve**: Tracking tote boxes between stores and warehouses, inventory discrepancies, transfers, replenishment and stocktaking efficiency.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/gemo-tracabilite-rfid-des-supports-logistiques/; https://ubisolutions.net/fr/solution/ubi-retail-boost/
- **Customers / partners explicitly named on the website**: Gémo
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Specialty retail and e-commerce | `specialty_retail_ecommerce`

- **French name**: Commerce spécialisé et e-commerce
- **English name**: Specialty retail and e-commerce
- **Segment family**: Retail and distribution
- **Business description (customer's perspective)**: We run retail or e-commerce in specific product categories, selling physical goods to individual or business customers. Company descriptions often list the products sold, the online store, inventory management and order fulfillment.
- **Typical LinkedIn industries**: Retail; Internet Marketplace Platforms
- **Positive keywords (FR)**: commerce spécialisé; e-commerce; vente en ligne; boutique spécialisée; gestion des stocks; détaillant; catalogue produits
- **Positive keywords (EN)**: specialty retail; ecommerce; online store; specialist retailer; inventory management; product catalog; direct sales
- **Positive keywords (ES)**: comercio especializado; comercio electrónico; venta en línea; tienda especializada; gestión de existencias; minorista; catálogo de productos
- **Confusable non-examples / how to tell apart**: Companies providing e-commerce platform software, marketing services or payment services are not retailers. They must own or run merchandise sales and hold inventory.
- **Problems we solve**: Retail inventory visibility, online overselling, stocktaking, warehouse goods-in/goods-out and order errors.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/west-cheval-optimiser-gestion-stocks-inventaires/; https://ubisolutions.net/fr/usecase/wonderbox-assurer-inventaire-precis-stocks-coffrets/; https://ubisolutions.net/fr/solution/ubi-retail-boost/
- **Customers / partners explicitly named on the website**: West Cheval; Wonderbox
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Grocery and supermarket chains | `grocery_supermarket_chains`

- **French name**: Supermarchés et distribution alimentaire
- **English name**: Grocery and supermarket chains
- **Segment family**: Retail and distribution
- **Business description (customer's perspective)**: We operate supermarkets, grocery stores or food retail chains, supplying consumers with food and everyday goods. Company descriptions often emphasize stores, food retail, distribution centers and the supply chain.
- **Typical LinkedIn industries**: Retail Groceries; Retail
- **Positive keywords (FR)**: supermarché; grande distribution; distribution alimentaire; magasins alimentaires; épicerie; chaîne de supermarchés; centrale logistique
- **Positive keywords (EN)**: supermarket; grocery retail; food distribution; grocery stores; grocery chain; food retail; distribution center
- **Positive keywords (ES)**: supermercado; distribución alimentaria; tiendas de alimentación; tienda de comestibles; cadena de supermercados; comercio de alimentos; centro logístico
- **Confusable non-examples / how to tell apart**: Companies that only do food production or food wholesale are not supermarket retail networks. There must be consumer-facing grocery or food stores.
- **Problems we solve**: Tracking reusable crates, pallets and distribution assets; inventory loss between stores and distribution centers.
- **Business lines (primary/secondary)**: rfid (primary); geoloc (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Construction and heavy-asset operations

#### Construction contractors | `construction_contractors`

- **French name**: Entreprises de BTP et entrepreneurs généraux
- **English name**: Construction contractors
- **Segment family**: Construction and heavy-asset operations
- **Business description (customer's perspective)**: We carry out building works, infrastructure projects or public works, managing construction sites, staff and project equipment. Company descriptions often mention general contracting, civil engineering, site works and project delivery.
- **Typical LinkedIn industries**: Construction; Civil Engineering
- **Positive keywords (FR)**: entreprise de BTP; chantier; travaux publics; génie civil; construction; entrepreneur général; gestion de chantier
- **Positive keywords (EN)**: construction contractor; jobsite; public works; civil engineering; building projects; general contractor; site management
- **Positive keywords (ES)**: empresa constructora; obra; obras públicas; ingeniería civil; construcción; contratista general; gestión de obras
- **Confusable non-examples / how to tell apart**: Suppliers that only sell construction machinery, building materials or BIM software are not construction contractors. They must directly take on and execute construction projects.
- **Problems we solve**: Recovering site equipment, dispatching tools and machinery, asset loss, construction vehicle movements and utilization.
- **Business lines (primary/secondary)**: geoloc (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-construction-tracking-solution-de-geolocalisation-pour-le-btp/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/; https://ubisolutions.net/fr/solution/assets-tracking/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Construction equipment rental | `construction_equipment_rental`

- **French name**: Location de matériels et équipements de chantier
- **English name**: Construction equipment rental
- **Segment family**: Construction and heavy-asset operations
- **Business description (customer's perspective)**: We buy, manage and rent out construction machinery or engineering equipment, delivering it to contractors and site customers. Company descriptions usually mention the rental fleet, construction machinery, rental-period management and equipment maintenance.
- **Typical LinkedIn industries**: Equipment Rental Services; Construction; Machinery Manufacturing
- **Positive keywords (FR)**: location de matériel BTP; parc machines; engins de chantier; location d’équipements; matériel de construction; flotte de machines; maintenance des engins
- **Positive keywords (EN)**: construction equipment rental; equipment fleet; plant hire; heavy machinery rental; machinery hire; construction machines; fleet maintenance
- **Positive keywords (ES)**: alquiler de maquinaria; parque de máquinas; maquinaria de obra; alquiler de equipos; maquinaria de construcción; flota de máquinas; mantenimiento de equipos
- **Confusable non-examples / how to tell apart**: Only manufacturing or dealing in construction machinery does not make a company a rental operator. Confirm that it owns and operates equipment assets and offers rental services.
- **Problems we solve**: Rental fleet location, equipment recovery, cross-site dispatching, theft prevention, utilization and abnormal-movement alerts.
- **Business lines (primary/secondary)**: geoloc (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/batamat-geolocalisation-des-equipements-btp/; https://ubisolutions.net/fr/solution/ubi-construction-tracking-solution-de-geolocalisation-pour-le-btp/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/
- **Customers / partners explicitly named on the website**: Batamat
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Logistics, transport and supply chain

#### Third-party logistics and warehousing | `third_party_logistics`

- **French name**: Prestataires logistiques et entrepôts 3PL
- **English name**: Third-party logistics and warehousing
- **Segment family**: Logistics, transport and supply chain
- **Business description (customer's perspective)**: We provide warehousing, inventory management, order processing or outsourced logistics services to other companies. Company descriptions often emphasize logistics platforms, distribution centers, warehouse operations and supply-chain execution.
- **Typical LinkedIn industries**: Transportation, Logistics, Supply Chain and Storage; Warehousing and Storage
- **Positive keywords (FR)**: prestataire logistique; entreposage; logistique contractuelle; 3PL; préparation de commandes; plateforme logistique; gestion d’entrepôt
- **Positive keywords (EN)**: logistics provider; warehousing; contract logistics; 3PL; order fulfillment; distribution center; warehouse operations
- **Positive keywords (ES)**: operador logístico; almacenamiento; logística contractual; 3PL; preparación de pedidos; centro de distribución; gestión de almacenes
- **Confusable non-examples / how to tell apart**: Vendors that only sell warehouse software/WMS, or ordinary retailers with their own warehouses, are not automatically 3PLs. The key is operating warehousing and logistics for third-party customers.
- **Problems we solve**: Identification, mismatches and losses of returnable containers, pallets, in-warehouse stock and cross-site flows.
- **Business lines (primary/secondary)**: rfid (primary); geoloc (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/es/
- **Customers / partners explicitly named on the website**: DHL France
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Freight transportation companies | `freight_transport`

- **French name**: Transporteurs de marchandises
- **English name**: Freight transportation companies
- **Segment family**: Logistics, transport and supply chain
- **Business description (customer's perspective)**: We provide freight transport, vehicle dispatching or long-haul and short-haul transport services for customers. Company descriptions usually list the transport fleet, freight routes, road transport and delivery guarantees.
- **Typical LinkedIn industries**: Truck Transportation; Freight and Package Transportation
- **Positive keywords (FR)**: transport de marchandises; transport routier; flotte de camions; transporteur; fret; livraison de marchandises; transport logistique
- **Positive keywords (EN)**: freight transportation; road haulage; truck fleet; carrier; freight; cargo delivery; trucking services
- **Positive keywords (ES)**: transporte de mercancías; transporte por carretera; flota de camiones; transportista; carga; entrega de mercancías; transporte logístico
- **Confusable non-examples / how to tell apart**: Freight brokerage software or transport equipment vendors are not actual carriers. The company must describe itself as carrying freight or operating a carrier network.
- **Problems we solve**: In-transit cargo security, vehicle-cargo association, unauthorized-opening alerts and transport asset visibility.
- **Business lines (primary/secondary)**: geoloc (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/connected-lock/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/solution/assets-tracking/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Postal and parcel networks | `postal_parcel_network`

- **French name**: Réseaux postaux et de colis
- **English name**: Postal and parcel networks
- **Segment family**: Logistics, transport and supply chain
- **Business description (customer's perspective)**: We operate parcel, mail or express networks, building sorting centers and distributing parcels to outlets or recipients. Company descriptions usually emphasize sorting, the postal network, last-mile delivery and express handling.
- **Typical LinkedIn industries**: Freight and Package Transportation; Postal Services
- **Positive keywords (FR)**: colis; réseau postal; tri postal; centre de tri; messagerie express; livraison de colis; distribution postale
- **Positive keywords (EN)**: parcel delivery; postal network; mail sorting; sorting hub; express parcels; last-mile delivery; postal distribution
- **Positive keywords (ES)**: paquetería; red postal; clasificación postal; centro de clasificación; mensajería exprés; entrega de paquetes; distribución postal
- **Confusable non-examples / how to tell apart**: A general 3PL does not necessarily operate a postal or parcel sorting network. The key is national or multi-site sorting, delivery or postal operations.
- **Problems we solve**: Tracking the circulation of parcel sorting containers and routing boxes, site stocktaking and container loss.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **Customers / partners explicitly named on the website**: Viaposte; Le Groupe La Poste
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Industrial manufacturing

#### Industrial manufacturing companies | `industrial_manufacturing`

- **French name**: Entreprises manufacturières industrielles
- **English name**: Industrial manufacturing companies
- **Segment family**: Industrial manufacturing
- **Business description (customer's perspective)**: We operate production plants, processing raw materials or components into industrial products and supplying customers. Descriptions usually emphasize production lines, assembly shops, industrial processes and plant logistics.
- **Typical LinkedIn industries**: Manufacturing; Industrial Machinery Manufacturing
- **Positive keywords (FR)**: usine; production industrielle; assemblage; fabrication; site de production; chaîne de production; atelier industriel
- **Positive keywords (EN)**: factory; industrial production; assembly; manufacturing; production plant; production line; industrial workshop
- **Positive keywords (ES)**: fábrica; producción industrial; ensamblaje; fabricación; planta de producción; línea de producción; taller industrial
- **Confusable non-examples / how to tell apart**: Pure industrial consultancies, robotics integrators and equipment sellers should not be classed as manufacturers just because they serve manufacturing. They must manufacture their own products.
- **Problems we solve**: Tracking work in progress, materials, finished-goods goods-in/goods-out and plant assets, improving the visibility of production logistics.
- **Business lines (primary/secondary)**: rfid (primary); geoloc (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/en/products/rfid-tags/; https://ubisolutions.net/fr/products/tags-rfid/; https://ubisolutions.net/fr/usecase/faurecia-controle-et-suivi-des-flux-de-produits-entrants-et-sortants/; https://ubisolutions.net/fr/solution/assets-tracking/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Automotive manufacturing and suppliers | `automotive_manufacturing`

- **French name**: Construction automobile et équipementiers
- **English name**: Automotive manufacturing and suppliers
- **Segment family**: Industrial manufacturing
- **Business description (customer's perspective)**: We produce vehicles, vehicle modules, structural parts or automotive components, operating plants and an industrial supply chain. Descriptions usually state the automotive industry, vehicle or component production, and OEM or Tier 1 supply.
- **Typical LinkedIn industries**: Motor Vehicle Manufacturing; Motor Vehicle Parts Manufacturing
- **Positive keywords (FR)**: industrie automobile; équipementier automobile; pièces automobiles; constructeur automobile; usine automobile; assemblage automobile; sous-traitant automobile
- **Positive keywords (EN)**: automotive industry; automotive supplier; auto parts; vehicle manufacturer; car factory; automotive assembly; tier one supplier
- **Positive keywords (ES)**: industria automotriz; proveedor automotriz; autopartes; fabricante de automóviles; planta automotriz; ensamblaje automotriz; proveedor de primer nivel
- **Confusable non-examples / how to tell apart**: Car dealers and after-sales repair networks are not vehicle manufacturers. Confirm plant manufacturing activity and component production from the description.
- **Problems we solve**: Tracking automotive parts and packaging, inbound/outbound plant logistics, the order chain and inventory control.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/faurecia-controle-et-suivi-des-flux-de-produits-entrants-et-sortants/; https://ubisolutions.net/fr/solution/assets-tracking/
- **Customers / partners explicitly named on the website**: Faurecia
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Aerospace manufacturing | `aerospace_manufacturing`

- **French name**: Industrie aéronautique et aérospatiale
- **English name**: Aerospace manufacturing
- **Segment family**: Industrial manufacturing
- **Business description (customer's perspective)**: We design or produce aerospace structures, engines, systems or components, delivering products to the aircraft or space supply chain. Companies usually describe aviation manufacturing, industrial production and component quality processes.
- **Typical LinkedIn industries**: Aviation and Aerospace Component Manufacturing; Aviation & Aerospace
- **Positive keywords (FR)**: industrie aéronautique; fabrication aéronautique; aérospatial; pièces aéronautiques; équipementier aéronautique; chaîne d’assemblage; composants aéronautiques
- **Positive keywords (EN)**: aerospace manufacturing; aircraft components; aviation manufacturing; aerospace supplier; aircraft parts; assembly line; aeronautical equipment
- **Positive keywords (ES)**: industria aeroespacial; fabricación aeronáutica; componentes aeronáuticos; proveedor aeroespacial; piezas de avión; línea de montaje; equipamiento aeronáutico
- **Confusable non-examples / how to tell apart**: Airlines and airport operators are not aerospace manufacturers. There should be a description of manufacturing aerospace products or industrial parts.
- **Problems we solve**: Tracking and counting critical tools, equipment, part locations and industrial assets.
- **Business lines (primary/secondary)**: geoloc (primary); rfid (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/assets-tracking/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Transport and infrastructure

#### Rail transport and infrastructure operators | `rail_transport_operators`

- **French name**: Opérateurs ferroviaires et infrastructures
- **English name**: Rail transport and infrastructure operators
- **Segment family**: Transport and infrastructure
- **Business description (customer's perspective)**: We operate rail transport services, track infrastructure or railway assets, and are responsible for lines, stations and related equipment. Company descriptions often mention rail transport, the track network, maintenance and infrastructure operations.
- **Typical LinkedIn industries**: Rail Transportation; Ground Passenger Transportation
- **Positive keywords (FR)**: opérateur ferroviaire; réseau ferré; transport ferroviaire; infrastructure ferroviaire; maintenance des voies; matériel ferroviaire; exploitation ferroviaire
- **Positive keywords (EN)**: rail operator; rail network; railway transport; rail infrastructure; track maintenance; rolling stock; railway operations
- **Positive keywords (ES)**: operador ferroviario; red ferroviaria; transporte ferroviario; infraestructura ferroviaria; mantenimiento de vías; material rodante; explotación ferroviaria
- **Confusable non-examples / how to tell apart**: Companies that only make model trains or track equipment, or provide railway engineering consulting, are not rail operators. Check whether the company actually operates railways or manages track assets.
- **Problems we solve**: Location of trackside tools and infrastructure assets, counting maintenance equipment, loss alerts.
- **Business lines (primary/secondary)**: geoloc (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/assets-tracking/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **Customers / partners explicitly named on the website**: SNCF
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Culture, events and venues

#### Event production and services | `event_services`

- **French name**: Prestataires événementiels
- **English name**: Event production and services
- **Segment family**: Culture, events and venues
- **Business description (customer's perspective)**: We plan and run trade shows, performances, conferences or large events and provide on-site services for them. Descriptions usually emphasize event production, trade-show organization, lighting and staging, on-site operations or event materials.
- **Typical LinkedIn industries**: Events Services; Entertainment Providers
- **Positive keywords (FR)**: événementiel; organisation d’événements; salon professionnel; spectacle; production événementielle; matériel événementiel; exposition
- **Positive keywords (EN)**: event services; event production; trade shows; live events; event management; event equipment; exhibitions
- **Positive keywords (ES)**: servicios de eventos; organización de eventos; feria comercial; espectáculos; producción de eventos; material para eventos; exposiciones
- **Confusable non-examples / how to tell apart**: Suppliers that only sell AV equipment or event-management SaaS do not necessarily run live events. There must be a clear business of executing events, renting props or operating venues.
- **Problems we solve**: Reuse of event materials, exhibition fittings and on-site assets across multiple events, cross-venue location and loss prevention.
- **Business lines (primary/secondary)**: geoloc (primary); rfid (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-events-pour-assurer-la-tracabilite-de-vos-actifs/; https://ubisolutions.net/fr/usecase/optimisation-des-flux-logistiques/
- **Customers / partners explicitly named on the website**: None (the listed pages only provide industry/use-case evidence)
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Cultural institutions and venues | `cultural_institutions_venues`

- **French name**: Institutions et lieux culturels
- **English name**: Cultural institutions and venues
- **Segment family**: Culture, events and venues
- **Business description (customer's perspective)**: We operate museums, exhibition facilities or heritage venues, offering public exhibitions and cultural activities. Company descriptions usually mention exhibitions, collections, cultural events, the visitor experience and venue operations.
- **Typical LinkedIn industries**: Museums, Historical Sites, and Zoos; Performing Arts
- **Positive keywords (FR)**: musée; institution culturelle; lieu culturel; exposition; patrimoine; collections; gestion de site culturel
- **Positive keywords (EN)**: museum; cultural institution; cultural venue; exhibitions; heritage; collections; venue operations
- **Positive keywords (ES)**: museo; institución cultural; espacio cultural; exposición; patrimonio; colecciones; gestión de espacios culturales
- **Confusable non-examples / how to tell apart**: Exhibition fit-out companies and art software providers are not cultural institutions. Confirm that the company actually operates cultural venues, events or collections.
- **Problems we solve**: Cross-venue management of exhibition materials and logistics containers, transfers and stocktaking of exhibition assets.
- **Business lines (primary/secondary)**: rfid (primary); geoloc (secondary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/optimisation-des-flux-logistiques/; https://ubisolutions.net/fr/solution/ubi-events-pour-assurer-la-tracabilite-de-vos-actifs/
- **Customers / partners explicitly named on the website**: GrandPalaisRmn
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### Food and resources

#### Food and agricultural processing | `food_processing`

- **French name**: Industries agroalimentaires
- **English name**: Food and agricultural processing
- **Segment family**: Food and resources
- **Business description (customer's perspective)**: We operate food production, meat or agricultural processing plants, turning raw materials into saleable food. Descriptions often mention food processing, packaging, hygiene and quality control, and supply-chain traceability.
- **Typical LinkedIn industries**: Food and Beverage Manufacturing; Food Production
- **Positive keywords (FR)**: industries agroalimentaires; transformation alimentaire; usine alimentaire; production de viande; conditionnement alimentaire; traçabilité alimentaire; produits agricoles
- **Positive keywords (EN)**: food processing; food manufacturing; food factory; meat processing; food packaging; food traceability; agricultural products
- **Positive keywords (ES)**: industria alimentaria; procesamiento de alimentos; fábrica de alimentos; procesamiento cárnico; envasado alimentario; trazabilidad alimentaria; productos agrícolas
- **Confusable non-examples / how to tell apart**: Pure restaurants and food marketing consultancies are not food processing plants. There must be a description of processing, packaging or industrial production of raw materials.
- **Problems we solve**: Traceability of food batches, livestock and poultry products and containers from processing to distribution; food safety and recall accuracy.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/ubi-food-supply-chain-tracabilite-alimentaire/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **Customers / partners explicitly named on the website**: Sénécal; 3A SOLUTIONS SAS
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

#### Beverage and bottled water production | `beverage_bottling`

- **French name**: Production de boissons et embouteillage
- **English name**: Beverage and bottled water production
- **Segment family**: Food and resources
- **Business description (customer's perspective)**: We produce bottled water, beverages or other packaged drinks, operating filling and packaging lines. Company descriptions often mention water sources, beverage production, bottling and outbound logistics.
- **Typical LinkedIn industries**: Beverage Manufacturing; Food and Beverage Manufacturing
- **Positive keywords (FR)**: eau embouteillée; usine d’embouteillage; boisson; production de boissons; ligne de conditionnement; bouteille; fabricant de boissons
- **Positive keywords (EN)**: bottled water; bottling plant; beverages; drink production; packaging line; bottles; beverage manufacturer
- **Positive keywords (ES)**: agua embotellada; planta embotelladora; bebidas; producción de bebidas; línea de envasado; botellas; fabricante de bebidas
- **Confusable non-examples / how to tell apart**: Beverage retailers, bars and bottle manufacturers are not beverage bottlers. There must be beverage production or bottling operations.
- **Problems we solve**: Traceability of the bottling process, verification of cases and goods at truck loading, preventing mis-shipments and breaks in batch information.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/; https://ubisolutions.net/fr/solution/ubi-food-supply-chain-tracabilite-alimentaire/
- **Customers / partners explicitly named on the website**: Eaux de Zilia
- **Confidence**: `inferred`
- **Inference reason**: The official website lists a specific use case for Eaux de Zilia, but bottled water/beverage bottling is not listed as a separate target industry entry.

#### Industrial and hazardous waste management | `hazardous_waste_management`

- **French name**: Traitement des déchets industriels dangereux
- **English name**: Industrial and hazardous waste management
- **Segment family**: Food and resources
- **Business description (customer's perspective)**: We collect, recover, treat or dispose of industrial hazardous waste, operating specialized treatment facilities. Company descriptions often mention waste management, chemical waste, recycling and regulatory compliance.
- **Typical LinkedIn industries**: Environmental Services; Waste Treatment and Disposal
- **Positive keywords (FR)**: déchets dangereux; gestion des déchets industriels; traitement chimique; recyclage industriel; déchets chimiques; centre de traitement; traçabilité des déchets
- **Positive keywords (EN)**: hazardous waste; industrial waste management; chemical treatment; industrial recycling; chemical waste; waste treatment plant; waste traceability
- **Positive keywords (ES)**: residuos peligrosos; gestión de residuos industriales; tratamiento químico; reciclaje industrial; residuos químicos; planta de tratamiento; trazabilidad de residuos
- **Confusable non-examples / how to tell apart**: Environmental consultants or waste-management software companies are not operators that actually collect and treat hazardous waste. There must be waste treatment facilities or operations.
- **Problems we solve**: Locating hazardous-waste containers and storage positions, tracking in hazardous areas, evidence of waste movements and compliance checks.
- **Business lines (primary/secondary)**: geoloc (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/suez-tracabilite-des-dechets-dangereux/; https://ubisolutions.net/fr/solution/assets-tracking/
- **Customers / partners explicitly named on the website**: Suez; Suez IWS Chemical
- **Confidence**: `explicit`
- **Inference reason**: Not applicable (explicit industry or use-case evidence on the website)

### IT-asset-intensive organizations

#### Telecommunications operators | `telecommunications_operators`

- **French name**: Opérateurs de télécommunications
- **English name**: Telecommunications operators
- **Segment family**: IT-asset-intensive organizations
- **Business description (customer's perspective)**: We operate communication networks, providing telephone, internet or data connectivity services to households or businesses. Company descriptions usually describe telecom services, network infrastructure, broadband, mobile communications and data centers.
- **Typical LinkedIn industries**: Telecommunications; Wireless Services
- **Positive keywords (FR)**: opérateur télécom; réseau télécom; télécommunications; connectivité; réseau mobile; fournisseur internet; infrastructure réseau
- **Positive keywords (EN)**: telecom operator; telecom network; telecommunications; connectivity; mobile network; internet service provider; network infrastructure
- **Positive keywords (ES)**: operador de telecomunicaciones; red de telecomunicaciones; telecomunicaciones; conectividad; red móvil; proveedor de internet; infraestructura de red
- **Confusable non-examples / how to tell apart**: Telecom equipment manufacturers and data-center integrators are not telecom network operators. The company must provide and actually operate communication services or networks.
- **Problems we solve**: Fast stocktaking of server-room servers and network assets, in-place equipment verification and IT infrastructure registers.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/solution/serveurs-archives-inventaires-rapides/; https://ubisolutions.net/fr/usecase/banque-de-france-linventaire-des-serveurs-informatiques/
- **Customers / partners explicitly named on the website**: Orange
- **Confidence**: `inferred`
- **Inference reason**: The official website mentions a server stocktaking project at an Orange data center, but the telecom industry itself is not listed as a separate solution industry.

#### Banking and financial institutions | `financial_institutions`

- **French name**: Banques et institutions financières
- **English name**: Banking and financial institutions
- **Segment family**: IT-asset-intensive organizations
- **Business description (customer's perspective)**: We provide banking, currency, credit or other financial services, and operate the IT infrastructure that supports the business. Company descriptions usually mention banking and finance, payments, financial services, and branches or data centers.
- **Typical LinkedIn industries**: Banking; Financial Services
- **Positive keywords (FR)**: banque; institution financière; services bancaires; secteur financier; établissements financiers; système bancaire; services financiers
- **Positive keywords (EN)**: bank; financial institution; banking services; financial sector; banking organization; banking systems; financial services
- **Positive keywords (ES)**: banco; institución financiera; servicios bancarios; sector financiero; entidades financieras; sistema bancario; servicios financieros
- **Confusable non-examples / how to tell apart**: Financial consultancies, fintech software developers and banking equipment suppliers are not banks or financial institutions providing financial services.
- **Problems we solve**: Inventories of servers and server-room equipment, stocktaking of critical IT assets, accuracy and auditing of asset management.
- **Business lines (primary/secondary)**: rfid (primary); ubi_cloud (secondary)
- **Scale threshold**: None
- **Official website evidence URLs**: https://ubisolutions.net/fr/usecase/banque-de-france-linventaire-des-serveurs-informatiques/; https://ubisolutions.net/fr/solution/serveurs-archives-inventaires-rapides/
- **Customers / partners explicitly named on the website**: Banque de France
- **Confidence**: `inferred`
- **Inference reason**: The official website has a Banque de France server stocktaking case, but the financial industry is not a formal separate industry entry.

## Non-target types or types to exclude

| Type | Typical signals in the LinkedIn company description | Distinction and exclusion rule |
|---|---|---|
| Direct competitors | Provide RFID/RTLS/GPS/BLE/LoRa tracking platforms or asset-location SaaS, sell complete tracking solutions | If the main business is selling similar technology solutions to customers rather than operating the tracked assets, exclude or flag separately as a competitor |
| RFID / IoT hardware makers | Make or sell readers, antennas, RFID tags, beacons, gateways, trackers, sensors | Do not classify as a user because product keywords such as `RFID` or `asset tracking` appear |
| System integrators / software implementers | system integration, intégration RFID, déploiement IoT, intégrateur | Their own business is deploying, integrating or maintaining solutions for others; they are not end-industry customers |
| Distributors / VARs / wholesale agents | distributeur, revendeur, reseller, value-added reseller, grossiste technologique | They sell third-party equipment or technology and should not be classified directly by their customers' industry |
| IT / supply-chain consultancies | conseil, consulting, digital transformation, supply chain consulting | Consulting and methodology are not warehousing, production, healthcare or transport operations |
| WMS / ERP / SaaS software vendors | warehouse management software, ERP vendor, logistics SaaS | Helping customers manage their business does not mean they run warehouses or logistics networks themselves |
| Industry equipment makers / suppliers | fabricant de machines à laver, équipements BTP, matériel médical, AV equipment | Do not classify laundry equipment vendors as laundries, nor equipment sellers as construction/hospital/event operators |
| Cross-industry companies with only internal assets | Only mention tracking, inventory, fleet, without stating a clear main business | Do not force a classification from technology-need keywords; classify by the actual main business first, and use `unknown` if necessary |

## Questions awaiting manual confirmation

1. Are the three retail segments (apparel and footwear, specialty retail/e-commerce, supermarkets) mutually exclusive, hierarchical, or multi-label?
2. How should third-party logistics, freight and postal/parcel networks be prioritized? Should mixed logistics groups get multiple labels?
3. When hotels, hospitals, industrial laundries and linen manufacturers appear in the same linen chain, the label should be decided by who the actual buyer is.
4. Is `industrial_manufacturing` only a catch-all segment, and how should it be deduplicated against the automotive and aerospace industry segments?
5. For the four inferred segments (TGL, Eaux de Zilia, Orange, Banque de France), is there enough commercial coverage to keep them long term?
6. The actual rules in the website's robots.txt, whether the pages may be crawled, and the request timestamps have not been verified. LinkedIn industry enum names need a technical review.
