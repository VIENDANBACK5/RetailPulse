/**
 * DATAOPS & MLOPS CLIENT-SIDE ENGINE
 * Quản trị vòng đời dữ liệu và mô hình máy học:
 * 1. Data Profiling & Validation (Phân tích lỗi, missing values, quality score)
 * 2. MLOps Model Registry (So sánh phiên bản, Silhouette, Inertia, Promote)
 * 3. Hyperparameter Tuning (K-Means K, Analysis Window, RFM Weights)
 * 4. Data Activation & CRM Dynamic Webhook/API Generator
 */

const STORAGE_KEY_REGISTRY = 'retailpulse_model_registry_v1';

// Default Model Versions
export const DEFAULT_MODEL_VERSIONS = [
  {
    version: "v1.0-baseline",
    name: "K-Means RFM Chuẩn Baseline",
    algorithm: "K-Means (log1p + StandardScale)",
    k_clusters: 4,
    analysis_window: "12 Tháng (Toàn kỳ)",
    rfm_weights: { r: 0.33, f: 0.33, m: 0.34 },
    silhouette_score: 0.3088,
    inertia: 1420.5,
    reconstruction_mse: null,
    status: "Archived",
    created_at: "2026-09-15 10:00:00",
    notes: "Mô hình phân cụm cơ sở theo đề cương môn học."
  },
  {
    version: "v1.1-rfm-weighted",
    name: "K-Means RFM Trọng Số Doanh Thu",
    algorithm: "K-Means (Weighted RFM)",
    k_clusters: 4,
    analysis_window: "12 Tháng (Toàn kỳ)",
    rfm_weights: { r: 0.20, f: 0.40, m: 0.40 },
    silhouette_score: 0.3145,
    inertia: 1380.2,
    reconstruction_mse: null,
    status: "Archived",
    created_at: "2026-09-18 14:30:00",
    notes: "Tăng trọng số Monetary & Frequency để tách biệt cụm VIP."
  },
  {
    version: "v2.0-deep-autoencoder",
    name: "Deep Autoencoder Latent Space 3D",
    algorithm: "MLP Autoencoder (8->16->3->16->8)",
    k_clusters: 4,
    analysis_window: "12 Tháng (Toàn kỳ)",
    rfm_weights: { r: 0.33, f: 0.33, m: 0.34 },
    silhouette_score: 0.3214,
    inertia: 940.8,
    reconstruction_mse: 0.0120,
    status: "Active Serving",
    created_at: "2026-09-22 09:15:00",
    notes: "Bottleneck Layer trích xuất biểu diễn phi tuyến tính Z; +4.1% Silhouette."
  }
];

// 1. Data Profiling Engine
export function profileCsvContent(csvText, fileName = "Uploaded_Batch.csv") {
  const lines = csvText.trim().split(/\r\n|\n/).filter(line => line.trim().length > 0);
  if (lines.length <= 1) {
    return {
      fileName,
      totalRows: 0,
      validRows: 0,
      invalidRows: 0,
      qualityScore: 0,
      status: "EMPTY"
    };
  }

  const header = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
  const dataLines = lines.slice(1);
  const totalRows = dataLines.length;

  let cancelledCount = 0;
  let missingCustCount = 0;
  let negQtyCount = 0;
  let invalidPriceCount = 0;
  let validDatetimeCount = 0;

  // Identify column indices
  const invIdx = header.findIndex(h => /invoice/i.test(h) && !/date/i.test(h));
  const qtyIdx = header.findIndex(h => /qty|quantity/i.test(h));
  const priceIdx = header.findIndex(h => /price|unitprice|amount/i.test(h));
  const custIdx = header.findIndex(h => /customer|cust/i.test(h));
  const dateIdx = header.findIndex(h => /date|time/i.test(h));

  let validRows = 0;

  dataLines.forEach(line => {
    // Simple CSV parser handling basic commas
    const cols = line.split(',').map(c => c.trim().replace(/^["']|["']$/g, ''));
    let isInvalid = false;

    // Cancelled invoice check
    if (invIdx !== -1 && cols[invIdx] && cols[invIdx].toUpperCase().startsWith('C')) {
      cancelledCount++;
      isInvalid = true;
    }

    // Missing Customer ID
    if (custIdx !== -1 && (!cols[custIdx] || cols[custIdx].length === 0 || cols[custIdx] === 'null')) {
      missingCustCount++;
      isInvalid = true;
    }

    // Negative / Zero Quantity
    if (qtyIdx !== -1) {
      const q = parseFloat(cols[qtyIdx]);
      if (isNaN(q) || q <= 0) {
        negQtyCount++;
        isInvalid = true;
      }
    }

    // Invalid / Zero Price
    if (priceIdx !== -1) {
      const p = parseFloat(cols[priceIdx]);
      if (isNaN(p) || p <= 0) {
        invalidPriceCount++;
        isInvalid = true;
      }
    }

    // Datetime parse test
    if (dateIdx !== -1 && cols[dateIdx]) {
      const dt = Date.parse(cols[dateIdx]);
      if (!isNaN(dt)) {
        validDatetimeCount++;
      }
    }

    if (!isInvalid) {
      validRows++;
    }
  });

  const invalidRows = totalRows - validRows;
  const validityPct = ((validRows / totalRows) * 100).toFixed(1);
  const completenessPct = (100 - (missingCustCount / totalRows * 100)).toFixed(1);
  const dateParsePct = dateIdx !== -1 ? ((validDatetimeCount / totalRows) * 100).toFixed(1) : 100.0;

  const qualityScore = Math.round(
    0.45 * parseFloat(validityPct) + 0.35 * parseFloat(completenessPct) + 0.2 * parseFloat(dateParsePct)
  );

  return {
    fileName,
    totalRows,
    validRows,
    invalidRows,
    validityPct,
    completenessPct,
    dateParsePct,
    invalidBreakdown: {
      cancelledOrders: cancelledCount,
      missingCustomerId: missingCustCount,
      negativeOrZeroQty: negQtyCount,
      invalidOrZeroPrice: invalidPriceCount
    },
    qualityScore,
    status: qualityScore >= 90 ? "EXCELLENT" : (qualityScore >= 70 ? "GOOD" : "NEEDS_CLEANING")
  };
}

// 2. Model Registry Storage & Versioning
export function getModelRegistry() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_REGISTRY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn('LocalStorage error, using default model registry', e);
  }
  return {
    activeVersion: "v2.0-deep-autoencoder",
    versions: [...DEFAULT_MODEL_VERSIONS]
  };
}

export function saveModelRegistry(registry) {
  try {
    localStorage.setItem(STORAGE_KEY_REGISTRY, JSON.stringify(registry));
  } catch (e) {
    console.error('Failed to save registry', e);
  }
}

export function promoteModelVersion(versionId) {
  const reg = getModelRegistry();
  reg.versions.forEach(v => {
    if (v.version === versionId) {
      v.status = "Active Serving";
      reg.activeVersion = versionId;
    } else if (v.status === "Active Serving") {
      v.status = "Archived";
    }
  });
  saveModelRegistry(reg);
  return reg;
}

// 3. Hyperparameter Retraining Engine
export function trainCustomModel(hyperparams) {
  const { k = 4, window = "12_months", weightR = 0.33, weightF = 0.33, weightM = 0.34, algorithm = "kmeans" } = hyperparams;
  const reg = getModelRegistry();

  // Theoretical heuristic calculation of Silhouette and Inertia based on parameters
  let silBase = 0.3088;
  let inertiaBase = 1420.5;

  if (algorithm === "autoencoder") {
    silBase = 0.3214;
    inertiaBase = 940.8;
  }

  // Effect of K
  if (k === 3) {
    silBase -= 0.015;
    inertiaBase += 280;
  } else if (k === 5) {
    silBase += 0.004;
    inertiaBase -= 190;
  } else if (k === 6) {
    silBase -= 0.010;
    inertiaBase -= 310;
  }

  // Effect of balanced weighting
  const weightVar = Math.abs(weightR - 0.33) + Math.abs(weightF - 0.33) + Math.abs(weightM - 0.34);
  silBase += Math.min(0.012, weightVar * 0.04);
  inertiaBase -= Math.min(60, weightVar * 80);

  const finalSil = Math.min(0.365, Math.max(0.24, silBase + (Math.random() * 0.003 - 0.0015)));
  const finalInertia = Math.round(inertiaBase + (Math.random() * 20 - 10));

  const verCount = reg.versions.length + 1;
  const versionId = `v${Math.floor(verCount / 2)}.${verCount % 2 + 1}-${algorithm === "autoencoder" ? "ae" : "km"}-k${k}`;

  const newVersion = {
    version: versionId,
    name: `Tuning K=${k} (${algorithm === "autoencoder" ? "Deep AE" : "K-Means"})`,
    algorithm: algorithm === "autoencoder" ? `Deep Autoencoder (3D Z, K=${k})` : `K-Means RFM (K=${k})`,
    k_clusters: k,
    analysis_window: window === "3_months" ? "3 Tháng" : (window === "6_months" ? "6 Tháng" : "12 Tháng"),
    rfm_weights: {
      r: Number(weightR.toFixed(2)),
      f: Number(weightF.toFixed(2)),
      m: Number(weightM.toFixed(2))
    },
    silhouette_score: Number(finalSil.toFixed(4)),
    inertia: finalInertia,
    reconstruction_mse: algorithm === "autoencoder" ? 0.0118 : null,
    status: "Trained (Candidate)",
    created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
    notes: `Siêu tham số: K=${k}, Trọng số [R:${weightR.toFixed(2)}, F:${weightF.toFixed(2)}, M:${weightM.toFixed(2)}].`
  };

  reg.versions.unshift(newVersion);
  saveModelRegistry(reg);
  return { newVersion, registry: reg };
}

// 4. Data Activation & CRM Webhook Generator
export function generateDynamicApiConfig(segmentSlug = "at-risk", protocol = "REST_PULL") {
  const token = `sk_live_crm_${Math.random().toString(36).substring(2, 10)}${Math.random().toString(36).substring(2, 10)}`;
  const endpointUrl = `http://localhost:8001/api/v1/activation/segments/${segmentSlug}/feed?api_key=${token}`;
  const webhookUrl = `https://crm.retailpulse.internal/webhooks/segment-${segmentSlug}-trigger`;

  const curlCommand = `curl -X GET '${endpointUrl}' \\\n  -H 'Authorization: Bearer ${token}' \\\n  -H 'Accept: application/json'`;

  return {
    segmentSlug,
    protocol,
    endpointUrl,
    webhookUrl,
    token,
    curlCommand,
    createdAt: new Date().toLocaleTimeString()
  };
}

export function getMockCrmFeed(segmentSlug = "at-risk") {
  const allSamples = {
    "at-risk": [
      { customer_code: "12350", recency_days: 30, frequency: 5, monetary_gbp: 1117.72, churn_risk_score: 0.78, next_best_action: "Gửi SMS tặng Voucher 15% kích hoạt trong 48h", channel: "Zalo / SMS" },
      { customer_code: "12382", recency_days: 76, frequency: 5, monetary_gbp: 1750.05, churn_risk_score: 0.85, next_best_action: "Dedicated Support liên hệ thăm dò ý kiến khách", channel: "Email / Call" },
      { customer_code: "12401", recency_days: 65, frequency: 4, monetary_gbp: 940.30, churn_risk_score: 0.72, next_best_action: "Đẩy push notification nhắc điểm thưởng sắp hết hạn", channel: "Mobile App" }
    ],
    "champions": [
      { customer_code: "12368", recency_days: 12, frequency: 11, monetary_gbp: 2318.92, churn_risk_score: 0.05, next_best_action: "Mời tham gia sự kiện độc quyền ra mắt BST mới", channel: "Concierge VIP" },
      { customer_code: "12375", recency_days: 84, frequency: 11, monetary_gbp: 1750.64, churn_risk_score: 0.12, next_best_action: "Tặng quà sinh nhật cao cấp & tích lũy x2 điểm", channel: "VIP Care" }
    ],
    "loyal": [
      { customer_code: "12397", recency_days: 10, frequency: 5, monetary_gbp: 776.15, churn_risk_score: 0.18, next_best_action: "Cross-sell danh mục phụ kiện đi kèm", channel: "App Push" },
      { customer_code: "12448", recency_days: 5, frequency: 4, monetary_gbp: 425.48, churn_risk_score: 0.15, next_best_action: "Mời nâng cấp hạng thẻ Silver lên Gold", channel: "Email" }
    ],
    "hibernating": [
      { customer_code: "12352", recency_days: 173, frequency: 3, monetary_gbp: 140.67, churn_risk_score: 0.92, next_best_action: "Email khảo sát lý do ngưng mua & tặng mã giảm giá", channel: "Email" },
      { customer_code: "12366", recency_days: 226, frequency: 1, monetary_gbp: 233.37, churn_risk_score: 0.95, next_best_action: "Tái kích hoạt qua chiến dịch Black Friday", channel: "Email / SMS" }
    ]
  };

  const feed = allSamples[segmentSlug] || allSamples["at-risk"];
  return {
    status: 200,
    segment: segmentSlug,
    total_records: feed.length,
    extracted_at: new Date().toISOString(),
    records: feed
  };
}

// 5. Heterogeneous Multi-Store & Master Data Management (MDM) Studio
export const MASTER_PRODUCT_CATALOG = [
  {
    canonical_sku: "PRD-001",
    canonical_name: "Bình nước thể thao SmartThermal 750ml",
    category: "Sports & Outdoors",
    base_price_gbp: 38.46,
    aliases: {
      HN: "HN-BOT-750",
      DN: "DN-FLASK-L",
      SG: "SG-HYDRA-750"
    }
  },
  {
    canonical_sku: "PRD-002",
    canonical_name: "Bàn chải điện sóng âm SmartSonic Pro",
    category: "Personal Care",
    base_price_gbp: 25.50,
    aliases: {
      HN: "HN-BRUSH-01",
      DN: "DN-SONIC-X",
      SG: "SG-ELEC-TOOTH"
    }
  },
  {
    canonical_sku: "PRD-003",
    canonical_name: "Đèn bàn LED chống cận ProtectEye V2",
    category: "Home & Living",
    base_price_gbp: 19.99,
    aliases: {
      HN: "HN-LAMP-DESK",
      DN: "DN-LIGHT-LED",
      SG: "SG-LUMEN-DK"
    }
  },
  {
    canonical_sku: "PRD-004",
    canonical_name: "Chuột không dây công thái học ErgoPro",
    category: "Electronics",
    base_price_gbp: 29.90,
    aliases: {
      HN: "HN-MOUSE-WL",
      DN: "DN-POINTER-BT",
      SG: "SG-ERGOMOUSE"
    }
  },
  {
    canonical_sku: "PRD-005",
    canonical_name: "Thảm tập Yoga TPE cao cấp 6mm",
    category: "Fitness",
    base_price_gbp: 15.20,
    aliases: {
      HN: "HN-MAT-YOGA",
      DN: "DN-PAD-YOGA",
      SG: "SG-YOGAMAT-TPE"
    }
  }
];

export const DEFAULT_CURRENCY_RATES = {
  GBP: 1.0,
  VND: 1.0 / 32500.0,
  USD: 1.0 / 1.30,
  EUR: 1.0 / 1.18
};

export const BRANCH_STORE_TOPOLOGY = [
  {
    store_nbr: 1,
    branch_code: "HN",
    name: "Hà Nội Flagship Supercenter",
    city: "Hà Nội",
    format: "CSV_BATCH_STREAM",
    currency: "VND",
    vpn_subnet: "10.8.1.0/24",
    ssh_tunnel: "port 2222 -> 5432",
    encryption: "WireGuard IPSec / AES-256",
    latency_ms: 12,
    fingerprint: "SHA256:4a8b...f91c (Ed25519)",
    status: "ACTIVE_TUNNEL"
  },
  {
    store_nbr: 2,
    branch_code: "DN",
    name: "Đà Nẵng Coastal Tech Hub",
    city: "Đà Nẵng",
    format: "SQL_RELATIONAL_CDC",
    currency: "USD",
    vpn_subnet: "10.8.2.0/24",
    ssh_tunnel: "port 2223 -> 5432",
    encryption: "IPSec / AES-256-GCM",
    latency_ms: 24,
    fingerprint: "SHA256:7b2c...a84e (Ed25519)",
    status: "ACTIVE_TUNNEL"
  },
  {
    store_nbr: 3,
    branch_code: "SG",
    name: "Sài Gòn Metro Distribution",
    city: "TP. Hồ Chí Minh",
    format: "REST_JSON_API",
    currency: "EUR",
    vpn_subnet: "10.8.3.0/24",
    ssh_tunnel: "port 2224 -> 5432",
    encryption: "mTLS Mutual Auth / TLS 1.3",
    latency_ms: 31,
    fingerprint: "SHA256:9c1a...e73d (Ed25519)",
    status: "ACTIVE_TUNNEL"
  }
];

export function resolveMdmProduct(rawSku) {
  const clean = (rawSku || "").trim().toUpperCase();
  for (const item of MASTER_PRODUCT_CATALOG) {
    if (item.canonical_sku.toUpperCase() === clean) return { ...item, is_matched: true };
    for (const [branch, alias] of Object.entries(item.aliases)) {
      if (alias.toUpperCase() === clean) {
        return { ...item, matched_branch: branch, matched_alias: alias, is_matched: true };
      }
    }
  }
  return {
    canonical_sku: `PRD-UNMAPPED-${clean}`,
    canonical_name: `Unmapped Product [${clean}]`,
    category: "General Merchandise",
    base_price_gbp: 10.0,
    is_matched: false
  };
}

export function convertCurrency(amount, fromCurr, toCurr = "GBP") {
  const fromRate = DEFAULT_CURRENCY_RATES[fromCurr.toUpperCase()] || 1.0;
  const toRate = DEFAULT_CURRENCY_RATES[toCurr.toUpperCase()] || 1.0;
  const amountGbp = amount * fromRate;
  const finalAmount = amountGbp / toRate;
  return {
    converted_amount: Number(finalAmount.toFixed(2)),
    rate_to_gbp: Number(fromRate.toFixed(8))
  };
}

export function simulateMultiBranchIngest() {
  const timestamp = new Date().toISOString();
  const txId = Math.floor(1000 + Math.random() * 9000);

  // 1. HN CSV
  const hnProduct = resolveMdmProduct("HN-BOT-750");
  const hnCurr = convertCurrency(2500000, "VND", "GBP");
  const hnCanonical = {
    canonical_order_id: `CAN-HN-${txId}`,
    source_system: "BRANCH_HN_CSV",
    branch_code: "HN",
    store_nbr: 1,
    customer_id: "CUST-HN-88219",
    transaction_timestamp: timestamp,
    raw_currency: "VND",
    raw_total_amount: 2500000.0,
    normalized_total_gbp: hnCurr.converted_amount,
    items: [
      {
        raw_sku: "HN-BOT-750",
        canonical_sku: hnProduct.canonical_sku,
        product_name: hnProduct.canonical_name,
        quantity: 2,
        normalized_unit_price_gbp: 38.46
      }
    ],
    tunnel: "SSH_TUNNEL_PORT_2222 (10.8.1.15)",
    topic: "retail.canonical.transactions"
  };

  // 2. DN SQL
  const dnProduct = resolveMdmProduct("DN-FLASK-L");
  const dnCurr = convertCurrency(50.0, "USD", "GBP");
  const dnCanonical = {
    canonical_order_id: `CAN-DN-${txId + 1}`,
    source_system: "BRANCH_DN_SQL",
    branch_code: "DN",
    store_nbr: 2,
    customer_id: "CUST-DN-9941",
    transaction_timestamp: timestamp,
    raw_currency: "USD",
    raw_total_amount: 50.0,
    normalized_total_gbp: dnCurr.converted_amount,
    items: [
      {
        raw_sku: "DN-FLASK-L",
        canonical_sku: dnProduct.canonical_sku,
        product_name: dnProduct.canonical_name,
        quantity: 1,
        normalized_unit_price_gbp: 38.46
      }
    ],
    tunnel: "SSH_TUNNEL_PORT_2223 (10.8.2.20)",
    topic: "retail.canonical.transactions"
  };

  // 3. SG REST
  const sgProduct = resolveMdmProduct("SG-HYDRA-750");
  const sgCurr = convertCurrency(45.38, "EUR", "GBP");
  const sgCanonical = {
    canonical_order_id: `CAN-SG-${txId + 2}`,
    source_system: "BRANCH_SG_REST",
    branch_code: "SG",
    store_nbr: 3,
    customer_id: "CUST-SG-4412",
    transaction_timestamp: timestamp,
    raw_currency: "EUR",
    raw_total_amount: 45.38,
    normalized_total_gbp: sgCurr.converted_amount,
    items: [
      {
        raw_sku: "SG-HYDRA-750",
        canonical_sku: sgProduct.canonical_sku,
        product_name: sgProduct.canonical_name,
        quantity: 1,
        normalized_unit_price_gbp: 38.46
      }
    ],
    tunnel: "SSH_TUNNEL_PORT_2224 (10.8.3.42)",
    topic: "retail.canonical.transactions"
  };

  return [hnCanonical, dnCanonical, sgCanonical];
}

