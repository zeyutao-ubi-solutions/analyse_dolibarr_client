# UBI Solutions 目标客户细分清单（研究恢复稿）

> 研究版本：2026-11-23。根据上一轮 Deep Research 已保存的研究报告和官网检索记录重建，**不是原始沙盒文件的逐字节副本**。研究记录共涉及 40 个 `ubisolutions.net` 主域名页面，部分证据来自页面索引摘要，未逐页重新核对全文。`robots.txt` 与各请求间隔至少 1 秒均**未得到独立验证**。因此本稿用于人工校审，不建议未经复核直接进入自动评分生产规则。

## 定义与使用方式

分类对象是潜在客户公司的**主营业务**，不是 UBI Solutions 所销售的产品或技术。匹配输入限制为 LinkedIn 公司页的简介、行业、专长与员工数；国家和地区不参与评分。行业名称是拟采用的 LinkedIn 行业映射，建议在部署前与实际使用的 LinkedIn 行业枚举版本核对。`explicit` 指官网有对应行业或客户应用直接证据，`inferred` 指由具体案例或使用场景归纳出客户主营业务类型，不代表官网正式独立行业入口。`rfid`、`geoloc`、`ubi_cloud` 的主次关系属于打分器设计草稿，需业务人员审批。

## 大类与细分

### 布草、纺织与工服

#### 工业洗衣房 | `industrial_laundry`

- **法文名**：Blanchisserie industrielle
- **英文名**：Industrial laundry services
- **所属大类**：布草、纺织与工服
- **业务描述（客户视角）**：我们为酒店、医院或机构客户提供专业化的布草洗涤、消毒、整理与周转服务。公司通常强调中央洗衣厂、工业洗涤产能、纺织品租赁和持续交付。
- **典型 LinkedIn 行业**：Facilities Services; Textile Manufacturing; Consumer Services
- **正向关键词（FR）**：blanchisserie industrielle; location entretien linge; lavage industriel; blanchisserie hospitalière; traitement du linge; entretien textile; linge professionnel
- **正向关键词（EN）**：industrial laundry; linen rental; commercial laundry; laundry services; linen processing; healthcare laundry; textile care
- **正向关键词（ES）**：lavandería industrial; alquiler de ropa blanca; lavado industrial; lavandería hospitalaria; tratamiento de ropa; servicios de lavandería; mantenimiento textil
- **易混淆的反例 / 区分方法**：销售洗衣机、烘干机和洗涤化学品的供应商不等于运营洗衣厂。需出现承接洗涤服务、布草租赁或布草周转的业务证据。
- **我们解决的问题**：布草丢失、客户归属不清、库存难盘点、跨洗涤工序追踪与周转成本。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-laundry/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **官网明确出现的客户 / 合作方**：AP-HP; BIH de Saint Germain en Laye; Interhospitalia; Fishers
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 酒店与住宿业 | `hotels_hospitality`

- **法文名**：Hôtellerie et hébergement
- **英文名**：Hotels and hospitality
- **所属大类**：布草、纺织与工服
- **业务描述（客户视角）**：我们经营酒店、度假住宿或酒店集团，为客人提供客房和住宿服务。公司简介常提到酒店品牌、客房、接待服务、住宿设施和物业运营。
- **典型 LinkedIn 行业**：Hospitality; Hotels and Motels
- **正向关键词（FR）**：hôtel; hôtellerie; chaîne hôtelière; hébergement; chambres; établissement hôtelier; accueil des clients
- **正向关键词（EN）**：hotel; hospitality; hotel chain; accommodation; guestrooms; lodging; guest services
- **正向关键词（ES）**：hotel; hostelería; cadena hotelera; alojamiento; habitaciones; establecimiento hotelero; huéspedes
- **易混淆的反例 / 区分方法**：酒店预订软件、酒店设备经销商和民宿平台不是酒店运营方。需识别实际经营住宿设施的企业。
- **我们解决的问题**：布草流失与房间布草配置、库存核对、洗涤交接和运营成本。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-intelligent-hospitality/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **官网明确出现的客户 / 合作方**：PPHE; Hilton
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 纺织品与布草制造商 | `textile_manufacturing`

- **法文名**：Fabrication textile et linge professionnel
- **英文名**：Textile and linen manufacturing
- **所属大类**：布草、纺织与工服
- **业务描述（客户视角）**：我们设计并生产面向机构客户的床品、布草或其他纺织品。公司通常介绍织造、缝制、成品生产及向客户或分销渠道供货的能力。
- **典型 LinkedIn 行业**：Textile Manufacturing; Apparel Manufacturing
- **正向关键词（FR）**：fabricant textile; production de linge; tissage; confection; textile professionnel; linge de maison; industrie textile
- **正向关键词（EN）**：textile manufacturer; linen production; weaving; garment production; institutional linens; textile factory; textile industry
- **正向关键词（ES）**：fabricante textil; producción de ropa blanca; tejido; confección; textil profesional; fábrica textil; industria textil
- **易混淆的反例 / 区分方法**：洗涤服务商与纺织零售商不同于制造商。关键在自述生产、织造、缝制和出厂供货，而非单纯清洗或销售。
- **我们解决的问题**：生产到交付及使用周期内的布草身份与流转追踪。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/; https://ubisolutions.net/fr/solution/ubi-laundry/
- **官网明确出现的客户 / 合作方**：TGL / Tissus Gisèle
- **置信度**：`inferred`
- **推断理由**：官网 TGL 布草追踪客户案例支持纺织生产环节，但没有将纺织制造单设为独立行业入口。

### 医疗与公共服务

#### 医院与大型医疗机构 | `hospitals_healthcare`

- **法文名**：Hôpitaux et établissements de santé
- **英文名**：Hospitals and healthcare providers
- **所属大类**：医疗与公共服务
- **业务描述（客户视角）**：我们运营医院、诊疗中心或综合医疗机构，为患者提供医疗、护理和住院服务。简介通常出现科室、临床服务、医护团队和医疗设施。
- **典型 LinkedIn 行业**：Hospitals and Health Care; Medical Practices
- **正向关键词（FR）**：hôpital; établissement de santé; centre hospitalier; soins aux patients; services hospitaliers; pharmacie hospitalière; équipement médical
- **正向关键词（EN）**：hospital; healthcare provider; medical center; patient care; clinical services; hospital pharmacy; healthcare facilities
- **正向关键词（ES）**：hospital; centro sanitario; atención al paciente; servicios hospitalarios; farmacia hospitalaria; centros médicos; equipamiento hospitalario
- **易混淆的反例 / 区分方法**：医疗器械制造商、诊所软件商与药品批发商不等于运营医院。应以实际提供诊疗和医院管理服务为主。
- **我们解决的问题**：病区设备定位、药品及耗材补货、医院布草盘点、资产寻回与库存准确性。
- **对应业务线（主次）**：geoloc（主）; rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/hospital-assets-tracking/; https://ubisolutions.net/fr/solution/e-kanban-optimise-la-gestion-des-medicaments-en-pharmacie/; https://ubisolutions.net/fr/solution/ubi-laundry/; https://ubisolutions.net/it/products/etichette-elettroniche/
- **官网明确出现的客户 / 合作方**：AP-HP
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 零售与分销

#### 服装与鞋履零售连锁 | `apparel_footwear_retail`

- **法文名**：Commerce de détail de vêtements et chaussures
- **英文名**：Apparel and footwear retail
- **所属大类**：零售与分销
- **业务描述（客户视角）**：我们面向消费者销售服装、鞋履和时尚配饰，并经营实体门店或线上零售渠道。企业简介常强调品牌、商品系列、门店网络与全渠道销售。
- **典型 LinkedIn 行业**：Retail Apparel and Fashion; Retail
- **正向关键词（FR）**：enseigne de mode; vente de vêtements; chaussures; magasins; distribution textile; prêt-à-porter; omnicanal
- **正向关键词（EN）**：fashion retailer; apparel retail; footwear; retail stores; clothing chain; ready-to-wear; omnichannel
- **正向关键词（ES）**：cadena de moda; venta de ropa; calzado; tiendas; distribución textil; prêt-à-porter; omnicanal
- **易混淆的反例 / 区分方法**：服装设计软件、服饰设备商与仅生产服装的代工厂不等于零售运营商。需存在面向消费者的门店或电商销售。
- **我们解决的问题**：门店与仓库周转箱追踪、库存差异、调拨、补货和盘点效率。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/gemo-tracabilite-rfid-des-supports-logistiques/; https://ubisolutions.net/fr/solution/ubi-retail-boost/
- **官网明确出现的客户 / 合作方**：Gémo
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 专业零售与电商 | `specialty_retail_ecommerce`

- **法文名**：Commerce spécialisé et e-commerce
- **英文名**：Specialty retail and e-commerce
- **所属大类**：零售与分销
- **业务描述（客户视角）**：我们在特定商品品类开展零售或电商业务，向个人或企业客户销售实物商品。公司简介常列出所售商品、在线商店、库存管理和订单履约。
- **典型 LinkedIn 行业**：Retail; Internet Marketplace Platforms
- **正向关键词（FR）**：commerce spécialisé; e-commerce; vente en ligne; boutique spécialisée; gestion des stocks; détaillant; catalogue produits
- **正向关键词（EN）**：specialty retail; ecommerce; online store; specialist retailer; inventory management; product catalog; direct sales
- **正向关键词（ES）**：comercio especializado; comercio electrónico; venta en línea; tienda especializada; gestión de existencias; minorista; catálogo de productos
- **易混淆的反例 / 区分方法**：提供电商平台软件、营销服务或支付服务的公司不等于零售商。需自有或经营商品销售活动及库存。
- **我们解决的问题**：零售库存可见性、线上超卖、商品盘点、仓储出入库和订单差错。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/west-cheval-optimiser-gestion-stocks-inventaires/; https://ubisolutions.net/fr/usecase/wonderbox-assurer-inventaire-precis-stocks-coffrets/; https://ubisolutions.net/fr/solution/ubi-retail-boost/
- **官网明确出现的客户 / 合作方**：West Cheval; Wonderbox
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 食品超市与杂货连锁 | `grocery_supermarket_chains`

- **法文名**：Supermarchés et distribution alimentaire
- **英文名**：Grocery and supermarket chains
- **所属大类**：零售与分销
- **业务描述（客户视角）**：我们经营超市、杂货店或食品连锁零售网络，向消费者提供食品和日用品。公司简介常强调门店、食品零售、配送中心及供应链。
- **典型 LinkedIn 行业**：Retail Groceries; Retail
- **正向关键词（FR）**：supermarché; grande distribution; distribution alimentaire; magasins alimentaires; épicerie; chaîne de supermarchés; centrale logistique
- **正向关键词（EN）**：supermarket; grocery retail; food distribution; grocery stores; grocery chain; food retail; distribution center
- **正向关键词（ES）**：supermercado; distribución alimentaria; tiendas de alimentación; tienda de comestibles; cadena de supermercados; comercio de alimentos; centro logístico
- **易混淆的反例 / 区分方法**：仅经营食品生产或食品批发的企业不等于超市零售网络。需有面向消费者的杂货或食品门店。
- **我们解决的问题**：可循环周转箱、托盘和配送资产的追踪、门店与配送中心之间的库存损失。
- **对应业务线（主次）**：rfid（主）; geoloc（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 建筑与重资产运营

#### 建筑施工与工程承包商 | `construction_contractors`

- **法文名**：Entreprises de BTP et entrepreneurs généraux
- **英文名**：Construction contractors
- **所属大类**：建筑与重资产运营
- **业务描述（客户视角）**：我们承担建筑工程、基础设施项目或公共工程施工，管理施工场地、人员和项目设备。公司简介常出现工程总包、土木工程、工地施工和项目交付。
- **典型 LinkedIn 行业**：Construction; Civil Engineering
- **正向关键词（FR）**：entreprise de BTP; chantier; travaux publics; génie civil; construction; entrepreneur général; gestion de chantier
- **正向关键词（EN）**：construction contractor; jobsite; public works; civil engineering; building projects; general contractor; site management
- **正向关键词（ES）**：empresa constructora; obra; obras públicas; ingeniería civil; construcción; contratista general; gestión de obras
- **易混淆的反例 / 区分方法**：仅销售工程机械、建筑材料或BIM软件的供应商不是施工承包商。需要直接承接并执行工程项目。
- **我们解决的问题**：工地设备找回、机具调度、资产丢失、施工车辆移动与使用率。
- **对应业务线（主次）**：geoloc（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-construction-tracking-solution-de-geolocalisation-pour-le-btp/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/; https://ubisolutions.net/fr/solution/assets-tracking/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 工程设备与施工机械租赁 | `construction_equipment_rental`

- **法文名**：Location de matériels et équipements de chantier
- **英文名**：Construction equipment rental
- **所属大类**：建筑与重资产运营
- **业务描述（客户视角）**：我们采购、管理并出租施工机械或工程装备，向承包商和工地客户交付设备。公司简介通常提到租赁机队、工程机械、租期管理和设备维护。
- **典型 LinkedIn 行业**：Equipment Rental Services; Construction; Machinery Manufacturing
- **正向关键词（FR）**：location de matériel BTP; parc machines; engins de chantier; location d’équipements; matériel de construction; flotte de machines; maintenance des engins
- **正向关键词（EN）**：construction equipment rental; equipment fleet; plant hire; heavy machinery rental; machinery hire; construction machines; fleet maintenance
- **正向关键词（ES）**：alquiler de maquinaria; parque de máquinas; maquinaria de obra; alquiler de equipos; maquinaria de construcción; flota de máquinas; mantenimiento de equipos
- **易混淆的反例 / 区分方法**：只生产或经销工程机械并不等于租赁运营商。应确认有自营设备资产及租赁服务。
- **我们解决的问题**：租赁机队位置、设备回收、跨工地调度、防盗、利用率及异常移动告警。
- **对应业务线（主次）**：geoloc（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/batamat-geolocalisation-des-equipements-btp/; https://ubisolutions.net/fr/solution/ubi-construction-tracking-solution-de-geolocalisation-pour-le-btp/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/
- **官网明确出现的客户 / 合作方**：Batamat
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 物流、运输与供应链

#### 第三方物流与仓储运营商 | `third_party_logistics`

- **法文名**：Prestataires logistiques et entrepôts 3PL
- **英文名**：Third-party logistics and warehousing
- **所属大类**：物流、运输与供应链
- **业务描述（客户视角）**：我们为其他企业提供仓储、库存管理、订单处理或物流外包服务。公司简介经常强调物流平台、配送中心、仓库运营与供应链执行。
- **典型 LinkedIn 行业**：Transportation, Logistics, Supply Chain and Storage; Warehousing and Storage
- **正向关键词（FR）**：prestataire logistique; entreposage; logistique contractuelle; 3PL; préparation de commandes; plateforme logistique; gestion d’entrepôt
- **正向关键词（EN）**：logistics provider; warehousing; contract logistics; 3PL; order fulfillment; distribution center; warehouse operations
- **正向关键词（ES）**：operador logístico; almacenamiento; logística contractual; 3PL; preparación de pedidos; centro de distribución; gestión de almacenes
- **易混淆的反例 / 区分方法**：只销售仓库软件/WMS的厂商或自建仓库的普通零售商不自动成为 3PL。重点是为第三方客户运营仓储和物流。
- **我们解决的问题**：周转容器、托盘、仓内库存及跨节点流动的识别、错配和损失。
- **对应业务线（主次）**：rfid（主）; geoloc（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/es/
- **官网明确出现的客户 / 合作方**：DHL France
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 货运与运输公司 | `freight_transport`

- **法文名**：Transporteurs de marchandises
- **英文名**：Freight transportation companies
- **所属大类**：物流、运输与供应链
- **业务描述（客户视角）**：我们为客户承担货物运输、车辆调度或干线与短途运输服务。公司简介通常列出运输车队、货运线路、道路运输和交付保障。
- **典型 LinkedIn 行业**：Truck Transportation; Freight and Package Transportation
- **正向关键词（FR）**：transport de marchandises; transport routier; flotte de camions; transporteur; fret; livraison de marchandises; transport logistique
- **正向关键词（EN）**：freight transportation; road haulage; truck fleet; carrier; freight; cargo delivery; trucking services
- **正向关键词（ES）**：transporte de mercancías; transporte por carretera; flota de camiones; transportista; carga; entrega de mercancías; transporte logístico
- **易混淆的反例 / 区分方法**：货运经纪软件或运输设备销售商不等于实际承运人。需有承担货运或运营承运网络的自述。
- **我们解决的问题**：在途货物安全、车货关联、异常开启告警与运输资产可见性。
- **对应业务线（主次）**：geoloc（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/connected-lock/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/solution/assets-tracking/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 邮政与包裹网络 | `postal_parcel_network`

- **法文名**：Réseaux postaux et de colis
- **英文名**：Postal and parcel networks
- **所属大类**：物流、运输与供应链
- **业务描述（客户视角）**：我们提供包裹、邮件或快递网络运营，建设分拣中心并向网点或收件人分发包裹。公司简介通常强调分拣、邮政网络、末端配送与快件处理。
- **典型 LinkedIn 行业**：Freight and Package Transportation; Postal Services
- **正向关键词（FR）**：colis; réseau postal; tri postal; centre de tri; messagerie express; livraison de colis; distribution postale
- **正向关键词（EN）**：parcel delivery; postal network; mail sorting; sorting hub; express parcels; last-mile delivery; postal distribution
- **正向关键词（ES）**：paquetería; red postal; clasificación postal; centro de clasificación; mensajería exprés; entrega de paquetes; distribución postal
- **易混淆的反例 / 区分方法**：一般 3PL 不一定经营邮政或包裹分拣网络。关键是全国或多节点分拣、投递或邮政运营活动。
- **我们解决的问题**：包裹分拣容器与路由箱循环追踪、节点盘点和容器丢失。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-supply-chain-optimisation/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **官网明确出现的客户 / 合作方**：Viaposte; Le Groupe La Poste
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 工业制造

#### 工业制造企业 | `industrial_manufacturing`

- **法文名**：Entreprises manufacturières industrielles
- **英文名**：Industrial manufacturing companies
- **所属大类**：工业制造
- **业务描述（客户视角）**：我们经营生产工厂，将原料或零部件加工成工业产品并向客户供货。简介通常强调生产线、装配车间、工业流程及工厂物流。
- **典型 LinkedIn 行业**：Manufacturing; Industrial Machinery Manufacturing
- **正向关键词（FR）**：usine; production industrielle; assemblage; fabrication; site de production; chaîne de production; atelier industriel
- **正向关键词（EN）**：factory; industrial production; assembly; manufacturing; production plant; production line; industrial workshop
- **正向关键词（ES）**：fábrica; producción industrial; ensamblaje; fabricación; planta de producción; línea de producción; taller industrial
- **易混淆的反例 / 区分方法**：纯工业咨询、机器人集成商、设备销售商不应因服务制造业而归入制造企业。需要自营产品制造活动。
- **我们解决的问题**：在制品、物料、成品出入库与工厂资产追踪，提高生产物流可视性。
- **对应业务线（主次）**：rfid（主）; geoloc（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/en/products/rfid-tags/; https://ubisolutions.net/fr/products/tags-rfid/; https://ubisolutions.net/fr/usecase/faurecia-controle-et-suivi-des-flux-de-produits-entrants-et-sortants/; https://ubisolutions.net/fr/solution/assets-tracking/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 汽车与零部件制造 | `automotive_manufacturing`

- **法文名**：Construction automobile et équipementiers
- **英文名**：Automotive manufacturing and suppliers
- **所属大类**：工业制造
- **业务描述（客户视角）**：我们生产汽车、汽车模块、结构件或车用零部件，运营工厂和工业供应链。简介通常写明汽车工业、整车或零部件生产及 OEM 或 Tier 1 供货。
- **典型 LinkedIn 行业**：Motor Vehicle Manufacturing; Motor Vehicle Parts Manufacturing
- **正向关键词（FR）**：industrie automobile; équipementier automobile; pièces automobiles; constructeur automobile; usine automobile; assemblage automobile; sous-traitant automobile
- **正向关键词（EN）**：automotive industry; automotive supplier; auto parts; vehicle manufacturer; car factory; automotive assembly; tier one supplier
- **正向关键词（ES）**：industria automotriz; proveedor automotriz; autopartes; fabricante de automóviles; planta automotriz; ensamblaje automotriz; proveedor de primer nivel
- **易混淆的反例 / 区分方法**：汽车经销商、售后维修网络不等于汽车制造商。需从描述中确认工厂制造活动及零部件生产。
- **我们解决的问题**：汽车零部件与包装器具追踪、工厂出入厂物流、订单链路和库存控制。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/faurecia-controle-et-suivi-des-flux-de-produits-entrants-et-sortants/; https://ubisolutions.net/fr/solution/assets-tracking/
- **官网明确出现的客户 / 合作方**：Faurecia
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 航空航天制造与供应链 | `aerospace_manufacturing`

- **法文名**：Industrie aéronautique et aérospatiale
- **英文名**：Aerospace manufacturing
- **所属大类**：工业制造
- **业务描述（客户视角）**：我们设计或生产航空航天结构、发动机、系统或零部件，向飞机或航天产业链交付产品。公司通常介绍航空制造、工业生产和零部件质量流程。
- **典型 LinkedIn 行业**：Aviation and Aerospace Component Manufacturing; Aviation & Aerospace
- **正向关键词（FR）**：industrie aéronautique; fabrication aéronautique; aérospatial; pièces aéronautiques; équipementier aéronautique; chaîne d’assemblage; composants aéronautiques
- **正向关键词（EN）**：aerospace manufacturing; aircraft components; aviation manufacturing; aerospace supplier; aircraft parts; assembly line; aeronautical equipment
- **正向关键词（ES）**：industria aeroespacial; fabricación aeronáutica; componentes aeronáuticos; proveedor aeroespacial; piezas de avión; línea de montaje; equipamiento aeronáutico
- **易混淆的反例 / 区分方法**：航空公司与机场运营方不是航空制造商。应出现制造航空产品或工业配件的描述。
- **我们解决的问题**：关键工具、设备、零部件位置与工业资产的追踪和盘点。
- **对应业务线（主次）**：geoloc（主）; rfid（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/assets-tracking/; https://ubisolutions.net/fr/solution/ubi-tools-tracking-pour-tracer-et-geolocaliser-tout-votre-outillage-et-equipements/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 交通与基础设施

#### 铁路运营与基础设施企业 | `rail_transport_operators`

- **法文名**：Opérateurs ferroviaires et infrastructures
- **英文名**：Rail transport and infrastructure operators
- **所属大类**：交通与基础设施
- **业务描述（客户视角）**：我们运营铁路运输服务、轨道基础设施或铁路资产，负责线路、车站及相关设备。公司简介常出现铁路运输、轨道网络、维护和基础设施运营。
- **典型 LinkedIn 行业**：Rail Transportation; Ground Passenger Transportation
- **正向关键词（FR）**：opérateur ferroviaire; réseau ferré; transport ferroviaire; infrastructure ferroviaire; maintenance des voies; matériel ferroviaire; exploitation ferroviaire
- **正向关键词（EN）**：rail operator; rail network; railway transport; rail infrastructure; track maintenance; rolling stock; railway operations
- **正向关键词（ES）**：operador ferroviario; red ferroviaria; transporte ferroviario; infraestructura ferroviaria; mantenimiento de vías; material rodante; explotación ferroviaria
- **易混淆的反例 / 区分方法**：单纯生产模型火车、轨道设备或铁路工程咨询的企业不等于铁路运营方。看是否实际运营铁路或管理轨道资产。
- **我们解决的问题**：铁路现场机具和基础设施资产位置、维护设备盘点、遗失预警。
- **对应业务线（主次）**：geoloc（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/assets-tracking/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **官网明确出现的客户 / 合作方**：SNCF
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 文化、活动与场馆

#### 活动、会展与演出服务 | `event_services`

- **法文名**：Prestataires événementiels
- **英文名**：Event production and services
- **所属大类**：文化、活动与场馆
- **业务描述（客户视角）**：我们策划、执行并为展会、演出、会议或大型活动提供现场服务。简介通常强调活动制作、展会组织、灯光舞台、现场运营或活动物料。
- **典型 LinkedIn 行业**：Events Services; Entertainment Providers
- **正向关键词（FR）**：événementiel; organisation d’événements; salon professionnel; spectacle; production événementielle; matériel événementiel; exposition
- **正向关键词（EN）**：event services; event production; trade shows; live events; event management; event equipment; exhibitions
- **正向关键词（ES）**：servicios de eventos; organización de eventos; feria comercial; espectáculos; producción de eventos; material para eventos; exposiciones
- **易混淆的反例 / 区分方法**：只销售 AV 设备或活动管理 SaaS 的供应商不一定承接现场活动。需明确活动执行、租赁道具或场馆运营业务。
- **我们解决的问题**：活动物料、布展器材和现场资产多场次复用、跨场馆位置与防遗失。
- **对应业务线（主次）**：geoloc（主）; rfid（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-events-pour-assurer-la-tracabilite-de-vos-actifs/; https://ubisolutions.net/fr/usecase/optimisation-des-flux-logistiques/
- **官网明确出现的客户 / 合作方**：无（所列页面仅提供行业/场景证据）
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 博物馆、文化场馆与机构 | `cultural_institutions_venues`

- **法文名**：Institutions et lieux culturels
- **英文名**：Cultural institutions and venues
- **所属大类**：文化、活动与场馆
- **业务描述（客户视角）**：我们经营博物馆、展览设施或文化遗产场馆，提供公众展览及文化活动。公司简介通常出现展览、馆藏、文化活动、参观体验和场馆运营。
- **典型 LinkedIn 行业**：Museums, Historical Sites, and Zoos; Performing Arts
- **正向关键词（FR）**：musée; institution culturelle; lieu culturel; exposition; patrimoine; collections; gestion de site culturel
- **正向关键词（EN）**：museum; cultural institution; cultural venue; exhibitions; heritage; collections; venue operations
- **正向关键词（ES）**：museo; institución cultural; espacio cultural; exposición; patrimonio; colecciones; gestión de espacios culturales
- **易混淆的反例 / 区分方法**：展陈施工公司和艺术品软件服务商不等于文化机构。必须确认实际运营文化场馆、活动或馆藏。
- **我们解决的问题**：展览物料与物流容器跨场馆管理、展陈资产调拨和盘点。
- **对应业务线（主次）**：rfid（主）; geoloc（辅）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/optimisation-des-flux-logistiques/; https://ubisolutions.net/fr/solution/ubi-events-pour-assurer-la-tracabilite-de-vos-actifs/
- **官网明确出现的客户 / 合作方**：GrandPalaisRmn
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### 食品与资源

#### 食品及农产品加工 | `food_processing`

- **法文名**：Industries agroalimentaires
- **英文名**：Food and agricultural processing
- **所属大类**：食品与资源
- **业务描述（客户视角）**：我们经营食品生产、肉类或农产品加工厂，将原料制成可销售食品。简介常提到食品加工、包装、卫生质量控制和供应链溯源。
- **典型 LinkedIn 行业**：Food and Beverage Manufacturing; Food Production
- **正向关键词（FR）**：industries agroalimentaires; transformation alimentaire; usine alimentaire; production de viande; conditionnement alimentaire; traçabilité alimentaire; produits agricoles
- **正向关键词（EN）**：food processing; food manufacturing; food factory; meat processing; food packaging; food traceability; agricultural products
- **正向关键词（ES）**：industria alimentaria; procesamiento de alimentos; fábrica de alimentos; procesamiento cárnico; envasado alimentario; trazabilidad alimentaria; productos agrícolas
- **易混淆的反例 / 区分方法**：纯餐饮门店与食品营销咨询并非食品加工厂。要有对原料开展加工、包装或工业生产的描述。
- **我们解决的问题**：食品批次、畜禽产品、容器从加工到配送的追溯，食品安全与召回准确性。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/ubi-food-supply-chain-tracabilite-alimentaire/; https://ubisolutions.net/fr/solution/ubi-intelligent-containers/; https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/
- **官网明确出现的客户 / 合作方**：Sénécal; 3A SOLUTIONS SAS
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

#### 饮料与瓶装水生产 | `beverage_bottling`

- **法文名**：Production de boissons et embouteillage
- **英文名**：Beverage and bottled water production
- **所属大类**：食品与资源
- **业务描述（客户视角）**：我们生产瓶装水、饮料或其他包装饮品，运营灌装和包装生产线。企业简介常出现水源、饮料生产、灌装和出厂物流。
- **典型 LinkedIn 行业**：Beverage Manufacturing; Food and Beverage Manufacturing
- **正向关键词（FR）**：eau embouteillée; usine d’embouteillage; boisson; production de boissons; ligne de conditionnement; bouteille; fabricant de boissons
- **正向关键词（EN）**：bottled water; bottling plant; beverages; drink production; packaging line; bottles; beverage manufacturer
- **正向关键词（ES）**：agua embotellada; planta embotelladora; bebidas; producción de bebidas; línea de envasado; botellas; fabricante de bebidas
- **易混淆的反例 / 区分方法**：饮料零售商、酒吧和瓶子制造商不等于饮料灌装生产商。需有饮料生产或灌装作业。
- **我们解决的问题**：灌装过程的追溯、箱包和货物装车核验，防止错发及批次信息断链。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/vos-success-stories-nous-inspirent/; https://ubisolutions.net/fr/solution/ubi-food-supply-chain-tracabilite-alimentaire/
- **官网明确出现的客户 / 合作方**：Eaux de Zilia
- **置信度**：`inferred`
- **推断理由**：官网列出 Eaux de Zilia 的具体应用案例，但没有把瓶装水/饮料灌装独立列为目标行业入口。

#### 工业与危险废物处理 | `hazardous_waste_management`

- **法文名**：Traitement des déchets industriels dangereux
- **英文名**：Industrial and hazardous waste management
- **所属大类**：食品与资源
- **业务描述（客户视角）**：我们收集、回收、处理或处置工业危险废物，运营专业处理设施。企业简介常提到废物管理、化学废物、回收和监管合规。
- **典型 LinkedIn 行业**：Environmental Services; Waste Treatment and Disposal
- **正向关键词（FR）**：déchets dangereux; gestion des déchets industriels; traitement chimique; recyclage industriel; déchets chimiques; centre de traitement; traçabilité des déchets
- **正向关键词（EN）**：hazardous waste; industrial waste management; chemical treatment; industrial recycling; chemical waste; waste treatment plant; waste traceability
- **正向关键词（ES）**：residuos peligrosos; gestión de residuos industriales; tratamiento químico; reciclaje industrial; residuos químicos; planta de tratamiento; trazabilidad de residuos
- **易混淆的反例 / 区分方法**：环保顾问或废物管理软件公司不等于实际收集和处理危险废物的运营方。需有废物处理设施或作业。
- **我们解决的问题**：危险废物容器和储位定位、危险区域追踪、废物流转证据与合规核验。
- **对应业务线（主次）**：geoloc（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/suez-tracabilite-des-dechets-dangereux/; https://ubisolutions.net/fr/solution/assets-tracking/
- **官网明确出现的客户 / 合作方**：Suez; Suez IWS Chemical
- **置信度**：`explicit`
- **推断理由**：不适用（官网行业或应用有明确证据）

### IT 资产密集型组织

#### 电信运营商 | `telecommunications_operators`

- **法文名**：Opérateurs de télécommunications
- **英文名**：Telecommunications operators
- **所属大类**：IT 资产密集型组织
- **业务描述（客户视角）**：我们运营通信网络，为家庭或企业提供电话、互联网或数据连接服务。公司简介通常描述电信服务、网络基础设施、宽带、移动通信和数据中心。
- **典型 LinkedIn 行业**：Telecommunications; Wireless Services
- **正向关键词（FR）**：opérateur télécom; réseau télécom; télécommunications; connectivité; réseau mobile; fournisseur internet; infrastructure réseau
- **正向关键词（EN）**：telecom operator; telecom network; telecommunications; connectivity; mobile network; internet service provider; network infrastructure
- **正向关键词（ES）**：operador de telecomunicaciones; red de telecomunicaciones; telecomunicaciones; conectividad; red móvil; proveedor de internet; infraestructura de red
- **易混淆的反例 / 区分方法**：通信设备制造商及数据中心集成商不等于电信网络运营商。需提供并实际运营通信服务或网络。
- **我们解决的问题**：机房服务器和网络资产快速盘点、设备在位核验与 IT 基础设施清册。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/solution/serveurs-archives-inventaires-rapides/; https://ubisolutions.net/fr/usecase/banque-de-france-linventaire-des-serveurs-informatiques/
- **官网明确出现的客户 / 合作方**：Orange
- **置信度**：`inferred`
- **推断理由**：官网提及 Orange 数据中心的服务器盘点项目，但电信业本身并未被列为独立解决方案行业。

#### 银行与金融机构 | `financial_institutions`

- **法文名**：Banques et institutions financières
- **英文名**：Banking and financial institutions
- **所属大类**：IT 资产密集型组织
- **业务描述（客户视角）**：我们提供银行、货币、信贷或其他金融服务，并运营支持业务的 IT 基础设施。公司简介通常出现银行金融、支付、金融服务和网点或数据中心。
- **典型 LinkedIn 行业**：Banking; Financial Services
- **正向关键词（FR）**：banque; institution financière; services bancaires; secteur financier; établissements financiers; système bancaire; services financiers
- **正向关键词（EN）**：bank; financial institution; banking services; financial sector; banking organization; banking systems; financial services
- **正向关键词（ES）**：banco; institución financiera; servicios bancarios; sector financiero; entidades financieras; sistema bancario; servicios financieros
- **易混淆的反例 / 区分方法**：金融咨询、金融科技软件开发商和银行设备供应商不等于经营金融服务的银行或金融机构。
- **我们解决的问题**：服务器与机房设备清单、重要 IT 资产盘点、资产管理的准确性与审计。
- **对应业务线（主次）**：rfid（主）; ubi_cloud（辅）
- **规模门槛**：无
- **官网证据 URL**：https://ubisolutions.net/fr/usecase/banque-de-france-linventaire-des-serveurs-informatiques/; https://ubisolutions.net/fr/solution/serveurs-archives-inventaires-rapides/
- **官网明确出现的客户 / 合作方**：Banque de France
- **置信度**：`inferred`
- **推断理由**：官网有 Banque de France 的服务器盘点案例，但金融业未被作为正式独立行业入口。

## 非目标或需要排除的类型

| 类型 | LinkedIn 公司简介中的典型识别信号 | 区分与排除规则 |
|---|---|---|
| 直接竞品 | 提供 RFID/RTLS/GPS/BLE/LoRa 追踪平台、资产定位 SaaS，销售整套追踪解决方案 | 若主营是向客户销售同类技术解决方案而非运营被追踪的资产，排除或独立标记竞争对手 |
| RFID / IoT 硬件厂商 | 生产或销售 reader、antenna、RFID tag、beacon、gateway、tracker、传感器 | 不因出现 `RFID`、`asset tracking` 等产品关键词判为使用方 |
| 系统集成商 / 软件实施商 | system integration、intégration RFID、déploiement IoT、intégrateur | 自身业务是替他人部署、集成或维护方案，不属于最终行业客户 |
| 经销商 / VAR / 批发代理 | distributeur、revendeur、reseller、value-added reseller、grossiste technologique | 销售第三方设备或技术，不应直接按其客户行业分类 |
| IT / 供应链咨询公司 | conseil、consulting、digital transformation、supply chain consulting | 咨询和方法论不是仓储、生产、医疗或运输运营活动 |
| WMS / ERP / SaaS 软件商 | warehouse management software、ERP vendor、logistics SaaS | 帮客户管理业务并不表示自身经营仓库或物流网络 |
| 行业设备制造 / 配套商 | fabricant de machines à laver、équipements BTP、matériel médical、AV equipment | 不把洗涤设备商归为洗衣房，不把设备销售商归为施工/医院/活动运营商 |
| 仅拥有内部资产的跨行业公司 | 只提 tracking、inventory、fleet，却不明确主营业务 | 不凭技术需求词强行归类，先按真实主营业务分类，必要时给 `unknown` |

## 待人工确认的问题

1. 零售三类（服装鞋履、专业零售/电商、超市）是互斥、层级关系还是允许多标签？
2. 第三方物流、货运和邮政包裹网络如何设优先级？混合型物流集团是否多标签？
3. 酒店、医院、工业洗衣房和布草制造商在同一布草链条出现时，应按谁是实际购买主体确定标签。
4. `industrial_manufacturing` 是否仅作兜底类，如何与汽车和航空航天的行业细分类去重？
5. 对 TGL、Eaux de Zilia、Orange、Banque de France 四个 inferred 细分，是否有足够的商业覆盖面长期保留？
6. 官网 robots.txt 的真实规则、页面是否允许抓取以及请求时间戳尚未验证。LinkedIn 行业枚举名需要技术复核。
