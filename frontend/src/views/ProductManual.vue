<template>
  <div class="page">
    <div class="topbar">
      <el-button class="back-btn" link @click="goBack">
        ← 返回
      </el-button>
      <div class="tabs">
        <div class="toolbar-like">
          <el-button round :type="tab === 'promo' ? 'primary' : ''" :plain="tab !== 'promo'" :icon="Promotion" @click="tab = 'promo'">规格页</el-button>
          <el-button round :type="tab === 'poster' ? 'primary' : ''" :plain="tab !== 'poster'" :icon="Picture" @click="tab = 'poster'">海报</el-button>
          <el-button round :type="tab === 'manual' ? 'primary' : ''" :plain="tab !== 'manual'" :icon="Document" @click="tab = 'manual'">说明书</el-button>
        </div>
      </div>
    </div>

    <div class="content">
      <div class="product-header">
        <div class="meta">
          <div class="name">产品：{{ productName || name }}</div>
          <div class="sub" v-if="name && productName && name !== productName">展示名称：{{ name }}</div>
          <div class="bom-row">
            <div class="bom-value">
              <span class="bom-label">当前 BOM：</span>
              <template v-if="bomLoading">
                <span class="bom-placeholder">正在加载…</span>
              </template>
              <span v-else-if="bomCode" class="bom-code">{{ bomCode }}</span>
              <span v-else class="bom-placeholder">会话未提供 BOM</span>
            </div>
            <div class="bom-actions">
              <el-button
                v-if="manualSessionId"
                size="small"
                type="primary"
                plain
                :loading="bomLoading"
                @click="loadSessionBom"
              >
                刷新 BOM
              </el-button>
              <el-button
                v-if="bomDetails"
                class="bom-detail-btn"
                size="small"
                type="info"
                text
                @click="openBomDetailDialog"
              >
                查看配置
              </el-button>
              <el-tag v-if="bomError" size="small" type="danger" effect="plain" class="bom-error-tip">
                {{ bomError }}
              </el-tag>
            </div>
            <el-button
              size="small"
              type="success"
              plain
              class="insert-neo4j-btn"
              :loading="insertingProduct"
              @click="handleInsertProduct"
            >
              将产品插入至数据库
            </el-button>
          </div>
        </div>
      </div>

      <el-dialog
        v-model="specsheetResultDialogVisible"
        title="规格页 API 返回"
        width="600px"
        @close="specsheetResultDialogVisible = false"
      >
        <div class="specsheet-result-dialog__content">
          <p class="dialog-tip">后端已返回下述 JSON（包含 LLM 默认兜底时的内容），便于排查。</p>
          <el-input
            type="textarea"
            :value="specsheetResultPayload"
            :rows="14"
            readonly
          />
        </div>
      </el-dialog>

      <el-dialog
        v-model="manualBookResultDialogVisible"
        title="说明书 API 返回"
        width="600px"
        @close="manualBookResultDialogVisible = false"
      >
        <div class="specsheet-result-dialog__content">
          <p class="dialog-tip">后端返回的说明书 JSON 及提示词，便于排查。</p>
          <el-input
            type="textarea"
            :value="manualBookResultPayload"
            :rows="14"
            readonly
          />
        </div>
      </el-dialog>

      <el-dialog
        v-model="bomDetailDialogVisible"
        title="BOM 配置明细"
        width="520px"
      >
        <el-empty v-if="!bomDetails?.segments?.length" description="暂无 BOM 配置数据" />
        <div v-else class="bom-detail-list">
          <div
            v-for="segment in bomDetails.segments"
            :key="segment.key"
            class="bom-detail-item"
          >
            <div class="detail-label">{{ segment.label }}</div>
            <div class="detail-value">
              <span class="code">{{ segment.value }}</span>
              <span v-if="segment.meaning" class="meaning">{{ segment.meaning }}</span>
              <span v-if="segment.reason" class="reason">{{ segment.reason }}</span>
            </div>
          </div>
        </div>
      </el-dialog>
      <div v-if="tab === 'promo'" class="panel">
        <div class="title row promo-header-row">
          <div class="promo-header-left">
            <div>规格页</div>
            <div class="promo-theme-switcher">
              <span class="theme-label">配色:</span>

              <span class="theme-presets">
                <el-button
                  size="small"
                  :type="promoMainColor === '#2c6ea4' && promoBgColor === '#ffffff' && promoTextColor === '#111827' ? 'primary' : 'default'"
                  @click="applyPromoPreset('default')"
                >默认</el-button>
                <el-button
                  size="small"
                  :type="promoMainColor === '#c25a1a' && promoBgColor === '#f5f7fa' && promoTextColor === '#5b4632' ? 'primary' : 'default'"
                  @click="applyPromoPreset('warm')"
                >暖色</el-button>
                <el-button
                  size="small"
                  :type="promoMainColor === '#93c5fd' && promoBgColor === '#111827' && promoTextColor === '#e5e7eb' ? 'primary' : 'default'"
                  @click="applyPromoPreset('dark')"
                >深色</el-button>
              </span>
                            <span class="theme-picker-group">
                <span class="theme-picker-label">主色</span>
                <el-color-picker
                  v-model="promoMainColor"
                  size="small"
                  :predefine="promoPredefineMainColors"
                />
                <span class="theme-picker-label">背景</span>
                <el-color-picker
                  v-model="promoBgColor"
                  size="small"
                  :predefine="promoPredefineBgColors"
                />
                <span class="theme-picker-label">文本</span>
                <el-color-picker
                  v-model="promoTextColor"
                  size="small"
                  :predefine="promoPredefineTextColors"
                />
              </span>
            </div>
          </div>
          <div class="row gap12">
            <el-button size="small" @click="resetPromo">重置内容</el-button>
            <el-button size="small" type="primary" @click="exportPromo">导出为图片</el-button>
            <el-button size="small" type="warning" @click="exportPromoPdfEditable">导出为PDF</el-button>
            <el-button size="small" type="info" @click="saveSpecsheetToDb">保存修改至数据库</el-button>
            <el-button size="small" type="info" plain @click="openRagChunksDialog">查看 RAG 来源</el-button>
            <!-- <el-button
              v-if="manualSessionId"
              size="small"
              type="success"
              plain
              :loading="runningSpecsheetAce"
              @click="handleRunSpecsheetAce"
            >
              规格页 ACE
            </el-button> -->
            <el-button size="small" type="primary" plain @click="handleGenerateSpecsheet" :loading="loadingSpecsheet">生成规格页</el-button>
          </div>
        </div>
        <!-- 加载进度显示 -->
        <div v-if="loadingSpecsheet" class="specsheet-loading">
          <el-progress
            :percentage="specsheetProgress"
            :status="specsheetProgressStatus"
            :stroke-width="8"
          />
          <div class="loading-text">{{ specsheetLoadingText }}</div>
        </div>
        <div v-else-if="specsheetError" class="specsheet-error">
          <el-alert
            :title="specsheetError"
            type="error"
            :closable="false"
            show-icon
          />
        </div>
        <div class="promo-wrap" v-loading="loadingSpecsheet" element-loading-text="正在从后端加载规格页内容...">
          <div
            class="promo-canvas"
            ref="promoRef"
            :style="{
              '--promo-main-color': promoMainColor,
              '--promo-bg-color': promoBgColor,
              '--promo-text-color': promoTextColor
            }"
          >
            <!-- 顶部灰色横幅与左上角 Logo 卡片 -->
            <div class="promo-top" :style="{ backgroundImage: `url(${backgroundSrc})` }">
              <!-- 仅负责背景图片更换的悬浮提示与点击层，不包含 Logo 区域 -->
              <el-tooltip :content="BACKGROUND_UPLOAD_TIPS" placement="top">
                <div class="promo-top-bg-layer" @click="onClickBackground"></div>
              </el-tooltip>
              <el-tooltip :content="LOGO_UPLOAD_TIPS" placement="bottom">
                <div class="logo-card" @click.stop="onClickLogo">
                  <div class="logo-mark">
                    <img :src="logoSrc" alt="" width="45" height="45" />
                  </div>
                </div>
              </el-tooltip>
            </div>

            <!-- 产品图片（叠加在顶部与正文之间） -->
            <el-tooltip :content="PRODUCT_UPLOAD_TIPS" placement="top">
              <div
                class="product-photo-wrap"
                :style="{ '--product-x': productAnchor.x, '--product-y': productAnchor.y }"
                @mousedown="onProductPhotoMouseDown"
              >
                <img
                  class="product-photo"
                  :src="productPhotoSrc"
                  alt="product"
                  @click="onProductPhotoClick"
                  :style="{ transform: `scale(${productPhotoScale}) rotate(${productPhotoRotate}deg)` }"
                />
                <div class="product-photo-tools" @mousedown.stop @click.stop>
                  <el-button
                    class="photo-tool-btn"
                    size="small"
                    text
                    @click.stop="decProductPhotoScale"
                  >
                    -
                  </el-button>
                  <el-button
                    class="photo-tool-btn"
                    size="small"
                    text
                    @click.stop="incProductPhotoScale"
                  >
                    +
                  </el-button>
                  <el-button
                    class="photo-tool-btn"
                    size="small"
                    text
                    @click.stop="rotateProductPhoto(-5)"
                  >
                    ⟲
                  </el-button>
                  <el-button
                    class="photo-tool-btn"
                    size="small"
                    text
                    @click.stop="rotateProductPhoto(5)"
                  >
                    ⟳
                  </el-button>
                  <el-button
                    class="photo-tool-btn"
                    size="small"
                    text
                    @click.stop="resetProductPhotoTransform"
                  >
                    Reset
                  </el-button>
                </div>
              </div>
            </el-tooltip>

            <!-- 内容区域 -->
            <div class="promo-body">
              <!-- 左列 -->
              <div class="col">
                <div class="product-title" contenteditable="true" data-placeholder="Vastera" @input="onEditTextWithCaret($event, 'productTitle')" v-text="promoData.productTitle"></div>
                <div class="section">
                  <div class="h2" data-placeholder="Feature">Feature</div>
                  <div class="icons">
                    <div class="icon">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.capacity" alt="Capacity" width="35" height="35" @click="openFeatureIconDialog('capacity')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Capacity</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="1" @input="onEditTextWithCaret($event, 'features.capacity')" v-text="promoData.features.capacity"></div>
                      </div>
                    </div>


                    <div class="icon">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.jets" alt="Jets" width="35" height="35" @click="openFeatureIconDialog('jets')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Jets</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="0" @input="onEditTextWithCaret($event, 'features.jets')" v-text="promoData.features.jets"></div>
                      </div>
                    </div>

                    <div class="icon">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.pumps" alt="Pumps" width="35" height="35" @click="openFeatureIconDialog('pumps')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Pumps</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="2" @input="onEditTextWithCaret($event, 'features.pumps')" v-text="promoData.features.pumps"></div>
                      </div>
                    </div>
                    
                  </div>
                  <div class="measurements-row">
                    <div class="m-icon">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.measurements" alt="Measurements" width="32" height="32" @click="openFeatureIconDialog('measurements')" />
                      </el-tooltip>
                    </div>
                    <div class="m-text">
                      <div class="m-label">Measurements</div>
                      <div class="m-value" contenteditable="true" data-placeholder="70&quot; × 33&quot; × 37&quot;" @input="onEditTextWithCaret($event, 'measurements')" v-text="promoData.measurements"></div>
                    </div>
                  </div>
                </div>

                <div class="section" v-if="promoSectionTitles.premium">
                  <div
                    class="h2"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'premium')"
                    v-html="promoSectionTitles.premium"
                  ></div>
                  <ul class="bullets">
                    <li v-for="(it, idx) in promoData.premiumFeatures" :key="'s0-'+idx">
                      <span contenteditable="true" @input="onEditTextWithCaret($event, `premiumFeatures.${idx}`)" @keydown="onListItemKeydown($event, 'premiumFeatures', idx)" v-text="it"></span>
                    </li>
                  </ul>
                </div>

                <div class="section" v-if="promoSectionTitles.insulation">
                  <div
                    class="h2"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'insulation')"
                    v-html="promoSectionTitles.insulation"
                  ></div>
                  <ul class="bullets">
                    <li v-for="(it, idx) in promoData.insulationFeatures" :key="'s1-'+idx">
                      <span contenteditable="true" @input="onEditTextWithCaret($event, `insulationFeatures.${idx}`)" @keydown="onListItemKeydown($event, 'insulationFeatures', idx)" v-text="it"></span>
                    </li>
                  </ul>
                </div>

                <div class="section" v-if="promoSectionTitles.extra">
                  <div
                    class="h2"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'extra')"
                    v-html="promoSectionTitles.extra"
                  ></div>
                  <ul class="bullets">
                    <li v-for="(it, idx) in promoData.extraFeatures" :key="'s2-'+idx">
                      <span contenteditable="true" @input="onEditTextWithCaret($event, `extraFeatures.${idx}`)" @keydown="onListItemKeydown($event, 'extraFeatures', idx)" v-text="it"></span>
                    </li>
                  </ul>
                </div>
              </div>

              <!-- 右列 -->
              <div class="col right-col">
                <div class="section" v-if="promoSectionTitles.specifications">
                  <div
                    class="h2"
                    data-placeholder="Specifications"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'specifications')"
                    v-html="promoSectionTitles.specifications"
                  ></div>
                  <ul class="specs-list">
                    <li
                      v-for="(specObj, idx) in promoData.Specifications"
                      :key="'spec-'+idx"
                      class="specs-item"
                      :class="{ clickable: idx === 0 || idx === 1 }"
                      @click="(idx === 0 || idx === 1) && openSpecColorDialog(idx)"
                    >
                      <span class="specs-label">{{ Object.keys(specObj)[0] }}</span>
                      <span class="specs-value" :class="{ 'bold': idx >= 2 }">
                        <!-- 如果是颜色字段（Cabinet Color 或 Shell Color），显示颜色点 -->
                        <template v-if="idx === 0 || idx === 1">
                          <span
                            v-for="(c, i) in parseColorList(Object.values(specObj)[0])"
                            :key="'c'+idx+'-'+i"
                            class="specs-dot"
                            :style="{ background: c }"
                          ></span>
                        </template>
                        <!-- 其他字段显示文本 -->
                        <template v-else>
                          <span contenteditable="true" data-placeholder="" @input="onEditSpecification($event, idx)" v-text="Object.values(specObj)[0]"></span>
                        </template>
                      </span>
                    </li>
                  </ul>
                </div>

                <div class="section" v-if="promoSectionTitles.smartWater">
                  <div
                    class="h2"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'smartWater')"
                    v-html="promoSectionTitles.smartWater"
                  ></div>
                  <ul class="bullets bullets-gray">
                    <li v-for="(it, idx) in promoData.smartWater" :key="'sw-'+idx">
                      <span contenteditable="true" @input="onEditTextWithCaret($event, `smartWater.${idx}`)" @keydown="onListItemKeydown($event, 'smartWater', idx)" v-text="it"></span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- 页脚 -->
            <div class="promo-footer">
              <div class="footnote">* Specifications are subject to change.</div>
            </div>
          </div>
          <!-- 隐藏文件输入：产品与背景图更换 -->
          <input ref="productInputRef" type="file" accept="image/*" style="display:none" @change="onPickProduct" />
          <input ref="backgroundInputRef" type="file" accept="image/*" style="display:none" @change="onPickBackground" />
          <!-- 隐藏文件输入：Feature 区图标更换 -->
          <input ref="featureIconInputRef" type="file" accept="image/*" style="display:none" @change="onPickFeatureIcon" />
          <!-- 隐藏文件输入：Logo 图标更换 -->
          <input ref="logoInputRef" type="file" accept="image/*" style="display:none" @change="onPickLogo" />

          <!-- 产品图片选择弹框 -->
          <el-dialog
            v-model="productDialogVisible"
            title="更换产品图片"
            width="520px"
          >
            <div class="product-dialog">
              <el-tabs v-model="productDialogTab">
                <el-tab-pane label="本地上传" name="local">
                  <div class="product-dialog-section">
                    <p>从本地选择一张图片作为产品图。</p>
                    <el-button type="primary" @click="triggerLocalProductUpload">选择本地图片</el-button>
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

          <el-dialog
            v-model="specColorDialogVisible"
            :title="specColorDialogTitle"
            width="520px"
          >
            <div class="spec-color-dialog">
              <div class="row">
                <div class="label">启用双色</div>
                <el-switch v-model="specColorDual" />
              </div>
              <div class="row">
                <div class="label">颜色 1</div>
                <el-color-picker v-model="specColor1" show-alpha="false" @click="specColorActive = 1" />
              </div>
              <div class="row" v-if="specColorDual">
                <div class="label">颜色 2</div>
                <el-color-picker v-model="specColor2" show-alpha="false" @click="specColorActive = 2" />
              </div>
              <div class="presets">
                <div class="label">预设</div>
                <div class="preset-grid">
                  <button
                    v-for="c in specColorPresets"
                    :key="'preset-'+c"
                    class="preset"
                    type="button"
                    :style="{ background: c }"
                    @click.stop="applyPresetColor(c)"
                  ></button>
                </div>
              </div>
            </div>
            <template #footer>
              <el-button @click="specColorDialogVisible = false">取消</el-button>
              <el-button type="primary" @click="saveSpecColor">保存</el-button>
            </template>
          </el-dialog>
          <!-- Feature 图标选择弹框：本地上传 + 图标库 -->
          <el-dialog
            v-model="featureIconDialogVisible"
            title="更换 Feature 图标"
            width="520px"
          >
            <div class="product-dialog">
              <el-tabs v-model="featureIconDialogTab">
                <el-tab-pane label="本地上传" name="local">
                  <div class="product-dialog-section">
                    <p>从本地选择一张图片作为该 Feature 的图标。</p>
                    <el-button type="primary" @click="triggerLocalFeatureIconUpload">选择本地图标</el-button>
                  </div>
                </el-tab-pane>
                <el-tab-pane label="图标库" name="kb">
                  <div class="product-dialog-section">
                    <p>从图标库中选择一个图标：</p>
                    <div class="kb-image-grid">
                      <div
                        v-for="icon in kbFeatureIcons"
                        :key="icon.src + '-' + icon.key"
                        class="kb-image-item"
                        @click="selectKbFeatureIcon(icon.src)"
                      >
                        <img :src="icon.src" :alt="icon.label" />
                        <div class="kb-image-label">{{ icon.label }}</div>
                      </div>
                    </div>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </div>
          </el-dialog>
          <!-- RAG 调试：查看用于生成规格页的来源文件 -->
          <el-dialog
            v-model="ragDialogVisible"
            title="查看RAG 来源"
            width="960px"
          >
            <div v-if="ragLoading" class="rag-chunks-loading">正在从后端加载 RAG 上下文...</div>
            <div v-else-if="ragError" class="rag-chunks-error">{{ ragError }}</div>
            <div v-else class="rag-dialog-body">
              <div v-if="hasTransferredDocs" class="rag-docs">
                <section v-if="productDocsFromRoute.length" class="rag-doc-section">
                  <div class="rag-doc-header">
                    <div>
                      <div class="rag-doc-title">产品相关文件</div>
                      <div class="rag-doc-sub">来自 BOM 详情页的 {{ productDocsFromRoute.length }} 个文件</div>
                    </div>
                  </div>
                  <div class="rag-doc-list">
                    <el-card
                      v-for="doc in productDocsFromRoute"
                      :key="doc.key"
                      class="rag-doc-card"
                      shadow="hover"
                    >
                      <div class="rag-doc-name">
                        {{ doc.name }}
                        <el-tag v-if="doc.type && doc.type !== 'document'" size="small" effect="plain">
                          {{ formatDocType(doc.type) }}
                        </el-tag>
                      </div>
                      <div v-if="doc.summary" class="rag-doc-summary">{{ doc.summary }}</div>
                      <div class="rag-doc-path">{{ doc.path || '未提供路径' }}</div>
                    </el-card>
                  </div>
                </section>

                <section
                  v-for="group in accessoryDocGroupsFromRoute"
                  :key="group.key"
                  class="rag-doc-section"
                >
                  <div class="rag-doc-header">
                    <div>
                      <div class="rag-doc-title">配件相关文件 · {{ group.accessory }}</div>
                      <div class="rag-doc-sub">共 {{ group.documents.length }} 个文件</div>
                    </div>
                  </div>
                  <div class="rag-doc-list">
                    <el-card
                      v-for="doc in group.documents"
                      :key="doc.key"
                      class="rag-doc-card"
                      shadow="hover"
                    >
                      <div class="rag-doc-name">
                        {{ doc.name }}
                        <el-tag v-if="doc.type && doc.type !== 'document'" size="small" effect="plain">
                          {{ formatDocType(doc.type) }}
                        </el-tag>
                      </div>
                      <div v-if="doc.summary" class="rag-doc-summary">{{ doc.summary }}</div>
                      <div class="rag-doc-path">{{ doc.path || '未提供路径' }}</div>
                    </el-card>
                  </div>
                </section>
              </div>
              <div v-else class="rag-empty">
                暂无可展示的生成来源，请在 BOM 详情页选择“生成产品手册”并重试。
              </div>

              <section v-if="manualSessionId" class="rag-doc-section rag-ocr">
                <div class="rag-doc-header">
                  <div>
                    <div class="rag-doc-title">手动 OCR 结果</div>
                    <div class="rag-doc-sub">会话 ID：{{ manualSessionId }}</div>
                  </div>
                  <el-tag v-if="manualOcrLoaded" type="success" effect="plain">
                    {{ countGroupArtifacts(manualOcrProductGroups) + countGroupArtifacts(manualOcrAccessoryGroups) }} 个文件
                  </el-tag>
                </div>

                <div v-if="manualOcrLoading" class="rag-chunks-loading">正在加载手动 OCR 结果...</div>
                <div v-else-if="manualOcrError" class="rag-chunks-error">{{ manualOcrError }}</div>
                <div v-else>
                  <template v-if="manualOcrLoaded">
                    <section v-if="manualOcrProductGroups.length" class="rag-doc-subsection">
                      <div class="rag-doc-header">
                        <div>
                          <div class="rag-doc-title">产品 OCR 文件</div>
                          <div class="rag-doc-sub">共 {{ manualOcrProductGroups.length }} 个文件组，{{ countGroupArtifacts(manualOcrProductGroups) }} 个产出</div>
                        </div>
                      </div>
                      <div class="rag-doc-list">
                        <el-card
                          v-for="group in manualOcrProductGroups"
                          :key="group.id"
                          class="rag-doc-card"
                          shadow="hover"
                        >
                          <div class="rag-doc-name">
                            {{ group.sourceName }}
                            <el-tag size="small" effect="plain">{{ group.pages.length }} 页</el-tag>
                          </div>
                          <div class="rag-doc-summary">{{ group.sourceMime }} · {{ formatSize(group.sourceSize) }}</div>
                          <div class="rag-doc-path">已生成 {{ countGroupArtifacts([group]) }} 个文件</div>
                        </el-card>
                      </div>
                    </section>

                    <section v-if="manualOcrAccessoryGroups.length" class="rag-doc-subsection">
                      <div class="rag-doc-header">
                        <div>
                          <div class="rag-doc-title">配件 OCR 文件</div>
                          <div class="rag-doc-sub">共 {{ manualOcrAccessoryGroups.length }} 个文件组，{{ countGroupArtifacts(manualOcrAccessoryGroups) }} 个产出</div>
                        </div>
                      </div>
                      <div class="rag-doc-list">
                        <el-card
                          v-for="group in manualOcrAccessoryGroups"
                          :key="group.id"
                          class="rag-doc-card"
                          shadow="hover"
                        >
                          <div class="rag-doc-name">
                            {{ group.sourceName }}
                            <el-tag size="small" effect="plain">{{ group.pages.length }} 页</el-tag>
                          </div>
                          <div class="rag-doc-summary">{{ group.sourceMime }} · {{ formatSize(group.sourceSize) }}</div>
                          <div class="rag-doc-path">已生成 {{ countGroupArtifacts([group]) }} 个文件</div>
                        </el-card>
                      </div>
                    </section>

                    <div v-if="!manualOcrProductGroups.length && !manualOcrAccessoryGroups.length" class="rag-empty">
                      该会话暂无 OCR 结果。
                    </div>
                  </template>
                  <div v-else class="rag-empty">OCR 数据尚未加载。</div>
                </div>
              </section>
            </div>
          </el-dialog>
        </div>
      </div>
      <div v-else-if="tab === 'poster'" class="panel">
        <div class="title row">
          <div>海报</div>
          <div class="row gap12">
            <el-button size="small" type="primary" plain @click="goPosterCanvasEditor">进入画布编辑器</el-button>
            <el-button size="small" type="primary" @click="exportPoster">导出为图片</el-button>
            <el-button size="small" type="success" @click="exportPosterPdf">导出为PDF</el-button>
            <el-button size="small" type="info" @click="savePosterToDb">保存修改至数据库</el-button>
            <el-button size="small" type="info" plain>查看 RAG 来源</el-button>
            <el-button size="small" type="primary" plain @click="handleGenerateSpecsheet" :loading="loadingSpecsheet">生成海报</el-button>
          </div>
        </div>
        <div class="poster-wrap">
          <div class="poster-canvas" ref="posterRef">
            <div class="poster-bg" :style="{ backgroundImage: `url(${posterData.background})` }" @click="pickPosterImage('background')"></div>
            <div class="poster-headmask"></div>
            <div class="poster-head">
              <div class="poster-title"><span class="hot">HOT</span><span class="mid">COLD</span><span class="end">COMBO</span></div>
              <div class="poster-brand">MASRREN</div>
              <div class="poster-sub">A STEP TO SWITCH TO A HEALTHIER LIFESTYLE.</div>
            </div>
            <div class="poster-mid">
              <div class="poster-left-col">
                <div class="poster-card small pl-feature-top">
                  <img :src="posterData.leftTop.img" alt="" @click="pickPosterImage('leftTop.img')" />
                  <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'leftTop.cap')">{{ posterData.leftTop.cap }}</div>
                </div>
                <div class="poster-bignum hot pl-hotnum">
                  <div class="num" contenteditable="true" @input="onEditPosterWithCaret($event, 'hotNum.value')">{{ posterData.hotNum.value }}</div>
                  <div class="zone" contenteditable="true" @input="onEditPosterWithCaret($event, 'hotNum.zone')">{{ posterData.hotNum.zone }}</div>
                </div>
                <div class="poster-card small pl-mini-heater">
                  <img :src="posterData.leftBottom.img" alt="" @click="pickPosterImage('leftBottom.img')" />
                  <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'leftBottom.cap')">{{ posterData.leftBottom.cap }}</div>
                </div>
              </div>
              <img class="poster-product" :src="posterData.product" alt="product" @click="pickPosterImage('product')" />
              <div class="poster-right-col">
                <div class="poster-card small pr-anti-freeze">
                  <img :src="posterData.rightTop.img" alt="" @click="pickPosterImage('rightTop.img')" />
                  <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'rightTop.cap')">{{ posterData.rightTop.cap }}</div>
                </div>
                <div class="poster-card small pr-aerospace">
                  <img :src="posterData.rightMid.img" alt="" @click="pickPosterImage('rightMid.img')" />
                  <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'rightMid.cap')">{{ posterData.rightMid.cap }}</div>
                </div>
                <div class="poster-bignum cold pr-coldnum">
                  <div class="num" contenteditable="true" @input="onEditPosterWithCaret($event, 'coldNum.value')">{{ posterData.coldNum.value }}</div>
                  <div class="zone" contenteditable="true" @input="onEditPosterWithCaret($event, 'coldNum.zone')">{{ posterData.coldNum.zone }}</div>
                </div>
                <div class="poster-card small pr-foam">
                  <img :src="posterData.rightBottom.img" alt="" @click="pickPosterImage('rightBottom.img')" />
                  <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'rightBottom.cap')">{{ posterData.rightBottom.cap }}</div>
                </div>
              </div>
            </div>
            <div class="poster-bottom">
              <div class="poster-card small ar169 pl-premium">
                <img :src="posterData.bottomLeft.img" alt="" @click="pickPosterImage('bottomLeft.img')" />
                <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'bottomLeft.cap')">{{ posterData.bottomLeft.cap }}</div>
              </div>
              <div class="poster-specs">
                <div class="spec">
                  <img src="/poster/Capacity.png" alt="Capacity" />
                  <div class="s-meta">
                    <div class="s-label">CAPACITY</div>
                    <div class="s-value" contenteditable="true" @input="onEditPosterWithCaret($event, 'specs.capacity')">{{ posterData.specs.capacity }}</div>
                  </div>
                </div>
                <div class="spec">
                  <img src="/poster/Pumps.png" alt="Pumps" />
                  <div class="s-meta">
                    <div class="s-label">PUMPS</div>
                    <div class="s-value" contenteditable="true" @input="onEditPosterWithCaret($event, 'specs.pumps')">{{ posterData.specs.pumps }}</div>
                  </div>
                </div>
                <div class="spec">
                  <img src="/poster/Jets.png" alt="Jets" />
                  <div class="s-meta">
                    <div class="s-label">JETS</div>
                    <div class="s-value" contenteditable="true" @input="onEditPosterWithCaret($event, 'specs.jets')">{{ posterData.specs.jets }}</div>
                  </div>
                </div>
                <div class="spec wide">
                  <img src="/poster/Measurements.png" alt="Measurements" />
                  <div class="s-meta">
                    <div class="s-label">MEASUREMENTS</div>
                    <div class="s-value" contenteditable="true" @input="onEditPosterWithCaret($event, 'specs.measurements')">{{ posterData.specs.measurements }}</div>
                  </div>
                </div>
              </div>
              <div class="poster-card small ar169 pr-hydro">
                <img :src="posterData.bottomRight.img" alt="" @click="pickPosterImage('bottomRight.img')" />
                <div class="poster-cap" contenteditable="true" @input="onEditPosterWithCaret($event, 'bottomRight.cap')">{{ posterData.bottomRight.cap }}</div>
              </div>
            </div>
          </div>
          <!-- 隐藏文件输入：统一更换海报各图片 -->
          <input ref="posterInputRef" type="file" accept="image/*" style="display:none" @change="onPickPosterImage" />
        </div>
      </div>
      <div v-else class="panel">
        <div class="manual-layout">
          <aside class="manual-toc">
            <div class="export-btn">
              <el-button type="primary" size="small" @click="exportManualPdfEditable">导出 PDF</el-button>
              <el-button size="small" style="margin-left:8px" @click="resetManual">重置内容</el-button>
              <el-button size="small" type="info" style="margin-left:8px" @click="saveManualToDb">保存修改至数据库</el-button>
              <el-button size="small" type="info" plain style="margin-left:8px">查看 RAG 来源</el-button>
              <el-button size="small" type="primary" plain style="margin-left:8px" @click="handleGenerateManualBook" :loading="loadingManualBook">生成说明书</el-button>
            </div>

            <div v-if="currentVariantSelectorGroup" class="variant-panel">
              <div class="variant-title">页面版本</div>
              <div class="variant-row">
                <div class="variant-label">{{ currentVariantSelectorGroup.label }}</div>
                <el-radio-group
                  size="small"
                  :model-value="selectedVariants[currentVariantSelectorGroup.key]"
                  @change="(val) => onVariantSelectionChange(currentVariantSelectorGroup.key, val)"
                >
                  <el-radio-button
                    v-for="opt in currentVariantSelectorGroup.options"
                    :key="opt.id"
                    :label="opt.id"
                  >
                    {{ opt.label }}
                  </el-radio-button>
                </el-radio-group>
              </div>
            </div>

            <div class="page-ops">
              <div class="ops-title">当前页操作</div>
              <div class="ops-current">当前页：{{ displayTocPage(currentPageIndex + 1) }} · {{ deriveTitle(currentPage || {}) }}</div>
              <div class="ops-row">
                <el-button size="small" plain @click="addBlankPage(currentPageIndex, 'before')">上方添加空白页</el-button>
                <el-button size="small" plain @click="addBlankPage(currentPageIndex, 'after')">下方添加空白页</el-button>
              </div>
              <div class="ops-row">
                <el-button size="small" type="danger" plain @click="deleteAnyPage(currentPageIndex)">删除当前页</el-button>
              </div>
            </div>
            <div class="toc-title">目录</div>
            <div class="toc-scroll">
              <ul class="toc-list">
                <li v-for="(item, idx) in sidebarItems" :key="'toc-'+idx">
                  <button class="toc-link" :class="{ active: currentPageIndex === (item.page-1) }" @click="goToPage(item.page)"><span class="ct-title">{{ item.title }}</span><span class="toc-page">{{ displayTocPage(item.page) }}</span></button>
                </li>
              </ul>
            </div>
          </aside>
          <main class="manual-pages" ref="manualPagesRef">
            <div class="zoom-toolbar">
              <el-button size="small" @click="decZoom">-</el-button>
              <div class="zoom-text">{{ Math.round(userZoom * 100) }}%</div>
              <el-button size="small" @click="resetZoom">100%</el-button>
              <el-button size="small" @click="incZoom">+</el-button>
            </div>
            <section
              v-if="currentPage"
              :key="currentPage.pageId || ('page-'+(currentPageIndex+1))"
              :class="['manual-page', 'page-'+(currentPageIndex+1)]"
              ref="currentPageRef"
            >
              <div class="page-inner">
                <div v-if="!currentPage.blocks || currentPage.blocks.length === 0" class="block">
                  <h1 class="h1" contenteditable="true" @input="onEditManualPageTitle($event)" v-text="currentPage.customTitle || deriveTitle(currentPage)"></h1>
                </div>
                <div v-for="(blk, bIdx) in currentPage.blocks" :key="(currentPage.pageId || (currentPageIndex+1)) + '-blk-' + bIdx" class="block">
                  <template v-if="blk.type === 'cover'">
                    <div class="cover" :style="coverStyle(blk)" @click.self="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'backSrc'))">
                      <img class="cover-logo" src="/instruction_book/logo.svg" alt="logo" />
                      <div class="cover-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'title'))" v-text="blk.title"></div>
                      <img class="cover-product" :src="blk.productSrc || '/instruction_book/product.png'" alt="product" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'productSrc'))" />
                      <div class="cover-bl">
                        <div class="cover-model" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'model'))">{{ blk.model || blk.title || 'Massern' }}</div>
                        <div class="cover-size" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'sizeText'))" v-text="blk.sizeText"></div>
                      </div>
                      <div class="cover-br">vers. 202409</div>
                    </div>
                  </template>
                  <template v-else-if="blk.type === 'heading'">
                    <h1 v-if="(blk.level ?? 1) === 1" class="h1" :id="blk.anchor || null" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'))" v-text="blk.text"></h1>
                    <h2 v-else-if="(blk.level ?? 1) === 2" class="h2" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'))" v-text="blk.text"></h2>
                    <h3 v-else class="h3" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'))" v-text="blk.text"></h3>
                  </template>
                  <p v-else-if="blk.type === 'paragraph'" class="para" :class="blk.className || ''" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'))" v-text="blk.text"></p>
                  <div v-else-if="blk.type === 'list'" class="list" :class="blk.className || ''">
                    <ol v-if="blk.ordered">
                      <li v-for="(it, li) in blk.items" :key="'li-'+li" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+li), true)" v-html="it"></li>
                    </ol>
                    <ul v-else>
                      <li v-for="(it, li) in blk.items" :key="'li-'+li" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+li), true)" v-html="it"></li>
                    </ul>
                  </div>
                  <figure v-else-if="blk.type === 'image'" class="figure" :class="{ full: blk.fullWidth }">
                    <img :src="blk.src" :alt="blk.alt || ''" :style="imageStyle(blk)" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'src'))" />
                    <figcaption v-if="blk.caption" class="caption" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'caption'))" v-text="blk.caption"></figcaption>
                  </figure>
                  <div v-else-if="blk.type === 'imageFloat' || (typeof blk.type === 'string' && blk.type.startsWith('imageFloat-'))"
                       :class="['img-float', (blk.position || (typeof blk.type==='string' && blk.type.startsWith('imageFloat-') ? blk.type.slice('imageFloat-'.length) : '')) || 'bottom-left']"
                       :style="imageStyle(blk)">
                    <img :src="blk.src" :alt="blk.alt || ''" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'src'))" />
                  </div>
                  <div v-else-if="blk.type === 'table'" class="table-wrap">
                    <table>
                      <thead v-if="blk.headers && blk.headers.length">
                        <tr>
                          <th v-for="(h, hi) in blk.headers" :key="'th-'+hi" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'headers.'+hi))" v-text="h"></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, ri) in blk.rows" :key="'tr-'+ri">
                          <td v-for="(cell, ci) in row" :key="'td-'+ri+'-'+ci" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'rows.'+ri+'.'+ci))" v-text="cell"></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-else-if="blk.type === 'grid4'" class="grid4-wrap">
                    <div class="grid4">
                      <div v-for="(it, i) in (blk.items || []).slice(0,4)" :key="'g4-'+i" class="grid4-item">
                        <div class="g4-head"><span class="g4-badge">{{ it.index ?? (i+1) }}</span><span class="g4-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+i+'.title'))" v-text="it.title"></span></div>
                        <div class="g4-img">
                          <img v-if="it.imgSrc" :src="it.imgSrc" :alt="it.title || ''" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'items.'+i+'.imgSrc'))" />
                          <div v-else class="g4-img-ph">No Image</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'grid2'" class="grid2">
                    <div v-for="(item, idx) in blk.items" :key="'g2-'+idx" class="grid2-item">
                      <img v-if="item.type === 'image'" :src="item.src" :alt="item.alt || ''" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'items.'+idx+'.src'))" />
                      <div v-else-if="item.type === 'list'" class="list">
                        <ol v-if="item.ordered">
                          <li v-for="(it, li) in item.items" :key="'li-'+li" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+idx+'.items.'+li))" v-text="it"></li>
                        </ol>
                        <ul v-else>
                          <li v-for="(it, li) in item.items" :key="'li-'+li" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+idx+'.items.'+li))" v-text="it"></li>
                        </ul>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'spec-box'" class="spec-box">
                    <div class="spec-box-inner">
                      <div class="spec-col left">
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.topLeft.title'))" v-text="blk.specs.topLeft.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.topLeft.items" :key="'tl-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.topLeft.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftTop.title'))" v-text="blk.specs.leftTop.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.leftTop.items" :key="'lt-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftTop.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftMiddle1.title'))" v-text="blk.specs.leftMiddle1.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.leftMiddle1.items" :key="'lm1-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftMiddle1.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftMiddle2.title'))" v-text="blk.specs.leftMiddle2.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.leftMiddle2.items" :key="'lm2-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftMiddle2.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftBottom.title'))" v-text="blk.specs.leftBottom.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.leftBottom.items" :key="'lb-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.leftBottom.items.'+i))" v-text="line"></div>
                        </div>
                      </div>

                      <div class="spec-center">
                        <img :src="blk.imageSrc" alt="Product Specification" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'imageSrc'))" />
                      </div>

                      <div class="spec-col right">
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.topRight.title'))" v-text="blk.specs.topRight.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.topRight.items" :key="'tr-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.topRight.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightTop.title'))" v-text="blk.specs.rightTop.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.rightTop.items" :key="'rt-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightTop.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightMiddle.title'))" v-text="blk.specs.rightMiddle.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.rightMiddle.items" :key="'rm-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightMiddle.items.'+i))" v-text="line"></div>
                        </div>
                        <div class="spec-card">
                          <h3 class="spec-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightBottom.title'))" v-text="blk.specs.rightBottom.title"></h3>
                          <div class="spec-text" v-for="(line, i) in blk.specs.rightBottom.items" :key="'rb-'+i" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'specs.rightBottom.items.'+i))" v-text="line"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'callout' || (typeof blk.type === 'string' && blk.type.startsWith('callout-'))"
                       :class="['callout', 'callout-'+(((blk.variant) || (typeof blk.type==='string' && blk.type.startsWith('callout-') ? blk.type.split('-')[1] : '')) || 'warning'), blk.className || '']">
                    <img class="callout-icon"
                         :src="blk.iconSrc || ((((blk.variant) || (typeof blk.type==='string' && blk.type.startsWith('callout-') ? blk.type.split('-')[1] : '')))==='error' ? '/instruction_book/error.png' : '/instruction_book/warning.png')"
                         alt="icon"
                         @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'iconSrc'))" />
                    <div class="callout-text" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'), true)" v-html="blk.text"></div>
                  </div>
                  <div v-else-if="blk.type === 'contents'" class="contents">
                    <div v-for="(it, i) in getContentsFor(currentPageIndex)" :key="'ct-'+i" class="tocline" :class="['lvl-'+(it.level || 0)]">
                      <span class="ct-title">{{ it.title }}</span>
                      <span class="ct-dots" aria-hidden="true"></span>
                      <span class="ct-page">{{ displayTocPage(it.page) }}</span>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'steps'" class="steps-wrap">
                    <div class="steps">
                      <div v-for="(it, i) in blk.items" :key="'step-'+i" class="step-item">
                        <div class="step-head"><span class="g4-badge">{{ i+1 }}</span></div>
                        <div class="step-text" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'items.'+i))" v-text="it"></div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'note'" class="note" :class="'note-'+(blk.style || 'info')" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'text'))" v-text="blk.text"></div>
                  <div v-else-if="blk.type === 'ts-section'" class="ts-section">
                    <div class="ts-num">{{ blk.index }}</div>
                    <div class="ts-card">
                      <div class="ts-grid">
                        <div class="ts-left">
                          <img class="ts-img" :src="blk.images?.[0]" alt="" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'images.0'))" />
                        </div>
                        <div class="ts-mid">
                          <img class="ts-img mid" :src="blk.images?.[1]" alt="" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'images.1'))" />
                        </div>
                        <div class="ts-right">
                          <div class="mag">
                            <div class="mag-ring">
                              <img v-if="blk.magnifier?.bgSrc" class="mag-shot" :src="blk.magnifier.bgSrc" alt="" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'magnifier.bgSrc'))" />
                            </div>
                            <div class="mag-lines">
                              <div class="mag-title"><span class="bracket">⟨</span> SERIAL NUMBER <span class="bracket">⟩</span></div>
                              <div class="mag-serial" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'magnifier.serial'))" v-text="blk.magnifier?.serial"></div>
                              <img v-if="blk.magnifier?.qrSrc && blk.magnifier?.qrVisible !== false" class="mag-qr" :src="blk.magnifier.qrSrc" alt="QR" :style="{
                                width: (blk.magnifier?.qrSize||72)+ 'px',
                                height: (blk.magnifier?.qrSize||72)+ 'px',
                                margin: (blk.magnifier?.qrMargin ?? '6px auto 6px')
                              }" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'magnifier.qrSrc'))" />
                              <div v-for="(t,i) in (blk.magnifier?.lines||[])" :key="'mline-'+i" class="mag-text" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'magnifier.lines.'+i))" v-text="t"></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="blk.type === 'troubleTable'" class="tb-wrap">
                    <div class="tb-header">
                      <div class="tb-col tb-col-left" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'headers.0'))" v-text="(blk.headers?.[0] || 'Symptom')"></div>
                      <div class="tb-col tb-col-right" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'headers.1'))" v-text="(blk.headers?.[1] || 'Possible Solutions')"></div>
                    </div>
                    <div class="tb-body">
                      <template v-for="(grp, gi) in (blk.groups || [])" :key="'grp-'+gi">
                        <div class="tb-group-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'groups.'+gi+'.title'))" v-text="grp.title"></div>
                        <div v-for="(it, ii) in grp.items" :key="'row-'+gi+'-'+ii" class="tb-row" :class="{ alt: (ii % 2) === 1 }">
                          <div class="tb-cell tb-left" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'groups.'+gi+'.items.'+ii+'.symptom'))" v-text="it.symptom"></div>
                          <div class="tb-cell tb-right">
                            <div v-if="Array.isArray(it.solutions)" class="tb-sol-list">
                              <p v-if="it.description" class="tb-desc" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'groups.'+gi+'.items.'+ii+'.description'))" v-text="it.description"></p>
                              <ul>
                                <li v-for="(s, si) in it.solutions" :key="'sol-'+si" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'groups.'+gi+'.items.'+ii+'.solutions.'+si))" v-text="s"></li>
                              </ul>
                            </div>
                            <p v-else class="tb-desc" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'groups.'+gi+'.items.'+ii+'.solutions'))" v-text="it.solutions"></p>
                          </div>
                        </div>
                      </template>
                    </div>
                  </div>
                  <hr v-else-if="blk.type === 'divider'" class="divider" />
                </div>
                <div v-if="isAfterContents(currentPageIndex)" class="page-num-footer">{{ displayPageNum(currentPageIndex) }}</div>
              </div>
            </section>
            <!-- 说明书图片选择弹框：本地上传 + 知识库图片 -->
            <el-dialog
              v-model="manualImageDialogVisible"
              title="更换说明书图片"
              width="520px"
            >
              <div class="product-dialog">
                <el-tabs v-model="manualImageDialogTab">
                  <el-tab-pane label="本地上传" name="local">
                    <div class="product-dialog-section">
                      <p>从本地选择一张图片替换当前说明书图片。</p>
                      <el-button type="primary" @click="triggerLocalManualImageUpload">选择本地图片</el-button>
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
                          @click="selectKbManualImage(img.src)"
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
            <input ref="manualImageInputRef" type="file" accept="image/*" style="display:none" @change="onPickManualImage" />
          </main>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import { useRoute, useRouter } from 'vue-router'
import { Promotion, Picture, Document } from '@element-plus/icons-vue'
import { useManualStore } from '@/stores/manualStore'
import { ElMessage } from 'element-plus'
import {
  insertManualProduct,
  getSpecsheet,
  saveSpecsheet,
  getManualSpecsheet,
  saveManualSpecsheet,
  runManualSpecsheetAce,
  getManualSession,
  getSavedBomBySession,
  getSavedManualBook,
  getSavedManualSpecsheet,
  saveManualBookTruth,
  saveManualSpecsheetTruth,
  getManualBookVariants,
  saveManualBookVariants,
  generateManualBookFromOcr
} from '@/services/api'
import { BOM_CONFIG } from '@/constants/bomOptions'

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id)
const manualStore = useManualStore()
const productName = computed(() => manualStore.productName || getFirstQueryValue(route.query.productName) || '')
const manualSessionId = computed(() => manualStore.sessionId || getFirstQueryValue(route.query.sessionId) || '')
const manualBomType = computed(() => manualStore.bomType || getFirstQueryValue(route.query.bomType) || '')
const name = computed(() => productName.value || route.query.name || 'OCR 规格页')
const image = computed(() => route.query.image || 'placeholder.jpg')
const bomCode = ref(manualStore.bomCode || '')
const bomDetails = ref(null)
const bomDetailDialogVisible = ref(false)
const bomLoading = ref(false)
const bomError = ref('')
const specsheetResultDialogVisible = ref(false)
const showSpecsheetResultDialogOnGenerate = ref(false)
const specsheetResultPayload = ref('')
const manualBookResultDialogVisible = ref(false)
const manualBookResultPayload = ref('')
const insertingProduct = ref(false)
const autoSpecsheetLoading = ref(false)
const autoSpecsheetLoadedKey = ref('')
const manualSpecsheetLoadedKey = ref('')

const savedManualBookLoading = ref(false)
const savedManualBookLoadedKey = ref('')

const savedManualSpecsheetLoading = ref(false)
const savedManualSpecsheetLoadedKey = ref('')

const redactChunkText = (chunk = {}) => {
  const sanitized = { ...chunk }
  if ('text' in sanitized) sanitized.text = '[REDACTED]'
  if ('raw_text' in sanitized) sanitized.raw_text = '[REDACTED]'
  if (Array.isArray(sanitized.documents)) {
    sanitized.documents = sanitized.documents.map((doc) => {
      const docClone = { ...doc }
      if ('text' in docClone) docClone.text = '[REDACTED]'
      if ('content' in docClone) docClone.content = '[REDACTED]'
      return docClone
    })
  }
  return sanitized
}

const handleGenerateManualBook = async () => {
  if (loadingManualBook.value) return

  const documents = getCurrentOcrDocuments()
  if (!documents.length) {
    manualBookError.value = '请先上传或传入 OCR 结果后再生成说明书'
    return
  }
  if (!bomCode.value) {
    manualBookError.value = '当前产品缺少 BOM 号，无法生成说明书'
    return
  }

  loadingManualBook.value = true
  manualBookProgress.value = 20
  manualBookLoadingText.value = '正在汇总 OCR 文档…'
  manualBookError.value = ''

  try {
    const payload = {
      documents,
      session_id: manualSessionId.value || undefined,
      bom_code: bomCode.value,
      product_name: productName.value || name.value || '',
    }
    const result = await generateManualBookFromOcr(payload)
    manualBookProgress.value = 80
    manualBookLoadingText.value = '正在解析说明书...'

    const dialogPayload = {
      request: {
        documents: sanitizeRequestDocuments(documents),
        bom_code: payload.bom_code,
        session_id: payload.session_id,
        product_name: payload.product_name
      },
      response: {
        manual_book: result?.manual_book || null,
        prompt_text: result?.prompt_text || '',
        system_prompt: result?.system_prompt || ''
      },
    }
    manualBookResultPayload.value = JSON.stringify(dialogPayload, null, 2)
    manualBookResultDialogVisible.value = true

    // 优先使用 pages 全量覆盖（假设后端已按固定顺序输出）；否则按 header 定点替换
    let hydrated = false
    const book = result?.manual_book

    // 新格式：直接返回数组；仅在数组有数据时全量覆盖
    const pagesFromBackend = Array.isArray(book) ? book : []

    if (pagesFromBackend.length) {
      const allowedTypes = new Set([
        'heading',
        'paragraph',
        'list',
        'cover',
        'image',
        'imageFloat-bottom-left',
        'imageFloat-bottom-right',
        'imageFloat-top-left',
        'imageFloat-top-right',
        'steps',
        'callout-warning',
        'callout-error',
        'spec-box',
        'grid2',
        'grid4',
        'contents',
        'divider',
        'ts-section',
        'troubleTable',
        'table',
      ])

      const isSuspiciousText = (text = '') => {
        const t = String(text || '').trim()
        if (!t) return false
        if (t.startsWith('[') || t.startsWith('{')) return true
        if (t === ']' || t === '}' || t === '},' || t === '],') return true
        if (t.includes('"header"') || t.includes('\"header\"')) return true
        if (t.includes('"blocks"') || t.includes('\"blocks\"')) return true
        if (t.includes('"type"') || t.includes('\"type\"')) return true
        if (t.includes('"items"') || t.includes('\"items\"')) return true
        if (/^"[A-Za-z_][A-Za-z0-9_]*"\s*:\s*/.test(t)) return true
        return false
      }

      const cloneDeep = (value) => {
        try {
          if (typeof structuredClone === 'function') return structuredClone(value)
        } catch (e) {}
        return JSON.parse(JSON.stringify(value))
      }

      const pageIdBase = `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`

      const normalizedPages = pagesFromBackend
        .filter((p) => p && p.header)
        .map((p, idx) => {
          const safeBlocks = Array.isArray(p.blocks)
            ? p.blocks
                .filter((blk) => blk && typeof blk === 'object' && allowedTypes.has(blk.type))
                .filter((blk) => {
                  if (blk.type === 'heading' || blk.type === 'paragraph') {
                    return !isSuspiciousText(blk.text)
                  }
                  if (blk.type === 'list' && Array.isArray(blk.items)) {
                    return !blk.items.some((item) => isSuspiciousText(item))
                  }
                  return true
                })
                .map((blk) => {
                  if (blk.type === 'table') {
                    const headers = Array.isArray(blk.headers) ? blk.headers : null
                    const rows = Array.isArray(blk.rows) ? blk.rows : null
                    if (headers && rows) return { ...blk }

                    const data = Array.isArray(blk.data) ? blk.data : null
                    if (data && data.length && Array.isArray(data[0])) {
                      const hdr = data[0].map((x) => String(x ?? ''))
                      const rs = data.slice(1).map((r) => (Array.isArray(r) ? r.map((x) => String(x ?? '')) : []))
                      return { ...blk, headers: hdr, rows: rs }
                    }
                    return { ...blk, headers: [], rows: [] }
                  }
                  return { ...blk }
                })
            : []

          const clonedBlocks = cloneDeep(safeBlocks)

          return {
            pageId: `${pageIdBase}-p${idx}`,
            header: p.header,
            blocks: clonedBlocks,
          }
        })
      if (normalizedPages.length) {
        manualPages.value = cloneDeep(normalizedPages)
        manualMeta.value.toc = normalizedPages.map((p, idx) => ({ title: p.header, page: idx + 1 }))
        currentPageIndex.value = 0
        hydrated = true
      }
    }

    manualBookProgress.value = 100
    manualBookLoadingText.value = hydrated
      ? '加载完成！（已按返回顺序覆盖或按 header 替换）'
      : '已返回 JSON，未找到匹配页面，保留原内容'
  } catch (error) {
    console.error('Failed to load manual book:', error)
    manualBookProgress.value = 100
    manualBookError.value = error?.message || '生成说明书失败'
  } finally {
    setTimeout(() => {
      loadingManualBook.value = false
    }, 600)
  }
}

const openBomDetailDialog = async () => {
  if (!bomDetails.value?.segments?.length) {
    await loadSessionBom({ reopen: true })
    if (!bomDetails.value?.segments?.length) {
      bomError.value = '暂无可展示的 BOM 配置'
      return
    }
  }
  bomDetailDialogVisible.value = true
}

const sanitizeSpecsheetResult = (result = {}) => {
  const payload = { ...result }
  if (Array.isArray(payload.chunks)) {
    payload.chunks = payload.chunks.map((chunk) => redactChunkText(chunk))
  }
  return payload
}

 const sanitizeRequestDocuments = (docs = []) => {
  return docs.map((doc) => ({
    name: doc?.name || '未命名文件',
    path: doc?.path || '',
    type: doc?.type || 'document',
    summary: doc?.summary || '',
    mime_type: doc?.mime_type || doc?.mime || doc?.kind || doc?.type || '',
    // 去掉可能包含敏感原文的大字段
    text: '[REDACTED]',
    image_base64: doc?.image_base64 ? '[IMAGE_BASE64]' : '',
  }))
}

const getFirstQueryValue = (value) => (Array.isArray(value) ? value[0] : value)

const goBack = () => {
  const returnTo = getFirstQueryValue(route.query.returnTo)
  if (typeof returnTo === 'string' && returnTo.trim()) {
    router.push(returnTo)
    return
  }

  if (window.history.length > 1) {
    router.back()
    return
  }

  router.push({
    name: 'ManualReview',
    query: {
      sessionId: manualSessionId.value || undefined,
      productName: productName.value || undefined,
      bomType: manualBomType.value || undefined,
    },
  })
}

const flattenBomSections = (sections = []) => {
  const flattened = []
  sections.forEach((section) => {
    if (Array.isArray(section.children) && section.children.length) {
      section.children.forEach((child) => {
        flattened.push({
          key: child.key,
          label: child.label,
          digits: child.digits || 0,
          options: child.options || {}
        })
      })
    } else {
      flattened.push({
        key: section.key,
        label: section.label,
        digits: section.digits || 0,
        options: section.options || {}
      })
    }
  })
  return flattened
}

const computeTotalDigits = (sections = []) => {
  return sections.reduce((sum, section) => sum + (section.digits || 0), 0)
}

const determineBomTypeFromCode = (code = '') => {
  const normalized = String(code || '').trim()
  if (!normalized.length) return null
  const hintedRaw = String(manualBomType.value || '').trim()
  const hintedKey = hintedRaw
    ? Object.keys(BOM_CONFIG).find((k) => k.toLowerCase() === hintedRaw.toLowerCase())
    : null
  if (hintedKey && BOM_CONFIG[hintedKey]) {
    const hintedSections = flattenBomSections(BOM_CONFIG[hintedKey])
    const hintedDigits = computeTotalDigits(hintedSections)
    if (hintedDigits === normalized.length) {
      return hintedKey
    }
  }
  const matchingType = Object.keys(BOM_CONFIG).find((type) => {
    const sections = flattenBomSections(BOM_CONFIG[type])
    return computeTotalDigits(sections) === normalized.length
  })
  return matchingType || Object.keys(BOM_CONFIG)[0] || null
}

const deriveBomDetailsFromCode = (code = '') => {
  const normalized = String(code || '').trim().toUpperCase()
  if (!normalized) return null
  const bomType = determineBomTypeFromCode(normalized)
  if (!bomType || !BOM_CONFIG[bomType]) return null
  const sections = flattenBomSections(BOM_CONFIG[bomType])
  if (!sections.length) return null
  const totalDigits = computeTotalDigits(sections)
  if (totalDigits !== normalized.length) return null
  const segments = []
  let cursor = 0
  for (const section of sections) {
    const digits = section.digits || 0
    if (!digits) continue
    const value = normalized.slice(cursor, cursor + digits)
    if (value.length !== digits) {
      return null
    }
    segments.push({
      key: section.key,
      label: section.label,
      value,
      digits,
      meaning: section.options?.[value] || '',
      reason: ''
    })
    cursor += digits
  }
  return { type: bomType, segments }
}

const ensureBomDetailsFromCode = () => {
  if (bomDetails.value && bomDetails.value.segments?.length) return
  const derived = deriveBomDetailsFromCode(bomCode.value)
  if (derived) {
    bomDetails.value = derived
  }
}

const setBomFromSession = (session) => {
  const code = session?.bom_code || manualStore.bomCode || ''
  const incomingType = session?.bom_type || session?.bomType || ''
  bomCode.value = code
  manualStore.bomCode = code
  if (incomingType) manualStore.bomType = incomingType
  bomDetails.value = session?.bom_details || null
  ensureBomDetailsFromCode()
}

const loadBomDetails = async () => {
  bomDetails.value = null
  if (!manualSessionId.value) return
  try {
    const saved = await getSavedBomBySession(manualSessionId.value)
    if (saved?.bomType) manualStore.bomType = saved.bomType
    bomDetails.value = saved?.segments?.length
      ? {
          type: saved.bomType,
          segments: saved.segments.map((segment) => ({
            key: segment.key,
            label: segment.label,
            value: segment.value,
            digits: segment.digits,
            meaning: segment.meaning,
            reason: segment.reason
          }))
        }
      : null
  } catch {
    // ignore detail load errors separately; overall load displays error already
  }
  ensureBomDetailsFromCode()
}

const loadSessionBom = async ({ reopen = false } = {}) => {
  if (!manualSessionId.value) {
    bomError.value = ''
    setBomFromSession(null)
    return
  }
  bomLoading.value = true
  bomError.value = ''
  try {
    const session = await getManualSession(manualSessionId.value)
    setBomFromSession(session)
    if (session?.bom_details) {
      bomDetails.value = session.bom_details
    } else {
      await loadBomDetails()
    }
    if (reopen && bomDetails.value?.segments?.length) {
      bomDetailDialogVisible.value = true
    }
  } catch (error) {
    bomError.value = error?.message || 'BOM 加载失败'
  } finally {
    bomLoading.value = false
  }
}

const normalizeDocsFromQuery = (value, label) => {
  const raw = getFirstQueryValue(value)
  if (typeof raw !== 'string' || !raw.trim()) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((item) => item && typeof item === 'object')
      .map((doc, index) => ({
        key: `${label}-${doc?.path || doc?.name || index}`,
        name: doc?.name || '未命名文件',
        path: doc?.path || '',
        type: doc?.type || 'document',
        summary: doc?.summary || '',
      }))
  } catch (error) {
    console.warn(`Failed to parse ${label} from query`, error)
    return []
  }
}

const handleGenerateSpecsheet = async () => {
  if (loadingSpecsheet.value) return
  await loadSpecsheetData()
}

const normalizeAccessoryGroupsFromQuery = (value) => {
  const raw = getFirstQueryValue(value)
  if (typeof raw !== 'string' || !raw.trim()) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((group, index) => {
        const groupLabel = group?.accessory || `accessory-${index + 1}`
        const docs = (Array.isArray(group?.documents) ? group.documents : []).map((doc, docIdx) => ({
          key: `${groupLabel}-${doc?.path || doc?.name || docIdx}`,
          name: doc?.name || '未命名文件',
          path: doc?.path || '',
          type: doc?.type || 'document',
          summary: doc?.summary || '',
        }))
        return {
          key: `group-${groupLabel}-${index}`,
          accessory: group?.accessory || `配件 ${index + 1}`,
          documents: docs,
        }
      })
      .filter((group) => group.documents.length)
  } catch (error) {
    console.warn('Failed to parse accessory docs from query', error)
    return []
  }
}

const productDocsFromRoute = computed(() => normalizeDocsFromQuery(route.query.productDocs, 'productDoc'))
const accessoryDocGroupsFromRoute = computed(() => normalizeAccessoryGroupsFromQuery(route.query.accessoryDocs))
const accessoryNameFromRoute = computed(() => getFirstQueryValue(route.query.accessoryName) || '')

const sessionDocuments = ref([])
const sessionDocumentsLoaded = ref(false)
const sessionDocumentsLoading = ref(false)
const sessionDocumentsError = ref('')

const resetSessionDocuments = () => {
  sessionDocuments.value = []
  sessionDocumentsLoaded.value = false
  sessionDocumentsLoading.value = false
  sessionDocumentsError.value = ''
}

const loadSessionDocuments = async () => {
  if (!manualSessionId.value || sessionDocumentsLoaded.value || sessionDocumentsLoading.value) return
  sessionDocumentsLoading.value = true
  sessionDocumentsError.value = ''
  try {
    const { getManualSessionInputs } = await import('@/services/api')
    const documents = await getManualSessionInputs(manualSessionId.value)
    sessionDocuments.value = Array.isArray(documents) ? documents.filter(Boolean) : []
    sessionDocumentsLoaded.value = true
  } catch (error) {
    sessionDocumentsError.value = error?.message || '加载会话 OCR 文档失败'
    console.error('Failed to load manual session documents:', error)
  } finally {
    sessionDocumentsLoading.value = false
  }
}

watch(manualSessionId, () => {
  resetSessionDocuments()
  if (manualSessionId.value) {
    loadSessionDocuments()
    loadSessionBom()
  } else {
    setBomFromSession(null)
    bomDetailDialogVisible.value = false
  }
})

onMounted(() => {
  if (manualSessionId.value) {
    loadSessionDocuments()
    loadSessionBom()
  }
})

const tryLoadSavedManualBook = async () => {
  const pn = (productName.value || name.value || '').trim()
  const bc = (bomCode.value || '').trim()
  if (!pn || !bc) return false
  const loadKey = `${pn}__${bc}`
  if (savedManualBookLoadedKey.value === loadKey || savedManualBookLoading.value) return false

  savedManualBookLoading.value = true
  try {
    const result = await getSavedManualBook(pn, bc)
    if (!result?.manual_book) {
      savedManualBookLoadedKey.value = loadKey
      return false
    }

    const book = result.manual_book
    const pagesFromBackend = Array.isArray(book) ? book : []
    if (!pagesFromBackend.length) {
      savedManualBookLoadedKey.value = loadKey
      return false
    }

    const cloneDeep = (value) => {
      try {
        if (typeof structuredClone === 'function') return structuredClone(value)
      } catch (e) {}
      return JSON.parse(JSON.stringify(value))
    }

    const pageIdBase = `manual-saved-${Date.now()}-${Math.random().toString(16).slice(2)}`
    const normalizedPages = pagesFromBackend
      .filter((p) => p && p.header)
      .map((p, idx) => ({
        pageId: `${pageIdBase}-p${idx}`,
        header: p.header,
        blocks: cloneDeep(Array.isArray(p.blocks) ? p.blocks : [])
      }))

    if (normalizedPages.length) {
      manualPages.value = cloneDeep(normalizedPages)
      manualMeta.value.toc = normalizedPages.map((p, idx) => ({ title: p.header, page: idx + 1 }))
      currentPageIndex.value = 0
    }

    savedManualBookLoadedKey.value = loadKey
    return true
  } catch (error) {
    console.warn('Failed to load saved manual book:', error)
    return false
  } finally {
    savedManualBookLoading.value = false
  }
}

watch(
  [productName, bomCode],
  () => {
    tryLoadSavedManualBook()
  },
  { immediate: true }
)

const getCurrentOcrDocuments = () => {
  // 所有来源的 OCR 文档最终都会被收集进 docs，作为生成规格页的输入
  const docs = []

  const normalizePath = (value) => {
    if (!value) return ''
    return value.replace(/^\/api\/files\//, '').replace(/^\/+/, '')
  }

  const isManualUploadPath = (path = '') => {
    if (!path) return false
    const normalized = path.replace(/^\/+/, '')
    return normalized.startsWith('manual_uploads/')
  }

  const pushDoc = (item) => {
    if (!item) return
    const rawPath = item.path || item.relative_path || normalizePath(item.url)
    const normalizedPath = normalizePath(rawPath)
    if (isManualUploadPath(normalizedPath)) return
    docs.push({
      name: item.name,
      path: normalizedPath,
      type: item.type || 'document',
      summary: item.summary,
      text: item.text,
      mime_type: item.mime_type || item.mime || item.kind || item.type,
      image_base64: item.image_base64 || '',
    })
  }

  // 1) 用户通过路由 query 直接传入的产品 / 配件文档
  productDocsFromRoute.value.forEach(pushDoc)
  accessoryDocGroupsFromRoute.value.forEach((group) => {
    group.documents.forEach(pushDoc)
  })

  // 2) 手动 OCR 会话接口返回的数据
  if (sessionDocuments.value.length) {
    sessionDocuments.value.forEach(pushDoc)
  }

  // 3) Pinia store 中实时上传的零散 OCR 文件
  ;(manualStore.productOcrFiles || []).forEach(pushDoc)
  ;(manualStore.accessoryOcrFiles || []).forEach(pushDoc)

  // 4) Pinia store 中按“页面/附件”结构存储的 OCR 分组，需要进一步展开
  const flattenGroups = (groups = []) => {
    groups.forEach((group) => {
      (group.pages || []).forEach((page) => {
        (page.artifacts || []).forEach((artifact) => {
          pushDoc({
            name: artifact.name,
            path: artifact.path,
            url: artifact.url,
            type: artifact.kind || artifact.type || 'document',
            summary: artifact.caption,
            text: artifact.text,
            mime_type: artifact.type || artifact.mime,
          })
        })
      })
    })
  }

  flattenGroups(manualStore.productOcrGroups)
  flattenGroups(manualStore.accessoryOcrGroups)

  return docs
}

const formatDocType = (type) => {
  if (type === 'image') return '图片'
  if (type === 'image_embedded') return '文档图片'
  return '文件'
}

const tab = ref('promo')

const goPosterCanvasEditor = () => {
  router.push({
    path: '/poster-editor',
    query: {
      returnTo: route.fullPath,
      productName: productName.value || undefined,
      bomCode: bomCode.value || undefined,
    },
  })
}

const handleInsertProduct = async () => {
  if (insertingProduct.value) return
  const docs = getCurrentOcrDocuments()
  if (!productName.value) {
    ElMessage.warning('缺少产品名称，请先填写或加载手册')
    return
  }
  if (!docs.length) {
    ElMessage.warning('暂无可写入的 OCR 文件，请先生成或加载文档')
    return
  }
  insertingProduct.value = true
  try {
    const payload = {
      product_name: productName.value,
      display_name: name.value,
      bom_code: bomCode.value || '',
      session_id: manualSessionId.value || '',
      documents: docs
    }
    const result = await insertManualProduct(payload)
    const { documents_attached: attached = 0 } = result?.result || {}
    ElMessage.success(`已写入 Neo4j（新增/更新 ${attached} 个文件关系）`)
  } catch (error) {
    console.error('Failed to insert product into Neo4j:', error)
    ElMessage.error(error?.message || '写入 Neo4j 失败，请稍后重试')
  } finally {
    insertingProduct.value = false
  }
}

// 规格页配色：主色 / 背景色 / 文本色，通过调色盘选择
const promoMainColor = ref('#2c6ea4')
const promoBgColor = ref('#ffffff')
const promoTextColor = ref('#111827')
const promoPredefineMainColors = ['#2c6ea4', '#c25a1a', '#111827']
const promoPredefineBgColors = ['#ffffff', '#f5f7fa', '#111827']
const promoPredefineTextColors = ['#111827', '#374151', '#e5e7eb']

// 规格页预设主题：默认 / 暖色 / 深色
const applyPromoPreset = (preset) => {
  if (preset === 'default') {
    promoMainColor.value = '#2c6ea4'
    promoBgColor.value = '#ffffff'
    promoTextColor.value = '#111827'
  } else if (preset === 'warm') {
    promoMainColor.value = '#c25a1a'
    promoBgColor.value = '#f5f7fa'
    promoTextColor.value = '#5b4632'
  } else if (preset === 'dark') {
    promoMainColor.value = '#93c5fd'
    promoBgColor.value = '#111827'
    promoTextColor.value = '#e5e7eb'
  }
}

const selectRagChunk = (idx) => {
  selectedRagIndex.value = idx | 0
}

// 海报：JSON 驱动数据（可通过路由查询参数 poster 传入 JSON 字符串覆盖）
// 数据格式说明：
// - background: string  海报背景图 URL（必填，支持相对/绝对路径）
// - product: string     海报产品主图 URL（必填）
// - leftTop / leftBottom / rightTop / rightMid / rightBottom / bottomLeft / bottomRight: { img: string, cap: string }
//     · img: 该卡片的图片 URL（必填，留空则不显示）
//     · cap: 该卡片的文字说明，可编辑
// - hotNum:   { value: string, zone: string }   热区大数字与分区文案
// - coldNum:  { value: string, zone: string }   冷区大数字与分区文案
// - specs:    { capacity: string, pumps: string, jets: string, measurements: string }
const initialPosterData = {
  "background": "/poster/back.png",
  "product": "/poster/product.png",
  "leftTop": { "img": "/poster/image.png", "cap": "Spacious Footwear Area" },
  "leftBottom": { "img": "/poster/image.png", "cap": "Mini Heater Exchanger" },
  "rightTop": { "img": "/poster/image.png", "cap": "Anti-freeze System" },
  "rightMid": { "img": "/poster/image.png", "cap": "One-Piece Aerospace Molding" },
  "rightBottom": { "img": "/poster/image.png", "cap": "Full Foam Insulation (cold zone)" },
  "bottomLeft": { "img": "/poster/image.png", "cap": "Premium Lighting" },
  "bottomRight": { "img": "/poster/image.png", "cap": "HydroPress Filter" },
  "hotNum": { "value": "104°F", "zone": "SPA ZONE" },
  "coldNum": { "value": "42°F", "zone": "COLD ZONE" },
  "specs": { "capacity": "4", "pumps": "3", "jets": "22", "measurements": '85" × 85" × 39"' }
}
// 顶部商标 Logo 图片
const logoSrc = ref('/product_standard/logo.png')
const logoInputRef = ref(null)
// 手册图片选择与写入
const manualImageInputRef = ref(null)
let _manualPickPath = ''
const manualImageDialogVisible = ref(false)
const manualImageDialogTab = ref('local')
const pickManualImage = (path) => {
  _manualPickPath = String(path || '')
  if (!_manualPickPath) return
  manualImageDialogTab.value = 'local'
  manualImageDialogVisible.value = true
}

const triggerLocalManualImageUpload = () => {
  if (!_manualPickPath) return
  if (manualImageInputRef.value) manualImageInputRef.value.click()
}

const selectKbManualImage = (src) => {
  if (!src || !_manualPickPath) return
  setByPath(manualRoot(), _manualPickPath, src)
  manualImageDialogVisible.value = false
}

const onPickManualImage = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    if (_manualPickPath) setByPath(manualRoot(), _manualPickPath, reader.result)
    manualImageDialogVisible.value = false
  }
  reader.readAsDataURL(f)
  // reset input
  try { e.target.value = '' } catch (err) {}
}
// 海报图片替换
const posterInputRef = ref(null)
let _posterPickPath = ''
const pickPosterImage = (path) => {
  const labelMap = {
    'background': '背景图片',
    'product': '产品图片',
    'leftTop.img': '左上图片',
    'leftBottom.img': '左下图片',
    'rightTop.img': '右上图片',
    'rightMid.img': '右中图片',
    'rightBottom.img': '右下图片',
    'bottomLeft.img': '底部左侧图片',
    'bottomRight.img': '底部右侧图片'
  }
  const label = labelMap[path] || '图片'
  const ok = window.confirm(`是否更换${label}?`)
  if (!ok) return
  _posterPickPath = path
  if (posterInputRef.value) posterInputRef.value.click()
}
const onPickPosterImage = (e) => {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    // 写入 posterData 指定路径
    const segs = _posterPickPath.split('.')
    let obj = posterData.value
    for (let i = 0; i < segs.length - 1; i++) {
      const k = segs[i]
      if (!(k in obj) || typeof obj[k] !== 'object') obj[k] = {}
      obj = obj[k]
    }
    obj[segs[segs.length - 1]] = reader.result
    // 若替换了背景，需刷新 inline 背景样式
    if (_posterPickPath === 'background') {
      // nothing else needed, style 绑定已指向 posterData.background
    }
  }
  reader.readAsDataURL(f)
  e.target.value = ''
}
const posterData = ref(JSON.parse(JSON.stringify(initialPosterData)))

const deepMerge = (target, src) => {
  if (src && typeof src === 'object') {
    Object.keys(src).forEach(k => {
      const sv = src[k]
      if (sv && typeof sv === 'object' && !Array.isArray(sv)) {
        if (!target[k] || typeof target[k] !== 'object') target[k] = {}
        deepMerge(target[k], sv)
      } else if (sv !== undefined) {
        target[k] = sv
      }
    })
  }
  return target
}

onMounted(() => {
  // 允许通过路由 query.poster 传入 URL 编码的 JSON 字符串
  const raw = route.query.poster
  if (typeof raw === 'string' && raw.trim()) {
    try {
      const decoded = decodeURIComponent(raw)
      const incoming = JSON.parse(decoded)
      posterData.value = deepMerge(JSON.parse(JSON.stringify(initialPosterData)), incoming)
    } catch (e) {
      // ignore parse errors and keep defaults
    }
  }
})

const loadScript = (src) =>
  new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve()
    const s = document.createElement('script')
    s.src = src
    s.onload = () => resolve()
    s.onerror = reject
    document.body.appendChild(s)
  })

// 规格页导出
const promoRef = ref(null)

const resolvePromoCanvasEl = async () => {
  // promo canvas sits under v-if (tab switch) and may not be in DOM immediately.
  // Retry a few frames to make export more robust.
  for (let i = 0; i < 5; i += 1) {
    await nextTick()
    const el = promoRef.value
    if (el) return el
    const fallback = document.querySelector('.promo-wrap .promo-canvas')
    if (fallback) return fallback
    await new Promise((r) => requestAnimationFrame(r))
  }
  return null
}

const exportPromo = async () => {
  if (!html2canvas) {
    ElMessage.error('导出失败：html2canvas 未就绪')
    return
  }
  const el = await resolvePromoCanvasEl()
  if (!el) {
    ElMessage.error('导出失败：未找到规格页画布')
    return
  }
  const scale = Math.max(2, Math.ceil(window.devicePixelRatio || 1)) * 2
  const canvas = await html2canvas(el, { scale, backgroundColor: '#ffffff', useCORS: true })
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = `${name.value || productName.value || '规格页'}-规格页.png`
  a.click()
}

const exportPromoPdfEditable = async () => {
  const el = await resolvePromoCanvasEl()
  if (!el) {
    ElMessage.error('导出失败：未找到规格页画布')
    return
  }
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  document.body.appendChild(iframe)
  const doc = iframe.contentDocument || iframe.contentWindow.document
  const styles = Array.from(document.querySelectorAll('style'))
    .map((s) => s.outerHTML)
    .join('\n')
  const title = name.value || productName.value || '规格页'
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${title} - 可编辑PDF导出</title>
      <style>
        @page { size: A4 portrait; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        .print-page { width: 210mm; height: 297mm; padding: 0; margin: 0; box-sizing: border-box; display: flex; justify-content: center; align-items: center; }
        .print-page .promo-canvas { width: 210mm; height: 297mm; }
      </style>
      ${styles}
    </head>
    <body>
      <div class="print-page">${el.outerHTML}</div>
      <script>
        window.addEventListener('load', () => { setTimeout(() => { window.focus(); window.print(); }, 50); });
        window.onafterprint = () => { setTimeout(() => { parent.document.body.removeChild(frameElement); }, 0); };
      <\/script>
    </body>
  </html>`
  doc.open()
  doc.write(html)
  doc.close()
}

const posterRef = ref(null)

const exportPoster = async () => {
  const el = posterRef.value
  if (!el || !html2canvas) {
    ElMessage.error('导出失败：未找到海报画布')
    return
  }
  const rect = el.getBoundingClientRect()
  const targetLongSide = 3508
  const computedScale = targetLongSide / Math.max(1, rect.width)
  const scale = Math.min(5, Math.max(2, computedScale))

  el.classList.add('exporting')
  await nextTick()
  let canvas
  try {
    const bgEl = el.querySelector('.poster-bg')
    const maskEl = el.querySelector('.poster-headmask')
    let prevBg = ''
    if (bgEl) {
      prevBg = bgEl.style.backgroundImage || getComputedStyle(bgEl).backgroundImage || ''
      bgEl.dataset.prevBg = prevBg
      const grad = 'linear-gradient(to bottom, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.12) 60%, rgba(0,0,0,0.01) 98%, rgba(0,0,0,0.001) 100%)'
      bgEl.style.backgroundImage = `${grad}, ${prevBg}`
    }
    if (maskEl) maskEl.style.display = 'none'

    canvas = await html2canvas(el, { scale, backgroundColor: '#ffffff', useCORS: true })

    if (bgEl) bgEl.style.backgroundImage = bgEl.dataset.prevBg || prevBg
    if (maskEl) maskEl.style.display = ''
  } finally {
    el.classList.remove('exporting')
  }
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = `${name.value || productName.value || '海报'}-海报.png`
  a.click()
}

const exportPosterPdf = async () => {
  const el = posterRef.value
  if (!el) {
    ElMessage.error('导出失败：未找到海报画布')
    return
  }
  const pageWmm = 297
  const pageHmm = 210
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  document.body.appendChild(iframe)
  const doc = iframe.contentDocument || iframe.contentWindow.document
  const styles = Array.from(document.querySelectorAll('style'))
    .map((s) => s.outerHTML)
    .join('\n')
  const title = name.value || productName.value || '海报'
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${title} - 海报PDF导出</title>
      ${styles}
      <style>
        @page { size: ${pageWmm}mm ${pageHmm}mm; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        .print-page { width: ${pageWmm}mm; height: ${pageHmm}mm; padding: 0; margin: 0; box-sizing: border-box; position: relative; }
        .print-page .poster-canvas { position: absolute; inset: 0; width: ${pageWmm}mm !important; height: ${pageHmm}mm !important; aspect-ratio: auto !important; border: 0 !important; border-radius: 0 !important; box-shadow: none !important; }
      </style>
    </head>
    <body>
      <div class="print-page">${el.outerHTML}</div>
      <script>
        window.addEventListener('load', () => { setTimeout(() => { window.focus(); window.print(); }, 50); });
        window.onafterprint = () => { setTimeout(() => { parent.document.body.removeChild(frameElement); }, 0); };
      <\/script>
    </body>
  </html>`
  doc.open()
  doc.write(html)
  doc.close()
}

const exportManualPdfEditable = async () => {
  const el = currentPageRef.value
  if (!el) {
    ElMessage.error('导出失败：未找到当前说明书页面')
    return
  }
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  document.body.appendChild(iframe)
  const doc = iframe.contentDocument || iframe.contentWindow.document
  const styles = Array.from(document.querySelectorAll('style'))
    .map((s) => s.outerHTML)
    .join('\n')
  const title = name.value || productName.value || '说明书'
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${title} - 说明书PDF导出</title>
      ${styles}
      <style>
        @page { size: A4 portrait; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        .print-page { width: 210mm; height: 297mm; padding: 0; margin: 0; box-sizing: border-box; position: relative; overflow: hidden; }
        .print-page .manual-page { position: absolute; inset: 0; width: 210mm !important; height: 297mm !important; transform: none !important; }
        .print-page .manual-page .page-inner { width: 100%; height: 100%; }
      </style>
    </head>
    <body>
      <div class="print-page">${el.outerHTML}</div>
      <script>
        window.addEventListener('load', () => { setTimeout(() => { window.focus(); window.print(); }, 50); });
        window.onafterprint = () => { setTimeout(() => { parent.document.body.removeChild(frameElement); }, 0); };
      <\/script>
    </body>
  </html>`
  doc.open()
  doc.write(html)
  doc.close()
}

// 记录初次渲染时各可编辑区域的原始 HTML
const _editableInitHTML = new WeakMap()
// 固定常量（不可编辑）
const BRAND_NAME = 'Bellagio\nSpas'
const PRODUCT_ANCHOR = { x: '75%', y: '32%' }
// 不同图片的上传提示（精简版）
const BACKGROUND_UPLOAD_TIPS = '背景图：≥2480×1400，≤5MB，横向大图即可。'
const PRODUCT_UPLOAD_TIPS = '产品图：≥1600×1200，≤5MB，建议 PNG/JPG。'
const FEATURE_ICON_UPLOAD_TIPS = 'Feature 图标：约 256×256，≤1MB，PNG/JPG。'
const LOGO_UPLOAD_TIPS = 'Logo：约 256×256，≤1MB，PNG/JPG（透明更佳）。'
// Identify the index of the first page containing a 'contents' block
const contentsIndex = computed(() => {
  const pages = manualPages.value || []
  return pages.findIndex(p => (p.blocks || []).some(b => b.type === 'contents'))
})
const isAfterContents = (pageIndex) => {
  const ci = contentsIndex.value
  return ci >= 0 && pageIndex > ci
}
const displayPageNum = (pageIndex) => {
  const ci = contentsIndex.value
  if (ci < 0) return ''
  return pageIndex - ci
}
const displayTocPage = (realPageNumber) => {
  const ci = contentsIndex.value
  if (ci < 0) return String(realPageNumber).padStart(2, '0')
  const idx = realPageNumber - 1
  if (idx <= ci) return ''
  return String(idx - ci).padStart(2, '0')
}

// 可替换的图片资源
const productPhotoSrc = ref('/back/product.png')
const backgroundSrc = ref('/back/back.png')
const productPhotoScale = ref(1)
const productPhotoRotate = ref(0)
// 产品图片锚点（固定值）
const productAnchor = ref({ ...PRODUCT_ANCHOR })
const _productDragState = reactive({
  active: false,
  moved: false,
  startX: 0,
  startY: 0,
  startedAt: 0,
})
const productInputRef = ref(null)
const backgroundInputRef = ref(null)

const productDialogVisible = ref(false)
const productDialogTab = ref('local')
const kbProductImages = ref([])

const onClickProduct = () => {
  productDialogTab.value = 'local'
  refreshKbProductImages()
  productDialogVisible.value = true
}

const onProductPhotoClick = (e) => {
  // If a drag just happened, swallow the click so it won't open replace dialog.
  if (_productDragState.moved) {
    _productDragState.moved = false
    return
  }
  onClickProduct()
}

const clampNumber = (value, min, max) => Math.min(max, Math.max(min, value))

const _parsePercent = (value, fallback) => {
  const raw = String(value ?? '').trim()
  const n = Number(raw.replace('%', ''))
  return Number.isFinite(n) ? n : fallback
}

const _updateProductAnchorFromClient = (clientX, clientY) => {
  const el = promoRef.value
  if (!el || !el.getBoundingClientRect) return
  const rect = el.getBoundingClientRect()
  if (!rect.width || !rect.height) return

  const xPct = ((clientX - rect.left) / rect.width) * 100
  const yPct = ((clientY - rect.top) / rect.height) * 100

  const clampedX = clampNumber(xPct, -10, 110)
  const clampedY = clampNumber(yPct, -10, 110)
  productAnchor.value = {
    ...productAnchor.value,
    x: `${clampedX.toFixed(2)}%`,
    y: `${clampedY.toFixed(2)}%`,
  }
}

const _onProductPhotoMouseMove = (ev) => {
  if (!_productDragState.active) return
  if (!ev.altKey) {
    _productDragState.active = false
    return
  }
  const dx = ev.clientX - _productDragState.startX
  const dy = ev.clientY - _productDragState.startY
  if (!_productDragState.moved && Math.hypot(dx, dy) > 4) {
    _productDragState.moved = true
  }
  _updateProductAnchorFromClient(ev.clientX, ev.clientY)
}

const _endProductPhotoDrag = () => {
  if (!_productDragState.active) return
  _productDragState.active = false
  window.removeEventListener('mousemove', _onProductPhotoMouseMove)
  window.removeEventListener('mouseup', _endProductPhotoDrag)
}

const onProductPhotoMouseDown = (ev) => {
  // Only start dragging when holding Alt + left mouse.
  if (!ev || ev.button !== 0 || !ev.altKey) return
  ev.preventDefault()
  ev.stopPropagation()

  _productDragState.active = true
  _productDragState.moved = false
  _productDragState.startX = ev.clientX
  _productDragState.startY = ev.clientY
  _productDragState.startedAt = Date.now()

  // Immediate update so the image follows the cursor from the first move.
  _updateProductAnchorFromClient(ev.clientX, ev.clientY)

  window.addEventListener('mousemove', _onProductPhotoMouseMove)
  window.addEventListener('mouseup', _endProductPhotoDrag)
}

const incProductPhotoScale = () => {
  productPhotoScale.value = clampNumber(Number(productPhotoScale.value || 1) + 0.1, 0.2, 3)
}

const decProductPhotoScale = () => {
  productPhotoScale.value = clampNumber(Number(productPhotoScale.value || 1) - 0.1, 0.2, 3)
}

const rotateProductPhoto = (delta) => {
  productPhotoRotate.value = clampNumber(Number(productPhotoRotate.value || 0) + Number(delta || 0), -180, 180)
}

const resetProductPhotoTransform = () => {
  productPhotoScale.value = 1
  productPhotoRotate.value = 0
}

const triggerLocalProductUpload = () => {
  if (productInputRef.value) productInputRef.value.click()
}

const selectKbProductImage = (src) => {
  if (!src) return
  productPhotoSrc.value = src
  if (promoData.value?.images) promoData.value.images.product = src
  productDialogVisible.value = false
}

const onPickProduct = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    const result = reader.result
    if (!result) return
    productPhotoSrc.value = result
    if (promoData.value?.images) promoData.value.images.product = result
  }
  reader.readAsDataURL(f)
  try {
    e.target.value = ''
  } catch (err) {}
}

const onClickBackground = () => {
  if (backgroundInputRef.value) backgroundInputRef.value.click()
}

const onPickBackground = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    const result = reader.result
    if (!result) return
    backgroundSrc.value = result
    if (promoData.value?.images) promoData.value.images.background = result
  }
  reader.readAsDataURL(f)
  try {
    e.target.value = ''
  } catch (err) {}
}

// Feature 区图标（Capacity / Jets / Pumps / Measurements）可替换
const featureIcons = ref({
  capacity: '/product_standard/Capacity.png',
  jets: '/product_standard/Jets.png',
  pumps: '/product_standard/Pumps.png',
  measurements: '/product_standard/Measurements.png',
})

const featureIconInputRef = ref(null)
let _featureIconKey = ''

const pickFeatureIcon = (key) => {
  const ok = window.confirm('是否更换该 Feature 图标?')
  if (!ok) return
  _featureIconKey = key
  if (featureIconInputRef.value) featureIconInputRef.value.click()
}

const onPickFeatureIcon = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f || !_featureIconKey) return
  const reader = new FileReader()
  reader.onload = () => {
    featureIcons.value = {
      ...featureIcons.value,
      [_featureIconKey]: reader.result,
    }
  }
  reader.readAsDataURL(f)
  try { e.target.value = '' } catch (err) {}
}

// Feature 图标弹框状态与图标库
const featureIconDialogVisible = ref(false)
const featureIconDialogTab = ref('local')
const kbFeatureIcons = ref([
  { key: 'capacity-people', src: '/product_standard/Capacity.png', label: 'Capacity 默认' },
  { key: 'jets-default', src: '/product_standard/Jets.png', label: 'Jets 默认' },
  { key: 'pumps-default', src: '/product_standard/Pumps.png', label: 'Pumps 默认' },
  { key: 'measure-default', src: '/product_standard/Measurements.png', label: 'Measurements 默认' },
])

const openFeatureIconDialog = (key) => {
  _featureIconKey = key
  featureIconDialogTab.value = 'local'
  featureIconDialogVisible.value = true
}

const triggerLocalFeatureIconUpload = () => {
  if (!_featureIconKey) return
  if (featureIconInputRef.value) featureIconInputRef.value.click()
}

const selectKbFeatureIcon = (src) => {
  if (!src || !_featureIconKey) return
  featureIcons.value = {
    ...featureIcons.value,
    [_featureIconKey]: src,
  }
  featureIconDialogVisible.value = false
}

// 规格页JSON 驱动数据初始状态
// 数据格式说明：
// - productTitle: string
// - features: { capacity: string, jets: string, pumps: string }
// - measurements: string
// - premiumFeatures: string[]  // Premium Lighting System 列表
// - insulationFeatures: string[]  // Energy-Saving Insulation System 列表
// - extraFeatures: string[]  // Extra Features 列表
// - Specifications: [{ "Cabinet Color": string|string[] }, { "Shell Color": string|string[] }, { "Dry Weight": string }, { "Water Capacity": string }, { "Pump": string }, { "Controls": string }]
//   · Cabinet Color: 颜色值，支持 string 或 string[]；例如 "#c4c4c4" 或 ["#c4c4c4", "#666666"]
//   · Shell Color: 同上，颜色值 string 或 string[]
//   · 其余（Dry Weight/Water Capacity/Pump/Controls）为普通字符串
// - smartWater: string[]
// - images: { product: string, background: string }
const initialPromoData = {
  productTitle: 'Vastera',
  features: { capacity: '1', jets: '0', pumps: '2' },
  measurements: '70" × 33" × 37"',
  premiumFeatures: ['LED Jet Illumination', 'Underwater Mood Lighting', 'Perimeter & Valve Laser Lighting', 'Corner Laser Lighting', 'LED Glow Cupholders'],
  insulationFeatures: ['Polyfoam Insulation', 'Triple-Layered Side Insulation', 'Enviro-Seal Base'],
  extraFeatures: ['Bluetooth Audio System', 'Heater/Chiller Ready'],
  Specifications: [
    { 'Cabinet Color': ['#c4c4c4', '#666666'] },
    { 'Shell Color': '#c4c4c4' },
    { 'Dry Weight': '293 lbs' },
    { 'Water Capacity': '79 gallons' },
    { 'Pump': '1 x Chiller' },
    { 'Controls': 'Joyonway Touch Screen' },
  ],
  smartWater: ['Ozonator', 'Filtration System', 'Circulation Pump *'],
  images: { product: '/back/product.png', background: '/back/back.png' },
}

// 规格页JSON 驱动数据
const promoData = ref(JSON.parse(JSON.stringify(initialPromoData)))
// 记录后端首次返回的规格页数据快照（用于“重置内容”）
const specsheetInitialSnapshot = ref(null)

// 规格页二级标题，可编辑/可删除
const promoSectionTitles = ref({
  premium: 'Premium<br>Lighting System',
  insulation: 'Energy-Saving<br>Insulation System',
  extra: 'Extra Features',
  specifications: 'Specifications',
  smartWater: 'Smart Water<br>Purification System',
})

const onEditSectionTitle = (evt, key) => {
  const el = evt?.target
  if (!el) return
  const html = (el.innerHTML || '').trim()
  promoSectionTitles.value = {
    ...promoSectionTitles.value,
    [key]: html,
  }
}

// 打开 RAG 来源调试面板
const openRagChunksDialog = async () => {
  ragDialogVisible.value = true
  ragError.value = ''
  ragLoading.value = false
  if (manualSessionId.value) {
    await loadManualOcrData()
  }
}

function parseColorList(input) {
  if (Array.isArray(input)) return input.filter(Boolean);
  if (typeof input === 'string') {
    return input
      .split(/[;,,\s]+/)
      .map(s => s.trim())
      .filter(Boolean);
  }
  return [];
}

const specColorDialogVisible = ref(false)
const specColorSpecIndex = ref(-1)
const specColorDual = ref(false)
const specColor1 = ref('#c4c4c4')
const specColor2 = ref('#666666')
const specColorActive = ref(1)

const specColorDialogTitle = computed(() => {
  const idx = specColorSpecIndex.value
  if (idx !== 0 && idx !== 1) return '编辑颜色'
  const specObj = promoData.value?.Specifications?.[idx]
  const key = specObj ? Object.keys(specObj)[0] : ''
  return key ? `编辑 ${key}` : '编辑颜色'
})

const specColorPresets = [
  '#ffffff', '#f5f5f5', '#e5e7eb', '#cbd5e1', '#9ca3af',
  '#6b7280', '#4b5563', '#374151', '#111827', '#000000',
  '#d6d3d1', '#a8a29e', '#78716c', '#57534e', '#3f3f46',
  '#d1d5db', '#94a3b8', '#64748b', '#475569', '#0f172a',
]

const openSpecColorDialog = (idx) => {
  if (idx !== 0 && idx !== 1) return
  const specObj = promoData.value?.Specifications?.[idx]
  if (!specObj) return
  const val = Object.values(specObj)[0]
  const list = parseColorList(val)
  specColorSpecIndex.value = idx
  specColorDual.value = list.length >= 2
  specColor1.value = list[0] || '#c4c4c4'
  specColor2.value = list[1] || list[0] || '#666666'
  specColorActive.value = 1
  specColorDialogVisible.value = true
}

const applyPresetColor = (color) => {
  if (!color) return
  if (specColorDual.value && specColorActive.value === 2) {
    specColor2.value = color
  } else {
    specColor1.value = color
  }
}

const saveSpecColor = () => {
  const idx = specColorSpecIndex.value
  if (idx !== 0 && idx !== 1) return
  const specObj = promoData.value?.Specifications?.[idx]
  if (!specObj) return
  const key = Object.keys(specObj)[0]
  const c1 = String(specColor1.value || '').trim()
  const c2 = String(specColor2.value || '').trim()
  const value = specColorDual.value
    ? [c1 || '#c4c4c4', c2 || c1 || '#666666']
    : (c1 || '#c4c4c4')
  promoData.value.Specifications[idx] = { [key]: value }
  specColorDialogVisible.value = false
}

const onListItemKeydown = (evt, path, index) => {
  if (!evt || !path) return
  if (evt.key === 'Enter') {
    evt.preventDefault()
    const segs = String(path).split('.')
    let obj = promoData.value
    for (let i = 0; i < segs.length - 1; i++) {
      const k = segs[i]
      if (!(k in obj)) obj[k] = {}
      obj = obj[k]
    }
    const key = segs[segs.length - 1]
    if (Array.isArray(obj[key])) {
      obj[key].splice(index + 1, 0, '')
      nextTick(() => {
        const li = evt.target?.closest?.('li')
        if (li && li.nextElementSibling) {
          const span = li.nextElementSibling.querySelector('[contenteditable]')
          if (span) {
            span.focus()
            try {
              const range = document.createRange()
              const sel = window.getSelection()
              if (span.firstChild) {
                range.setStart(span.firstChild, 0)
                range.collapse(true)
                sel.removeAllRanges()
                sel.addRange(range)
              }
            } catch (e) {}
          }
        }
      })
    }
  } else if (evt.key === 'Backspace' || evt.key === 'Delete') {
    const el = evt.target
    const text = el?.innerText || ''
    if (text.trim() === '') {
      const segs = String(path).split('.')
      let obj = promoData.value
      for (let i = 0; i < segs.length - 1; i++) {
        const k = segs[i]
        if (!(k in obj)) return
        obj = obj[k]
      }
      const key = segs[segs.length - 1]
      if (Array.isArray(obj[key]) && obj[key].length > 1) {
        evt.preventDefault()
        obj[key].splice(index, 1)
        nextTick(() => {
          const li = evt.target?.closest?.('li')
          const target = li?.previousElementSibling || li?.nextElementSibling
          if (target) {
            const span = target.querySelector('[contenteditable]')
            if (span) {
              span.focus()
              try {
                const range = document.createRange()
                const sel = window.getSelection()
                const lastNode = span.lastChild || span
                const offset = lastNode.nodeType === Node.TEXT_NODE ? lastNode.textContent.length : 0
                range.setStart(lastNode, offset)
                range.collapse(true)
                sel.removeAllRanges()
                sel.addRange(range)
              } catch (e) {}
            }
          }
        })
      }
    }
  }
}

const onEditTextWithCaret = (evt, path) => {
  const el = evt?.target
  if (!el || !path) return
  const selection = window.getSelection()
  let caretOffset = 0
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(el)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    caretOffset = preCaretRange.toString().length
  }
  const val = el.innerText ?? ''
  const segs = String(path).split('.')
  let obj = promoData.value
  for (let i = 0; i < segs.length - 1; i++) {
    const k = segs[i]
    if (!(k in obj) || typeof obj[k] !== 'object') obj[k] = {}
    obj = obj[k]
  }
  obj[segs[segs.length - 1]] = val
  nextTick(() => {
    if (!el || !el.firstChild) return
    try {
      const range = document.createRange()
      const sel = window.getSelection()
      let charCount = 0
      let found = false
      const walk = (node) => {
        if (found) return
        if (node.nodeType === Node.TEXT_NODE) {
          const len = node.textContent.length
          if (charCount + len >= caretOffset) {
            range.setStart(node, Math.min(caretOffset - charCount, len))
            range.collapse(true)
            found = true
          } else {
            charCount += len
          }
        } else {
          for (let i = 0; i < node.childNodes.length; i++) {
            walk(node.childNodes[i])
          }
        }
      }
      walk(el)
      if (found) {
        sel.removeAllRanges()
        sel.addRange(range)
      }
    } catch (e) {
      // ignore caret restore errors
    }
  })
}

// 编辑规格项的函数（带光标位置保持）
const onEditSpecification = (evt, idx) => {
  const el = evt?.target
  if (!el) return

  // 记录当前光标在该元素内的字符偏移
  const selection = window.getSelection()
  let caretOffset = 0
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(el)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    caretOffset = preCaretRange.toString().length
  }

  // 更新规格数据
  const val = el.innerText ?? ''
  const specKey = Object.keys(promoData.value.Specifications[idx] || {})[0]
  if (specKey) {
    promoData.value.Specifications[idx] = { [specKey]: val }
  }

  // 下一帧恢复光标位置
  nextTick(() => {
    if (!el) return
    try {
      const range = document.createRange()
      const sel = window.getSelection()
      let charCount = 0
      let found = false
      const walk = (node) => {
        if (found) return
        if (node.nodeType === Node.TEXT_NODE) {
          const len = node.textContent.length
          if (charCount + len >= caretOffset) {
            range.setStart(node, Math.min(caretOffset - charCount, len))
            range.collapse(true)
            found = true
          } else {
            charCount += len
          }
        } else {
          for (let i = 0; i < node.childNodes.length; i++) {
            walk(node.childNodes[i])
          }
        }
      }
      walk(el)
      if (found && sel) {
        sel.removeAllRanges()
        sel.addRange(range)
      }
    } catch (e) {
      // ignore caret restore errors
    }
  })
}

// 规格页加载状态
const loadingSpecsheet = ref(false)
const specsheetProgress = ref(0)
const specsheetProgressStatus = ref('')
const specsheetLoadingText = ref('')
const specsheetError = ref('')

// 说明书加载状态
const loadingManualBook = ref(false)
const manualBookProgress = ref(0)
const manualBookLoadingText = ref('')
const manualBookError = ref('')

// RAG 调试：规格页相关 chunks
const ragDialogVisible = ref(false)
const ragChunks = ref([])
const ragLoading = ref(false)
const ragError = ref('')
const selectedRagIndex = ref(0)
const manualOcrLoading = ref(false)
const manualOcrError = ref('')
const manualOcrLoaded = ref(false)
const manualOcrProductGroups = ref([])
const manualOcrAccessoryGroups = ref([])
const selectedRagChunk = computed(() => {
  const list = ragChunks.value || []
  if (!list.length) return null
  const idx = Math.min(Math.max(selectedRagIndex.value, 0), list.length - 1)
  return list[idx]
})

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
  collectImageEntriesFromGroups(manualStore.accessoryOcrGroups || [], images, seen)
  collectImageEntriesFromGroups(manualOcrProductGroups.value || [], images, seen)
  collectImageEntriesFromGroups(manualOcrAccessoryGroups.value || [], images, seen)

  ;(manualStore.productOcrFiles || []).forEach((file) => {
    if (!isImageLike(file)) return
    const src = file.url || toPublicFileUrl(file.path)
    if (!src || seen.has(src)) return
    images.push({ src, label: file.name || file.path || 'OCR 图片' })
    seen.add(src)
  })

  ;(manualStore.accessoryOcrFiles || []).forEach((file) => {
    if (!isImageLike(file)) return
    const src = file.url || toPublicFileUrl(file.path)
    if (!src || seen.has(src)) return
    images.push({ src, label: file.name || file.path || 'OCR 图片' })
    seen.add(src)
  })

  ;(ragChunks.value || []).forEach((chunk) => {
    const path = (chunk?.source_path || '').trim()
    if (!path) return
    const lower = path.toLowerCase()
    if (!IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext))) return
    const src = toPublicFileUrl(path)
    if (!src || seen.has(src)) return
    images.push({ src, label: path })
    seen.add(src)
  })

  return images
})

const normalizeOcrGroups = (groups = []) => {
  if (!Array.isArray(groups)) return []
  return groups.map((group, index) => ({
    id: `${group?.source_name || 'group'}-${index}`,
    sourceName: group?.source_name || '未命名文件',
    sourceMime: group?.source_mime || 'application/octet-stream',
    sourceSize: group?.source_size || 0,
    pages: Array.isArray(group?.pages)
      ? group.pages.map((page, pageIdx) => ({
          id: `${group?.source_name || 'group'}-${pageIdx}`,
          pageNumber: page?.page_number,
          artifacts: Array.isArray(page?.artifacts) ? page.artifacts : [],
        }))
      : [],
  }))
}

const countGroupArtifacts = (groups = []) => {
  return groups.reduce((sum, group) => {
    return (
      sum +
      group.pages.reduce((pageTotal, page) => pageTotal + (page.artifacts?.length || 0), 0)
    )
  }, 0)
}

const resetManualOcrState = () => {
  manualOcrLoaded.value = false
  manualOcrError.value = ''
  manualOcrProductGroups.value = []
  manualOcrAccessoryGroups.value = []
}

watch(manualSessionId, () => {
  resetManualOcrState()
})

const loadManualOcrData = async () => {
  if (!manualSessionId.value || manualOcrLoaded.value || manualOcrLoading.value) return
  manualOcrLoading.value = true
  manualOcrError.value = ''
  try {
    const { getManualSession } = await import('@/services/api')
    const session = await getManualSession(manualSessionId.value)
    manualOcrProductGroups.value = normalizeOcrGroups(session?.product_ocr_groups)
    manualOcrAccessoryGroups.value = normalizeOcrGroups(session?.accessory_ocr_groups)
    manualOcrLoaded.value = true
  } catch (error) {
    manualOcrError.value = error?.message || '加载 OCR 数据失败'
  } finally {
    manualOcrLoading.value = false
  }
}

const formatSize = (size = 0) => {
  if (!size) return '未知大小'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let val = size
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx++
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`
}

const hydratePromoFromSpecsheet = (specsheetData, { fromSaved = false, chunks = [] } = {}) => {
  if (!specsheetData) return false

  promoData.value = JSON.parse(JSON.stringify(initialPromoData))
  promoData.value.productTitle = productName.value || specsheetData.productTitle || promoData.value.productTitle

  if (specsheetData.features) {
    promoData.value.features = { ...specsheetData.features }
  }
  if (specsheetData.measurements) {
    promoData.value.measurements = specsheetData.measurements
  }
  if (Array.isArray(specsheetData.premiumFeatures) && specsheetData.premiumFeatures.length > 0) {
    promoData.value.premiumFeatures = [...specsheetData.premiumFeatures]
  }
  if (Array.isArray(specsheetData.insulationFeatures) && specsheetData.insulationFeatures.length > 0) {
    promoData.value.insulationFeatures = [...specsheetData.insulationFeatures]
  }
  if (Array.isArray(specsheetData.extraFeatures) && specsheetData.extraFeatures.length > 0) {
    promoData.value.extraFeatures = [...specsheetData.extraFeatures]
  }
  if (Array.isArray(specsheetData.Specifications) && specsheetData.Specifications.length >= 6) {
    promoData.value.Specifications = specsheetData.Specifications.map((spec) => {
      if (typeof spec === 'object' && !Array.isArray(spec)) {
        return { ...spec }
      }
      return spec
    })
  }
  if (Array.isArray(specsheetData.smartWater) && specsheetData.smartWater.length > 0) {
    promoData.value.smartWater = [...specsheetData.smartWater]
  }
  if (specsheetData.images) {
    promoData.value.images = { ...specsheetData.images }
    if (specsheetData.images.product) {
      productPhotoSrc.value = specsheetData.images.product
    }
    if (specsheetData.images.background) {
      backgroundSrc.value = specsheetData.images.background
    }
  }

  ragChunks.value = fromSaved ? [] : chunks

  if (!specsheetInitialSnapshot.value) {
    specsheetInitialSnapshot.value = JSON.parse(JSON.stringify(promoData.value))
  }
  return true
}

const hydrateManualFromBook = (manualBook, pageIndex = null) => {
  if (!manualBook) return false
  const newPage = {
    header: manualBook.header || '说明书',
    blocks: Array.isArray(manualBook.blocks)
      ? manualBook.blocks.map((blk) => ({
          ...blk,
          type: blk.type,
        }))
      : [],
  }

  // 若指定 pageIndex，则仅替换该页；否则重建全部
  if (typeof pageIndex === 'number' && pageIndex >= 0 && pageIndex < manualPages.value.length) {
    const pages = [...manualPages.value]
    pages.splice(pageIndex, 1, newPage)
    manualPages.value = pages
    // 更新 TOC 中对应页标题（按 page 序号匹配）
    if (Array.isArray(manualMeta.value?.toc)) {
      manualMeta.value.toc = manualMeta.value.toc.map((item) =>
        item.page === pageIndex + 1 ? { ...item, title: newPage.header } : item
      )
    }
  } else {
    manualMeta.value = {
      title: newPage.header,
      toc: [{ title: newPage.header, page: 1 }],
      footer: manualMeta.value?.footer || { left: '© 2025', right: '' },
    }
    manualPages.value = [newPage]
    currentPageIndex.value = 0
  }
  return true
}

const loadSpecsheetData = async () => {
  if (manualSessionId.value && !sessionDocumentsLoaded.value && !sessionDocumentsLoading.value) {
    await loadSessionDocuments()
  }

  const documents = getCurrentOcrDocuments()
  if (!documents.length) {
    specsheetError.value = '请先上传或传入 OCR 结果后再生成规格页'
    return
  }

  if (!bomCode.value) {
    specsheetError.value = '当前产品缺少 BOM 号，无法生成规格页'
    return
  }
  
  loadingSpecsheet.value = true
  specsheetProgress.value = 0
  specsheetProgressStatus.value = ''
  specsheetLoadingText.value = '正在连接后端服务...'
  specsheetError.value = ''

  let payload = null
  try {
    const { generateSpecsheetFromOcr } = await import('@/services/api')

    let specsheetData = null
    let chunks = []
    let progressInterval = null

    const startProgressInterval = () => {
      if (progressInterval) return
      progressInterval = setInterval(() => {
        if (specsheetProgress.value < 90) {
          specsheetProgress.value += 10
          if (specsheetProgress.value === 20) {
            specsheetLoadingText.value = '正在查询产品信息...'
          } else if (specsheetProgress.value === 40) {
            specsheetLoadingText.value = '正在检索相关文档...'
          } else if (specsheetProgress.value === 60) {
            specsheetLoadingText.value = '正在提取规格页内容...'
          } else if (specsheetProgress.value === 80) {
            specsheetLoadingText.value = '正在验证数据格式...'
          }
        }
      }, 200)
    }

    const clearProgressInterval = () => {
      if (progressInterval) {
        clearInterval(progressInterval)
        progressInterval = null
      }
    }

    startProgressInterval()
    specsheetProgress.value = 30
    specsheetLoadingText.value = '正在汇总 OCR 文档…'

    payload = {
      documents,
      session_id: manualSessionId.value || undefined,
      bom_code: bomCode.value,
      bom_type: manualBomType.value || undefined,
      product_name: productName.value || name.value || ''
    }
    const result = await generateSpecsheetFromOcr(payload)
    const dialogPayload = {
      request: {
        documents: sanitizeRequestDocuments(documents),
        bom_code: payload.bom_code,
        bom_type: payload.bom_type,
        session_id: payload.session_id,
        product_name: payload.product_name
      },
      response: {
        ...sanitizeSpecsheetResult(result),
        prompt_text: result?.prompt_text || '',
        system_prompt: result?.system_prompt || ''
      },
    }
    specsheetResultPayload.value = JSON.stringify(dialogPayload, null, 2)
    // 关闭弹窗
    // specsheetResultDialogVisible.value = !!showSpecsheetResultDialogOnGenerate.value
    // 打开弹窗
    specsheetResultDialogVisible.value = true
    specsheetData = result?.specsheet || null
    chunks = Array.isArray(result?.chunks) ? result.chunks : []

    clearProgressInterval()
    specsheetProgress.value = 90
    specsheetLoadingText.value = '正在处理数据...'
    
    const hydrated = hydratePromoFromSpecsheet(specsheetData, { chunks })

    if (hydrated) {
      specsheetProgress.value = 100
      specsheetProgressStatus.value = 'success'
      specsheetLoadingText.value = '加载完成！'
      
      // 延迟隐藏进度条
      setTimeout(() => {
        loadingSpecsheet.value = false
      }, 1000)
    } else {
      throw new Error('未获取到规格页数据')
    }
  } catch (error) {
    console.error('Failed to load specsheet data:', error)
    try {
      const dialogPayload = {
        request: {
          documents: sanitizeRequestDocuments(documents),
          bom_code: payload?.bom_code || bomCode.value,
          bom_type: payload?.bom_type || manualBomType.value || undefined,
          session_id: payload?.session_id || manualSessionId.value || undefined,
          product_name: payload?.product_name || productName.value || name.value || ''
        },
        response: {
          error_message: error?.message || '未知错误',
          error_stack: error?.stack || ''
        }
      }
      specsheetResultPayload.value = JSON.stringify(dialogPayload, null, 2)
      specsheetResultDialogVisible.value = true
    } catch (e) {
      // ignore dialog payload errors
    }
    specsheetProgress.value = 100
    specsheetProgressStatus.value = 'exception'
    specsheetError.value = `加载失败: ${error.message || '未知错误'}`
    loadingSpecsheet.value = false
    // Continue with default data if API call fails
  }
}

const buildSpecsheetPayload = () => ({
    productTitle: promoData.value.productTitle,
    features: { ...promoData.value.features },
    measurements: promoData.value.measurements,
    premiumFeatures: [...(promoData.value.premiumFeatures || [])],
    insulationFeatures: [...(promoData.value.insulationFeatures || [])],
    extraFeatures: [...(promoData.value.extraFeatures || [])],
    Specifications: promoData.value.Specifications.map((spec) => ({ ...spec })),
    smartWater: [...(promoData.value.smartWater || [])],
    images: { ...promoData.value.images }
})

const saveSpecsheetToDb = async () => {
  const payload = buildSpecsheetPayload()
  try {
    if (!productName.value || !bomCode.value) {
      ElMessage.warning('缺少 产品名称 或 BOM，无法保存')
      return
    }
    await saveManualSpecsheetTruth(productName.value, bomCode.value, payload)
    savedManualSpecsheetLoadedKey.value = ''
    autoSpecsheetLoadedKey.value = ''
    ElMessage.success('规格页已保存至数据库')
    specsheetInitialSnapshot.value = JSON.parse(JSON.stringify(promoData.value))
  } catch (error) {
    console.error('Failed to save specsheet:', error)
    ElMessage.error(error?.message || '保存规格页失败，请稍后重试')
  }
}

const runningSpecsheetAce = ref(false)

const handleRunSpecsheetAce = async () => {
  if (runningSpecsheetAce.value) return
  if (!manualSessionId.value) {
    ElMessage.warning('仅支持在手动 OCR 会话下触发 ACE 学习')
    return
  }

  const payload = buildSpecsheetPayload()
  runningSpecsheetAce.value = true
  try {
    await saveManualSpecsheet(manualSessionId.value, payload, bomCode.value)
    const result = await runManualSpecsheetAce(manualSessionId.value, null, bomCode.value)
    ElMessage.success(`ACE 训练完成，当前策略条数：${result?.playbook_size ?? '未知'}`)
  } catch (error) {
    console.error('Failed to trigger specsheet ACE:', error)
    ElMessage.error(error?.message || '触发 ACE 学习失败，请稍后重试')
  } finally {
    runningSpecsheetAce.value = false
  }
}

const tryPrefillSpecsheetFromSaved = async () => {
  if (autoSpecsheetLoading.value) return
  const comboKey = `${manualSessionId.value || 'no-session'}::${productName.value || ''}::${bomCode.value || ''}`
  if (autoSpecsheetLoadedKey.value === comboKey) return
  autoSpecsheetLoading.value = true
  try {
    let specsheet = null
    if (productName.value && bomCode.value) {
      const key = `${productName.value}__${bomCode.value}`
      if (savedManualSpecsheetLoadedKey.value !== key && !savedManualSpecsheetLoading.value) {
        savedManualSpecsheetLoading.value = true
        try {
          specsheet = await getSavedManualSpecsheet(productName.value, bomCode.value)
          savedManualSpecsheetLoadedKey.value = key
        } catch (error) {
          console.warn('Failed to load saved manual specsheet:', error)
        } finally {
          savedManualSpecsheetLoading.value = false
        }
      }
    }
    if (specsheet) {
      const hydrated = hydratePromoFromSpecsheet(specsheet, { fromSaved: true })
      if (hydrated) {
        autoSpecsheetLoadedKey.value = comboKey
        specsheetError.value = ''
        loadingSpecsheet.value = false
      }
    } else {
      // 未找到保存文件：保留默认内容即可
      autoSpecsheetLoadedKey.value = comboKey
    }
  } catch (error) {
    console.warn('自动加载规格页失败，将保留默认内容', error)
  } finally {
    autoSpecsheetLoading.value = false
  }
}

watch(
  () => [manualSessionId.value, productName.value, bomCode.value],
  () => {
    tryPrefillSpecsheetFromSaved()
  },
  { immediate: true }
)

const savePosterToDb = async () => {}

const saveManualToDb = async () => {
  try {
    if (!productName.value || !bomCode.value) {
      ElMessage.warning('缺少 产品名称 或 BOM，无法保存')
      return
    }
    const pages = Array.isArray(manualPages.value)
      ? manualPages.value.map((p) => ({ header: p.header, blocks: p.blocks }))
      : []
    await saveManualBookTruth(productName.value, bomCode.value, pages)
    savedManualBookLoadedKey.value = ''
    ElMessage.success('说明书已保存至 truth 文件')
  } catch (error) {
    console.error('Failed to save manual book:', error)
    ElMessage.error(error?.message || '保存说明书失败，请稍后重试')
  }
}

// 初始化图片与 promoData 同步（暂不自动触发规格页加载）
onMounted(() => {
  productPhotoSrc.value = promoData.value.images?.product || productPhotoSrc.value
  backgroundSrc.value = promoData.value.images?.background || backgroundSrc.value
})

// 后续如需在切换产品时联动加载规格页，可在此重新启用 watch
// watch([productName, bom], ([newProductName, newBom], [oldProductName, oldBom]) => {
//   if ((newProductName !== oldProductName || newBom !== oldBom) && newProductName && newBom) {
//     loadSpecsheetData()
//   }
// }, { immediate: false })
// 说明书数据与辅助函数 Json 驱动
/*
 JSON 格式说明:
 - root.title: string 手册标题
 - root.toc: 数组，目录项 { title, page, children? }
   - children: 可选 [{ title, page }]
 - root.pages: 数组，每页 { number, customTitle?, blocks }
 - blocks: 根据 type 不同有不同字段
   - type: 'cover'
     - title: string
     - sizeText: string
     - model?: string
     - backSrc?: string 背景图片
     - productSrc?: string 产品图片
     - 注意: logo 与版本号为固定渲染（logo: '/instruction_book/logo.svg'，版本: 'vers. 202409'），非 JSON 传入
   - type: 'heading' { level: 1|2|3, text, anchor? }
   - type: 'paragraph' { text, className? }
   - type: 'list' { ordered: boolean, items: string[], className? }
   - type: 'image' { src, alt?, width?, height?, fullWidth?, marginTop?, marginBottom?, caption? }
   - type: 'imageFloat' { src, alt?, position: 'bottom-left'|'bottom-right'|'top-left'|'top-right', width? }
   - type: 'table' { headers?: string[], rows: string[][] }
   - type: 'grid4' { items: [{ index?, title, imgSrc? }] }
   - type: 'grid2' { items: [{ type: 'image'|'list', src?, alt?, ordered?, items? }] }
   - type: 'spec-box' { imageSrc, specs: { ...分区: title 与 items[] } }
*/
const manualMeta = ref({
  title: 'Vastera 使用说明书',
  toc: [
    { title: 'Cover', page: 1 },
    { title: 'Embrace the Revitalizing Chill', page: 2 },
    { title: 'Premium Materials', page: 3 },
    { title: 'Contents', page: 4 },
    { title: 'Installation & User Manual', page: 5 },
    { title: 'How To Set Up', page: 6 },
    { title: 'Important Safety Instructions', page: 7 },
    { title: 'Important Safety Instructions', page: 8 },
    { title: 'Specification', page: 9 },
    { title: 'Touchscreen Control Panel', page: 10 },
    { title: 'Troubleshooting', page: 11 },
    { title: 'Troubleshooting', page: 12 },
    { title: 'Troubleshooting', page: 13 }
  ],
  footer: { left: '© 2025 Bellagio Spas', right: '文档版本 1.0.0' }
})
const manualPages = ref([
    {
      header: 'Cover',
      blocks: [
        { type: 'cover', title: 'VINTERKÖLD', sizeText: '85” x 85” x 39”', backSrc: '/instruction_book/back.jpg', productSrc: '/instruction_book/product.png' }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 一级标题
      //   · { type: 'paragraph', text } 段落
      //   · { type: 'list', items: string[] } 列表（items 可含基础 HTML）
      //   · { type: 'imageFloat-<pos>', src } 浮动图，pos=bottom-left|bottom-right|top-left|top-right
      //
      // 页面 JSON 格式说明：
      // - header: 页面标题
      // - blocks: 页面内容块数组
      //   · type: 内容块类型
      //     - heading: 一级标题
      //       · text: 标题文本
      //     - paragraph: 段落
      //       · text: 段落文本
      //     - list: 列表
      //       · items: 列表项数组（可含基础 HTML）
      //     - imageFloat-<pos>: 浮动图
      //       · src: 图片 URL
      //       · pos: 位置（bottom-left|bottom-right|top-left|top-right）
      header: 'Embrace the Revitalizing Chill',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Embrace the Revitalizing Chill' },
        { type: 'paragraph', text: 'Experience the invigorating benefits of cold therapy through our innovative Masren product. Cold therapy, also known as cryotherapy, involves subjecting the body to cold temperatures for therapeutic purposes. With its age-old roots and modern applications, this practice offers diverse and remarkable benefits for your well-being:' },
        { type: 'list', items: [
          'Reduced Inflammation:Cold therapy is a natural anti-inflammatory. It helps to constrict blood vessels, reducing blood flow to inflamed areas and thereby alleviating swelling and pain. Whether you\'re recovering from an intense workout or seeking relief from sore muscles, our Masren can provide the cool comfort your body craves.',
          'Faster Recovery: Athletes and fitness enthusiasts often turn to cold therapy to accelerate recovery times. The controlled exposure to cold temperatures promotes quicker muscle repair, reduces muscle soreness, and aids in preventing overexertion.',
          'Increased Circulation: Paradoxically, cold therapy can lead to improved circulation. As the body responds to cold, it works to keep vital organs warm by increasing blood flow to the core. Once you exit the cold environment, this increased blood flow returns to the extremities, promoting better overall circulation.',
          'Enhanced Mental Well-being: Cold therapy is not just about physical benefits; it can positively impact your mental state too. The shock of cold triggers the release of endorphins, which are natural mood lifters. Many people find that cold therapy leaves them feeling refreshed, invigorated, and more mentally focused.',
          'Boosted Immune System: Regular exposure to cold temperatures has been associated with improvements in the immune system. It stimulates the production of immune cells and activates the body\'s natural defense mechanisms, helping you stay resilient against illness.'
        ] },
        { type: 'paragraph', text: 'With a Masren, you can integrate the power of cold therapy seamlessly into your routine. Whether you\'re looking to enhance your recovery, reduce inflammation, or simply invigorate your senses, the Masren offers a convenient and effective solution.' },
        { type: 'paragraph', text: 'Embrace the chill and unlock a new realm of well-being today.' },
        { type: 'imageFloat-bottom-left', src: '/instruction_book/product.png' },
        { type: 'imageFloat-bottom-right', src: '/instruction_book/cold.png' }
      ]
    },
    {
      header: 'Embrace the Revitalizing Chill',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Embrace the Revitalizing Chill' },
        { type: 'paragraph', text: 'Experience the invigorating benefits of cold therapy through our innovative Masren product. Cold therapy, also known as cryotherapy, involves subjecting the body to cold temperatures for therapeutic purposes. With its age-old roots and modern applications, this practice offers diverse and remarkable benefits for your well-being:' },
        { type: 'list', items: [
          'Reduced Inflammation:Cold therapy is a natural anti-inflammatory. It helps to constrict blood vessels, reducing blood flow to inflamed areas and thereby alleviating swelling and pain. Whether you\'re recovering from an intense workout or seeking relief from sore muscles, our Masren can provide the cool comfort your body craves.',
          'Faster Recovery: Athletes and fitness enthusiasts often turn to cold therapy to accelerate recovery times. The controlled exposure to cold temperatures promotes quicker muscle repair, reduces muscle soreness, and aids in preventing overexertion.',
          'Increased Circulation: Paradoxically, cold therapy can lead to improved circulation. As the body responds to cold, it works to keep vital organs warm by increasing blood flow to the core. Once you exit the cold environment, this increased blood flow returns to the extremities, promoting better overall circulation.',
          'Enhanced Mental Well-being: Cold therapy is not just about physical benefits; it can positively impact your mental state too. The shock of cold triggers the release of endorphins, which are natural mood lifters. Many people find that cold therapy leaves them feeling refreshed, invigorated, and more mentally focused.',
          'Boosted Immune System: Regular exposure to cold temperatures has been associated with improvements in the immune system. It stimulates the production of immune cells and activates the body\'s natural defense mechanisms, helping you stay resilient against illness.'
        ] },
        { type: 'paragraph', text: 'With a Masren, you can integrate the power of cold therapy seamlessly into your routine. Whether you\'re looking to enhance your recovery, reduce inflammation, or simply invigorate your senses, the Masren offers a convenient and effective solution.' },
        { type: 'paragraph', text: 'Embrace the chill and unlock a new realm of well-being today.' },
        { type: 'imageFloat-bottom-left', src: '/instruction_book/product.png' },
        { type: 'imageFloat-bottom-right', src: '/instruction_book/cold.png' }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'paragraph', text } 简述
      //   · { type: 'grid4', items } 四宫格
      //       items: [{ index?: number 手动序号, title: string 标题, imgSrc?: string 图片 }]
      header: 'Premium Materials',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Premium Materials' },
        { type: 'paragraph', text: 'Embrace the chill and rejuvenate your body and mind with our product, showcasing an Acrylic Surface for aesthetics, an AluCombo Cabinet for efficient cooling, an aluminum frame for durability, and an insulated pipe sleeve to prevent condensation. Perfect for year-round outdoor use, energy-efficient, and reliable. Enjoy hassle-free cooling without water-related concerns.' },
        { type: 'grid4', items: [
          { index: 1, title: 'Acrylic Surface', imgSrc: '/instruction_book/Acrylic_Surface.png' },
          { index: 2, title: 'Aluminum Frame', imgSrc: '/instruction_book/Acrylic_Surface.png' },
          { index: 3, title: 'Tri-layered Side Cabinet', imgSrc: '/instruction_book/Acrylic_Surface.png' },
          { index: 4, title: 'Insulation Sleeve', imgSrc: '/instruction_book/Acrylic_Surface.png' }
        ] }
      ]
    },
    {
      header: 'Premium Materials',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Premium Materials' },
        { type: 'paragraph', text: 'Embrace the chill and rejuvenate your body and mind with our product, showcasing an Acrylic  Surface for aesthetics, and an insulated pipe sleeve to prevent condensation. Perfect for  year-round outdoor use, energy-efficient, and reliable. Enjoy hassle-free cooling without  water-related concerns.' },
        { type: 'grid4', items: [
          { index: 1, title: 'Acrylic Surface', imgSrc: '/instruction_book/Acrylic_Surface.png' },
          { index: 2, title: 'Aluminum Frame', imgSrc: '/instruction_book/Acrylic_Surface.png' },
          { index: 3, title: 'Tri-layered Side Cabinet', imgSrc: '/instruction_book/Acrylic_Surface.png' }
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'contents', items } 目录（实际由 getContentsFor 自动生成）
      //       items: 预置目录 [{ title: string, page: number }]（可作占位/示例）
      header: 'Contents',
      blocks: [
        { type: 'heading', text: 'Contents' },
        { type: 'contents', items: [
          { title: 'Installation & User Manual', page: 1 },
          { title: 'How to Set Up', page: 2 },
          { title: 'Important Safety Instructions', page: 3 },
          { title: 'Specification', page: 5 },
          { title: 'Touchscreen Control Panel', page: 6 },
          { title: 'Preparation for Your Masrren', page: 9 },
          { title: 'Exhaust Air and Replace Filter', page: 9 },
          { title: 'Drainage', page: 10 },
          { title: 'Normal Drainage', page: 11 },
          { title: 'Condensate Drainage', page: 12 },
          { title: 'Thermo Protection Activation', page: 14 },
          { title: 'Water on or Around the Control Screen', page: 15 },
          { title: 'Preparing for Your Masrren', page: 16 },
          { title: 'Remove and Install the Skirt', page: 16 },
          { title: 'Troubleshooting', page: 17 }
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'callout-warning' | 'callout-error', text, className? } 警示（text 支持 HTML）
      //   · { type: 'paragraph', text, className? } 说明
      //   · { type: 'list', items: string[], className? } 步骤/要点
      header: 'Installation & User Manual',
      blocks: [
        { type: 'heading', text: 'Installation & User Manual' },
        { type: 'callout-warning', text: 'Warning! Risk of fire, electric shock and water leakage.' },
        { type: 'callout-error', text: 'Your Vinterköld includes a detailed Installation & User Manual. Follow all instructions in the Installation & User Manual closely.' },
        { type: 'callout-warning', text: 'Warning! Improper installation, usage or maintenance can lead to loss of warranty, injury or property damage. Spa tub should be installed in accordance with BCA and local regulatory standards by qualified persons only. An isolation switch is recommended. Electrical installation must comply with AS:3000–Electrical Wiring Rules.' },
        { type: 'callout-warning', text: 'Warning! Ensure there is at least 150mm of clearance around the air inlet and outlet.' },
        { type: 'callout-warning', text: 'Warning! Suitable for operation in ambient temperatures ranging from −5°C to 43°C.' },
        { type: 'callout-warning', text: 'Warning! During installation and transportation, the unit must not be placed on its side or upside down.' },
        { type: 'callout-warning', className: 'special-note', text: 'Special Note:' },
        { type: 'paragraph', className: 'callout-align', text: 'To ensure optimal performance of the equipment after each refilling, please follow these steps:' },
        { type: 'list', className: 'callout-align', items: [
          'Connect the power supply and activate the control panel to start the equipment.',
          'Allow the equipment to operate for 20–30 seconds. Then, bleed the filter for 20–40 seconds by opening the bleeder valve on one side of the filter cover (refer to the figure). When water flows out from the filter vent, tighten the filter approximately 5–10 seconds after water appears.',
          'Completing these steps will ensure the circulation pump operates at its peak performance.',
          'If the control panel indicates that the circulation pump is functioning normally but there is no water circulation in the pipeline, please repeat steps 1 and 2. (This is a rare occurrence)'
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'paragraph', text, className? } 引导说明
      //   · { type: 'steps', items: string[] } 步骤（自动编号）
      header: 'How To Set Up',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'How To Set Up' },
        { type: 'paragraph', className: 'lead', text: "If you're excited to reap the benefits of your Masrren, start by following these simple guidelines to embark on your journey." },
        { type: 'paragraph', text: 'We understand your enthusiasm, but we strongly recommend reading the entire instruction manual, paying special attention to the safety information, before beginning your cold therapy sessions with the Masrren. Your safety and maximum enjoyment are our top priorities.' },
        { type: 'steps', items: [
          'Place your Masrren in a suitable location and fill it with water to tub until the water level reaches the recommended mark as specified.',
          'Open the air bleed screw to exhaust air from the filter and pump housing for cold zone. See page 9 for more details.',
          'Plug the dual-temp tub into a 110V/60Hz power source and set the desired temperature using the control panel.',
          'Within a few hours, you can enjoy the refreshing experience of cold water therapy.',
          'We highly recommend regularly cleaning and sanitizing.'
        ] }
      ]
    },
    {
      header: 'How To Set Up',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'How To Set Up' },
        { type: 'paragraph', className: 'lead', text: "If you're excited to reap the benefits of your Masrren, start by following these simple guidelines to embark on your journey." },
        { type: 'paragraph', text: 'We understand your enthusiasm, but we strongly recommend reading the entire instruction manual, paying special attention to the safety information, before beginning your cold therapy sessions with the Masrren. Your safety and maximum enjoyment are our top priorities.' },
        { type: 'steps', items: [
          'Place your Masrren in a suitable location and fill it with water to tub until the water level reaches the recommended mark as specified.',
          'Open the air bleed screw to exhaust air from the filter and pump housing.',
          'Plug the cold tub into a 120V / 60Hz power source and set the desired temperature using the control panel.',
          'Within a few hours, you can enjoy the refreshing experience of cold water therapy.',
          'We highly recommend regularly cleaning and sanitizing.'
        ] }
      ]
    },
    {
      header: 'How To Set Up',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'How To Set Up' },
        { type: 'heading', level: 2, text: 'Pre-Delivery Checklist' },
        { type: 'paragraph', text: 'Most cities and counties require permits for exterior construction and electrical circuits. In addition, some communities have codes requiring residential barriers such as fencing and/or self-closing gates on property to prevent unsupervised access to the property by children. Your dealer can provide information on which permits may be required and how to obtain them prior to the delivery of your spa.' },
        { type: 'heading', level: 2, text: 'Before Delivery' },
        { type: 'list', items: [
          'Plan your delivery route',
          'Choose a suitable location for the spa',
          'Lay a 5 - 8 cm concrete slab',
          'Install dedicated electrical supply'
        ] },
        { type: 'heading', level: 2, text: 'After Delivery' },
        { type: 'list', items: [
          'Place spa on slab',
          'Connect electrical components',
          '* Check spa and register serial number.'
        ] },
        { type: 'image', src: '/instruction_book/package_list.png' }
      ]
    },
    {
      header: 'How To Set Up',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'How To Set Up' },
        { type: 'heading', level: 2, text: 'Planning the Best Location' },
        { type: 'paragraph', text: 'Safety First' },
        { type: 'paragraph', text: 'Do not place your spa within 10 feet (3 m) of overhead power lines.' },
        { type: 'heading', level: 2, text: 'Consider How You Will Use Your Spa' },
        { type: 'paragraph', text: 'How you intend to use your spa will help you determine where you should position it. For example, will you use your spa for recreational or therapeutic purposes? If your spa is mainly used for family recreation, be sure to leave plenty of room around it for activity. If you will use it for relaxation and therapy, you will probably want to create a specific mood around it.' },
        { type: 'heading', level: 2, text: 'Plan for Your Environment' },
        { type: 'paragraph', text: 'If you live in a region where it snows in the winter or rains frequently, place the spa near a house entry. By doing this, you will have a place to change clothes and not be uncomfortable.' },
        { type: 'heading', level: 2, text: 'Consider Your Privacy' },
        { type: 'paragraph', text: "In a cold-weather climate, bare trees won't provide much privacy. Think of your spa's surroundings during all seasons to determine your best privacy options. Consider the view of your neighbors as well when you plan the location of your spa." },
        { type: 'heading', level: 2, text: 'Provide a View with Your Spa' },
        { type: 'paragraph', text: 'Think about the direction you will be facing when sitting in your spa. Do you have a special landscaped area in your yard that you find enjoyable? Perhaps there is an area that catches a soothing breeze during the day or a lovely sunset in the evening.' },
        { type: 'heading', level: 2, text: 'Keep Your Spa Clean' },
        { type: 'paragraph', text: "In planning your spa's location, consider a location where the path to and from the house can be kept clean and free of debris. Prevent dirt and contaminants from being tracked into your spa by placing a foot mat at the spa's entrance where the bathers can clean their feet before entering your spa." },
        { type: 'paragraph', className: 'warning-text', text: 'Guide to Transportation, Placement, and Installation of the Heat Pump:\nWhen transporting or storing the Heat Pump in temp mini, do not lay it on its side. It must be placed upright to prevent issues such as internal component compression, pipeline breakage, fin damage, and refrigerant leakage.\n\nAdditionally, after being transported to the factory or customer site, it should be kept idle for more than 24 hours before powering on or testing.\n\n* Suitable for products with a built-in temp.mini heat pump' },
        { type: 'image', src: '/instruction_book/package_list.png' }
      ]
    },
    {
      header: 'How To Set Up',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'How To Set Up' },
        { type: 'heading', level: 2, text: 'Clearance for Service Access' },
        { type: 'paragraph', text: 'While you are planning where to locate your spa, you need to determine how much access you will need for service.' },
        { type: 'paragraph', text: 'All spa models require a minimum of three feet / one meter access to all sides of the spa for potential service. For this reason, the spa should never be placed in a manner where any side is permanently blocked. Examples include placing the spa against a building, structural posts or columns, or a fence.' },
        { type: 'paragraph', text: 'Spa models require access to all sides in case they need service or repair. See the figure below.' },
        { type: 'paragraph', text: 'If you are planning to enclose or surround your spa with a deck, make sure there is easy access for service or repair.' },
        { type: 'paragraph', text: 'Spas require clearance on all sides of the spa.' },
        { type: 'image', src: '/instruction_book/package_list.png' }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'paragraph', text, className? } 提示
      //   · { type: 'list', items: string[] } 安全要点（items 可含 HTML，如 <br/>、<ul>）
      header: 'Important Safety Instructions',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'paragraph', className: 'lead', text: 'READ AND FOLLOW ALL INSTRUCTIONS' },
        { type: 'paragraph', text: 'Taking the plunge is a significant step, and we disclaim all liability for damages due to failure to follow the provided guidelines.' },
        { type: 'list', items: [
          'Health Disclaimer<br/>If unsure, consult your doctor before using the Masrren. While generally suitable for most individuals, those with reduced mobility or sensory/cognitive abilities should use the Masrren under supervision and only if knowledgeable about safe usage and potential risks.',
          'Temperature Awareness<br/>Start with a higher temperature (59°F / 15°C) and a shorter duration (1–2 minutes).',
          'Gradual Adaptation<br/>Tolerance to cold water varies. Gradually increase Masrren usage time. Sudden immersion can shock the body; enter slowly, keeping face, shoulders, and hands above water until breathing is steady.',
          'Cold Exposure Risks<br/>Cold shock response decreases with exposure experience. Hypothermia is a risk—it can lead to loss of consciousness and heart failure. Duration in cold water depends on factors like temperature, body size, and experience. Consult your doctor. Start with brief dips to find limits. Exit if uncomfortable.',
          'Safety Precautions<ul><li>Supervise children around the Masrren.</li><li>Pregnant women, children, and those with medical conditions must consult a doctor before using.</li><li>Avoid alcohol or drugs before use.</li><li>Do not use in extreme weather or flood conditions.</li><li>Ensure proper drainage to avoid water accumulation.</li></ul>',
          'Maintenance<ul><li>Be cautious when entering and exiting the Masrren.</li><li>Keep the inlet clean to protect the pump.</li><li>Avoid using electrical appliances nearby when empty.</li><li>Use only approved cleaning agents; rinse thoroughly.</li><li>Do not pressure wash the Masrren.</li><li>Keep the cover on to prevent injuries and water ingress.</li><li>For repairs, consult Masrren\'s approved engineers.</li></ul>',
          'Power Supply Safety<br/>Ensure the power supply is on an GFCI protected circuit for safety.'
        ] }
      ]
    },
    {
      header: 'Important Safety Instructions',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'paragraph', className: 'lead', text: 'READ AND FOLLOW ALL INSTRUCTIONS' },
        { type: 'paragraph', text: 'Taking the plunge is a significant step, and we disclaim all liability for damages due to failure to follow the provided guidelines.' },
        { type: 'list', items: [
          'Health Disclaimer<br/>If unsure, consult your doctor before using the Masrren. While generally suitable for most individuals, those with reduced mobility or sensory/cognitive abilities should use the Masrren under supervision and only if knowledgeable about safe usage and potential risks.',
          'Temperature Awareness<br/>Start with a higher temperature (59°F / 15°C) and a shorter duration (1–2 minutes).',
          'Gradual Adaptation<br/>Tolerance to cold water varies. Gradually increase Masrren usage time. Sudden immersion can shock the body; enter slowly, keeping face, shoulders, and hands above water until breathing is steady.',
          'Cold Exposure Risks<br/>Cold shock response decreases with exposure experience. Hypothermia is a risk—it can lead to loss of consciousness and heart failure. Duration in cold water depends on factors like temperature, body size, and experience. Consult your doctor. Start with brief dips to find limits. Exit if uncomfortable.',
          'Safety Precautions<ul><li>Supervise children around the Masrren.</li><li>Pregnant women, children, and those with medical conditions must consult a doctor before using.</li><li>Avoid alcohol or drugs before use.</li><li>Do not use in extreme weather or flood conditions.</li><li>Ensure proper drainage to avoid water accumulation.</li></ul>',
          'Maintenance<ul><li>Be cautious when entering and exiting the Masrren.</li><li>Keep the inlet clean to protect the pump.</li><li>Avoid using electrical appliances nearby when empty.</li><li>Use only approved cleaning agents; rinse thoroughly.</li><li>Do not pressure wash the Masrren.</li><li>Keep the cover on to prevent injuries and water ingress.</li><li>For repairs, consult Masrren\'s approved engineers.</li></ul>',
          'Power Supply Safety<br/>Ensure the power supply is on an GFCI protected circuit for safety.'
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'heading', level: 2, text } 分组标题（WARNING/CAUTION）
      //   · { type: 'list', items: string[] } 分组要点
      //   · { type: 'paragraph', text, className? } 警示说明
      //   · { type: 'divider' } 分割线
      //   · { type: 'image', src, fullWidth?, rotate?, marginTop? } 插图
      header: 'Important Safety Instructions',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'heading', level: 2, text: 'WARNING:' },
        { type: 'list', items: [
          'People with infectious diseases should not use a spa or hot tub.',
          'To avoid injury, exercise care when entering or exiting the spa or hot tub.',
          'Do not use drugs or alcohol before or during the use of a spa or hot tub to avoid unconsciousness and possible drowning.',
          'Do not use a spa or hot tub immediately following strenuous exercise.',
          'Prolonged immersion in a spa or hot tub may be injurious to your health.'
        ] },
        { type: 'heading', level: 2, text: 'CAUTION:' },
        { type: 'list', items: [
          "Maintain water chemistry in accordance with manufacturer's instructions."
        ] },
        { type: 'paragraph', className: 'warning-text', text: '* Please read the instructions carefully and use according to the instructions.\nChildren should use this product under the close supervision of adults.' },
        { type: 'heading', text: 'WARNING:' },
        { type: 'list', items: [
          'After transporting or installing the cold plunge, let the tub rest for 24 hours before turning on the chiller. Note: Failing to do so may result in chiller malfunction.',
          'To remove the back cover, wrap the cap with a cloth or use cloth gloves. Then, use pliers to grip the cap and pull it outward to remove it.',
          'If the control panel displays the ER03 code, it indicates there is air in the pipes. The air should be released through the exhaust port on the filter.',
          "The wind baffle inside the back cover of the Balta's ventilation system is a consumable item. It has a magnetic strip on the back that adheres to the chiller. If it breaks, it does not affect its functionality."
        ] },
        { type: 'heading', text: 'WARNING:' },
        { type: 'list', items: [
          'When the temperature is below 23°F (-5°C), heat pump will work in a very low efficency. Therefore it is important to manually activate the winter anti-freeze mode which is required to prevent the heat pump and pipes in cold zone from freezing and cracking.',
          'To prevent freezing, the product should either be powered on or drained when the temperature is between 23°F (-5°C) and 32°F (0°C).',
          'When the temperature falls below 23°F (-5°C), it is mandatory to drain the water to prevent freezing.'
        ] }
      ]
    },
    {
      header: 'Important Safety Instructions',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'heading', level: 2, text: 'WARNING:' },
        { type: 'list', items: [
          'People with infectious diseases should not use a spa or hot tub.',
          'To avoid injury, exercise care when entering or exiting the spa or hot tub.',
          'Do not use drugs or alcohol before or during the use of a spa or hot tub to avoid unconsciousness and possible drowning.',
          'Do not use a spa or hot tub immediately following strenuous exercise.',
          'Prolonged immersion in a spa or hot tub may be injurious to your health.'
        ] },
        { type: 'heading', level: 2, text: 'CAUTION:' },
        { type: 'list', items: [
          "Maintain water chemistry in accordance with manufacturer's instructions."
        ] },
        { type: 'paragraph', className: 'warning-text', text: '* Please read the instructions carefully and use according to the instructions.\nChildren should use this product under the close supervision of adults.' },
        { type: 'heading', text: 'WARNING:' },
        { type: 'list', items: [
          'After transporting or installing the cold plunge, let the tub rest for 24 hours before turning on the chiller. Note: Failing to do so may result in chiller malfunction.',
          'To remove the back cover, wrap the cap with a cloth or use cloth gloves. Then, use pliers to grip the cap and pull it outward to remove it.',
          'If the control panel displays the ER03 code, it indicates there is air in the pipes. The air should be released through the exhaust port on the filter.'
        ] },
        { type: 'heading', text: 'WARNING:' },
        { type: 'list', items: [
          'When the temperature is below 23°F (-5°C), heat pump will work in a very low efficency. Therefore it is important to manually activate the winter anti-freeze mode which is required to prevent the heat pump and pipes in cold zone from freezing and cracking.',
          'To prevent freezing, the product should either be powered on or drained when the temperature is between 23°F (-5°C) and 32°F (0°C).',
          'When the temperature falls below 23°F (-5°C), it is mandatory to drain the water to prevent freezing.'
        ] }
      ]
    },
    {
      header: 'Important Safety Instructions',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'paragraph', className: 'lead', text: 'READ AND FOLLOW ALL INSTRUCTIONS.' },

        { type: 'list', className: 'safety-box', items: [
          '<strong>DANGER -- Risk of accidental drowning:</strong><br/>Do not allow children to be in or around the spa unless a responsible adult supervises them. Keep the spa cover on and locked when not in use. See instructions enclosed with your cover for locking procedures.'
        ] },
        { type: 'list', className: 'safety-box', items: [
          '<strong>DANGER -- Risk of injury:</strong><br/>The suction fittings in this spa are sized to match the specific water flow created by the pump. Should the need arise to replace the suction fittings, or the pump, be sure the flow rates are compatible.<br/><br/>Never operate the spa if the suction fitting or filter baskets are broken or missing. Never replace a suction fitting with one that is rated less than the flow rate marked on the original suction fitting.'
        ] },
        { type: 'list', className: 'safety-box', items: [
          '<strong>DANGER -- Risk of electric shock:</strong><br/>Install the spa at least 5 feet (1.5 meters) from all metal surfaces. As an alternative, a spa may be installed within 5 feet of metal surfaces if each metal surface is permanently bonded by a minimum #8 AWG solid copper conductor to the outside of the spa\'s control box.<br/><br/>Do not permit any external electrical appliances, such as lights, telephones, radios, televisions, and etc., within five feet (1.5 meters) of the spa. Never attempt to operate any electrical device from inside the spa.<br/><br/>Replace a damaged power cord immediately.<br/><br/>Do not bury the power cord.<br/><br/>Connect to a grounded, grounding-type receptacle only.'
        ] },

        { type: 'heading', level: 2, text: 'WARNING -- To reduce the risk of injury:' },
        { type: 'list', items: [
          'The spa water should never exceed 104°F (40°C). Water temperatures between 100°F (38°C) and 104°F (40°C) are considered safe for a healthy adult. Lower water temperatures are recommended for young children and when spa use exceeds 10 minutes.',
          'High water temperatures have a high potential for causing fetal damage during pregnancy. Women who are pregnant, or who think they are pregnant, should always check with their physician prior to spa usage.',
          'The use of alcohol, drugs or medication before or during spa use may lead to unconsciousness, with the possibility of drowning.',
          'Persons suffering from obesity, a medical history of heart disease, low or high blood pressure, circulatory system problems or diabetes should consult a physician before using the spa.',
          'Persons using medications should consult a physician before using the spa since some medications may induce drowsiness while others may affect heart rate, blood pressure and circulation.'
        ] },
        { type: 'imageFloat-center', src: '/instruction_book/Exclamation.png', width: 520 }
      ]
    },
    {
      header: 'Important Safety Instructions',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },

        { type: 'list', className: 'safety-box', items: [
          '<strong>HYPERTHERMIA DANGER:</strong><br/>Prolonged exposure to hot air or water can in 4°C above 37°C. While hyperthermia has many health benefits, it is important not to allow your body\'s core temperature to rise above 103°F (39.5°C).<br/><br/>Symptoms of excessive hyperthermia include dizziness, lethargy, drowsiness and fainting. The effects of excessive hyperthermia may include:',
          'Failure to perceive heat',
          'Failure to recognize the need to exit spa or hot tub',
          'Unawareness of impending hazard',
          'Fetal damage in pregnant women',
          'Physical inability to exit the spa',
          'Unconsciousness'
        ] },

        { type: 'list', className: 'safety-lines', items: [
          '<strong>WARNING:</strong> The use of alcohol, drugs, or medication can greatly increase the risk of fatal hyperthermia.',
          '<strong>WARNING:</strong> People with infectious diseases should not use a spa or hot tub.',
          '<strong>WARNING:</strong> To avoid injury, exercise care when entering or exiting the spa or hot tub.',
          '<strong>WARNING:</strong> Do not use drugs or alcohol before or during the use of a spa or hot tub to avoid unconsciousness and possible drowning.',
          '<strong>WARNING:</strong> Do not use a spa or hot tub immediately following strenuous exercise.',
          '<strong>WARNING:</strong> Prolonged immersion in a spa or hot tub may be injurious to your health.'
        ] },

        { type: 'list', className: 'safety-lines', items: [
          '<strong>CAUTION:</strong> Maintain water chemistry in accordance with manufacturer\'s instructions.'
        ] },
        { type: 'paragraph', className: 'warning-text', text: '* Please read the instructions carefully and use according to the instructions. Children should use this product under the close supervision of adults.' },
        { type: 'imageFloat-center', src: '/instruction_book/Stop.png', width: 520 }
      ]
    },
    {
      header: 'Important Safety Instructions',
      variantId: 'C',
      blocks: [
        { type: 'heading', text: 'Important Safety Instructions' },
        { type: 'list', className: 'safety-lines', items: [
          '<strong>WARNING:</strong> All electrical hookups must be performed by a licensed electrician.',
          '<strong>WARNING:</strong> Spas with a cord must be connected to a dedicated 115-volt, 20-amp, GFCI-protected, grounded circuit.<br/>Spas without a cord must be connected to an electrical subpanel containing dedicated GFCI breakers to supply power to the spa',
          '<strong>WARNING:</strong> Removing or bypassing any Ground Fault Circuit Interrupter (GFCI) breaker will result in an unsafe spa and will void the spa\'s warranty."'
        ] },
        { type: 'imageFloat-center', src: '/instruction_book/Exclamation.png', width: 520 }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'spec-box', imageSrc, specs } 规格盒
      //       specs: 分区 { topLeft/topRight/leftTop/leftMiddle1/leftMiddle2/leftBottom/rightTop/rightMiddle/rightBottom }
      //              每区 { title: string, items: string[] }
      //   · { type: 'paragraph', text } 说明
      //   · { type: 'grid2', items } 左右图文
      //       items: [{ type: 'image', src } | { type: 'list', ordered?, items }]
      header: 'Specification',
      blocks: [
        { type: 'heading', text: 'Specification' },
        { type: 'spec-box', 
          imageSrc: '/instruction_book/Specification_1.png',
          specs: {
            topLeft: { title: 'Power Supply', items: ['Rated: 110V, 60 Hz, 15A', 'with Leakage Protection', 'Water Flow: 20gal/Min', '68L/Min'] },
            topRight: { title: 'Draining', items: ['3-way draining:', '2*normal drain outlet and', '1*heat pump condensate', 'outlets'] },
            leftTop: { title: 'Materials', items: ['Acrylic', 'Aluminum', 'Polyurethane'] },
            leftMiddle1: { title: 'Dry Weight', items: ['617 lbs', '280 kg'] },
            leftMiddle2: { title: 'Water Capacity', items: ['Spa Zone:', '217 gallons/820L', 'Cold Zone:', '87 gallons/330L'] },
            leftBottom: { title: 'Temperature Control', items: ['Spa Zone:', '50-104°F (10-40°C)', 'Cold Zone:', '37-104°F (3-40°C)'] },
            rightTop: { title: 'Antifreeze function', items: ['With the auto freeze-proof', 'function, heating will', 'initiate when the water', 'temperature drops below', '37°F (3°C) and will', 'automatically turn off', 'when the temperature', 'reaches 48°F(9°C)'] },
            rightMiddle: { title: 'Filtration', items: ['HydroPur Filter within', 'arm\'s reach for easy', 'configuration and', 'maintenance'] },
            rightBottom: { title: 'Cover', items: ['An aesthetic Aqua-shield', 'Lid that optimizes space,', 'and gives an', 'interior-grade look'] }
          }
        },
        { type: 'paragraph', text: 'By default the product is equipped with the following features as indicated in the illustration above:' },
        { type: 'grid2', items: [
          { type: 'image', src: '/instruction_book/Specification_2.png' },
          { type: 'list', ordered: true, items: [
            'Insulation Sleeves',
            'Chiller',
            'Control box',
            'Circulation Pump',
            'Ozone Sterilizer'
          ] }
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'paragraph', text } 简述
      //   · { type: 'image', src, fullWidth?, rotate?, marginTop? } 插图
      header: 'Touchscreen Control Panel',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Touchscreen Control Panel' },
        { type: 'paragraph', text: 'Control Panel Installation Instructions' },
        { type: 'image', src: '/instruction_book/Touchscreen_Control_Panel.png' }
      ]
    },
    {
      header: 'Touchscreen Control Panel',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Touchscreen Control Panel' },
        { type: 'paragraph', text: 'Control Panel Installation Instructions' },
        { type: 'image', src: '/instruction_book/Touchscreen_Control_Panel.png' }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'list', items } 引导问题
      //   · { type: 'ts-section', index, images, magnifier } 故障定位图
      //       images: [string, string, string]
      //       magnifier?: {
      //         serial?: string 序列号
      //         qrSrc?: string 二维码图片
      //         qrVisible?: boolean 是否显示二维码
      //         qrSize?: number 二维码大小
      //         qrMargin?: string 二维码外边距
      //         bgSrc?: string 放大镜背景图
      //         lines?: string[] 放大镜下说明文字
      //       }
      header: 'Troubleshooting',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'list', items: [
          'Where to find Serial Number on Masrren?',
          'If any after-sales service needs arise regarding the product, please provide this serial number.'
        ] },
        { type: 'ts-section', index: 1, images: [
          '/instruction_book/Troubleshooting1_1.png',
          '/instruction_book/Troubleshooting1_2.png',
          '/instruction_book/Troubleshooting1_3.png'
        ], magnifier: {
          serial: 'AC003204030',
          qrSrc: '/instruction_book/Troubleshooting1_3.png',
          qrVisible: true,
          qrSize: 78,
          qrMargin: '6px auto 8px',
          bgSrc: '',
          lines: [
            '32. Masrren',
            'Marble White',
            '1780*840*950mm',
            '23ZBG09E22898',
            'K100CIAICOBOALOANDAOKA',
            'MOD15946'
          ]
        } },
        { type: 'ts-section', index: 2, images: [
          '/instruction_book/Troubleshooting2_1.png',
          '/instruction_book/Troubleshooting2_2.png',
          '/instruction_book/Troubleshooting2_3.png'
        ], magnifier: { bgSrc: '/instruction_book/Troubleshooting2_3.png', qrSrc: '' } }
      ]
    },
    {
      header: 'Troubleshooting',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'heading', level: 2, text: 'Basic Troubleshooting' },
        { type: 'paragraph', text: 'The troubleshooting guidance provided here is intended to cover the most common problems a spa owner may encounter. For more in-depth troubleshooting, go to www.bellagioluxury.com.' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Problems starting up', items: [
            { symptom: "Pump won't prime", solutions: 'See priming instructions on page 14.' },
            { symptom: 'Breaker keeps shutting off', solutions: 'Reset the GFCI breaker. If this continues, contact your dealer or a qualified spa technician.' },
          ]},
          { title: 'Power and system problems', items: [
            { symptom: "System won’t start up or breaker keeps shutting off", solutions: 'Power may be shut off. Turn on GFCI circuit breaker. If this continues, contact your dealer or a qualified spa technician.' },
            { symptom: "Control panel doesn’t respond", solutions: [
              'Turn on or reset the GFCI circuit breaker. If this does not solve the problem, contact your dealer or a qualified spa technician.',
              "If you hear the pump running but the control panel doesn’t respond, contact your dealer."
            ] },
            { symptom: 'Spa does not turn off', solutions: [
              'Spa may be trying to heat up. Check if spa is in Ready or Rest mode.',
              'In cold climates, if spa is not equipped with full foam or any kind of insulation, it will try to maintain the set temperature. Set the spa to low temperature range and set the temperature to 80°F.',
              'Spa may be in filter cycle. If it is, this is normal and no adjustment is necessary.'
            ] },
            { symptom: 'Message on the control panel', solutions: 'There may be a problem. Please scan the QR code on page 15 for instructions.' }
          ]}
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'troubleTable', headers, groups } 故障表
      //       headers: [string, string] 表头（症状/可能解决方案）
      //       groups: [{ title: string, items }]
      //         · items: 数组 { symptom: string, description?: string, solutions: string | string[] }
      header: 'Troubleshooting',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Start-up problem', items: [
            { symptom: "Pump won't prime", description: 'Sometimes air may get trapped in the pump during spa filling. You may notice that after filling and starting the spa, the pump appears to be non-functional. You can hear the pump running, but there\'s no water movement.', solutions: [
              'The pump will not work properly while air is trapped in it.',
              'Continuing to operate the pump in this way will cause damage.'
            ] }
          ]},
          { title: 'Power and system problems', items: [
            { symptom: "System won’t start up or breaker keeps shutting off", solutions: 'Power may be shut off. If this continues, contact your dealer or a qualified spa technician.' },
            { symptom: 'Communication problem between the control mainframe and the circulation pump.', solutions: 'Please check the connecting wire between the control main unit and the heat pump and replace it if necessary. Or please check if the heat pump is powered.' },
            { symptom: 'The control panel cannot communicate with the control mainframe', solutions: 'Check the connecting wire between the control panel and the control main unit. Replace if necessary.' }
          ]}
        ] }
      ]
    },
    {
      header: 'Troubleshooting',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Heat problems', items: [
            { symptom: 'Spa water does not get hot', solutions: [
              'Spa may be in low temperature range. Set the spa to high temperature range.',
              'The filter may be dirty or may need to be replaced. Clean or replace the filter.',
              'The water level may be too low. Fill the spa with water level at 4 to 6 inches from the top.',
              'The temperature is not turned up high enough. Raise temperature on topside control.',
              'Cover the spa. The cover will keep heat in the spa and help keep heat from escaping. Make sure the cover is on at all times when spa is not in use.',
              'The heater element may be old, deteriorated, coated with scale, or defective. Contact your dealer for more assistance.',
              'The gate valves may be partially or completely closed. NEVER OPERATE YOUR SPA WITH THE GATE VALVES CLOSED!'
            ] },
            { symptom: 'Spa overheats - temperature greater than 110°F / 43°C', solutions: [
              'Overheating can occur during summer months and may not necessarily indicate a malfunction. When it occurs, a message code may also appear on the control panel.',
              'Temperature may be set too high. Turn the set temperature down to a lower temperature.',
              'Filtration time may be too long. Turn the filtration cycles down during the warm months.',
              'The spa may not be properly ventilated. Make sure the front of the spa is not blocked to allow air flow.',
              'High speed pumps may have been running too long. Limit pump running time to no more than 15 to 30 minutes.'
            ] }
          ]}
        ] }
      ]
    },
    {
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'troubleTable', headers, groups }（同上）
      header: 'Troubleshooting',
      variantId: 'A',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Chiller problems', items: [
            { symptom: 'Water does not get cold', solutions: [
              'Spa may be in high-temperature range. Set the spa to low-temperature range.',
              'The filter may be dirty or need to be replaced. Clean or replace the filter.',
              'The pump may have an airlock. Remove the airlock by priming the spa.',
              'The water level may be too low. Fill the spa until the water level is 4 to 6 inches from the top.',
              'The suction fittings may be blocked. Remove any debris that may be blocking them.',
              'The temperature may not be set low enough. Lower the temperature on the topside control.',
              'The filter skimmer may be blocked. Remove the blockage.',
              'Cover the spa to retain its warmth and prevent cold from penetrating. Ensure the cover is in place whenever the spa is not in use.',
              'Gate valves may be closed. Open gate valves. Note: Never operate your spa with closed gate valves.',
              'The cooling element may be old, defective, or coated with scale. For further assistance, please contact your dealer.',
              'Spa may be running in heating mode.'
            ] }
          ]},
          { title: 'Other problems', items: [
            { symptom: 'The water is murky', solutions: [
              'Ensure the filter is clean. This should be rinsed every month and changed every 3 months.',
              'Check if there is a green light on the ozonator. Change the water if it has become too dirty.'
            ] },
            { symptom: 'Bad smell', solutions: 'If the water looks clean and clear there should be no adverse smells. Run a clean cycle several times. If the water looks murky, drain and change it.' },
            { symptom: 'The temperature differs from what the thermometer shows', solutions: 'The internal temperature probe is calibrated to within 0.3° +/- . There could be an issue with the temperature sensor or PCB board.' },
            { symptom: 'Air lock', solutions: 'For the product with the Ozonator, it is recommended to clean the air intake hose using a brush once a year to prevent air line clogging' }
          ]}
        ] }
      ]
    },
    {
      header: 'Troubleshooting',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Water pressure problems', items: [
            { symptom: 'Low water pressure', solutions: [
              'Jet valves may be partially or fully closed. Open the jet valves.',
              'Filter cartridge may be dirty. Clean or replace the filter.',
              'Pump may have airlock. Remove airlock by priming spa (page 13).',
              'The suction fittings may be blocked. Remove any debris that may be blocking them.',
              'The filter skimmer may be blocked. Remove the blockage.',
              'Gate valves may be closed. Open gate valves. Note: Never operate your spa with the gate valves closed!',
              'Spa may be running in filtration mode. Press JETS or JETS 1 button to turn on high speed pump.'
            ] },
            { symptom: 'No water pressure (no water stream from any jets)', solutions: [
              'Power may be switched off. Turn the power back on.',
              'The pump may be defective. After you have tried all other troubleshooting, contact your dealer for assistance.'
            ] },
            { symptom: 'Jets surge on and off', solutions: 'Water level may be too low. Add water to normal level.' }
          ]},
          { title: 'Pump problems', items: [
            { symptom: 'Pump runs constantly – will not shut off', solutions: 'There may be a problem with circuit board. Contact your dealer' },
            { symptom: 'Noisy pump', solutions: [
              'The water level may be too low. Fill the spa with water level at 4 to 6 inches from the top.',
              'Filter cartridge may be dirty. Clean or replace the filter.',
              'Pump may have airlock. Remove airlock by priming spa (page 13)',
              'The suction fittings may be blocked. Remove any debris that may be blocking the suction fittings.',
              'Gate valves may be closed. Open gate valves. Note: Never operate your spa with the gate valves closed!',
              'Air may be leaking into the suction line. Contact your dealer for assistance.',
              'Debris may be inside the pump. Contact your dealer for assistance.',
              'Noise may be a sign of damage. Contact your dealer for service.'
            ] },
            
          ]}
        ] },
        { type: 'paragraph', className: 'warranty-title', text: 'LIMITED WARRANTY' },
        { type: 'list', className: 'warranty-lines', items: [
          '<strong>Five Years on Spa Shell Structure:</strong><br/>The spa shell structure is warranted against water loss due to defects in materials or workmanship for five (5) years from the original date of delivery.',
          '<strong>Five Years on Spa Shell Surface:</strong><br/>The acrylic spa shell is warranted against cracking, blistering or delaminating due to defects in materials or workmanship for five (5) years from the original date of delivery. Surface checking is not included.',
          '<strong>Two Years on Spa Plumbing:</strong><br/>Spa fittings and plumbing are warranted against leaks due to defects in materials or workmanship for 2 years from the original date of delivery.'
        ] }
      ]
    },
    {
      header: 'Troubleshooting',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'troubleTable', headers: ['Symptom','Possible Solutions'], groups: [
          { title: 'Pump problems', items: [
            { symptom: 'Pump turns off during operation', solutions: [
              'Automatic timer may have completed its cycle. Press JETS or JETS 1 button to start the cycle again.',
              'Pump may have overheated due to the vents on the equipment door being blocked. Make sure the front of the spa is not blocked to allow air flow.',
              'The pump motor may be defective. Contact your dealer for assistance.'
            ] },
            { symptom: 'Pump has a burning smell while running', solutions: 'A burning smell may be a sign of damage. Contact your dealer for service.' },
            { symptom: 'Pump does not run', solutions: [
              'Pump may have over heated. Let it cool for an hour and try operating the spa for a shorter time.',
              'Power to the spa may be shut off. Turn on or reset the GFCI circuit breaker. If this does not solve the problem, contact your dealer or a qualified spa technician.'
            ] }
          ]}
        ] },
        { type: 'paragraph', className: 'warranty-title', text: 'LIMITED WARRANTY' },
        { type: 'list', className: 'warranty-lines', items: [
          '<strong>Two Years on Standard Spa Equipment - Electronic Spa Control Systems, Jet Pump(s), Circulation Pump and Heater:</strong><br/>The spa equipment systems are warranted against failure due to defects in materials or workmanship for two years from the date of delivery.',
          '<strong>One Year on Sterilizer:</strong><br/>The sterilizer is warranted against failure due to defects in materials or workmanship for one year from the original date of delivery.',
          '<strong>One Year on Blower:</strong><br/>The blower is warranted against failure due to defects in materials or workmanship for one year from the original date of delivery.'
        ] }
      ]
    },
    {
      header: 'Troubleshooting',
      variantId: 'B',
      blocks: [
        { type: 'heading', text: 'Troubleshooting' },
        { type: 'paragraph', className: 'warranty-title', text: 'LIMITED WARRANTY' },
        { type: 'list', className: 'warranty-lines', items: [
          '<strong>One Year on Audio and Video System Components:</strong><br/>The factory installed audio and video components (i.e. power supply, stereo topside, IR sensor, cables, wires, etc.) are warranted against failure due to defects in materials or workmanship for one (1) year from the original date of delivery.',
          '<strong>One Year on L.E.D.\'s:</strong><br/>The factory installed L.E.D.\'s are warranted against failure due to defects in materials or workmanship for one (1) year from the original date of delivery.',
          '<strong>One Year on Spa Cabinet:</strong><br/>The spa cabinet is warranted to be free of defects in materials or workmanship for one year from the original date of delivery. Normal wear or appearance is not included. This warranty does not include damage caused in delivery, variations in color, wear or appearance, as all wood reacts differently to environmental conditions.',
          '<strong>Ninety Days on Spa Pillows and Filter Box:</strong><br/>Pillows and filter box are subject to water chemistry variation and are warranted for ninety (90) days from original date of delivery.',
          '<strong>Spa Covers:</strong><br/>Spa covers are warranted to be free of defects in materials and workmanship for a period of two (2) years on vinyl and one (1) year on foam core.',
          '<strong>Spa Accessories:</strong><br/>The spa accessories are warranted by the accessory manufacturer and are specifically excluded. Please see the respective product manufacturer\'s warranty for details.',
          '<strong>In-field labor shall be covered by dealers.</strong>',
          '<strong>Limited Warranty should be read in conjunction with Warranty Performance.</strong>'
        ] }
      ]
    },
])
// 记录初始说明书快照用于重置
const manualInitialMeta = JSON.parse(JSON.stringify(manualMeta.value))
const manualInitialPages = JSON.parse(JSON.stringify(manualPages.value))
const manualPagesRef = ref(null)
const currentPageRef = ref(null)
const currentPageIndex = ref(0)

const VARIANT_GROUP_BY_HEADER = {
  'Embrace the Revitalizing Chill': { key: 'embrace', label: 'Embrace the Revitalizing Chill' },
  'How To Set Up': { key: 'how_to_set_up', label: 'How To Set Up' },
  'Important Safety Instructions': { key: 'important_safety_instructions', label: 'Important Safety Instructions' },
  'Premium Materials': { key: 'premium_materials', label: 'Premium Materials' },
  'Touchscreen Control Panel': { key: 'touchscreen_control_panel', label: 'Touchscreen Control Panel' },
  'Troubleshooting': { key: 'troubleshooting', label: 'Troubleshooting' },
}

const selectedVariants = reactive({})
const variantsLoading = ref(false)
const variantsLoadedKey = ref('')
let _variantsSaveTimer = null

const manualPagesWithMeta = computed(() => {
  const pages = Array.isArray(manualPages.value) ? manualPages.value : []
  const occurrenceByGroup = {}
  return pages.map((page, rawIndex) => {
    const header = page?.header
    const group = header && VARIANT_GROUP_BY_HEADER[header] ? VARIANT_GROUP_BY_HEADER[header] : null
    const groupKey = group ? group.key : null
    const variantId = page?.variantId ? String(page.variantId) : 'A'

    let order = null
    if (groupKey) {
      const k = `${groupKey}__${variantId}`
      occurrenceByGroup[k] = (occurrenceByGroup[k] || 0) + 1
      order = occurrenceByGroup[k]
    }

    return {
      page,
      rawIndex,
      header,
      variantGroup: groupKey,
      variantLabel: group ? group.label : null,
      variantId,
      variantOrder: order,
    }
  })
})

const ensureVariantDefaults = () => {
  manualPagesWithMeta.value.forEach((row) => {
    if (!row.variantGroup) return
    if (!selectedVariants[row.variantGroup]) {
      selectedVariants[row.variantGroup] = row.variantId || 'A'
    }
  })
}

const visibleManualPagesWithMeta = computed(() => {
  ensureVariantDefaults()
  const rows = manualPagesWithMeta.value
  const filtered = rows.filter((row) => {
    if (!row.variantGroup) return true
    const sel = selectedVariants[row.variantGroup]
    return String(row.variantId) === String(sel)
  })

  // Keep multi-page sections in a stable order
  filtered.sort((a, b) => {
    if (a.rawIndex !== b.rawIndex) return a.rawIndex - b.rawIndex
    const ao = a.variantOrder ?? 0
    const bo = b.variantOrder ?? 0
    return ao - bo
  })
  return filtered
})

const visibleManualPages = computed(() => visibleManualPagesWithMeta.value.map((r) => r.page))

const currentPage = computed(() => visibleManualPages.value[currentPageIndex.value])

const currentVariantSelectorGroup = computed(() => {
  const header = currentPage.value?.header
  const group = header && VARIANT_GROUP_BY_HEADER[header] ? VARIANT_GROUP_BY_HEADER[header] : null
  if (!group) return null

  // options for this group
  const optionsSet = new Set()
  manualPagesWithMeta.value.forEach((row) => {
    if (row.variantGroup === group.key) optionsSet.add(row.variantId)
  })
  const order = { A: 0, B: 1, C: 2 }
  const options = Array.from(optionsSet)
    .map((id) => ({ id, label: id }))
    .sort((a, b) => {
      const ao = order[String(a.id)]
      const bo = order[String(b.id)]
      const av = typeof ao === 'number' ? ao : 99
      const bv = typeof bo === 'number' ? bo : 99
      if (av !== bv) return av - bv
      return String(a.id).localeCompare(String(b.id))
    })

  if (options.length < 2) return null
  return {
    key: group.key,
    label: group.label,
    options,
  }
})

const visibleIndexToRawIndex = (visibleIndex) => {
  const row = visibleManualPagesWithMeta.value[Number(visibleIndex)]
  return row ? row.rawIndex : Number(visibleIndex)
}

const variantSelectorGroups = computed(() => {
  const byKey = {}
  manualPagesWithMeta.value.forEach((row) => {
    const g = row.variantGroup
    if (!g) return
    byKey[g] = byKey[g] || {
      key: g,
      label: row.variantLabel || g,
      options: {},
    }
    byKey[g].options[row.variantId] = byKey[g].options[row.variantId] || {
      id: row.variantId,
      label: row.variantId,
    }
  })

  return Object.values(byKey)
    .map((g) => ({
      key: g.key,
      label: g.label,
      options: Object.values(g.options).sort((a, b) => String(a.id).localeCompare(String(b.id))),
    }))
    .filter((g) => g.options.length >= 2)
})
const userZoom = ref(1)
// 计算缩放，移除垂直滚动，由左侧目录直接切换（以原始A4画布 820px 宽为基准）
const BASE_WIDTH = 820
const BASE_HEIGHT = Math.round(820 * 1.414)
const applyScale = () => {
  const el = manualPagesRef.value
  if (!el) return
  const cw = el.clientWidth
  const ch = el.clientHeight
  if (!cw || !ch) return
  // 考虑容器内边距，使用可用尺寸计算缩放，避免底部被裁切
  const cs = window.getComputedStyle(el)
  const ph = parseFloat(cs.paddingLeft || '0') + parseFloat(cs.paddingRight || '0')
  const pv = parseFloat(cs.paddingTop || '0') + parseFloat(cs.paddingBottom || '0')
  const availW = Math.max(0, cw - ph)
  const availH = Math.max(0, ch - pv)
  const base = Math.min(1, availW / BASE_WIDTH, availH / BASE_HEIGHT)
  const scale = base * (userZoom.value || 1)
  el.style.setProperty('--page-scale', String(scale))
}
let ro = null
onMounted(async () => {
  await nextTick()
  applyScale()
  // 监听窗口与容器尺寸变化
  window.addEventListener('resize', applyScale)
  try {
    ro = new ResizeObserver(() => applyScale())
    if (manualPagesRef.value) ro.observe(manualPagesRef.value)
  } catch (e) { /* ResizeObserver 不可用时忽略 */ }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', applyScale)
  if (ro) {
    try {
      ro.disconnect()
    } catch (e) {}
    ro = null
  }
})

watch(currentPageIndex, async () => {
  await nextTick()
  applyScale()
})

watch(userZoom, () => applyScale())

watch(tab, async (v) => {
  if (v === 'manual') {
    await nextTick()
    applyScale()
  }
})

const clamp = (v, min, max) => (v < min ? min : v > max ? max : v)
const incZoom = () => {
  userZoom.value = clamp((userZoom.value || 1) + 0.1, 0.5, 2)
}
const decZoom = () => {
  userZoom.value = clamp((userZoom.value || 1) - 0.1, 0.5, 2)
}
const resetZoom = () => {
  userZoom.value = 1
}

const goToPage = (pageNumber) => {
  const idx = clamp((pageNumber | 0) - 1, 0, (visibleManualPages.value?.length || 1) - 1)
  currentPageIndex.value = idx
}

const addBlankPage = (index, pos) => {
  const rawIndex = visibleIndexToRawIndex(index)
  const insertAt = pos === 'before' ? rawIndex : rawIndex + 1
  const neighbor = manualPages.value[rawIndex]
  const inferred = neighbor ? (neighbor.header || deriveTitle(neighbor) || 'Blank Page') : 'Blank Page'
  manualPages.value.splice(insertAt, 0, { header: inferred, blocks: [] })
  nextTick(() => {
    // 跳到新插入的空白页，保证侧栏与页眉同步
    // Recompute and jump to the inserted page in visible list.
    const targetVisibleIndex = visibleManualPagesWithMeta.value.findIndex((r) => r.rawIndex === insertAt)
    if (targetVisibleIndex >= 0) goToPage(targetVisibleIndex + 1)
  })
}

const deleteBlankPage = (index) => {
  const pg = manualPages.value[index]
  if (pg && (!pg.blocks || pg.blocks.length === 0)) {
    manualPages.value.splice(index, 1)
    nextTick(() => {
      goToPage(Math.max(1, index))
    })
  }
}

const deleteAnyPage = (index) => {
  const rawIndex = visibleIndexToRawIndex(index)
  const pg = manualPages.value[rawIndex]
  if (!pg) return
  if (pg.blocks && pg.blocks.length > 0) {
    const ok = window.confirm('该页包含内容，确认删除？此操作不可撤销')
    if (!ok) return
  }
  manualPages.value.splice(rawIndex, 1)
  const nextIndex = Math.min(index, (visibleManualPages.value?.length || 1) - 1)
  nextTick(() => {
    goToPage(Math.max(1, nextIndex + 1))
  })
}

const deriveTitle = (page) => {
  const blks = page?.blocks || []
  if (page && page.customTitle) return page.customTitle
  const hd = blks.find((b) => b.type === 'heading')
  if (hd && hd.text) return hd.text
  if (!blks.length) return 'Blank Page'
  if (blks[0].type === 'cover') return 'Cover'
  if (page && page.header) return page.header
  return 'Page'
}

const sidebarItems = computed(() => {
  const total = (visibleManualPages.value || []).length
  return Array.from({ length: total }, (_, i) => ({
    page: i + 1,
    title: deriveTitle(visibleManualPages.value[i] || {})
  }))
})

const resetManual = () => {
  manualMeta.value = JSON.parse(JSON.stringify(manualInitialMeta))
  manualPages.value = JSON.parse(JSON.stringify(manualInitialPages))
  nextTick(() => {
    currentPageIndex.value = 0
    goToPage(1)
  })
}

const getByPath = (obj, path) => {
  if (!path) return undefined
  const segs = String(path).split('.')
  let o = obj
  for (let i = 0; i < segs.length; i++) {
    if (o == null) return undefined
    o = o[segs[i]]
  }
  return o
}

const setByPath = (obj, path, value) => {
  const segs = String(path).split('.')
  let o = obj
  for (let i = 0; i < segs.length - 1; i++) {
    const k = segs[i]
    if (typeof o[k] !== 'object' || o[k] === null) o[k] = {}
    o = o[k]
  }
  o[segs[segs.length - 1]] = value
}

const makeManualPath = (pageIndex, blockIndex, tail) => {
  const p = visibleIndexToRawIndex(pageIndex)
  const b = Number(blockIndex)
  return `pages.${p}.blocks.${b}` + (tail ? `.${tail}` : '')
}

const manualRoot = () => ({ pages: manualPages.value })

const onEditManualWithCaret = (evt, path, useHTML = false) => {
  const el = evt?.target
  if (!el) return
  const selection = window.getSelection()
  let caretOffset = 0
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(el)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    caretOffset = preCaretRange.toString().length
  }
  const val = useHTML ? (el.innerHTML ?? '') : (el.innerText ?? '')
  setByPath(manualRoot(), path, val)
  nextTick(() => {
    if (!el || !el.firstChild) return
    try {
      const range = document.createRange()
      const sel = window.getSelection()
      let charCount = 0
      let found = false
      const walk = (node) => {
        if (found) return
        if (node.nodeType === Node.TEXT_NODE) {
          const len = node.textContent.length
          if (charCount + len >= caretOffset) {
            range.setStart(node, Math.min(caretOffset - charCount, len))
            range.collapse(true)
            found = true
          } else {
            charCount += len
          }
        } else {
          for (let i = 0; i < node.childNodes.length; i++) walk(node.childNodes[i])
        }
      }
      walk(el)
      if (found) {
        sel.removeAllRanges()
        sel.addRange(range)
      }
    } catch (e) {}
  })
}

const onEditManualPageTitle = (evt) => {
  const path = `pages.${visibleIndexToRawIndex(currentPageIndex.value)}.customTitle`
  onEditManualWithCaret(evt, path)
}

const onVariantSelectionChange = async (groupKey, variantId) => {
  if (!groupKey) return
  selectedVariants[groupKey] = String(variantId)

  // Jump to the first page in this group under the newly selected variant.
  await nextTick()
  const targetIndex = visibleManualPagesWithMeta.value.findIndex(
    (r) => r.variantGroup === groupKey
  )
  if (targetIndex >= 0) {
    currentPageIndex.value = targetIndex
  } else {
    currentPageIndex.value = clamp(currentPageIndex.value, 0, (visibleManualPages.value?.length || 1) - 1)
  }

  // Persist selection (debounced)
  const pn = (productName.value || name.value || '').trim()
  const bc = (bomCode.value || '').trim()
  if (!pn || !bc) return
  if (_variantsSaveTimer) clearTimeout(_variantsSaveTimer)
  _variantsSaveTimer = setTimeout(async () => {
    try {
      await saveManualBookVariants(pn, bc, { ...selectedVariants })
      variantsLoadedKey.value = `${pn}__${bc}`
    } catch (e) {
      // silent fail
    }
  }, 350)
}

const tryLoadSavedManualVariants = async () => {
  const pn = (productName.value || name.value || '').trim()
  const bc = (bomCode.value || '').trim()
  if (!pn || !bc) return false
  const loadKey = `${pn}__${bc}`
  if (variantsLoadedKey.value === loadKey || variantsLoading.value) return false
  variantsLoading.value = true
  try {
    const saved = await getManualBookVariants(pn, bc)
    if (saved && typeof saved === 'object') {
      Object.keys(saved).forEach((k) => {
        selectedVariants[k] = String(saved[k])
      })
    }
    variantsLoadedKey.value = loadKey
    return true
  } catch (e) {
    variantsLoadedKey.value = loadKey
    return false
  } finally {
    variantsLoading.value = false
  }
}

watch(
  [productName, bomCode, tab],
  async () => {
    if (tab.value !== 'manual') return
    await nextTick()
    await tryLoadSavedManualVariants()
  },
  { immediate: true }
)

const getContentsFor = (pageIndex) => {
  const pages = manualPages.value || []
  const start = pageIndex + 1
  const after = pages.slice(start).map((p, i) => ({ title: deriveTitle(p), page: start + i + 1 }))
  const result = []
  for (let i = 0; i < after.length; i++) {
    const cur = after[i]
    const prev = result[result.length - 1]
    if (prev && prev.title === cur.title) continue
    result.push(cur)
  }
  return result.map((it) => ({ title: it.title, page: it.page, level: 0, displayPage: displayTocPage(it.page) }))
}

const imageStyle = (blk) => {
  const s = { objectFit: 'contain', maxWidth: '100%' }
  const isFloat = blk?.type === 'imageFloat' || (typeof blk?.type === 'string' && blk.type.startsWith('imageFloat-'))
  if (!isFloat && !blk.fullWidth && !blk.width && !blk.height) {
    s.width = '70%'
    s.display = 'block'
    s.margin = '0 auto'
  }
  if (blk.fullWidth) s.width = '100%'
  if (blk.width) s.width = typeof blk.width === 'number' ? blk.width + 'px' : blk.width
  if (blk.height) s.height = typeof blk.height === 'number' ? blk.height + 'px' : blk.height
  if (typeof blk.rotate === 'number') {
    s.transform = `rotate(${blk.rotate}deg)`
    s.transformOrigin = 'center center'
    s.display = 'block'
    s.margin = '0 auto'
  }
  if (typeof blk.marginTop === 'number') s.marginTop = blk.marginTop + 'px'
  if (typeof blk.marginBottom === 'number') s.marginBottom = blk.marginBottom + 'px'
  return s
}

const coverStyle = (blk) => ({
  position: 'absolute',
  inset: '0 0 0 0',
  background: `url(${blk.backSrc || '/instruction_book/back.jpg'}) center/cover no-repeat`,
})
// 允许通过路由 query.manualPages / query.manualMeta 传入 URL 编码的 JSON 字符串覆盖页面内容或目录
onMounted(() => {
  const rawPages = route.query.manualPages
  if (typeof rawPages === 'string' && rawPages.trim()) {
    try {
      const decoded = decodeURIComponent(rawPages)
      const incoming = JSON.parse(decoded)
      if (Array.isArray(incoming)) manualPages.value = incoming
    } catch (e) {}
  }
  const rawMeta = route.query.manualMeta
  if (typeof rawMeta === 'string' && rawMeta.trim()) {
    try {
      const decoded = decodeURIComponent(rawMeta)
      const incoming = JSON.parse(decoded)
      if (incoming && typeof incoming === 'object') {
        if (Array.isArray(incoming.toc)) manualMeta.value.toc = incoming.toc
        if (incoming.title) manualMeta.value.title = incoming.title
        if (incoming.footer && typeof incoming.footer === 'object') manualMeta.value.footer = incoming.footer
      }
    } catch (e) {}
  }
})

</script>

<style scoped>
@font-face {
  font-family: 'SourceSansPro-Regular';
  src: url('/fonts/SourceSansPro-Regular.otf') format('opentype');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'SourceSansPro-Bold';
  src: url('/fonts/SourceSansPro-Bold.ttf') format('truetype');
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'SourceSansPro-Semibold';
  src: url('/fonts/SourceSansPro-Semibold.ttf') format('truetype');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
.page { padding: 16px; }
.topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 10px; }
.back-btn { font-weight: 600; }
.tabs { flex: 1; display: flex; justify-content: center; }
.toolbar-like { display: flex; gap: 16px; }
.content { display: grid; gap: 16px; }
.product-header { display: flex; gap: 16px; align-items: center; padding: 12px; border: 1px solid var(--color-border, #ebeef5); border-radius: 10px; }
.thumb { width: 96px; height: 96px; object-fit: contain; border-radius: 8px; background: #fafafa; padding: 8px; }
.meta .name { font-size: 18px; font-weight: 700; }
.meta .sub { color: #666; }
.bom-row { display: flex; align-items: center; gap: 16px; margin-top: 8px; flex-wrap: wrap; }
.bom-value { display: flex; align-items: center; gap: 6px; font-weight: 600; color: #303133; }
.bom-label { color: #909399; font-size: 13px; }
.bom-code { font-size: 14px; color: #1f6aa0; }
.bom-placeholder { color: #c0c4cc; font-size: 13px; }
.bom-detail-btn {
  border-radius: 999px;
  padding: 0 14px;
  height: 30px;
  line-height: 30px;
  border: 1px solid transparent;
  background: linear-gradient(130deg, rgba(49,130,206,0.12), rgba(99,179,237,0.2));
  color: #1f6aa0;
  font-weight: 500;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.bom-detail-btn:hover {
  border-color: rgba(49,130,206,0.5);
  box-shadow: 0 2px 6px rgba(31,106,160,0.25);
}
.bom-detail-btn:focus-visible {
  outline: none;
  border-color: rgba(49,130,206,0.8);
  box-shadow: 0 0 0 2px rgba(49,130,206,0.2);
}
.bom-dialog-shell .el-dialog__body { padding-top: 8px; }
.bom-dialog { display: grid; gap: 12px; max-height: 60vh; overflow: hidden; }
.bom-type-switch { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.bom-type-label { font-weight: 600; color: #303133; }
.bom-type-tip { color: #909399; font-size: 13px; }
.bom-alert { margin-top: 4px; }
.bom-error-list { margin: 6px 0 0; padding-left: 18px; }
.bom-error-list li { line-height: 1.3; }
.bom-section-list { overflow: auto; border: 1px solid #ebeef5; border-radius: 10px; padding: 12px; display: grid; gap: 12px; max-height: 48vh; }
.bom-section { padding-bottom: 10px; border-bottom: 1px dashed #ebeef5; display: grid; gap: 8px; }
.bom-section:last-child { border-bottom: none; padding-bottom: 0; }
.bom-section-title { font-weight: 600; color: #303133; display: flex; justify-content: space-between; align-items: center; }
.bom-section-digits { color: #909399; font-size: 12px; }
.bom-fields { display: grid; gap: 12px; }
.bom-field { display: grid; gap: 4px; }
.bom-field-label { display: flex; align-items: center; gap: 8px; font-weight: 500; color: #303133; }
.bom-field-label .digits { font-size: 12px; color: #909399; }
.bom-field-control { display: grid; }
.bom-dialog-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.bom-dialog-footer .footer-hint { color: #909399; font-size: 13px; }
.bom-detail-list { max-height: 60vh; overflow: auto; display: grid; gap: 8px; }
.bom-detail-item { display: grid; gap: 2px; padding: 10px; border: 1px solid #ebeef5; border-radius: 8px; }
.bom-detail-item .detail-label { font-weight: 600; color: #303133; }
.bom-detail-item .detail-value { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.bom-detail-item .code { font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; font-weight: 700; color: #1f6aa0; }
.bom-detail-item .meaning { color: #606266; font-size: 13px; }
.panel { background: #fff; border: 1px solid var(--color-border, #ebeef5); border-radius: 10px; padding: 12px; }
.panel .title { font-weight: 700; margin-bottom: 8px; }

/* 产品图片选择弹框样式 */
.product-dialog-section { margin-top: 4px; }
.product-dialog-section p { margin: 0 0 10px; font-size: 13px; color: #606266; }
.kb-image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; max-height: 320px; overflow: auto; padding: 4px 0; }
.kb-image-item { border: 1px solid #e4e7ed; border-radius: 6px; padding: 6px; cursor: pointer; text-align: center; transition: border-color .15s ease, box-shadow .15s ease, transform .08s ease; background: #fafafa; }
.kb-image-item:hover { border-color: #409eff; box-shadow: 0 0 0 1px rgba(64,158,255,0.3); transform: translateY(-1px); }
.kb-image-item img { width: 100%; height: 80px; object-fit: contain; margin-bottom: 4px; }
.kb-image-label { font-size: 12px; color: #606266; word-break: break-all; }

/* Match Home.vue toolbar spacing */
.tabs :deep(.el-button) { padding: 8px 18px; }

/* 规格页加载进度样式 */
.specsheet-loading { margin: 20px 0; padding: 20px; background: #f5f7fa; border-radius: 8px; }
.specsheet-loading .loading-text { margin-top: 12px; text-align: center; color: #606266; font-size: 14px; }

.specsheet-error {
  margin: 20px 0;
}

/* Promo template styles (match base2.jpg) */
.promo-wrap { display: flex; justify-content: center; padding: 12px; }
.promo-canvas {
  width: 820px;
  aspect-ratio: 1/1.414;
  background: var(--promo-bg-color, #fff);
  border: 1px solid #e5e7eb;
  position: relative;
  overflow: hidden;
  --promo-main-color: #2c6ea4;
  --promo-bg-color: #ffffff;
  --promo-text-color: #111827;
}
.promo-canvas :where([contenteditable="true"]) { cursor: text; outline: none; border: none; }
.promo-canvas :where([contenteditable="true"]):focus { outline: none; box-shadow: none; border: none; background: transparent; }
.promo-top { height: 35%; background: #e9ecef url('/back/back.png') center/cover no-repeat; position: relative; cursor: pointer; }
.promo-top-bg-layer { position: absolute; inset: 0; z-index: 1; cursor: pointer; }
.logo-card { position: absolute; left: 20px; width: 100px; height: 130px; padding: 12px; background: #eaeff5; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border: 1px solid #eee; display: flex; align-items: center; justify-content: center; box-sizing: border-box; z-index: 6; cursor: pointer; }
.logo-mark { color: #c99a2e; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.logo-mark img { width: 100px; height: 100px; object-fit: contain; display: block; }

/* 产品名 */
.product-title { font-size: 42px; font-weight: 800; color: var(--promo-main-color); letter-spacing: 0.5px; margin-bottom: 6px; line-height: 1.1; }

.promo-body { display: grid; grid-template-columns: 1fr 1fr; padding: 20px 46px; gap: 30px 60px; }
.col { display: grid; gap: 8px; }
.section { display: grid; gap: 6px;margin-top: 10px; }
.h2 { color: var(--promo-main-color); font-weight: 700; font-size: 19px; white-space: pre-line; line-height: 1.3; }

.icons { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; align-items: start; }
.icon { display: grid; grid-template-columns: 35px 1fr; align-items: center; column-gap: 10px; color: var(--promo-text-color); }
.icon img { width: 35px; height: 35px; aspect-ratio: 1 / 1; object-fit: contain; display: block; }
.icon-text { display: grid; justify-items: start; row-gap: 2px;margin-left: 10px; }
.icon-num { color: var(--promo-text-color); font-size: 18px; font-weight: 600; }
.icon-t { font-size: 12px; color: #6b7280; font-weight: 400; }

.measurements-row { display: grid; grid-template-columns: 32px 1fr; align-items: center; gap: 14px; margin-top: 6px; }
.m-icon img { width: 32px; height: 32px; aspect-ratio: 1 / 1; object-fit: contain; display: block; }
.m-text { display: grid; }
.m-text .m-label { color: #6b7280; font-size: 12px; line-height: 1; font-weight: 400; }
.m-text .m-value { color: var(--promo-text-color); font-size: 17px; line-height: 1.2; font-weight: 500; }

.bullets { list-style: none !important; padding-left: 0; margin: 0; display: grid; gap: 3px; color: var(--promo-text-color); font-size: 14px; }
.bullets li { list-style: none !important; position: relative; padding-left: 16px; line-height: 1.3; font-weight: 400; }
.bullets li::marker { content: ''; }
.bullets li::before { content: ''; position: absolute; left: 0; top: 0.65em; width: 6px; height: 6px; background: var(--promo-main-color); border-radius: 50%; transform: translateY(-50%); }
.specs { display: grid; gap: 8px; color: var(--promo-text-color); }

/* Right column: Specifications list */
.specs-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 5px; }
.specs-item { display: grid; grid-template-columns: 120px 1fr; align-items: baseline; column-gap: 12px; }
.specs-label { color: #6b7280; text-align: right; justify-self: end; font-size: 14px; font-weight: 400; }
.specs-value { color: var(--promo-text-color); text-align: left; justify-self: start; font-size: 14px; font-weight: 400; }
.specs-value.bold { color: var(--promo-text-color); font-weight: 500; }
.specs-dot { display: inline-block; width: 8px; height: 8px; background: #c4c4c4; border-radius: 50%; vertical-align: middle; }
.specs-dot + .specs-dot { margin-left: 10px; }
.specs-item.clickable { cursor: pointer; }
.specs-item.clickable .specs-label, .specs-item.clickable .specs-value { user-select: none; }

.spec-color-dialog { display: grid; gap: 12px; }
.spec-color-dialog .row { display: grid; grid-template-columns: 120px 1fr; align-items: center; gap: 10px; }
.spec-color-dialog .label { font-weight: 600; color: #303133; }
.spec-color-dialog .presets { display: grid; grid-template-columns: 120px 1fr; gap: 10px; align-items: start; }
.spec-color-dialog .preset-grid { display: grid; grid-template-columns: repeat(10, 1fr); gap: 8px; }
.spec-color-dialog .preset { width: 22px; height: 22px; border-radius: 6px; border: 1px solid rgba(0,0,0,0.12); cursor: pointer; }

/* Gray bullets for Smart Water Purification System */
.bullets-gray { color: #6b7280; font-size: 14px; }
.bullets-gray li { font-weight: 400; }
.bullets-gray li::marker { content: ''; }
.bullets-gray li::before { background: #6b7280; }

.promo-footer { position: absolute; bottom: 0; left: 0; right: 0; height: 26px; background: var(--promo-main-color); display: flex; align-items: center; }
.footnote { font-size: 10px; color: #6b7280; padding-left: 24px; margin-bottom: 60px;}

.rag-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
  max-height: 70vh;
}
.rag-master {
  border-right: 1px solid #ebeef5;
  padding-right: 8px;
  display: grid;
  gap: 6px;
  overflow-y: auto;
  max-height: 70vh;
  padding-bottom: 4px;
}
.rag-detail {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  max-height: 70vh;
  padding-right: 4px;
}
.rag-detail-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: #f5f7fa;
  cursor: pointer;
  display: grid;
  gap: 2px;
}
.rag-item-btn {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 6px 8px;
  background: #f5f7fa;
  cursor: pointer;
  display: grid;
  gap: 2px;
}
.rag-item-btn:hover {
  border-color: #c0c4cc;
}
.rag-item-btn.active {
  border-color: #409eff;
  background: #ecf5ff;
}
.rag-detail {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rag-detail-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: #606266;
}
.rag-detail-path {
  color: #909399;
  word-break: break-all;
}
.rag-chunk-text {
  overflow: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.rag-empty-detail {
  color: #909399;
  font-size: 13px;
}

/* Poster layout */
.poster-wrap { display: flex; justify-content: center; padding: 12px; }
.poster-canvas { position: relative; width: 820px; aspect-ratio: 1.414/1; border: 1px solid #e5e7eb; background: transparent; overflow: hidden; border-radius: 6px; }
.poster-canvas :where([contenteditable="true"]) { cursor: text; outline: none; border: none; box-shadow: none; background: transparent; }
.poster-canvas :where([contenteditable="true"]):focus { outline: none; border: none; box-shadow: none; background: transparent; }
.poster-bg { position: absolute; inset: 0; background: center/cover no-repeat; filter: none; }
/* 防止导出时渐变边缘出现 1px 黑线：
   - 略微加大高度并向下覆盖 2px
   - 调整渐变停靠点，避免在完全透明处出现色带
   - 启用 GPU 合成避免子像素缝隙 */
.poster-headmask { position: absolute; left: 0; right: 0; top: 0; height: calc(30% + 2px); margin-bottom: -2px; background: linear-gradient(to bottom, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.12) 60%, rgba(0,0,0,0.01) 98%, rgba(0,0,0,0) 100%); z-index: 4; pointer-events: none; transform: translateZ(0); backface-visibility: hidden; will-change: transform; }
.poster-canvas.exporting .poster-headmask { display: none; }
/* 导出时将渐变作为 poster-bg 的伪元素叠加，避免与下层黑底发生混合产生黑线 */
.poster-canvas.exporting .poster-bg::before { content: ''; position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.12) 60%, rgba(0,0,0,0.01) 98%, rgba(0,0,0,0.001) 100%); pointer-events: none; z-index: 1; }
.poster-canvas::after { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg, rgba(0,0,0,0.08), rgba(0,0,0,0.08)); pointer-events: none; }
.poster-canvas.exporting { border: 0 !important; border-radius: 0 !important; box-shadow: none !important; }
.poster-canvas.exporting::after { display: none !important; }
.poster-head { position: absolute; top: 30px; left: 50%; transform: translateX(-50%); width: 92%; display: grid; justify-items: center; gap: 0; z-index: 5; pointer-events: none; }
.poster-title { font-weight: 900; letter-spacing: 1px; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; font-size: 34px; line-height: 0.72; text-shadow: 0 3px 10px rgba(0,0,0,0.35), 0 0 1px rgba(0,0,0,0.25); transform: scaleY(0.6); transform-origin: center top; }
.poster-title .hot { color: #f39b2f; margin-right: 8px; }
.poster-title .mid { color: #5aa3e6; margin-right: 8px; }
.poster-title .end { color: #d8a53b; }
.poster-brand { font-size: 62px; font-weight: 900; color: #ffffff; text-shadow: 0 5px 16px rgba(0,0,0,0.4), 0 0 1px rgba(0,0,0,0.3); letter-spacing: 1.5px; line-height: 0.56; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; transform: scaleY(0.6); transform-origin: center top; }
.poster-sub { color: #e5e7eb; font-size: 10px; opacity: 0.98; letter-spacing: 0.6px; text-shadow: 0 2px 8px rgba(0,0,0,0.4); line-height: 0.75; }
.poster-product { position: absolute; left: 50%; top: 47%; transform: translate(-50%, -50%); width: 40%; height: auto; object-fit: contain; filter: drop-shadow(0 14px 28px rgba(0,0,0,0.35)); z-index: 4; }
.poster-side { position: absolute; top: 100px; display: grid; gap: 14px; z-index: 3; }
.poster-side.left { left: 24px; width: 200px; }
.poster-side.right { right: 24px; width: 240px; }
.poster-card.small { display: grid; gap: 4px; align-items: start; z-index: 3; aspect-ratio: 16/9; }
.poster-card.small img { width: 100%; height: 100%; display: block; border-radius: 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.18); object-fit: cover; }
.poster-cap { color: #f3f4f6; text-shadow: 0 2px 8px rgba(0,0,0,0.5); font-size: 9px; line-height: 1.0; font-weight: 600; }
.poster-card.small, .poster-bignum { position: absolute; z-index: 3; }
/* Left column positions (adjusted for compact header) */
.pl-feature-top { left: 8%; top: 30%; width: 16%; }
.pl-hotnum { left: 10%; top: 46%; }
.pl-mini-heater { left: 8%; top: 60%; width: 16%; }
.pl-premium { left: 8%; bottom: 6%; width: 16%; }
/* Right column positions (adjusted for compact header) */
.pr-anti-freeze { right: 8%; top: 28%; width: 16%; }
.pr-aerospace { right: 8%; top: 45%; width: 16%; }
.pr-coldnum { right: 8%; top: 62%; text-align: right; }
.pr-foam { right: 8%; bottom: 10%; width: 16%; }
.pr-hydro { right: 8%; bottom: 6%; width: 16%; }
/* Big number styles */
.poster-bignum .num { font-size: 48px; }
.poster-bignum .zone { font-size: 18px; }
.poster-card.small.ar169 { aspect-ratio: 16/9; }
.poster-card.small.ar169 img { width: 100%; height: 100%; object-fit: cover; }
.poster-bignum { display: grid; justify-items: start; gap: 0; margin: 0; }
.poster-bignum .num { font-size: 48px; font-weight: 900; letter-spacing: 0.5px; line-height: 1; text-shadow: 0 4px 12px rgba(0,0,0,0.25); }
.poster-bignum .zone { font-weight: 900; letter-spacing: 1.6px; font-size: 24px; line-height: 0.9; text-transform: uppercase; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; text-shadow: 0 2px 6px rgba(0,0,0,0.25); transform: scaleY(0.9); transform-origin: center; }
.poster-bignum.hot .num { color: #f39b2f; }
.poster-bignum.hot .zone { color: #f39b2f; }
.poster-bignum.cold { justify-items: end; }
.poster-bignum.cold .num { color: #5aa3e6; }
.poster-bignum.cold .zone { color: #5aa3e6; }
.poster-left-col { position: absolute; left: 8%; top: 24%; width: 16%; display: grid; grid-auto-rows: auto; gap: 10px; z-index: 3; justify-items: center; }
.poster-left-col > * { position: static !important; width: 100%; z-index: auto; }
.poster-left-col .poster-card.small { display: grid; justify-items: center; row-gap: 0; }
.poster-left-col .poster-card.small img { width: 86%; height: auto; }
.poster-left-col .poster-cap { text-align: center; }
.poster-left-col .poster-bignum { width: 100%; display: grid; justify-items: center; margin: 0; }
.poster-right-col { position: absolute; right: 8%; top: 24%; width: 16%; display: grid; grid-auto-rows: auto; gap: 10px; z-index: 3; justify-items: center; }
.poster-right-col > * { position: static !important; width: 100%; z-index: auto; }
.poster-right-col .poster-card.small { display: grid; justify-items: center; row-gap: 0; }
.poster-right-col .poster-card.small img { width: 86%; height: auto; }
.poster-right-col .poster-cap { text-align: center; }
.poster-right-col .poster-bignum { width: 100%; display: grid; justify-items: center; margin: 0; }
.poster-bottom { position: absolute; left: 50%; bottom: 2%; transform: translateX(-50%); width: 64%; display: grid; grid-template-columns: 1fr 1.6fr 1fr; align-items: center; gap: 8px; z-index: 4; }
.poster-bottom .poster-card.small { position: static; width: 100%; display: grid; justify-items: center; align-content: center; }
.poster-bottom .poster-card.small img { width: 86%; height: auto; }
.poster-bottom .poster-cap { text-align: center; }
.poster-bottom .poster-specs { position: static; transform: none; left: auto; bottom: auto; width: 100%; padding: 10px 14px; border-radius: 18px; display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 12px; align-items: center; }
.poster-specs { position: absolute; left: 50%; bottom: 6%; transform: translateX(-50%); padding: 10px 14px; border-radius: 18px; background: transparent; border: 2px solid rgba(255,255,255,0.9); display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 12px; z-index: 4; overflow: hidden; box-sizing: border-box; }
.poster-specs .spec { display: grid; grid-template-columns: 26px 1fr; align-items: center; gap: 8px; background: transparent; border: 0; border-radius: 0; padding: 0; min-width: 0; }
.poster-specs .s-meta { display: grid; gap: 4px; }
.poster-specs .spec.wide { grid-column: span 1; }
.poster-specs .spec img { width: 26px; height: 26px; object-fit: contain; filter: none; opacity: 0.95; }
.poster-specs .s-label { color: rgba(255,255,255,0.9); font-size: 6.5px; letter-spacing: 0.4px; line-height: 1.05; display: inline-block; width: fit-content; max-width: 100%; padding-bottom: 1px; border-bottom: 1px solid rgba(255,255,255,0.9); }
.poster-specs .s-value { color: #ffffff; font-weight: 800; font-size: 10px; line-height: 1.05; word-break: keep-all; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-block; width: fit-content; max-width: 100%; padding-bottom: 1px; border-bottom: 1px solid rgba(255,255,255,0.9); }
.poster-specs .spec:last-child .s-value { font-size: 8px; }
/* 产品图片叠加样式 */
.product-photo-wrap { position: absolute; left: var(--product-x, 78%); top: var(--product-y, 22%); transform: translate(-50%, -50%); z-index: 5; pointer-events: auto; }
.product-photo { width: auto; height: auto; max-width: 380px; max-height: 420px; object-fit: contain; filter: drop-shadow(0px 5px 5px rgba(0,0,0,0.5)); cursor: pointer; transform-origin: center center; transition: transform 0.12s ease-out; display: block; }
.product-photo-tools { position: absolute; top: 8px; right: 8px; display: flex; gap: 6px; padding: 6px 8px; background: rgba(17, 24, 39, 0.65); border-radius: 10px; opacity: 0; pointer-events: none; transition: opacity 0.12s ease-out; }
.product-photo-wrap:hover .product-photo-tools { opacity: 1; pointer-events: auto; }
.photo-tool-btn {
  --el-button-text-color: #ffffff;
  --el-button-hover-text-color: #ffffff;
  --el-button-active-text-color: #ffffff;
  --el-button-bg-color: transparent;
  --el-button-hover-bg-color: rgba(255, 255, 255, 0.12);
  --el-button-active-bg-color: rgba(255, 255, 255, 0.18);
  --el-button-border-color: rgba(255, 255, 255, 0.2);
  --el-button-hover-border-color: rgba(255, 255, 255, 0.35);
  --el-button-active-border-color: rgba(255, 255, 255, 0.35);
  color: #fff;
  padding: 0 6px;
  min-height: 22px;
  height: 22px;
  line-height: 22px;
  font-weight: 600;
}
.right-col { padding-top: 230px; padding-left: 30px; position: relative; z-index: 3; }

/* Manual layout */
.manual-layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; min-height: 600px; align-items: start; }
.manual-toc { position: sticky; top: 16px; align-self: start; height: calc(100vh - 32px); padding: 12px; border: 1px solid #ebeef5; border-radius: 10px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.02); display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.toc-title { font-weight: 700; margin-bottom: 8px; }
.toc-scroll { overflow: auto; padding-right: 6px; flex: 1; min-height: 0; }
.toc-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
.toc-link { width: 100%; text-align: left; background: transparent; border: none; padding: 6px 8px; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background .15s ease; color: #000; }
.toc-link:hover { background: #f3f4f6; }
.toc-link.active { background: #eef6ff; }
.toc-page { color: #000; font-size: 12px; width: 40px; display: inline-flex; align-items: center; justify-content: center; font-variant-numeric: tabular-nums; }
.toc-link .ct-title { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.manual-pages { overflow: hidden; padding: 6px; display: flex; justify-content: center; align-items: flex-start; gap: 0; height: calc(100vh - 140px); box-sizing: border-box; position: relative; }
.toc-sub { list-style: none; padding-left: 10px; margin: 4px 0 0; display: grid; gap: 4px; }
.toc-link.sub { padding-left: 18px; font-size: 13px; }
.export-btn { margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
.zoom-toolbar { position: absolute; top: 6px; right: 6px; display: flex; align-items: center; gap: 6px; padding: 6px; background: rgba(255,255,255,0.9); border: 1px solid #ebeef5; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); z-index: 10; }
.zoom-text { min-width: 44px; text-align: center; font-weight: 600; color: #111827; }
.manual-page { width: 820px; aspect-ratio: 1/1.414; background: #fff; border: 1px solid #e5e7eb; margin: 0 auto; position: relative; transform: scale(var(--page-scale, 1)); transform-origin: top center; }
.page-inner { padding: 22px 26px 34px; display: grid; gap: 8px; }
.manual-page:not(.page-1) .page-inner { padding: 20px 40px 32px; }
.page-num-footer { position: absolute; right: 20px; bottom: 16px; padding: 6px 10px;border-radius: 8px; background: #fff; color: #111827; font-weight: 700; font-size: 14px; line-height: 1; min-width: 26px; text-align: center; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }

.page-tools { position: absolute; top: 8px; right: 12px; display: flex; gap: 6px; z-index: 2; }
.cover { position: absolute; inset: 0; color: #fff; }
.cover-logo { position: absolute; top: 60px; left: 40px; height: 26px; object-fit: contain; }
.cover-title { position: absolute; top: 170px; left: 56px; font-size: 90px; font-weight: 900; text-transform: uppercase; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.cover-product { position: absolute; left: 50%; bottom: 250px; transform: translateX(-50%); width: 70%; height: auto; object-fit: contain; filter: drop-shadow(0 12px 24px rgba(0,0,0,0.5)); }
.cover-bl { position: absolute; left: 36px; bottom: 56px; display: grid; gap: 4px; }
.cover-model { font-size: 50px; font-weight: 700; letter-spacing: 1px;font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.cover-size { font-size: 28px; opacity: 0.9;font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.cover-br { position: absolute; right: 48px; bottom: 70px; font-size: 10px; opacity: 0.9; }
.block .h1 { font-size: 24px; font-weight: 800; margin: 6px 0 8px; color: #4a90bf; letter-spacing: 0.5px; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.block .h1::after { content: ''; display: block; height: 1px; background: #4a90bf; border-radius: 2px; margin-top: 6px; }
.block .h2 { font-size: 16px; font-weight: 700; margin: 4px 0; color: #111827; }
.block .h3 { font-size: 16px; font-weight: 700; margin: 6px 0; }
.block .para { color: #374151; line-height: 1.6; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.block .list { color: #374151; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.block .list ul { list-style-type: disc !important; padding-left: 20px; margin: 6px 0; }
.block .list ul li { list-style-type: disc !important; list-style-position: outside; margin-bottom: 3px; }
.block .list ul li::marker { content: '• '; color: #374151; }
.block .list ol { padding-left: 20px; margin: 8px 0; }
.block .list ol li { margin-bottom: 4px; }
.figure { display: grid; justify-items: center; gap: 4px; }
.figure.full img { width: 100%; transform: rotate(var(--rotate, 0deg)); margin-top: var(--marginTop, 0px); }
.caption { color: #6b7280; font-size: 12px; }
.table-wrap table { width: 100%; border-collapse: collapse; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.table-wrap th, .table-wrap td { border: 1px solid #e5e7eb; padding: 5px 8px; font-size: 13px; text-align: left; }
.para.lead { font-weight: 800; color: #111827; }
.para.warning-text { font-size: 13px; line-height: 1.5; padding-left: 20px; white-space: pre-line; }
.steps-wrap { background: #f5f9fc; border: 1px solid #e3eef7; border-radius: 16px; padding: 14px 16px; display: grid; gap: 0; }
.steps { display: grid; }
.step-item { display: grid; grid-template-columns: 40px 1fr; align-items: start; gap: 10px; padding: 14px 4px; }
.step-item + .step-item { border-top: 2px dashed #c7d4df; }
.step-head .g4-badge { width: 28px; height: 28px; border: 3px solid #4a90bf; color: #1f6aa0; border-radius: 8px; background: #fff; font-weight: 800; display: inline-grid; place-items: center; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.step-text { color: #2f3b45; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.note { padding: 8px 10px; border-radius: 6px; font-size: 13px; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.caption { font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.note-info { background: #eff6ff; color: #1d4ed8; }
.note-warning { background: #fff7ed; color: #b45309; }
.divider { border: 0; border-top: 1px solid #e5e7eb; margin: 6px 0; }

.list.safety-lines ul { list-style: none; padding-left: 0; margin: 0; }
.list.safety-lines li { margin: 6px 0; }

.list.safety-box { background: #eef1f4; border-radius: 10px; padding: 14px 16px; }
.list.safety-box ul { margin: 0; padding-left: 18px; }
.list.safety-box li:first-child { list-style: none; margin-left: -18px; }
.list.safety-box li { margin: 6px 0; }

.appendix-bar { background: #a3a3a3; color: #ffffff; border-radius: 999px; padding: 10px 14px; text-align: center; font-weight: 800; letter-spacing: 0.8px; margin: 4px 0 10px; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }

.list.warranty-box { background: #eef1f4; border-radius: 10px; padding: 12px 16px; }
.list.warranty-box ul { list-style: none; padding-left: 0; margin: 0; }
.list.warranty-box li { margin: 8px 0; }
.list.warranty-box li strong { display: block; font-weight: 800; margin-bottom: 4px; }

.warranty-title { text-align: center; font-weight: 900; font-size: 20px; letter-spacing: 0.8px; margin: 10px 0 6px; color: #4a90bf; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.warranty-title::after { content: ''; display: block; height: 1px; background: #4a90bf; border-radius: 2px; margin-top: 6px; }

.list.warranty-lines ul { list-style: none; padding-left: 0; margin: 0; }
.list.warranty-lines li { padding: 10px 12px; margin: 10px 0; }
.list.warranty-lines li { background: transparent; }
.list.warranty-lines li strong { display: block; font-weight: 800; margin-bottom: 4px; }
.list.warranty-lines li::marker { content: '' !important; }

.img-float.center { left: 50%; top: 56%; transform: translate(-50%, -50%); width: auto; }
.img-float.center img { width: 520px; max-width: 520px; opacity: 0.07; filter: brightness(0) saturate(100%); }

/* Floating images on the page (e.g., product and cold icon) */
.img-float { position: absolute; pointer-events: none; }
.img-float img { width: 100%; height: auto; display: block; }
.img-float.bottom-left { left: 180px; bottom: 140px; width: 400px!important;}
.img-float.bottom-right { right: 80px; bottom: 350px; width: 100px!important;}

/* Grid4 materials box */
.grid4-wrap { background: #f5f9fc; border: 1px solid #e3eef7; border-radius: 18px; padding: 18px 20px; position: relative; }
.grid4 { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 28px 36px; position: relative; }
.grid4::after { content: ''; position: absolute; left: 12px; right: 12px; top: 50%; height: 0; border-top: 2px dashed #c7d4df; transform: translateY(-50%); }
.grid4-item { display: grid; gap: 10px; }
.g4-head { display: flex; align-items: center; gap: 8px; }
.g4-badge { display: inline-grid; place-items: center; width: 28px; height: 28px; border: 3px solid #4a90bf; color: #1f6aa0; border-radius: 8px; background: #fff; font-weight: 800; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.g4-title { font-weight: 700; color: #374151; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.g4-img { width: 100%; aspect-ratio: 1 / 1; border-radius: 14px; overflow: hidden; background: #fff; box-shadow: 0 6px 18px rgba(0,0,0,0.08); }
.g4-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.g4-img-ph { width: 100%; height: 100%; display: grid; place-items: center; color: #9ca3af; background: repeating-linear-gradient(45deg,#f3f4f6 0 10px,#e5e7eb 10px 20px); }

/* Specification box with blue gradient background */
.spec-box { position: relative; background: linear-gradient(135deg, #2563a8 0%, #5b8fc4 50%, #87a9cd 100%); border-radius: 16px; padding: 24px; min-height: auto; margin: 8px 0; color: #fff; box-shadow: 0 6px 20px rgba(0,0,0,0.15); font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; box-sizing: border-box; width: 100%; max-width: 100%; }
.spec-box-inner { display: grid; grid-template-columns: minmax(160px,1fr) auto minmax(160px,1fr); column-gap: 28px; row-gap: 14px; align-items: stretch; }
.spec-col { display: grid; gap: 12px; width: auto; }
.spec-col.left { justify-self: start; }
.spec-col.right { justify-self: end; text-align: right; }
.spec-card { background: rgba(255,255,255,0.08); border-radius: 12px; padding: 10px 12px; width: 100%; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08), 0 6px 14px rgba(0,0,0,0.12); }
.spec-card .spec-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; line-height: 1.3; }
.spec-card .spec-text { font-size: 13px; line-height: 1.4; opacity: 0.95; }
.spec-box .spec-center { position: relative; top: auto; left: auto; transform: none; width: 220px; z-index: 1; justify-self: center; align-self: center; }
.spec-box .spec-center img { width: 100%; height: auto; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); display: block; }
/* remove obsolete absolute rules for previous implementation */
.spec-center { position: relative; top: auto; left: auto; transform: none; width: 300px; z-index: 1; justify-self: center; }
.spec-center img { width: 100%; height: auto; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); }

/* Grid2 layout for specification page */
.grid2 { display: grid; grid-template-columns: 2fr 1fr; gap: 24px 30px; align-items: start; margin: 12px 0; }
.grid2-item img { width: 100%; height: auto; object-fit: contain; border-radius: 8px; }
.grid2 .list ol { padding-left: 20px; margin: 0; display: grid; gap: 8px; }
.grid2 .list ol li { color: #374151; font-size: 15px; line-height: 1.5; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }

/* Contents (TOC) page styling */
.contents { display: grid; gap: 12px; margin-top: 4px; }
.tocline { display: flex; align-items: center; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; color: #000; }
.tocline .ct-title { white-space: normal; }
.tocline .ct-dots { flex: 1; border-bottom: 2px dotted #a9c2d6; margin: 0 8px; transform: translateY(-4px); }
.tocline .ct-page { width: 40px; display: flex; align-items: center; justify-content: center; color: #000; font-weight: 700; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; font-variant-numeric: tabular-nums; }
.tocline.lvl-0 { font-weight: 700; }
.tocline.lvl-1 { padding-left: 28px; font-weight: 600; opacity: 0.95; }

/* Callout (warning/error) */
.callout { display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: start; }
.callout + .callout { margin-top: 8px; }
.callout-icon { width: 26px; height: 26px; object-fit: contain; margin-top: 2px; }
.callout-text { color: #2f3b45; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.callout-text strong { font-weight: 700; }
.callout-align { margin-left: 36px; }
.special-note .callout-text { color: #111827; }

/* Troubleshooting sections */
.ts-section { display: grid; grid-template-columns: 36px 1fr; gap: 10px; align-items: start; margin-top: 8px; }
.ts-section + .ts-section { margin-top: 28px; padding-top: 22px; border-top: 2px dashed #c7d4df; }
.ts-num { width: 28px; height: 28px; border: 3px solid #4a90bf; color: #1f6aa0; border-radius: 8px; background: #fff; font-weight: 800; display: inline-grid; place-items: center; font-family: 'AgencyFB-Bold', 'Agency FB', Impact, 'Segoe UI', Arial, sans-serif; }
.ts-card { background: #f5f9fc; border: 1px solid #e3eef7; border-radius: 16px; padding: 16px; overflow: hidden; }
.ts-grid { display: grid; grid-template-columns: 1.2fr 0.9fr 1.1fr; gap: 16px; align-items: start; }
.ts-img { width: 100%; height: auto; display: block; border-radius: 12px; background: #fff; box-shadow: 0 6px 12px rgba(0,0,0,0.08); object-fit: contain; }
.ts-mid { display: grid; justify-items: center; align-items: center; }

/* Magnifier */
.mag { position: relative; display: grid; grid-template-columns: 1fr; justify-items: center; }
.mag-ring { width: 260px; height: 260px; border-radius: 50%; border: 6px solid #d1d9e6; position: relative; display: grid; place-items: center; background: radial-gradient(ellipse at top, #eef3f8 0%, #ffffff 60%); overflow: hidden; }
.mag-shot { width: 120%; height: auto; object-fit: cover; z-index: 1; }
.mag-lines { position: absolute; top: 16px; left: 50%; transform: translateX(-50%); width: 74%; text-align: center; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; color: #444; z-index: 2; display: grid; gap: 4px; }
.mag-title { color: #f59e0b; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 2px; }
.mag-title .bracket { color: #f59e0b; opacity: 0.9; }
.mag-serial { font-weight: 800; color: #2b3640; margin-bottom: 2px; }
.mag-qr { width: 72px; height: 72px; object-fit: contain; display: block; margin: 6px auto 6px; }
.mag-text { font-size: 8px; line-height: 1; color: #2b3640; }

/* Troubleshooting table */
.tb-wrap { display: grid; gap: 8px; margin-top: 6px; font-family: 'SourceSansPro-Regular', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif; }
.tb-header { display: grid; grid-template-columns: 3fr 7fr; background: #b9cde3; color: #ffffff; font-weight: 700; border-radius: 6px; overflow: hidden; align-items: center; min-height: 28px; }
.tb-header .tb-col { padding: 8px 12px; color: #ffffff; }
.tb-col-left { border-right: none; }
.tb-body { display: grid; gap: 10px; }
.tb-group-title { color: #374151; font-weight: 700; margin: 6px 0 4px; }
.tb-row { display: grid; grid-template-columns: 3fr 7fr; border-radius: 6px; background: #e3edf7; overflow: hidden; }
.tb-row.alt { background: #ffffff; border: none; }
.tb-cell { padding: 10px 12px; color: #2f3b45; line-height: 1.45; }
.tb-left { font-weight: 700; }
.tb-right { background: transparent; }
.tb-sol-list { display: grid; gap: 8px; }
.tb-sol-list ul { margin: 0; padding-left: 20px; }
.tb-sol-list li { list-style: disc; margin: 6px 0; }
.tb-desc { margin: 0; }

@media print {
  @page { size: A4; margin: 0; }
  html, body { margin: 0 !important; padding: 0 !important; }
  .topbar, .product-header, .manual-toc { display: none !important; }
  .page { padding: 0 !important; }
  .panel { padding: 0 !important; border: 0 !important; border-radius: 0 !important; }
  .content { margin: 0 !important; }
  .manual-layout { grid-template-columns: 1fr !important; }
  .manual-pages { display: block !important; overflow: visible !important; height: auto !important; padding: 0 !important; }
  .manual-page { display: block !important; width: 210mm !important; height: 297mm !important; margin: 0 !important; border: 0 !important; box-shadow: none !important; box-sizing: border-box !important; }
  .page-num-footer { border-color: #e5e7eb !important; background: #fff !important; }
  /* Keep on-screen paddings/margins exactly; only ensure colors are preserved */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
