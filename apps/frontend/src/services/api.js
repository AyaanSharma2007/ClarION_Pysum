import axios from 'axios';

const LAYER1_URL = 'http://localhost:8000';
const LAYER2_URL = 'http://localhost:8001';
const OLLAMA_URL = 'http://localhost:11434';

export const checkSystemHealth = async () => {
  const results = {
    layer1: false,
    layer2: false,
    ollama: false,
  };

  try {
    const l1Res = await axios.get(`${LAYER1_URL}/api/health`, { timeout: 3000 });
    results.layer1 = l1Res.status === 200;
  } catch (e) {
    results.layer1 = false;
  }

  try {
    const l2Res = await axios.get(`${LAYER2_URL}/api/health`, { timeout: 3000 });
    results.layer2 = l2Res.status === 200;
  } catch (e) {
    results.layer2 = false;
  }

  try {
    const olRes = await axios.get(`${OLLAMA_URL}/api/tags`, { timeout: 3000 });
    results.ollama = olRes.status === 200;
  } catch (e) {
    results.ollama = false;
  }

  return results;
};

// Layer 1 API calls
export const ingestRfiLayer1 = async (payload) => {
  try {
    const res = await axios.post(`${LAYER1_URL}/ingest`, payload);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const parsePdfLayer1 = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await axios.post(`${LAYER1_URL}/parse-pdf`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

// Layer 2 API calls — field name is `query` + `top_k` + `owner_team` per Layer 2 SearchRequest schema
export const searchSemantic = async (queryText, topK = 5, ownerTeam = 'EU-Hub-Regulatory') => {
  try {
    const res = await axios.post(
      `${LAYER2_URL}/search`,
      {
        query: queryText,
        top_k: topK,
        owner_team: ownerTeam,
      },
      {
        headers: { 'X-Owner-Team': ownerTeam },
      }
    );
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const searchRecommend = async (concernText, topK = 5) => {
  try {
    const res = await axios.post(`${LAYER2_URL}/search/recommend`, {
      concern_text: concernText,
      top_k: topK
    });
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const searchHybrid = async (queryText, topK = 5, ownerTeam = 'EU-Hub-Regulatory') => {
  try {
    const res = await axios.post(
      `${LAYER2_URL}/search/hybrid`,
      {
        query: queryText,
        top_k: topK,
        owner_team: ownerTeam,
      },
      {
        headers: { 'X-Owner-Team': ownerTeam },
      }
    );
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const fetchAllRfis = async () => {
  try {
    const res = await axios.get(`${LAYER2_URL}/rfi`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const getRfiByUuid = async (identifier) => {
  try {
    const res = await axios.get(`${LAYER2_URL}/rfi/${identifier}`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const advanceRfiStage = async (identifier, stage, actor = 'RA Clinical Specialist') => {
  try {
    const res = await axios.patch(`${LAYER2_URL}/rfi/${identifier}/stage`, {
      stage,
      actor,
    });
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const getRfiAuditChain = async (identifier) => {
  try {
    const res = await axios.get(`${LAYER2_URL}/rfi/${identifier}/audit`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const ingestDirectLayer2 = async (payload, ownerTeam = 'EU-Hub-Regulatory') => {
  try {
    const enrichedPayload = { owner_team: ownerTeam, ...payload };
    const res = await axios.post(`${LAYER2_URL}/rfi`, enrichedPayload, {
      headers: { 'X-Owner-Team': ownerTeam },
    });
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

// Active Learning Correction Capture Loop (Bible Section 14.1)
export const submitCategoryCorrection = async (
  rfiId,
  originalCategory,
  correctedCategory,
  actor = 'RA Clinical Specialist'
) => {
  try {
    const res = await axios.post(`${LAYER1_URL}/api/extraction/correction`, {
      rfi_id: rfiId,
      original_category: originalCategory,
      corrected_category: correctedCategory,
      actor,
    });
    return res.data;
  } catch (err) {
    console.error('[submitCategoryCorrection] Failed to record correction:', err?.response?.data || err);
    throw err.response?.data || err;
  }
};


// Layer 4 Risk Prediction Engine API calls (Clarion Bible §9)
export const predictDossierRisk = async (dossierFeatures) => {
  try {
    const res = await axios.post(`${LAYER1_URL}/api/risk/predict`, dossierFeatures);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const getRiskFeatureSchema = async () => {
  try {
    const res = await axios.get(`${LAYER1_URL}/api/risk/features`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const draftAiResponse = async (considerationId, force = false) => {
  try {
    const res = await axios.post(`${LAYER1_URL}/api/draft/${considerationId}${force ? '?force=true' : ''}`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};

export const getDraftHistory = async (considerationId) => {
  try {
    const res = await axios.get(`${LAYER1_URL}/api/draft/${considerationId}/history`);
    return res.data;
  } catch (err) {
    throw err.response?.data || err;
  }
};
