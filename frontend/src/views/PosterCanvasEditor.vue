<template>
  <div class="poster-editor-page" @contextmenu.prevent>
    <div class="top-left">
      <el-button size="small" @click="handleBack">返回</el-button>
    </div>

    <el-dialog
      v-model="imageDialogVisible"
      title="插入图片"
      width="520px"
    >
      <div class="product-dialog">
        <el-tabs v-model="imageDialogTab">
          <el-tab-pane label="本地上传" name="local">
            <div class="product-dialog-section">
              <p>从本地选择一张图片插入到画布。</p>
              <el-button type="primary" @click="triggerLocalImageUpload">选择本地图片</el-button>
            </div>
          </el-tab-pane>
          <el-tab-pane label="知识库图片" name="kb">
            <div class="product-dialog-section">
              <p>从知识库中选择一张现有图片：</p>
              <div class="kb-image-grid">
                <div
                  v-for="img in kbProductImages"
                  :key="img.src"
                  class="kb-image-item"
                  @click="selectKbProductImage(img.src)"
                >
                  <img :src="img.src" :alt="img.label" />
                  <div class="kb-image-label">{{ img.label }}</div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <div class="top-right">
      <div class="zoom-pill">
        <el-button size="small" text @click="decZoom">-</el-button>
        <div class="zoom-text">{{ Math.round(zoom * 100) }}%</div>
        <el-button size="small" text @click="incZoom">+</el-button>
      </div>
    </div>

    <div class="left-toolbar">
      <el-button class="tool-btn" size="small" text @click="addText">文字</el-button>
      <el-button class="tool-btn" size="small" text @click="triggerPickImage">图片</el-button>
    </div>

    <div class="stage" ref="stageRef">
      <canvas ref="canvasEl"></canvas>

      <div v-if="initError" class="init-error">{{ initError }}</div>

      <div
        v-if="objOverlay.visible"
        class="obj-toolbar"
        :data-place="objOverlay.placement"
        ref="objToolbarRef"
        :style="{ left: objOverlay.left + 'px', top: objOverlay.top + 'px' }"
      >
        <button class="tool" type="button" @click="duplicateActive">复制</button>
        <button class="tool" type="button" @click="rotateActive">旋转</button>
        <button class="tool" type="button" @click="downloadActive">下载</button>
        <button class="tool danger" type="button" @click="removeActive">删除</button>
      </div>

      <div
        v-if="objOverlay.sizeVisible"
        class="obj-size-tag"
        ref="objSizeTagRef"
        :style="{ left: objOverlay.sizeLeft + 'px', top: objOverlay.sizeTop + 'px' }"
      >
        {{ objOverlay.sizeText }}
      </div>

      <div v-if="resizeOverlay.visible" class="resize-handles">
        <div
          v-for="h in resizeOverlay.handles"
          :key="h.key"
          class="resize-handle"
          :data-key="h.key"
          :style="{ left: h.x + 'px', top: h.y + 'px' }"
          @pointerdown="(e) => onResizeHandleDown(h.key, e)"
        ></div>
      </div>
    </div>

    <input ref="imageInputRef" type="file" accept="image/*" style="display:none" @change="onPickImage" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import jsPDF from 'jspdf'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Canvas as FabricCanvas, Textbox as FabricTextbox, Image as FabricImage, Point as FabricPoint, Rect as FabricRect, Shadow as FabricShadow, Pattern as FabricPattern } from 'fabric'
import { useManualStore } from '@/stores/manualStore'

const router = useRouter()
const route = useRoute()

const manualStore = useManualStore()

const POSTER_CANVAS_WIDTH = 1080
const POSTER_CANVAS_HEIGHT = 1920
const DRAFT_KEY = 'posterCanvasDraft'

const canvasEl = ref(null)
const stageRef = ref(null)
const imageInputRef = ref(null)
const objToolbarRef = ref(null)
const objSizeTagRef = ref(null)

const canvasInstance = ref(null)
const zoom = ref(1)

const initError = ref('')

const objOverlay = reactive({
  visible: false,
  left: 0,
  top: 0,
  placement: 'top',
  sizeVisible: false,
  sizeLeft: 0,
  sizeTop: 0,
  sizeText: '',
})

const resizeOverlay = reactive({
  visible: false,
  handles: [],
})

const resizeState = reactive({
  active: false,
  corner: '',
  oppCorner: '',
  startDist: 1,
  startScaleX: 1,
  startScaleY: 1,
  anchor: { x: 0, y: 0 },
  obj: null,
})

const isSpaceDown = ref(false)
const isPanning = ref(false)
const lastPan = reactive({ x: 0, y: 0 })
const artboard = ref(null)

const clipboard = ref(null)
const clipboardData = ref(null)
const pasteCount = ref(0)

const imageDialogVisible = ref(false)
const imageDialogTab = ref('local')
const kbProductImages = ref([])

const raf = () => new Promise((resolve) => requestAnimationFrame(() => resolve()))

const waitForStageSize = async () => {
  const stage = stageRef.value
  if (!stage) return { w: 0, h: 0 }

  for (let i = 0; i < 30; i++) {
    const w = stage.clientWidth
    const h = stage.clientHeight
    if (w > 0 && h > 0) return { w, h }
    await raf()
  }
  return { w: stage.clientWidth, h: stage.clientHeight }
}

const applySelectionStyle = (obj) => {
  if (!obj) return
  // Skip background-like objects
  if (obj?.data?.role === 'artboard') return
  try {
    obj.set({
      selectable: true,
      evented: true,
      hasControls: true,
      hasBorders: true,
      lockScalingX: false,
      lockScalingY: false,
      lockUniScaling: false,
      lockRotation: false,
      lockSkewingX: false,
      lockSkewingY: false,
      lockMovementX: false,
      lockMovementY: false,
    })
  } catch (e) {}
  try {
    obj.set({
      borderColor: 'rgba(59, 130, 246, 0.95)',
      cornerColor: '#ffffff',
      cornerStrokeColor: 'rgba(59, 130, 246, 0.95)',
      cornerStyle: 'circle',
      cornerSize: 14,
      touchCornerSize: 30,
      transparentCorners: false,
      borderScaleFactor: 1,
      padding: 0,
    })
  } catch (e) {
    // ignore
  }

  if (obj?.type === 'image') {
    try {
      obj.set({
        hasControls: false,
        hasBorders: true,
        lockScalingFlip: true,
        lockUniScaling: true,
        selectable: true,
        evented: true,
        lockScalingX: false,
        lockScalingY: false,
        cornerSize: 22,
        touchCornerSize: 44,
        padding: 6,
      })
      if (typeof obj.setControlsVisibility === 'function') {
        obj.setControlsVisibility({
          tl: false,
          tr: false,
          bl: false,
          br: false,
          mt: false,
          mb: false,
          ml: false,
          mr: false,
          mtr: false,
        })
      }
    } catch (e) {
      // ignore
    }
  }

  try {
    if (obj && typeof obj.setCoords === 'function') obj.setCoords()
  } catch (e) {}
}

const applySelectionStyleToAll = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  try {
    canvas.getObjects().forEach((o) => applySelectionStyle(o))
  } catch (e) {
    // ignore
  }
}

const clamp = (v, min, max) => (v < min ? min : v > max ? max : v)

const _cornerIndex = (k) => {
  if (k === 'tl') return 0
  if (k === 'tr') return 1
  if (k === 'br') return 2
  if (k === 'bl') return 3
  return 0
}

const _oppCornerKey = (k) => {
  if (k === 'tl') return 'br'
  if (k === 'tr') return 'bl'
  if (k === 'br') return 'tl'
  if (k === 'bl') return 'tr'
  return 'br'
}

const _dist = (a, b) => {
  const dx = (a?.x || 0) - (b?.x || 0)
  const dy = (a?.y || 0) - (b?.y || 0)
  return Math.hypot(dx, dy)
}

const onResizeHandleMove = (e) => {
  if (!resizeState.active) return
  if (resizeState.pointerId != null && e?.pointerId != null && e.pointerId !== resizeState.pointerId) return
  const canvas = canvasInstance.value
  const obj = resizeState.obj
  if (!canvas || !obj) return

  try {
    const pointer = canvas.getPointer(e)
    const ratio = _dist(pointer, resizeState.anchor) / (resizeState.startDist || 1)
    const base = resizeState.startScaleX || 1
    const s = clamp(base * ratio, 0.02, 50)
    obj.set({ scaleX: s, scaleY: s })
    if (typeof obj.setCoords === 'function') obj.setCoords()

    // Keep opposite corner fixed in absolute coordinates
    const coords = typeof obj.getCoords === 'function' ? obj.getCoords() : null
    if (coords && coords.length >= 4) {
      const idxOpp = _cornerIndex(resizeState.oppCorner)
      const nowAnchor = coords[idxOpp]
      const dx = (resizeState.anchor?.x || 0) - (nowAnchor?.x || 0)
      const dy = (resizeState.anchor?.y || 0) - (nowAnchor?.y || 0)
      obj.set({ left: (obj.left || 0) + dx, top: (obj.top || 0) + dy })
      if (typeof obj.setCoords === 'function') obj.setCoords()
    }
  } catch (err) {
    // ignore
  }

  try {
    canvas.requestRenderAll()
  } catch (e2) {}
  updateObjOverlay()
}

const onResizeHandleUp = (e) => {
  if (!resizeState.active) return
  if (resizeState.pointerId != null && e?.pointerId != null && e.pointerId !== resizeState.pointerId) return
  resizeState.active = false
  resizeState.obj = null
  resizeState.pointerId = null
  try {
    window.removeEventListener('pointermove', onResizeHandleMove, true)
    window.removeEventListener('pointerup', onResizeHandleUp, true)
    window.removeEventListener('pointercancel', onResizeHandleUp, true)
  } catch (err) {}
}

const onResizeHandleDown = (cornerKey, e) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || obj.type !== 'image') return
  if (!e) return

  try {
    e.preventDefault()
    e.stopPropagation()
  } catch (err) {}

  try {
    if (e.currentTarget && typeof e.currentTarget.setPointerCapture === 'function') {
      e.currentTarget.setPointerCapture(e.pointerId)
    }
  } catch (err) {}

  try {
    if (typeof obj.setCoords === 'function') obj.setCoords()
  } catch (err) {}

  const coords = typeof obj.getCoords === 'function' ? obj.getCoords() : null
  if (!coords || coords.length < 4) return

  const oppCorner = _oppCornerKey(cornerKey)
  const idxOpp = _cornerIndex(oppCorner)
  const anchor = coords[idxOpp]
  const pointer = canvas.getPointer(e)
  const startDist = Math.max(1e-6, _dist(pointer, anchor))

  resizeState.active = true
  resizeState.corner = cornerKey
  resizeState.oppCorner = oppCorner
  resizeState.startDist = startDist
  resizeState.startScaleX = Number(obj.scaleX ?? 1) || 1
  resizeState.startScaleY = Number(obj.scaleY ?? 1) || 1
  resizeState.anchor = { x: anchor.x, y: anchor.y }
  resizeState.obj = obj
  resizeState.pointerId = e.pointerId

  try {
    window.addEventListener('pointermove', onResizeHandleMove, true)
    window.addEventListener('pointerup', onResizeHandleUp, true)
    window.addEventListener('pointercancel', onResizeHandleUp, true)
  } catch (err) {}
}

const recalcAllObjectCoords = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  try {
    canvas.getObjects().forEach((o) => {
      try { if (o && typeof o.setCoords === 'function') o.setCoords() } catch (e) {}
    })
  } catch (e) {}
}

const applyZoom = () => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage) return
  const z = zoom.value || 1
  const w = stage.clientWidth
  const h = stage.clientHeight
  if (!w || !h) return

  const vt = canvas.viewportTransform || [z, 0, 0, z, w / 2, h / 2]
  const tx = vt[4]
  const ty = vt[5]

  try {
    canvas.setViewportTransform([z, 0, 0, z, tx, ty])
    recalcAllObjectCoords()
    canvas.calcOffset()
    canvas.requestRenderAll()
  } catch (e) {
    // ignore
  }
  updateObjOverlay()
}

const fitToScreen = () => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage) return
  const w = stage.clientWidth
  const h = stage.clientHeight
  if (!w || !h) return

  const pad = 160
  const z = Math.min((w - pad) / POSTER_CANVAS_WIDTH, (h - pad) / POSTER_CANVAS_HEIGHT, 1)
  zoom.value = clamp(z, 0.1, 3)

  // Center the poster artboard in the viewport
  const tx = w / 2 - (POSTER_CANVAS_WIDTH * zoom.value) / 2
  const ty = h / 2 - (POSTER_CANVAS_HEIGHT * zoom.value) / 2

  try {
    canvas.setViewportTransform([zoom.value, 0, 0, zoom.value, tx, ty])
    recalcAllObjectCoords()
    canvas.calcOffset()
    canvas.requestRenderAll()
  } catch (e) {
    // ignore
  }
  updateObjOverlay()
}

const getViewportCenterInWorld = () => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage) return { x: 0, y: 0 }
  const w = stage.clientWidth
  const h = stage.clientHeight
  const vt = canvas.viewportTransform || [1, 0, 0, 1, w / 2, h / 2]
  const z = vt[0] || 1
  const tx = vt[4] || 0
  const ty = vt[5] || 0
  return {
    x: (w / 2 - tx) / z,
    y: (h / 2 - ty) / z,
  }
}

const transformPoint = (pt, m) => {
  const x = pt?.x || 0
  const y = pt?.y || 0
  const a = m?.[0] ?? 1
  const b = m?.[1] ?? 0
  const c = m?.[2] ?? 0
  const d = m?.[3] ?? 1
  const e = m?.[4] ?? 0
  const f = m?.[5] ?? 0
  return { x: a * x + c * y + e, y: b * x + d * y + f }
}

const getScreenRectForObject = (obj) => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage || !obj) return null

  // Use world-space bounding rect, then transform into viewport using viewportTransform.
  try {
    if (typeof obj.setCoords === 'function') obj.setCoords()
  } catch (e) {}

  let r = null
  try {
    r = obj.getBoundingRect?.(true, true)
  } catch (e) {
    r = null
  }
  if (!r) return null

  const vpt = canvas.viewportTransform || [1, 0, 0, 1, 0, 0]
  const ptsWorld = [
    { x: r.left, y: r.top },
    { x: r.left + r.width, y: r.top },
    { x: r.left + r.width, y: r.top + r.height },
    { x: r.left, y: r.top + r.height },
  ]
  const ptsViewport = ptsWorld.map((p) => transformPoint(p, vpt))
  const xs = ptsViewport.map((p) => p.x)
  const ys = ptsViewport.map((p) => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)

  const upper = canvas.upperCanvasEl
  if (!upper) return null
  const canvasRect = upper.getBoundingClientRect()
  const stageRect = stage.getBoundingClientRect()
  const logicalW = typeof canvas.getWidth === 'function' ? (canvas.getWidth() || 1) : 1
  const logicalH = typeof canvas.getHeight === 'function' ? (canvas.getHeight() || 1) : 1
  const ratioX = (canvasRect.width || 1) / logicalW
  const ratioY = (canvasRect.height || 1) / logicalH
  const offsetX = canvasRect.left - stageRect.left
  const offsetY = canvasRect.top - stageRect.top

  const left = offsetX + minX * ratioX
  const top = offsetY + minY * ratioY
  const right = offsetX + maxX * ratioX
  const bottom = offsetY + maxY * ratioY
  return {
    left,
    top,
    width: right - left,
    height: bottom - top,
    centerX: (left + right) / 2,
    centerY: (top + bottom) / 2,
    right,
    bottom,
    topRight: { x: right, y: top },
  }
}

const updateObjOverlay = () => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage) return
  const obj = canvas.getActiveObject()

  if (!obj || obj.type !== 'image') {
    objOverlay.visible = false
    objOverlay.sizeVisible = false
    resizeOverlay.visible = false
    return
  }

  const sr = getScreenRectForObject(obj)
  if (!sr) {
    objOverlay.visible = false
    objOverlay.sizeVisible = false
    resizeOverlay.visible = false
    return
  }

  if (!Number.isFinite(sr.centerX) || !Number.isFinite(sr.top) || !Number.isFinite(sr.bottom)) {
    objOverlay.visible = false
    objOverlay.sizeVisible = false
    resizeOverlay.visible = false
    return
  }

  const gap = 26
  const preferTop = sr.top > 72
  objOverlay.placement = preferTop ? 'top' : 'bottom'
  objOverlay.visible = true
  objOverlay.left = Math.max(12, Math.min(sr.centerX, stage.clientWidth - 12))
  objOverlay.top = preferTop ? (sr.top - gap) : (sr.bottom + gap)

  const getScaledDim = (o, key) => {
    try {
      if (key === 'w' && typeof o.getScaledWidth === 'function') return o.getScaledWidth()
      if (key === 'h' && typeof o.getScaledHeight === 'function') return o.getScaledHeight()
    } catch (e) {}
    const base = key === 'w' ? (o.width || 0) : (o.height || 0)
    const scale = key === 'w' ? (o.scaleX || 1) : (o.scaleY || 1)
    return base * scale
  }
  const wText = Math.max(1, Math.round(Math.abs(getScaledDim(obj, 'w'))))
  const hText = Math.max(1, Math.round(Math.abs(getScaledDim(obj, 'h'))))
  objOverlay.sizeText = `${wText} × ${hText}`
  objOverlay.sizeVisible = true
  objOverlay.sizeLeft = Math.max(12, Math.min((sr.topRight?.x ?? sr.right) - 4, stage.clientWidth - 12))
  objOverlay.sizeTop = Math.max(12, Math.min((sr.topRight?.y ?? sr.top) - 4, stage.clientHeight - 12))

  resizeOverlay.visible = true
  resizeOverlay.handles = [
    { key: 'tl', x: sr.left, y: sr.top },
    { key: 'tr', x: sr.right, y: sr.top },
    { key: 'br', x: sr.right, y: sr.bottom },
    { key: 'bl', x: sr.left, y: sr.bottom },
  ]

  // Avoid overlap between toolbar and size tag
  try {
    const tbEl = objToolbarRef.value
    const tgEl = objSizeTagRef.value
    if (tbEl && tgEl) {
      requestAnimationFrame(() => {
        try {
          const stageRect = stage.getBoundingClientRect()
          const tb = tbEl.getBoundingClientRect()
          const tg = tgEl.getBoundingClientRect()
          const tbR = {
            left: tb.left - stageRect.left,
            top: tb.top - stageRect.top,
            right: tb.right - stageRect.left,
            bottom: tb.bottom - stageRect.top,
          }
          const tgR = {
            left: tg.left - stageRect.left,
            top: tg.top - stageRect.top,
            right: tg.right - stageRect.left,
            bottom: tg.bottom - stageRect.top,
            width: tg.width,
            height: tg.height,
          }
          const overlap = !(tgR.right < tbR.left || tgR.left > tbR.right || tgR.bottom < tbR.top || tgR.top > tbR.bottom)
          if (!overlap) return

          const stageW = stage.clientWidth || 1
          const stageH = stage.clientHeight || 1
          const clampX = (x) => Math.max(12, Math.min(x, stageW - 12))
          const clampY = (y) => Math.max(12, Math.min(y, stageH - 12))
          const rectFromAnchor = (anchorLeft, anchorTop) => {
            // size tag uses transform translate(-100%, -100%), so anchor point is its bottom-right
            const left = anchorLeft - tgR.width
            const top = anchorTop - tgR.height
            return { left, top, right: left + tgR.width, bottom: top + tgR.height }
          }
          const overlapsToolbar = (r) => !(r.right < tbR.left || r.left > tbR.right || r.bottom < tbR.top || r.top > tbR.bottom)
          const withinStage = (r) => r.left >= 0 && r.top >= 0 && r.right <= stageW && r.bottom <= stageH

          // Candidates (anchors are bottom-right points)
          const candidates = [
            // 1) below toolbar (right aligned)
            { left: clampX(tbR.right), top: clampY(tbR.bottom + 10 + tgR.height) },
            // 2) above toolbar
            { left: clampX(tbR.right), top: clampY(tbR.top - 10) },
            // 3) below object (right aligned)
            { left: clampX(sr.right), top: clampY(sr.bottom + 10 + tgR.height) },
            // 4) above object
            { left: clampX(sr.right), top: clampY(sr.top - 10) },
          ]

          for (const c of candidates) {
            const r2 = rectFromAnchor(c.left, c.top)
            if (!withinStage(r2)) continue
            if (overlapsToolbar(r2)) continue
            objOverlay.sizeLeft = c.left
            objOverlay.sizeTop = c.top
            return
          }

          // Fallback: put it at toolbar right-below even if clipped
          objOverlay.sizeLeft = clampX(tbR.right)
          objOverlay.sizeTop = clampY(tbR.bottom + 10 + tgR.height)
        } catch (e) {}
      })
    }
  } catch (e) {}
}

const resizeCanvasToStage = () => {
  const canvas = canvasInstance.value
  const stage = stageRef.value
  if (!canvas || !stage) return
  const w = stage.clientWidth
  const h = stage.clientHeight
  if (!w || !h) return
  try {
    if (typeof canvas.setDimensions === 'function') {
      canvas.setDimensions({ width: w, height: h })
    } else {
      canvas.setWidth(w)
      canvas.setHeight(h)
    }
  } catch (e) {
    canvas.setWidth(w)
    canvas.setHeight(h)
  }
  canvas.calcOffset()
  canvas.requestRenderAll()
  updateObjOverlay()
}

const initCanvas = async () => {
  if (canvasInstance.value) return
  await nextTick()
  if (!canvasEl.value) return

  initError.value = ''

  try {
    const { w, h } = await waitForStageSize()

    const canvas = new FabricCanvas(canvasEl.value, {
      width: w || 300,
      height: h || 300,
      preserveObjectStacking: true,
      selection: true,
      enableRetinaScaling: true,
      targetFindTolerance: 18,
      perPixelTargetFind: false,
    })

    // Important: set instance early so resizeCanvasToStage() can update dimensions and calcOffset
    canvasInstance.value = canvas
    try { window.__posterCanvas = canvas } catch (e) {}

    // Selection style polish (Fabric v6)
    try {
      canvas.selectionColor = 'rgba(59, 130, 246, 0.12)'
      canvas.selectionBorderColor = 'rgba(59, 130, 246, 0.9)'
      canvas.selectionLineWidth = 1
    } catch (e) {}

    // Make corner scaling proportional by default
    try {
      canvas.uniformScaling = true
    } catch (e) {}

    try {
      canvas.targetFindTolerance = 18
      canvas.perPixelTargetFind = false
    } catch (e) {}

    canvas.on('object:added', (opt) => {
      const t = opt?.target
      if (t) applySelectionStyle(t)
    })

    // Infinite dot grid background (scales with viewport)
    try {
      canvas.backgroundVpt = true
      const p = document.createElement('canvas')
      const s = 36
      p.width = s
      p.height = s
      const ctx = p.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, s, s)
        ctx.fillStyle = 'rgba(17, 24, 39, 0.18)'
        ctx.beginPath()
        ctx.arc(s / 2, s / 2, 1.9, 0, Math.PI * 2)
        ctx.fill()
      }
      if (typeof FabricPattern === 'function') {
        canvas.backgroundColor = new FabricPattern({ source: p, repeat: 'repeat' })
      }
    } catch (e) {
      // ignore
    }

    // Ensure stage size is applied
    await raf()
    resizeCanvasToStage()
    try {
      if (canvas.upperCanvasEl) canvas.upperCanvasEl.draggable = false
      if (canvas.lowerCanvasEl) canvas.lowerCanvasEl.draggable = false
      if (canvas.upperCanvasEl) canvas.upperCanvasEl.style.touchAction = 'none'
      if (canvas.lowerCanvasEl) canvas.lowerCanvasEl.style.touchAction = 'none'
    } catch (e) {}
    canvas.requestRenderAll()

    canvas.on('mouse:dblclick', (opt) => {
      const target = opt?.target
      if (!target) return
      if (typeof target.enterEditing === 'function') {
        try {
          canvas.setActiveObject(target)
          target.enterEditing()
          if (typeof target.hiddenTextarea?.focus === 'function') {
            target.hiddenTextarea.focus()
          }
        } catch (e) {
          // ignore
        }
      }
    })

    canvas.on('mouse:down', (opt) => {
      try {
        if (!window.__posterDebug) return
      } catch (e) {
        return
      }
      try {
        const e = opt?.e
        const t = opt?.target
        const corner = opt?.corner || t?.__corner
        const tr = canvas._currentTransform
        // eslint-disable-next-line no-console
        console.log('[PosterDebug] down', {
          button: e?.button,
          hasTarget: !!t,
          targetType: t?.type,
          corner,
          action: tr?.action,
          transformTargetType: tr?.target?.type,
        })
      } catch (e) {}
    })

    // Ctrl+wheel zoom to pointer
    canvas.on('mouse:wheel', (opt) => {
      const e = opt.e
      if (!e) return
      if (!e.ctrlKey) return

      e.preventDefault()
      e.stopPropagation()

      const delta = e.deltaY
      let z = zoom.value || 1
      z *= Math.pow(0.999, delta)
      z = clamp(z, 0.1, 3)
      zoom.value = z

      const point = new FabricPoint(e.offsetX, e.offsetY)
      try {
        canvas.zoomToPoint(point, z)
        recalcAllObjectCoords()
        canvas.calcOffset()
        canvas.requestRenderAll()
      } catch (err) {
        // ignore
      }
      updateObjOverlay()
    })

    // Panning: Space + drag OR middle mouse drag
    canvas.on('mouse:down', (opt) => {
      const e = opt.e
      if (!e) return
      const isMiddle = e.button === 1
      const hasTarget = !!opt?.target
      // If user is interacting with an object/controls, never enter panning mode
      if (hasTarget) {
        isPanning.value = false
        return
      }
      // If Fabric is already transforming, do not pan
      try {
        if (canvas._currentTransform) {
          isPanning.value = false
          return
        }
      } catch (err) {}
      // Only pan when:
      // - middle mouse button, OR
      // - space is held AND user starts drag from empty canvas area
      if (!isMiddle && !(e.button === 0 && isSpaceDown.value && !hasTarget)) return
      isPanning.value = true
      lastPan.x = e.clientX
      lastPan.y = e.clientY
      if (!hasTarget) {
        canvas.discardActiveObject()
        canvas.requestRenderAll()
      }
    })
    canvas.on('mouse:move', (opt) => {
      if (!isPanning.value) return
      // If Fabric starts a transform, stop panning immediately
      try {
        if (canvas._currentTransform) {
          isPanning.value = false
          return
        }
      } catch (err) {}
      const e = opt.e
      if (!e) return
      const dx = e.clientX - lastPan.x
      const dy = e.clientY - lastPan.y
      lastPan.x = e.clientX
      lastPan.y = e.clientY
      try {
        if (typeof canvas.relativePan === 'function') {
          canvas.relativePan(new FabricPoint(dx, dy))
        } else {
          const vt = (canvas.viewportTransform || [1, 0, 0, 1, 0, 0]).slice()
          vt[4] += dx
          vt[5] += dy
          canvas.setViewportTransform(vt)
        }
        recalcAllObjectCoords()
        canvas.calcOffset()
      } catch (e2) {
        // ignore
      }
      canvas.requestRenderAll()
      updateObjOverlay()
    })
    canvas.on('mouse:up', () => {
      isPanning.value = false
    })

    canvas.on('selection:created', () => {
      recalcAllObjectCoords()
      updateObjOverlay()
    })
    canvas.on('selection:updated', () => {
      recalcAllObjectCoords()
      updateObjOverlay()
    })
    canvas.on('selection:cleared', () => {
      updateObjOverlay()
      resizeOverlay.visible = false
      resizeState.active = false
    })
    canvas.on('object:moving', updateObjOverlay)
    canvas.on('object:scaling', (opt) => {
      const t = opt?.target
      if (t && t.type === 'image') {
        try {
          const sx = Number(t.scaleX ?? 1)
          const sy = Number(t.scaleY ?? 1)
          if (Number.isFinite(sx) && Number.isFinite(sy) && Math.abs(sx - sy) > 1e-3) {
            const s = (Math.abs(sx) + Math.abs(sy)) / 2
            t.set({ scaleX: s, scaleY: s })
          }
          if (typeof t.setCoords === 'function') t.setCoords()
        } catch (e) {}
      }
      updateObjOverlay()
    })
    canvas.on('object:rotating', updateObjOverlay)

    canvasInstance.value = canvas
    try { window.__posterCanvas = canvas } catch (e) {}
    zoom.value = 1
    fitToScreen()

    // After viewport transform and initial DOM layout, re-calc offsets to ensure drag hit-testing works
    try {
      await raf()
      if (canvas.upperCanvasEl) canvas.upperCanvasEl.style.pointerEvents = 'auto'
      canvas.calcOffset()
    } catch (e) {}

    // Optional restore from previous draft
    let raw = ''
    try { raw = sessionStorage.getItem(DRAFT_KEY) || '' } catch (e) { raw = '' }
    if (raw) {
      try {
        await ElMessageBox.confirm('检测到上次编辑的草稿，是否恢复？', '恢复草稿', {
          confirmButtonText: '恢复',
          cancelButtonText: '不恢复',
          type: 'info',
        })
        await loadDraft()
        applySelectionStyleToAll()
        fitToScreen()
      } catch (e) {
        // user canceled
      }
    }
  } catch (e) {
    console.error('PosterCanvasEditor init failed:', e)
    initError.value = e?.message ? `初始化失败：${e.message}` : '初始化失败（请打开控制台查看错误）'
    try { ElMessage.error(initError.value) } catch (err) {}
  }
}

const disposeCanvas = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  try {
    canvas.dispose()
  } catch (e) {
    // ignore
  }
  canvasInstance.value = null
}

const resetCanvas = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  canvas.clear()
  // keep background
  try { canvas.requestRenderAll() } catch (e) {}
  objOverlay.visible = false
  zoom.value = 1
  fitToScreen()
}

const addText = () => {
  const canvas = canvasInstance.value
  if (!canvas) {
    ElMessage.error('画布未初始化成功')
    return
  }
  const c = getViewportCenterInWorld()
  const tb = new FabricTextbox('双击编辑文字', {
    left: c.x - 200,
    top: c.y - 40,
    width: 520,
    fontFamily: 'sans-serif',
    fontSize: 44,
    fill: '#111827',
    fontWeight: 'normal',
  })
  tb.editable = true
  applySelectionStyle(tb)
  canvas.add(tb)
  canvas.setActiveObject(tb)
  canvas.requestRenderAll()
  updateObjOverlay()
}

const triggerPickImage = () => {
  imageDialogTab.value = 'local'
  refreshKbProductImages()
  imageDialogVisible.value = true
}

const triggerLocalImageUpload = () => {
  if (imageInputRef.value) imageInputRef.value.click()
}

const insertImageFromUrl = async (url) => {
  if (!url) return
  const canvas = canvasInstance.value
  if (!canvas) {
    ElMessage.error('画布未初始化成功')
    return
  }
  const c = getViewportCenterInWorld()
  try {
    const img = await FabricImage.fromURL(url, { crossOrigin: 'anonymous' })
    const maxW = POSTER_CANVAS_WIDTH * 0.7
    const maxH = POSTER_CANVAS_HEIGHT * 0.7
    const rawW = img?.width || 1
    const rawH = img?.height || 1
    const scale = Math.min(maxW / rawW, maxH / rawH, 1)
    img.set({
      left: c.x - (rawW * scale) / 2,
      top: c.y - (rawH * scale) / 2,
      scaleX: scale,
      scaleY: scale,
    })
    try {
      if (typeof img.setControlsVisibility === 'function') {
        img.setControlsVisibility({
          tl: true,
          tr: true,
          bl: true,
          br: true,
          mt: true,
          mb: true,
          ml: true,
          mr: true,
          mtr: true,
        })
      }
    } catch (e) {}
    applySelectionStyle(img)
    try { if (typeof img.setCoords === 'function') img.setCoords() } catch (e) {}
    canvas.add(img)
    canvas.setActiveObject(img)
    canvas.requestRenderAll()
    updateObjOverlay()
  } catch (err) {
    ElMessage.error('图片加载失败，请重试')
  }
}

const onPickImage = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return

  const reader = new FileReader()
  reader.onload = async () => {
    const url = reader.result
    await insertImageFromUrl(url)
  }
  reader.readAsDataURL(f)
  try { e.target.value = '' } catch (err) {}
  imageDialogVisible.value = false
}

const selectKbProductImage = async (src) => {
  if (!src) return
  imageDialogVisible.value = false
  await insertImageFromUrl(src)
}

const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif']
const DEFAULT_KB_PRODUCT_IMAGES = []

const toPublicFileUrl = (value = '') => {
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  const normalized = value.replace(/^\/api\/files\//, '').replace(/^\/+/, '')
  return `/api/files/${normalized}`
}

const isProductCandidateImage = (src = '') => {
  const lower = String(src || '').toLowerCase()
  if (!lower) return false
  if (lower.includes('result_with_boxes')) return false
  return lower.includes('/images/')
}

const isImageLike = (item = {}) => {
  const mime = (item.mime_type || item.mime || item.kind || item.type || '').toLowerCase()
  if (mime.startsWith('image/')) return true
  const nameOrPath = (item.url || item.path || item.name || '').toLowerCase()
  return IMAGE_EXTENSIONS.some((ext) => nameOrPath.endsWith(ext))
}

const collectImageEntriesFromGroups = (groups = [], bucket, seen) => {
  groups.forEach((group) => {
    ;(group.pages || []).forEach((page) => {
      ;(page.artifacts || []).forEach((artifact) => {
        if (!isImageLike(artifact)) return
        const src = artifact.url || toPublicFileUrl(artifact.path)
        if (!src || seen.has(src)) return
        bucket.push({ src, label: artifact.name || artifact.caption || artifact.path || 'OCR 图片' })
        seen.add(src)
      })
    })
  })
}

const ragImageEntries = computed(() => {
  const images = []
  const seen = new Set()

  collectImageEntriesFromGroups(manualStore.productOcrGroups || [], images, seen)
  ;(manualStore.productOcrFiles || []).forEach((file) => {
    if (!isImageLike(file)) return
    const src = file.url || toPublicFileUrl(file.path)
    if (!src || seen.has(src)) return
    images.push({ src, label: file.name || file.caption || file.path || 'OCR 图片' })
    seen.add(src)
  })

  return images
})

const refreshKbProductImages = () => {
  const images = []
  const seen = new Set()
  ;(DEFAULT_KB_PRODUCT_IMAGES || []).forEach((img) => {
    if (!img?.src || seen.has(img.src)) return
    images.push({ src: img.src, label: img.label || img.src })
    seen.add(img.src)
  })
  ;(ragImageEntries.value || []).forEach((img) => {
    if (!img?.src || seen.has(img.src)) return
    if (!isProductCandidateImage(img.src)) return
    images.push({ src: img.src, label: img.label || img.src })
    seen.add(img.src)
  })
  kbProductImages.value = images
}

const incZoom = () => {
  zoom.value = clamp((zoom.value || 1) + 0.1, 0.2, 3)
  applyZoom()
}
const decZoom = () => {
  zoom.value = clamp((zoom.value || 1) - 0.1, 0.2, 3)
  applyZoom()
}
const resetZoom = () => {
  fitToScreen()
}

const serializeCanvas = () => {
  const canvas = canvasInstance.value
  if (!canvas) return null
  return JSON.stringify(canvas.toJSON())
}

const saveDraft = () => {
  const json = serializeCanvas()
  if (!json) return
  try {
    sessionStorage.setItem(DRAFT_KEY, json)
    ElMessage.success('已保存草稿')
  } catch (e) {
    ElMessage.error('保存草稿失败')
  }
}

const loadDraft = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return

  let raw = ''
  try {
    raw = sessionStorage.getItem(DRAFT_KEY) || ''
  } catch (e) {
    raw = ''
  }
  if (!raw) return

  try {
    const json = JSON.parse(raw)
    await canvas.loadFromJSON(json)
    canvas.requestRenderAll()
  } catch (e) {
    // ignore
  }
}

const exportPng = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const objs = canvas.getObjects().filter((o) => o && o.visible !== false)
  if (!objs.length) {
    ElMessage.warning('画布为空')
    return
  }
  const rects = objs.map((o) => o.getBoundingRect(true, true))
  const left = Math.min(...rects.map((r) => r.left))
  const top = Math.min(...rects.map((r) => r.top))
  const right = Math.max(...rects.map((r) => r.left + r.width))
  const bottom = Math.max(...rects.map((r) => r.top + r.height))
  const imgData = canvas.toDataURL({
    format: 'png',
    multiplier: 3,
    left,
    top,
    width: right - left,
    height: bottom - top,
  })
  const a = document.createElement('a')
  a.href = imgData
  a.download = `海报.png`
  a.click()
}

const downloadActive = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片')
    return
  }

  // Export selected object by rendering it into an offscreen canvas.
  // This avoids all viewportTransform/retina/cropping coordinate pitfalls.
  const rect = obj.getBoundingRect(false, true)
  const pad = 2
  const w = Math.max(1, Math.ceil(rect.width + pad * 2))
  const h = Math.max(1, Math.ceil(rect.height + pad * 2))

  const offEl = document.createElement('canvas')
  offEl.width = w
  offEl.height = h
  const off = new FabricCanvas(offEl, {
    width: w,
    height: h,
    preserveObjectStacking: true,
  })

  try {
    let cloned = null
    try {
      cloned = await cloneObject(obj)
    } catch (e) {
      // Fallback for images: recreate from element src
      const el = obj.getElement && obj.getElement()
      const src = el?.currentSrc || el?.src
      if (src) {
        cloned = await FabricImage.fromURL(src, { crossOrigin: 'anonymous' })
        cloned.set({
          scaleX: obj.scaleX,
          scaleY: obj.scaleY,
          angle: obj.angle,
          flipX: obj.flipX,
          flipY: obj.flipY,
          skewX: obj.skewX,
          skewY: obj.skewY,
          opacity: obj.opacity,
        })
      }
    }
    if (!cloned) throw new Error('clone failed')

    // Place the cloned object so its world-space bounding rect aligns with offscreen origin
    const cloneRect = cloned.getBoundingRect(false, true)
    cloned.set({ left: (cloned.left || 0) - cloneRect.left + pad, top: (cloned.top || 0) - cloneRect.top + pad })
    off.add(cloned)
    off.requestRenderAll()
    const imgData = off.toDataURL({ format: 'png', multiplier: 2 })
    const a = document.createElement('a')
    a.href = imgData
    a.download = `对象.png`
    a.click()
  } catch (e) {
    console.error('downloadActive failed:', e)
    ElMessage.error('下载失败')
  } finally {
    try { off.dispose() } catch (e) {}
  }
}

const cloneObject = (obj) => {
  return new Promise((resolve, reject) => {
    try {
      // Fabric v6: clone may return a Promise; older: uses callback
      if (typeof obj.clone !== 'function') throw new Error('Object is not clonable')

      let ret = null
      // Prefer promise form when available (clone has no callback arity)
      if (obj.clone.length === 0) {
        ret = obj.clone()
        if (ret && typeof ret.then === 'function') {
          ret.then(resolve).catch(reject)
          return
        }
        // If it returned synchronously
        if (ret) {
          resolve(ret)
          return
        }
      }

      // Callback form
      ret = obj.clone((cloned) => resolve(cloned))
      if (ret && typeof ret.then === 'function') {
        ret.then(resolve).catch(reject)
      }
    } catch (e) {
      reject(e)
    }
  })
}

const duplicateActive = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj) {
    ElMessage.warning('请先选中一个对象')
    return
  }
  try {
    let cloned = null
    try {
      cloned = await cloneObject(obj)
    } catch (e) {
      // Some image objects fail to clone reliably depending on load state.
      // Fallback: recreate from src element.
      if (obj.type === 'image') {
        const el = obj.getElement && obj.getElement()
        if (el) {
          cloned = await FabricImage.fromURL(el.currentSrc || el.src, { crossOrigin: 'anonymous' })
          cloned.set({
            scaleX: obj.scaleX,
            scaleY: obj.scaleY,
            angle: obj.angle,
          })
        }
      }
      if (!cloned) throw e
    }

    applySelectionStyle(cloned)
    cloned.set({ left: (obj.left || 0) + 24, top: (obj.top || 0) + 24 })
    try { if (typeof cloned.setCoords === 'function') cloned.setCoords() } catch (e) {}
    canvas.add(cloned)
    canvas.setActiveObject(cloned)
    canvas.requestRenderAll()
    updateObjOverlay()
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const removeActive = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj) return
  canvas.remove(obj)
  canvas.discardActiveObject()
  canvas.requestRenderAll()
  updateObjOverlay()
}

const exportPdf = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const objs = canvas.getObjects().filter((o) => o && o.visible !== false)
  if (!objs.length) {
    ElMessage.warning('画布为空')
    return
  }
  const rects = objs.map((o) => o.getBoundingRect(true, true))
  const left = Math.min(...rects.map((r) => r.left))
  const top = Math.min(...rects.map((r) => r.top))
  const right = Math.max(...rects.map((r) => r.left + r.width))
  const bottom = Math.max(...rects.map((r) => r.top + r.height))
  const imgData = canvas.toDataURL({
    format: 'png',
    multiplier: 3,
    left,
    top,
    width: right - left,
    height: bottom - top,
  })
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const imgW = pageW
  const imgH = (POSTER_CANVAS_HEIGHT / POSTER_CANVAS_WIDTH) * imgW
  const y = (pageH - imgH) / 2 < 0 ? 0 : (pageH - imgH) / 2
  pdf.addImage(imgData, 'PNG', 0, y, imgW, imgH)
  pdf.save(`海报.pdf`)
}

const handleBack = () => {
  saveDraft()
  if (window.history.length > 1) {
    router.back()
    return
  }
  const returnTo = route.query.returnTo
  if (typeof returnTo === 'string' && returnTo) {
    router.replace(returnTo)
    return
  }
  router.push({ name: 'Home' })
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', onWindowBlur)
  window.addEventListener('mouseup', onWindowMouseUp)
  await initCanvas()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', onWindowBlur)
  window.removeEventListener('mouseup', onWindowMouseUp)
  window.removeEventListener('resize', onResize)
  try {
    window.removeEventListener('pointermove', onResizeHandleMove, true)
    window.removeEventListener('pointerup', onResizeHandleUp, true)
    window.removeEventListener('pointercancel', onResizeHandleUp, true)
  } catch (e) {}
  disposeCanvas()
})

const onWindowBlur = () => {
  isSpaceDown.value = false
  isPanning.value = false
}

const onWindowMouseUp = () => {
  isPanning.value = false
}

const onResize = () => {
  resizeCanvasToStage()
  fitToScreen()
}

const onKeyDown = (e) => {
  if (!e) return
  const tag = (e.target && e.target.tagName) ? String(e.target.tagName).toUpperCase() : ''
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable) {
    return
  }
  const canvas = canvasInstance.value
  const active = canvas ? canvas.getActiveObject() : null
  if (active && active.isEditing) {
    return
  }
  if (e.code === 'Space') {
    isSpaceDown.value = true
    e.preventDefault()
  }
  const isMod = e.ctrlKey || e.metaKey
  if (isMod && (e.key === 'c' || e.key === 'C')) {
    e.preventDefault()
    copyActive()
    return
  }
  if (isMod && (e.key === 'v' || e.key === 'V')) {
    e.preventDefault()
    pasteActive()
    return
  }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault()
    removeActive()
    return
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
    e.preventDefault()
    saveDraft()
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === '0')) {
    e.preventDefault()
    fitToScreen()
  }
}

const onKeyUp = (e) => {
  if (!e) return
  if (e.code === 'Space') {
    isSpaceDown.value = false
  }
}

const rotateActive = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片')
    return
  }
  const nextAngle = ((obj.angle || 0) + 90) % 360
  try {
    obj.rotate(nextAngle)
    if (typeof obj.setCoords === 'function') obj.setCoords()
    canvas.requestRenderAll()
    updateObjOverlay()
  } catch (e) {
    ElMessage.error('旋转失败')
  }
}

const copyActive = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || obj?.data?.role === 'artboard') return
  try {
    let cloned = null
    try {
      cloned = await cloneObject(obj)
    } catch (e) {
      // Fallback for images: recreate from element src
      if (obj.type === 'image') {
        const el = obj.getElement && obj.getElement()
        const src = el?.currentSrc || el?.src
        if (src) {
          cloned = await FabricImage.fromURL(src, { crossOrigin: 'anonymous' })
          cloned.set({
            scaleX: obj.scaleX,
            scaleY: obj.scaleY,
            angle: obj.angle,
            flipX: obj.flipX,
            flipY: obj.flipY,
            skewX: obj.skewX,
            skewY: obj.skewY,
            opacity: obj.opacity,
          })
        }
      }
      if (!cloned) throw e
    }
    applySelectionStyle(cloned)
    clipboard.value = cloned
    if (obj.type === 'image') {
      const el = obj.getElement && obj.getElement()
      const src = el?.currentSrc || el?.src
      clipboardData.value = {
        kind: 'image',
        src,
        props: {
          scaleX: obj.scaleX,
          scaleY: obj.scaleY,
          angle: obj.angle,
          flipX: obj.flipX,
          flipY: obj.flipY,
          skewX: obj.skewX,
          skewY: obj.skewY,
          opacity: obj.opacity,
        },
      }
    } else {
      clipboardData.value = { kind: 'object' }
    }
    pasteCount.value = 0
    ElMessage.success('已复制')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const pasteActive = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const stored = clipboardData.value
  if (!stored) {
    ElMessage.warning('没有可粘贴的内容')
    return
  }
  try {
    let next = null
    if (stored.kind === 'image' && stored.src) {
      next = await FabricImage.fromURL(stored.src, { crossOrigin: 'anonymous' })
      next.set({
        left: 0,
        top: 0,
        ...(stored.props || {}),
      })
    } else if (clipboard.value) {
      next = await cloneObject(clipboard.value)
    }

    if (!next) throw new Error('paste failed')

    applySelectionStyle(next)
    const nudge = 24 * ((pasteCount.value || 0) + 1)
    pasteCount.value = (pasteCount.value || 0) + 1

    const active = canvas.getActiveObject()
    const baseLeft = active?.left ?? next.left ?? 0
    const baseTop = active?.top ?? next.top ?? 0
    next.set({ left: baseLeft + nudge, top: baseTop + nudge })
    try { if (typeof next.setCoords === 'function') next.setCoords() } catch (e) {}

    canvas.add(next)
    canvas.setActiveObject(next)
    canvas.requestRenderAll()
    updateObjOverlay()
  } catch (e) {
    ElMessage.error('粘贴失败')
  }
}
</script>

<style scoped>
.poster-editor-page {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #f3f4f6;
}

.stage {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: #ffffff;
}

.stage canvas {
  display: block;
  pointer-events: auto;
  touch-action: none;
}

.resize-handles {
  position: absolute;
  inset: 0;
  z-index: 42;
  pointer-events: none;
}

.resize-handle {
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  border: 2px solid rgba(59, 130, 246, 0.95);
  box-shadow: 0 6px 16px rgba(17, 24, 39, 0.18);
  transform: translate(-50%, -50%);
  pointer-events: auto;
  touch-action: none;
}

.resize-handle[data-key='tl'],
.resize-handle[data-key='br'] {
  cursor: nwse-resize;
}

.resize-handle[data-key='tr'],
.resize-handle[data-key='bl'] {
  cursor: nesw-resize;
}

.top-left {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 30;
}

.top-right {
  position: absolute;
  right: 14px;
  top: 14px;
  z-index: 30;
}

.zoom-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 999px;
  padding: 6px 10px;
  box-shadow: 0 6px 18px rgba(17, 24, 39, 0.08);
}

.zoom-text {
  min-width: 52px;
  text-align: center;
  font-weight: 600;
  color: #111827;
}

.left-toolbar {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 14px;
  padding: 10px 8px;
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.08);
}

.tool-btn {
  width: 64px;
}

.left-toolbar :deep(.el-button + .el-button) {
  margin-left: 0;
}

.obj-overlay {
  position: absolute;
  z-index: 40;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 10px;
  padding: 6px;
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.14);
}

.obj-toolbar {
  position: absolute;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(17, 24, 39, 0.92);
  box-shadow: 0 18px 40px rgba(17, 24, 39, 0.22);
  backdrop-filter: blur(10px);
  transform: translateX(-50%);
  pointer-events: none;
}

.obj-toolbar[data-place='top'] {
  transform: translate(-50%, -100%);
}

.obj-toolbar[data-place='bottom'] {
  transform: translate(-50%, 0%);
}

.obj-size-tag {
  position: absolute;
  z-index: 41;
  transform: translate(-100%, -100%);
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 8px;
  padding: 2px 6px;
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.14);
  color: rgba(17, 24, 39, 0.9);
  font-size: 10px;
  font-weight: 600;
  pointer-events: none;
}

.obj-toolbar .tool {
  appearance: none;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  font-weight: 600;
  padding: 5px 9px;
  border-radius: 9px;
  cursor: pointer;
  pointer-events: auto;
}

.obj-toolbar .tool:hover {
  background: rgba(255, 255, 255, 0.10);
}

.obj-toolbar .tool.danger {
  color: rgba(248, 113, 113, 0.95);
}

.obj-toolbar .tool.danger:hover {
  background: rgba(248, 113, 113, 0.12);
}

.init-error {
  position: absolute;
  left: 50%;
  top: 18px;
  transform: translateX(-50%);
  z-index: 50;
  max-width: min(720px, calc(100vw - 40px));
  padding: 10px 12px;
  border-radius: 10px;
  color: #7f1d1d;
  background: rgba(254, 226, 226, 0.95);
  border: 1px solid rgba(248, 113, 113, 0.6);
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.14);
  font-size: 13px;
}

 .product-dialog-section .kb-image-grid {
   max-height: 420px;
   overflow: auto;
   display: grid;
   grid-template-columns: repeat(3, minmax(0, 1fr));
   gap: 12px;
   padding-right: 6px;
 }

 .product-dialog-section .kb-image-item {
   cursor: pointer;
   border: 1px solid rgba(229, 231, 235, 0.9);
   border-radius: 10px;
   overflow: hidden;
   background: rgba(255, 255, 255, 0.92);
 }

 .product-dialog-section .kb-image-item img {
   display: block;
   width: 100%;
   height: 110px;
   object-fit: cover;
 }

 .product-dialog-section .kb-image-label {
   font-size: 12px;
   color: rgba(17, 24, 39, 0.82);
   padding: 6px 8px;
   white-space: nowrap;
   overflow: hidden;
   text-overflow: ellipsis;
 }
</style>
