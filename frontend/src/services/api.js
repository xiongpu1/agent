/**
 * API service for backend communication.
 * Encapsulates all backend API calls.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const rewriteMaterialImageUrl = (url) => {
  const u = String(url || '')
  if (!u) return ''
  // When API_BASE_URL is empty, frontend relies on Vite proxy rules.
  // Some environments don't proxy /static/material_images correctly, so we
  // expose images under /api/material_images/* and rewrite accordingly.
  if (!API_BASE_URL && u.startsWith('/static/material_images/')) {
    return u.replace('/static/material_images/', '/api/material_images/')
  }
  return u
}

const resolveApiUrl = (path) => {
  const p = String(path || '')
  if (!p) return ''
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  if (p.startsWith('/') && API_BASE_URL) return `${API_BASE_URL}${p}`
  return p
}

const encodeDocumentPath = (docPath) =>
  (docPath || '')
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')

async function handleResponse(response, defaultMessage) {
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `${defaultMessage}: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Generate specsheet purely from OCR documents.
 * @param {{documents: object[]}} payload
 * @returns {Promise<{specsheet: object|null, chunks: object[]}>}
 */
export async function generateSpecsheetFromOcr(payload) {
  const response = await fetch(`${API_BASE_URL}/api/specsheet/from_ocr_docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? { documents: [] }),
  })
  const data = await handleResponse(response, 'Failed to generate specsheet from OCR docs')
  return {
    specsheet: data.specsheet || null,
    chunks: Array.isArray(data.chunks) ? data.chunks : [],
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

/**
 * Generate instruction/manual book purely from OCR documents.
 * @param {{documents: object[]}} payload
 * @returns {Promise<{manual_book: object|null, prompt_text?: string, system_prompt?: string}>}
 */
export async function generateManualBookFromOcr(payload) {
  const response = await fetch(`${API_BASE_URL}/api/manual/book/from_ocr_docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? { documents: [] }),
  })
  const data = await handleResponse(response, 'Failed to generate manual book from OCR docs')
  return {
    manual_book: data.manual_book || null,
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

/**
 * Plan manual book variant selection (A/B/C) per section group, and optionally generate pages only when uncertain.
 * @param {{documents: object[], product_name?: string, bom_code?: string, session_id?: string, llm_provider?: string, llm_model?: string}} payload
 * @returns {Promise<{variants: object, generated_pages: object, prompt_text?: string, system_prompt?: string}>}
 */
export async function planManualBookVariants(payload) {
  const response = await fetch(`${API_BASE_URL}/api/manual/book/variant_plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? { documents: [] }),
  })
  const data = await handleResponse(response, 'Failed to plan manual book variants')
  return {
    variants: data.variants && typeof data.variants === 'object' ? data.variants : {},
    generated_pages: data.generated_pages && typeof data.generated_pages === 'object' ? data.generated_pages : {},
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

/**
 * One-shot manual generation: single LLM call returns variants + generated_pages + fixed_pages.
 * @param {{documents: object[], product_name: string, bom_code: string, session_id?: string, llm_provider?: string, llm_model?: string}} payload
 * @returns {Promise<{variants: object, generated_pages: object, fixed_pages: object, prompt_text?: string, system_prompt?: string}>}
 */
export async function generateManualBookOneShot(payload) {
  const response = await fetch(`${API_BASE_URL}/api/manual/book/one_shot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? { documents: [] }),
  })
  const data = await handleResponse(response, 'Failed to generate manual book (one-shot)')
  return {
    variants: data.variants && typeof data.variants === 'object' ? data.variants : {},
    fixed_pages: data.fixed_pages && typeof data.fixed_pages === 'object' ? data.fixed_pages : {},
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

export async function getSavedManualBook(productName, bomCode) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const query = `?product_name=${encodeURIComponent(productName)}&bom_code=${encodeURIComponent(bomCode)}`
  const response = await fetch(`${API_BASE_URL}/api/manual/book/saved${query}`)
  if (response.status === 404) return null
  const data = await handleResponse(response, 'Failed to fetch saved manual book')
  return {
    manual_book: data.manual_book || null,
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

export async function getSavedManualSpecsheet(productName, bomCode) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const query = `?product_name=${encodeURIComponent(productName)}&bom_code=${encodeURIComponent(bomCode)}`
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/saved${query}`)
  if (response.status === 404) return null
  const data = await handleResponse(response, 'Failed to fetch saved manual specsheet')
  return data.specsheet || null
}

export async function getSavedManualSpecsheetLayout(productName, bomCode) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const query = `?product_name=${encodeURIComponent(productName)}&bom_code=${encodeURIComponent(bomCode)}`
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/layout${query}`)
  if (response.status === 404) return null
  const data = await handleResponse(response, 'Failed to fetch saved manual specsheet layout')
  return data.layout || null
}

export async function saveManualBookTruth(productName, bomCode, manualBookPages, targetFolder = 'truth') {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const response = await fetch(`${API_BASE_URL}/api/manual/book/truth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_name: productName,
      bom_code: bomCode,
      manual_book: Array.isArray(manualBookPages) ? manualBookPages : [],
      target_folder: targetFolder
    })
  })
  const data = await handleResponse(response, 'Failed to save manual book truth')
  return {
    manual_book: data.manual_book || null,
    prompt_text: data.prompt_text || '',
    system_prompt: data.system_prompt || ''
  }
}

export async function saveManualSpecsheetTruth(productName, bomCode, specsheet) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/truth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_name: productName,
      bom_code: bomCode,
      specsheet: specsheet || null
    })
  })
  const data = await handleResponse(response, 'Failed to save manual specsheet truth')
  return data.specsheet || null
}

export async function saveManualSpecsheetLayout(productName, bomCode, layout, updatedBy) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/layout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_name: productName,
      bom_code: bomCode,
      layout: layout && typeof layout === 'object' ? layout : {},
      updated_by: updatedBy || null
    })
  })
  const data = await handleResponse(response, 'Failed to save manual specsheet layout')
  return data.layout || null
}

export async function getManualBookVariants(productName, bomCode) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const query = `?product_name=${encodeURIComponent(productName)}&bom_code=${encodeURIComponent(bomCode)}`
  const response = await fetch(`${API_BASE_URL}/api/manual/book/variants${query}`)
  if (response.status === 404) return null
  const data = await handleResponse(response, 'Failed to fetch manual book variants')
  return data.variants && typeof data.variants === 'object' ? data.variants : null
}

export async function saveManualBookVariants(productName, bomCode, variants) {
  if (!productName) throw new Error('Missing productName')
  if (!bomCode) throw new Error('Missing bomCode')
  const response = await fetch(`${API_BASE_URL}/api/manual/book/variants`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_name: productName,
      bom_code: bomCode,
      variants: variants && typeof variants === 'object' ? variants : {}
    })
  })
  const data = await handleResponse(response, 'Failed to save manual book variants')
  return data.variants && typeof data.variants === 'object' ? data.variants : null
}

export async function analyzePosterReference({
  file,
  image_url,
  prompt,
  model,
  font_candidates,
} = {}) {
  const toDataUrl = (f) =>
    new Promise((resolve, reject) => {
      try {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('Failed to read image file'))
        reader.readAsDataURL(f)
      } catch (e) {
        reject(e)
      }
    })

  let resolvedImageUrl = image_url
  if (file) {
    resolvedImageUrl = await toDataUrl(file)
  }

  const response = await fetch(`${API_BASE_URL}/api/poster/analyze_reference`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_url: resolvedImageUrl || null,
      prompt: prompt || null,
      model: model || null,
      font_candidates: Array.isArray(font_candidates) ? font_candidates : null,
    }),
  })
  return handleResponse(response, 'Failed to analyze poster reference')
}

export async function generatePosterCopy({
  step1_result,
  requirements,
  target_language,
  model,
  product_name,
  bom_code,
  bom_type,
  product_file,
  product_image_url,
  background_file,
  background_image_url,
} = {}) {
  const toDataUrl = (f) =>
    new Promise((resolve, reject) => {
      try {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('Failed to read image file'))
        reader.readAsDataURL(f)
      } catch (e) {
        reject(e)
      }
    })

  let resolvedProductUrl = product_image_url
  if (product_file) {
    resolvedProductUrl = await toDataUrl(product_file)
  }

  let resolvedBackgroundUrl = background_image_url
  if (background_file) {
    resolvedBackgroundUrl = await toDataUrl(background_file)
  }

  const response = await fetch(`${API_BASE_URL}/api/poster/generate_copy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      step1_result: step1_result && typeof step1_result === 'object' ? step1_result : null,
      requirements: requirements || null,
      target_language: target_language || null,
      model: model || null,
      product_name: product_name || null,
      bom_code: bom_code || null,
      bom_type: bom_type || null,
      product_image_url: resolvedProductUrl || null,
      background_image_url: resolvedBackgroundUrl || null,
    }),
  })
  return handleResponse(response, 'Failed to generate poster copy')
}

export async function generatePosterImageEdit({
  step1_result,
  product_name,
  bom_code,
  reference_file,
  reference_image_url,
  product_file,
  product_image_url,
  background_file,
  background_image_url,
  title,
  subtitle,
  sellpoints,
  output_width,
  output_height,
  watermark,
  negative_prompt,
} = {}) {
  const toDataUrl = (f) =>
    new Promise((resolve, reject) => {
      try {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('Failed to read image file'))
        reader.readAsDataURL(f)
      } catch (e) {
        reject(e)
      }
    })

  let resolvedRefUrl = reference_image_url
  if (reference_file) {
    resolvedRefUrl = await toDataUrl(reference_file)
  }

  let resolvedProductUrl = product_image_url
  if (product_file) {
    resolvedProductUrl = await toDataUrl(product_file)
  }

  let resolvedBackgroundUrl = background_image_url
  if (background_file) {
    resolvedBackgroundUrl = await toDataUrl(background_file)
  }

  const response = await fetch(`${API_BASE_URL}/api/poster/generate_image_edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reference_image_url: resolvedRefUrl || null,
      product_image_url: resolvedProductUrl || null,
      background_image_url: resolvedBackgroundUrl || null,
      step1_result: step1_result && typeof step1_result === 'object' ? step1_result : null,
      product_name: product_name || null,
      bom_code: bom_code || null,
      title: title || null,
      subtitle: subtitle || null,
      sellpoints: Array.isArray(sellpoints) ? sellpoints : null,
      output_width: Number.isFinite(Number(output_width)) ? Number(output_width) : null,
      output_height: Number.isFinite(Number(output_height)) ? Number(output_height) : null,
      watermark: typeof watermark === 'boolean' ? watermark : null,
      negative_prompt: negative_prompt || null,
    }),
  })
  return handleResponse(response, 'Failed to generate poster image')
}

/**
 * Legacy helper: generate specsheet using docs grouped by product/accessory.
 * (Kept for backward compatibility on other pages.)
 */
export async function generateSpecsheetFromDocs(productName, bomVersion, payload) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productName)}/boms/${encodeURIComponent(bomVersion)}/specsheet_from_docs`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload ?? {}),
    }
  )
  const data = await handleResponse(response, 'Failed to generate specsheet from docs')
  return {
    specsheet: data.specsheet || null,
    chunks: Array.isArray(data.chunks) ? data.chunks : [],
  }
}

export async function getSpecsheet(productName, bomVersion) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productName)}/boms/${encodeURIComponent(bomVersion)}/specsheet`
  )
  const data = await handleResponse(response, 'Failed to fetch specsheet')
  return data.specsheet || null
}

export async function getSpecsheetWithChunks(productName, bomVersion) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productName)}/boms/${encodeURIComponent(bomVersion)}/specsheet_with_chunks`
  )
  const data = await handleResponse(response, 'Failed to fetch specsheet with chunks')
  return {
    specsheet: data.specsheet || null,
    chunks: Array.isArray(data.chunks) ? data.chunks : [],
  }
}

export async function saveSpecsheet(productName, bomVersion, specsheet) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productName)}/boms/${encodeURIComponent(bomVersion)}/specsheet`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ specsheet }),
    }
  )
  return handleResponse(response, 'Failed to save specsheet')
}

/**
 * Get all product English names.
 * @returns {Promise<string[]>} List of product names
 */
export async function getProducts() {
  const response = await fetch(`${API_BASE_URL}/api/products`)
  const data = await handleResponse(response, 'Failed to fetch products')
  return Array.isArray(data.products) ? data.products : []
}

export async function getMaterials() {
  const response = await fetch(`${API_BASE_URL}/api/materials`)
  const data = await handleResponse(response, 'Failed to fetch materials')
  return Array.isArray(data.materials) ? data.materials : []
}

export async function getBomsByMaterial(materialCode) {
  const response = await fetch(`${API_BASE_URL}/api/materials/${encodeURIComponent(materialCode)}/boms`)
  if (response.status === 404) return []
  const data = await handleResponse(response, 'Failed to fetch BOMs for material')
  return data.boms || []
}

export async function getProductImage(productName) {
  const name = String(productName || '').trim()
  if (!name) return { product_name: '', found: false, image_url: '' }
  const response = await fetch(`${API_BASE_URL}/api/products/${encodeURIComponent(name)}/image`)
  if (response.status === 404) return { product_name: name, found: false, image_url: '' }
  const data = await handleResponse(response, 'Failed to fetch image for product')
  return {
    ...data,
    image_url: rewriteMaterialImageUrl(resolveApiUrl(data?.image_url))
  }
}

export async function getMaterialImage(materialCode) {
  const code = String(materialCode || '').trim()
  if (!code) return { material_code: '', found: false, image_url: '' }
  const response = await fetch(`${API_BASE_URL}/api/materials/${encodeURIComponent(code)}/image`)
  if (response.status === 404) return { material_code: code, found: false, image_url: '' }
  const data = await handleResponse(response, 'Failed to fetch image for material')
  return {
    ...data,
    image_url: rewriteMaterialImageUrl(resolveApiUrl(data?.image_url))
  }
}

export async function getAccessoriesZhByMaterialBom(materialCode, bomId) {
  const response = await fetch(
    `${API_BASE_URL}/api/materials/${encodeURIComponent(materialCode)}/boms/${encodeURIComponent(bomId)}/accessories`
  )
  if (response.status === 404) return []
  const data = await handleResponse(response, 'Failed to fetch accessories for material BOM')
  return data.accessories || []
}

/**
 * Get documents linked to an accessory.
 * @param {string} accessoryName
 * @returns {Promise<{name:string, path:string, created_at?:string, type?:string, summary?:string}[]>}
 */
export async function getDocumentsByAccessory(accessoryName) {
  const response = await fetch(
    `${API_BASE_URL}/api/accessories/${encodeURIComponent(accessoryName)}/documents`
  )
  const data = await handleResponse(response, 'Failed to fetch documents for accessory')
  return Array.isArray(data.documents) ? data.documents : []
}

/**
 * Get documents linked to a product BOM.
 * @param {string} productName
 * @param {string} bomVersion
 * @returns {Promise<{name:string, path:string, created_at?:string, type?:string, summary?:string}[]>}
 */
export async function getDocumentsByProductBom(productName, bomVersion) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productName)}/boms/${encodeURIComponent(bomVersion)}/documents`
  )
  const data = await handleResponse(response, 'Failed to fetch documents for BOM')
  return Array.isArray(data.documents) ? data.documents : []
}

export async function getKbOverview(productId) {
  const response = await fetch(`${API_BASE_URL}/api/products/${encodeURIComponent(productId)}/kb_overview`)
  if (response.status === 404) return null
  return handleResponse(response, 'Failed to fetch KB overview')
}

export async function updateProductConfig(productId, configTextZh) {
  if (!productId) throw new Error('Missing productId')
  const response = await fetch(`${API_BASE_URL}/api/products/${encodeURIComponent(productId)}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_text_zh: configTextZh ?? '' }),
  })
  return handleResponse(response, 'Failed to update product config')
}

/**
 * Get full document detail including file content.
 * @param {string} docPath
 * @returns {Promise<{name:string,path:string,content:string}>}
 */
export async function getDocumentDetail(docPath) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeDocumentPath(docPath)}`)
  return handleResponse(response, 'Failed to fetch document detail')
}

export async function generateBomFromOcr(payload) {
  const response = await fetch(`${API_BASE_URL}/api/bom/from_ocr_docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? { documents: [] })
  })
  return handleResponse(response, 'Failed to generate BOM from OCR docs')
}

export async function saveBomCode(payload) {
  const response = await fetch(`${API_BASE_URL}/api/bom/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {})
  })
  return handleResponse(response, 'Failed to save BOM code')
}

export async function getSavedBomBySession(sessionId) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/bom/session/${encodeURIComponent(sessionId)}`)
  if (response.status === 404) return null
  return handleResponse(response, 'Failed to fetch saved BOM')
}

/**
 * Update document content (and optionally rename).
 * @param {string} docPath
 * @param {{content:string,new_name?:string|null}} payload
 */
export async function updateDocument(docPath, payload) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeDocumentPath(docPath)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleResponse(response, 'Failed to update document')
}

/**
 * Delete a document.
 * @param {string} docPath
 */
export async function deleteDocument(docPath) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeDocumentPath(docPath)}`, {
    method: 'DELETE',
  })
  return handleResponse(response, 'Failed to delete document')
}

/**
 * Move a document to a new product or accessory owner.
 * @param {string} docPath
 * @param {{target_type:'product'|'accessory',product_name?:string,bom_version?:string,accessory_name?:string}} payload
 */
export async function moveDocument(docPath, payload) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeDocumentPath(docPath)}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleResponse(response, 'Failed to move document')
}

/**
 * Get documents that are not attached to any product/accessory.
 * @returns {Promise<{name:string,path:string,created_at?:string}[]>}
 */
export async function getUnmatchedDocuments() {
  const response = await fetch(`${API_BASE_URL}/api/documents/unmatched`)
  const data = await handleResponse(response, 'Failed to fetch unmatched documents')
  return Array.isArray(data) ? data : []
}

/**
 * Attach an unmatched document to a product or accessory.
 * @param {{doc_path:string,target_type:'product'|'accessory',product_name?:string,bom_version?:string,accessory_name?:string}} payload
 */
export async function attachDocument(payload) {
  const response = await fetch(`${API_BASE_URL}/api/documents/attach`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleResponse(response, 'Failed to attach document')
}

/**
 * Get detail for an unmatched document (Document or Unknown).
 * @param {string} docPath
 */
export async function getUnmatchedDocumentDetail(docPath) {
  const response = await fetch(
    `${API_BASE_URL}/api/documents/unmatched/${encodeDocumentPath(docPath)}`
  )
  return handleResponse(response, 'Failed to fetch unmatched document detail')
}

/**
 * Get accessories linked to a product BOM.
 * @param {string} productName
 * @param {string} bomVersion
 * @returns {Promise<{name:string, path:string, created_at?:string}[]>}
 */
export async function getAccessoriesByProductBom(productId, bomId) {
  const response = await fetch(
    `${API_BASE_URL}/api/products/${encodeURIComponent(productId)}/boms/${encodeURIComponent(bomId)}/accessories`
  )
  const data = await handleResponse(response, 'Failed to fetch accessories for BOM')
  return data.accessories || []
}

/**
 * Get all accessories.
 * @returns {Promise<{name:string, path:string, created_at?:string}[]>}
 */
export async function getAccessories() {
  const response = await fetch(`${API_BASE_URL}/api/accessories`)
  const data = await handleResponse(response, 'Failed to fetch accessories')
  return Array.isArray(data.accessories) ? data.accessories : []
}

/**
 * Get BOMs for a product.
 * @param {string} productName
 * @returns {Promise<{name:string, path:string, created_at?:string}[]>}
 */
export async function getBomsByProduct(productId) {
  const response = await fetch(`${API_BASE_URL}/api/products/${encodeURIComponent(productId)}/boms`)
  if (response.status === 404) return []
  const data = await handleResponse(response, 'Failed to fetch BOMs')
  return data.boms || []
}

/**
 * Fetch OCR session inputs for manual generation (product files + accessory files + OCR groups).
 * @param {string} sessionId
 */
export async function getManualSessionInputs(sessionId) {
  const session = await getManualSession(sessionId)
  const documents = []

  const normalizePath = (path) => {
    if (!path) return ''
    return path.replace(/^\/+/, '')
  }

  const stripApiPrefix = (value) => {
    if (!value) return ''
    return value.replace(/^\/api\/files\//, '')
  }

  const pushDoc = (doc) => {
    if (!doc) return
    const rawPath = doc.path || doc.relative_path || stripApiPrefix(doc.url)
    documents.push({
      name: doc.name || doc.source_name || doc.path,
      path: normalizePath(rawPath),
      type: doc.type || doc.kind || 'document',
      summary: doc.summary || doc.caption || '',
      text: doc.text || doc.raw_text || '',
      mime_type: doc.mime_type || doc.mime || doc.type || doc.kind,
      image_base64: doc.image_base64 || '',
    })
  }

  ;(session?.product_files || []).forEach(pushDoc)
  ;(session?.accessory_files || []).forEach(pushDoc)

  const flattenGroups = (groups = []) => {
    groups.forEach((group) => {
      (group.pages || []).forEach((page) => {
        (page.artifacts || []).forEach((artifact) => {
          pushDoc({
            name: artifact.name,
            path: artifact.path || stripApiPrefix(artifact.url),
            type: artifact.kind,
            summary: artifact.caption,
            mime_type: artifact.type || artifact.mime,
          })
        })
      })
    })
  }

  flattenGroups(session?.product_ocr_groups)
  flattenGroups(session?.accessory_ocr_groups)

  return documents
}

const appendFilesToFormData = (formData, fieldName, files = []) => {
  files.forEach((file, index) => {
    const raw = file?.rawFile || file?.raw || file
    if (!(raw instanceof Blob)) return
    const filename = file?.name || raw?.name || `${fieldName}-${index + 1}`
    formData.append(fieldName, raw, filename)
  })
}

export async function createManualSession({ productName, bomCode, productFiles = [], accessoryFiles = [] } = {}) {
  const formData = new FormData()
  formData.append('product_name', productName || '')
  formData.append('bom_code', bomCode || '')
  if (arguments[0]?.bomType) {
    formData.append('bom_type', arguments[0].bomType || '')
  }
  appendFilesToFormData(formData, 'product_files', productFiles)
  appendFilesToFormData(formData, 'accessory_files', accessoryFiles)

  const response = await fetch(`${API_BASE_URL}/api/manual-sessions`, {
    method: 'POST',
    body: formData
  })

  return handleResponse(response, 'Failed to create manual session')
}

export async function initManualSession({ productName, bomCode, bomType, materialCode, bomId } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_name: productName || '',
      bom_code: bomCode || '',
      bom_type: bomType || '',
      material_code: materialCode || '',
      bom_id: bomId || ''
    })
  })
  return handleResponse(response, 'Failed to init manual session')
}

export async function runManualOcr(productName, productFiles = [], accessoryFiles = [], options = {}) {
  const { sessionId } = options
  const formData = new FormData()
  formData.append('product_name', productName || '')
  appendFilesToFormData(formData, 'product_files', productFiles)
  appendFilesToFormData(formData, 'accessory_files', accessoryFiles)
  if (sessionId) {
    formData.append('session_id', sessionId)
  }

  const response = await fetch(`${API_BASE_URL}/api/manual/ocr`, {
    method: 'POST',
    body: formData
  })

  return handleResponse(response, 'Failed to run manual OCR')
}

export async function runManualOcrSession(sessionId) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}/ocr`, {
    method: 'POST'
  })
  return handleResponse(response, 'Failed to trigger manual OCR')
}

export async function runPromptReverse(sessionId, userPrompt = '') {
  if (!sessionId) throw new Error('Missing sessionId')
  const body = userPrompt ? { user_prompt: userPrompt } : {}
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}/prompt-reverse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: Object.keys(body).length ? JSON.stringify(body) : null
  })
  return handleResponse(response, 'Failed to trigger prompt reverse')
}

export async function getManualOcrProgress(sessionId) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}/progress`)
  if (response.status === 404) {
    return null
  }
  return handleResponse(response, 'Failed to fetch manual OCR progress')
}

export async function getManualHistory(limit = 50) {
  const response = await fetch(`${API_BASE_URL}/api/manual/ocr/history?limit=${encodeURIComponent(limit)}`)
  const data = await handleResponse(response, 'Failed to fetch manual OCR history')
  return Array.isArray(data.history) ? data.history : []
}

export async function getManualSession(sessionId) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}`)
  if (response.status === 404) {
    throw new Error('未找到该 OCR 记录，可能已被删除')
  }
  return handleResponse(response, 'Failed to fetch manual session')
}

export async function appendManualSessionUploads(sessionId, { productFiles = [], accessoryFiles = [] } = {}) {
  if (!sessionId) throw new Error('Missing sessionId')
  const formData = new FormData()
  appendFilesToFormData(formData, 'product_files', productFiles)
  appendFilesToFormData(formData, 'accessory_files', accessoryFiles)
  const response = await fetch(`${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}/uploads`, {
    method: 'POST',
    body: formData
  })
  return handleResponse(response, 'Failed to append manual session uploads')
}

export async function deleteManualSessionUpload(sessionId, path) {
  if (!sessionId) throw new Error('Missing sessionId')
  if (!path) throw new Error('Missing file path')
  const response = await fetch(
    `${API_BASE_URL}/api/manual-sessions/${encodeURIComponent(sessionId)}/uploads?path=${encodeURIComponent(path)}`,
    { method: 'DELETE' }
  )
  return handleResponse(response, 'Failed to delete manual session upload')
}

export async function deleteManualSession(sessionId) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual/ocr/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE'
  })
  if (response.status === 404) {
    throw new Error('OCR 记录不存在或已被删除')
  }
  return handleResponse(response, 'Failed to delete manual OCR session')
}

export async function insertManualProduct(payload = {}) {
  const response = await fetch(`${API_BASE_URL}/api/manual/insert-neo4j`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(response, '写入 Neo4j 失败')
}

export async function getManualSpecsheet(sessionId, bomCode) {
  if (!sessionId) throw new Error('Missing sessionId')
  const query = bomCode ? `?bom_code=${encodeURIComponent(bomCode)}` : ''
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/${encodeURIComponent(sessionId)}${query}`)
  if (response.status === 404) return null
  const data = await handleResponse(response, 'Failed to fetch manual specsheet')
  return data.specsheet || null
}

export async function saveManualSpecsheet(sessionId, specsheet, bomCode) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/${encodeURIComponent(sessionId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      specsheet,
      bom_code: bomCode || undefined
    })
  })
  const data = await handleResponse(response, 'Failed to save manual specsheet')
  return data.specsheet || null
}

export async function runManualSpecsheetAce(sessionId, specsheet, bomCode) {
  if (!sessionId) throw new Error('Missing sessionId')
  const response = await fetch(`${API_BASE_URL}/api/manual/specsheet/${encodeURIComponent(sessionId)}/ace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      // ground_truth is loaded by backend from manual_ocr_results/<session_or_folder>/truth/specsheet.json
      bom_code: bomCode || undefined
    })
  })
  return handleResponse(response, '触发规格页 ACE 失败')
}

export async function clearManualHistory() {
  const response = await fetch(`${API_BASE_URL}/api/manual/ocr/history`, {
    method: 'DELETE'
  })
  return handleResponse(response, 'Failed to clear manual OCR history')
}

export async function getPromptPlaybooks({ productNames = [], playbookType = '' } = {}) {
  const params = new URLSearchParams()
  if (Array.isArray(productNames) && productNames.length) {
    productNames.forEach((name) => {
      if (name) params.append('product_names', name)
    })
  }
  if (playbookType) {
    params.set('playbook_type', playbookType)
  }
  const query = params.toString()
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks${query ? `?${query}` : ''}`)
  const data = await handleResponse(response, 'Failed to fetch prompt playbooks')
  return Array.isArray(data.items) ? data.items : []
}

export async function runPromptPlaybookAce(payload = {}) {
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/ace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(response, '触发 ACE 提示词优化失败')
}

export async function getPromptPlaybookDatasets(limit = 20) {
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/datasets?limit=${encodeURIComponent(limit)}`)
  const data = await handleResponse(response, 'Failed to fetch ACE datasets')
  return Array.isArray(data.datasets) ? data.datasets : []
}

export async function getPromptPlaybookRules(limit) {
  const query = typeof limit === 'number' ? `?limit=${encodeURIComponent(limit)}` : ''
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/rules${query}`)
  const data = await handleResponse(response, 'Failed to fetch prompt playbook rules')
  return Array.isArray(data.rules) ? data.rules : []
}

export async function getPromptPlaybookRulesByType(playbookType = 'spec', limit) {
  const params = new URLSearchParams()
  if (typeof limit === 'number') {
    params.set('limit', String(limit))
  }
  if (playbookType) {
    params.set('playbook_type', playbookType)
  }
  const query = params.toString()
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/rules${query ? `?${query}` : ''}`)
  const data = await handleResponse(response, 'Failed to fetch prompt playbook rules')
  return Array.isArray(data.rules) ? data.rules : []
}

export async function deletePromptPlaybookRule(ruleId) {
  if (!ruleId) throw new Error('ruleId is required')
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/rules/${encodeURIComponent(ruleId)}`, {
    method: 'DELETE'
  })
  await handleResponse(response, '删除规则失败')
  return true
}

export async function deletePromptPlaybookRuleByType(ruleId, playbookType = 'spec') {
  if (!ruleId) throw new Error('ruleId is required')
  const params = new URLSearchParams()
  if (playbookType) {
    params.set('playbook_type', playbookType)
  }
  const query = params.toString()
  const response = await fetch(
    `${API_BASE_URL}/api/prompt-playbooks/rules/${encodeURIComponent(ruleId)}${query ? `?${query}` : ''}`,
    {
      method: 'DELETE'
    }
  )
  await handleResponse(response, '删除规则失败')
  return true
}

export async function deletePromptPlaybookDataset(filePath) {
  const response = await fetch(`${API_BASE_URL}/api/prompt-playbooks/datasets`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath })
  })
  await handleResponse(response, '删除 ACE 数据集失败')
  return true
}
