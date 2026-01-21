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
      <div class="top-right-inner">
        <div class="zoom-pill">
          <el-button size="small" text @click="decZoom">-</el-button>
          <div class="zoom-text">{{ Math.round(zoom * 100) }}%</div>
          <el-button size="small" text @click="incZoom">+</el-button>
        </div>
        <el-button class="panel-toggle-btn" size="small" circle :icon="Operation" @click="togglePanel" />
      </div>
    </div>

    <div class="left-toolbar">
      <el-button class="tool-btn" size="small" text @click="addText">文字</el-button>
      <el-button class="tool-btn" size="small" text @click="triggerPickImage">图片</el-button>
    </div>

    <div class="right-panel" :class="{ open: rightPanelOpen }" @click.stop>
      <div class="panel-header">
        <el-radio-group v-model="rightPanelKey" size="small">
          <el-radio-button label="export">导出</el-radio-button>
          <el-radio-button label="layers">图层</el-radio-button>
          <el-radio-button label="props">属性</el-radio-button>
          <el-radio-button label="gen">海报生成</el-radio-button>
        </el-radio-group>
        <el-button size="small" text @click="rightPanelOpen = false">收起</el-button>
      </div>

      <div class="panel-body">
        <template v-if="rightPanelKey === 'export'">
          <div class="panel-actions">
            <el-button type="primary" @click="saveDraft">保存草稿</el-button>
            <el-button @click="exportPng">导出 PNG</el-button>
            <el-button @click="exportPdf">导出 PDF</el-button>
          </div>
        </template>

        <template v-else-if="rightPanelKey === 'layers'">
          <div class="layers-list">
            <div
              v-for="item in layerItems"
              :key="item.id"
              class="layer-item"
              :class="{ active: item.id === activeLayerId }"
              @click="selectLayer(item.id)"
            >
              <div class="layer-name">{{ item.label }}</div>
              <div class="layer-meta">{{ item.meta }}</div>
              <div class="layer-actions" @click.stop>
                <button class="layer-btn" type="button" title="上移一层" :disabled="item.lockedBottom" @click="moveLayerById(item.id, 'up')">上</button>
                <button class="layer-btn" type="button" title="下移一层" :disabled="item.lockedBottom" @click="moveLayerById(item.id, 'down')">下</button>
                <button class="layer-btn" type="button" title="置顶" :disabled="item.lockedBottom" @click="moveLayerById(item.id, 'top')">顶</button>
                <button class="layer-btn" type="button" title="置底" :disabled="item.lockedBottom" @click="moveLayerById(item.id, 'bottom')">底</button>
              </div>
            </div>
            <div v-if="layerItems.length === 0" class="panel-empty">暂无图层</div>
          </div>
        </template>

        <template v-else-if="rightPanelKey === 'props'">
          <div v-if="!activeObject" class="panel-empty">请先选中一个对象</div>
          <div v-else class="props-form">
            <div class="pf-row">
              <div class="pf-label">X</div>
              <el-input-number v-model="propForm.x" :step="1" :controls="true" @change="applyPropForm" />
            </div>
            <div class="pf-row">
              <div class="pf-label">Y</div>
              <el-input-number v-model="propForm.y" :step="1" :controls="true" @change="applyPropForm" />
            </div>
            <div class="pf-row">
              <div class="pf-label">缩放</div>
              <el-input-number v-model="propForm.scale" :step="0.02" :min="0.02" :max="50" :controls="true" @change="applyPropForm" />
            </div>
            <div class="pf-row">
              <div class="pf-label">旋转</div>
              <el-input-number v-model="propForm.angle" :step="1" :min="-360" :max="360" :controls="true" @change="applyPropForm" />
            </div>
            <div class="pf-row">
              <div class="pf-label">透明度</div>
              <el-input-number v-model="propForm.opacity" :step="0.05" :min="0" :max="1" :controls="true" @change="applyPropForm" />
            </div>
          </div>
        </template>

        <template v-else-if="rightPanelKey === 'gen'">
          <div class="gen-layout">
            <div class="gen-col">
              <div class="gen-col-title">上传参考图</div>

              <div class="gen-row">
                <div class="gen-label">参考图</div>
                <div class="gen-actions">
                  <el-button size="small" @click="triggerRefLocalUpload">本地上传</el-button>
                  <el-button size="small" @click="openRefKbPicker">知识库选择</el-button>
                  <el-button size="small" @click="useActiveImageAsRef">使用已选图片</el-button>
                </div>
              </div>

              <div v-if="refPreviewUrl" class="gen-preview">
                <div class="gen-preview-wrap">
                  <img :src="refPreviewUrl" alt="reference" />
                  <div v-if="posterOverlayBoxes.length" class="gen-overlay">
                    <div v-for="box in posterOverlayBoxes" :key="box.key" class="gen-box" :style="box.style">
                      <div class="gen-box-label">{{ box.label }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="panel-empty">请选择一张参考图（支持本地/知识库/画板选中图片）</div>

              <div class="gen-row" style="margin-top: 10px;">
                <el-button type="primary" :loading="posterAnalyzeLoading" @click="analyzeReferenceImage">分析参考图框架</el-button>
                <el-button text :disabled="!posterAnalysisResult && !posterAnalyzeError" @click="clearPosterAnalysis">清空</el-button>
              </div>

              <div v-if="posterAnalyzeError" class="gen-error">{{ posterAnalyzeError }}</div>

              <div class="gen-col gen-col-full" style="margin-top: 10px;">
                <div class="gen-col-title">生成文案</div>
                <el-input
                  v-model="posterStep2Requirements"
                  type="textarea"
                  :rows="4"
                  placeholder="例如：面向美国经销商销售按摩浴缸，主打节能、舒适、易安装"
                />
                <div class="gen-actions" style="margin-top: 10px;">
                  <el-button type="primary" :loading="posterStep2Loading" @click="generatePosterCopyStep2">生成文案</el-button>
                  <el-button text @click="clearStep2Assets">清空素材</el-button>
                  <el-button text @click="clearStep2All">清空</el-button>
                </div>
              </div>

              <div v-if="posterStep2Error" class="gen-error">{{ posterStep2Error }}</div>
            </div>

            <div class="gen-col">
              <div class="gen-col-title">海报框架</div>

              <div class="gen-row" style="margin-top: 10px;">
                <div class="gen-label">尺寸</div>
              </div>
              <div class="gen-size-row">
                <div class="gen-size-item">
                  <div class="gen-size-label">W</div>
                  <el-input-number v-model="posterFramework.size.width" :min="1" :step="10" @change="onFrameworkSizeChange" />
                </div>
                <div class="gen-size-item">
                  <div class="gen-size-label">H</div>
                  <el-input-number v-model="posterFramework.size.height" :min="1" :step="10" @change="onFrameworkSizeChange" />
                </div>
              </div>

              <div class="gen-assets-row" style="margin-top: 10px;">
                <div class="gen-asset-block">
                  <div class="gen-row">
                    <div class="gen-label">背景图</div>
                  </div>
                  <div class="gen-actions gen-actions-compact">
                    <el-button size="small" @click="triggerStep2BackgroundUpload">本地上传</el-button>
                    <el-button size="small" @click="openStep2BackgroundKbPicker">知识库选择</el-button>
                    <el-button size="small" @click="useActiveImageAsStep2Background">使用已选图片</el-button>
                  </div>
                  <div v-if="step2BackgroundPreviewUrl" class="gen-asset-preview gen-asset-preview--small">
                    <img :src="step2BackgroundPreviewUrl" alt="background" />
                  </div>
                </div>

                <div class="gen-asset-block">
                  <div class="gen-row">
                    <div class="gen-label">产品图</div>
                  </div>
                  <div class="gen-actions gen-actions-compact">
                    <el-button size="small" @click="triggerStep2ProductUpload">本地上传</el-button>
                    <el-button size="small" @click="openStep2ProductKbPicker">知识库选择</el-button>
                    <el-button size="small" @click="useActiveImageAsStep2Product">使用已选图片</el-button>
                  </div>
                  <div v-if="step2ProductPreviewUrl" class="gen-asset-preview gen-asset-preview--small">
                    <img :src="step2ProductPreviewUrl" alt="product" />
                  </div>
                </div>
              </div>

              <div class="gen-row" style="margin-top: 10px;">
                <div class="gen-label">标题文字</div>
              </div>
              <div class="gen-text-with-icons">
                <el-input v-model="posterFramework.text.title" placeholder="标题" />
                <div class="gen-icon-editor">
                  <div class="gen-icon-actions">
                    <el-button size="small" text @click="openIconPicker('title')">添加图标</el-button>
                    <el-button size="small" text :disabled="!getIconItems('title').length" @click="clearIcons('title')">清空</el-button>
                    <el-button size="small" text @click="useActiveImageAsIcon('title')">使用已选图片</el-button>
                  </div>
                  <div v-if="getIconItems('title').length" class="gen-icon-list">
                    <div v-for="(ic, i) in getIconItems('title')" :key="'title-icon-' + i" class="gen-icon-item">
                      <img :src="ic.src" alt="icon" />
                      <div class="gen-icon-item-actions">
                        <el-button size="small" text @click="replaceIcon('title', i)">替换</el-button>
                        <el-button size="small" text @click="moveIcon('title', i, -1)">上移</el-button>
                        <el-button size="small" text @click="moveIcon('title', i, 1)">下移</el-button>
                        <el-button size="small" text @click="removeIcon('title', i)">删除</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="gen-row" style="margin-top: 10px;">
                <div class="gen-label">标题下文字</div>
              </div>
              <div class="gen-text-with-icons">
                <el-input v-model="posterFramework.text.subtitle" placeholder="副标题" />
                <div class="gen-icon-editor">
                  <div class="gen-icon-actions">
                    <el-button size="small" text @click="openIconPicker('subtitle')">添加图标</el-button>
                    <el-button size="small" text :disabled="!getIconItems('subtitle').length" @click="clearIcons('subtitle')">清空</el-button>
                    <el-button size="small" text @click="useActiveImageAsIcon('subtitle')">使用已选图片</el-button>
                  </div>
                  <div v-if="getIconItems('subtitle').length" class="gen-icon-list">
                    <div v-for="(ic, i) in getIconItems('subtitle')" :key="'subtitle-icon-' + i" class="gen-icon-item">
                      <img :src="ic.src" alt="icon" />
                      <div class="gen-icon-item-actions">
                        <el-button size="small" text @click="replaceIcon('subtitle', i)">替换</el-button>
                        <el-button size="small" text @click="moveIcon('subtitle', i, -1)">上移</el-button>
                        <el-button size="small" text @click="moveIcon('subtitle', i, 1)">下移</el-button>
                        <el-button size="small" text @click="removeIcon('subtitle', i)">删除</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="gen-row" style="margin-top: 10px;">
                <div class="gen-label">卖点</div>
                <div class="gen-actions">
                  <el-button size="small" text @click="addFrameworkSellpoint">添加</el-button>
                </div>
              </div>
              <div class="gen-sellpoints">
                <div v-for="(sp, idx) in posterFramework.text.sellpoints" :key="sp.id" class="gen-sellpoint-item">
                  <div class="gen-sellpoint-main">
                    <el-input v-model="sp.text" :placeholder="`卖点${idx + 1}`" />
                    <div class="gen-icon-editor" style="margin-top: 6px;">
                      <div class="gen-icon-actions">
                        <el-button size="small" text @click="openIconPicker(`sellpoint_${idx + 1}`)">添加图标</el-button>
                        <el-button size="small" text :disabled="!getIconItems(`sellpoint_${idx + 1}`).length" @click="clearIcons(`sellpoint_${idx + 1}`)">清空</el-button>
                        <el-button size="small" text @click="useActiveImageAsIcon(`sellpoint_${idx + 1}`)">使用已选图片</el-button>
                        <el-button v-if="idx === 0" size="small" text :disabled="!getIconItems('sellpoint_1').length" @click="applySellpointIconsToAll">应用到所有卖点</el-button>
                      </div>
                      <div v-if="getIconItems(`sellpoint_${idx + 1}`).length" class="gen-icon-list" style="margin-top: 6px;">
                        <div v-for="(ic, i) in getIconItems(`sellpoint_${idx + 1}`)" :key="`sellpoint-${idx + 1}-icon-${i}`" class="gen-icon-item">
                          <img :src="ic.src" alt="icon" />
                          <div class="gen-icon-item-actions">
                            <el-button size="small" text @click="replaceIcon(`sellpoint_${idx + 1}`, i)">替换</el-button>
                            <el-button size="small" text @click="moveIcon(`sellpoint_${idx + 1}`, i, -1)">上移</el-button>
                            <el-button size="small" text @click="moveIcon(`sellpoint_${idx + 1}`, i, 1)">下移</el-button>
                            <el-button size="small" text @click="removeIcon(`sellpoint_${idx + 1}`, i)">删除</el-button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <el-button size="small" text @click="removeFrameworkSellpoint(idx)">删除</el-button>
                </div>
              </div>

              
            </div>
          </div>

          <div class="gen-col gen-col-full" style="margin-top: 12px;">
            <div class="gen-col-title">预览图</div>
            <div class="gen-row" style="margin-top: -2px;">
              <div class="gen-label" style="font-weight: 500; opacity: 0.85;">显示框</div>
              <el-switch v-model="previewShowBoxes" />
              <el-button size="small" :loading="posterImageEditLoading" style="margin-left: 10px;" @click="generatePosterImageEditNow">生成海报</el-button>
              <el-button size="small" style="margin-left: auto;" @click="exportPreviewToCanvas">导出到画布</el-button>
            </div>
            <div v-if="posterImageEditError" class="gen-error" style="margin-top: 8px;">{{ posterImageEditError }}</div>
            <div v-if="previewBaseUrl" ref="previewCanvasRef" class="gen-preview-canvas" :style="previewContainerStyle">
              <img ref="previewBgRef" class="gen-preview-bg" :src="previewBaseUrl" alt="preview" @load="onPreviewBgLoad" />
              <img v-if="previewProductUrl" class="gen-preview-product" :src="previewProductUrl" alt="product" :style="previewProductStyle" />
              <div v-if="previewShowBoxes" class="gen-preview-box-layer">
                <div v-for="b in previewTextBoxes" :key="b.key" class="gen-preview-box" :style="b.style"></div>
              </div>
              <div v-for="item in previewTextItems" :key="item.key" class="gen-preview-text" :style="item.style">
                <div class="gen-preview-text-inner" :style="item.innerStyle || null">
                  <div v-if="item.icons && item.icons.length" class="gen-preview-icons" :style="item.iconsStyle || null">
                    <img
                      v-for="(src, i) in item.icons"
                      :key="item.key + '-ic-' + i"
                      class="gen-preview-icon"
                      :src="src"
                      alt="icon"
                      :style="{ width: (item.iconSize || 18) + 'px', height: (item.iconSize || 18) + 'px' }"
                    />
                  </div>
                  <div class="gen-preview-text-content">{{ item.text }}</div>
                </div>
              </div>
            </div>
            <div v-else class="panel-empty">请先选择参考图并完成分析</div>
          </div>
        </template>
      </div>
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
        <template v-if="activeIsTextbox">
          <el-select
            class="tool tool-el-select"
            :model-value="textTool.fontFamily"
            size="small"
            :teleported="true"
            popper-class="obj-toolbar-popper"
            @update:model-value="(v) => onTextToolChange('fontFamily', v)"
          >
            <el-option v-for="f in textToolFontOptions" :key="f" :label="f" :value="f">
              <div class="font-opt">
                <div class="font-opt-name">{{ f }}</div>
                <div class="font-opt-sample" :style="{ fontFamily: f }">AaBb 你好 123</div>
              </div>
            </el-option>
          </el-select>
          <input class="tool tool-number" type="number" min="8" max="300" :value="textTool.fontSize" @change="(e) => onTextToolChange('fontSize', e?.target?.value)" />
          <input class="tool tool-color" type="color" :value="textTool.fill" @input="(e) => onTextToolChange('fill', e?.target?.value)" />
          <button class="tool" type="button" :data-active="textTool.bold ? '1' : '0'" @click="toggleTextBold">加粗</button>
          <span class="tool tool-sep"></span>
        </template>
        <template v-if="activeIsSelection">
          <button class="tool" type="button" @click="groupActiveSelection">创建分组</button>
          <span class="tool tool-sep"></span>
          <button class="tool" type="button" @click="alignActiveSelection('left')">左对齐</button>
          <button class="tool" type="button" @click="alignActiveSelection('hcenter')">水平居中</button>
          <button class="tool" type="button" @click="alignActiveSelection('right')">右对齐</button>
          <span class="tool tool-sep"></span>
          <button class="tool" type="button" @click="alignActiveSelection('top')">上对齐</button>
          <button class="tool" type="button" @click="alignActiveSelection('vcenter')">垂直居中</button>
          <button class="tool" type="button" @click="alignActiveSelection('bottom')">下对齐</button>
          <span class="tool tool-sep"></span>
        </template>
        <template v-else-if="activeIsGroup">
          <button class="tool" type="button" @click="ungroupActiveGroup">取消成组</button>
          <span class="tool tool-sep"></span>
        </template>
        <button class="tool" type="button" @click="moveActiveLayer('up')">上移</button>
        <button class="tool" type="button" @click="moveActiveLayer('down')">下移</button>
        <button class="tool" type="button" @click="duplicateActive">复制</button>
        <button class="tool" type="button" @click="rotateActive">旋转</button>
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
    <input ref="refImageInputRef" type="file" accept="image/*" style="display:none" @change="onPickRefImage" />
    <input ref="step2ProductInputRef" type="file" accept="image/*" style="display:none" @change="onPickStep2Product" />
    <input ref="step2BackgroundInputRef" type="file" accept="image/*" style="display:none" @change="onPickStep2Background" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import jsPDF from 'jspdf'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Operation } from '@element-plus/icons-vue'
import { Canvas as FabricCanvas, Textbox as FabricTextbox, Image as FabricImage, Point as FabricPoint, Rect as FabricRect, Shadow as FabricShadow, Pattern as FabricPattern, Group as FabricGroup, ActiveSelection as FabricActiveSelection } from 'fabric'
import { useManualStore } from '@/stores/manualStore'
import { analyzePosterReference, generatePosterCopy, generatePosterImageEdit } from '../services/api'

const router = useRouter()
const route = useRoute()

const manualStore = useManualStore()

const productName = computed(() => String(route.query.productName || manualStore.productName || '').trim())
const bomCode = computed(() => String(route.query.bomCode || manualStore.bomCode || '').trim())
const bomType = computed(() => String(route.query.bomType || manualStore.bomType || '').trim())

const POSTER_CANVAS_WIDTH = 1080
const POSTER_CANVAS_HEIGHT = 1920
const DRAFT_KEY = 'posterCanvasDraft'

const canvasEl = ref(null)
const stageRef = ref(null)
const imageInputRef = ref(null)
const refImageInputRef = ref(null)
const step2ProductInputRef = ref(null)
const step2BackgroundInputRef = ref(null)
const objToolbarRef = ref(null)
const objSizeTagRef = ref(null)

const canvasInstance = ref(null)
const zoom = ref(1)

const rightPanelOpen = ref(false)
const rightPanelKey = ref('props')
const activeObjectRef = ref(null)

const activeType = computed(() => {
  const o = activeObjectRef.value
  return String(o?.type || '')
})

const activeIsSelection = computed(() => activeType.value.toLowerCase() === 'activeselection')
const activeIsGroup = computed(() => activeType.value.toLowerCase() === 'group')

const propForm = reactive({ x: 0, y: 0, scale: 1, angle: 0, opacity: 1 })

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
  mode: 'uniform',
  corner: '',
  oppCorner: '',
  startDist: 1,
  startScaleX: 1,
  startScaleY: 1,
  startPointer: { x: 0, y: 0 },
  startRect: { left: 0, top: 0, width: 0, height: 0 },
  anchor: { x: 0, y: 0 },
  obj: null,
  pointerId: null,
})

const isSpaceDown = ref(false)
const isPanning = ref(false)
const lastPan = reactive({ x: 0, y: 0 })
const artboard = ref(null)

const clipboard = ref(null)
const clipboardData = ref(null)
const pasteCount = ref(0)

const isShiftDown = ref(false)

const snapGuides = reactive({
  active: false,
  vx: null,
  hy: null,
})

const historyUndo = ref([])
const historyRedo = ref([])
let historyEnabled = false
let historyApplying = false
let historyTimer = null
const HISTORY_MAX = 60

const getCanvasSnapshot = () => {
  const canvas = canvasInstance.value
  if (!canvas) return null
  try {
    return JSON.stringify(canvas.toJSON(['data']))
  } catch (e) {
    try {
      return JSON.stringify(canvas.toJSON())
    } catch (e2) {
      return null
    }
  }
}

const pushHistorySnapshot = (snap) => {
  if (!snap) return
  const u = historyUndo.value
  if (u.length && u[u.length - 1] === snap) return
  u.push(snap)
  if (u.length > HISTORY_MAX) u.splice(0, u.length - HISTORY_MAX)
  historyRedo.value.splice(0, historyRedo.value.length)
}

const scheduleHistory = () => {
  if (!historyEnabled || historyApplying) return
  try {
    if (historyTimer) clearTimeout(historyTimer)
  } catch (e) {}
  historyTimer = setTimeout(() => {
    historyTimer = null
    if (!historyEnabled || historyApplying) return
    const snap = getCanvasSnapshot()
    pushHistorySnapshot(snap)
  }, 180)
}

const initHistoryForCanvas = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  historyUndo.value.splice(0, historyUndo.value.length)
  historyRedo.value.splice(0, historyRedo.value.length)
  historyEnabled = true
  historyApplying = false
  const snap = getCanvasSnapshot()
  if (snap) historyUndo.value.push(snap)

  // record key interactions
  try {
    canvas.on('object:added', scheduleHistory)
    canvas.on('object:removed', scheduleHistory)
    canvas.on('object:modified', (opt) => {
      try {
        const t = opt?.target
        if (t && String(t.type || '') === 'textbox') {
          bakeTextboxScaling(t)
        }
      } catch (e) {}
      scheduleHistory()
    })
    canvas.on('text:changed', scheduleHistory)
  } catch (e) {}
}

const isLockedBottomLayer = (o) => {
  const role = String(o?.data?.role || '')
  return role === 'artboard' || role === 'poster_background'
}

const clearSnapGuides = () => {
  snapGuides.active = false
  snapGuides.vx = null
  snapGuides.hy = null
  try {
    const canvas = canvasInstance.value
    if (canvas) canvas.requestRenderAll()
  } catch (e) {}
}

const _worldToCanvasXY = (canvas, x, y) => {
  const vpt = canvas?.viewportTransform || [1, 0, 0, 1, 0, 0]
  return {
    x: vpt[0] * x + vpt[2] * y + vpt[4],
    y: vpt[1] * x + vpt[3] * y + vpt[5],
  }
}

const renderSnapGuides = () => {
  // Temporarily disabled: user requested to hide helper guide lines.
  return
}

const handleObjectMovingWithSnap = (opt) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = opt?.target
  if (!obj) return
  if (isLockedBottomLayer(obj)) {
    clearSnapGuides()
    updateObjOverlay()
    return
  }

  const tl = String(obj?.type || '').toLowerCase()
  if (tl !== 'image' && tl !== 'textbox') {
    clearSnapGuides()
    updateObjOverlay()
    return
  }

  if (isShiftDown.value) {
    clearSnapGuides()
    updateObjOverlay()
    return
  }

  const snapPx = 6
  const z = Number(zoom.value || 1) || 1
  const threshold = snapPx / Math.max(1e-6, z)

  let rect = null
  try {
    rect = obj.getBoundingRect(true, true)
  } catch (e) {
    rect = null
  }
  if (!rect) {
    clearSnapGuides()
    updateObjOverlay()
    return
  }

  const left = Number(rect.left || 0)
  const top = Number(rect.top || 0)
  const w = Number(rect.width || 0)
  const h = Number(rect.height || 0)
  const right = left + w
  const bottom = top + h
  const cx = left + w / 2
  const cy = top + h / 2

  const xTargets = [left, cx, right]
  const yTargets = [top, cy, bottom]

  const boardXGuides = [0, POSTER_CANVAS_WIDTH / 2, POSTER_CANVAS_WIDTH]
  const boardYGuides = [0, POSTER_CANVAS_HEIGHT / 2, POSTER_CANVAS_HEIGHT]
  const objectXGuides = []
  const objectYGuides = []

  try {
    const all = canvas.getObjects?.() || []
    all.forEach((o) => {
      try {
        if (!o || o === obj) return
        if (isLockedBottomLayer(o)) return
        const tt = String(o.type || '').toLowerCase()
        if (tt === 'group' || tt === 'activeselection') return
        const r = o.getBoundingRect?.(true, true)
        if (!r) return
        const l2 = Number(r.left || 0)
        const t2 = Number(r.top || 0)
        const w2 = Number(r.width || 0)
        const h2 = Number(r.height || 0)
        const r2 = l2 + w2
        const b2 = t2 + h2
        const cx2 = l2 + w2 / 2
        const cy2 = t2 + h2 / 2
        objectXGuides.push(l2, cx2, r2)
        objectYGuides.push(t2, cy2, b2)
      } catch (e) {}
    })
  } catch (e) {}

  const findBestSnap = (guides, targets) => {
    let bestAbs = Infinity
    let bestD = 0
    let bestG = null
    ;(guides || []).forEach((g0) => {
      const g = Number(g0)
      if (!Number.isFinite(g)) return
      ;(targets || []).forEach((t0) => {
        const t = Number(t0)
        if (!Number.isFinite(t)) return
        const d = g - t
        const ad = Math.abs(d)
        if (ad <= threshold && ad < bestAbs) {
          bestAbs = ad
          bestD = d
          bestG = g
        }
      })
    })
    if (!Number.isFinite(bestAbs) || bestAbs === Infinity) return { abs: Infinity, d: 0, g: null }
    return { abs: bestAbs, d: bestD, g: bestG }
  }

  // Prefer snapping to other objects. Only show guides when object snapping is active.
  const xObj = findBestSnap(objectXGuides, xTargets)
  const yObj = findBestSnap(objectYGuides, yTargets)
  const xBoard = findBestSnap(boardXGuides, xTargets)
  const yBoard = findBestSnap(boardYGuides, yTargets)

  const useObjX = xObj.abs !== Infinity
  const useObjY = yObj.abs !== Infinity

  const bestDx = useObjX ? xObj.d : xBoard.d
  const bestDy = useObjY ? yObj.d : yBoard.d
  const showVx = useObjX ? xObj.g : null
  const showHy = useObjY ? yObj.g : null

  if (bestDx !== 0 || bestDy !== 0) {
    try {
      obj.set({ left: Number(obj.left || 0) + bestDx, top: Number(obj.top || 0) + bestDy })
      if (typeof obj.setCoords === 'function') obj.setCoords()
    } catch (e) {}
  }

  // Only display helper lines when snapping to other objects (not board).
  // Temporarily disabled: user requested to hide helper guide lines.
  snapGuides.active = false
  snapGuides.vx = null
  snapGuides.hy = null

  updateObjOverlay()
}

const getMovableObjects = () => {
  const canvas = canvasInstance.value
  if (!canvas) return []
  try {
    return (canvas.getObjects() || []).filter((o) => o && !isLockedBottomLayer(o))
  } catch (e) {
    return []
  }
}

const getFirstMovableCanvasIndex = () => {
  const canvas = canvasInstance.value
  if (!canvas) return 0
  const objs = canvas.getObjects ? canvas.getObjects() : []
  let maxLockedIdx = -1
  objs.forEach((o, idx) => {
    if (o && isLockedBottomLayer(o)) maxLockedIdx = Math.max(maxLockedIdx, idx)
  })
  return Math.max(0, maxLockedIdx + 1)
}

const sanitizeActiveSelection = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || String(obj.type || '').toLowerCase() !== 'activeselection') return

  try {
    const all = typeof obj.getObjects === 'function' ? (obj.getObjects() || []) : []
    const locked = all.filter((o) => o && isLockedBottomLayer(o))
    if (!locked.length) return
    locked.forEach((o) => {
      try {
        if (typeof obj.remove === 'function') obj.remove(o)
      } catch (e) {}
    })
    const remain = typeof obj.getObjects === 'function' ? (obj.getObjects() || []) : []
    if (remain.length <= 1) {
      canvas.discardActiveObject()
      if (remain[0]) canvas.setActiveObject(remain[0])
    }
  } catch (e) {}
}

const refreshFabricCoords = (o) => {
  if (!o) return
  try {
    // Group/ActiveSelection needs internal bounds recalculation beyond setCoords.
    const tl = String(o.type || '').toLowerCase()
    if (tl === 'group' || tl === 'activeselection') {
      try {
        if (typeof o._calcBounds === 'function') o._calcBounds()
      } catch (e) {}
      try {
        if (typeof o._updateObjectsCoords === 'function') o._updateObjectsCoords()
      } catch (e) {}
      try {
        if (typeof o._setObjectCoords === 'function') o._setObjectCoords()
      } catch (e) {}
    }
    try {
      if (typeof o.setCoords === 'function') o.setCoords()
    } catch (e) {}
  } catch (e) {}
}

const reorderObject = (obj, dir) => {
  const canvas = canvasInstance.value
  if (!canvas || !obj) return
  if (isLockedBottomLayer(obj)) return

  const movable = getMovableObjects()
  const idx = movable.indexOf(obj)
  if (idx < 0) return
  const firstIdx = getFirstMovableCanvasIndex()

  let targetIdx = idx
  if (dir === 'up') targetIdx = Math.min(movable.length - 1, idx + 1)
  else if (dir === 'down') targetIdx = Math.max(0, idx - 1)
  else if (dir === 'top') targetIdx = movable.length - 1
  else if (dir === 'bottom') targetIdx = 0
  else return

  if (targetIdx === idx) return

  // movable list is in canvas order; map to absolute canvas index
  const absIndex = firstIdx + targetIdx
  try {
    canvas.moveObjectTo(obj, absIndex)
    canvas.setActiveObject(obj)
    canvas.requestRenderAll()
    updateObjOverlay()
    scheduleHistory()
  } catch (e) {}
}

const moveActiveLayer = (dir) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj) {
    ElMessage.warning('请先选中一个对象')
    return
  }
  reorderObject(obj, dir)
}

const groupActiveSelection = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  sanitizeActiveSelection()
  const obj = canvas.getActiveObject()
  if (!obj || String(obj.type || '').toLowerCase() !== 'activeselection') return

  let prevVpt = null
  try {
    const objects = (typeof obj.getObjects === 'function' ? obj.getObjects() : []).filter((o) => o && !isLockedBottomLayer(o))
    if (objects.length < 2) {
      ElMessage.warning('请至少选择两个可编辑对象')
      return
    }

    try {
      objects.forEach((o) => refreshFabricCoords(o))
      refreshFabricCoords(obj)
    } catch (e) {}

    prevVpt = Array.isArray(canvas.viewportTransform) ? canvas.viewportTransform.slice() : null

    try {
      canvas.setViewportTransform([1, 0, 0, 1, 0, 0])
      canvas.calcOffset()
    } catch (e) {}

    if (typeof obj.toGroup === 'function') {
      try {
        try { console.debug('[group] using native toGroup()') } catch (e) {}
        const group = obj.toGroup()
        if (!group) return
        refreshFabricCoords(group)

        canvas.setActiveObject(group)
        try {
          recalcAllObjectCoords()
          canvas.calcOffset()
        } catch (e) {}
        canvas.requestRenderAll()
        updateObjOverlay()
        scheduleHistory()
        return
      } catch (err) {
        ElMessage.error(`成组失败: ${err?.message || String(err)}`)
        return
      }
    }

    let minL = Infinity
    let minT = Infinity
    let maxR = -Infinity
    let maxB = -Infinity
    objects.forEach((o) => {
      try {
        const r = typeof o.getBoundingRect === 'function' ? o.getBoundingRect(true, true) : null
        if (!r) return
        const l = Number(r.left)
        const t = Number(r.top)
        const w = Number(r.width)
        const h = Number(r.height)
        if (!Number.isFinite(l) || !Number.isFinite(t) || !Number.isFinite(w) || !Number.isFinite(h)) return
        minL = Math.min(minL, l)
        minT = Math.min(minT, t)
        maxR = Math.max(maxR, l + w)
        maxB = Math.max(maxB, t + h)
      } catch (e) {}
    })
    if (!Number.isFinite(minL) || !Number.isFinite(minT) || !Number.isFinite(maxR) || !Number.isFinite(maxB)) {
      ElMessage.error('成组失败：无法计算选区范围')
      return
    }
    const center = { x: (minL + maxR) / 2, y: (minT + maxB) / 2 }

    const allObjs = canvas.getObjects ? canvas.getObjects() : []
    const indices = objects.map((o) => allObjs.indexOf(o)).filter((n) => n >= 0)
    const firstIdx = getFirstMovableCanvasIndex()
    const targetIndex = Math.max(firstIdx, indices.length ? Math.min(...indices) : firstIdx)

    objects.forEach((o) => {
      try {
        const ox = String(o.originX || 'left')
        const oy = String(o.originY || 'top')
        const pt = typeof o.getPointByOrigin === 'function' ? o.getPointByOrigin(ox, oy) : null
        const px = Number(pt?.x)
        const py = Number(pt?.y)
        if (Number.isFinite(px) && Number.isFinite(py)) {
          o.set({ left: px - center.x, top: py - center.y })
        }
        if (typeof o.setCoords === 'function') o.setCoords()
      } catch (e) {}
    })

    objects.forEach((o) => {
      try { canvas.remove(o) } catch (e) {}
    })

    let group = null
    try {
      group = new FabricGroup(objects, { left: center.x, top: center.y, originX: 'center', originY: 'center' })
    } catch (e) {
      group = null
    }
    if (!group) {
      ElMessage.error('成组失败：无法创建 Group')
      return
    }

    try {
      if (typeof group.setPositionByOrigin === 'function') {
        group.setPositionByOrigin(new FabricPoint(center.x, center.y), 'center', 'center')
      }
    } catch (e) {}

    refreshFabricCoords(group)

    canvas.add(group)
    try {
      canvas.moveObjectTo(group, Math.min(targetIndex, (canvas.getObjects?.() || []).length - 1))
    } catch (e) {}
    canvas.setActiveObject(group)
    try {
      recalcAllObjectCoords()
      canvas.calcOffset()
    } catch (e) {}
    canvas.requestRenderAll()
    updateObjOverlay()
    try {
      requestAnimationFrame(() => {
        try {
          canvas.requestRenderAll()
          updateObjOverlay()
        } catch (e) {}
      })
    } catch (e) {}
    scheduleHistory()
  } catch (e) {}
  finally {
    try {
      if (prevVpt) {
        canvas.setViewportTransform(prevVpt)
        canvas.calcOffset()
        try {
          recalcAllObjectCoords()
        } catch (e) {}
        canvas.requestRenderAll()
        updateObjOverlay()
      }
    } catch (e) {}
  }
}

const ungroupActiveGroup = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || String(obj.type || '').toLowerCase() !== 'group') return
  if (isLockedBottomLayer(obj)) return

  try {
    let prevVpt = null
    let groupRect = null
    try {
      groupRect = obj.getBoundingRect?.(true, true) || null
    } catch (e) {
      groupRect = null
    }

    const alignItemsToGroupRect = (items) => {
      if (!groupRect) return
      try {
        let minL = Infinity
        let minT = Infinity
        let maxR = -Infinity
        let maxB = -Infinity
        ;(items || []).forEach((o) => {
          try {
            const r = o?.getBoundingRect?.(true, true)
            if (!r) return
            const l = Number(r.left)
            const t = Number(r.top)
            const w = Number(r.width)
            const h = Number(r.height)
            if (!Number.isFinite(l) || !Number.isFinite(t) || !Number.isFinite(w) || !Number.isFinite(h)) return
            minL = Math.min(minL, l)
            minT = Math.min(minT, t)
            maxR = Math.max(maxR, l + w)
            maxB = Math.max(maxB, t + h)
          } catch (e) {}
        })
        if (!Number.isFinite(minL) || !Number.isFinite(minT) || !Number.isFinite(maxR) || !Number.isFinite(maxB)) return
        const dx = Number(groupRect.left) - minL
        const dy = Number(groupRect.top) - minT
        if (!Number.isFinite(dx) || !Number.isFinite(dy)) return

        try {
          if (window.__posterDebug) {
            // eslint-disable-next-line no-console
            console.log('[PosterDebug] ungroup:align', {
              groupRect,
              itemsRectBefore: { left: minL, top: minT, width: maxR - minL, height: maxB - minT },
              dx,
              dy,
            })
          }
        } catch (e) {}

        ;(items || []).forEach((o) => {
          try {
            if (!o) return
            o.set({ left: Number(o.left || 0) + dx, top: Number(o.top || 0) + dy })
            if (typeof o.setCoords === 'function') o.setCoords()
          } catch (e) {}
        })

        try {
          if (window.__posterDebug) {
            let minL2 = Infinity
            let minT2 = Infinity
            let maxR2 = -Infinity
            let maxB2 = -Infinity
            ;(items || []).forEach((o) => {
              try {
                const r = o?.getBoundingRect?.(true, true)
                if (!r) return
                const l = Number(r.left)
                const t = Number(r.top)
                const w = Number(r.width)
                const h = Number(r.height)
                if (!Number.isFinite(l) || !Number.isFinite(t) || !Number.isFinite(w) || !Number.isFinite(h)) return
                minL2 = Math.min(minL2, l)
                minT2 = Math.min(minT2, t)
                maxR2 = Math.max(maxR2, l + w)
                maxB2 = Math.max(maxB2, t + h)
              } catch (e) {}
            })
            // eslint-disable-next-line no-console
            console.log('[PosterDebug] ungroup:align:after', {
              itemsRectAfter: { left: minL2, top: minT2, width: maxR2 - minL2, height: maxB2 - minT2 },
            })
          }
        } catch (e) {}
      } catch (e) {}
    }

    try {
      if (window.__posterDebug) {
        const r0 = obj.getBoundingRect?.(true, true)
        // eslint-disable-next-line no-console
        console.log('[PosterDebug] ungroup:before', {
          vpt: (canvas.viewportTransform || []).slice?.() || canvas.viewportTransform,
          zoom: zoom.value,
          group: {
            left: obj.left,
            top: obj.top,
            scaleX: obj.scaleX,
            scaleY: obj.scaleY,
            angle: obj.angle,
            originX: obj.originX,
            originY: obj.originY,
            rect: r0,
          },
        })
      }
    } catch (e) {}

    const items = typeof obj.getObjects === 'function' ? ((obj.getObjects() || []).slice()) : []
    if (!items.length) return
    const groupIndex = (canvas.getObjects?.() || []).indexOf(obj)

    try {
      prevVpt = Array.isArray(canvas.viewportTransform) ? canvas.viewportTransform.slice() : null
      canvas.setViewportTransform([1, 0, 0, 1, 0, 0])
      canvas.calcOffset()
    } catch (e) {}

    try {
      groupRect = obj.getBoundingRect?.(true, true) || groupRect
    } catch (e) {}

    let liveItems = items
    let ungroupOk = false

    // Prefer Fabric's official ungroup path (Fabric 6+): toActiveSelection() handles restore + re-add.
    // Run under identity VPT to avoid viewport-related drift.
    try {
      if (typeof obj.toActiveSelection === 'function') {
        const sel = obj.toActiveSelection()
        if (sel) {
          liveItems = typeof sel.getObjects === 'function' ? (sel.getObjects() || []) : liveItems
          ungroupOk = true
        }
      }
    } catch (e) {}

    // Fallback for environments where toActiveSelection is unavailable/failed.
    if (!ungroupOk) {
      try {
        // Let fabric restore absolute coords. Do NOT apply extra manual transforms (causes drift).
        refreshFabricCoords(obj)
        if (typeof obj._restoreObjectsState === 'function') obj._restoreObjectsState()
      } catch (e) {}
      try {
        canvas.remove(obj)
      } catch (e) {}
      liveItems = items
      liveItems.forEach((o) => {
        try {
          try {
            if (typeof o?._set === 'function') o._set('group', null)
          } catch (e) {}
          try { o.group = null } catch (e) {}
          try { o.parent = null } catch (e) {}
          try { o._group = null } catch (e) {}
          try { o.__owningGroup = null } catch (e) {}
          try { o.canvas = canvas } catch (e) {}
          refreshFabricCoords(o)
          canvas.add(o)
        } catch (e) {}
      })
      try {
        if (typeof FabricActiveSelection === 'function') {
          const sel = new FabricActiveSelection(liveItems, { canvas })
          ungroupOk = true
        }
      } catch (e) {}
    }

    try {
      if (groupRect) {
        let minL = Infinity
        let minT = Infinity
        let maxR = -Infinity
        let maxB = -Infinity
        ;(liveItems || []).forEach((o) => {
          try {
            const r = o?.getBoundingRect?.(true, true)
            if (!r) return
            const l = Number(r.left)
            const t = Number(r.top)
            const w = Number(r.width)
            const h = Number(r.height)
            if (!Number.isFinite(l) || !Number.isFinite(t) || !Number.isFinite(w) || !Number.isFinite(h)) return
            minL = Math.min(minL, l)
            minT = Math.min(minT, t)
            maxR = Math.max(maxR, l + w)
            maxB = Math.max(maxB, t + h)
          } catch (e) {}
        })
        if (Number.isFinite(minL) && Number.isFinite(minT) && Number.isFinite(maxR) && Number.isFinite(maxB)) {
          const dx = Number(groupRect.left) - minL
          const dy = Number(groupRect.top) - minT
          if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            try { alignItemsToGroupRect(liveItems) } catch (e) {}
          }
        }
      }
    } catch (e) {}

    try {
      recalcAllObjectCoords()
      canvas.calcOffset()
    } catch (e) {}
    try {
      if (typeof groupIndex === 'number' && groupIndex >= 0) {
        // keep approx original position in stack
        const objs = canvas.getObjects?.() || []
        const firstIdx = getFirstMovableCanvasIndex()
        const base = Math.max(firstIdx, groupIndex)
        liveItems.forEach((o, i) => {
          try {
            canvas.moveObjectTo(o, Math.min(base + i, objs.length - 1))
          } catch (e) {}
        })
      }
    } catch (e) {}

    try {
      if (prevVpt) {
        canvas.setViewportTransform(prevVpt)
        canvas.calcOffset()
      }
    } catch (e) {}

    // Scheme B: do not keep multi-selection after ungroup.
    try {
      canvas.discardActiveObject()
    } catch (e) {}

    canvas.requestRenderAll()
    updateObjOverlay()
    scheduleHistory()
  } catch (e) {}
  finally {
    try {
      if (prevVpt) {
        canvas.setViewportTransform(prevVpt)
      }
    } catch (e) {}
    try { canvas.calcOffset() } catch (e) {}
    try {
      const ao = canvas.getActiveObject?.()
      const tl = String(ao?.type || '').toLowerCase()
      if (ao && (tl === 'activeselection' || tl === 'group')) {
        try { refreshFabricCoords(ao) } catch (e) {}
        try {
          const its = typeof ao.getObjects === 'function' ? (ao.getObjects() || []) : []
          its.forEach((o) => {
            try { refreshFabricCoords(o) } catch (e) {}
          })
        } catch (e) {}
      }
    } catch (e) {}
    try {
      const ao = canvas.getActiveObject?.()
      try {
        if (ao) ao.dirty = true
      } catch (e) {}
      try {
        const its = ao && typeof ao.getObjects === 'function' ? (ao.getObjects() || []) : []
        its.forEach((o) => {
          try { if (o) o.dirty = true } catch (e) {}
        })
      } catch (e) {}
      try {
        ;(canvas.getObjects?.() || []).forEach((o) => {
          try { if (o) o.dirty = true } catch (e) {}
        })
      } catch (e) {}
    } catch (e) {}
    try {
      recalcAllObjectCoords()
    } catch (e) {}
    try {
      canvas.requestRenderAll()
      updateObjOverlay()
    } catch (e) {}
    try {
      if (typeof canvas.renderAll === 'function') canvas.renderAll()
    } catch (e) {}

    try {
      if (window.__posterDebug) {
        const ao = canvas.getActiveObject?.()
        const objs = canvas.getObjects?.() || []
        // eslint-disable-next-line no-console
        console.log('[PosterDebug] ungroup:final', {
          vpt: (canvas.viewportTransform || []).slice?.() || canvas.viewportTransform,
          activeType: ao?.type,
          activeRect: ao?.getBoundingRect?.(true, true),
          objects: objs.map((o) => ({
            type: o?.type,
            left: o?.left,
            top: o?.top,
            groupType: o?.group?.type,
            groupLeft: o?.group?.left,
            groupTop: o?.group?.top,
            rect: o?.getBoundingRect?.(true, true),
          })),
        })
      }
    } catch (e) {}
  }
}

const alignActiveSelection = (mode) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  sanitizeActiveSelection()
  const sel = canvas.getActiveObject()
  if (!sel || String(sel.type || '').toLowerCase() !== 'activeselection') return

  let refRect = null
  try {
    refRect = sel.getBoundingRect(true, true)
  } catch (e) {
    refRect = null
  }
  if (!refRect) return

  const objects = (typeof sel.getObjects === 'function' ? sel.getObjects() : []).filter((o) => o && !isLockedBottomLayer(o))
  if (objects.length < 2) {
    ElMessage.warning('请至少选择两个可编辑对象')
    return
  }

  const refLeft = Number(refRect.left || 0)
  const refTop = Number(refRect.top || 0)
  const refRight = refLeft + Number(refRect.width || 0)
  const refBottom = refTop + Number(refRect.height || 0)
  const refCenterX = refLeft + Number(refRect.width || 0) / 2
  const refCenterY = refTop + Number(refRect.height || 0) / 2

  objects.forEach((o) => {
    try {
      const r = o.getBoundingRect(true, true)
      const left = Number(r.left || 0)
      const top = Number(r.top || 0)
      const right = left + Number(r.width || 0)
      const bottom = top + Number(r.height || 0)
      const centerX = left + Number(r.width || 0) / 2
      const centerY = top + Number(r.height || 0) / 2

      let dx = 0
      let dy = 0
      if (mode === 'left') dx = refLeft - left
      else if (mode === 'right') dx = refRight - right
      else if (mode === 'hcenter') dx = refCenterX - centerX
      else if (mode === 'top') dy = refTop - top
      else if (mode === 'bottom') dy = refBottom - bottom
      else if (mode === 'vcenter') dy = refCenterY - centerY
      else return

      o.set({ left: Number(o.left || 0) + dx, top: Number(o.top || 0) + dy })
      if (typeof o.setCoords === 'function') o.setCoords()
    } catch (e) {}
  })

  try {
    if (typeof sel.setCoords === 'function') sel.setCoords()
  } catch (e) {}
  canvas.requestRenderAll()
  updateObjOverlay()
  scheduleHistory()
}

const moveLayerById = (id, dir) => {
  const item = (layerItems.value || []).find((x) => x.id === id)
  const obj = item?.obj
  if (!obj) return
  try {
    const canvas = canvasInstance.value
    canvas?.setActiveObject?.(obj)
  } catch (e) {}
  reorderObject(obj, dir)
}

const bakeTextboxScaling = (obj) => {
  const canvas = canvasInstance.value
  if (!canvas || !obj || String(obj.type || '') !== 'textbox') return
  const sx = Number(obj.scaleX ?? 1) || 1
  const sy = Number(obj.scaleY ?? 1) || 1
  // Only bake when there is meaningful scaling.
  if (Math.abs(sx - 1) < 1e-3 && Math.abs(sy - 1) < 1e-3) return

  try {
    const baseFont = Number(obj.fontSize || 0) || 12
    const baseW = Number(obj.width || 0) || 1
    const baseH = Number(obj.height || 0) || 1
    // Use average scale to keep proportions; update box size accordingly.
    const s = Math.max(0.05, (sx + sy) / 2)
    obj.set({
      fontSize: Math.max(8, Math.round(baseFont * s)),
      width: Math.max(1, baseW * sx),
      height: Math.max(1, baseH * sy),
      scaleX: 1,
      scaleY: 1,
    })
    if (typeof obj.setCoords === 'function') obj.setCoords()
    canvas.requestRenderAll()
    updateObjOverlay()
    syncTextToolFromActive()
    scheduleHistory()
  } catch (e) {}
}

const undoCanvas = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const u = historyUndo.value
  if (!u || u.length < 2) return
  const current = u.pop()
  if (current) historyRedo.value.push(current)
  const prev = u[u.length - 1]
  if (!prev) return
  historyApplying = true
  try {
    await canvas.loadFromJSON(JSON.parse(prev))
    canvas.requestRenderAll()
    applySelectionStyleToAll()
    recalcAllObjectCoords()
    updateObjOverlay()
  } catch (e) {
    // ignore
  } finally {
    historyApplying = false
  }
}

const redoCanvas = async () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const r = historyRedo.value
  if (!r || r.length < 1) return
  const next = r.pop()
  if (!next) return
  pushHistorySnapshot(next)
  historyApplying = true
  try {
    await canvas.loadFromJSON(JSON.parse(next))
    canvas.requestRenderAll()
    applySelectionStyleToAll()
    recalcAllObjectCoords()
    updateObjOverlay()
  } catch (e) {
    // ignore
  } finally {
    historyApplying = false
  }
}

const imageDialogVisible = ref(false)
const imageDialogTab = ref('local')
const kbProductImages = ref([])
const imageDialogPurpose = ref('insert')

const refPreviewUrl = ref('')
const refImageUrl = ref('')
const refImageFile = ref(null)
const posterAnalyzeLoading = ref(false)
const posterAnalyzeError = ref('')
const posterAnalysisResult = ref(null)
const posterAnalysisDebug = ref('')

const posterStep2Requirements = ref('')
const posterStep2Loading = ref(false)
const posterStep2Error = ref('')
const posterStep2Result = ref(null)
const posterStep2Debug = ref('')
const posterStep2ProductFile = ref(null)
const posterStep2BackgroundFile = ref(null)
const posterStep2ProductUrl = ref('')
const posterStep2BackgroundUrl = ref('')

const posterImageEditLoading = ref(false)
const posterImageEditError = ref('')
const posterImageEditResultUrl = ref('')

const posterFramework = reactive({
  size: {
    width: 0,
    height: 0,
  },
  icons: {},
  text: {
    title: '',
    subtitle: '',
    sellpoints: [],
  },
})

const ensureIconBucket = (id) => {
  const key = String(id || '').trim()
  if (!key) return null
  if (!posterFramework.icons || typeof posterFramework.icons !== 'object') posterFramework.icons = {}
  const existing = posterFramework.icons[key]
  if (existing && typeof existing === 'object' && Array.isArray(existing.items)) return existing
  posterFramework.icons[key] = { items: [] }
  return posterFramework.icons[key]
}

const getIconItems = (id) => {
  const key = String(id || '').trim()
  if (!key) return []
  const b = posterFramework.icons && typeof posterFramework.icons === 'object' ? posterFramework.icons[key] : null
  const items = b && typeof b === 'object' && Array.isArray(b.items) ? b.items : []
  return items.filter((x) => x && typeof x === 'object' && typeof x.src === 'string' && x.src.trim())
}

const pushIcon = (id, src) => {
  const key = String(id || '').trim()
  const url = String(src || '').trim()
  if (!key || !url) return
  const b = ensureIconBucket(key)
  if (!b) return
  b.items.push({ src: url })
}

const setIconAt = (id, idx, src) => {
  const key = String(id || '').trim()
  const url = String(src || '').trim()
  const i = Number(idx)
  if (!key || !url || !Number.isFinite(i) || i < 0) return
  const b = ensureIconBucket(key)
  if (!b) return
  if (i >= b.items.length) return
  b.items.splice(i, 1, { src: url })
}

const removeIcon = (id, idx) => {
  const key = String(id || '').trim()
  const i = Number(idx)
  if (!key || !Number.isFinite(i) || i < 0) return
  const b = ensureIconBucket(key)
  if (!b) return
  if (i >= b.items.length) return
  b.items.splice(i, 1)
}

const moveIcon = (id, idx, delta) => {
  const key = String(id || '').trim()
  const i = Number(idx)
  const d = Number(delta)
  if (!key || !Number.isFinite(i) || !Number.isFinite(d)) return
  const b = ensureIconBucket(key)
  if (!b) return
  const next = i + d
  if (i < 0 || i >= b.items.length) return
  if (next < 0 || next >= b.items.length) return
  const it = b.items[i]
  b.items.splice(i, 1)
  b.items.splice(next, 0, it)
}

const clearIcons = (id) => {
  const key = String(id || '').trim()
  if (!key) return
  const b = ensureIconBucket(key)
  if (!b) return
  b.items.splice(0, b.items.length)
}

const applySellpointIconsToAll = () => {
  const base = getIconItems('sellpoint_1')
  if (!base.length) return
  const sps = Array.isArray(posterFramework.text.sellpoints) ? posterFramework.text.sellpoints : []
  for (let i = 0; i < sps.length; i++) {
    const key = `sellpoint_${i + 1}`
    const cur = getIconItems(key)
    if (cur.length) continue
    const b = ensureIconBucket(key)
    if (!b) continue
    base.forEach((it) => b.items.push({ src: it.src }))
  }
}

const openIconPicker = (id) => {
  const key = String(id || '').trim()
  if (!key) return
  imageDialogTab.value = 'kb'
  refreshKbProductImages()
  imageDialogPurpose.value = `icon_add:${key}`
  imageDialogVisible.value = true
}

const replaceIcon = (id, idx) => {
  const key = String(id || '').trim()
  const i = Number(idx)
  if (!key || !Number.isFinite(i) || i < 0) return
  imageDialogTab.value = 'kb'
  refreshKbProductImages()
  imageDialogPurpose.value = `icon_replace:${key}:${i}`
  imageDialogVisible.value = true
}

const useActiveImageAsIcon = (id) => {
  const key = String(id || '').trim()
  if (!key) return
  const obj = activeObjectRef.value
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片对象')
    return
  }
  const el = obj.getElement?.() || obj._element || obj._originalElement || null
  const src = el?.currentSrc || el?.src || obj?.src || ''
  if (!src) {
    ElMessage.warning('无法获取选中图片的源地址')
    return
  }
  pushIcon(key, src)
}

const frameworkSizeTouched = ref(false)

const onFrameworkSizeChange = () => {
  frameworkSizeTouched.value = true
}

const _updateFrameworkSizeFromUrl = async (url) => {
  const u = String(url || '').trim()
  if (!u) return false
  try {
    await new Promise((resolve) => {
      const img = new Image()
      img.onload = () => {
        const w = Number(img.naturalWidth || img.width || 0)
        const h = Number(img.naturalHeight || img.height || 0)
        if (Number.isFinite(w) && w > 0) posterFramework.size.width = Math.round(w)
        if (Number.isFinite(h) && h > 0) posterFramework.size.height = Math.round(h)
        resolve(true)
      }
      img.onerror = () => resolve(false)
      img.src = u
    })
    return true
  } catch (e) {
    return false
  }
}

const _updateFrameworkSizeFromFile = async (file) => {
  const f = file
  if (!f) return false
  try {
    const bitmap = await createImageBitmap(f)
    const w = Number(bitmap?.width || 0)
    const h = Number(bitmap?.height || 0)
    if (Number.isFinite(w) && w > 0) posterFramework.size.width = Math.round(w)
    if (Number.isFinite(h) && h > 0) posterFramework.size.height = Math.round(h)
    try { bitmap.close && bitmap.close() } catch (e) {}
    return true
  } catch (e) {
    return false
  }
}

const updateFrameworkSizeAuto = async () => {
  if (frameworkSizeTouched.value) return
  // Prefer background size if user provided background, otherwise fallback to reference.
  try {
    if (posterStep2BackgroundFile.value) {
      const ok = await _updateFrameworkSizeFromFile(posterStep2BackgroundFile.value)
      if (ok) return
    }
    const bgUrl = String(step2BackgroundPreviewUrl.value || posterStep2BackgroundUrl.value || '').trim()
    if (bgUrl) {
      const ok = await _updateFrameworkSizeFromUrl(bgUrl)
      if (ok) return
    }
  } catch (e) {}

  try {
    if (refImageFile.value) {
      await _updateFrameworkSizeFromFile(refImageFile.value)
      return
    }
    const url = String(refPreviewUrl.value || refImageUrl.value || '').trim()
    if (!url) return
    await _updateFrameworkSizeFromUrl(url)
  } catch (e) {
    // ignore
  }
}

const updateFrameworkSizeFromRef = async () => {
  if (frameworkSizeTouched.value) return
  await updateFrameworkSizeAuto()
}

const newFrameworkSellpoint = (text = '') => {
  return { id: `${Date.now()}_${Math.random().toString(16).slice(2)}`, text: String(text || '') }
}

const addFrameworkSellpoint = () => {
  posterFramework.text.sellpoints.push(newFrameworkSellpoint(''))
}

const removeFrameworkSellpoint = (idx) => {
  const i = Number(idx)
  if (!Number.isFinite(i)) return
  if (i < 0 || i >= posterFramework.text.sellpoints.length) return
  posterFramework.text.sellpoints.splice(i, 1)
}

const fillFrameworkFromStep1 = (result) => {
  if (!result || typeof result !== 'object') return

  const w = Number(result.width || 0)
  const h = Number(result.height || 0)
  if (Number.isFinite(w) && w > 0) posterFramework.size.width = Math.round(w)
  if (Number.isFinite(h) && h > 0) posterFramework.size.height = Math.round(h)

  const els = Array.isArray(result.elements) ? result.elements : []
  posterOverlayBoxes.value = els
    .filter((e) => e && typeof e === 'object')
    .map((e) => {
      const id = String(e.id || '')
      const x0 = Number(e.x0 || 0)
      const y0 = Number(e.y0 || 0)
      const x1 = Number(e.x1 || 0)
      const y1 = Number(e.y1 || 0)
      return { id, x0, y0, x1, y1 }
    })

  const getTextById = (id) => {
    const el = els.find((e) => String(e?.id || '') === id)
    const t = el?.text
    if (typeof t === 'string' && t.trim()) return t.trim()
    return ''
  }

  const curTitle = String(posterFramework.text.title || '').trim()
  const curSubtitle = String(posterFramework.text.subtitle || '').trim()
  if (!curTitle) posterFramework.text.title = getTextById('title')
  if (!curSubtitle) posterFramework.text.subtitle = getTextById('subtitle')

  const sellpointEls = els
    .map((e) => {
      const id = String(e?.id || '')
      const m = id.match(/^sellpoint_(\d+)$/)
      if (!m) return null
      const n = Number(m[1])
      if (!Number.isFinite(n)) return null
      const t = typeof e?.text === 'string' ? e.text.trim() : ''
      return { n, text: t }
    })
    .filter(Boolean)
    .sort((a, b) => a.n - b.n)

  const curSellpoints = Array.isArray(posterFramework.text.sellpoints) ? posterFramework.text.sellpoints : []
  const curHasAnySellpointText = curSellpoints.some((sp) => String(sp?.text || '').trim())
  if (!curHasAnySellpointText) {
    posterFramework.text.sellpoints.splice(0, posterFramework.text.sellpoints.length)
    sellpointEls.forEach((sp) => {
      posterFramework.text.sellpoints.push(newFrameworkSellpoint(sp.text || ''))
    })
  }

  try {
    const nextIcons = {}
    const curIcons = posterFramework.icons && typeof posterFramework.icons === 'object' ? posterFramework.icons : {}
    ;['title', 'subtitle'].forEach((k) => {
      const prev = curIcons[k]
      if (prev && typeof prev === 'object' && Array.isArray(prev.items)) nextIcons[k] = { items: prev.items.slice() }
      else nextIcons[k] = { items: [] }
    })
    for (let i = 0; i < sellpointEls.length; i++) {
      const k = `sellpoint_${i + 1}`
      const prev = curIcons[k]
      if (prev && typeof prev === 'object' && Array.isArray(prev.items)) nextIcons[k] = { items: prev.items.slice() }
      else nextIcons[k] = { items: [] }
    }
    posterFramework.icons = nextIcons
  } catch (e) {}
}

const step2ProductObjectUrl = ref('')
const step2BackgroundObjectUrl = ref('')

watch(
  () => posterStep2ProductFile.value,
  (f) => {
    try {
      if (step2ProductObjectUrl.value) URL.revokeObjectURL(step2ProductObjectUrl.value)
    } catch (e) {}
    step2ProductObjectUrl.value = ''
    try {
      if (f) step2ProductObjectUrl.value = URL.createObjectURL(f)
    } catch (e) {}
  }
)

watch(
  () => posterStep2BackgroundFile.value,
  (f) => {
    try {
      if (step2BackgroundObjectUrl.value) URL.revokeObjectURL(step2BackgroundObjectUrl.value)
    } catch (e) {}
    step2BackgroundObjectUrl.value = ''
    try {
      if (f) step2BackgroundObjectUrl.value = URL.createObjectURL(f)
    } catch (e) {}
  }
)

onBeforeUnmount(() => {
  try {
    if (step2ProductObjectUrl.value) URL.revokeObjectURL(step2ProductObjectUrl.value)
  } catch (e) {}
  try {
    if (step2BackgroundObjectUrl.value) URL.revokeObjectURL(step2BackgroundObjectUrl.value)
  } catch (e) {}
})

const step2ProductPreviewUrl = computed(() => {
  return step2ProductObjectUrl.value || posterStep2ProductUrl.value || ''
})

const step2BackgroundPreviewUrl = computed(() => {
  return step2BackgroundObjectUrl.value || posterStep2BackgroundUrl.value || ''
})

const previewBaseUrl = computed(() => {
  return posterImageEditResultUrl.value || step2BackgroundPreviewUrl.value || refPreviewUrl.value || ''
})

const previewProductUrl = computed(() => {
  if (posterImageEditResultUrl.value) return ''
  return step2ProductPreviewUrl.value || ''
})

const previewBaseSize = computed(() => {
  const res = posterAnalysisResult.value
  const w = Number(res?.width || 0)
  const h = Number(res?.height || 0)
  return { w: Math.max(1, Math.round(w || 1)), h: Math.max(1, Math.round(h || 1)) }
})

const previewContainerStyle = computed(() => {
  const sz = previewBaseSize.value
  return { aspectRatio: `${sz.w} / ${sz.h}` }
})

const previewShowBoxes = ref(false)
const previewCanvasRef = ref(null)
const previewBgRef = ref(null)
const previewCanvasWidthPx = ref(0)
const previewCanvasHeightPx = ref(0)
const previewBgNatural = reactive({ w: 0, h: 0 })

const previewScale = computed(() => {
  const sz = previewBaseSize.value
  const w = Number(sz.w || 1)
  const px = Number(previewCanvasWidthPx.value || 0)
  if (!Number.isFinite(w) || w <= 0) return 1
  if (!Number.isFinite(px) || px <= 0) return 1
  return Math.max(0.1, px / w)
})

let previewResizeObserver = null
onMounted(() => {
  try {
    if (typeof ResizeObserver === 'undefined') return
    previewResizeObserver = new ResizeObserver((entries) => {
      const el = previewCanvasRef.value
      if (!el) return
      const rect = el.getBoundingClientRect?.()
      const w = rect?.width || el.clientWidth || 0
      const h = rect?.height || el.clientHeight || 0
      previewCanvasWidthPx.value = Number(w || 0)
      previewCanvasHeightPx.value = Number(h || 0)
    })
    if (previewCanvasRef.value) previewResizeObserver.observe(previewCanvasRef.value)
  } catch (e) {}
})

watch(
  () => previewBaseUrl.value,
  async () => {
    await nextTick()
    try {
      if (previewResizeObserver && previewCanvasRef.value) {
        previewResizeObserver.disconnect()
        previewResizeObserver.observe(previewCanvasRef.value)
      }
    } catch (e) {}
    try {
      const el = previewCanvasRef.value
      if (!el) return
      const rect = el.getBoundingClientRect?.()
      const w = rect?.width || el.clientWidth || 0
      const h = rect?.height || el.clientHeight || 0
      previewCanvasWidthPx.value = Number(w || 0)
      previewCanvasHeightPx.value = Number(h || 0)
    } catch (e) {}
  }
)

onBeforeUnmount(() => {
  try {
    if (previewResizeObserver) previewResizeObserver.disconnect()
  } catch (e) {}
  previewResizeObserver = null
})

const onPreviewBgLoad = () => {
  try {
    const img = previewBgRef.value
    if (!img) return
    const nw = Number(img.naturalWidth || 0)
    const nh = Number(img.naturalHeight || 0)
    if (Number.isFinite(nw) && nw > 0) previewBgNatural.w = nw
    if (Number.isFinite(nh) && nh > 0) previewBgNatural.h = nh
  } catch (e) {}
}

const bboxToPreviewStyle = (bb) => {
  // Treat Step1 bbox as layout template on the canvas (container).
  const cw = Number(previewCanvasWidthPx.value || 0)
  const ch = Number(previewCanvasHeightPx.value || 0)
  if (!bb || cw <= 0 || ch <= 0) return null

  // When preview background uses object-fit: contain, compute the actual rendered image rect
  // and place overlay boxes inside it so the whole image is visible without cropping.
  const nw = Number(previewBgNatural.w || 0)
  const nh = Number(previewBgNatural.h || 0)
  let renderW = cw
  let renderH = ch
  let offsetX = 0
  let offsetY = 0
  if (Number.isFinite(nw) && nw > 0 && Number.isFinite(nh) && nh > 0) {
    const s = Math.min(cw / nw, ch / nh)
    renderW = nw * s
    renderH = nh * s
    offsetX = (cw - renderW) / 2
    offsetY = (ch - renderH) / 2
  }

  const leftPx = offsetX + (bb.x0 / 1000) * renderW
  const topPx = offsetY + (bb.y0 / 1000) * renderH
  const widthPx = ((bb.x1 - bb.x0) / 1000) * renderW
  const heightPx = ((bb.y1 - bb.y0) / 1000) * renderH
  return {
    left: `${(leftPx / cw) * 100}%`,
    top: `${(topPx / ch) * 100}%`,
    width: `${(widthPx / cw) * 100}%`,
    height: `${(heightPx / ch) * 100}%`,
    widthPx,
    heightPx,
  }
}

const estimateFontSizeBasePx = (text, boxW, boxH, { kind } = {}) => {
  const t = String(text || '').trim()
  if (!t) return Math.max(12, Math.round(boxH * 0.5))
  const w = Math.max(1, Number(boxW || 1))
  const h = Math.max(1, Number(boxH || 1))
  const lineH = 1.18
  let fs = h * 0.72
  if (kind === 'sellpoint') fs *= 0.9
  if (kind === 'subtitle') fs *= 0.95
  fs = Math.max(10, Math.min(fs, 180))

  const avgChar = 0.56
  for (let i = 0; i < 8; i++) {
    const charsPerLine = Math.max(1, Math.floor(w / (fs * avgChar)))
    const lines = Math.max(1, Math.ceil(t.length / charsPerLine))
    const needH = lines * fs * lineH
    if (needH <= h && fs * avgChar * Math.min(t.length, charsPerLine) <= w * 1.02) break
    fs *= 0.88
    if (fs < 9) break
  }
  return Math.max(10, Math.round(fs))
}

const fontForElement = (el) => {
  const result = posterAnalysisResult.value
  const fg = result?.font_guess
  const id = String(el?.id || '')
  let name = null
  try {
    if (fg && typeof fg === 'object') {
      if (fg[id] && typeof fg[id] === 'object') {
        name = fg[id].name
      }
    }
  } catch (e) {}
  const n = typeof name === 'string' && name.trim() ? name.trim() : ''
  if (!n) return 'system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", sans-serif'
  return `"${n}", system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", sans-serif`
}

const weightForElement = (el) => {
  const id = String(el?.id || '')
  if (id === 'title') return 700
  if (id === 'subtitle') return 600
  if (/^sellpoint_\d+$/.test(id)) return 600
  return 600
}

const normalizePreviewBbox = (el) => {
  const bbox = Array.isArray(el?.bbox) ? el.bbox : null
  if (!bbox || bbox.length !== 4) return null
  let y0 = Number(bbox[0])
  let x0 = Number(bbox[1])
  let y1 = Number(bbox[2])
  let x1 = Number(bbox[3])
  if (![y0, x0, y1, x1].every((n) => Number.isFinite(n))) return null

  const type = String(el?.type || '').toLowerCase()
  const idText = String(el?.id || '').toLowerCase()
  const labelText = String(el?.label || '').toLowerCase()
  const keyText = `${idText} ${labelText}`
  const iconLike =
    keyText.includes('icon') ||
    keyText.includes('badge') ||
    keyText.includes('logo') ||
    keyText.includes('stamp') ||
    keyText.includes('tag') ||
    keyText.includes('label') ||
    keyText.includes('drone')
  const w = x1 - x0
  const h = y1 - y0
  if (w > 0 && h > 0) {
    if (type === 'text') {
      if (w < h) {
        ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
      }
    } else if (iconLike) {
      if (w < h) {
        ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
      }
    } else if (type === 'product' || type === 'image') {
      if (h < w) {
        ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
      }
    }
  }
  if (y1 <= y0 || x1 <= x0) return null

  // Step1 bbox is normalized to 0..1000.
  const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n))
  y0 = clamp(y0, 0, 1000)
  y1 = clamp(y1, 0, 1000)
  x0 = clamp(x0, 0, 1000)
  x1 = clamp(x1, 0, 1000)
  if (y1 <= y0 || x1 <= x0) return null

  return { y0, x0, y1, x1 }
}

const previewProductStyle = computed(() => {
  const result = posterAnalysisResult.value
  const els = Array.isArray(result?.elements) ? result.elements : []
  const el = els.find((e) => String(e?.id || '') === 'main_product')
  if (!el) return {}
  const bb = normalizePreviewBbox(el)
  if (!bb) return {}
  const st = bboxToPreviewStyle(bb)
  if (!st) return {}
  return { left: st.left, top: st.top, width: st.width, height: st.height }
})

const previewTextBoxes = computed(() => {
  const result = posterAnalysisResult.value
  const els = Array.isArray(result?.elements) ? result.elements : []
  const boxes = []
  els.forEach((el, idx) => {
    const type = String(el?.type || '').toLowerCase()
    if (type !== 'text') return
    const bb = normalizePreviewBbox(el)
    if (!bb) return
    const st = bboxToPreviewStyle(bb)
    if (!st) return
    const id = String(el?.id || '')
    boxes.push({
      key: String(id || idx),
      style: {
        left: st.left,
        top: st.top,
        width: st.width,
        height: st.height,
      },
    })
  })
  return boxes
})

const previewTextItems = computed(() => {
  if (posterImageEditResultUrl.value) return []
  const result = posterAnalysisResult.value
  const els = Array.isArray(result?.elements) ? result.elements : []
  const sz = previewBaseSize.value

  const idToText = {}
  if (typeof posterFramework.text.title === 'string' && posterFramework.text.title.trim()) idToText.title = posterFramework.text.title.trim()
  if (typeof posterFramework.text.subtitle === 'string' && posterFramework.text.subtitle.trim()) idToText.subtitle = posterFramework.text.subtitle.trim()
  const sps = Array.isArray(posterFramework.text.sellpoints) ? posterFramework.text.sellpoints : []
  sps.forEach((sp, idx) => {
    const t = String(sp?.text || '').trim()
    if (!t) return
    idToText[`sellpoint_${idx + 1}`] = t
  })

  const items = []
  els.forEach((el, idx) => {
    const type = String(el?.type || '').toLowerCase()
    if (type !== 'text') return
    const bb = normalizePreviewBbox(el)
    if (!bb) return
    const st = bboxToPreviewStyle(bb)
    if (!st) return
    const id = String(el?.id || '')
    const fallbackText = typeof el?.text === 'string' ? el.text.trim() : ''
    const text = String(idToText[id] || fallbackText || el?.label || id || '').trim()
    if (!text) return
    const kind = id === 'title' ? 'title' : (id === 'subtitle' ? 'subtitle' : (/^sellpoint_\d+$/.test(id) ? 'sellpoint' : 'other'))
    // Font fitting should happen in pixels. Prefer rendered size (after contain) to avoid drift.
    const boxWpx = Number(st.widthPx || 0) || (((bb.x1 - bb.x0) / 1000) * Number(sz.w || 1))
    const boxHpx = Number(st.heightPx || 0) || (((bb.y1 - bb.y0) / 1000) * Number(sz.h || 1))
    const baseFont = estimateFontSizeBasePx(text, boxWpx, boxHpx, { kind })
    const px = Math.max(10, Math.round(baseFont))

    const iconItems = getIconItems(id)
    const desiredIcon = Math.max(10, Math.min(44, Math.round(boxHpx * 0.62)))
    const gap = 4
    const minTextW = 40
    let iconSize = desiredIcon
    let visibleIcons = iconItems.map((x) => x.src)
    if (visibleIcons.length) {
      const maxSizeByWidth = Math.floor((Math.max(0, boxWpx - minTextW - gap * (visibleIcons.length - 1))) / visibleIcons.length)
      if (Number.isFinite(maxSizeByWidth) && maxSizeByWidth > 0) iconSize = Math.min(iconSize, maxSizeByWidth)
      iconSize = Math.max(10, iconSize)
      const fullWidth = visibleIcons.length * iconSize + gap * (visibleIcons.length - 1)
      const maxIcons = Math.max(0, Math.floor((Math.max(0, boxWpx - minTextW + gap)) / (iconSize + gap)))
      if (fullWidth > Math.max(0, boxWpx - minTextW)) {
        if (maxIcons <= 0) visibleIcons = []
        else if (maxIcons < visibleIcons.length) visibleIcons = visibleIcons.slice(0, maxIcons)
      }
    }

    const iconsWidth = visibleIcons.length ? (visibleIcons.length * iconSize + gap * (visibleIcons.length - 1)) : 0
    const paddingLeft = iconsWidth ? (iconsWidth + 8) : 0
    items.push({
      key: String(id || idx),
      text,
      icons: visibleIcons,
      iconSize,
      style: {
        left: st.left,
        top: st.top,
        width: st.width,
        fontSize: `${px}px`,
        fontFamily: fontForElement(el),
        fontWeight: weightForElement(el),
      },
      innerStyle: paddingLeft ? { paddingLeft: `${paddingLeft}px` } : null,
      iconsStyle: visibleIcons.length ? { left: '0px', top: '50%', transform: 'translateY(-50%)', gap: `${gap}px` } : null,
    })
  })
  return items
})

const posterOverlayTextMap = computed(() => {
  const step2 = posterStep2Result.value
  const copy = step2?.copy
  if (!copy || typeof copy !== 'object') return {}

  const out = {}
  if (typeof copy.title === 'string' && copy.title.trim()) out.title = copy.title.trim()
  if (typeof copy.subtitle === 'string' && copy.subtitle.trim()) out.subtitle = copy.subtitle.trim()
  if (typeof copy.cta === 'string' && copy.cta.trim()) out.cta = copy.cta.trim()
  if (typeof copy.footer === 'string' && copy.footer.trim()) out.footer = copy.footer.trim()
  if (Array.isArray(copy.sellpoints)) {
    const sp = copy.sellpoints.map((s) => String(s || '').trim()).filter(Boolean)
    sp.forEach((t, i) => {
      out[`sellpoint_${i + 1}`] = t
    })
  }
  return out
})

const posterOverlayBoxes = computed(() => {
  const result = posterAnalysisResult.value
  const els = result?.elements
  if (!Array.isArray(els) || els.length === 0) return []

  const textMap = posterOverlayTextMap.value || {}

  const safe = (v) => {
    const n = Number(v)
    if (!Number.isFinite(n)) return 0
    return Math.max(0, Math.min(1000, n))
  }

  const toBox = (el, idx) => {
    const bbox = Array.isArray(el?.bbox) ? el.bbox : null
    if (!bbox || bbox.length !== 4) return null
    let y0 = safe(bbox[0])
    let x0 = safe(bbox[1])
    let y1 = safe(bbox[2])
    let x1 = safe(bbox[3])

    const type = String(el?.type || '').toLowerCase()
    const idText = String(el?.id || '').toLowerCase()
    const labelText = String(el?.label || '').toLowerCase()
    const keyText = `${idText} ${labelText}`
    const iconLike =
      keyText.includes('icon') ||
      keyText.includes('badge') ||
      keyText.includes('logo') ||
      keyText.includes('stamp') ||
      keyText.includes('tag') ||
      keyText.includes('label') ||
      keyText.includes('drone')
    const w = x1 - x0
    const h = y1 - y0

    // Heuristic: if bbox seems to be [xmin,ymin,xmax,ymax], swap it.
    if (w > 0 && h > 0) {
      if (type === 'text') {
        // text should be wide
        if (w < h) {
          ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
        }
      } else if (iconLike) {
        // icons/badges/logos are typically wide and short
        if (w < h) {
          ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
        }
      } else if (type === 'product' || type === 'image') {
        // product in posters tends to be tall
        if (h < w) {
          ;[y0, x0, y1, x1] = [x0, y0, x1, y1]
        }
      }
    }
    if (y1 <= y0 || x1 <= x0) return null
    const left = (x0 / 1000) * 100
    const top = (y0 / 1000) * 100
    const width = ((x1 - x0) / 1000) * 100
    const height = ((y1 - y0) / 1000) * 100
    const elId = String(el?.id || '')
    const mapped = elId ? textMap[elId] : ''
    const label = String(mapped || el?.label || el?.id || `box_${idx}`)
    return {
      key: String(el?.id || idx),
      label,
      style: {
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
      },
    }
  }

  return els.map(toBox).filter(Boolean)
})

const togglePanel = () => {
  rightPanelOpen.value = !rightPanelOpen.value
  if (rightPanelOpen.value && !rightPanelKey.value) {
    rightPanelKey.value = 'props'
  }
}

const activeObject = computed(() => activeObjectRef.value)

const activeIsTextbox = computed(() => {
  const o = activeObject.value
  return !!o && String(o.type || '') === 'textbox'
})

const textTool = reactive({
  fontFamily: 'system-ui',
  fontSize: 32,
  fill: '#ffffff',
  bold: false,
})

const textToolFontOptions = computed(() => {
  const opts = new Set([
    'system-ui',
    'Inter',
    'Roboto',
    'Montserrat',
    'Poppins',
    'Oswald',
    'Bebas Neue',
    'Noto Sans',
    'Noto Serif',
    'Noto Sans SC',
    'Noto Serif SC',
    'Source Han Sans SC',
    'Source Han Serif SC',
    'Alibaba PuHuiTi',
  ])
  try {
    const fg = posterAnalysisResult.value?.font_guess
    if (fg && typeof fg === 'object') {
      Object.values(fg).forEach((v) => {
        const n = v?.name
        if (typeof n === 'string' && n.trim()) opts.add(n.trim())
      })
    }
  } catch (e) {}
  return Array.from(opts)
})

const syncTextToolFromActive = () => {
  const o = activeObject.value
  if (!o || String(o.type || '') !== 'textbox') return
  try {
    const ff = typeof o.fontFamily === 'string' && o.fontFamily.trim() ? o.fontFamily.trim() : 'system-ui'
    const fs = Number(o.fontSize || 0)
    const fill = typeof o.fill === 'string' && o.fill.trim() ? o.fill.trim() : '#ffffff'
    const fw = String(o.fontWeight || '').trim()
    textTool.fontFamily = ff
    textTool.fontSize = Number.isFinite(fs) && fs > 0 ? Math.round(fs) : 32
    textTool.fill = fill.startsWith('#') ? fill : '#ffffff'
    textTool.bold = fw === '700' || fw === 'bold' || Number(fw) >= 700
  } catch (e) {}
}

const onTextToolChange = (key, value) => {
  const canvas = canvasInstance.value
  const o = activeObject.value
  if (!canvas || !o || String(o.type || '') !== 'textbox') return
  try {
    if (key === 'fontFamily') {
      const v = String(value || '').trim() || 'system-ui'
      textTool.fontFamily = v
      o.set({ fontFamily: v })
    } else if (key === 'fontSize') {
      const n = Math.max(8, Math.min(300, Math.round(Number(value || 0) || 0)))
      if (!Number.isFinite(n) || n <= 0) return
      textTool.fontSize = n
      o.set({ fontSize: n })
    } else if (key === 'fill') {
      const v = String(value || '').trim() || '#ffffff'
      textTool.fill = v
      o.set({ fill: v })
    }
    if (typeof o.setCoords === 'function') o.setCoords()
    canvas.requestRenderAll()
    updateObjOverlay()
    scheduleHistory()
  } catch (e) {}
}

const toggleTextBold = () => {
  const canvas = canvasInstance.value
  const o = activeObject.value
  if (!canvas || !o || String(o.type || '') !== 'textbox') return
  try {
    textTool.bold = !textTool.bold
    const fw = textTool.bold ? 700 : 400
    o.set({ fontWeight: fw })
    if (typeof o.setCoords === 'function') o.setCoords()
    canvas.requestRenderAll()
    updateObjOverlay()
    scheduleHistory()
  } catch (e) {}
}

const layerItems = computed(() => {
  const canvas = canvasInstance.value
  if (!canvas) return []
  const items = []
  try {
    const objs = canvas.getObjects ? canvas.getObjects() : []
    objs.forEach((o, idx) => {
      if (!o) return
      if (o?.data?.role === 'artboard') return
      const id = o.__uid || o.__objectId || String(idx)
      const type = o.type || 'object'
      const w = Math.round(Math.abs(o.getScaledWidth ? o.getScaledWidth() : (o.width || 0) * (o.scaleX || 1)))
      const h = Math.round(Math.abs(o.getScaledHeight ? o.getScaledHeight() : (o.height || 0) * (o.scaleY || 1)))
      let label = '对象'
      if (type === 'image') label = '图片'
      if (type === 'textbox') label = String(o.text || '').trim() ? String(o.text).slice(0, 18) : '双击编辑文字'
      const lockedBottom = isLockedBottomLayer(o)
      items.push({
        id,
        obj: o,
        label,
        meta: `${w}×${h}`,
        lockedBottom,
      })
    })
  } catch (e) {
    // ignore
  }
  return items
})

const activeLayerId = computed(() => {
  const o = activeObject.value
  if (!o) return ''
  return o.__uid || o.__objectId || ''
})

const selectLayer = (id) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const target = (layerItems.value || []).find((x) => x.id === id)?.obj
  if (!target) return
  try {
    canvas.setActiveObject(target)
    canvas.requestRenderAll()
  } catch (e) {}
  syncPropFormFromActive()
  updateObjOverlay()
  syncTextToolFromActive()
}

const syncPropFormFromActive = () => {
  const o = activeObjectRef.value
  if (!o) return
  propForm.x = Math.round(Number(o.left ?? 0))
  propForm.y = Math.round(Number(o.top ?? 0))
  const sx = Number(o.scaleX ?? 1) || 1
  const sy = Number(o.scaleY ?? 1) || 1
  propForm.scale = Number(((sx + sy) / 2).toFixed(4))
  propForm.angle = Math.round(Number(o.angle ?? 0))
  try {
    syncTextToolFromActive()
  } catch (e) {}
  propForm.opacity = Number((Number(o.opacity ?? 1)).toFixed(3))
}

const applyPropForm = () => {
  const canvas = canvasInstance.value
  const o = activeObjectRef.value
  if (!canvas || !o) return
  try {
    const x = Number(propForm.x ?? o.left ?? 0)
    const y = Number(propForm.y ?? o.top ?? 0)
    const s = clamp(Number(propForm.scale ?? 1), 0.02, 50)
    const ang = Number(propForm.angle ?? 0)
    const op = clamp(Number(propForm.opacity ?? 1), 0, 1)
    o.set({ left: x, top: y, scaleX: s, scaleY: s, angle: ang, opacity: op })
    if (typeof o.setCoords === 'function') o.setCoords()
    canvas.requestRenderAll()
  } catch (e) {}
  updateObjOverlay()
}

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
    if (resizeState.mode === 'width') {
      const pointer = canvas.getPointer(e)
      const dx = (pointer?.x || 0) - (resizeState.startPointer?.x || 0)
      const rect0 = resizeState.startRect || { left: 0, top: 0, width: 0, height: 0 }
      const scaleX = Number(obj.scaleX ?? 1) || 1
      const w0 = Math.max(1, Number(rect0.width || 1))
      let w1 = w0
      if (resizeState.corner === 'mr') {
        w1 = w0 + dx
      } else if (resizeState.corner === 'ml') {
        w1 = w0 - dx
      }
      w1 = Math.max(10, w1)
      const nextWidth = Math.max(1, w1 / Math.max(1e-6, Math.abs(scaleX)))
      obj.set({ width: nextWidth })
      try { if (typeof obj.setCoords === 'function') obj.setCoords() } catch (e2) {}
      const rect1 = obj.getBoundingRect?.(true, true)
      if (rect1) {
        if (resizeState.corner === 'mr') {
          const dxFix = (rect0.left || 0) - (rect1.left || 0)
          obj.set({ left: (obj.left || 0) + dxFix })
        } else if (resizeState.corner === 'ml') {
          const r0 = (rect0.left || 0) + (rect0.width || 0)
          const r1 = (rect1.left || 0) + (rect1.width || 0)
          const dxFix = r0 - r1
          obj.set({ left: (obj.left || 0) + dxFix })
        }
        try { if (typeof obj.setCoords === 'function') obj.setCoords() } catch (e3) {}
      }
    } else {
      const pointer = canvas.getPointer(e)
      const ratio = _dist(pointer, resizeState.anchor) / (resizeState.startDist || 1)
      const base = resizeState.startScaleX || 1
      const s = clamp(base * ratio, 0.02, 50)
      obj.set({ scaleX: s, scaleY: s })
      if (typeof obj.setCoords === 'function') obj.setCoords()

      const coords = typeof obj.getCoords === 'function' ? obj.getCoords() : null
      if (coords && coords.length >= 4) {
        const idxOpp = _cornerIndex(resizeState.oppCorner)
        const nowAnchor = coords[idxOpp]
        const dx2 = (resizeState.anchor?.x || 0) - (nowAnchor?.x || 0)
        const dy2 = (resizeState.anchor?.y || 0) - (nowAnchor?.y || 0)
        obj.set({ left: (obj.left || 0) + dx2, top: (obj.top || 0) + dy2 })
        if (typeof obj.setCoords === 'function') obj.setCoords()
      }
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
  const obj = resizeState.obj
  resizeState.active = false
  resizeState.mode = 'uniform'
  resizeState.obj = null
  resizeState.pointerId = null
  try {
    window.removeEventListener('pointermove', onResizeHandleMove, true)
    window.removeEventListener('pointerup', onResizeHandleUp, true)
    window.removeEventListener('pointercancel', onResizeHandleUp, true)
  } catch (err) {}
  try {
    if (resizeState.corner === 'ml' || resizeState.corner === 'mr') {
      scheduleHistory()
      return
    }
    if (obj && String(obj.type || '') === 'textbox') {
      bakeTextboxScaling(obj)
      return
    }
  } catch (err) {}
  try {
    scheduleHistory()
  } catch (err) {}
}

const onResizeHandleDown = (cornerKey, e) => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj) return
  const t = String(obj.type || '')
  const isSide = cornerKey === 'ml' || cornerKey === 'mr'
  if (isSide) {
    if (t !== 'textbox') return
    const a0 = ((Number(obj.angle ?? 0) % 360) + 360) % 360
    const a = Math.min(a0, 360 - a0)
    if (a > 0.5) return
  } else {
    if (t !== 'image' && t !== 'textbox') return
  }
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

  const pointer = canvas.getPointer(e)
  resizeState.startPointer = { x: pointer?.x || 0, y: pointer?.y || 0 }
  const br0 = obj.getBoundingRect?.(true, true)
  resizeState.startRect = {
    left: Number(br0?.left ?? 0),
    top: Number(br0?.top ?? 0),
    width: Number(br0?.width ?? 0),
    height: Number(br0?.height ?? 0),
  }

  if (isSide) {
    resizeState.active = true
    resizeState.mode = 'width'
    resizeState.corner = cornerKey
    resizeState.oppCorner = ''
    resizeState.startDist = 1
    resizeState.startScaleX = Number(obj.scaleX ?? 1) || 1
    resizeState.startScaleY = Number(obj.scaleY ?? 1) || 1
    resizeState.anchor = { x: 0, y: 0 }
    resizeState.obj = obj
    resizeState.pointerId = e.pointerId
  } else {
    const coords = typeof obj.getCoords === 'function' ? obj.getCoords() : null
    if (!coords || coords.length < 4) return

    const oppCorner = _oppCornerKey(cornerKey)
    const idxOpp = _cornerIndex(oppCorner)
    const anchor = coords[idxOpp]
    const startDist = Math.max(1e-6, _dist(pointer, anchor))

    resizeState.active = true
    resizeState.mode = 'uniform'
    resizeState.corner = cornerKey
    resizeState.oppCorner = oppCorner
    resizeState.startDist = startDist
    resizeState.startScaleX = Number(obj.scaleX ?? 1) || 1
    resizeState.startScaleY = Number(obj.scaleY ?? 1) || 1
    resizeState.anchor = { x: anchor.x, y: anchor.y }
    resizeState.obj = obj
    resizeState.pointerId = e.pointerId
  }

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
      try {
        if (!o) return
        const tl = String(o.type || '').toLowerCase()
        if (tl === 'group' || tl === 'activeselection') {
          refreshFabricCoords(o)
          return
        }
        if (typeof o.setCoords === 'function') o.setCoords()
      } catch (e) {}
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
    const tl = String(obj?.type || '').toLowerCase()
    if (tl === 'group' || tl === 'activeselection') {
      refreshFabricCoords(obj)
    } else if (typeof obj.setCoords === 'function') {
      obj.setCoords()
    }
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

  activeObjectRef.value = obj || null
  syncPropFormFromActive()

  const t = obj ? String(obj.type || '') : ''
  const tl = t.toLowerCase()
  const supported = tl === 'image' || tl === 'textbox' || tl === 'activeselection' || tl === 'group'
  const singleObject = tl === 'image' || tl === 'textbox'
  if (!obj || !supported) {
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

  // size tag only for images (single object only)
  if (t === 'image' && singleObject) {
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
  } else {
    objOverlay.sizeVisible = false
  }

  // Custom resize handles only apply to single objects.
  if (!singleObject) {
    resizeOverlay.visible = false
    return
  }

  resizeOverlay.visible = true
  resizeOverlay.handles = [
    { key: 'tl', x: sr.left, y: sr.top },
    { key: 'tr', x: sr.right, y: sr.top },
    { key: 'br', x: sr.right, y: sr.bottom },
    { key: 'bl', x: sr.left, y: sr.bottom },
  ]
  try {
    const tl2 = String(obj?.type || '').toLowerCase()
    if (tl2 === 'textbox') {
      const a0 = ((Number(obj.angle ?? 0) % 360) + 360) % 360
      const a = Math.min(a0, 360 - a0)
      if (a <= 0.5) {
        const midY = (sr.top + sr.bottom) / 2
        resizeOverlay.handles.push({ key: 'ml', x: sr.left, y: midY })
        resizeOverlay.handles.push({ key: 'mr', x: sr.right, y: midY })
      }
    }
  } catch (e) {}

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

      try {
        if (window.__posterDebug) {
          // eslint-disable-next-line no-console
          console.log('[PosterDebug] wheel', { z })
        }
      } catch (e1) {}

      applyZoom()
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
      sanitizeActiveSelection()
      recalcAllObjectCoords()
      activeObjectRef.value = canvas.getActiveObject() || null
      syncPropFormFromActive()
      updateObjOverlay()
    })
    canvas.on('selection:updated', () => {
      sanitizeActiveSelection()
      recalcAllObjectCoords()
      activeObjectRef.value = canvas.getActiveObject() || null
      syncPropFormFromActive()
      updateObjOverlay()
    })
    canvas.on('selection:cleared', () => {
      activeObjectRef.value = null
      updateObjOverlay()
      resizeOverlay.visible = false
      resizeState.active = false
      clearSnapGuides()
    })
    canvas.on('object:moving', handleObjectMovingWithSnap)
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

    canvas.on('object:modified', () => {
      clearSnapGuides()
    })
    canvas.on('after:render', renderSnapGuides)

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

    // Enable undo/redo after optional draft restore.
    initHistoryForCanvas()
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

let exportToCanvasCount = 0
const exportPreviewToCanvas = async () => {
  const canvas = canvasInstance.value
  if (!canvas) {
    ElMessage.error('画布未初始化成功')
    return
  }
  // If image-edit result exists, export it as a single editable image.
  if (posterImageEditResultUrl.value) {
    const url = String(posterImageEditResultUrl.value || '').trim()
    if (!url) {
      ElMessage.error('生成海报图片不存在')
      return
    }
    const c = getViewportCenterInWorld()
    try {
      const img = await FabricImage.fromURL(url, { crossOrigin: 'anonymous' })
      const maxW = POSTER_CANVAS_WIDTH * 0.8
      const maxH = POSTER_CANVAS_HEIGHT * 0.8
      const rawW = img?.width || 1
      const rawH = img?.height || 1
      const scale = Math.min(maxW / rawW, maxH / rawH, 1)
      img.set({
        left: c.x - (rawW * scale) / 2,
        top: c.y - (rawH * scale) / 2,
        scaleX: scale,
        scaleY: scale,
      })
      img.data = { ...(img.data || {}), role: 'poster_image_edit' }
      applySelectionStyle(img)
      try { if (typeof img.setCoords === 'function') img.setCoords() } catch (e) {}
      canvas.add(img)
      canvas.setActiveObject(img)
      canvas.requestRenderAll()
      updateObjOverlay()
      fitToScreen()
      ElMessage.success('已导出生成海报到画布')
    } catch (e) {
      console.error('export image-edit failed:', e)
      ElMessage.error('导出到画布失败')
    }
    return
  }
  if (!posterAnalysisResult.value) {
    ElMessage.warning('请先完成参考图分析')
    return
  }
  const W = Math.max(1, Math.round(Number(posterFramework.size.width || posterAnalysisResult.value?.width || POSTER_CANVAS_WIDTH || 1000)))
  const H = Math.max(1, Math.round(Number(posterFramework.size.height || posterAnalysisResult.value?.height || POSTER_CANVAS_HEIGHT || 1500)))

  const els = Array.isArray(posterAnalysisResult.value?.elements) ? posterAnalysisResult.value.elements : []
  const bboxById = (id) => {
    const el = els.find((e) => String(e?.id || '') === id)
    const bbox = Array.isArray(el?.bbox) ? el.bbox : null
    if (!bbox || bbox.length !== 4) return null
    const y0 = Number(bbox[0])
    const x0 = Number(bbox[1])
    const y1 = Number(bbox[2])
    const x1 = Number(bbox[3])
    if (![y0, x0, y1, x1].every((n) => Number.isFinite(n))) return null
    if (y1 <= y0 || x1 <= x0) return null
    return { y0, x0, y1, x1 }
  }
  const rectFromBbox = (bb) => {
    if (!bb) return null
    return {
      left: (bb.x0 / 1000) * W,
      top: (bb.y0 / 1000) * H,
      width: ((bb.x1 - bb.x0) / 1000) * W,
      height: ((bb.y1 - bb.y0) / 1000) * H,
    }
  }

  const center = getViewportCenterInWorld()
  exportToCanvasCount += 1
  const nudge = 28 * exportToCanvasCount
  const originLeft = center.x - W / 2 + nudge
  const originTop = center.y - H / 2 + nudge

  const addLockedImageCover = async (src, { w, h, left, top } = {}) => {
    const url = String(src || '').trim()
    if (!url) return null
    const img = await FabricImage.fromURL(url, { crossOrigin: 'anonymous' })
    const iw = Number(img.width || 1)
    const ih = Number(img.height || 1)
    const cw = Number(w || 1)
    const ch = Number(h || 1)
    const scale = Math.max(cw / iw, ch / ih)
    const dw = iw * scale
    const dh = ih * scale
    img.set({
      left: Number(left || 0) + (cw - dw) / 2,
      top: Number(top || 0) + (ch - dh) / 2,
      scaleX: scale,
      scaleY: scale,
      selectable: false,
      evented: false,
      hasControls: false,
      hasBorders: false,
      lockMovementX: true,
      lockMovementY: true,
      lockScalingX: true,
      lockScalingY: true,
      lockRotation: true,
    })
    img.data = { ...(img.data || {}), role: 'poster_background' }
    return img
  }

  const addEditableImageContainBottom = async (src, box, { left, top } = {}) => {
    const url = String(src || '').trim()
    if (!url || !box) return null
    const img = await FabricImage.fromURL(url, { crossOrigin: 'anonymous' })
    const iw = Number(img.width || 1)
    const ih = Number(img.height || 1)
    const bw = Math.max(1, Number(box.width || 1))
    const bh = Math.max(1, Number(box.height || 1))
    const scale = Math.min(bw / iw, bh / ih)
    const dw = iw * scale
    const dh = ih * scale
    img.set({
      left: Number(left || 0) + Number(box.left || 0) + (bw - dw) / 2,
      top: Number(top || 0) + Number(box.top || 0) + (bh - dh),
      scaleX: scale,
      scaleY: scale,
    })
    img.data = { ...(img.data || {}), role: 'poster_product' }
    applySelectionStyle(img)
    return img
  }

  const addTextbox = (text, box, { fontFamily, fontWeight } = {}) => {
    if (!box) return null
    const t = String(text || '').trim()
    if (!t) return null
    const fs = estimateFontSizeBasePx(t, Number(box.width || 1), Number(box.height || 1), { kind: 'other' })
    const tb = new FabricTextbox(t, {
      left: originLeft + Number(box.left || 0),
      top: originTop + Number(box.top || 0),
      width: Math.max(1, Number(box.width || 1)),
      height: Math.max(1, Number(box.height || 1)),
      fontFamily: fontFamily || 'system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", sans-serif',
      fontSize: Math.max(10, Math.round(fs)),
      fontWeight: fontWeight || 600,
      fill: 'rgba(255,255,255,0.95)',
      lineHeight: 1.12,
      textAlign: 'left',
      shadow: new FabricShadow({ color: 'rgba(0,0,0,0.55)', blur: 8, offsetX: 0, offsetY: 2 }),
    })
    tb.data = { ...(tb.data || {}), role: 'poster_text' }
    applySelectionStyle(tb)
    return tb
  }

  try {
    const bg = await addLockedImageCover(previewBaseUrl.value, { w: W, h: H, left: originLeft, top: originTop })
    if (bg) canvas.add(bg)

    const productBox = rectFromBbox(bboxById('main_product'))
    const product = await addEditableImageContainBottom(previewProductUrl.value, productBox, { left: originLeft, top: originTop })
    if (product) canvas.add(product)

    // Map ids to texts from current framework (already contains Step2 overrides)
    const idToText = {}
    if (typeof posterFramework.text.title === 'string' && posterFramework.text.title.trim()) idToText.title = posterFramework.text.title.trim()
    if (typeof posterFramework.text.subtitle === 'string' && posterFramework.text.subtitle.trim()) idToText.subtitle = posterFramework.text.subtitle.trim()
    const sps = Array.isArray(posterFramework.text.sellpoints) ? posterFramework.text.sellpoints : []
    sps.forEach((sp, idx) => {
      const t = String(sp?.text || '').trim()
      if (!t) return
      idToText[`sellpoint_${idx + 1}`] = t
    })

    const fg = posterAnalysisResult.value?.font_guess
    const getFont = (id) => {
      try {
        const n = fg?.[id]?.name
        if (typeof n === 'string' && n.trim()) return `"${n.trim()}", system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", sans-serif`
      } catch (e) {}
      return 'system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", sans-serif'
    }

    const addTextById = async (id, kind) => {
      const bb = bboxById(id)
      const box = rectFromBbox(bb)
      if (!box) return
      const text = idToText[id] || ''
      if (!String(text || '').trim()) return
      const iconItems = getIconItems(id)
      const gap = 8
      const minTextW = 80
      const desiredIcon = Math.max(10, Math.min(64, Math.round(Number(box.height || 1) * 0.62)))
      let iconSize = desiredIcon
      let visible = iconItems.map((x) => x.src)
      if (visible.length) {
        const maxSizeByWidth = Math.floor((Math.max(0, Number(box.width || 1) - minTextW - gap * (visible.length - 1))) / visible.length)
        if (Number.isFinite(maxSizeByWidth) && maxSizeByWidth > 0) iconSize = Math.min(iconSize, maxSizeByWidth)
        iconSize = Math.max(10, iconSize)
        const full = visible.length * iconSize + gap * (visible.length - 1)
        const maxIcons = Math.max(0, Math.floor((Math.max(0, Number(box.width || 1) - minTextW + gap)) / (iconSize + gap)))
        if (full > Math.max(0, Number(box.width || 1) - minTextW)) {
          if (maxIcons <= 0) visible = []
          else if (maxIcons < visible.length) visible = visible.slice(0, maxIcons)
        }
      }

      let inset = 0
      if (visible.length) {
        inset = visible.length * iconSize + gap * (visible.length - 1) + 10
        const iconTop = originTop + Number(box.top || 0) + (Number(box.height || 1) - iconSize) / 2
        let x = originLeft + Number(box.left || 0)
        for (let i = 0; i < visible.length; i++) {
          const src = String(visible[i] || '').trim()
          if (!src) continue
          try {
            const img = await FabricImage.fromURL(src, { crossOrigin: 'anonymous' })
            const iw = Number(img.width || 0)
            const ih = Number(img.height || 0)
            if (iw > 0 && ih > 0) {
              const s = iconSize / Math.max(iw, ih)
              img.set({ left: x, top: iconTop, scaleX: s, scaleY: s })
              img.data = { ...(img.data || {}), role: 'poster_icon', posterId: id, posterIconIndex: i }
              applySelectionStyle(img)
              canvas.add(img)
            }
          } catch (e) {}
          x += iconSize + gap
        }
      }

      const fs = estimateFontSizeBasePx(String(text), Math.max(1, Number(box.width || 1) - inset), Number(box.height || 1), { kind })
      const tb = new FabricTextbox(String(text), {
        left: originLeft + Number(box.left || 0) + inset,
        top: originTop + Number(box.top || 0),
        width: Math.max(1, Number(box.width || 1) - inset),
        height: Math.max(1, Number(box.height || 1)),
        fontFamily: getFont(id),
        fontSize: Math.max(10, Math.round(fs)),
        fontWeight: id === 'title' ? 700 : 600,
        fill: 'rgba(255,255,255,0.95)',
        lineHeight: 1.12,
        textAlign: 'left',
        shadow: new FabricShadow({ color: 'rgba(0,0,0,0.55)', blur: 8, offsetX: 0, offsetY: 2 }),
      })
      tb.data = { ...(tb.data || {}), role: 'poster_text', posterId: id }
      applySelectionStyle(tb)
      canvas.add(tb)
    }

    await addTextById('title', 'title')
    await addTextById('subtitle', 'subtitle')
    for (let i = 1; i <= 5; i++) {
      await addTextById(`sellpoint_${i}`, 'sellpoint')
    }

    canvas.requestRenderAll()
    fitToScreen()
    ElMessage.success('已导出到画布（可编辑）')
  } catch (e) {
    console.error('exportPreviewToCanvas failed:', e)
    ElMessage.error('导出到画布失败')
  }
}

const triggerPickImage = () => {
  imageDialogTab.value = 'local'
  refreshKbProductImages()
  imageDialogPurpose.value = 'insert'
  imageDialogVisible.value = true
}

const triggerLocalImageUpload = () => {
  if (imageInputRef.value) imageInputRef.value.click()
}

const triggerRefLocalUpload = () => {
  if (refImageInputRef.value) refImageInputRef.value.click()
}

const openRefKbPicker = () => {
  rightPanelKey.value = 'gen'
  refreshKbProductImages()
  imageDialogTab.value = 'kb'
  imageDialogPurpose.value = 'ref'
  imageDialogVisible.value = true
}

const openStep2ProductKbPicker = () => {
  rightPanelKey.value = 'gen'
  refreshKbProductImages()
  imageDialogTab.value = 'kb'
  imageDialogPurpose.value = 'step2_product'
  imageDialogVisible.value = true
}

const openStep2BackgroundKbPicker = () => {
  rightPanelKey.value = 'gen'
  refreshKbProductImages()
  imageDialogTab.value = 'kb'
  imageDialogPurpose.value = 'step2_background'
  imageDialogVisible.value = true
}

const setReferenceImageFromUrl = (url) => {
  if (!url) return
  refImageFile.value = null
  refImageUrl.value = url
  refPreviewUrl.value = url
  updateFrameworkSizeAuto()
}

const setReferenceImageFromFile = (file) => {
  if (!file) return
  refImageFile.value = file
  refImageUrl.value = ''
  try {
    refPreviewUrl.value = URL.createObjectURL(file)
  } catch (e) {
    refPreviewUrl.value = ''
  }
  updateFrameworkSizeAuto()
}

const compressImageFile = async (file, { maxSide = 1100, targetBytes = 550 * 1024 } = {}) => {
  if (!file) return file
  if (file.size <= targetBytes) return file

  let bitmap = null
  try {
    bitmap = await createImageBitmap(file)
  } catch (e) {
    return file
  }

  const w = bitmap.width || 1
  const h = bitmap.height || 1
  const scale = Math.min(1, maxSide / Math.max(w, h))
  const outW = Math.max(1, Math.round(w * scale))
  const outH = Math.max(1, Math.round(h * scale))

  const canvas = document.createElement('canvas')
  canvas.width = outW
  canvas.height = outH
  const ctx = canvas.getContext('2d')
  if (!ctx) return file
  ctx.drawImage(bitmap, 0, 0, outW, outH)

  const toBlobAsync = (type, quality) =>
    new Promise((resolve) => {
      try {
        canvas.toBlob((b) => resolve(b), type, quality)
      } catch (e) {
        resolve(null)
      }
    })

  let bestBlob = null
  const type = 'image/jpeg'
  const qualities = [0.82, 0.72, 0.62, 0.52]
  for (const q of qualities) {
    const b = await toBlobAsync(type, q)
    if (!b) continue
    bestBlob = b
    if (b.size <= targetBytes) break
  }

  if (!bestBlob) return file
  const name = (file.name || 'reference').replace(/\.(png|jpg|jpeg|webp|bmp|gif)$/i, '') + '.jpg'
  return new File([bestBlob], name, { type })
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

  const purpose = String(imageDialogPurpose.value || 'insert')

  const reader = new FileReader()
  reader.onload = async () => {
    const url = reader.result
    const p = String(purpose || 'insert')
    if (p.startsWith('icon_add:')) {
      const id = p.slice('icon_add:'.length)
      pushIcon(id, url)
      imageDialogVisible.value = false
      return
    }
    if (p.startsWith('icon_replace:')) {
      const rest = p.slice('icon_replace:'.length)
      const parts = rest.split(':')
      const id = parts[0]
      const idx = Number(parts[1])
      if (id && Number.isFinite(idx)) setIconAt(id, idx, url)
      imageDialogVisible.value = false
      return
    }
    await insertImageFromUrl(url)
  }
  reader.readAsDataURL(f)
  try { e.target.value = '' } catch (err) {}
  imageDialogVisible.value = false
}

const onPickRefImage = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return
  ;(async () => {
    let fileToUse = f
    try {
      fileToUse = await compressImageFile(f)
      if (fileToUse && fileToUse.size < f.size) {
        ElMessage.success(`已压缩参考图 ${(f.size / 1024).toFixed(0)}KB → ${(fileToUse.size / 1024).toFixed(0)}KB`)
      }
    } catch (err) {
      fileToUse = f
    }
    setReferenceImageFromFile(fileToUse)
  })()
  try { e.target.value = '' } catch (err) {}
}

const selectKbProductImage = async (src) => {
  if (!src) return
  imageDialogVisible.value = false
  const purpose = String(imageDialogPurpose.value || 'insert')
  if (purpose.startsWith('icon_add:')) {
    const id = purpose.slice('icon_add:'.length)
    pushIcon(id, src)
    return
  }
  if (purpose.startsWith('icon_replace:')) {
    const rest = purpose.slice('icon_replace:'.length)
    const parts = rest.split(':')
    const id = parts[0]
    const idx = Number(parts[1])
    if (id && Number.isFinite(idx)) setIconAt(id, idx, src)
    return
  }
  if (purpose === 'ref') {
    setReferenceImageFromUrl(src)
    return
  }
  if (purpose === 'step2_product') {
    posterStep2ProductFile.value = null
    posterStep2ProductUrl.value = src
    return
  }
  if (purpose === 'step2_background') {
    posterStep2BackgroundFile.value = null
    posterStep2BackgroundUrl.value = src
    return
  }
  await insertImageFromUrl(src)
}

const useActiveImageAsRef = () => {
  const obj = activeObjectRef.value
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片对象')
    return
  }

  const el = obj.getElement?.() || obj._element || obj._originalElement || null
  const src = el?.currentSrc || el?.src || obj?.src || ''
  if (!src) {
    ElMessage.warning('无法获取选中图片的源地址')
    return
  }
  setReferenceImageFromUrl(src)
}

const useActiveImageAsStep2Product = () => {
  const obj = activeObjectRef.value
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片对象')
    return
  }
  const el = obj.getElement?.() || obj._element || obj._originalElement || null
  const src = el?.currentSrc || el?.src || obj?.src || ''
  if (!src) {
    ElMessage.warning('无法获取选中图片的源地址')
    return
  }
  posterStep2ProductFile.value = null
  posterStep2ProductUrl.value = src
}

const useActiveImageAsStep2Background = () => {
  const obj = activeObjectRef.value
  if (!obj || obj.type !== 'image') {
    ElMessage.warning('请先选中一张图片对象')
    return
  }
  const el = obj.getElement?.() || obj._element || obj._originalElement || null
  const src = el?.currentSrc || el?.src || obj?.src || ''
  if (!src) {
    ElMessage.warning('无法获取选中图片的源地址')
    return
  }
  posterStep2BackgroundFile.value = null
  posterStep2BackgroundUrl.value = src
  updateFrameworkSizeAuto()
}

const clearPosterAnalysis = () => {
  posterAnalyzeError.value = ''
  posterAnalysisResult.value = null
  posterAnalysisDebug.value = ''
  posterImageEditError.value = ''
  posterImageEditResultUrl.value = ''
  clearPosterStep2()
}

const clearPosterStep2 = () => {
  posterStep2Error.value = ''
  posterStep2Result.value = null
  posterStep2Debug.value = ''
}

const generatePosterImageEditNow = async () => {
  if (posterImageEditLoading.value) return
  posterImageEditError.value = ''
  if (!posterAnalysisResult.value) {
    posterImageEditError.value = '请先完成参考图分析'
    return
  }
  const refOk = Boolean(refImageFile.value || refImageUrl.value || refPreviewUrl.value)
  if (!refOk) {
    posterImageEditError.value = '请先选择参考图'
    return
  }
  const productOk = Boolean(posterStep2ProductFile.value || posterStep2ProductUrl.value || step2ProductObjectUrl.value)
  if (!productOk) {
    posterImageEditError.value = '请先选择产品图'
    return
  }

  posterImageEditLoading.value = true
  try {
    const sellpoints = Array.isArray(posterFramework.text.sellpoints)
      ? posterFramework.text.sellpoints.map((x) => String(x?.text || '').trim()).filter(Boolean)
      : []

    const resp = await generatePosterImageEdit({
      step1_result: posterAnalysisResult.value,
      product_name: productName.value || undefined,
      bom_code: bomCode.value || undefined,
      reference_file: refImageFile.value || undefined,
      reference_image_url: refImageUrl.value || refPreviewUrl.value || undefined,
      product_file: posterStep2ProductFile.value || undefined,
      product_image_url: posterStep2ProductUrl.value || undefined,
      background_file: posterStep2BackgroundFile.value || undefined,
      background_image_url: posterStep2BackgroundUrl.value || undefined,
      title: String(posterFramework.text.title || '').trim() || undefined,
      subtitle: String(posterFramework.text.subtitle || '').trim() || undefined,
      sellpoints,
      output_width: Number(posterFramework.size.width || posterAnalysisResult.value?.width || 0) || undefined,
      output_height: Number(posterFramework.size.height || posterAnalysisResult.value?.height || 0) || undefined,
      watermark: true,
    })

    if (resp?.ok === false) {
      posterImageEditError.value = resp?.error || '海报生成失败'
      return
    }
    const url = resp?.result?.image_url
    if (!url) {
      posterImageEditError.value = '后端未返回 image_url'
      return
    }
    posterImageEditResultUrl.value = String(url)
    ElMessage.success('海报已生成，可预览并导出到画布')
  } catch (e) {
    posterImageEditError.value = e?.message || String(e)
  } finally {
    posterImageEditLoading.value = false
  }
}

const clearStep2Assets = () => {
  posterStep2ProductFile.value = null
  posterStep2BackgroundFile.value = null
  posterStep2ProductUrl.value = ''
  posterStep2BackgroundUrl.value = ''
  updateFrameworkSizeAuto()
}

const resolveReferenceImagePayload = async () => {
  if (refImageFile.value) {
    return { file: refImageFile.value, image_url: undefined }
  }

  const raw = String(refImageUrl.value || refPreviewUrl.value || '').trim()
  if (!raw) {
    return { file: undefined, image_url: undefined }
  }

  if (raw.startsWith('data:')) {
    return { file: undefined, image_url: raw }
  }

  const tryFetchAsFile = async (url) => {
    const resp = await fetch(url)
    if (!resp.ok) {
      throw new Error(`fetch image failed: ${resp.status}`)
    }
    const blob = await resp.blob()
    const mt = blob?.type || 'image/png'
    const ext = mt.includes('jpeg') ? 'jpg' : (mt.includes('webp') ? 'webp' : 'png')
    return new File([blob], `poster_reference.${ext}`, { type: mt })
  }

  if (raw.startsWith('blob:')) {
    const file = await tryFetchAsFile(raw)
    return { file, image_url: undefined }
  }

  if (/^https?:\/\//i.test(raw)) {
    // Do NOT fetch() external urls here: it will fail on CORS and surface as "Failed to fetch".
    // The backend can consume urls directly.
    try {
      const u = new URL(raw)
      if (u.pathname.startsWith('/api/files/')) {
        return { file: undefined, image_url: u.pathname }
      }
    } catch (e) {}
    return { file: undefined, image_url: raw }
  }

  return { file: undefined, image_url: raw }
}

const triggerStep2ProductUpload = () => {
  try {
    step2ProductInputRef.value?.click?.()
  } catch (e) {}
}

const triggerStep2BackgroundUpload = () => {
  try {
    step2BackgroundInputRef.value?.click?.()
  } catch (e) {}
}

const onPickStep2Product = (e) => {
  const f = e?.target?.files?.[0]
  if (!f) return
  posterStep2ProductFile.value = f
  posterStep2ProductUrl.value = ''
  try {
    e.target.value = ''
  } catch (err) {}
}

const onPickStep2Background = (e) => {
  const f = e?.target?.files?.[0]
  if (!f) return
  posterStep2BackgroundFile.value = f
  posterStep2BackgroundUrl.value = ''
  updateFrameworkSizeAuto()
  try {
    e.target.value = ''
  } catch (err) {}
}

const generatePosterCopyStep2 = async () => {
  if (!posterAnalysisResult.value) {
    posterStep2Error.value = '请先完成参考图分析'
    return
  }

  posterStep2Loading.value = true
  posterStep2Error.value = ''
  try {
    posterStep2Result.value = null
    posterStep2Debug.value = ''

    const basePayload = {
      step1_result: posterAnalysisResult.value,
      requirements: String(posterStep2Requirements.value || '').trim() || undefined,
      product_name: productName.value || undefined,
      bom_code: bomCode.value || undefined,
      bom_type: bomType.value || undefined,
    }

    const resp = await generatePosterCopy({
      ...basePayload,
    })

    if (resp?.ok === false) {
      posterStep2Error.value = resp?.error || 'Step2 生成失败'
      posterStep2Result.value = null
      posterStep2Debug.value = resp?.debug ? JSON.stringify(resp.debug, null, 2) : ''
      return
    }

    const result = resp?.result ?? null
    posterStep2Result.value = result
    posterStep2Debug.value = resp?.debug ? JSON.stringify(resp.debug, null, 2) : ''

    try {
      const copy = result?.copy
      if (copy && typeof copy === 'object') {
        if (typeof copy.title === 'string' && copy.title.trim()) posterFramework.text.title = copy.title.trim()
        if (typeof copy.subtitle === 'string' && copy.subtitle.trim()) posterFramework.text.subtitle = copy.subtitle.trim()
        if (Array.isArray(copy.sellpoints)) {
          const sp = copy.sellpoints.map((s) => String(s || '').trim()).filter(Boolean)
          const step1 = posterAnalysisResult.value
          const els = Array.isArray(step1?.elements) ? step1.elements : []
          const expected = els.filter((e) => /^sellpoint_\d+$/.test(String(e?.id || ''))).length
          const finalSp = expected > 0 ? sp.slice(0, expected) : []
          posterFramework.text.sellpoints.splice(0, posterFramework.text.sellpoints.length)
          finalSp.forEach((t) => posterFramework.text.sellpoints.push(newFrameworkSellpoint(t)))
        }
      }
    } catch (e) {}
  } catch (e) {
    posterStep2Error.value = e?.message || String(e)
  } finally {
    posterStep2Loading.value = false
  }
}

const analyzeReferenceImage = async () => {
  if (!refImageFile.value && !refImageUrl.value) {
    posterAnalyzeError.value = '请先选择参考图'
    return
  }

  posterAnalyzeLoading.value = true
  posterAnalyzeError.value = ''
  try {
    posterAnalysisResult.value = null
    posterAnalysisDebug.value = ''
    const resolved = await resolveReferenceImagePayload()
    if (!resolved?.file && !resolved?.image_url) {
      posterAnalyzeError.value = '请先选择参考图'
      return
    }

    const resp = await analyzePosterReference({
      file: resolved.file || undefined,
      image_url: resolved.image_url || undefined,
    })
    if (resp?.ok === false) {
      posterAnalyzeError.value = resp?.error || 'JSON 解析失败，已展示原始返回'
      posterAnalysisResult.value = null
      posterAnalysisDebug.value = resp?.debug ? JSON.stringify(resp.debug, null, 2) : ''
      return
    }

    const result = resp?.result ?? null
    posterAnalysisResult.value = result
    posterAnalysisDebug.value = resp?.debug ? JSON.stringify(resp.debug, null, 2) : ''

    try {
      fillFrameworkFromStep1(result)
    } catch (e) {}
  } catch (e) {
    posterAnalyzeError.value = e?.message || String(e)
  } finally {
    posterAnalyzeLoading.value = false
  }
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
  return canvas.toJSON()
}

const saveDraft = () => {
  const canvasJson = serializeCanvas()
  if (!canvasJson) return
  try {
    const frameworkSnapshot = JSON.parse(JSON.stringify(posterFramework))
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ canvas: canvasJson, framework: frameworkSnapshot }))
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
    const parsed = JSON.parse(raw)
    const canvasJson = parsed && typeof parsed === 'object' && parsed.canvas ? parsed.canvas : parsed
    await canvas.loadFromJSON(canvasJson)
    canvas.requestRenderAll()

    try {
      const fw = parsed && typeof parsed === 'object' && parsed.framework ? parsed.framework : null
      if (fw && typeof fw === 'object') {
        if (fw.size && typeof fw.size === 'object') {
          const w = Number(fw.size.width || 0)
          const h = Number(fw.size.height || 0)
          if (Number.isFinite(w) && w > 0) posterFramework.size.width = w
          if (Number.isFinite(h) && h > 0) posterFramework.size.height = h
        }
        if (fw.text && typeof fw.text === 'object') {
          if (typeof fw.text.title === 'string') posterFramework.text.title = fw.text.title
          if (typeof fw.text.subtitle === 'string') posterFramework.text.subtitle = fw.text.subtitle
          if (Array.isArray(fw.text.sellpoints)) {
            posterFramework.text.sellpoints.splice(0, posterFramework.text.sellpoints.length)
            fw.text.sellpoints.forEach((sp) => posterFramework.text.sellpoints.push(newFrameworkSellpoint(String(sp?.text || ''))))
          }
        }
        if (fw.icons && typeof fw.icons === 'object') {
          posterFramework.icons = fw.icons
        }
      }
    } catch (e) {}
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

const cloneTextboxFallback = (obj) => {
  if (!obj || String(obj.type || '') !== 'textbox') return null
  const text = typeof obj.text === 'string' ? obj.text : ''
  const cloned = new FabricTextbox(text, {
    left: Number(obj.left ?? 0),
    top: Number(obj.top ?? 0),
    width: Number(obj.width ?? 1) || 1,
    height: Number(obj.height ?? 1) || 1,
    fontFamily: obj.fontFamily,
    fontSize: obj.fontSize,
    fontWeight: obj.fontWeight,
    fontStyle: obj.fontStyle,
    fill: obj.fill,
    stroke: obj.stroke,
    strokeWidth: obj.strokeWidth,
    textAlign: obj.textAlign,
    lineHeight: obj.lineHeight,
    charSpacing: obj.charSpacing,
    backgroundColor: obj.backgroundColor,
    opacity: obj.opacity,
    angle: obj.angle,
    scaleX: obj.scaleX,
    scaleY: obj.scaleY,
    flipX: obj.flipX,
    flipY: obj.flipY,
    skewX: obj.skewX,
    skewY: obj.skewY,
    shadow: obj.shadow,
  })
  try {
    cloned.data = obj.data ? JSON.parse(JSON.stringify(obj.data)) : undefined
  } catch (e) {
    cloned.data = obj.data
  }
  try {
    if (typeof cloned.setCoords === 'function') cloned.setCoords()
  } catch (e) {}
  return cloned
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
      } else if (obj.type === 'textbox') {
        cloned = cloneTextboxFallback(obj)
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
    try { ElMessage.success('已复制') } catch (e) {}
  } catch (e) {
    ElMessage.error(`复制失败${e?.message ? `：${e.message}` : ''}`)
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

  if (e.key === 'Shift') {
    isShiftDown.value = true
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
  if (isMod && (e.key === 'z' || e.key === 'Z')) {
    e.preventDefault()
    if (e.shiftKey) {
      redoCanvas()
    } else {
      undoCanvas()
    }
    return
  }
  if (isMod && (e.key === 'y' || e.key === 'Y')) {
    e.preventDefault()
    redoCanvas()
    return
  }
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
  if (e.key === 'Shift') {
    isShiftDown.value = false
    clearSnapGuides()
  }
  if (e.code === 'Space') {
    isSpaceDown.value = false
  }
}

const rotateActive = () => {
  const canvas = canvasInstance.value
  if (!canvas) return
  const obj = canvas.getActiveObject()
  if (!obj || (obj.type !== 'image' && obj.type !== 'textbox')) {
    ElMessage.warning('请先选中一个对象')
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
      } else if (obj.type === 'textbox') {
        cloned = cloneTextboxFallback(obj)
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
    ElMessage.error(`复制失败${e?.message ? `：${e.message}` : ''}`)
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
      try {
        next = await cloneObject(clipboard.value)
      } catch (err) {
        if (clipboard.value?.type === 'textbox') {
          next = cloneTextboxFallback(clipboard.value)
        } else {
          throw err
        }
      }
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
    ElMessage.error(`粘贴失败${e?.message ? `：${e.message}` : ''}`)
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

.resize-handle[data-key='ml'],
.resize-handle[data-key='mr'] {
  cursor: ew-resize;
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

.top-right-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-toggle-btn {
  width: 38px;
  height: 38px;
  min-width: 38px;
  padding: 0;
  border-radius: 50%;
}

.panel-toggle-btn :deep(.el-icon) {
  font-size: 18px;
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

.right-panel {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: clamp(440px, 48vw, 760px);
  z-index: 31;
  background: rgba(255, 255, 255, 0.96);
  border-left: 1px solid rgba(229, 231, 235, 0.9);
  box-shadow: -10px 0 24px rgba(17, 24, 39, 0.08);
  transform: translateX(100%);
  transition: transform 0.18s ease-out;
  display: flex;
  flex-direction: column;
  pointer-events: auto;
}

.right-panel.open {
  transform: translateX(0%);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px;
  border-bottom: 1px solid rgba(229, 231, 235, 0.9);
}

.panel-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}

.layers-list {
  display: grid;
  gap: 8px;
}

.gen-section {
  display: grid;
  gap: 10px;
}

.gen-layout {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(360px, 1.25fr);
  gap: 12px;
}

@media (max-width: 1180px) {
  .gen-layout {
    grid-template-columns: 1fr;
  }
}

.gen-col-full {
  grid-column: 1 / -1;
}

.gen-col {
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.06);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.gen-col-title {
  font-weight: 700;
  color: rgba(15, 23, 42, 0.92);
  font-size: 13px;
}

.gen-size-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.gen-size-item {
  display: grid;
  grid-template-columns: 20px 1fr;
  align-items: center;
  gap: 8px;
}

.gen-size-label {
  font-size: 12px;
  font-weight: 700;
  color: rgba(15, 23, 42, 0.8);
}

.gen-sellpoints {
  display: grid;
  gap: 8px;
}

.gen-sellpoint-item {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px;
}

.gen-sellpoint-main {
  display: grid;
  gap: 6px;
}

.gen-text-with-icons {
  display: grid;
  gap: 6px;
}

.gen-icon-editor {
  border: 1px dashed rgba(148, 163, 184, 0.65);
  border-radius: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.6);
}

.gen-icon-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.gen-icon-list {
  display: grid;
  gap: 8px;
}

.gen-icon-item {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 10px;
  align-items: center;
}

.gen-icon-item img {
  display: block;
  width: 44px !important;
  height: 44px !important;
  max-width: 44px !important;
  max-height: 44px !important;
  border-radius: 10px;
  object-fit: contain;
  background: rgba(15, 23, 42, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.6);
}

.gen-icon-item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.gen-preview-canvas {
  position: relative;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.03);
}

.gen-preview-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: 50% 50%;
}

.gen-preview-box-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.gen-preview-box {
  position: absolute;
  border: 2px solid rgba(239, 68, 68, 0.95);
  box-sizing: border-box;
}

.gen-preview-product {
  position: absolute;
  object-fit: contain;
  object-position: 50% 100%;
  border-radius: 10px;
}

.gen-preview-text {
  position: absolute;
  padding: 2px 3px;
  color: rgba(255, 255, 255, 0.95);
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.55);
  line-height: 1.12;
  overflow: visible;
  word-break: break-word;
  white-space: pre-wrap;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.gen-preview-text-inner {
  position: relative;
  width: 100%;
  height: 100%;
}

.gen-preview-icons {
  position: absolute;
  display: inline-flex;
  align-items: center;
}

.gen-preview-icon {
  object-fit: contain;
  border-radius: 6px;
}

.gen-preview-text-content {
  position: relative;
}

.gen-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.gen-label {
  font-size: 13px;
  color: rgba(15, 23, 42, 0.9);
  font-weight: 600;
}

.gen-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.gen-actions-compact {
  gap: 6px;
}

.gen-assets-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

@media (max-width: 1180px) {
  .gen-assets-row {
    grid-template-columns: 1fr;
  }
}

.gen-asset-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.layer-item {
  position: relative;
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 10px;
  padding: 10px 10px;
  background: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  display: grid;
  gap: 4px;
}

.layer-item:hover {
  background: rgba(243, 244, 246, 0.9);
}

.layer-item.active {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.layer-name {
  font-weight: 700;
  color: rgba(17, 24, 39, 0.92);
  font-size: 13px;
}

.layer-meta {
  font-size: 12px;
  color: rgba(17, 24, 39, 0.6);
  font-variant-numeric: tabular-nums;
}

.layer-actions {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 6px;
}

.layer-btn {
  appearance: none;
  border: 1px solid rgba(148, 163, 184, 0.30);
  background: rgba(15, 23, 42, 0.14);
  color: rgba(15, 23, 42, 0.78);
  border-radius: 8px;
  padding: 4px 7px;
  font-size: 12px;
  cursor: pointer;
}

.layer-btn:hover {
  background: rgba(15, 23, 42, 0.20);
}

.layer-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.gen-preview {
  margin: 8px 0 12px;
}

.gen-preview-wrap {
  position: relative;
  width: 100%;
}

.gen-preview-wrap img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 6px;
}

.gen-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.gen-box {
  position: absolute;
  border: 2px solid rgba(64, 158, 255, 0.95);
  box-sizing: border-box;
}

.gen-box-label {
  position: absolute;
  top: -18px;
  left: 0;
  font-size: 12px;
  line-height: 16px;
  color: #fff;
  background: rgba(64, 158, 255, 0.95);
  padding: 1px 6px;
  border-radius: 4px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gen-preview {
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.9);
}

.gen-preview img {
  width: 100%;
  height: auto;
  border-radius: 8px;
  display: block;
}

.gen-error {
  color: #b42318;
  font-size: 12px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}

.gen-asset-preview {
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  padding: 8px;
  overflow: hidden;
}

.gen-asset-preview--small {
  padding: 6px;
}

.gen-asset-preview img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 8px;
}

.gen-asset-preview--small img {
  max-height: 120px;
  object-fit: cover;
}

.layer-item {
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 10px;
  padding: 10px 10px;
  background: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  display: grid;
  gap: 4px;
}

.layer-item:hover {
  background: rgba(243, 244, 246, 0.9);
}

.layer-item.active {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.layer-name {
  font-weight: 700;
  color: rgba(17, 24, 39, 0.92);
  font-size: 13px;
}

.layer-meta {
  font-size: 12px;
  color: rgba(17, 24, 39, 0.6);
  font-variant-numeric: tabular-nums;
}

.props-form {
  display: grid;
  gap: 10px;
}

.pf-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  align-items: center;
  gap: 10px;
}

.pf-label {
  color: rgba(17, 24, 39, 0.7);
  font-size: 13px;
  font-weight: 600;
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

.obj-toolbar .tool-select {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  pointer-events: auto;
}

.obj-toolbar .tool-number {
  width: 64px;
  padding: 6px 8px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  pointer-events: auto;
}

.obj-toolbar .tool-color {
  width: 34px;
  height: 30px;
  padding: 0;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.35);
  pointer-events: auto;
}

.obj-toolbar .tool-el-select {
  pointer-events: auto;
}

.obj-toolbar .tool-el-select .el-select__wrapper {
  min-height: 30px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.35);
  box-shadow: none;
  color: rgba(255, 255, 255, 0.92);
}

.obj-toolbar .tool-el-select .el-select__selected-item,
.obj-toolbar .tool-el-select .el-select__input {
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
}

:global(.obj-toolbar-popper) {
  --el-bg-color-overlay: rgba(15, 23, 42, 0.98);
  --el-text-color-regular: rgba(255, 255, 255, 0.96);
  --el-fill-color-light: rgba(255, 255, 255, 0.10);
  --el-border-color-light: rgba(255, 255, 255, 0.18);
}

:global(.obj-toolbar-popper .el-select-dropdown) {
  background: rgba(15, 23, 42, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

:global(.obj-toolbar-popper .el-select-dropdown__item) {
  height: auto;
  padding: 12px 12px;
  line-height: 1.2;
  color: rgba(255, 255, 255, 0.96);
}

:global(.obj-toolbar-popper .el-select-dropdown__item:hover) {
  background: rgba(255, 255, 255, 0.10);
}

:global(.obj-toolbar-popper .el-select-dropdown__item.is-selected) {
  color: rgba(96, 165, 250, 0.98);
}

.font-opt {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.font-opt-name {
  font-size: 12px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
}

.font-opt-sample {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.82);
}

.obj-toolbar .tool[data-active='1'] {
  background: rgba(255, 255, 255, 0.12);
}

.obj-toolbar .tool-sep {
  display: inline-block;
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.14);
  margin: 0 6px;
  border-radius: 1px;
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
