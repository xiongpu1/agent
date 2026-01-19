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
        <img class="thumb" :src="imgUrl" :alt="name" @error="onImgError" />
        <div class="meta">
          <div class="name">{{ name }}</div>
          <div class="sub" v-if="productName">产品：{{ productName }}</div>
          <div class="sub" v-if="bom">
            BOM：{{ bom }}
            <el-button link type="primary" size="small" @click="openBomDetailDialog">展示配置</el-button>
          </div>
        </div>
      </div>

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
            <el-button size="small" type="success" @click="exportPromoPdf">导出为PDF</el-button>
            <el-button size="small" type="warning" @click="exportPromoPdfEditable">导出可编辑PDF</el-button>
            <el-button size="small" :type="promoEditMode ? 'danger' : 'primary'" plain @click="togglePromoEditMode">
              {{ promoEditMode ? '退出编辑模式' : '进入编辑模式' }}
            </el-button>
            <el-button size="small" type="primary" :disabled="!promoEditMode" @click="savePromoLayoutToBackend">保存布局/样式</el-button>
            <el-button size="small" type="info" @click="saveSpecsheetToDb">保存修改至数据库（传json）</el-button>
            <el-button size="small" type="info" plain @click="openRagChunksDialog">查看 RAG 来源</el-button>
            <el-button size="small" type="primary" plain @click="handleGenerateSpecsheetOcr">生成规格页</el-button>
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
            <div
              class="promo-top promo-block"
              data-layout-id="promoTop"
              :class="promoBlockClass('promoTop')"
              :style="mergePromoBlockStyle('promoTop', { backgroundImage: `url(${backgroundSrc})` })"
              @pointerdown="onPromoBlockPointerDown($event, 'promoTop')"
            >
              <!-- 仅负责背景图片更换的悬浮提示与点击层，不包含 Logo 区域 -->
              <el-tooltip :content="BACKGROUND_UPLOAD_TIPS" placement="top">
                <div class="promo-top-bg-layer" @click="onClickBackground"></div>
              </el-tooltip>
              <el-tooltip :content="LOGO_UPLOAD_TIPS" placement="bottom">
                <div
                  class="logo-card promo-block"
                  data-layout-id="logoCard"
                  :class="promoBlockClass('logoCard')"
                  :style="mergePromoBlockStyle('logoCard')"
                  @pointerdown="onPromoBlockPointerDown($event, 'logoCard')"
                  @click.stop="onClickLogo"
                >
                  <div class="logo-mark">
                    <img :src="logoSrc" alt="" width="45" height="45" />
                  </div>
                </div>
              </el-tooltip>
            </div>

            <!-- 产品图片（叠加在顶部与正文之间） -->
            <el-tooltip :content="PRODUCT_UPLOAD_TIPS" placement="top">
              <img
                class="product-photo promo-block"
                data-layout-id="productPhoto"
                :class="promoBlockClass('productPhoto')"
                :src="productPhotoSrc"
                alt="product"
                @click="onClickProduct"
                @pointerdown="onPromoBlockPointerDown($event, 'productPhoto')"
                :style="mergePromoBlockStyle('productPhoto', { '--product-x': productAnchor.x, '--product-y': productAnchor.y, transform: 'translate(-50%, -50%)' })"
              />
            </el-tooltip>

            <!-- 内容区域 -->
            <div class="promo-body">
              <!-- 左列 -->
              <div class="col">
                <div
                  class="product-title promo-block"
                  data-layout-id="productTitle"
                  :class="promoBlockClass('productTitle')"
                  :style="mergePromoBlockStyle('productTitle')"
                  @pointerdown="onPromoBlockPointerDown($event, 'productTitle')"
                  contenteditable="true"
                  data-placeholder="Vastera"
                  @input="onEditTextWithCaret($event, 'productTitle')"
                  v-text="promoData.productTitle"
                ></div>
                <div class="section">
                  <div class="h2" data-placeholder="Feature">Feature</div>
                  <div class="icons">
                    <div class="icon promo-block" data-layout-id="featureCapacity" :class="promoBlockClass('featureCapacity')" :style="mergePromoBlockStyle('featureCapacity')" @pointerdown="onPromoBlockPointerDown($event, 'featureCapacity')">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.capacity" alt="Capacity" width="35" height="35" @click="openFeatureIconDialog('capacity')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Capacity</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="1" @input="onEditTextWithCaret($event, 'features.capacity')" v-text="promoData.features.capacity"></div>
                      </div>
                    </div>


                    <div class="icon promo-block" data-layout-id="featureJets" :class="promoBlockClass('featureJets')" :style="mergePromoBlockStyle('featureJets')" @pointerdown="onPromoBlockPointerDown($event, 'featureJets')">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.jets" alt="Jets" width="35" height="35" @click="openFeatureIconDialog('jets')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Jets</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="0" @input="onEditTextWithCaret($event, 'features.jets')" v-text="promoData.features.jets"></div>
                      </div>
                    </div>

                    <div class="icon promo-block" data-layout-id="featurePumps" :class="promoBlockClass('featurePumps')" :style="mergePromoBlockStyle('featurePumps')" @pointerdown="onPromoBlockPointerDown($event, 'featurePumps')">
                      <el-tooltip :content="FEATURE_ICON_UPLOAD_TIPS" placement="top">
                        <img :src="featureIcons.pumps" alt="Pumps" width="35" height="35" @click="openFeatureIconDialog('pumps')" />
                      </el-tooltip>
                      <div class="icon-text">
                        <div class="icon-t">Pumps</div>
                        <div class="icon-num" contenteditable="true" data-placeholder="2" @input="onEditTextWithCaret($event, 'features.pumps')" v-text="promoData.features.pumps"></div>
                      </div>
                    </div>
                    
                  </div>
                  <div class="measurements-row promo-block" data-layout-id="featureMeasurements" :class="promoBlockClass('featureMeasurements')" :style="mergePromoBlockStyle('featureMeasurements')" @pointerdown="onPromoBlockPointerDown($event, 'featureMeasurements')">
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

                <div class="section promo-block" v-if="promoSectionTitles.premium" data-layout-id="sectionPremium" :class="promoBlockClass('sectionPremium')" :style="mergePromoBlockStyle('sectionPremium')" @pointerdown="onPromoBlockPointerDown($event, 'sectionPremium')">
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

                <div class="section promo-block" v-if="promoSectionTitles.insulation" data-layout-id="sectionInsulation" :class="promoBlockClass('sectionInsulation')" :style="mergePromoBlockStyle('sectionInsulation')" @pointerdown="onPromoBlockPointerDown($event, 'sectionInsulation')">
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

                <div class="section promo-block" v-if="promoSectionTitles.extra" data-layout-id="sectionExtra" :class="promoBlockClass('sectionExtra')" :style="mergePromoBlockStyle('sectionExtra')" @pointerdown="onPromoBlockPointerDown($event, 'sectionExtra')">
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
                <div class="section promo-block" v-if="promoSectionTitles.specifications" data-layout-id="sectionSpecifications" :class="promoBlockClass('sectionSpecifications')" :style="mergePromoBlockStyle('sectionSpecifications')" @pointerdown="onPromoBlockPointerDown($event, 'sectionSpecifications')">
                  <div
                    class="h2"
                    data-placeholder="Specifications"
                    contenteditable="true"
                    @blur="onEditSectionTitle($event, 'specifications')"
                    v-html="promoSectionTitles.specifications"
                  ></div>
                  <ul class="specs-list">
                    <li v-for="(specObj, idx) in promoData.Specifications" :key="'spec-'+idx" class="specs-item">
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

                <div class="section promo-block" v-if="promoSectionTitles.smartWater" data-layout-id="sectionSmartWater" :class="promoBlockClass('sectionSmartWater')" :style="mergePromoBlockStyle('sectionSmartWater')" @pointerdown="onPromoBlockPointerDown($event, 'sectionSmartWater')">
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
            <div class="promo-footer promo-block" data-layout-id="promoFooter" :class="promoBlockClass('promoFooter')" :style="mergePromoBlockStyle('promoFooter')" @pointerdown="onPromoBlockPointerDown($event, 'promoFooter')">
              <div class="footnote">* Specifications are subject to change.</div>
            </div>

            <div v-if="promoEditMode" class="promo-props-panel" @pointerdown.stop>
              <div class="props-title">编辑属性</div>
              <div v-if="!selectedPromoBlockId" class="props-empty">请选择一个区块</div>
              <div v-else class="props-body">
                <div class="props-row">
                  <div class="props-label">区块</div>
                  <div class="props-value">{{ selectedPromoBlockId }}</div>
                </div>

                <div class="props-row">
                  <div class="props-label">字体</div>
                  <el-select v-model="selectedBlockStyle.fontFamily" size="small" style="width: 160px" @change="applySelectedBlockStyle">
                    <el-option v-for="f in promoFontCandidates" :key="f" :label="f" :value="f" />
                  </el-select>
                </div>

                <div class="props-row">
                  <div class="props-label">字号</div>
                  <el-input-number v-model="selectedBlockStyle.fontSize" size="small" :min="8" :max="120" @change="applySelectedBlockStyle" />
                </div>

                <div class="props-row">
                  <div class="props-label">字重</div>
                  <el-select v-model="selectedBlockStyle.fontWeight" size="small" style="width: 160px" @change="applySelectedBlockStyle">
                    <el-option label="400" :value="400" />
                    <el-option label="600" :value="600" />
                    <el-option label="700" :value="700" />
                    <el-option label="800" :value="800" />
                  </el-select>
                </div>

                <div class="props-row">
                  <div class="props-label">颜色</div>
                  <el-color-picker v-model="selectedBlockStyle.color" size="small" @change="applySelectedBlockStyle" />
                </div>

                <div class="props-row">
                  <div class="props-label">对齐</div>
                  <el-select v-model="selectedBlockStyle.textAlign" size="small" style="width: 160px" @change="applySelectedBlockStyle">
                    <el-option label="left" value="left" />
                    <el-option label="center" value="center" />
                    <el-option label="right" value="right" />
                  </el-select>
                </div>

                <div class="props-row">
                  <el-button size="small" @click="resetSelectedBlockTransform">重置位置</el-button>
                  <el-button size="small" @click="clearSelectedBlockStyle">清除样式</el-button>
                </div>
              </div>
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
            <div v-else>
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
            </div>
          </el-dialog>

          <el-dialog v-model="specsheetResultDialogVisible" title="规格页 API 返回" width="960px">
            <pre style="white-space: pre-wrap; word-break: break-word; max-height: 70vh; overflow: auto;">{{ specsheetResultPayload }}</pre>
          </el-dialog>

          <el-dialog v-model="bomDetailDialogVisible" title="BOM 配置明细" width="720px">
            <div v-if="!bomDetails || !(bomDetails.segments || []).length">暂无可展示的 BOM 配置</div>
            <div v-else>
              <el-card v-for="(seg, idx) in bomDetails.segments" :key="seg.key + '-' + idx" style="margin-bottom: 12px" shadow="never">
                <div style="font-weight: 600; margin-bottom: 6px">{{ seg.label }}</div>
                <div>
                  <span style="display: inline-block; min-width: 56px; font-weight: 700">{{ seg.value }}</span>
                  <span>{{ seg.meaning }}</span>
                </div>
              </el-card>
            </div>
          </el-dialog>
        </div>
      </div>
      <div v-else-if="tab === 'poster'" class="panel">
        <div class="title row">
          <div>海报</div>
          <div class="row gap12">
            <el-button size="small" type="primary" @click="exportPoster">导出为图片</el-button>
            <el-button size="small" type="success" @click="exportPosterPdf">导出为PDF</el-button>
            <el-button size="small" type="info" @click="savePosterToDb">保存修改至数据库</el-button>
            <el-button size="small" type="info" plain>查看 RAG 来源</el-button>
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
            </div>
            <div class="page-ops">
              <div class="ops-title">当前页操作</div>
              <div class="ops-current">当前页：{{ displayTocPage(currentPageIndex + 1) }} · {{ deriveTitle(manualPages[currentPageIndex] || {}) }}</div>
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
              :key="'page-'+(currentPageIndex+1)"
              :class="['manual-page', 'page-'+(currentPageIndex+1)]"
              ref="currentPageRef"
            >
              <div class="page-inner">
                <div v-if="!currentPage.blocks || currentPage.blocks.length === 0" class="block">
                  <h1 class="h1" contenteditable="true" @input="onEditManualPageTitle($event)" v-text="currentPage.customTitle || deriveTitle(currentPage)"></h1>
                </div>
                <div v-for="(blk, bIdx) in currentPage.blocks" :key="'blk-'+(currentPageIndex+1)+'-'+bIdx" class="block">
                  <template v-if="blk.type === 'cover'">
                    <div class="cover" :style="coverStyle(blk)" @click.self="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'backSrc'))">
                      <img class="cover-logo" src="/instruction_book/logo.svg" alt="logo" />
                      <div class="cover-title" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'title'))" v-text="blk.title"></div>
                      <img class="cover-product" :src="blk.productSrc || '/instruction_book/product.png'" alt="product" @click="pickManualImage(makeManualPath(currentPageIndex, bIdx, 'productSrc'))" />
                      <div class="cover-bl">
                        <div class="cover-model" contenteditable="true" @input="onEditManualWithCaret($event, makeManualPath(currentPageIndex, bIdx, 'model'))">{{ blk.model || 'Massern' }}</div>
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
            <input ref="manualImageInputRef" type="file" accept="image/*" style="display:none" @change="onPickManualImage" />
          </main>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import { useRoute, useRouter } from 'vue-router'
import { Promotion, Picture, Document } from '@element-plus/icons-vue'
import { BOM_CONFIG } from '@/constants/bomOptions'

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id)
const productName = computed(() => route.query.productName || '')
const name = computed(() => route.query.name || productName.value || `产品${route.params.id}`)
const image = computed(() => route.query.image || 'placeholder.jpg')
const bom = computed(() => route.query.bom || '')

const getFirstQueryValue = (value) => (Array.isArray(value) ? value[0] : value)

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

const promoEditMode = ref(false)
const promoLayout = ref({
  version: 1,
  blocks: {},
  overrides: {},
})

const promoFontCandidates = [
  'AgencyFB-Bold',
  'SourceSansPro-Regular',
  'SourceSansPro-Semibold',
  'SourceSansPro-Bold',
  'Arial',
  'Helvetica',
  'Times New Roman',
  'Georgia',
  'Verdana',
  'Tahoma',
]

const selectedPromoBlockId = ref('')
const selectedBlockStyle = ref({
  fontFamily: '',
  fontSize: null,
  fontWeight: null,
  color: '',
  textAlign: '',
})

const promoBlockClass = (id) => {
  return {
    'promo-editable': promoEditMode.value,
    'promo-selected': promoEditMode.value && selectedPromoBlockId.value === id,
  }
}

const _readBlockLayout = (id) => {
  const blocks = promoLayout.value?.blocks && typeof promoLayout.value.blocks === 'object' ? promoLayout.value.blocks : {}
  const b = blocks?.[id]
  return b && typeof b === 'object' ? b : null
}

const mergePromoBlockStyle = (id, baseStyle = {}) => {
  if (!promoEditMode.value) return baseStyle
  const b = _readBlockLayout(id)
  const tx = typeof b?.tx === 'number' ? b.tx : 0
  const ty = typeof b?.ty === 'number' ? b.ty : 0
  const style = b?.style && typeof b.style === 'object' ? b.style : {}
  const baseTransform = baseStyle && typeof baseStyle === 'object' ? (baseStyle.transform || '') : ''
  const baseTransformStr = typeof baseTransform === 'string' ? baseTransform.trim() : ''
  const hasDrag = !!tx || !!ty
  const dragTransform = hasDrag ? `translate(${tx}px, ${ty}px)` : ''
  const mergedTransform = hasDrag
    ? (baseTransformStr ? `${baseTransformStr} ${dragTransform}` : dragTransform)
    : baseTransformStr
  const out = {
    ...baseStyle,
    ...style,
    touchAction: 'none',
  }
  if (mergedTransform) out.transform = mergedTransform
  return out
}

const _ensureBlockLayout = (id) => {
  if (!promoLayout.value || typeof promoLayout.value !== 'object') {
    promoLayout.value = { version: 1, blocks: {}, overrides: {} }
  }
  if (!promoLayout.value.blocks || typeof promoLayout.value.blocks !== 'object') {
    promoLayout.value.blocks = {}
  }
  if (!promoLayout.value.blocks[id] || typeof promoLayout.value.blocks[id] !== 'object') {
    promoLayout.value.blocks[id] = { tx: 0, ty: 0, style: {} }
  }
  if (!promoLayout.value.blocks[id].style || typeof promoLayout.value.blocks[id].style !== 'object') {
    promoLayout.value.blocks[id].style = {}
  }
  return promoLayout.value.blocks[id]
}

const _syncSelectedStyleFromLayout = (id) => {
  const b = _readBlockLayout(id)
  const s = b?.style && typeof b.style === 'object' ? b.style : {}
  selectedBlockStyle.value = {
    fontFamily: s.fontFamily || '',
    fontSize: typeof s.fontSize === 'number' ? s.fontSize : null,
    fontWeight: typeof s.fontWeight === 'number' ? s.fontWeight : null,
    color: s.color || '',
    textAlign: s.textAlign || '',
  }
}

const applySelectedBlockStyle = () => {
  const id = selectedPromoBlockId.value
  if (!promoEditMode.value || !id) return
  const b = _ensureBlockLayout(id)
  const s = { ...(b.style || {}) }
  const next = selectedBlockStyle.value || {}

  if (next.fontFamily) s.fontFamily = next.fontFamily
  else delete s.fontFamily
  if (typeof next.fontSize === 'number') s.fontSize = next.fontSize
  else delete s.fontSize
  if (typeof next.fontWeight === 'number') s.fontWeight = next.fontWeight
  else delete s.fontWeight
  if (next.color) s.color = next.color
  else delete s.color
  if (next.textAlign) s.textAlign = next.textAlign
  else delete s.textAlign

  b.style = s
}

const resetSelectedBlockTransform = () => {
  const id = selectedPromoBlockId.value
  if (!promoEditMode.value || !id) return
  const b = _ensureBlockLayout(id)
  b.tx = 0
  b.ty = 0
}

const clearSelectedBlockStyle = () => {
  const id = selectedPromoBlockId.value
  if (!promoEditMode.value || !id) return
  const b = _ensureBlockLayout(id)
  b.style = {}
  _syncSelectedStyleFromLayout(id)
}

const _applyPromoOverrides = () => {
  const o = promoLayout.value?.overrides && typeof promoLayout.value.overrides === 'object' ? promoLayout.value.overrides : {}
  const promo = o.promoData && typeof o.promoData === 'object' ? o.promoData : {}
  const titles = o.sectionTitles && typeof o.sectionTitles === 'object' ? o.sectionTitles : {}

  Object.keys(promo).forEach((path) => {
    const val = promo[path]
    if (typeof path !== 'string') return

    // Special-case Specifications because it's an array of single-key objects.
    const m = path.match(/^Specifications\.(\d+)\.(.+)$/)
    if (m) {
      const idx = parseInt(m[1], 10)
      const key = m[2]
      if (Number.isFinite(idx) && idx >= 0 && Array.isArray(promoData.value.Specifications) && key) {
        if (promoData.value.Specifications[idx] && typeof promoData.value.Specifications[idx] === 'object') {
          promoData.value.Specifications[idx] = { [key]: typeof val === 'string' ? val : (val ?? '') }
        }
      }
      return
    }

    const segs = path.split('.')
    let obj = promoData.value
    for (let i = 0; i < segs.length - 1; i++) {
      const k = segs[i]
      if (!(k in obj) || typeof obj[k] !== 'object') obj[k] = {}
      obj = obj[k]
    }
    obj[segs[segs.length - 1]] = typeof val === 'string' ? val : (val ?? '')
  })

  if (Object.keys(titles).length) {
    promoSectionTitles.value = {
      ...promoSectionTitles.value,
      ...titles,
    }
  }
}

const _setPromoOverride = (path, value) => {
  if (!promoEditMode.value) return
  if (!path) return
  if (!promoLayout.value || typeof promoLayout.value !== 'object') {
    promoLayout.value = { version: 1, blocks: {}, overrides: {} }
  }
  if (!promoLayout.value.overrides || typeof promoLayout.value.overrides !== 'object') {
    promoLayout.value.overrides = {}
  }
  if (!promoLayout.value.overrides.promoData || typeof promoLayout.value.overrides.promoData !== 'object') {
    promoLayout.value.overrides.promoData = {}
  }
  promoLayout.value.overrides.promoData[path] = typeof value === 'string' ? value : (value ?? '')
}

const _setSectionTitleOverride = (key, html) => {
  if (!promoEditMode.value) return
  if (!key) return
  if (!promoLayout.value || typeof promoLayout.value !== 'object') {
    promoLayout.value = { version: 1, blocks: {}, overrides: {} }
  }
  if (!promoLayout.value.overrides || typeof promoLayout.value.overrides !== 'object') {
    promoLayout.value.overrides = {}
  }
  if (!promoLayout.value.overrides.sectionTitles || typeof promoLayout.value.overrides.sectionTitles !== 'object') {
    promoLayout.value.overrides.sectionTitles = {}
  }
  promoLayout.value.overrides.sectionTitles[key] = typeof html === 'string' ? html : (html ?? '')
}

const togglePromoEditMode = async () => {
  promoEditMode.value = !promoEditMode.value
  selectedPromoBlockId.value = ''
  if (!promoEditMode.value) return

  if (!productName.value || !bom.value) {
    window.alert('缺少产品名称或 BOM 版本，无法进入编辑模式。')
    promoEditMode.value = false
    return
  }

  try {
    const { getSavedManualSpecsheetLayout } = await import('@/services/api')
    const saved = await getSavedManualSpecsheetLayout(productName.value, bom.value)
    if (saved && typeof saved === 'object') {
      promoLayout.value = saved
    } else {
      promoLayout.value = { version: 1, blocks: {}, overrides: {} }
    }
    _applyPromoOverrides()
  } catch (e) {
    promoLayout.value = { version: 1, blocks: {}, overrides: {} }
  }
}

const savePromoLayoutToBackend = async () => {
  if (!productName.value || !bom.value) {
    window.alert('缺少产品名称或 BOM 版本，无法保存布局。')
    return
  }
  if (!promoEditMode.value) return
  try {
    const { saveManualSpecsheetLayout } = await import('@/services/api')
    await saveManualSpecsheetLayout(productName.value, bom.value, promoLayout.value || {}, null)
    window.alert('布局/样式已保存。')
  } catch (e) {
    window.alert(`保存布局失败: ${e?.message || '未知错误'}`)
  }
}

const _dragState = ref({
  active: false,
  moved: false,
  id: '',
  pointerId: 0,
  pointerType: '',
  startX: 0,
  startY: 0,
  baseTx: 0,
  baseTy: 0,
})

const onPromoBlockPointerDown = (evt, id) => {
  if (!promoEditMode.value) return
  if (!evt || evt.button === 2) return

  selectedPromoBlockId.value = id
  _syncSelectedStyleFromLayout(id)

  // Editing mode: click selects. Dragging requires holding Alt (mouse).
  if ((evt.pointerType === 'mouse' || !evt.pointerType) && !evt.altKey) {
    return
  }

  const isEditingText = evt.target && (evt.target.isContentEditable || evt.target.closest?.('[contenteditable="true"]'))
  if (isEditingText) return

  const b = _ensureBlockLayout(id)
  _dragState.value = {
    active: true,
    moved: false,
    id,
    pointerId: evt.pointerId,
    pointerType: evt.pointerType || '',
    startX: evt.clientX,
    startY: evt.clientY,
    baseTx: typeof b.tx === 'number' ? b.tx : 0,
    baseTy: typeof b.ty === 'number' ? b.ty : 0,
  }
  try {
    evt.currentTarget && evt.currentTarget.setPointerCapture && evt.currentTarget.setPointerCapture(evt.pointerId)
  } catch (e) {}
  evt.preventDefault()
}

const _onPromoPointerMove = (evt) => {
  if (!promoEditMode.value) return
  const st = _dragState.value
  if (!st?.active) return
  if (evt.pointerId !== st.pointerId) return

  // Mouse: if button is no longer pressed, stop dragging to avoid drift.
  if ((st.pointerType === 'mouse' || evt.pointerType === 'mouse') && evt.buttons === 0) {
    _dragState.value = { active: false, moved: false, id: '', pointerId: 0, pointerType: '', startX: 0, startY: 0, baseTx: 0, baseTy: 0 }
    return
  }

  const dx = evt.clientX - st.startX
  const dy = evt.clientY - st.startY

  if (!st.moved) {
    if (Math.hypot(dx, dy) < 10) return
    st.moved = true
  }

  const b = _ensureBlockLayout(st.id)
  b.tx = st.baseTx + dx
  b.ty = st.baseTy + dy
}

const _onPromoPointerUp = (evt) => {
  const st = _dragState.value
  if (!st?.active) return
  if (evt.pointerId !== st.pointerId) return
  _dragState.value = { active: false, moved: false, id: '', pointerId: 0, pointerType: '', startX: 0, startY: 0, baseTx: 0, baseTy: 0 }
}

onMounted(() => {
  window.addEventListener('pointermove', _onPromoPointerMove)
  window.addEventListener('pointerup', _onPromoPointerUp)
  window.addEventListener('pointercancel', _onPromoPointerUp)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', _onPromoPointerMove)
  window.removeEventListener('pointerup', _onPromoPointerUp)
  window.removeEventListener('pointercancel', _onPromoPointerUp)
})

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
const hasTransferredDocs = computed(
  () =>
    productDocsFromRoute.value.length > 0 ||
    accessoryDocGroupsFromRoute.value.some((group) => group.documents.length > 0)
)

const bomDetailDialogVisible = ref(false)
const bomDetails = ref(null)
const bomTypeForParsing = ref('outdoor')

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

const deriveBomDetailsFromCode = (code = '') => {
  const normalized = String(code || '').trim().toUpperCase()
  if (!normalized) return null
  const type = bomTypeForParsing.value || 'outdoor'
  const configSections = BOM_CONFIG?.[type] || BOM_CONFIG?.outdoor || []
  const sections = flattenBomSections(configSections)
  if (!sections.length) return null
  const totalDigits = computeTotalDigits(sections)
  if (totalDigits !== normalized.length) return null

  const segments = []
  let cursor = 0
  for (const section of sections) {
    const digits = section.digits || 0
    if (!digits) continue
    const value = normalized.slice(cursor, cursor + digits)
    if (value.length !== digits) return null
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
  return { type, segments }
}

const openBomDetailDialog = () => {
  if (!bom.value) return
  const derived = deriveBomDetailsFromCode(bom.value)
  bomDetails.value = derived
  bomDetailDialogVisible.value = true
}

const buildDocsPayload = () => ({
  product_docs: productDocsFromRoute.value.map((doc) => ({
    name: doc.name,
    path: doc.path,
    type: doc.type,
    summary: doc.summary,
  })),
  accessory_docs: accessoryDocGroupsFromRoute.value.map((group) => ({
    accessory: group.accessory,
    documents: group.documents.map((doc) => ({
      name: doc.name,
      path: doc.path,
      type: doc.type,
      summary: doc.summary,
    })),
  })),
})

const formatDocType = (type) => {
  if (type === 'image') return '图片'
  if (type === 'image_embedded') return '文档图片'
  return '文件'
}

const tab = ref('promo')

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
const pickManualImage = (path) => {
  const ok = window.confirm('是否更换图片?')
  if (!ok) return
  _manualPickPath = String(path || '')
  if (manualImageInputRef.value) manualImageInputRef.value.click()
}
const onPickManualImage = (e) => {
  const f = e?.target?.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    if (_manualPickPath) setByPath(manualRoot(), _manualPickPath, reader.result)
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

// 规格页导出
const promoRef = ref(null)
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
// 产品图片锚点（固定值）
const productAnchor = ref({ ...PRODUCT_ANCHOR })
const productInputRef = ref(null)
const backgroundInputRef = ref(null)

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
  _setSectionTitleOverride(key, html)
}

// 打开 RAG 来源调试面板
const openRagChunksDialog = () => {
  ragDialogVisible.value = true
  ragError.value = ''
  ragLoading.value = false
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
    _setPromoOverride(`Specifications.${idx}.${specKey}`, val)
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

// RAG 调试：规格页相关 chunks
const ragDialogVisible = ref(false)
const ragChunks = ref([])
const ragLoading = ref(false)
const ragError = ref('')
const selectedRagIndex = ref(0)
const selectedRagChunk = computed(() => {
  const list = ragChunks.value || []
  if (!list.length) return null
  const idx = Math.min(Math.max(selectedRagIndex.value, 0), list.length - 1)
  return list[idx]
})

const specsheetResultDialogVisible = ref(false)
const specsheetResultPayload = ref('')

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
    text: '[REDACTED]',
    image_base64: doc?.image_base64 ? '[IMAGE_BASE64]' : ''
  }))
}

const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif']

const inferMimeTypeFromPath = (path = '') => {
  const lower = String(path || '').toLowerCase()
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg'
  if (lower.endsWith('.webp')) return 'image/webp'
  if (lower.endsWith('.bmp')) return 'image/bmp'
  if (lower.endsWith('.gif')) return 'image/gif'
  return ''
}

const normalizeMimeType = (raw = '', path = '') => {
  const cleaned = String(raw || '').trim().toLowerCase()
  if (!cleaned) return inferMimeTypeFromPath(path)
  if (cleaned.includes('/')) return cleaned
  // 常见错误：前端传了 "image"，导致后端不会走 image/* 逻辑（从而把二进制 text 拼进 prompt）
  if (cleaned === 'image') return inferMimeTypeFromPath(path)
  if (cleaned === 'jpeg' || cleaned === 'jpg') return 'image/jpeg'
  if (cleaned === 'png') return 'image/png'
  if (cleaned === 'webp') return 'image/webp'
  if (cleaned === 'bmp') return 'image/bmp'
  if (cleaned === 'gif') return 'image/gif'
  return inferMimeTypeFromPath(path)
}

const looksLikeBinaryText = (value) => {
  if (typeof value !== 'string' || !value) return false
  const head = value.slice(0, 200)
  // JPEG/二进制特征：JFIF + 大量 \u0000 等不可见字符
  if (head.includes('JFIF')) return true
  return /\u0000/.test(head)
}

const getCurrentOcrDocuments = () => {
  const docs = []
  const normalizePath = (value) => {
    if (!value) return ''
    return String(value).replace(/^\/api\/files\//, '').replace(/^\/+/, '')
  }
  const pushDoc = (item) => {
    if (!item) return
    const normalizedPath = normalizePath(item.path)
    const rawMime = item.mime_type || item.mime || item.kind || item.type || ''
    const mimeType = normalizeMimeType(rawMime, normalizedPath)
    const isImage =
      (mimeType && mimeType.startsWith('image/')) ||
      IMAGE_EXTENSIONS.some((ext) => String(normalizedPath || '').toLowerCase().endsWith(ext))

    const rawText = item.text || ''
    const safeText = isImage || looksLikeBinaryText(rawText) ? '' : rawText
    docs.push({
      name: item.name,
      path: normalizedPath,
      type: item.type || 'document',
      summary: item.summary,
      mime_type: mimeType,
      text: safeText,
      image_base64: isImage ? '' : (item.image_base64 || '')
    })
  }

  productDocsFromRoute.value.forEach(pushDoc)
  accessoryDocGroupsFromRoute.value.forEach((group) => {
    group.documents.forEach(pushDoc)
  })

  return docs
}

const hydratePromoFromSpecsheet = (specsheetData, { fromSaved = false, chunks = [] } = {}) => {
  if (!specsheetData) return false

  promoData.value = JSON.parse(JSON.stringify(initialPromoData))

  if (specsheetData.productTitle) {
    promoData.value.productTitle = specsheetData.productTitle
  }
  if (specsheetData.features) {
    promoData.value.features = { ...specsheetData.features }
  }
  if (specsheetData.measurements) {
    promoData.value.measurements = specsheetData.measurements
  }
  if (specsheetData.premiumFeatures && specsheetData.premiumFeatures.length > 0) {
    promoData.value.premiumFeatures = [...specsheetData.premiumFeatures]
  }
  if (specsheetData.insulationFeatures && specsheetData.insulationFeatures.length > 0) {
    promoData.value.insulationFeatures = [...specsheetData.insulationFeatures]
  }
  if (specsheetData.extraFeatures && specsheetData.extraFeatures.length > 0) {
    promoData.value.extraFeatures = [...specsheetData.extraFeatures]
  }
  if (specsheetData.Specifications && specsheetData.Specifications.length >= 6) {
    promoData.value.Specifications = specsheetData.Specifications.map((spec) => {
      if (typeof spec === 'object' && !Array.isArray(spec)) {
        return { ...spec }
      }
      return spec
    })
  }
  if (specsheetData.smartWater && specsheetData.smartWater.length > 0) {
    promoData.value.smartWater = [...specsheetData.smartWater]
  }
  if (specsheetData.images) {
    promoData.value.images = { ...specsheetData.images }
    productPhotoSrc.value = specsheetData.images.product || productPhotoSrc.value
    backgroundSrc.value = specsheetData.images.background || backgroundSrc.value
  }

  ragChunks.value = fromSaved ? [] : chunks
  if (!specsheetInitialSnapshot.value) {
    specsheetInitialSnapshot.value = JSON.parse(JSON.stringify(promoData.value))
  }
  return true
}

const handleGenerateSpecsheetOcr = async () => {
  if (!productName.value || !bom.value) {
    window.alert('缺少产品名称或 BOM，无法生成规格页。')
    return
  }

  const documents = getCurrentOcrDocuments()
  if (!documents.length && !bom.value) {
    specsheetError.value = '请先在 BOM 详情页选择“生成产品手册”，并传入 OCR 文件后再生成规格页'
    return
  }

  loadingSpecsheet.value = true
  specsheetProgress.value = 0
  specsheetProgressStatus.value = ''
  specsheetLoadingText.value = '正在连接后端服务...'
  specsheetError.value = ''

  try {
    const { generateSpecsheetFromOcr } = await import('@/services/api')
    let progressInterval = null

    const startProgressInterval = () => {
      if (progressInterval) return
      progressInterval = setInterval(() => {
        if (specsheetProgress.value < 90) {
          specsheetProgress.value += 10
          if (specsheetProgress.value === 20) {
            specsheetLoadingText.value = '正在汇总 OCR 文档...'
          } else if (specsheetProgress.value === 40) {
            specsheetLoadingText.value = '正在向大模型发送请求...'
          } else if (specsheetProgress.value === 60) {
            specsheetLoadingText.value = '正在解析规格页数据...'
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

    const payload = {
      documents: documents.map((doc) => ({
        name: doc.name,
        path: doc.path,
        type: doc.type,
        summary: doc.summary || '',
        mime_type: doc.mime_type || '',
        text: doc.text || '',
        image_base64: doc.image_base64 || ''
      })),
      product_name: productName.value || '',
      bom_code: bom.value || '',
      bom_type: bomTypeForParsing.value || 'outdoor'
    }

    const result = await generateSpecsheetFromOcr(payload)
    const dialogPayload = {
      request: {
        documents: sanitizeRequestDocuments(payload.documents),
        product_name: payload.product_name,
        bom_code: payload.bom_code,
        bom_type: payload.bom_type
      },
      response: {
        ...sanitizeSpecsheetResult(result),
        prompt_text: result?.prompt_text || '',
        system_prompt: result?.system_prompt || ''
      }
    }
    specsheetResultPayload.value = JSON.stringify(dialogPayload, null, 2)
    specsheetResultDialogVisible.value = true

    clearProgressInterval()
    specsheetProgress.value = 90
    specsheetLoadingText.value = '正在处理数据...'

    const specsheetData = result?.specsheet || null
    const chunks = Array.isArray(result?.chunks) ? result.chunks : []
    const hydrated = hydratePromoFromSpecsheet(specsheetData, { chunks })
    if (!hydrated) {
      throw new Error('未获取到规格页数据')
    }

    specsheetProgress.value = 100
    specsheetProgressStatus.value = 'success'
    specsheetLoadingText.value = '加载完成！'
    setTimeout(() => {
      loadingSpecsheet.value = false
    }, 1000)
  } catch (error) {
    console.error('Failed to generate specsheet from OCR:', error)
    specsheetProgress.value = 100
    specsheetProgressStatus.value = 'exception'
    specsheetError.value = `生成失败: ${error.message || '未知错误'}`
    loadingSpecsheet.value = false
  }
}

// 加载规格页数据的函数
const loadSpecsheetData = async () => {
  // 如果缺少必要参数，不加载
  if (!productName.value || !bom.value) {
    return
  }
  
  loadingSpecsheet.value = true
  specsheetProgress.value = 0
  specsheetProgressStatus.value = ''
  specsheetLoadingText.value = '正在连接后端服务...'
  specsheetError.value = ''
  
  try {
    const { getSpecsheet } = await import('@/services/api')

    let specsheetData = null
    let usedSavedSpecsheet = false

    specsheetLoadingText.value = '正在检查已保存的规格页...'
    try {
      const savedSpecsheet = await getSpecsheet(productName.value, bom.value)
      if (savedSpecsheet) {
        specsheetData = savedSpecsheet
        usedSavedSpecsheet = true
      }
    } catch (error) {
      console.warn('Failed to load saved specsheet', error)
    }

    if (!specsheetData) {
      specsheetProgress.value = 100
      specsheetProgressStatus.value = 'exception'
      specsheetError.value = '未找到已保存的规格页，请点击“生成规格页（OCR）”'
      loadingSpecsheet.value = false
      ragChunks.value = []
      return
    }

    specsheetProgress.value = 90
    specsheetLoadingText.value = usedSavedSpecsheet ? '已加载保存的规格页' : '正在处理数据...'
    const hydrated = hydratePromoFromSpecsheet(specsheetData, { fromSaved: true })
    if (!hydrated) {
      throw new Error('未获取到规格页数据')
    }
    specsheetProgress.value = 100
    specsheetProgressStatus.value = 'success'
    specsheetLoadingText.value = '加载完成！'
    setTimeout(() => {
      loadingSpecsheet.value = false
    }, 1000)
  } catch (error) {
    console.error('Failed to load specsheet data:', error)
    specsheetProgress.value = 100
    specsheetProgressStatus.value = 'exception'
    specsheetError.value = `加载失败: ${error.message || '未知错误'}`
    loadingSpecsheet.value = false
    // Continue with default data if API call fails
  }
}

const saveSpecsheetToDb = async () => {
  if (!productName.value || !bom.value) {
    window.alert('缺少产品名称或 BOM 版本，无法保存规格页到数据库。')
    return
  }

  const ok = window.confirm('确定将当前规格页内容保存到数据库吗？')
  if (!ok) return

  try {
    // 动态引入 API，保持与 getSpecsheet 相同的风格
    const { saveSpecsheet } = await import('@/services/api')

    // 组装要保存的规格页数据
    const payload = {
      ...promoData.value,
      // 确保图片字段中包含当前画布使用的图片
      images: {
        ...(promoData.value.images || {}),
        product: productPhotoSrc.value || promoData.value.images?.product,
        background: backgroundSrc.value || promoData.value.images?.background,
      },
    }

    await saveSpecsheet(productName.value, bom.value, payload)

    window.alert('规格页已成功保存到数据库。')

    // 将当前界面状态作为最新快照，后续再载入时可与数据库保持一致
    specsheetInitialSnapshot.value = JSON.parse(JSON.stringify(promoData.value))
  } catch (error) {
    console.error('Failed to save specsheet:', error)
    window.alert(`保存规格页失败: ${error.message || '未知错误'}`)
  }
}

const savePosterToDb = async () => {
}

const saveManualToDb = async () => {
}

// 初始化图片与 promoData 同步
onMounted(() => {
  productPhotoSrc.value = promoData.value.images?.product || productPhotoSrc.value
  backgroundSrc.value = promoData.value.images?.background || backgroundSrc.value
})

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
      // - header: string 页面标题
      // - blocks: 数组 页面内容块
      //   · type: 'cover' 封面块
      //     - title: string 主标题/机型名
      //     - sizeText: string 尺寸说明
      //     - backSrc: string 背景图 URL（整页背景）
      //     - productSrc: string 产品主图 URL
      //
      // 页面 JSON 格式说明：
      // - header: 页面标题
      // - blocks: 页面内容块数组
      //   · type: 内容块类型
      //     - cover: 封面块
      //       · title: 主标题/机型名
      //       · sizeText: 尺寸说明
      //       · backSrc: 背景图 URL（整页背景）
      //       · productSrc: 产品主图 URL
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
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'paragraph', text, className? } 提示
      //   · { type: 'list', items: string[] } 安全要点（items 可含 HTML，如 <br/>、<ul>）
      header: 'Important Safety Instructions',
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
          "The wind baffle inside the back cover of the Balta's ventilation system is a consumable item. It has a magnetic strip on the back that adheres to the chiller. If it breaks, it does not affect its functionality.",
          'If the control panel displays the ER03 code, it indicates there is air in the pipes. The air should be released through the exhaust port on the filter.'
        ] },
        { type: 'divider' },
        { type: 'heading', text: 'Package List' },
        { type: 'image', src: '/instruction_book/package_list.png', fullWidth: true }
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
      blocks: [
        { type: 'heading', text: 'Touchscreen Control Panel' },
        { type: 'paragraph', text: 'Control Panel Installation Instructions' },
        { type: 'image', src: '/instruction_book/Touchscreen_Control_Panel.png', fullWidth: true, rotate: -90, marginTop: 240 }
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
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'troubleTable', headers, groups } 故障表
      //       headers: [string, string] 表头（症状/可能解决方案）
      //       groups: [{ title: string, items }]
      //         · items: 数组 { symptom: string, description?: string, solutions: string | string[] }
      header: 'Troubleshooting',
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
      // - header: string 页面标题
      // - blocks:
      //   · { type: 'heading', text } 标题
      //   · { type: 'troubleTable', headers, groups }（同上）
      header: 'Troubleshooting',
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
            { symptom: 'The temperature differs from what the thermometer shows', solutions: 'The internal temperature probe is calibrated to within 0.3° +/- . There could be an issue with the temperature sensor or PCB board.' }
          ]}
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
const currentPage = computed(() => manualPages.value[currentPageIndex.value])
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
onBeforeUnmount(() => {
  window.removeEventListener('resize', applyScale)
  if (ro) { try { ro.disconnect() } catch (e) {} ro = null }
})
watch(currentPageIndex, async () => { await nextTick(); applyScale() })
watch(userZoom, () => applyScale())
// 切换到“说明书”标签时重新计算缩放
watch(tab, async (v) => {
  if (v === 'manual') {
    await nextTick(); applyScale()
  }
})

const clamp = (v, min, max) => (v < min ? min : v > max ? max : v)
const incZoom = () => { userZoom.value = clamp((userZoom.value || 1) + 0.1, 0.5, 2) }
const decZoom = () => { userZoom.value = clamp((userZoom.value || 1) - 0.1, 0.5, 2) }
const resetZoom = () => { userZoom.value = 1 }

const goToPage = (pageNumber) => {
  const idx = clamp((pageNumber | 0) - 1, 0, (manualPages.value?.length || 1) - 1)
  currentPageIndex.value = idx
}
const deriveTitle = (page) => {
  const blks = page?.blocks || []
  if (page && page.customTitle) return page.customTitle
  const hd = blks.find(b => b.type === 'heading')
  if (hd && hd.text) return hd.text
  if (!blks.length) return 'Blank Page'
  if (blks[0].type === 'cover') return 'Cover'
  if (page && page.header) return page.header
  return 'Page'
}
const onEditManualPageTitle = (evt) => {
  const path = `pages.${currentPageIndex.value}.customTitle`
  onEditManualWithCaret(evt, path)
}
// Generate dynamic contents for the Contents page (list pages after the current page)
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
  return result.map(it => ({ title: it.title, page: it.page, level: 0, displayPage: displayTocPage(it.page) }))
}
// 左侧导航：合并固定 TOC 与实际页面数量，确保新增空白页也能显示在侧栏
const sidebarItems = computed(() => {
  const total = (manualPages.value || []).length
  return Array.from({ length: total }, (_, i) => ({
    page: i + 1,
    title: deriveTitle(manualPages.value[i] || {})
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
// 手册：路径读写工具
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
  const p = Number(pageIndex)
  const b = Number(blockIndex)
  return `pages.${p}.blocks.${b}` + (tail ? `.${tail}` : '')
}
// Root wrapper for manual pages editing using path that starts with 'pages.'
const manualRoot = () => ({ pages: manualPages.value })

// 手册：带光标保持的编辑（支持纯文本或富文本 innerHTML）
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
// 手册：可编辑式打印预览（与规格页相同方式）
const exportManualPdfEditable = async () => {
  const prevIndex = currentPageIndex.value
  const prevZoom = userZoom.value
  userZoom.value = 1
  await nextTick()

  // 收集当前页面样式（仅内联 <style>，已足够）；如有全局 link 样式需另行处理
  const styles = Array.from(document.querySelectorAll('style'))
    .map(s => s.outerHTML)
    .join('\n')

  // 构建每一页的 HTML
  let pagesHTML = ''
  for (let i = 0; i < (manualPages.value || []).length; i++) {
    currentPageIndex.value = i
    await nextTick()
    applyScale()
    const container = manualPagesRef.value
    const pageEl = container?.querySelector('.manual-page')
    if (!pageEl) continue
    // 临时置 1:1，确保输出排版不受 transform 影响
    const oldScale = container.style.getPropertyValue('--page-scale')
    container.style.setProperty('--page-scale', '1')
    await nextTick()
    pagesHTML += `<div class="print-page">${pageEl.outerHTML}</div>`
    if (oldScale) container.style.setProperty('--page-scale', oldScale)
  }

  // 创建隐藏 iframe，写入可打印 HTML，打开系统打印预览
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  document.body.appendChild(iframe)
  const doc = iframe.contentDocument || iframe.contentWindow.document
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${name.value} - Manual Print</title>
      <style>
        @page { size: A4 portrait; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        /* 每个容器严格占满一页，强制分页，避免被下一页覆盖或裁切 */
        .print-page { width: 210mm; height: 297mm; padding: 0; margin: 0; box-sizing: border-box; display: flex; justify-content: center; align-items: flex-start; overflow: hidden; page-break-after: always; break-after: page; }
        .print-page:last-child { page-break-after: auto; break-after: auto; }
        /* 覆盖手册页在打印中的尺寸与缩放，使用相对尺寸贴合父容器 */
        .print-page .manual-page { width: 100%; height: 100%; transform: none !important; border: none; margin: 0; box-shadow: none; overflow: hidden; }
        .print-page .page-inner { box-sizing: border-box; }
      </style>
      ${styles}
    </head>
    <body>
      ${pagesHTML}
      <script>
        window.addEventListener('load', () => { setTimeout(() => { window.focus(); window.print(); }, 50); });
        window.onafterprint = () => { setTimeout(() => { parent.document.body.removeChild(frameElement); }, 0); };
      <\/script>
    </body>
  </html>`
  doc.open(); doc.write(html); doc.close()

  // 状态还原
  currentPageIndex.value = prevIndex
  userZoom.value = prevZoom
  await nextTick(); applyScale()
}
// 导出整本说明书为 PDF（所有页面）
const exportAllManual = async () => {
  const prevIndex = currentPageIndex.value
  const prevZoom = userZoom.value
  // 导出时使用基准缩放，避免 transform 带来的模糊与裁切
  userZoom.value = 1
  await nextTick()

  const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
  const pageW = 210
  const pageH = 297

  for (let i = 0; i < manualPages.value.length; i++) {
    currentPageIndex.value = i
    await nextTick()
    applyScale()

    const node = manualPagesRef.value?.querySelector('.manual-page')
    if (!node) continue

    // 临时强制 1:1 截图
    const oldScale = manualPagesRef.value.style.getPropertyValue('--page-scale')
    manualPagesRef.value.style.setProperty('--page-scale', '1')
    await nextTick()

    const canvas = await html2canvas(node, { scale: 2, useCORS: true, backgroundColor: '#ffffff' })
    const imgData = canvas.toDataURL('image/jpeg', 0.92)
    const imgW = pageW
    const imgH = imgW * (canvas.height / canvas.width)
    if (i > 0) pdf.addPage('a4', 'p')
    const y = (pageH - imgH) / 2
    pdf.addImage(imgData, 'JPEG', 0, Math.max(0, y), imgW, imgH)

    // 还原缩放
    if (oldScale) manualPagesRef.value.style.setProperty('--page-scale', oldScale)
    await nextTick()
  }

  // 恢复状态
  currentPageIndex.value = prevIndex
  userZoom.value = prevZoom
  await nextTick()
  applyScale()

  // 打开打印预览而非直接下载
  try { pdf.autoPrint({ variant: 'non-conform' }) } catch (e) {}
  const blobUrl = pdf.output('bloburl')
  window.open(blobUrl, '_blank')
}
const addBlankPage = (index, pos) => {
  const insertAt = pos === 'before' ? index : index + 1
  const neighbor = manualPages.value[ pos === 'before' ? index : Math.max(0, index) ]
  const inferred = neighbor ? (neighbor.header || deriveTitle(neighbor) || 'Blank Page') : 'Blank Page'
  manualPages.value.splice(insertAt, 0, { header: inferred, blocks: [] })
  nextTick(() => {
    // 跳到新插入的空白页，保证侧栏与页眉同步
    goToPage(insertAt + 1)
  })
}
const deleteBlankPage = (index) => {
  const pg = manualPages.value[index]
  if (pg && (!pg.blocks || pg.blocks.length === 0)) {
    manualPages.value.splice(index, 1)
    nextTick(() => { goToPage(Math.max(1, index)) })
  }
}
const deleteAnyPage = (index) => {
  const pg = manualPages.value[index]
  if (!pg) return
  if (pg.blocks && pg.blocks.length > 0) {
    const ok = window.confirm('该页包含内容，确认删除？此操作不可撤销')
    if (!ok) return
  }
  manualPages.value.splice(index, 1)
  const nextIndex = Math.min(index, manualPages.value.length - 1)
  nextTick(() => { goToPage(Math.max(1, nextIndex + 1)) })
}
const imageStyle = (blk) => {
  const s = { objectFit: 'contain', maxWidth: '100%' }
  const isFloat = blk?.type === 'imageFloat' || (typeof blk?.type === 'string' && blk.type.startsWith('imageFloat-'))
  // 浮动图：完全由 CSS 控制，不应用默认 70% 宽度；普通图应用默认 70%
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
  position: 'absolute', inset: '0 0 0 0', /* 预留页脚高度 */
  background: `url(${blk.backSrc || '/instruction_book/back.jpg'}) center/cover no-repeat`
})
const loadScript = (src) => new Promise((resolve, reject) => {
  if (document.querySelector(`script[src="${src}"]`)) return resolve()
  const s = document.createElement('script')
  s.src = src
  s.onload = () => resolve()
  s.onerror = reject
  document.body.appendChild(s)
})

const exportPromo = async () => {
  await loadScript('https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js')
  const el = promoRef.value
  if (!el || !window.html2canvas) return
  const scale = Math.max(2, Math.ceil(window.devicePixelRatio || 1)) * 2
  const canvas = await window.html2canvas(el, { scale, backgroundColor: '#ffffff', useCORS: true })
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = `${name.value}-规格页.png`
  a.click()
}

// 可编辑（文本可选中）的 PDF：用隐藏 iframe，避免弹窗拦截
const exportPromoPdfEditable = () => {
  const el = promoRef.value
  if (!el) return
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
    .map(s => s.outerHTML)
    .join('\n')
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${name.value} - 可编辑PDF导出</title>
      <style>
        @page { size: A4 portrait; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        /* A4 页面满版，无任何边距 */
        .print-page { width: 210mm; height: 297mm; padding: 0; margin: 0; box-sizing: border-box; display: flex; justify-content: center; align-items: center; }
        /* 画布精确铺满 A4（promo-canvas 自身为 A4 比例） */
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

const exportPromoPdf = async () => {
  await loadScript('https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js')
  await loadScript('https://unpkg.com/jspdf@2.5.1/dist/jspdf.umd.min.js')
  const el = promoRef.value
  if (!el || !window.html2canvas || !window.jspdf) return
  const scale = Math.max(2, Math.ceil(window.devicePixelRatio || 1)) * 2
  const canvas = await window.html2canvas(el, { scale, backgroundColor: '#ffffff', useCORS: true })
  const imgData = canvas.toDataURL('image/png')
  const { jsPDF } = window.jspdf
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const imgWidth = pageWidth
  const imgHeight = (canvas.height / canvas.width) * imgWidth
  const y = (pageHeight - imgHeight) / 2 < 0 ? 0 : (pageHeight - imgHeight) / 2
  pdf.addImage(imgData, 'PNG', 0, y, imgWidth, imgHeight)
  pdf.save(`${name.value}-规格页.pdf`)
}

// 海报导出：按屏幕显示的像素尺寸一模一样导出
const posterRef = ref(null)
const exportPoster = async () => {
  await loadScript('https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js')
  const el = posterRef.value
  if (!el || !window.html2canvas) return
  // 提高分辨率：按 A4 横向长边 3508px 计算放大倍数（2x~5x）
  const rect = el.getBoundingClientRect()
  const targetLongSide = 3508
  const computedScale = targetLongSide / Math.max(1, rect.width)
  const scale = Math.min(5, Math.max(2, computedScale))
  // 导出期间应用无缝样式，避免渐变造成 1px 黑线
  el.classList.add('exporting')
  await nextTick()
  let canvas
  try {
    // 将顶部渐变并入背景图，避免多层叠加边界
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

    canvas = await window.html2canvas(el, { scale, backgroundColor: '#ffffff', useCORS: true })

    if (bgEl) bgEl.style.backgroundImage = bgEl.dataset.prevBg || prevBg
    if (maskEl) maskEl.style.display = ''
  } finally {
    el.classList.remove('exporting')
  }
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = `${name.value}-海报.png`
  a.click()
}
const exportPosterPdf = () => {
  const el = posterRef.value
  if (!el) return
  // Use standard A4 landscape to avoid driver ignoring custom sizes
  let pageWmm = 297
  let pageHmm = 210
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
    .map(s => s.outerHTML)
    .join('\n')
  const html = `<!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>${name.value} - 海报PDF导出</title>
      ${styles}
      <style>
        /* Standard A4 landscape with no margins */
        @page { size: ${pageWmm}mm ${pageHmm}mm; margin: 0; }
        html, body { height: 100%; margin: 0; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #fff; }
        .print-page { width: ${pageWmm}mm; height: ${pageHmm}mm; padding: 0; margin: 0; box-sizing: border-box; position: relative; }
        /* Fill the entire page and override on-screen aspect ratio */
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

// 简易 contenteditable 同步到 promoData（支持路径 a.b.c）
const onEditText = (path, evt) => {
  const val = evt?.target?.innerText ?? ''
  const segs = path.split('.')
  let obj = promoData.value
  for (let i = 0; i < segs.length - 1; i++) {
    const k = segs[i]
    if (!(k in obj) || typeof obj[k] !== 'object') obj[k] = {}
    obj = obj[k]
  }
  obj[segs[segs.length - 1]] = val
}

// 列表项键盘事件处理（回车添加新项，Backspace删除空项）
const onListItemKeydown = (evt, path, index) => {
  if (evt.key === 'Enter') {
    evt.preventDefault()
    // 在当前项后插入新条目
    const segs = path.split('.')
    let obj = promoData.value
    for (let i = 0; i < segs.length - 1; i++) {
      const k = segs[i]
      if (!(k in obj)) obj[k] = {}
      obj = obj[k]
    }
    const key = segs[segs.length - 1]
    if (Array.isArray(obj[key])) {
      obj[key].splice(index + 1, 0, '')
      // 下一帧聚焦到新条目
      nextTick(() => {
        const li = evt.target.closest('li')
        if (li && li.nextElementSibling) {
          const span = li.nextElementSibling.querySelector('[contenteditable]')
          if (span) {
            span.focus()
            // 将光标移到开头
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
    const text = el.innerText || ''
    // 如果当前项为空且不是唯一项，则删除
    if (text.trim() === '') {
      const segs = path.split('.')
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
        // 聚焦到前一项或后一项
        nextTick(() => {
          const li = evt.target.closest('li')
          const target = li?.previousElementSibling || li?.nextElementSibling
          if (target) {
            const span = target.querySelector('[contenteditable]')
            if (span) {
              span.focus()
              // 将光标移到末尾
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

// 带光标位置保持的编辑函数
const onEditTextWithCaret = (evt, path) => {
  const el = evt?.target
  if (!el) return
  // 保存光标位置
  const selection = window.getSelection()
  let caretOffset = 0
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(el)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    caretOffset = preCaretRange.toString().length
  }
  // 更新数据
  const val = el.innerText ?? ''
  const segs = path.split('.')
  let obj = promoData.value
  for (let i = 0; i < segs.length - 1; i++) {
    const k = segs[i]
    if (!(k in obj) || typeof obj[k] !== 'object') obj[k] = {}
    obj = obj[k]
  }
  obj[segs[segs.length - 1]] = val
  _setPromoOverride(path, val)
  // 下一帧恢复光标位置
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
      // 光标恢复失败，忽略
    }
  })
}

const resetPromo = () => {
  // 优先使用后端返回的初始规格页快照；若无则回退到内置模板
  const base = specsheetInitialSnapshot.value || initialPromoData

  // 重置所有 JSON 数据
  promoData.value = JSON.parse(JSON.stringify(base))

  // 重置产品与背景图片
  const imgBase = base.images || initialPromoData.images
  productPhotoSrc.value = imgBase.product
  backgroundSrc.value = imgBase.background

  // 重置产品锚点为固定值
  productAnchor.value = { ...PRODUCT_ANCHOR }

  // 重置 Feature 区图标为默认资源
  featureIcons.value = {
    capacity: '/product_standard/Capacity.png',
    jets: '/product_standard/Jets.png',
    pumps: '/product_standard/Pumps.png',
    measurements: '/product_standard/Measurements.png',
  }

  // 重置二级标题为初始文案
  promoSectionTitles.value = {
    premium: 'Premium<br>Lighting System',
    insulation: 'Energy-Saving<br>Insulation System',
    extra: 'Extra Features',
    specifications: 'Specifications',
    smartWater: 'Smart Water<br>Purification System',
  }
}

// 在组件挂载后记录各可编辑区域的初始 HTML
onMounted(() => {
  nextTick(() => {
    if (!promoRef.value) return
    const editable = promoRef.value.querySelectorAll('[contenteditable="true"]')
    editable.forEach((el) => {
      _editableInitHTML.set(el, el.innerHTML)
    })
  })
})

// 海报：带光标位置保持的编辑函数（写入 posterData，支持路径 a.b.c）
const onEditPosterWithCaret = (evt, path) => {
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
  const val = el.innerText ?? ''
  const segs = path.split('.')
  let obj = posterData.value
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

const imgUrl = computed(() => `/product/${image.value}`)
const onImgError = (e) => { e.target.src = '/favicon.ico' }
const goBack = () => router.back()
const printManual = () => {
  // 提示用户打印设置中勾选“背景图形”以保留封面背景
  try {
    window.print()
  } catch (e) {}
}

// 交互：点击更换图片
const onClickProduct = () => {
  productDialogTab.value = 'local'
  productDialogVisible.value = true
}
// 阈值：当宽/高 > ROTATE_RATIO 时旋转 90°（顺时针）
const ROTATE_RATIO = 1.3
const loadAndMaybeRotate = (file, cb) => {
  const reader = new FileReader()
  reader.onload = () => {
    const url = reader.result
    const img = new Image()
    img.onload = () => {
      const w = img.naturalWidth, h = img.naturalHeight
      if (w / h > ROTATE_RATIO) {
        const canvas = document.createElement('canvas')
        canvas.width = h
        canvas.height = w
        const ctx = canvas.getContext('2d')
        ctx.translate(h, 0)
        ctx.rotate(Math.PI / 2)
        ctx.drawImage(img, 0, 0)
        cb(canvas.toDataURL('image/png'))
      } else {
        cb(url)
      }
    }
    img.onerror = () => cb(url)
    img.src = url
  }
  reader.readAsDataURL(file)
}
const onPickProduct = (e) => {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  loadAndMaybeRotate(f, (res) => {
    productPhotoSrc.value = res
    if (!promoData.value.images) promoData.value.images = {}
    promoData.value.images.product = res
    // 本地上传完成后关闭弹框
    if (productDialogVisible.value) productDialogVisible.value = false
  })
  e.target.value = ''
}
const onClickBackground = () => {
  const ok = window.confirm('是否更换背景图片?')
  if (ok && backgroundInputRef.value) backgroundInputRef.value.click()
}
const onPickBackground = (e) => {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    backgroundSrc.value = reader.result
    if (!promoData.value.images) promoData.value.images = {}
    promoData.value.images.background = reader.result
  }
  reader.readAsDataURL(f)
  e.target.value = ''
}

const onClickLogo = () => {
  const ok = window.confirm('是否更换商标 Logo 图片?')
  if (ok && logoInputRef.value) logoInputRef.value.click()
}
const onPickLogo = (e) => {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    logoSrc.value = reader.result
    if (!promoData.value.images) promoData.value.images = {}
    promoData.value.images.logo = reader.result
  }
  reader.readAsDataURL(f)
  e.target.value = ''
}

// 产品图片选择弹框状态与逻辑
const productDialogVisible = ref(false)
const productDialogTab = ref('local')
const kbProductImages = ref([
  { src: '/product/Alta.png', label: 'Alta' },
  { src: '/product/BO-01.png', label: 'BO-01' },
  { src: '/product/IRIS-D.png', label: 'IRIS-D' },
  { src: '/product/Vattern-Grey+Marble White-T-250701-1.png', label: 'Vattern Grey + Marble White' },
])

const triggerLocalProductUpload = () => {
  if (productInputRef.value) productInputRef.value.click()
}

const selectKbProductImage = (src) => {
  if (!src) return
  productPhotoSrc.value = src
  if (!promoData.value.images) promoData.value.images = {}
  promoData.value.images.product = src
  productDialogVisible.value = false
}
</script>

<style scoped>
@font-face {
  font-family: 'AgencyFB-Bold';
  src: url('/fonts/AgencyFB-Bold.woff2') format('woff2'),
       url('/fonts/AgencyFB-Bold.woff') format('woff');
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}
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

.promo-block.promo-editable {
  cursor: move;
}
.promo-block.promo-editable.promo-selected {
  outline: 2px solid rgba(64, 158, 255, 0.9);
  outline-offset: 2px;
}
.promo-block.promo-editable:hover {
  outline: 1px dashed rgba(64, 158, 255, 0.7);
  outline-offset: 2px;
}

.promo-props-panel {
  position: absolute;
  right: 10px;
  top: 10px;
  width: 230px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  z-index: 999;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}
.promo-props-panel .props-title {
  font-weight: 700;
  margin-bottom: 8px;
}
.promo-props-panel .props-empty {
  color: #6b7280;
  font-size: 12px;
}
.promo-props-panel .props-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 8px 0;
}
.promo-props-panel .props-label {
  font-size: 12px;
  color: #374151;
  min-width: 44px;
}
.promo-props-panel .props-value {
  font-size: 12px;
  color: #111827;
  word-break: break-all;
  text-align: right;
}
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
.product-photo { position: absolute; left: var(--product-x, 78%); top: var(--product-y, 22%); transform: translate(-50%, -50%); width: auto; height: auto; max-width: 380px; max-height: 420px; object-fit: contain; filter: drop-shadow(0px 5px 5px rgba(0,0,0,0.5)); z-index: 5; pointer-events: auto; cursor: pointer; }
.right-col { padding-top: 230px; padding-left: 30px; position: relative; z-index: 3; }

/* Manual layout */
.manual-layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; min-height: 600px; align-items: start; }
.manual-toc { position: sticky; top: 16px; align-self: start; height: calc(100vh - 32px); padding: 12px; border: 1px solid #ebeef5; border-radius: 10px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.02); display: grid; grid-template-rows: auto auto auto 1fr; gap: 12px; }
.toc-title { font-weight: 700; margin-bottom: 8px; }
.toc-scroll { overflow: auto; padding-right: 6px; }
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
